# 12 — D Language Research for A7

Source: D (dlang.org) — systems language with GC by default, opt-out
determinism layers, and the template model closest to A7's `$T` needs.

## 1. Memory story: GC + `@nogc` + betterC + arenas

- Default is a GC heap (`new`, slices, closures, `~` concat allocate).
  GC is stop-the-world, non-moving, partly conservative. Pause control is
  manual: `GC.disable()/enable()`, `GC.collect()`, `GC.free()`.
- `@nogc` is a function attribute enforced by the compiler: a `@nogc`
  function cannot call the GC (directly or transitively). It is part of the
  type signature, so it propagates through interfaces. It says nothing
  about *which* allocator replaces the GC — callers pass in stack buffers,
  arenas, or `malloc`.
- `-betterC` removes the D runtime (GC, TypeInfo, exceptions, module
  constructors). Result is a C-like subset: no dynamic arrays that need
  the GC, no `throw`, limited stdlib. Used for firmware, drivers, WASI.
- Community practice for GC-free code without fighting the language:
  stack buffers + caller-provided slices + simple arena allocators
  (`std.allocator`), with `-vgc` flag to audit hidden allocations
  (array literals, closures, `~`). `scope`/`return scope` params let the
  compiler avoid heap-allocating short-lived values.
- Phobos itself is only partly `@nogc`; a 2019 tracking issue ("Are we
  @nogc yet?") records that large stdlib parts still need the GC.

A7 take: A7 already plans compiler-managed memory (README: V1 target).
D shows the layering that works: safe default, attribute-enforced
no-GC subset, runtime-free subset, and a compiler flag that names every
hidden allocation.

## 2. Templates + constraints + specialization (closest model to `$T`)

- Declaration: `template Foo(T, int N)` / function template
  `void bar(T)(T x)`. Args can be types, values (int, float, string),
  symbols, or templates, each with defaults.
- Specialization patterns: `Foo(T : T*)`, `Foo(T : T[])`,
  `Foo(T, U : T)`. No "primary template": all same-name templates are
  candidates; the most specialized match wins; ambiguity is an error.
- Constraints (`if` clause) are a separate boolean filter evaluated
  after matching: `void foo(T)(T x) if (isNumeric!T)`. Constraints do
  NOT rank overloads — specialization picks the winner, constraints only
  admit/reject. Mutually exclusive constraints give overload-by-predicate.
- Introspection behind constraints: `is(T : float)`, `__traits(compiles, …)`,
  `std.traits` (`isNumeric`, `isInputRange`, `hasLength`), `std.meta`
  (`AliasSeq`, `staticMap`, `allSatisfy`). Duck-typing checks live in
  library code, not new syntax.
- Eponymous templates (`template Foo(T) { alias Foo = …; }`) and
  `static if` inside bodies replace most partial-specialization machinery.

A7 take: this two-axis design (patterns rank, predicates filter) maps
directly onto open A7 questions — user specialization (`04-generics.md`
gap 4) and `where` clauses (gap 3). Adopt it nearly as-is.

## 3. CTFE (compile-time function execution)

- Any ordinary function whose arguments are compile-time-known can run at
  compile time — no `constexpr` marker needed. Same source serves both
  phases. Classic use: `ctRegex` builds a regex automaton at compile time
  from the same code as the runtime `regex`.
- Limits: CTFE interpreter supports a large but not total subset
  (no inline asm, no raw pointer tricks, no system calls). Failures fall
  back to runtime when values are not constant.

A7 take: "same function, either phase" beats a separate const-eval
language. Relevant to `$N` value params (gap 2): const args should just
be CTFE-evaluable expressions.

## 4. Ranges + `std.algorithm`

- Range = structural interface by capability ladder:
  input (`front`/`popFront`/`empty`) → forward (`save`) →
  bidirectional (`back`/`popBack`) → random-access (`opIndex`/`length`).
  Detection is trait-based (`isInputRange!R`), not inheritance.
- `std.algorithm` (~searching/comparison/iteration/sorting/setops/
  mutation) is lazy, composable, and predicate-parameterized:
  `arr.filter!(a => a < 3).map!(a => a * 2).sum`. Predicates accept a
  lambda, a function alias, or a compile-time string (`"a > b"`).
- UFCS chains make it read left-to-right (see §8).

A7 take: trait-detected capability ladders are the right precedent for
A7 iteration/collections work (`03-collections-stdlib.md`). No base-class
tax; algorithms degrade gracefully to the weakest capability offered.

## 5. Fibers / concurrency

- `core.thread.fiber.Fiber`: cooperative user-space threads, explicit
  `call()`/`yield()`. Basis for generators and user schedulers.
- Two stdlib models: `std.concurrency` (message passing between logical
  threads via `spawn`/`send`/`receive`, `Tid` handles; scheduler is
  pluggable — kernel threads by default, `FiberScheduler` available) and
  `std.parallelism` (task pool, `parallel(foreach)`, `taskPool.reduce`,
  futures; tasks double as memory barriers).
- Design guidance in D docs: prefer `parallelism` for independent work,
  message passing over lock-sharing otherwise.

A7 take: fibers-as-building-block + message-passing default is a sane
later-stage concurrency story. Nothing A7 needs now, but do not design
`defer`/destructors in a way that forbids stackful coroutines later.

## 6. Visibility / modules

- One public symbol per module file; `module foo.bar;` + `import`.
  Visibility: `public` (default), `private` (module), `package`
  (package subtree), `protected` (inheritance). Selective and renamed
  imports (`import std.stdio : writeln;`), `public import` re-export.

A7 take: unremarkable but proven. `package` visibility is the one idea
worth stealing early — module-only private is too coarse for stdlib work.

## 7. Error handling (note: A7 has `defer`)

- Exceptions by default (`throw`/`try`/`catch`/`finally`), `Exception`
  vs `Error` (recoverable vs fatal) hierarchy, function contracts
  (`in`/`out`/invariant) checked at runtime.
- `scope(exit)` / `scope(success)` / `scope(failure)` run cleanup on
  scope unwinding however it happens. A7's `defer` covers `scope(exit)`;
  D's lesson is that `success`/`failure` variants earn their keep for
  commit/rollback patterns without a `try` in sight.
- `nothrow` attribute (like `@nogc`) statically guarantees no throw;
  `-betterC` drops exceptions entirely (error-code style instead).

## 8. UFCS (uniform function call syntax)

- `a.foo(b)` rewrites to `foo(a, b)` when no member `foo` exists.
  Enables `arr.filter!(…).map!(…).sum` chains over free functions and
  lets library authors extend built-in types without wrappers.

A7 take: high value, low cost. Makes a small core type set feel large.

## 9. Stdlib breadth (Phobos = fat-stdlib precedent)

- Phobos ships algorithms, ranges, containers, regex, JSON, CSV, UUID,
  sockets, parallelism, math, random, datetime, digest, unicode,
  metaprogramming (`std.traits`, `std.meta`, `std.typecons`,
  `std.variant`, `std.sumtype`). `import std;` pulls it all in.
- Cost, honestly stated: Phobos is large, partly GC-bound, and carries
  decades of accretion — the "small compiler, fat stdlib" direction A7
  wants must budget for `@nogc`-cleanliness from day one, which D did not.

## 10. Ranked steal-list for A7 (with sketches)

1. **Constraint-clause generics (patterns rank, predicates filter).**
   `fn max($T)(a: $T, b: $T) -> $T where Numeric($T)` — call-site
   inference unchanged; `where` admits/rejects, never ranks. Resolves
   `04-generics.md` gaps 3+4 with D's exact semantics.
2. **Specialization with most-specific-wins + ambiguity error.**
   `fn ser($T: $T[])(x: $T)` beside `fn ser($T)(x: $T)`; slices win for
   slices, anything else falls through. No priority pragmas.
3. **`where`-building-block traits in the stdlib, not syntax.**
   `Numeric($T)`, `isRange($T)`, `compiles($T, "a+b")` as ordinary
   generic bool functions over `$T`, composed with `and/or/not`.
4. **CTFE for value params.** `Tensor($T, $N)` where `$N` is any
   compile-time-known expression evaluated by the normal interpreter.
   One language, two phases.
5. **`scope(success)` / `scope(failure)` alongside `defer`.**
   `defer` = `scope(exit)`; add the two siblings for commit/rollback.
6. **UFCS method-call sugar for free functions.** Zero type-system
   impact; unlocks range-style chaining the day A7 has iterators.
7. **`@nogc`-style attribute + `-vgc`-style audit flag.**
   Enforcement plus diagnostics (`array literal may allocate`),
   once A7's memory story lands. Do not retrofit — require new stdlib
   code to state its allocation behavior.
8. **`package` visibility.** Between module-private and public; needed
   as soon as the stdlib spans multiple files per package.
9. **Range capability ladder for iteration.** `front/popFront/empty`
   structural checks via traits; algorithms generic over the ladder.
   Later-stage, but shapes collection API design now.
10. **Eponymous-template idiom for type aliases.**
    `Vec($T) = struct { … }` usable as a type directly — minor sugar,
    include only if generic structs get clumsy.
