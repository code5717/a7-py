# A7 language needs: read-over index (00)

Scope: one row per feature area across files 01–21 plus two in-chat
findings (Lexical §2, Tensors §9). Verdicts repeat each file's own
verdict; no new behavior is approved here.

## Direction

Small compiler core, fat standard library. Sockets, TLS, HTTP, JSON,
time, rand, GPU kernels are library code over OS/native calls, not
syntax. The compiler grows no network, crypto, regex, or kernel
primitives (10, 16, 18–21).

## Tooling: parked as a separate futuristic project

Excluded from language scope; tracked apart, not in the table below:

- `a7 fmt` (canonical layout, `--check`) and `a7 test` (file discovery,
  per-file pass/fail) — G6 decision, P-MOD does not cover (07).
- `a7 doc` rendering + `///` doc comments — pure tooling, no language
  risk (07, 15).
- `test "..." {}` blocks + runner + `assert` — needs comptime steps
  1–5 first; script tests until then (13).
- `a7 fix` edition migration rewrites — only at first approved break (16).
- Backtraces/debug-info track — boundary is now (values vs abort),
  traces later (15).
- `-vgc`-style hidden-allocation audit flag — after memory story lands (12).

## How to read the table

Each row: what the area is; how Zig / Odin / Rust / Jai / C handle it
(compact, `—` where a language has no analog); NEED NOW (V1-blocking),
LATER (gated future work), or NEVER (refused); gate that must decide it.
`none` means a pure bug fix or locked decision.

| # | Area | What it is | Zig / Odin / Rust / Jai / C | Verdict + reason | Gate |
|---|------|-----------|------------------------------|------------------|------|
| 01a | Reversed match ranges | `case 10..1` silently normalizes; must reject const, document dynamic-empty | Zig errors / Rust empty-iter / C n/a / Odin empty / Jai n/a | NEED NOW — silent never-match is a correctness hole | none (bug fix) |
| 01b | `break` in match-in-loop | Unlabeled `break` in a case arm exits the lowered `switch`, not the loop | C/Zig same trap / Rust needs label / Go labeled break | NEED NOW — wrong control flow, reject or label | none (bug fix, note in SPEC) |
| 01c | Div/neg/shift overflow | `MIN/-1`, `-MIN`, overshift: trap vs wrap unstated across fold, proof, backend | Zig traps / Rust panics-debug wraps-release / C UB / Odin mode-dependent | NEED NOW once decided — pick trap (matches backend) | G3 |
| 02 | Payload matching + exhaustiveness | `.tag(bind)` tests discriminant and binds payload; missing tags are exit-6 | Zig `switch` exhaustive / Rust `match` exhaustive / Odin silent fallthrough / Jai convention | NEED NOW — ends silent whole-value capture trap | G5 (order: 7a before 7b) |
| 02b | Option/Result + `?` + recoverable I/O | Stdlib generic unions, exact-type `?` propagation, `*_ok` I/O beside panicking helpers | Rust `?`+`From` (A7: no conversion) / V `?`+`or{}` / Gleam `use`+`Result` / Zig error unions | NEED NOW (7a) then LATER (7b I/O) — `get`/`pop` need it | G5, M33, M49 |
| 15a | Match guards | Optional `if` after pattern, first match+guard wins, side-effect free | Rust/Zig/Odin have guards / D,C++ n/a | NEED NOW — small, composes with 02 match work | G5 |
| LEX | Lexical §2 fixes | UTF-8+BOM, `;`, `#`, `_`-leading, `@`/`$`, `...`, prefixes, exponents, chars, multiline strings, `xFF`, 32767 limit, stale §12 list | Per-language lexer detail, no design split | NEED NOW — doc/code mismatches, all small | none |
| 03 | Owning collections | `String` vs `string` view, `List`/`Map`/`Table`/`Id`, derived `Eq`+`Hash`, one default hash | Zig explicit-allocator maps / Odin builtin map+Builder / Rust `String`/`Vec`/`HashMap` / Go GC builtins | NEED NOW in order (Option→String→List→hash→Map→Table→stdlib) — V1 library core | G5, M1/M5/M13/M33/M39, L42 |
| 14a | Format freeze + capacity + int-range for | Keep `{}`+escapes comptime-only; decide len/cap/growth before `List`; add `for i in 0..n` + adapters | Zig comptime `std.fmt` / Rust full grammar / Go `%v` verbs / Python f-strings | NEED NOW — shipped behavior + `List` blockers | G3 (casts), M2/M13/M39 |
| 14b | Surface refusals | No `$"..."` interpolation, no v1 overloading, no map literal yet, no iterator protocol yet | Non-GC langs refuse both except via traits; ranges start builtin-only | NEVER (interp/overload-v1) / LATER rest — simplicity stance | none now; traits later |
| 04a | Generics: enums/unions + conflict error | Monomorphize generic enums/unions like structs; conflicting `$T` binds are errors | Zig duck-types / C++ ambiguity-is-error / D patterns-rank | NEED NOW — pure implementation, no syntax | none |
| 04b | Generics: `$N`, `where`, specialization, fn-values | Value params, minimal `where`, exact-beats-generic, explicit instantiation syntax | Zig `comptime N` / Odin `where` / Rust traits / D patterns-rank-predicates-filter | LATER — each needs a user spelling decision | user gates per item |
| 13 | Comptime + reflection | `comptime` blocks, mini-CTFE, `fields`/`field`/`typeName`/`compiles`/`compileError`, `comptime for`, `$N` | Zig comptime+`@typeInfo` / D CTFE / Nim macros (reject) / Odin `when` (too weak) / Rust `const fn` | NEED NOW except `test` blocks, `@Type`, macros (LATER/NEVER) — unlocks `$N`, `where`, serialization | joint with 04 |
| 05 | Numerics packets D1–D6 | Typed-vs-`::` fold routing; `MIN/-1`; oversized shifts; narrowing-cast proof; float→int path; ReleaseFast backstop | Zig trap/UB split / Rust panic-or-saturate / C UB / Odin confirm | NEED NOW once decided — fail-closed until each packet lands | G3 (D1–D4,D6), G1 (D5) |
| 06 | Memory mechanism B1 vs B2 | Arena extents vs refcount behind one flag; aliasing holes open; 7 bench shapes decide | Zig allocator taxonomy / Odin per-scope allocator / Jai scoped reset / Rust exclusivity (no lifetimes in A7) | LATER — B3 measures, packet + user decision selects | memory packet, L38/L39 |
| 07 | Modules + visibility | `_name` private (L27), fields always visible (L29), keep cycle rejection, drop `mod.a7` fallback | Zig `pub`-per-file / Odin private-by-attr / Go uppercase / Rust `pub(crate)` | NEED NOW — enforce already-locked L25/L27/L29/L54 | P-MOD + G6 |
| 08 | Native boundary + release | Minimal C interface via Zig (handles, no raw pointers), explicit-branch checks surviving ReleaseFast, tier matrix | Zig `extern`+4 modes / Odin separate check flags / Rust `unsafe`+per-check toggles | LATER design (descriptors now) — V1 is Zig-only CPU | L39/L41 |
| 09a | Concurrency tasks/channels | Structured groups, cancellation, join outcomes, close ownership; V1 records IR effects only | Go explicit close+context / Kotlin structured+cooperative / D fibers+pools | LATER — V1 keeps strict float order + effect recording | G7 (needs G5, M10) |
| 09b | Tensors §9 fixes + semantics | `^` conflict, bool tensors, `struct $N`, broadcast text, destructuring, named args, multi-index, view+`del`, autodiff, f16/bf16, `Device`, array-vs-tensor `+` | PyTorch views+counters / JAX pure-functional / TinyGrad lazy values / Burn owned / Mojo owned | LATER — SPEC §9 is design target; tensors-as-values (JAX/TinyGrad way) | G8 (needs G1, M11/M17–M24) |
| 17 | SIMD vectors | Extend array `+` to `-`/`*`/`/` via `@Vector`, then optional `simd[N]T` + `splat`/`reduce`/`select` | Zig `@Vector` / Odin `#simd` / Rust `Simd` / Mojo `SIMD`+`vectorize` | LATER — after V1 correctness+memory; no broadcast, no target flags | G8-adjacent |
| 10 | Network + system stdlib | `std/net` dial/listen, `tls.wrap`, `std/http` get/serve, then fs/path/process/time/rand | Go one-dial+handler (copy) / Zig explicit-allocator (refuse) / Nim sync+async dup (refuse) | LATER — after 03 + G5 `?`; fs/path/time/rand first, TLS/HTTP-server last | G5, G7 |
| 16 | Ecosystem + versioning | `--target` passthrough (WASI first), C-only interop, minimal time/args/log/rand, JSON later | Zig `-target` free / Rust editions (copy lite) / Go compat promise | NEED NOW: args accessor + edition reservation; rest LATER; C++/regex/crypto NEVER | L2 |
| 15b | Annotations + platform + atomics + async | `@target_os()` builtin, closed `@(...)` allowlist, `AtomicU32`+ordering lib, panic-vs-values boundary now | Rust `cfg`+`AtomicU32` / D `version`+`scope` / Zig builtins-no-syntax / C++ `[[..]]`+`co_await` | LATER except boundary (NOW); async syntax NEVER (library post-V1) | G7 (atomics), 05 const-eval |
| 11/12 | Language steals | Nim concepts→`where`, Roc uniqueness→arenas, Gleam `use`/`Result`, V `?`/`or{}`, D patterns-rank/predicates-filter + CTFE + UFCS + `scope(success/failure)` + `package` | As listed per language | LATER — adopts via 02/04/06/13 tracks, not directly | per-track gates |
| 18–21 | GPU path | WebGPU-default + Vulkan-ceiling + CUDA/HIP-speed backends; handle+copy+error contract now; kernels/streams later; CPU fallback mandatory | Nim/Odin/V FFI-first (imitate) / Futhark/Mojo/Bend stacks (reject) / Burn trait shape (imitate) | Design NOW (handles, bridge); LATER (kernels, one FFI backend); NEVER (IR/MLIR, auto-offload, CUDA-only) | L8/L9/L41, file-09 step order |
