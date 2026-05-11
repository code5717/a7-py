# Gap 03 — Definite assignment

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.6](../07-language-review.md#16-definite-assignment--currently-absent).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

Reading an unassigned local is silently allowed today. The Zig
backend handles uninit by either emitting `undefined` (UB under
`-O ReleaseFast`) or by zero-initialising — neither is correct.
Definite assignment is a standard data-flow pass; the work is in
deciding what counts as an "assignment" and handling the awkward
corner cases.

## Subcases

| # | Pattern | Today | Decision target |
| --- | --- | --- | --- |
| DA-01 | `var x: int = 5; print x` | Works | Trivially definitely-assigned |
| DA-02 | `var x: int; print x` | Reads default zero | **Compile error** |
| DA-03 | `var x: int; if c then x = 1 end; print x` | Reads zero on false branch | **Compile error**: not assigned on every path |
| DA-04 | `var x: int; if c then x = 1 else x = 2 end; print x` | Works | Both arms assign ⇒ DA |
| DA-05 | `var x: int; match v { case A: x = 1; case B: x = 2 }` | Works if exhaustive | Definite-assigned only if **every** match arm assigns |
| DA-06 | `var x: int; for i in 0..n: x = i; print x` | Works in body if `n > 0`; reads zero if `n == 0` | **Compile error** unless `n` is statically proved `> 0` |
| DA-07 | `var x: int; while c { x = 1 }; print x` | Same | **Compile error**: while bodies may not execute |
| DA-08 | `var x: int; loop { x = 1; break }; print x` | Works | Definitely-assigned (a `break` after an assignment in an unconditional loop) |
| DA-09 | `var x: int; if c then return; x = 1; print x` | Works | Early return doesn't break DA at the print |
| DA-10 | `var x: int; defer print(x); x = 1` | Works (defer runs after x=1) | DA must understand `defer` runs at scope exit |
| DA-11 | Partial struct init: `p: Point = .{x: 1}; print p.y` | Reads zero | **Compile error**: `y` not assigned |
| DA-12 | Stack array: `buf: [N]u8; print buf[0]` | Reads zero | **Compile error** unless an explicit init/fill |
| DA-13 | Array fill: `buf: [N]u8; for i in 0..N: buf[i] = compute(i); print buf[0]` | Works | DA must understand that "every index written in a loop covering `0..N`" assigns every element |
| DA-14 | `new`-then-fill: `p: ref T = new T{...}; p.val.x = 1; print p.val.x` | If `new T{...}` zero-inits, works | Two options: `new` requires full init, or `new` returns a partially-init type that DA must close |
| DA-15 | Function out-parameter `fn fill(out: inout T)`: caller passes uninit `var x: T`, `fill(&x)`, then reads `x` | Today: not really supported | **Decision**: `inout` parameter that's "write before read" must be declared (e.g., `set T`); definite-assignment at the caller is satisfied by the call |
| DA-16 | Closure captures (when added) — capturing an uninit variable | n/a | When closures land, DA must run on the closure body's captures |
| DA-17 | Mutual `match` arms binding different fields of the same struct | Today: not idiomatic | If every arm assigns the same field, DA passes for that field |
| DA-18 | Definite-assignment through tagged-union variants. `match u { case A(x): assigned = x; case B(y): assigned = y }` | Works if exhaustive | Same as DA-05 |
| DA-19 | Shadowing: `var x = 1; { var x: int; print x }` | Inner `x` is uninit | Inner `x` triggers DA error; outer untouched |
| DA-20 | Self-referential init: `var x = x` | Undefined; today emits | **Compile error** unless `x` was previously declared at outer scope |

## Interactions

- **Gap 01 cast.** Cast doesn't write to a target; the target of an
  assignment is what DA tracks. `let y = cast(T, x)` assigns `y`.
- **Gap 02 nullable pointers.** N-22 builder pattern. If non-null
  `ref T` fields must be initialised before read, the same DA
  machinery catches violations.
- **Gap 04 NonZero division.** No direct interaction.
- **Gap 05 stack budget.** Stack-allocated locals' frame size includes
  uninitialised storage; DA doesn't change frame size but ensures
  the uninit memory is never read.
- **Gap 06 typed arithmetic.** DA must run before range analysis (so
  range analysis sees only assigned values).
- **Gap 07 bounded indexing.** DA-13 — proving "every index in
  `0..N` was assigned" is the loop-induction case. Reuses the same
  flow analysis as Gap 07's four-pattern catalog.
- **Gap 08 `Option<T>` / `Result<T, E>`.** `Option<T>::none` is a fully
  initialised value; constructing an `Option` doesn't trigger DA
  issues for its payload.
- **Gap 09 refinement-lite.** A `NonZero<int>` field is initialised
  the moment a `NonZero` value is stored; partial inits don't apply
  to refinements.
- **Gap 10 affine ownership.** A *moved* binding is in the same
  "must-not-read" state as an uninit binding. DA and move analysis
  share infrastructure — both are flow-sensitive "is this readable
  here?" questions over the CFG.
- **Gap 11 finite floats.** Float locals default to whatever the
  backend produces; DA forces an explicit init.
- **Gap 12 FFI.** Foreign functions taking pointers to be filled
  out work through `inout`/`set` parameters; DA at the caller is
  satisfied by the call.
- **Existing semantic validator.** Reuse the CFG plumbing at
  `a7/passes/semantic_validator.py:140-236` for the iterative
  traversal. The recursion-check function-graph at lines 546–589
  doesn't apply directly (DA is intra-procedural), but the same
  traversal patterns do.
- **Tagged unions.** DA-18. Each variant's payload is initialised by
  the constructor (`u = A(value)`); destructuring in a `match` arm
  binds the payload as definitely-assigned.

## Failure modes

### False positives

- Loops whose bodies are known to execute at least once but the
  prover can't see it. Mitigation: use `loop { ... }` with `break`
  (DA-08) when the user is sure; reject `while` / `for` cases.
- Complex match arms that all assign through different paths the
  prover can't unify. Acceptable cost.
- Generic code that worked uninstantiated: rare, since locals are
  per-instantiation anyway.

### False negatives

- Aliasing: `var x: int; var p = &x; *p = 1; print x`. Through the
  pointer, `x` is now assigned. Either DA gives up when an
  address-of is taken (sound but conservative), or it tracks
  through pointers (precise but expensive). Phase C decision.
- Writes through opaque function calls: `var x: int; fill(&x); print
  x`. Same issue. Mitigation: `set` / `inout` parameter modes (Gap
  10) make this explicit.

### Ergonomic costs

- Builder patterns get harder; see Gap 02 Q02e.
- "Definitely assigned by argument" is a real pattern (caller
  passes an uninit buffer for the callee to fill). The `set` / `inout`
  parameter modes (Gap 10) provide the language-level escape.

### Performance costs

- None. DA is compile-time only.
- *Removing* the silent zero-init may actually speed up generated
  code (Zig can use `undefined` for the slot until the user's
  explicit assignment lands).

## Open questions

- **Q03a.** Are stack arrays (`buf: [N]u8`) implicitly required to be
  fully initialised, or can they be declared and progressively
  filled (DA-13)? Three options:
  - Require an explicit initialiser at declaration.
  - Allow declaration; track element-wise DA through loops.
  - Provide `[N]T::uninit() -> [N]MaybeUninit<T>` and require
    `assume_init()` on the array.
- **Q03b.** Address-taken locals: does DA give up, or does it track
  through? Decision affects DA precision vs implementation cost.
- **Q03c.** Loop induction proving "every iteration writes": is the
  prover sound only for `for i in 0..N: arr[i] = ...` (literal
  match), or does it work for any provably-covering iteration?
- **Q03d.** Struct partial-init (DA-11) — disallow entirely, or
  permit and rely on field-wise DA?
- **Q03e.** What does DA emit when a violation is found? A single
  error per binding ("`x` used uninitialised at line N"), or one
  error per usage site?
- **Q03f.** Does DA run before or after generics instantiation?
  Before (treats `$T` parameters uniformly) is simpler; after
  catches more cases (a `$T = i32` instantiation might initialise
  to literal 0 implicitly, but `$T = NonZero<i32>` cannot).
- **Q03g.** Self-referential init (DA-20): hard error, or silently
  accept (today's behaviour because Zig has its own rules)?
- **Q03h.** Should A7 introduce a `MaybeUninit<T>` type, or only
  rely on the `set` parameter mode + structural rules?

## Source citations

- No definite-assignment pass exists today —
  `a7/passes/type_checker.py` has no relevant function. This entire
  feature is greenfield.
- Existing CFG / iterative traversal in the validator:
  `a7/passes/semantic_validator.py:140-236`. Reuse.
- Backend emission of uninit locals: behaviour varies; see
  `build/debug/zig/src/002_var.zig:22-23` which shows
  `const value: i32 = 0;` for what was an uninit A7 var.
- Examples to audit: every example with a variable declaration —
  start with `examples/002_var.a7`, then sweep the rest.

## Phase C decision-input summary

1. Q03a — stack array policy. **Drives:** DA-12, DA-13, big chunk
   of migration work.
2. Q03b — address-taken locals. **Drives:** DA precision and
   complexity.
3. Q03d — struct partial-init policy.
4. Q03e — diagnostic shape.
5. Q03h — `MaybeUninit<T>` yes/no.
6. Q03f — DA before/after generics instantiation.

The remaining questions follow.
