# Local measurements, 2026-09-19

Machine: Linux x86_64 (Arch, kernel 7.1.9), Zig 0.16.0 (bundled clang 21.1.0),
system clang/LLVM 22.1.8, A7 at master with the working tree of this session.
All commands run from the repository root unless a `cd` is shown.
Artifacts under `tmp/research/optimization/measure/`.

## M1. Zig 0.16.0 has no PGO flag for Zig-language code

    $ zig build-exe --help | grep -ic profile
    0
    $ zig cc --help | grep -E 'fprofile-(generate|use)'
    -fprofile-generate=<directory>
    -fprofile-generate      Generate instrumented code to collect execution counts into default.profraw ...
    -fprofile-use=<pathname>

`zig build-exe --help` contains the string "profile" zero times. `-flto`,
`-fstrip`, `--emit-relocs`, `-femit-llvm-ir`, `-femit-llvm-bc` and
`-fopt-bisect-limit` are present.

## M2. BOLT's documented precondition is satisfiable for an A7 binary

    $ zig build-exe bench2.zig -OReleaseFast --emit-relocs -femit-bin=bench2.relocs
    $ readelf -S bench2.relocs | grep -c RELA
    9

`llvm-bolt` is not installed on this machine and `perf` is not either, so BOLT
itself was not run. Only the precondition was checked.

## M3. Binary size at four Zig optimization levels (four A7 examples)

| Example | Debug | ReleaseSafe | ReleaseFast | ReleaseSmall |
| --- | --- | --- | --- | --- |
| 029_sorting | 10,268,557 | 3,802,992 | 3,829,768 | 146,672 |
| 032_prime_numbers | 10,267,896 | 3,798,104 | 3,829,984 | 146,688 |
| 035_matrix | 12,135,202 | 3,834,152 | 3,850,040 | 151,224 |
| 037_language_tour | 12,086,349 | 3,817,024 | 3,854,400 | 148,408 |

ReleaseFast is *larger* than ReleaseSafe in all four. Size at this program size
is dominated by the Zig standard library's panic, DWARF and Io machinery, not by
A7's own emitted code, so size is not a usable discriminator here.

`size -A 032_prime_numbers.<mode> | awk '/\.text/'`: Debug 2,128,314;
ReleaseSafe 404,809; ReleaseFast 421,769; ReleaseSmall 91,864.

## M4. What Zig's runtime safety checks cost, measured

`bench.a7` (trial division, no arrays) and `bench2.a7` (4096-element array,
200000 passes, accumulate into i64). Wall clock, `subprocess.run` around the
binary, n=5 (bench) / n=9 (bench2), min and median in seconds.

| Binary | min | median |
| --- | --- | --- |
| bench Debug | 1.026 | 1.052 |
| bench ReleaseSafe | 0.727 | 0.743 |
| bench ReleaseFast | 0.721 | 0.735 |
| bench ReleaseSmall | 0.706 | 0.727 |
| bench2 Debug | 1.245 | 1.259 |
| bench2 ReleaseSafe | 0.165 | 0.166 |
| bench2 ReleaseFast | 0.0807 | 0.0991 |
| bench2 ReleaseSmall | 0.178 | 0.180 |

Attribution, bench2: editing the emitted Zig's `acc += buf[k]` to the wrapping
`acc +%= buf[k]` and rebuilding at **ReleaseSafe** gives min 0.080 s, median
0.085 s — i.e. it closes the whole ReleaseSafe/ReleaseFast gap. The gap is the
**integer overflow check on the accumulator**, not the bounds check on `buf[k]`.

## M5. A7 compiles deterministically under varied hash seeds

All 43 files in `examples/` compiled at `PYTHONHASHSEED` 1, 2, 3 and 12345;
every pair of emitted `.zig` files compared with `cmp`.

    examples with hash-seed-dependent output: 0

This is the test `docs/plan/memory.md` gate M40 proposes. It passes on the
current example set. It is an absence over 43 programs, not a proof.

## M6. Proof-gated emission sites in the backend

    $ grep -n _require_backend_approval a7/backends/zig.py
    1319: "deref"   1326: op.name.lower()   1607: op.name.lower()
    1692: "index"   1710: "slice"   1736: "deref"   1750: "deref"   1773: "cast"

Eight call sites; operations `deref`, `index`, `slice`, `cast` and the binary
operators (division, remainder). `BackendPlan.require` (a7/safety.py:214-218)
raises unless `SafetyProofPass` approved that exact node for that exact
operation; the key is `(id(node), operation)`.

## M7. Build loop, re-measured

`examples/037_language_tour.a7`, 143 lines, min/median of 5:

| Step | min | median |
| --- | --- | --- |
| `uv run a7 ... --mode pipeline` | 0.186 | 0.199 |
| `uv run a7 ... --output /tmp/tour.zig` | 0.118 | 0.126 |
| `zig build-exe /tmp/tour.zig` | 0.220 | 0.246 |

Faster than the 0.262 s + 0.298 s recorded in
`docs/plan/research/runtime-model/00-claims-audit.md` on 2026-09-18; same order.

## M8. A complete instrumented-PGO loop does run on A7 output

Sequence that worked (2026-09-19):

    zig build-exe bench2.zig -OReleaseFast -lc -femit-llvm-bc=bench2c.bc -femit-bin=bench2c.tmp
    clang -O3 -fprofile-generate bench2c.bc -o bench2.instr3        # clang 22.1.8
    LLVM_PROFILE_FILE=b2b.profraw ./bench2.instr3
    llvm-profdata merge -output=b2b.profdata b2b.profraw
    clang -O3 -fprofile-use=b2b.profdata bench2c.bc -o bench2.pgo

Both binaries print `acc = 819200000`, the same as `bench2.ReleaseFast`.

Timing (n=7-9): `bench2.noPGO` (clang -O3, no profile) min 0.0254 / median
0.0380; `bench2.pgo` min 0.0249 / median 0.0269. **No measurable PGO gain.**
The benchmark is one hot loop with no branch-layout or inlining opportunity, so
this is a statement about the benchmark, not about PGO.

Three failures on the way, each an adoption cost:

1. `zig cc -fprofile-generate bench2.bc` fails with `duplicate symbol: _start`
   (glibc `crt1.o` against `std/start.zig:190`) unless the module is built with
   `-lc` so Zig uses the libc entry path.
2. Linking against `libclang_rt.profile-x86_64.a` produces `__llvm_prf_cnts` and
   `__llvm_prf_names` sections but writes **no** `.profraw`: the runtime's
   registration symbols are never pulled from the archive. `-u__llvm_profile_runtime`
   fixes it.
3. `zig cc -fprofile-use` on a profile indexed by the host `llvm-profdata` fails:
   `unsupported instrumentation profile format version` — Zig 0.16.0 bundles
   clang 21.1.0, the host tools are LLVM 22.1.8, and `llvm-profdata merge` has no
   version-downgrade flag. The loop completes only by leaving the Zig driver
   entirely and using the host clang for both halves.

## M9. One benchmark-specific codegen gap, not a general result

`clang -O3` re-optimizing the module Zig itself emitted is 3.2x faster than
`zig build-exe -OReleaseFast` on bench2 (0.0254 vs 0.0807 min) and **slower** on
bench (0.774 vs 0.758 min). Neither binary contains the folded constant
`$0x30d40000`, so neither computed the answer at compile time. Cause not
isolated; not used as evidence for any claim. A second full -O3 over an
already-optimized module is not a normal build configuration.

## M10. Two A7 defects found while writing the benchmarks (incidental)

1. **Shadow-rename miscompile.** `tmp/research/optimization/measure/bench2_shadow.a7`
   (a `for i := ...` loop inside a block where an earlier sibling block also
   declared `i`) emits `var i_1 = @as(usize, 0); while ((i < 4096)) : (i += 1)`.
   The declaration is renamed and the uses are not. A7 exits 0; `zig build-exe`
   rejects it: `error: use of undeclared identifier 'i'`. Visible failure, not a
   silent one.
2. **Loop-variable type inference ignores the comparand.** In
   `sum_primes(limit: i64)`, `for n := 2; n <= limit; n += 1` emits
   `var n: i32 = 2` and compares an `i32` against an `i64`.

Neither is this report's subject; both are recorded here because they were
produced by it.
