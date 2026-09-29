# Parameter Modes — Research Notes for Cluster CC

> Status: Phase C research proposal, added in commit 86819f5 (2026-05-11). Not
> approved. The parameter-mode keywords (D.040, D.041, D.049) were not accepted,
> and the [memory plan](../plan/memory.md) makes ownership internal. The
> [decision ledger](../plan/decisions.md) overrides this file.

Companion to [`narrowing.md`](./narrowing.md), `conversions.md` and
`compile-time-knowledge.md`. This file designs A7's ownership and
parameter-passing surface from the Odin, Hylo, Swift and Mojo precedents, under
the contract: zero runtime errors, simple syntax, native performance.

## Where this stands (2026-09-16)

| Topic in this file | Newer record | Effect |
| --- | --- | --- |
| Immutable parameters | L6: argument bindings are immutable | Principle approved; no mode syntax approved. `ref` parameters remain the working form |
| `borrow` / `inout` / `consume` keywords, inferred modes | Proposed D.040, D.041, D.049 not accepted; ledger O2 replaced by the memory plan | Keywords are not planned for user code |
| No storable references | Memory plan gate M4 | Direction kept: `ref` only as a parameter, never stored or returned |
| Call-site exclusivity | Memory plan §1 item 8.1, corpus 14 | Direction kept, enforced internally |
| `del p` consumes | Memory plan gate M3 | `del` removed from ordinary code |
| Scope-exit auto-drop (Q9) | Memory plan §1 item 5 | Direction kept: the compiler places releases |
| `go` tasks, move-only channels | Memory plan gates M10, M27, M36 | Tasks are structured (no detach); children may read parent values the parent does not change |
| `int` in examples | L4: explicit widths only | Examples below use `i32` (originally `int`) |

Examples below are proposals. They are labeled "Proposed" unless they show
current syntax.

## The design directive

The user's directions for this cluster at the time:

1. **Function parameters are immutable** (Odin / Zig style).
2. **Users should not need to write parameter modes.** The compiler infers them.
   The keywords `borrow`, `inout` and `consume` stay available to lock an API
   contract, but are never required.
3. **References exist only as parameter modes** (Hylo). No storable references
   in v1.
4. **Concurrency: channels plus isolated owned data.** No reference
   capabilities and no shared mutable state across tasks.
5. **`del p` consumes `p`.** Any later use is a compile error.

The cluster fixes the parameter vocabulary (inferred by default, explicit at API
boundaries), the ownership rules, and the channel and task primitives.

## The inference algorithm

For each parameter `x` of a function `f`, the compiler walks the body and keeps
the strongest use:

| Level | Use site | Mode |
| --- | --- | --- |
| 0 | Read only: `x.field`, `x[i]` on the right side, passing `x` to a `borrow` parameter | `borrow` |
| 1 | Write: `x = ...`, `x.field = ...`, `x[i] = ...`, passing `x` to an `inout` parameter | `inout` |
| 2 | Consume: `del x`, passing `x` to a `consume` parameter, returning it, storing it in a struct field | `consume` |

The final mode is the maximum level over all uses (`borrow < inout < consume`).

```a7
// Proposed
print :: fn(s: []u8) {
    io.println("{}", s)          // read only → borrow
}
// Inferred: s: borrow []u8

fill :: fn(b: []u8) {
    i: usize = 0
    while i < b.length {
        b[i] = 0                  // write → inout
        i += 1
    }
}
// Inferred: b: inout []u8

release :: fn(p: ref Buf) {
    use(p)                        // read → level 0
    del p                         // del → level 2
}
// Inferred: p: consume ref Buf (max of 0 and 2)
```

Users write `borrow`, `inout` or `consume` only to lock the contract at a
function boundary, for example to stop a later maintainer from adding mutation
to a `borrow` function.

## What A7 has today

At the time of writing:

- `ref T` is a pointer type.
- `new T` allocates on the heap and returns a reference that is `nil` when
  allocation fails (the original text tied this nullable result, `?ref T`, to
  CA D.013 and its revision).
- `del p` frees.
- Methods exist (`docs/SPEC.md`).
- There are no parameter modes. Values pass by copy, or by reference through
  `ref T`.
- There is no move analysis, and aliasing is unchecked.

Note (2026-09-16): `docs/SPEC.md` §8.4 now says direct reads after `del` are
rejected until the binding is reassigned; aliasing and double free are still
unchecked. The memory plan records that aliased `ref` arguments such as
`both(x, x)` compile today in A7 and Zig, and proposes rejecting them.

```a7
// Current A7: a ref parameter changes the caller's value
increment :: fn(p: ref i32) {
    p += 1
}

main :: fn() {
    x: i32 = 10
    increment(x)              // no sigil at the call site
}
```

## The four parameter modes A7 will adopt

Following Hylo, Swift and Mojo:

| Mode | Read | Write | Caller still owns after the call | Zig lowering |
| --- | --- | --- | --- | --- |
| (default) | Yes | No | Yes | Copy if `Copy`; automatic pointer if not (Odin style) |
| `borrow T` | Yes | No | Yes | `*const T` |
| `inout T` | Yes | Yes | Yes | `*T` |
| `consume T` | Consumed | Consumed | No | By-value move |

### The default mode is "borrow" by another name

Following Odin's rule that all parameters are immutable, the default mode acts
like `borrow`: the callee reads but does not write, and the caller keeps
ownership.

Small `Copy` types (numbers, booleans, enum tags) pass by copy. Larger
non-`Copy` types (slices, strings, references) pass by automatic pointer, as in
Odin.

Users do not write `borrow` for the default. The keyword exists for emphasis or
the rare case that needs disambiguation.

Note (2026-09-16): a later review
(`docs/plan/research/ownership-zig-odin-glm.md`) reports that Odin and Zig
parameters are immutable bindings but still allow writes through a pointer or
slice. Deep read-only access, as `can't write s.bytes[0]` below implies, is not
what those languages do; that review names Jai-style deep const as the closer
precedent.

## The full table — what the user writes

```a7
// Proposed
// Default: immutable, caller owns
read_only :: fn(x: i32, s: string) {
    // x = ...          not allowed
    // s.bytes[0] = ... not allowed
}

// Explicit borrow: same as the default
print_buf :: fn(b: borrow []u8) {
    io.println("got {} bytes", b.length)
    // b[0] = 0   // compile error: borrow is read-only
}

// inout: the caller's value changes
fill :: fn(b: inout []u8) {
    i: usize = 0
    while i < b.length {
        b[i] = 0
        i += 1
    }
}

// consume: ownership moves to the callee
take :: fn(p: consume ref Buf) {
    // the caller cannot use the value after the call
    process(p)
}
```

Call sites carry no sigils (as in Mojo):

```a7
// Proposed
main :: fn() {
    n: i32 = 5
    read_only(n, "hi")       // default mode
    print_buf([1, 2, 3])     // array literal passed as borrow

    buf: [4]u8 = [0, 0, 0, 0]
    fill(buf)                // inout call without a sigil (see below)

    p: ref Buf = new Buf{...}
    take(p)                  // ownership moves to take(); p is unusable
    // n2 := p.size          // compile error: p was consumed
}
```

Note (2026-09-16): examples changed from `int` to `i32` (L4), from C-style
`for i := 0` loops to `usize` counters in `while` loops. The
commented `p.val` became `p.size`, because public A7 has no `.val`. `new T{...}`
is not current syntax (`docs/SPEC.md` §8.2). The examples as first written are in
git commit `701c679`.

## Open: do `inout` calls need a sigil at the call-site?

Swift requires `&` at the call site: `fill(&buf)`. Mojo and Hylo do not.

| Option | Benefit | Cost |
| --- | --- | --- |
| Sigil (`&buf`) | The call site shows that `buf` may change | Ceremony |
| No sigil (`buf`) | Cleaner calls | Readers check the signature to see what each argument does |

**Recommendation: no sigil**, as in Mojo and Hylo. The signature documents the
mode.

Note (2026-09-16): current A7 already passes `ref` arguments without a sigil,
and public A7 has no prefix `&` (`CLAUDE.md`). A sigil would add a new operator.

## Move analysis lattice

For each binding `x`, the compiler tracks one state at each program point:

| State | Meaning | Allowed operations |
| --- | --- | --- |
| Live | Initialized and not consumed | read, borrow, inout, consume |
| Partially moved | A field such as `x.field` was consumed | read unconsumed fields; whole-`x` operations are errors |
| Consumed | Moved out | none; any use is a compile error |

Transitions:

| Operation | Effect on `x` |
| --- | --- |
| `x := ...` | Live |
| `x = new_value` | Live again; the old non-`Copy` value is consumed |
| `f(x)`, parameter has no keyword | `Copy`: unchanged. Non-`Copy`: unresolved (see note below) |
| `f(x)`, parameter is `borrow` | Unchanged |
| `f(x)`, parameter is `inout` | Unchanged; writes happen |
| `f(x)`, parameter is `consume` | Consumed |
| `del x` | Consumed |
| `y := x` | Consumed if non-`Copy`; copied otherwise |
| `y := x.f` | Partially moved on field `f` |

### Note on "default" for non-Copy

The parameter declaration decides the mode, never the call site. A parameter
uses one of: no keyword (default), `borrow`, `inout` or `consume`. The call site
does not repeat the keyword.

The original table cell for `f(x)` with no keyword read "consumed for non-`Copy`
(because default = borrow for non-`Copy` but pass-by-value for `Copy` — wait,
see note below)". The two readings conflict:

| Source | `f(x)`, no keyword, non-`Copy` `x` |
| --- | --- |
| This note (original text) | The default acts as `borrow`, so `x` stays live |
| [D.043 in 08-decisions.md](./08-decisions.md) | `x` becomes consumed |

This file never settled the question. D.041 later made modes inferred for
private functions and required for public ones, so the "no keyword" case means
"inferred mode" rather than a fixed default.

The compiler checks each call's effects: `consume` ends the binding, `inout`
invalidates narrowings, and `borrow` keeps both.

## Call-site exclusivity for `inout`

Hylo's rule: in one call, two `inout` parameters cannot alias the same value.

```a7
// Proposed
swap :: fn(x: inout i32, y: inout i32) {
    tmp := x
    x = y
    y = tmp
}

main :: fn() {
    a: i32 = 1
    b: i32 = 2
    swap(a, b)                  // OK: distinct
    swap(a, a)                  // compile error: aliasing
}
```

The same holds for `inout` plus `borrow` of one value:

```a7
// Proposed
read_and_modify :: fn(r: borrow i32, w: inout i32) {
    // ...
}

main :: fn() {
    a: i32 = 5
    read_and_modify(a, a)       // compile error: read and write alias
}
```

Several `borrow`s of one value are allowed, because `borrow` is read-only:

```a7
// Proposed
add_two_views :: fn(a: borrow i32, b: borrow i32) i32 {
    ret a + b
}

main :: fn() {
    x: i32 = 7
    add_two_views(x, x)          // OK: both read
}
```

Note (2026-09-16): the memory plan keeps this rule with current syntax: two
`ref` arguments naming the same place are an exclusivity error, and
`swap(a[i], a[j])` with unknown indices is rejected unless they are proven
distinct (corpus 14).

## Aliasing detection — what the compiler checks

Two arguments alias when:

1. They are the same identifier: `f(a, a)`.
2. One is a field of the other: `f(x.field, x)`.
3. They index the same array or slice with indices proved equal:
   `f(arr[0], arr[0])` or `f(arr[i], arr[i])`.
4. They index the same array or slice with indices not proved distinct:
   `f(arr[i], arr[j])` is a compile error unless the prover shows `i != j`.

For case 4 the prover uses the same narrowing as elsewhere. `arr[i]` and
`arr[i+1]` are trivially distinct, so both can be `inout`.

## What this gives the user

1. **No use after free at compile time.** `del p` consumes; using `p` afterward
   is an error.
2. **No double free at compile time.** A second `del` uses a consumed value.
3. **No aliased writes.** Two `inout` arguments to the same memory are rejected.
4. **No iterator invalidation.** An iterator, once added, cannot outlive a
   mutating call on its source, because borrow rules block that call during
   iteration.
5. **No lifetime annotations.** References never outlive a call.

## What this does NOT give the user

- **Shared mutable state across functions in one task.** A function holds
  `inout` access while it runs; nothing else touches the value until it returns.
  Multiple writers need a different architecture, typically an `Arc<Mutex<T>>`
  analog (v2 or later).
- **Storable references.** Out of scope for v1. Code that stores references
  (callbacks with state, observers) must use indices into an owning container.
- **Self-referential structures.** A struct cannot hold a reference to itself.
  Use indices.

Note (2026-09-16): the memory plan answers the index case with `usize`
positions and generation-tagged `Id(T)` handles (gates M1, M5), as in
`examples/025_linked_list.a7` and `examples/026_binary_tree.a7`.

## Concurrency model — channels + isolated owned data

The user chose channels that carry owned (moved) values between tasks, with no
shared mutable state across tasks: the actor model.

Note (2026-09-16): the memory plan proposes structured tasks instead of
free-running ones. A task ends before the scope that started it; scope exit
cancels and joins children; there is no detach in v1 (M10). Children may read
parent values that the parent does not change until they finish (M36), which
relaxes "only moves cross tasks". Channels close explicitly or when the task
group ends (M27). None of this is approved, and A7 has no task syntax today.

### Tasks

```a7
// Proposed
go process(work)            // Go-style syntax
// or: spawn process(work)
```

Each task has its own stack and private heap region. Tasks communicate only
through channels.

### Channels

```a7
// Proposed
ch: Channel<i32> = Channel.new<i32>(capacity: 16)

// Producer task
go fn() {
    i: i32 = 0
    while i < 100 {
        ch.send(i)               // sends an owned i32
        i += 1
    }
    ch.close()
}()

// Consumer
for value in ch {                 // iterates until close
    print(value)
}
```

Values travel by move: the sender loses ownership and the receiver gains it. For
`Copy` types this is the same as copying. For allocations, the receiver now owns
the allocation.

### Cross-task references — forbidden

A task cannot hold a reference to a value another task owns. Only moved data
crosses task boundaries.

```a7
// Proposed
go fn() {
    p: ref Buf = new Buf{...}
    other_task.send(borrow p)    // compile error: borrow does not cross tasks
    other_task.send(consume p)   // OK: p moves; this task loses it
}()
```

### Why this is safe by construction

- Each task owns its data.
- Transfer between tasks is a full move.
- No two tasks can hold writable references to the same memory at once.
- No locks are needed, because nothing is shared.

The type system enforces one writer at a time. The writer is either a
function-local `inout` or the task that received ownership through a channel.

### Trade-off vs. Pony's six capabilities

Pony's six capabilities (`iso`, `val`, `ref`, `box`, `tag`, `trn`) let
immutable `val` values be shared freely and unique `iso` values be transferred.
A7's simpler model:

- Immutable data is shared within a task as `borrow`.
- Only moves cross tasks.

A7 gives up Pony's shared immutable data across tasks. In concurrency-heavy code,
immutable snapshots are copied at the channel boundary instead of shared through
reference counts. In return, the model is simpler: no six-capability vocabulary
and no `recover` blocks.

For v1 the simpler model is the right choice. If sharing immutable data across
tasks becomes a bottleneck, v2 can add an `Arc<T>` analog without breaking v1
code.

## Comparison to other languages

| Language | Mode keywords | Default mode | Aliasing check | Storable refs |
| --- | --- | --- | --- | --- |
| Rust | `&`, `&mut`, owned | owned (move) | Borrow checker (lifetimes) | Yes |
| Swift | `borrowing`, `consuming`, `inout` | borrowing | Law of Exclusivity (static and runtime) | Yes (with `~Escapable`) |
| Hylo | `let`, `inout`, `sink`, `set` | `let` | Call-site exclusivity (static only) | No |
| Mojo | `borrowed`, `inout`, `owned` | `borrowed` | Argument exclusivity (static) | Yes (with `Reference[lifetime]`) |
| Odin | none (all immutable) | immutable | n/a | Yes (raw pointers) |
| Zig | none (immutable params) | immutable | n/a | Yes (raw pointers) |
| A7 proposed | (default), `borrow`, `inout`, `consume` | default = borrow | Call-site exclusivity (static only, like Hylo) | No |

A7 sits between Hylo (no storable references) and Mojo (no caller-side sigils).
The closest production analog is Mojo without storable references.

Note (2026-09-16): language rows were not re-verified. Mojo has since renamed
some argument conventions (for example `borrowed` to `read` and `inout` to
`mut`); check current Mojo docs before citing. The Odin/Zig review above
suggests adding a qualified Jai row.

## Open questions for Cluster CC

Each question was to become a numbered decision.

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | Default mode: no annotation, or the word `borrow`? | No annotation; `borrow` available for emphasis |
| 2 | `consume`, `sink` or `owned`? | `consume` (Swift); reads as plain English |
| 3 | Caller-side sigils for `inout`? | No (Mojo) |
| 4 | Infer `Copy` structurally? | Yes (from CA D.021) |
| 5 | Which types are `Copy` by default? | Primitives, `bool`, enums without payload, structs of `Copy` fields; inferred structurally |
| 6 | Partial moves allowed? | Yes, per field |
| 7 | Self-alias detection (`f(inout x, inout x)`): syntactic only, or field paths too? | Syntactic plus simple field-path equality: reject `f(x.a, x.a)`, allow `f(x.a, x.b)` |
| 8 | Does `del p` consume the binding and schedule the free? | Yes; a second `del` is use after consume |
| 9 | What happens when a non-`Copy` binding leaves scope unconsumed? | Auto-drop (see below) |
| 10 | Channel API | `Channel.new<T>(capacity)`, `ch.send(v)`, `ch.recv() -> ?T`, `ch.close()`, `for v in ch`; later `select { case ch1.recv() -> v: ... case ch2.send(v): ... }` |
| 11 | Task spawn syntax: `go fn() { ... }()` (Go), `spawn { ... }` (Pony) or a method call? | `go`: short and familiar |
| 12 | Stack size for spawned tasks? | The same compile-time stack-budget analysis as `main` (Cluster CE) |

Options for question 9:

| Option | Behavior | Trade-off |
| --- | --- | --- |
| Auto-drop (Rust style) | Compiler emits `del` at scope exit | Convenient |
| Explicit only | User must write `del p` somewhere | Forces thought about every release |
| Compile error | "unconsumed value at scope exit" | Strictest |

Recommendation: auto-drop, so users do not write `del` for every local.

Note (2026-09-16): questions 1–3 and 8 assume user-facing keywords and `del`,
which the ledger and memory plan no longer plan for. Questions 4–7 and 9 carry
over as internal compiler rules. Questions 10–12 are open under memory plan
gates M10, M26 and M27 and v1 gates G7 and G8.

## What's deferred to v2+

- Shared immutable data across tasks (Pony's `val` or an `Arc<T>` analog).
- Storable references (Rust's `&T` in a struct).
- Self-referential structures.
- User-defined destructors (Rust's `Drop`).
- Asynchronous task cancellation.
- `select { ... }` over multiple channels.

## Cross-references

- [`narrowing.md`](./narrowing.md) — how `inout` calls invalidate narrowings.
- [`08-decisions.md`](./08-decisions.md) — Clusters CA and CB accepted; CC
  (D.040–D.053) stayed proposed, and the ledger lists D.040, D.041 and D.049 as
  not accepted.
- [`comparative/hylo.md`](./comparative/hylo.md) — the parameter-mode model A7
  most closely follows.
- [`comparative/swift.md`](./comparative/swift.md) — production reference for
  borrowing, consuming and inout.
- [`comparative/pony.md`](./comparative/pony.md) — reference capabilities, the
  alternative A7 does not adopt.
- [`comparative/inko-koka-verona.md`](./comparative/inko-koka-verona.md) —
  Inko's isolated-heap model, which informed the concurrency choice.
- [`../plan/decisions.md`](../plan/decisions.md) and
  [`../plan/memory.md`](../plan/memory.md) — the current records.

## Estimated Cluster CC decision count

About 14 decisions: ownership and parameters ~10 (D.040–D.049), concurrency ~4
(D.050–D.053). Of these, D.040, D.041 and D.049 are recorded as not accepted.
