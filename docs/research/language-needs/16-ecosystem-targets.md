# 16 — Ecosystem Targets: WASM, Cross-Compilation, Interop, Utility Stdlib, Versioning

## 0. Current single-target reality (verified)

- One backend only: `a7/backends/__init__.py` registers `BACKENDS = {"zig": ...}`.
  CLI `--backend` accepts only `zig` (`a7/cli.py:234`).
- V1 qualification target is Linux x86-64, Python 3.13, Zig 0.16.0 (`a7/cli.py:101`).
- Emit path is `zig build-exe` on the host (`scripts/build_examples.py:120`); no
  `--target` passthrough exists in `a7/` or `scripts/`.
- Stdlib is two virtual modules: `std/io`, `std/math` (`docs/SPEC.md` §10.3).
  No serialization, regex, crypto, time, args, logging, or random module exists.
- No `extern`, `@cImport`, or C-header import syntax exists in the grammar
  (§2.4 keywords, §11 builtins). SPEC §1.2 claims "C ABI compatibility" as
  philosophy only; type checker rejects un-lowered ABIs (`a7/compile.py:936`).
- L2 (`docs/plan/decisions.md:37`): documented breaking changes allowed under
  approval rule. No carrying mechanism (edition flag, changelog gate) exists yet.
  Package registry is out of scope and not proposed here.

## 1. WASM target

- Zig: `wasm32-freestanding` and `wasm32-wasi` are ordinary `-Dtarget` values.
  Freestanding = no libc; WASI = syscall shim.
  (`wazero.io/languages/zig`). User code must avoid OS calls on these targets.
- Odin: WASM via `wasm-ld` link step (`odin-lang.org/docs/install`); needs
  `lld` installed. `vendor:wgpu` wraps browser WebGPU for the WASM case.
  Works but is a second-class target with extra host deps.
- Rust: `wasm32-unknown-unknown` + wasm-bindgen/wasm-pack; mature but external
  tooling heavy.
- Go: `GOOS=js GOARCH=wasm` + `wasm_exec.js` bridge; simple, slow runtime.
- Proposal: add `a7 build --target <zig-triple>` passthrough to `zig build-exe
  -target`, default host. Qualify `wasm32-wasi` first (libc present, so current
  `std/io` survives); freestanding later. Reject OS-gated stdlib fns per target
  at semantic stage, not link time.
- Verdict: later. Host correctness first; WASI is the cheap first extra target.

## 2. Cross-compilation story

- Zig: best in class. `zig build-exe -target <triple>` bundles libc for
  supported libcs; one host compiles for all Tier-supported targets
  (`ziglang.org/learn/platform-support`). A7 inherits this free via passthrough.
- Odin: cross compiles via per-target LLVM backends but leans on host linkers;
  more friction than Zig.
- Rust: `rustup target add` + cross-linker config; works, heavier.
- Go: `GOOS/GOARCH` env, trivial for pure Go, cgo breaks it.
- Proposal: no A7-native linker work. `a7 build --target` forwards the triple;
  `a7 doctor` prints exercised targets; CI pins one extra triple once host V1
  is green. A7 supports what its pinned Zig supports, nothing more.
- Verdict: later (thin flag + docs). Near-zero compiler work, real CI cost.

## 3. C interop (cimport-style) + C++ namespaces

- Zig: `@cImport`/`@cInclude` translates C headers at compile time; `extern fn`
  declares C-ABI symbols; C++ only via `extern "C"` shims — no namespace/class
  import. `zig cc/c++` doubles as a C/C++ compiler reusing target flags.
- Odin: `foreign import` + `foreign` blocks bind C libs; same C-ABI boundary,
  no C++ namespace support.
- Rust: `extern "C"` blocks + bindgen; C++ needs cxx crate shims.
- Go: cgo; powerful, kills cross-compilation simplicity.
- Proposal: `cextern` declaration block mapping 1:1 to Zig `extern fn` + a
  lowers to `@cImport`. C only, C ABI only. Explicit never: C++ namespaces,
  classes, templates, exceptions — C++ users write a flat `extern "C"` shim,
  same rule as Zig/Odin/Rust.
- Verdict: C interop later; C++ namespaces never.

## 4. Serialization (JSON first)

- Zig: `std.json` in stdlib (stringify/parse into known structs).
- Odin: `core:encoding/json` (+ csv, base64, hex, varint).
- Go: `encoding/json`, `encoding/xml`, `encoding/gob` in stdlib.
- Rust: `serde` + `serde_json` external crates (de-facto standard, not std).
- Proposal: `std/json` virtual module with `stringify(T)` / `parse(T, string)`
  lowered to `std.json`. Struct-field driven; no binary formats in stdlib.
- Verdict: later. Needed for networking/system tracks (report 10 dependency).

## 5. Regex

- Zig: no regex in stdlib (deliberate; users vendor PCRE or write matchers).
- Odin: `core:text/regex` exists.
- Go: `regexp` (RE2) in stdlib.
- Rust: `regex` crate (external, standard choice).
- Proposal: no `std/regex` now. Glob/prefix matching via `std/string` covers
  tooling uses. Revisit only for a qualified use case, as a single linear-time
  engine choice (RE2-style, Go/Rust model — not backtracking).
- Verdict: never (until proven otherwise). Do not grow a regex engine.

## 6. Crypto

- Zig: `std.crypto` (hashes, AEAD, signatures) in stdlib.
- Odin: `core:crypto/*` packages.
- Go: `crypto/*` in stdlib.
- Rust: `ring`/`rustcrypto` external crates, audited third party.
- Proposal: never implement crypto primitives in A7 stdlib. Expose via C
  interop (§3) to OS/Zig-provided primitives only when needed. Document
  "A7 does not ship crypto" as a standing decision.
- Verdict: never.

## 7. Time/date

- Zig: `std.time` (timestamps, sleep) — no calendar formatting richness.
- Odin: `core:time` (with date/time parsing and formatting).
- Go: `time` package (parsing, zones, arithmetic) — reference implementation.
- Rust: `chrono`/`time` external crates.
- Proposal: minimal `std/time`: wall/monotonic timestamp as `i64`, `sleep`,
  duration arithmetic. No timezone database or calendar formatting in V1.
- Verdict: later, minimal shape only.

## 8. Args parsing

- Zig: `std.process.argsAlloc`, manual iteration; parsing is user code.
- Odin: `core:flags` / `os.args`, thin helpers.
- Go: `flag` (stdlib) + `os.Args`.
- Rust: `clap` external crate.
- Proposal: minimal runtime accessor `std/args`: count + indexed access as
  `string`. No declarative parser in stdlib; parsing loops are ordinary A7 code.
  A Go-`flag`-style helper is optional later.
- Verdict: need now (accessor, ~10 lines of backend). Parser helper later.

## 9. Logging

- Zig: `std.log` with levels + scope, compile-time filtering.
- Odin: `core:log` package.
- Go: `log` then structured `log/slog` (Go 1.21, levels + handlers).
- Rust: `log` facade + `env_logger`/`tracing` external.
- Proposal: `std/log` with levels (debug/info/warn/error) on Zig `std.log`
  scoped loggers; stderr sink reuses `std/io` eprint path. Structured
  key-value logging deferred.
- Verdict: later, small. Pairs with `std/io` buffering already specified.

## 10. Random

- Zig: `std.Random` (xoshiro, ChaCha) + `std.crypto.random` seeding.
- Odin: `core:math/rand` + `core:math/rand_extra`.
- Go: `math/rand` (+ `crypto/rand` for security).
- Rust: `rand` external crate.
- Proposal: `std/rand` seeded PRNG lowering to Zig `std.Random`, plus seed fn.
  Deterministic default seed for tests, OS seed opt-in. No stdlib CSPRNG claim.
- Verdict: later. Small, lowers directly, unblocks examples/tests needing noise.

## 11. Versioning / edition system for breaking changes

- Rust: editions (2015/2018/2021/2024) — opt-in per-crate modes; breaking
  syntax lands only in new editions. `cargo fix` automates migration.
- Go: Go 1 compat promise — almost never breaks.
- Zig/Odin: no editions; Zig breaks freely pre-1.0, Odin stable-by-care.
- Proposal: Rust-lite carrying mechanism for L2:
  1. `edition` field in the module manifest (e.g. `edition = "2026"`); compiler
     accepts all shipped editions, behavior keyed per-module, mixed editions link.
  2. New keywords/syntax land only behind a new edition; old edition keeps prior
     parse. No silent reinterpretation.
  3. Each edition ships a migration note + `a7 fix` rewrite where mechanical.
  4. CHANGELOG entry mandatory per break (extends post-change checklist);
     `docs/plan/decisions.md` records approval.
  5. Cadence: at most one edition per year; V1 pre-freeze needs none — reserve
     the field now so the first break has somewhere to go.
- Verdict: need now the reservation (manifest field + policy doc, no behavior);
  full edition machinery later, at the first approved break.
## Summary table

| Item | Verdict |
|---|---|
| WASM (WASI first) | later |
| Cross-compilation flag | later |
| C interop (`cimport`/`extern`) | later |
| C++ namespaces/classes | never |
| Serialization (`std/json`) | later |
| Regex | never |
| Crypto primitives | never |
| Time/date (minimal) | later |
| Args accessor | need now |
| Args parser helper | later |
| Logging (levels) | later |
| Random (seeded PRNG) | later |
| Edition reservation + policy | need now |
| Edition machinery | later |
| Package registry | out of scope (never proposed) |

Order of work: args accessor + edition reservation now (trivial, unblock tooling
and L2 governance); logging/random/time/JSON with networking and string tracks;
WASM-WASI + `--target` after host V1 greens; C interop after module gaps close;
regex/crypto/C++ stay out.
