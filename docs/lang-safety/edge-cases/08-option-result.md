# Gap 08 — `Option<T>` and `Result<T, E>` stdlib types

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.8](../07-language-review.md#18-no-optiont--resultt-e--fallibility-is-unmodelled).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

Today A7 has no `Option<T>` or `Result<T, E>` — the only nullability
is through `ref T` (Gap 02), and there is no way to model fallible
operations. The contract requires every fallible operation to
return a typed value the user must consume. The work is in picking
the shape of these types and the sugar around them.

## Subcases

| # | Pattern | Today | Decision target |
| --- | --- | --- | --- |
| OR-01 | `Option<T>` with `some(T)` / `none` variants | n/a | Standard sum type |
| OR-02 | `?T` syntax sugar for `Option<T>` | n/a | Sugar (with rules — see Q08a) |
| OR-03 | `Result<T, E>` with `ok(T)` / `err(E)` variants | n/a | Standard sum type |
| OR-04 | `Option<ref T>` vs `?ref T` | latter is Gap 02 syntax | Same type or distinct? — Q02a + Q08b |
| OR-05 | Nested `Option<Option<T>>` | n/a | Allowed; outer none means "no answer", inner none means "answer is no value" |
| OR-06 | `Option<Result<T, E>>` and `Result<Option<T>, E>` | n/a | Both meaningful; user matches |
| OR-07 | `?` propagation operator: `let v = expr?` | n/a | Open question Q08c |
| OR-08 | `match x { case some(v): ...; case null: ... }` | n/a | Standard exhaustive match |
| OR-09 | `Option::map(f)`, `Option::and_then(f)` methods | n/a | Standard combinators |
| OR-10 | `Result::map(f)`, `Result::map_err(f)` | n/a | Standard combinators |
| OR-11 | `unwrap()` method | n/a | **Forbidden**: would be a runtime trap |
| OR-12 | `expect("message")` method | n/a | **Forbidden**: same reason |
| OR-13 | `unwrap_or(default)` | n/a | Allowed: total |
| OR-14 | `unwrap_or_else(f)` | n/a | Allowed: total |
| OR-15 | Pattern-bind `if let some(v) = x` | n/a | Open question Q08d |
| OR-16 | Convert `Option<T>` ⟷ `Result<T, NoValue>` | n/a | Stdlib helpers; rarely needed |
| OR-17 | Builder/finalise: `Builder<T>` returns `Result<T, BuildError>` on `.build()` | n/a | Standard idiom |
| OR-18 | Error chains: `Result<T, MyError>` where `MyError` is a sum of subordinate errors | n/a | Standard; sum types compose |
| OR-19 | "Try-with-resources" / scope-bound error: `defer` on a `Result` | n/a | `defer` operates on values; `Result` users `match` |
| OR-20 | Niche optimisation for `Option<ref T>` → use Zig's `?*T` directly | n/a | Backend should emit the niche-optimised form |
| OR-21 | Generic over `Result`: `fn combine<$E>(rs: []Result<int, $E>) -> Result<int, $E>` | n/a | Standard generic |
| OR-22 | `Option<()>` (unit-typed option) | n/a | Equivalent to `bool` but more informative |
| OR-23 | Default values: `Option<T>::or_default()` when `T: Default` | n/a | Open: do we have a `Default` trait? |
| OR-24 | Iteration: `for v in option { ... }` (option as 0-or-1 iterator) | n/a | Stdlib trait integration; defer until iterator protocol exists |
| OR-25 | `Result<T, E>` cross-conversion `into<U: From<E>>` | n/a | Open: do we have a `From` trait? |

## Interactions

- **Gap 01 cast.** No interaction; conversion is explicit (`some(x)`,
  `none`, etc.).
- **Gap 02 nullable pointers.** OR-04 — the relationship between
  `?ref T` and `Option<ref T>` is the key Phase C decision.
- **Gap 03 definite assignment.** `Option`/`Result` values are
  initialised by their constructors; standard DA applies.
- **Gap 04 NonZero division.** `NonZero::new` returns `Option<NonZero<T>>`.
- **Gap 05 stack budget.** Adds a tag byte (or niche-optimised);
  frame-size accounting includes.
- **Gap 06 typed arithmetic.** `checked_add` returns
  `Option<T>`.
- **Gap 07 bounded indexing.** `try_get` returns `Option<T>`.
- **Gap 09 refinement-lite.** Refinement constructors return
  `Option<Refined>` uniformly.
- **Gap 10 affine ownership.** Pattern-binding `case some(v): ...`
  *moves* the inner `v` if `T` is affine. Borrowing-style match
  (`case some(borrow v): ...`) is open (Q08e).
- **Gap 11 finite floats.** `Fin::new` returns `Option<Fin<F>>`.
- **Gap 12 FFI.** FFI shims return `Result<T, ForeignError>` per
  the contract.
- **Generics.** `Option<$T>` and `Result<$T, $E>` are first-class
  generics. Already supported by A7's generic infrastructure.
- **Match.** Exhaustive match over `Option<T>` and `Result<T, E>` is
  the canonical consumption pattern.

## Failure modes

### False positives

- None expected — these are purely additive type-system features.
- Possible: if `?T` sugar and `?ref T` are *separate* shapes (Q08b
  "distinct"), code that mixes them needs explicit conversion.
  Annoying but soluble.

### False negatives

- `unwrap()` and `expect()` are common in other languages; if a user
  asks for them, the language must redirect to `match` or
  `unwrap_or`. Document.
- `?` propagation operator (OR-07) — if it exists, it's a stealth
  control-flow construct that hides early returns. The Rust
  experience is that it's powerful but takes some learning.

### Ergonomic costs

- Match every `Option` is verbose. Mitigation: `?` operator, plus
  combinator methods (`map`, `and_then`, `or_default`,
  `unwrap_or`).
- Nested `Option<Option<T>>` is awkward. Standard advice: `flatten()`
  method.

### Performance costs

- None. Tagged unions compile to Zig's native tagged unions; `?T`
  with `T = ref U` niche-optimises to `?*U`; `Result<T, ()>` may
  compile to `?T` directly.

## Open questions

- **Q08a.** `?T` sugar's scope:
  - Always sugar for `Option<T>`.
  - Sugar for `Option<T>` when `T` is not a reference type; sugar
    for `?ref U` (separate) when `T = ref U`. Hybrid.
- **Q08b.** Relationship between `?ref T` (Gap 02) and `Option<ref T>`
  (this gap). Same type or separate? **Recommendation**: same type
  with niche-optimisation in the backend — keeps the user-visible
  surface uniform.
- **Q08c.** `?` propagation operator. Three options:
  - Yes, `expr?` desugars to `match expr { case ok(v): v; case err(e):
    return err(e) }`. Works for both `Option` (returning `none`) and
    `Result` (returning `err(e)`).
  - No; user writes explicit `match`. Simplest; verbose.
  - Yes, but only for `Result<_, E>` where the function returns
    `Result<_, E>` for some compatible `E`.
- **Q08d.** `if let` syntax (OR-15). Three options:
  - Yes (Rust-style): `if let some(v) = expr { ... } else { ... }`.
  - No; use `match`.
  - A more general `let ... else { return; }` form.
- **Q08e.** Borrowing-style match (Gap 10 interaction):
  `match opt { case some(borrow v): use(v) }` — does this exist?
  Open until Gap 10 is decided.
- **Q08f.** Method-call syntax on `Option<T>` (`opt.map(f)`) requires
  a method-resolution machinery. If A7 doesn't have generic methods
  yet, these become free functions: `Option::map(opt, f)`. Decision
  affects ergonomic surface heavily.
- **Q08g.** `Default` and `From` traits — do they exist in A7?
  Influence on `unwrap_or_default` (OR-23) and `?`-propagation
  cross-conversion (OR-25).
- **Q08h.** `Result<T, E>` error type — should there be a single
  canonical error trait (`Error`)? Or are errors structural
  (any type is a valid `E`)? Two options:
  - Structural: any type works. Simplest; less consistent error API.
  - Trait: errors must implement an `Error` trait. More structured;
    requires the trait system.
- **Q08i.** Iteration over `Option<T>` (OR-24) — yes/no/deferred.
- **Q08j.** Convert between `Result` and `Option`: explicit methods
  only (`.ok()` → `Option`, `.ok_or(e)` → `Result`), or implicit?
  Explicit always.

## Source citations

- No `Option` or `Result` type exists in A7 today; this is
  greenfield.
- Generics infrastructure already in place:
  `a7/generics.py`, `a7/types.py:TypeSetType`.
- Match exhaustiveness check at
  `a7/passes/type_checker.py:1854-1858` will handle these types as
  soon as they're declared.
- Stdlib organisation: see `a7/stdlib/__init__.py` for where
  `option.py` and `result.py` would live.

## Phase C decision-input summary

1. Q08a — `?T` sugar shape.
2. Q08b — `?ref T` vs `Option<ref T>` identity.
3. Q08c — `?` propagation operator.
4. Q08d — `if let` syntax.
5. Q08f — method-call vs free-function surface.
6. Q08h — Error trait policy.

The rest follow.
