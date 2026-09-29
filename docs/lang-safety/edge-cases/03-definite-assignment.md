# Gap 03 — Definite assignment

Status: Phase A research from before 2026-09-14, not a decision. Decisions are in the [ledger](../../plan/decisions.md); memory plan gate M34 proposes rejecting unassigned reads.

Audit finding: [`../07-language-review.md` §1.6](../07-language-review.md#16-definite-assignment--currently-absent).
Phase C decisions were to land in [`../08-decisions.md`](../08-decisions.md).

## Summary

Reading an unassigned local is silently allowed. The Zig backend either
emits `undefined` (undefined behavior under `-O ReleaseFast`) or
zero-initializes. Neither is correct.

Definite assignment (DA) is a standard data-flow pass. The work is in
deciding what counts as an assignment and in handling the awkward corner
cases.

## Current behavior (2026-09-16)

Note (2026-09-16): the Phase A picture still holds. Evidence is a source
read on 2026-09-16; no program was compiled in this session.

- No DA pass exists. `a7/safety.py:308` records
  `ValueFact(initialized=False)` for a declaration without a value, but no
  code in `safety.py` reads that field.
- A declaration with an explicit type and no value emits the type's
  default, which is zero for integers (`a7/backends/zig.py:685-689`).
  Without a type it emits `undefined` (`zig.py:691`).
- `build/debug/zig/src/002_var.zig:27` shows `const value: i32 = 0;` for
  the uninitialized `value: i32` in `examples/002_var.a7`. That example,
  and the comment in `examples/005_for_loop.a7`, present zero defaults as
  a feature.
- The [memory plan](../../plan/memory.md) (section 3, gate M34) proposes
  rejecting a read that no path assigns. It records that such a read is
  accepted today after a zero-iteration loop.

Phase A notation: the subcase table uses pseudo-syntax (`var x: int`,
`print`, `then ... end`, `loop`, `p.val`, `&x`). Current A7 writes
`x: i32`, `x := 1`, `if c { }` and `while true { }`, and has no `int` type
(L4) and no public address-of or dereference. The examples below use
current syntax.

## Subcases

| # | Pattern | Phase A: today | Phase A: target |
| --- | --- | --- | --- |
| DA-01 | `var x: int = 5; print x` | Works | Trivially assigned |
| DA-02 | `var x: int; print x` | Reads default zero | Compile error |
| DA-03 | `var x: int; if c then x = 1 end; print x` | Reads zero on the false branch | Compile error: not assigned on every path |
| DA-04 | `var x: int; if c then x = 1 else x = 2 end; print x` | Works | Both arms assign, so assigned |
| DA-05 | `var x: int; match v { case A: x = 1; case B: x = 2 }` | Works if exhaustive | Assigned only if every arm assigns |
| DA-06 | `var x: int; for i in 0..n: x = i; print x` | Works if `n > 0`; reads zero if `n == 0` | Compile error unless `n > 0` is proven |
| DA-07 | `var x: int; while c { x = 1 }; print x` | Same | Compile error: a `while` body may not run |
| DA-08 | `var x: int; loop { x = 1; break }; print x` | Works | Assigned: the `break` follows the assignment in an unconditional loop |
| DA-09 | `var x: int; if c then return; x = 1; print x` | Works | An early return does not break DA at the print |
| DA-10 | `var x: int; defer print(x); x = 1` | Works (the defer runs after `x = 1`) | DA must model that `defer` runs at scope exit |
| DA-11 | Partial struct init: `p: Point = .{x: 1}; print p.y` | Reads zero | Compile error: `y` not assigned |
| DA-12 | Stack array: `buf: [N]u8; print buf[0]` | Reads zero | Compile error unless explicitly initialized or filled |
| DA-13 | Array fill: `buf: [N]u8; for i in 0..N: buf[i] = compute(i); print buf[0]` | Works | DA must see that writing every index in a loop over `0..N` assigns every element |
| DA-14 | `new` then fill: `p: ref T = new T{...}; p.val.x = 1; print p.val.x` | Works if `new T{...}` zero-initializes | Either `new` requires full init, or `new` returns a partly initialized type that DA must close |
| DA-15 | Out-parameter `fn fill(out: inout T)`: the caller passes an uninit `var x: T`, calls `fill(&x)`, then reads `x` | Not really supported | An `inout` parameter written before read must be declared (for example `set T`); the call satisfies DA at the caller |
| DA-16 | Closure capturing an uninit variable (when closures exist) | n/a | DA must run on the closure body's captures |
| DA-17 | Different `match` arms assigning fields of one struct | Not idiomatic | If every arm assigns the same field, DA passes for that field |
| DA-18 | DA through tagged-union variants: `match u { case A(x): assigned = x; case B(y): assigned = y }` | Works if exhaustive | Same as DA-05 |
| DA-19 | Shadowing: `var x = 1; { var x: int; print x }` | The inner `x` is uninit | Error on the inner `x`; the outer `x` is untouched |
| DA-20 | Self-referential init: `var x = x` | Undefined; emitted today | Compile error unless an outer `x` exists |

Note (2026-09-16): DA-14 and DA-15 use `.val`, `&x` and `inout`/`set`,
which are not public or accepted syntax (`docs/SAFETY_CONTRACT.md`
"Reference Surface"; ledger L6 scope limit; D.040, D.041 and D.049 not
accepted). The memory plan removes `new` (DA-14) and rejects capturing
function values (gate M6, DA-16). Struct initialization completeness
(DA-11) is open under G5.

### Examples

Current A7 blocks use today's syntax. Unless a comment cites evidence,
their compile result was not checked in this session.

```a7
// Current A7. DA-01, DA-02, DA-19.
io :: import "std/io"

main :: fn() {
    ready: i32 = 5               // DA-01
    io.println("{}", ready)
    value: i32                   // DA-02: emitted as 0 (002_var.zig:27)
    io.println("{}", value)
    if ready > 0 {
        ready: i32               // DA-19: inner binding, never assigned
        io.println("{}", ready)
    }
}
```

```a7
// Current A7. DA-03, DA-04, DA-09.
pick :: fn(c: bool) i32 {
    x: i32
    if c {
        x = 1                    // DA-03: unassigned when c is false
    }
    y: i32
    if c {
        y = 1
    } else {
        y = 2                    // DA-04: both arms assign
    }
    ret x + y
}

early :: fn(c: bool) i32 {
    x: i32
    if c {
        ret 0
    }
    x = 1
    ret x                        // DA-09
}
```

```a7
// Current A7. DA-05, DA-17.
Color :: enum {
    Red
    Green
}
Point :: struct {
    x: i32
    y: i32
}

code :: fn(c: Color) i32 {
    x: i32
    match c {
        case Color.Red: {
            x = 1
        }
        case Color.Green: {
            x = 2
        }
    }
    ret x                        // DA-05: every arm assigns
}

place :: fn(c: Color) Point {
    p: Point
    match c {
        case Color.Red: {
            p.x = 1
        }
        case Color.Green: {
            p.x = 2
        }
    }
    ret p                        // DA-17: p.x set on every arm, p.y never
}
```

```a7
// Current A7. DA-06, DA-07, DA-08.
last :: fn(n: usize) usize {
    x: usize
    for i := cast(usize, 0); i < n; i += 1 {
        x = i                    // DA-06: body may run zero times
    }
    y: i32
    going := n > 0
    while going {
        y = 1                    // DA-07
        going = false
    }
    z: i32
    while true {
        z = 1
        break                    // DA-08: assigned before the only exit
    }
    ret x
}
```

```a7
// Current A7. DA-10.
io :: import "std/io"

main :: fn() {
    x: i32
    defer io.println("{}", x)    // runs at scope exit, after x = 1
    x = 1
}
```

```a7
// Current A7. DA-11, DA-12, DA-13.
Point :: struct {
    x: i32
    y: i32
}

main :: fn() {
    p := Point{x: 1}             // DA-11: y not given
    buf: [8]u8                   // DA-12: zero today (005_for_loop.a7 comment)
    first := buf[0]
    filled: [8]u8
    for i := cast(usize, 0); i < 8; i += 1 {
        filled[i] = 7            // DA-13: every index written
    }
}
```

```a7
// Current A7. DA-14, DA-15, DA-20.
Box :: struct {
    value: i32
}

fill :: fn(out: ref i32) {
    out = 7
}

main :: fn() {
    b := new Box                 // DA-14: no field values given
    if b == nil {
        ret
    }
    defer del b
    b.value = 1

    x: i32
    fill(x)                      // DA-15: the callee writes before the caller reads
    y := x

    z := z                       // DA-20
}
```

```a7
// Proposed (Phase A). Closures and tagged-union payload matching are not
// current features (docs/STATUS.md). DA-16, DA-18.
total: i32
add := fn() { total += 1 }       // DA-16: captures an uninit variable

area: i32
match shape {
    case Circle(r): { area = r }
    case Square(s): { area = s } // DA-18
}
```

## Interactions

- **Gap 01, cast.** Cast does not write to a target. DA tracks the target
  of an assignment: `let y = cast(T, x)` assigns `y`.
- **Gap 02, nullable pointers.** The N-22 builder pattern. If non-null
  `ref T` fields must be set before they are read, the same DA machinery
  catches violations.
- **Gap 04, NonZero division.** No direct interaction.
- **Gap 05, stack budget.** A frame includes uninitialized storage. DA
  does not change the frame size, but ensures uninit memory is never read.
- **Gap 06, typed arithmetic.** DA runs before range analysis, so range
  analysis sees only assigned values.
- **Gap 07, bounded indexing.** DA-13: proving "every index in `0..N` was
  assigned" is the loop-induction case. It reuses the flow analysis of
  Gap 07's four-pattern catalog.
- **Gap 08, `Option<T>` and `Result<T, E>`.** `Option<T>::none` is a fully
  initialized value; constructing an `Option` raises no DA issue for its
  payload.
- **Gap 09, refinement-lite.** A `NonZero<int>` field is initialized as
  soon as a `NonZero` value is stored; partial init does not apply to
  refinements.
- **Gap 10, affine ownership.** A moved binding is in the same
  "must not read" state as an uninit binding. DA and move analysis share
  infrastructure: both ask "is this readable here?" over the CFG. Note
  (2026-09-16): the memory plan makes ownership internal (ledger O2);
  `a7/safety.py` already rejects direct use after `del`.
- **Gap 11, finite floats.** Float locals default to whatever the backend
  emits; DA forces an explicit init.
- **Gap 12, FFI.** Foreign functions that fill a pointer work through
  `inout`/`set` parameters; the call satisfies DA at the caller.
- **Existing semantic validator.** Reuse the iterative traversal at
  `a7/passes/semantic_validator.py:140-236`. The recursion check's
  function graph (`semantic_validator.py:546-589`) does not apply
  directly, because DA is intra-procedural, but its traversal patterns do.
- **Tagged unions.** DA-18. The constructor (`u = A(value)`) initializes
  each variant's payload; destructuring in a `match` arm binds the payload
  as assigned.

## Failure modes

### False positives

- Loops whose bodies always run at least once, where the prover cannot see
  it. Mitigation: use `loop { ... }` with `break` (DA-08) when the user is
  sure; reject the `while` and `for` forms.
- Match arms that all assign through paths the prover cannot unify. An
  acceptable cost.
- Generic code: rare, since locals are per instantiation.

### False negatives

- Aliasing: a write to `x` through a reference assigns `x`. Phase A wrote
  this as `var x: int; var p = &x; *p = 1; print x`, which is not public
  A7 syntax. Either DA gives up once an address is taken (sound but
  conservative), or it tracks through pointers (precise but expensive).
  Phase C decision.
- Writes through opaque calls: `var x: int; fill(&x); print x`. The same
  issue. Mitigation: `set`/`inout` parameter modes (Gap 10) make it
  explicit. Note (2026-09-16): current A7 passes the lvalue to a `ref`
  parameter instead (DA-15 example).

### Ergonomic costs

- Builders get harder; see Gap 02 Q02e.
- "Assigned by argument" is a real pattern: the caller passes an uninit
  buffer for the callee to fill. The `set`/`inout` modes (Gap 10) are the
  language-level escape.

### Performance costs

- None; DA is compile-time only.
- Removing the silent zero-init may speed up generated code: Zig can use
  `undefined` for the slot until the explicit assignment.

## Open questions

- **Q03a.** Must a stack array (`buf: [N]u8`) be fully initialized at
  declaration, or can it be filled progressively (DA-13)?
  - Require an explicit initializer at declaration.
  - Allow declaration; track element-wise DA through loops.
  - Provide `[N]T::uninit() -> [N]MaybeUninit<T>` and require
    `assume_init()` on the array.
- **Q03b.** Address-taken locals: does DA give up or track through? The
  choice trades DA precision against implementation cost. Note
  (2026-09-16): public address-of does not exist; the question applies to
  `ref` arguments and internal lowering.
- **Q03c.** Loop induction ("every iteration writes"): is the prover sound
  only for the literal `for i in 0..N: arr[i] = ...` shape, or for any
  provably covering iteration?
- **Q03d.** Partial struct init (DA-11): forbid it, or allow it and rely on
  field-wise DA?
- **Q03e.** What does DA report? One error per binding ("`x` used
  uninitialized at line N") or one per use site?
- **Q03f.** Does DA run before or after generic instantiation? Before
  (treating `$T` uniformly) is simpler. After catches more: a `$T = i32`
  instantiation might initialize to literal 0 implicitly, but
  `$T = NonZero<i32>` cannot.
- **Q03g.** Self-referential init (DA-20): hard error, or accept silently
  (Phase A behavior, since Zig has its own rules)?
- **Q03h.** Add a `MaybeUninit<T>` type, or rely only on the `set`
  parameter mode and structural rules? Note (2026-09-16): `set` is not
  accepted (ledger L6 scope limit).

## Source citations

- No DA pass exists: `a7/passes/type_checker.py` has no relevant function.
  The feature is greenfield. Still true on 2026-09-16 (see "Current
  behavior").
- Iterative traversal to reuse: `a7/passes/semantic_validator.py:140-236`.
- Backend emission of uninit locals varies. Phase A cited
  `build/debug/zig/src/002_var.zig:22-23`; the line is now
  `002_var.zig:27`, `const value: i32 = 0;`. Emission code:
  `a7/backends/zig.py:685-691`.
- Examples to audit: every example with a variable declaration, starting
  with `examples/002_var.a7`.

## Phase C decision inputs

1. Q03a, stack array policy. Drives DA-12, DA-13 and much of the
   migration.
2. Q03b, address-taken locals. Drives DA precision and complexity.
3. Q03d, partial struct init policy.
4. Q03e, diagnostic shape.
5. Q03h, `MaybeUninit<T>` or not.
6. Q03f, DA before or after generic instantiation.

The other questions follow.
