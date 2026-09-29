# Gap 08 — `Option<T>` and `Result<T, E>` stdlib types

Status: Phase A research from before 2026-09-14. Not approved. Current decisions
are in the [v1 decision ledger](../../plan/decisions.md).

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.8](../07-language-review.md#18-no-optiont--resultt-e--fallibility-is-unmodelled).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

## Summary

A7 has no `Option<T>` or `Result<T, E>`. The only nullability is `ref T`
(Gap 02), and fallible operations cannot be modeled. The contract requires every
fallible operation to return a typed value that the user must consume. The work is
choosing the shape of these types and the sugar around them.

## Audit notes (2026-09-16)

- Note (2026-09-16): still greenfield. [`STATUS.md`](../../STATUS.md) lists
  `Option` and `Result` as planned stdlib work, and `a7/stdlib/` has no option or
  result module.
- Note (2026-09-16): `08-decisions.md` later recorded these as ACCEPTED. Under the
  ledger's approval rule they still need user approval with examples.

  | Entry | Line | Recorded choice | Answers |
  | --- | --- | --- | --- |
  | D.010 | 336 | `?T` is sugar for `Option<T>`; one mechanism | Q08a, Q08b |
  | D.013 | 401 | `nil` stays the absent literal; `case nil` in match | OR-01, OR-08 spelling |
  | D.016 | 480 | Stdlib sum types; `E` is structural, no `Error` trait | OR-01, OR-03, Q08h |
  | D.017 | 504 | Postfix `?`; return type must match exactly; no `From` conversion | OR-07, Q08c, OR-25 |
  | D.018 | 531 | No `unwrap()` or `expect()` | OR-11, OR-12 |
  | D.019 | 549 | v1 combinators are only `.map` and `.unwrap_or` | OR-09, OR-10, Q08f |

- Note (2026-09-16): the ledger supersedes the `int`/`number` parts of D.010 (L3,
  L4). OR-21 uses `int`, which no longer exists; read it as a fixed-width type.
- Note (2026-09-16): D.013 keeps `nil`. The [memory plan](../../plan/memory.md)
  (proposed) uses optionals for absence, writes `none` in its example and lists
  `nil` as "removed or reserved". The spelling is unresolved.
- Note (2026-09-16): borrow-style match (Q08e) and the Gap 10 row depend on
  user-visible ownership modes. The memory plan makes ownership internal, so that
  direction is superseded.
- Note (2026-09-16): `Fin::new` (Gap 11 row) is superseded by ledger L16; floats
  are IEEE.

## Subcases

| # | Pattern | Phase A state | Decision target |
| --- | --- | --- | --- |
| OR-01 | `Option<T>` with `some(T)` / `none` | n/a | Standard sum type |
| OR-02 | `?T` sugar for `Option<T>` | n/a | Sugar, with rules (Q08a) |
| OR-03 | `Result<T, E>` with `ok(T)` / `err(E)` | n/a | Standard sum type |
| OR-04 | `Option<ref T>` vs `?ref T` | `?ref T` is Gap 02 syntax | Same type or distinct? (Q02a, Q08b) |
| OR-05 | Nested `Option<Option<T>>` | n/a | Allowed. Outer none means "no answer"; inner none means "the answer is no value" |
| OR-06 | `Option<Result<T, E>>` and `Result<Option<T>, E>` | n/a | Both meaningful; user matches |
| OR-07 | `?` propagation: `let v = expr?` | n/a | Q08c |
| OR-08 | `match x { case some(v): ...; case null: ... }` | n/a | Standard exhaustive match |
| OR-09 | `Option::map(f)`, `Option::and_then(f)` | n/a | Standard combinators |
| OR-10 | `Result::map(f)`, `Result::map_err(f)` | n/a | Standard combinators |
| OR-11 | `unwrap()` | n/a | Forbidden: a runtime trap |
| OR-12 | `expect("message")` | n/a | Forbidden: same reason |
| OR-13 | `unwrap_or(default)` | n/a | Allowed: total |
| OR-14 | `unwrap_or_else(f)` | n/a | Allowed: total |
| OR-15 | Pattern bind `if let some(v) = x` | n/a | Q08d |
| OR-16 | Convert `Option<T>` ⟷ `Result<T, NoValue>` | n/a | Stdlib helpers; rarely needed |
| OR-17 | Builder: `Builder<T>.build()` returns `Result<T, BuildError>` | n/a | Standard idiom |
| OR-18 | Error chains: `Result<T, MyError>`, `MyError` a sum of sub-errors | n/a | Standard; sum types compose |
| OR-19 | Scope-bound error: `defer` with a `Result` | n/a | `defer` works on values; `Result` users `match` |
| OR-20 | Niche optimization: `Option<ref T>` as Zig `?*T` | n/a | Backend emits the niche form |
| OR-21 | Generic over `Result`: `fn combine<$E>(rs: []Result<int, $E>) -> Result<int, $E>` | n/a | Standard generic |
| OR-22 | `Option<()>` | n/a | Same information as `bool`, clearer intent |
| OR-23 | `Option<T>::or_default()` when `T: Default` | n/a | Open: is there a `Default` trait? |
| OR-24 | `for v in option { ... }` (0-or-1 iterator) | n/a | Defer until an iterator protocol exists |
| OR-25 | Cross-conversion `into<U: From<E>>` | n/a | Open: is there a `From` trait? |

Note (2026-09-16): OR-08 writes `case null`; OR-01 writes `none`; D.013 writes
`case nil`. The table keeps the Phase A text.

## Examples

OR-07, OR-08 and OR-13, the three consumption forms:

```a7
// Proposed (spelling per D.013, D.017, D.019; not implemented)
parse_digit :: fn(c: char) ?u8 {
    if c >= '0' and c <= '9' {
        ret cast(u8, c) - cast(u8, '0')
    }
    ret nil
}

sum_two :: fn(a: char, b: char) ?u8 {
    x := parse_digit(a)?          // OR-07: returns nil early
    y := parse_digit(b)?
    ret x + y
}

main :: fn() {
    match sum_two('4', '2') {     // OR-08
        case some(v): { io.println("sum = {}", v) }
        case nil: { io.println("not digits") }
    }
    d := parse_digit('x').unwrap_or(0)   // OR-13
}
```

OR-19, `defer` next to a `Result`:

```a7
// Proposed (Result and open_file are not implemented)
read_config :: fn(path: string) Result(Config, IoError) {
    file := open_file(path)?
    defer file.close()            // runs on both the ok and err paths
    ret parse_config(file)
}
```

## Interactions

| Gap | Interaction |
| --- | --- |
| 01 cast | No interaction; construction is explicit (`some(x)`, `none`). |
| 02 nullable pointers | OR-04: whether `?ref T` and `Option<ref T>` are the same is the key Phase C decision. |
| 03 definite assignment | Constructors initialize the values; standard definite assignment applies. |
| 04 NonZero division | `NonZero::new` returns `Option<NonZero<T>>`. |
| 05 stack budget | Adds a tag byte unless niche-optimized; frame-size accounting includes it. |
| 06 typed arithmetic | `checked_add` returns `Option<T>`. |
| 07 bounded indexing | `try_get` returns `Option<T>`. |
| 09 refinement-lite | Refinement constructors return `Option<Refined>` uniformly. |
| 10 affine ownership | `case some(v)` moves `v` if `T` is affine. Borrow-style match (`case some(borrow v)`) is open (Q08e). |
| 11 finite floats | `Fin::new` returns `Option<Fin<F>>`. |
| 12 FFI | FFI shims return `Result<T, ForeignError>` per the contract. |
| Generics | `Option<$T>` and `Result<$T, $E>` are first-class generics on the existing generic infrastructure. |
| Match | Exhaustive match is the canonical way to consume both types. |

## Failure modes

### False positives

- None expected; these types are additive.
- Possible: if `?T` and `?ref T` are separate shapes (Q08b "distinct"), mixing them
  needs explicit conversion. Annoying but solvable.

### False negatives

- Users from other languages will ask for `unwrap()` and `expect()`. The language
  must redirect them to `match` or `unwrap_or`. Document it.
- The `?` operator (OR-07) hides early returns. Rust shows it is powerful but takes
  some learning.

### Ergonomic costs

- Matching every `Option` is verbose. Mitigation: the `?` operator and combinators
  (`map`, `and_then`, `or_default`, `unwrap_or`).
- `Option<Option<T>>` is awkward. Standard advice: a `flatten()` method.

### Performance costs

- None. Tagged unions compile to Zig tagged unions. `?T` with `T = ref U`
  niche-optimizes to `?*U`. `Result<T, ()>` may compile to `?T`.

## Open questions

- **Q08a.** Scope of the `?T` sugar:
  - Always sugar for `Option<T>`.
  - Hybrid: sugar for `Option<T>` when `T` is not a reference; a separate `?ref U`
    when `T = ref U`.
- **Q08b.** Are `?ref T` (Gap 02) and `Option<ref T>` the same type?
  Recommendation: the same type, niche-optimized in the backend, so the surface
  stays uniform.
- **Q08c.** The `?` propagation operator:
  - Yes: `expr?` desugars to `match expr { case ok(v): v; case err(e): return err(e) }`.
    Works for `Option` (returns `none`) and `Result` (returns `err(e)`).
  - No: the user writes `match`. Simplest; verbose.
  - Yes, only for `Result<_, E>` inside a function returning `Result<_, E>` with a
    compatible `E`.
- **Q08d.** `if let` (OR-15):
  - Yes, Rust style: `if let some(v) = expr { ... } else { ... }`.
  - No; use `match`.
  - A general `let ... else { return; }` form.
- **Q08e.** Borrow-style match (Gap 10): does `match opt { case some(borrow v): use(v) }`
  exist? Open until Gap 10 is decided.
- **Q08f.** Method syntax (`opt.map(f)`) needs method resolution. Without generic
  methods these become free functions: `Option::map(opt, f)`. The choice shapes the
  ergonomic surface.
- **Q08g.** Do `Default` and `From` traits exist? They affect `unwrap_or_default`
  (OR-23) and `?` cross-conversion (OR-25).
- **Q08h.** Error type policy for `Result<T, E>`:
  - Structural: any type is a valid `E`. Simplest; less consistent error API.
  - Trait: `E` must implement `Error`. More structure; needs a trait system.
- **Q08i.** Iteration over `Option<T>` (OR-24): yes, no or deferred.
- **Q08j.** Converting between `Result` and `Option`: explicit methods only
  (`.ok()` to `Option`, `.ok_or(e)` to `Result`) or implicit? Recommendation:
  always explicit.

## Source citations

- No `Option` or `Result` type exists; greenfield.
- Generics infrastructure: `a7/generics.py`, `a7/types.py:TypeSetType`.
- Match exhaustiveness check at `a7/passes/type_checker.py:1854-1858` will handle
  these types once they are declared. Note (2026-09-16): stale; those lines now
  hold `visit_deref`. The current location was not re-verified.
- Stdlib layout: `a7/stdlib/__init__.py`, where `option.py` and `result.py` would
  live.

## Phase C decision-input summary

1. Q08a — `?T` sugar shape.
2. Q08b — `?ref T` vs `Option<ref T>` identity.
3. Q08c — `?` propagation operator.
4. Q08d — `if let` syntax.
5. Q08f — method-call vs free-function surface.
6. Q08h — Error trait policy.

The rest follow from these.
