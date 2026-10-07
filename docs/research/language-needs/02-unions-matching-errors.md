# Unions, matching, and errors

Scope: tagged-union payload matching + exhaustiveness, case-capture semantics,
`Option`/`Result` spelling, error propagation, recoverable I/O replacing
panicking helpers. Sources: `docs/SPEC.md` §3.3/§5.2/§11, `docs/STATUS.md`,
`docs/plan/README.md` G5, `docs/plan/execution.md` tracks 7a/7b, P10.

## 1. Current A7 state

- Tagged unions parse: `union(tag) { ok: i32, err: string }`
  (`a7/parser.py:2113-2163`). Untagged unions emit Zig `union { ... }`,
  tagged unions emit `union(enum) { ... }` (`a7/backends/zig.py:730-738`).
- No payload matching. `case ok` on a tagged union binds the whole union
  value to a new name instead of testing the tag (G5 example,
  `docs/plan/README.md:238-258`; lowering as if-chain in
  `a7/backends/zig.py:1153-1351`).
- Tag inspection is reserved syntax, not implemented (`docs/SPEC.md:386-387`).
  Union discriminant access proofs are an open gap (`docs/STATUS.md:88-92`).
- Exhaustiveness covers only `bool` and plain `enum`, plus `else`/`_`/capture
  fallback (`a7/passes/semantic_validator.py:1446-1480`). Unions are never
  exhaustive without `else`. Match-expression form is gated by the same check
  (`semantic_validator.py:339-341`).
- Capture rule: an identifier pattern with no visible binding becomes an
  immutable branch-local capture and counts as wildcard
  (`a7/passes/type_checker.py:2677-2692`, `semantic_validator.py:1482-1488`).
  A stray variant name (`case Blu:`) silently matches everything
  (`docs/STATUS.md:119-121`). Capture must be alone in its case
  (`type_checker.py:2694-2707`).
- No `Option`/`Result` types. SPEC §7.2 shows them only as generic
  shape sketches (`SPEC.md:1032-1043`). STATUS lists both as planned stdlib
  (`STATUS.md:96-97`). No propagation operator (`?` lexes but has no grammar
  rule; `SPEC.md:1828-1831`).
- I/O helpers panic instead of reporting failure: stdout/stderr print and
  flush helpers end in `catch @panic(...)` (`a7/backends/zig.py:193-205`).
  Planned recoverable I/O is track 7b work.

## 2. What others do

- Zig `union(enum)`: `switch (u) { .ok => |v| ..., .err => |e| ... }`.
  Payload binds with `|v|` after the tag. `switch` over a tagged union must
  be exhaustive or have `else`; the compiler rejects a missing tag at
  compile time. Untagged `union` field access is unchecked.
- Odin: `union { A, B }` with `switch v in u { case A: ... }`. The `in`
  form binds the payload to `v` typed as the selected variant. No
  exhaustiveness proof; missing tags fall through silently.
- Rust `enum`: `match u { Ok(v) => ..., Err(e) => ... }`. Patterns bind
  payloads by value/ref. Exhaustiveness is checked; `_` or full coverage
  required. `?` propagates `Err` with `From` conversion; `Option` uses
  `None`/`Some(v)` with the same match rules.
- Jai: `union` + `if u is A { ... }` type tests, or `switch` on the tag.
  Payload access after a successful test is direct field read. No
  exhaustiveness checker; discipline is by convention.

Lesson for A7: take Zig/Rust exhaustiveness (compiler-checked, payload
binding in the pattern), keep A7 `case` spelling, avoid Odin/Jai silent
fallthrough. Keep `?` propagation Rust-style but without implicit
conversion: the error type must match the return type exactly.

## 3. Proposal

Syntax (extends current `match`, no new keyword):

```a7
Shape :: union(tag) { circle: f32, rect: Pt, none: bool }

area :: fn(s: Shape) f32 {
    ret match s {
        case .circle(r): 3.14 * r * r
        case .rect(p): p.x * p.y
        case .none(_): 0.0
    }
}
```

Rules:

1. `.tag(bind)` tests the discriminant and binds the payload immutably in
   the arm. `.tag(_)` tests without binding. Bare `case tag:` keeps the
   P5 interim meaning (whole-value capture) until G5 lands, then becomes
   an error on tagged unions to end the silent-capture trap.
2. Exhaustiveness: every tag covered, or an `else`/`_` arm, or a lone
   capture arm. Missing tags are exit-6 semantic errors listing the
   uncovered variants. Same rule for statement and expression `match`.
3. `Option(T)` / `Result(T, E)` are stdlib generic unions, not builtins:
   `Option(T) :: union(tag) { some: T, none: bool }`,
   `Result(T, E) :: union(tag) { ok: T, err: E }`. `?T` is sugar for
   `Option(T)` once generics specialize composite types (track 7a order).
4. Propagation: `value := fallible()?` desugars to match-and-early-return:
   on `err(e)` return `err(e)` from a `Result`-returning fn, on `none`
   return `none` from an `Option`-returning fn. Mismatched kinds reject.
   No `From`-style conversion, no exceptions, no implicit panic path.
5. Recoverable I/O: keep `io.println` (panicking) for examples, add
   `io.println_ok(s: string) Result(usize, IoErr)` and
   `io.read_line(buf: []u8) Result(usize, IoErr)` in track 7b. Panicking
   helpers stay but are documented as non-recoverable.

```a7
n := io.read_line(buf)?        // early-ret err on failure
total += match opt {
    case .some(v): v
    case .none: 0
}
```

## 4. Dependency on G5

This report is input to G5 (`README.md:231-258`) and execution tracks
7a/7b plus packet P10. Order: 7a first (`?T`, payload matching,
exhaustiveness, real `case ok` semantics), then 7b (`Result`,
propagation, recoverable I/O). Blocked on generic composite
specialization for `Option(T)`/`Result(T, E)` and on the memory-plan
gates for owning payloads (M33 lookup results, M49 storage-owning
unions). G7 concurrency join outcomes also wait on G5 error values.

## 5. Test plan

- Parse/typecheck: each tag binds with payload type; `.tag(_)` needs no
  binding; bare `case ok` on tagged union rejects after G5; stray name
  (`case Blu:`) rejects instead of capturing.
- Exhaustiveness matrix: all-tags-covered passes; one tag missing fails
  naming the tag; `else`/`_` passes; expression `match` without coverage
  fails at the match span.
- Backend: payload match lowers to Zig `switch (u) { .tag => |cap| }`;
  `union(enum)` discriminant read never emits unchecked field access.
- Propagation: `?` in `Result`-fn and `Option`-fn passes; cross-kind use
  rejects; error payload type flows to caller unchanged.
- I/O: `println_ok` failure returns `err`, no panic; golden outputs for
  one ok-path and one err-path example per profile.
