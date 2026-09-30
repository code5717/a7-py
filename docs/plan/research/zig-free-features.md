# Free features from Zig, and what an x86 backend must reproduce

Status: advisory research, 2026-09-30. No report approves a language change,
verifies an implementation, or qualifies a release. User decisions live in
`docs/plan/decisions.md`.

Scope: user asked to document every feature A7 gets for free by emitting Zig
instead of machine code, then observed that a direct x86 backend could
reproduce all of it. This file lists the free features with evidence, then
prices the reproduction claim item by item. Code claims cite `a7-py` files
and lines checked 2026-09-30. Optimizer behavior claims are inference from
LLVM documentation unless marked otherwise.

## The Zig hop today

```
A7 source -> tokenizer/parser/semantic/proofs (Python)
           -> Zig source (a7/backends/zig.py)
           -> zig build-exe -O Debug|ReleaseFast (a7/cli.py:135)
           -> native binary
```

Zig is pinned to 0.16.0 (`a7/toolchain.py:8`). The artifact gates validate
emitted Zig with `zig ast-check` and `zig fmt --check`
(`scripts/build_examples.py:106-112`). Decision L43 keeps the Python compiler
and the Zig backend for V1 (`docs/plan/decisions.md:122`).

## The free features

### 1. The LLVM optimizer (ReleaseFast)

Inlining, common-subexpression elimination, loop-invariant code motion,
loop unrolling, SLP and loop vectorization, strength reduction, instruction
scheduling, register allocation. A7's emitter does none of these; it emits
straight-line Zig and LLVM does the work.

The wins measured on 2026-09-30 show the split of labor: the 5.7x print
speedup came from A7's own buffered writer, the 190x allocator speedup from
A7's allocator choice, and the 23% vector_ops speedup from A7 proving
non-wrapping arithmetic so LLVM regains `nsw` facts
(`bench/pins/cx89.json`). A7 owns the semantics; LLVM owns the instruction
quality.

### 2. Debug lane runtime checks

Debug builds carry Zig's safety net: array index bounds checks, `@intCast`
narrowing traps, slice bounds, and panic stack traces with source locations.
A7's proof planning discharges statically what it can
(`a7/safety.py:215-224`); Zig Debug catches the residue at run time. README
states the honest limit: ReleaseFast establishes no complete memory safety.

### 3. Builtins that lower to optimal machine code

The backend emits Zig builtins and LLVM picks the instructions
(`a7/backends/zig.py`): `@divTrunc` and `@rem` (zig.py:1549, 1854; LLVM
fuses shared div+rem), `@intCast` for narrowing and widening, `@bitCast`
for bit reuse, `@abs`, `@intFromFloat`/`@floatFromInt`/`@floatCast` for
float conversions, `@Vector` for SIMD array math (zig.py:1588), and the
stdlib math surface `@sqrt @abs @floor @ceil @sin @cos @tan @log @exp @min
@max` (`a7/stdlib/math.py:10-22`). `@sqrt` lowers to hardware `sqrtss` on
x86-64 (inference from LLVM lowering rules).

### 4. Struct layout and calling convention

Zig computes field offsets by alignment-sorted packing
(`a7/layout.py`, verified against `@offsetOf` on Zig 0.16.0), rounds sizes
to alignment, and passes struct values under the platform ABI. A7 emits
plain declarations and inherits both.

### 5. Runtime pieces emitted into the preamble

The generated program leans on `std.Io.File.writerStreaming` for buffered
stdout (zig.py:213), `std.heap.smp_allocator` in release and
`page_allocator` in debug (zig.py:183, 185), `std.process.Init` for the
main wrapper, and `catch @panic` failure paths with stack traces (zig.py:
192-204).

### 6. Toolchain surface

`zig ast-check` and `zig fmt --check` act as free validators of emitted
code in the artifact gates. `zig build-exe` links, strips, and produces the
binary. Cross-compilation to every LLVM target, static linking, and musl or
glibc selection exist behind one `-target` flag that A7 does not expose
(a7/cli.py:135 passes only `-O` and `-femit-bin`).

## Pricing the x86 claim

User claim: an x86 backend can reproduce it all. Item by item:

| Free feature | Reproduction cost |
| --- | --- |
| Builtins to instructions | Small: an instruction-selection table for the x86-64 subset. `@bitCast` free, casts one instruction, div+rem one fusion rule. |
| Struct layout, SysV ABI | Small: layout already computed in `a7/layout.py`; SysV call rules are documented. |
| Runtime pieces | Medium: buffered writer, allocator, panic path. The allocator choice and writer already exist as A7 decisions; porting them is bounded work. |
| Debug checks, stack traces | Medium: emit bounds checks and trap lines; traces need frame data. |
| Register allocation | Large: linear-scan on straight-line A7 code is enough for loops over locals, but is its own project. |
| Loop opts, vectorization, CSE, unrolling | Large: this is LLVM proper. A minimal set (div/rem fusion, strength reduction, loop SIMD for the `@Vector` path) covers most measured A7 code shapes, but the ceiling is far lower. |
| Cross-target, libc linking | Large: a linker story plus libc headers. Zig embeds this; A7 would re-enter that business. |
| `ast-check`/`fmt` validation | None: the check disappears with the Zig output it validates; the assembler takes over. |

Verdict: the language-visible features are reproducible; the performance
features are reproducible only to the level of a simple optimizing backend.
The 2026-09-30 bench results support this: the largest measured wins came
from A7-level decisions (buffering, allocator, proof-driven arithmetic), not
from LLVM passes that a simple backend would miss. Unverified: how much of
the six-bench suite a naive backend matches. The instrument to answer it
already exists: any new backend must hold `scripts/bench_perf.py` pins
within the 1.15 gate ratio before it can replace Zig.

## Recommendation

Keep the Zig backend for V1 per decision L43. Treat a direct x86 backend as
a V2+ experiment with one acceptance rule: parity with
`scripts/bench_perf.py` pins on the same host, plus identical e2e golden
outputs. Do not start it before the Phase 1-3 items in
`cpu-memory-dop.md`, which deliver measured wins without a backend rewrite.
