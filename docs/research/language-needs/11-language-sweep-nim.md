# 11 — Language Sweep: Nim, Gleam, Hare, V, Roc

Scope: five languages other sweeps likely skipped. Each gets memory, generics,
errors, metaprogramming, stdlib, compile model, and one steal with a sketch.
Standing A7 direction: small compiler + fat stdlib, Python-simple surface,
compile-time arena/pool grouping, no user-visible memory work (L15–L19).

## 1. Nim

- Memory: ORC by default since 2.0 — ARC (compile-time destructor injection,
  move semantics) plus a cycle collector. Deterministic for acyclic data,
  GC pauses only on cycles. User can also pick ARC, Boehm GC, or manual.
- Generics/constraints: generic procs with `SomeNumber`, `SomeInteger`-style
  built-in type classes plus user `concept` blocks (structural: "has op +").
  Concepts check signatures, not names.
- Errors: exceptions (`raise`/`try`/`except`) plus `Option[T]` and
  `Result[T, E]` in stdlib. `{.raises: [].}` pragma can enforce checked
  exceptions at compile time.
- Metaprogramming: strongest of the five. `template` (hygienic AST paste),
  `macro` (full typed/untyped AST transform in Nim itself), `static` blocks
  and `const` proc evaluation. Pragmas attach semantics to symbols.
- Stdlib: fat. Strings, seqs, tables, JSON, HTTP, async, threading, `strformat`,
  unit test — ships with the compiler.
- Compile model: Nim source → C/C++/JS/Objective-C, then native toolchain.
  Slow full builds, fast incremental via C caching. One `--mm` flag picks
  the memory strategy per build.
- Steal: `concept`-style structural constraints for generics. Fits A7's
  `$T: Numeric` sets: grow sets into signature-checked concepts.
  Sketch:
  ```
  concept Addable($T):
    fn add(a: $T, b: $T) -> $T
  fn sum($T: Addable, xs: []$T) -> $T
  ```

## 2. Gleam

- Memory: none of its own — runs on BEAM (Erlang VM, per-process GC) or JS
  (host GC). Immutability everywhere makes GC cheap and safe.
- Generics/constraints: parametric generics with full inference, no bounds
  or traits. Constraints are expressed as function arguments, not typeclasses.
- Errors: `Result(ok, err)` and `Option` as language-level types, `let assert`
  for honest unwraps, `use` sugar for early return. No exceptions in user code;
  OTP supervisors handle crashing processes ("let it crash").
- Metaprogramming: none by design. No macros. Code sharing is functions and
  modules; FFI is `external` declarations per target.
- Stdlib: thin core (`gleam`, `gleam_stdlib`) + one-package-per-concern
  (`gleam_erlang`, `gleam_otp`, `gleam_json`). Small compiler, ecosystem of
  focused libs — closest to A7's stated stdlib direction.
- Compile model: Gleam → Erlang or JavaScript, then that toolchain. Fast,
  incremental, excellent diagnostics. Same source targets both runtimes via
  per-function `external` clauses.
- Steal: `use` + `Result` error plumbing as the default A7 error style.
  Total functions, typed errors, one sugar keyword instead of exceptions.
  Sketch:
  ```
  fn read_config(path: string) -> Result(Config, IoErr):
    use text: try read_file(path)?
    return Ok(parse_config(text)?)
  ```

## 3. Hare

- Memory: fully manual, C-style `alloc`/`free`, plus `defer` for scoped
  cleanup. No GC, no ARC, no borrow checker. Safety comes from conventions
  (tagged unions, slice bounds checks) not automation.
- Generics/constraints: none, deliberately. No generics, no comptime, no
  overloading. Shared code is `void`-pointer + explicit vtables or
  preprocessor-light `@match` on types. Known pain point for containers.
- Errors: tagged unions `(T | error)` returned by value; caller must
  `match` or propagate with `yield`-style early return. No exceptions.
  Errors are values, exhaustive by construction.
- Metaprogramming: almost none. Build tags, `@static` asserts, comptime-free
  by policy. What you read is what runs.
- Stdlib: medium-fat for a systems language: `io`, `fmt`, `strings`,
  `crypto`, `os`, `net`, `sort`. Bigger than C's, smaller than Nim's.
- Compile model: Hare → QBE IR → native binary. Tiny toolchain, very fast
  builds, third-party bootstrappable. Defines "small compiler" in practice.
- Steal: Hare's build discipline, not its memory model. One IR, one fast
  backend path, no config flags that change semantics. For A7: keep Zig as
  the single backend and make arena placement a compiler decision, never a
  user annotation. Sketch (policy, not syntax): `a7 build` has no `--mm`
  flag; `debug` profile inserts bounds checks, `release` strips them.

## 4. V

- Memory: hybrid story with a warning. Default is GC (Boehm) or `-gc none`
  with manual free; `autofree` (compile-time free insertion) was the big
  promise but never stabilized. Lesson: compile-time freeing without
  ownership types drifts.
- Generics/constraints: `fn max[T](a: T, b: T) T` with optional bounds
  (`[T: Numeric]`-style via interfaces). Interfaces double as constraints.
  Simple, monomorphized, occasionally leaky diagnostics.
- Errors: `Option` (`?T`, `none`) and `Result` (`!T`, `return err()`),
  propagated with `?`. No exceptions. `or {}` blocks handle inline.
  Cleanest `?`-propagation of the five.
- Metaprogramming: `comptime` conditionals, `$for` field loops, `$if`
  platform branches, compile-time reflection (`T.fields()`). Weaker than
  Nim macros, stronger than Hare/Gleam, aimed at serialization-style code.
- Stdlib: fat and batteries-included: `os`, `net`, `json`, `orm`-ish `db`,
  `web` framework, `ui` experiments in-repo. Matches A7's fat-stdlib goal
  in shape, not quality bar.
- Compile model: V → C (human-readable, single `v.c` bootstrap story),
  then cc. Very fast for small programs; C backend keeps portability.
  Same shape as A7→Zig today.
- Steal: `?` propagation with `or {}` fallback blocks. One character to
  propagate, one block to recover — less syntax than try/catch, clearer
  than bare `unwrap`.
  Sketch:
  ```
  data := read_file(path)? or { return default_config() }
  ```

## 5. Roc

- Memory: uniqueness / ownership without user annotations. Pure functions
  plus in-place update when the compiler proves unique ownership
  (like Koka/Lean). No GC pauses for unique data; refcount fallback
  otherwise. Closest published match to A7 L15–L19.
- Generics/constraints: structural "abilities" (typeclasses done right):
  `Hash`, `Eq`, `Encoding` as ability interfaces with derived
  implementations. Parametric + abilities, no subtyping.
- Errors: `Result`/`Bool`-matched tags, exhaustive `when` (match). No
  exceptions, no null. Errors are ordinary tag unions.
- Metaprogramming: none in-language. Zero-cost `expect`/`dbg` builtins for
  tests and traces instead. Extension point is platforms, not macros.
- Stdlib: deliberately thin core — I/O lives in *platforms*, not the
  language. App = pure Roc code, platform = effect provider. Stdlib stays
  small because effects are outsourced per target.
- Compile model: direct to machine code (own IR/codegen, LLVM/assembly
  backends historically). `roc app.roc` builds against exactly one
  platform. Reproducible, no C intermediary.
- Steal: platform/app split for effects and targets. A7's Zig backend is
  today's platform; tensor/accelerator backends (L8) become named platforms
  with declared primitives instead of growing compiler flags.
  Sketch:
  ```
  platform CpuAccel:
    provides kernel(matmul, conv2d, checkpoint)
  app Classifier uses CpuAccel:
    train(): checkpoint(model.train(data))
  ```

## 6. Ranked steal-list (all five)

1. Roc uniqueness inference (in-place update on proven-unique values) —
   the concrete mechanism behind A7's "compiler groups arenas itself"
   (L17). Adopt first; it removes user-visible memory without a GC.
2. Nim `concept` constraints — grows A7's `$T: Set` into structural
   signature checks without inventing a trait system from zero.
3. Gleam `use` + `Result` plumbing — makes total functions the path of
   least resistance; pairs with A7's exhaustive match.
4. V `?` / `or {}` propagation — cheapest error syntax of the five;
   adopt the spelling only if Gleam-style `use` is judged too magic.
5. Hare single-backend discipline — no memory-strategy flags, one fast
   path, profiles change checks not semantics. Process rule, adopt free.
