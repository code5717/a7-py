# Parameter Modes — Research Notes for Cluster CC

> Phase C research input. Companion to `narrowing.md`,
> `conversions.md`, and `compile-time-knowledge.md`. Designs
> A7's ownership and parameter-passing surface, informed by the
> Odin / Hylo / Swift / Mojo precedents and constrained by the
> contract: zero runtime errors, simple syntax, native
> performance.

## The design directive

The user's stated directions for this cluster:

1. **Function parameters are immutable** (Odin / Zig style).
2. **The user shouldn't need to write parameter modes** —
   inference is the default; the keywords (`borrow`, `inout`,
   `consume`) remain available for explicit API contracts but
   are not required.
3. **References exist only as parameter modes** (Hylo /
   confirmed earlier). No storable refs in v1.
4. **Concurrency model committed: channels + isolated owned
   data**. No reference capabilities, no shared mutable state
   across tasks.
5. **`del p` consumes** `p`; subsequent use is a compile error.

The cluster locks in the parameter-passing vocabulary
(inferred by default, explicit at API boundaries), the
ownership rules, and the channel-and-task primitives for
concurrency.

## The inference algorithm

For each parameter `x` in a function `f`, the compiler walks
the body and tracks the highest-strength use:

| Lattice level | Use site | Mode |
| --- | --- | --- |
| 0 — borrow | Read only: `x.field`, `x[i]` rhs, `f(x)` where `f` takes `borrow`, etc. | `borrow` |
| 1 — inout | Write: `x = ...`, `x.field = ...`, `x[i] = ...`, passed to an `inout` parameter, etc. | `inout` |
| 2 — consume | Consumed: `del x`, passed to a `consume` parameter, returned, stored in a struct field, etc. | `consume` |

Final mode = `max` of all use-site lattice levels (with `borrow
< inout < consume`).

**Example walkthrough:**

```a7
// User writes:
print :: fn(s: []u8) {
    io.println("{}", s)          // read-only use → borrow
}
// Compiler infers: s: borrow []u8

fill :: fn(b: []u8) {
    for i := 0; i < b.length; i += 1 {
        b[i] = 0                  // write → inout
    }
}
// Compiler infers: b: inout []u8

release :: fn(p: ref Buf) {
    use(p)                        // read → borrow (level 0)
    del p                         // del → consume (level 2)
}
// Compiler infers: p: consume ref Buf (max of 0 and 2)
```

The user never types `borrow`, `inout`, `consume` unless they
want to **lock the API contract** at a function boundary
(e.g., to prevent a future maintainer from accidentally
adding mutation to a `borrow` function).

## What A7 has today

From the existing examples and audit:

- A7 has `ref T` as a pointer type.
- A7 has `new T` for heap allocation, returning `ref T` (or
  `?ref T` per CA D.013's predecessor — but with CA's revision,
  the nullability is by-allocator-failure: `new T` returns
  `?ref T` because allocation can fail).
- A7 has `del p` for deallocation.
- A7 has methods (per `docs/SPEC.md`).
- A7 currently has no parameter modes; everything is passed
  by value (with copying) or by reference (via `ref T`).
- A7 currently has no move analysis; aliasing is unchecked.

## The four parameter modes A7 will adopt

Following the Hylo / Swift / Mojo lineage:

| Mode | Read | Write | Caller still owns at return? | Lowers to (Zig) |
| --- | --- | --- | --- | --- |
| (default) | ✅ | ❌ | ✅ | by-value copy if `Copy`; auto-pointer if non-`Copy` (Odin-style) |
| `borrow T` | ✅ | ❌ | ✅ | `*const T` |
| `inout T` | ✅ | ✅ | ✅ (after return) | `*T` |
| `consume T` | (consumed) | (consumed) | ❌ | by-value move |

### The default mode is "borrow" by another name

Per Odin's "all parameters are immutable" rule, A7's **default**
parameter mode is effectively `borrow`: the callee can read but
not write, and the caller still owns the value after the call.

For small `Copy` types (numerics, booleans, enum tags), the
compiler emits a by-value copy — efficient. For larger
non-`Copy` types (slices, strings, refs), the compiler emits an
auto-pointer — same as Odin.

The user **doesn't write `borrow`** for the default case; it's
implicit. The keyword `borrow` exists for emphasis or when
disambiguation is needed (rare).

## The full table — what the user writes

```a7
// Default (immutable, caller owns):
read_only :: fn(x: int, s: string) {
    // x is read; can't write x = ...
    // s is read; can't write s.bytes[0] = ...
}

// Explicit borrow (same as default but explicit):
print_buf :: fn(b: borrow []u8) {
    io.println("got {} bytes", b.length)
    // b[0] = 0   // compile error: borrow is read-only
}

// inout: caller's value is mutated:
fill :: fn(b: inout []u8) {
    for i := 0; i < b.length; i += 1 {
        b[i] = 0
    }
}

// consume: ownership transferred to the callee:
take :: fn(p: consume ref Buf) {
    // p is now owned by this function
    // caller cannot use the value after the call
    process(p)
}
```

Call sites — **no sigils** (matching Mojo's design):

```a7
main :: fn() {
    n: int = 5
    read_only(n, "hi")       // n and "hi" passed by default
    print_buf([1, 2, 3])     // array literal passed as borrow

    buf: [4]u8 = [0, 0, 0, 0]
    fill(buf)                // implicit inout-call (see decision below)

    p: ref Buf = new Buf{...}
    take(p)                  // ownership moves to take(); p unusable after
    // use_p_again := p.val  // compile error: p was consumed
}
```

## Open: do `inout` calls need a sigil at the call-site?

Swift requires `&` at the call site: `fill(&buf)`. Mojo doesn't.
Hylo doesn't.

**Trade-off:**
- **With sigil** (`&buf`): visible at call site that `buf` might be mutated. Cost: ceremony.
- **Without sigil** (`buf`): cleaner; user looks at the function signature to know what each argument does. Cost: less explicit at call.

**Recommendation: no sigil.** Match Mojo / Hylo. The function
signature documents the mode; the call reads naturally. If the
user wants to emphasise mutation, they can — but the language
doesn't force it.

## Move analysis lattice

For each binding `x`, the compiler tracks one of three states at
each program point:

| State | Meaning | Allowed operations |
| --- | --- | --- |
| **Live** | `x` is initialised and not consumed | read, borrow, inout, consume |
| **Partially moved** | A field of `x` (e.g., `x.field`) has been consumed | read non-consumed fields; full-`x` operations are errors |
| **Consumed** | `x` has been moved out | none — compile error on use |

State transitions:

| Operation | Effect |
| --- | --- |
| `x := ...` (initialisation) | live |
| `x = new_value` | re-live; old value consumed if was non-`Copy` |
| `f(x)` (default mode) | live (unchanged) for `Copy`; consumed for non-`Copy` (because default = borrow for non-`Copy` but pass-by-value for `Copy` — wait, see note below) |
| `f(borrow x)` | live |
| `f(inout x)` | live (writes happen) |
| `f(consume x)` | consumed |
| `del x` | consumed |
| `y := x` (assignment) | `x` consumed if non-`Copy`, copied otherwise |
| Field move `y := x.f` | `x` partially-moved on field `f` |

### Note on "default" for non-Copy

Tricky: the default mode is "borrow" (immutable, caller owns).
But if the user writes `f(x)` and `f` is declared
`f(x: consume T)`, the call obviously consumes. The keyword on
the parameter side defines the mode; the default applies only
when no keyword is given.

The cleanest formulation:

- Parameter declaration uses one of `(default)`, `borrow`,
  `inout`, `consume`.
- Call site doesn't repeat the keyword; the function's
  signature determines what happens.
- The compiler checks the call-site implications (consume
  drops the binding; inout invalidates narrowings; default
  / borrow preserves).

## Call-site exclusivity for `inout`

Critical Hylo-style rule: at any single call, two `inout`
parameters cannot alias the same value:

```a7
swap :: fn(x: inout int, y: inout int) {
    tmp := x
    x = y
    y = tmp
}

main :: fn() {
    a: int = 1
    b: int = 2
    swap(a, b)                  // OK; a and b are distinct
    swap(a, a)                  // compile error: aliasing
}
```

Same for `inout` + `borrow` of the same value:

```a7
read_and_modify :: fn(r: borrow int, w: inout int) {
    // ...
}

main :: fn() {
    a: int = 5
    read_and_modify(a, a)       // compile error: read+write alias
}
```

Multiple `borrow`s of the same value: **allowed**, because
borrow is read-only.

```a7
add_two_views :: fn(a: borrow int, b: borrow int) int {
    ret a + b
}

main :: fn() {
    x: int = 7
    add_two_views(x, x)          // OK; both reads
}
```

## Aliasing detection — what the compiler checks

Two arguments alias if:

1. They are syntactically the same identifier (`f(a, a)`).
2. One is a field access of the other (`f(x.field, x)` — `x`
   covers `x.field`).
3. Both index the same slice/array with proved-equal indices
   (`f(arr[0], arr[0])` — same; or `f(arr[i], arr[i])`).
4. Both index the same slice/array with non-proved-distinct
   indices (`f(arr[i], arr[j])` — compile error unless prover
   shows `i != j`).

For (4), the prover follows the same narrowing as everywhere
else. Common case: `arr[i]` and `arr[i+1]` where the prover
trivially shows `i != i+1` — both can be `inout`.

## What this gives the user

1. **Compile-time UAF safety**: `del p` consumes; using `p`
   after is a compile error.
2. **Compile-time double-free safety**: same mechanism; second
   `del` is a use of a consumed value.
3. **Compile-time aliasing safety for `inout`**: two writers to
   the same memory are rejected.
4. **Iterator invalidation safety**: an iterator (when added)
   can't outlive a mutating call on its source, because borrow
   semantics prevent the call during iteration.
5. **No lifetime annotations**: ever. References don't survive
   beyond a call.

## What this does NOT give the user

- **Shared mutable state across functions** within one task:
  not directly. A function takes `inout` of a value while it
  runs; no other code touches that value until the call
  returns. If multiple-writers semantics is needed, the
  application architecture must change — typically using an
  `Arc<Mutex<T>>` analog (deferred to v2+).
- **Storable references**: out of scope for v1. Idioms that
  store references (callbacks holding state, observer pattern)
  need to be rewritten using indices into an owning container.
- **Self-referential structures**: a struct containing a
  reference to itself is not expressible. Use indices.

## Concurrency model — channels + isolated owned data

Per the user's earlier pick: A7's concurrency model is
**channels carrying owned (moved) values between tasks**, with
**no shared mutable state across tasks**. The actor model.

### Tasks

```a7
// Spawn a task:
go process(work)            // borrow Go's syntax
// or: spawn process(work)
```

Each task has its own stack and its own private heap region.
Cross-task communication is via channels only.

### Channels

```a7
ch: Channel<int> = Channel.new<int>(capacity: 16)

// Producer task:
go fn() {
    for i := 0; i < 100; i += 1 {
        ch.send(i)               // sends an int (owned)
    }
    ch.close()
}()

// Consumer task:
for value in ch {                 // iterates until close
    print(value)
}
```

The value travels by **move**: the sender loses ownership; the
receiver gains it. For `Copy` types (numerics), this is
indistinguishable from copying. For non-`Copy` types
(allocations), the allocation is now owned by the receiver.

### Cross-task references — forbidden

A task cannot hold a reference to a value owned by another
task. References don't survive across task boundaries; only
moved-by-value (`consume`-equivalent) data crosses.

```a7
go fn() {
    p: ref Buf = new Buf{...}
    other_task.send(borrow p)    // compile error: borrow doesn't cross tasks
    other_task.send(consume p)   // OK; p is moved; this task loses ownership
}()
```

### Why this is safe by construction

- Each task owns its data.
- Cross-task transfer is by move (full ownership transfer).
- No two tasks can simultaneously hold writable references to
  the same memory.
- **No locks are needed** because no sharing is possible.

The model is **single-writer-at-a-time enforced by the type
system**, where the writer is either a function-local `inout`
or a task that received ownership via a channel.

### Trade-off vs. Pony's six capabilities

Pony's six caps (iso / val / ref / box / tag / trn) let you
share `val` (immutable) values freely and isolate `iso`
(unique-ownership) values for transfer. A7's simpler model:

- Immutable data can be shared **within a task** as `borrow`.
- Across tasks, **only moves** are allowed.

A7 loses the "shared immutable across tasks" capability that
Pony has. The cost: in concurrency-heavy code, immutable
shared snapshots must be copied at the channel boundary
instead of shared via reference count. The benefit: simpler
mental model, no six-cap vocabulary, no `recover` blocks.

For v1, the simpler model is the right pick. If
shared-immutable-across-tasks becomes a performance bottleneck,
v2 can add an `Arc<T>` analog without breaking the v1 surface.

## Comparison to other languages

| Language | Param-mode keywords | Default mode | Aliasing check | Storable refs |
| --- | --- | --- | --- | --- |
| **Rust** | `&`, `&mut`, owned | owned (move) | Borrow checker (lifetime-based) | Yes |
| **Swift** | `borrowing`, `consuming`, `inout` | borrowing | Law of Exclusivity (static + runtime) | Yes (with `~Escapable`) |
| **Hylo** | `let`, `inout`, `sink`, `set` | `let` | Call-site exclusivity (static only) | No |
| **Mojo** | `borrowed`, `inout`, `owned` | `borrowed` | Argument exclusivity (static) | Yes (with `Reference[lifetime]`) |
| **Odin** | (all immutable) | immutable | n/a | Yes (raw pointers) |
| **Zig** | (immutable params) | immutable | n/a | Yes (raw pointers) |
| **A7 proposed** | (default), `borrow`, `inout`, `consume` | (default = borrow) | Call-site exclusivity (static only, like Hylo) | **No** |

A7 lands between Hylo (no storable refs) and Mojo (no
caller-side sigils). The closest production analog is **Mojo
without the storable-ref escape**.

## Open questions for Cluster CC

Each becomes a numbered decision.

1. **Default param mode keyword name**: just no annotation, or
   the literal word `borrow`? Recommendation: no annotation
   (cleaner); `borrow` available for emphasis.
2. **`consume` vs `sink` vs `owned`**: which keyword? `consume`
   (Swift) reads English-clearly. **Recommendation: `consume`.**
3. **Caller-side sigils for `inout`**: yes / no. Recommendation:
   no (Mojo).
4. **`Copy` inference rules**: structural? Recommendation: yes
   (already from CA D.021).
5. **What types are `Copy` by default**: primitives + bool +
   enums-without-payload + structs of `Copy` fields.
   Recommendation: structural (compiler-inferred).
6. **Partial move semantics**: allowed? Recommendation: yes,
   per-field.
7. **Self-move detection** (`f(inout x, inout x)`): syntactic
   only, or also tracking field aliases? Recommendation:
   syntactic + simple field-path equivalence (so `f(x.a, x.a)`
   is rejected but `f(x.a, x.b)` is allowed).
8. **`del` consume vs free**: `del p` consumes the binding and
   schedules the deallocation. Recommendation: yes;
   double-`del` is compile error (use after consume).
9. **Scope-exit drop**: when a non-`Copy` binding goes out of
   scope without being consumed, what happens? Three options:
   - **Auto-drop** (Rust style): compiler emits `del` at scope
     exit. Convenient.
   - **Explicit-only** (require `del p` somewhere): forces the
     user to think about it.
   - **Compile error** ("unconsumed value at scope exit"):
     strictest.
   Recommendation: **auto-drop** for ergonomics; the user
   doesn't write `del` for every local.
10. **Channel API surface**: `Channel.new<T>(capacity)`,
    `ch.send(v)`, `ch.recv() -> ?T`, `ch.close()`, `for v in
    ch` iteration. Plus `select { case ch1.recv() -> v: ...
    case ch2.send(v): ... }` for multi-channel waits (later
    addition).
11. **Task spawn syntax**: `go fn() { ... }()` (Go style) or
    `spawn { ... }` (Pony) or method-call?
    Recommendation: **`go`** (Go style; short, familiar).
12. **Stack size for spawned tasks**: configured how?
    Recommendation: same compile-time stack-budget analysis as
    main (CE).

## What's deferred to v2+

- Shared immutable data across tasks (Pony's `val` cap or
  `Arc<T>` analog).
- Storable references (Rust's `&T` in a struct).
- Self-referential structures.
- User-defined custom destructors (Rust's `Drop` trait).
- Asynchronous task cancellation.
- `select { ... }` over multiple channels.

## Cross-references

- [`narrowing.md`](./narrowing.md) — invalidation rules for
  narrowings under `inout` calls.
- [`08-decisions.md`](./08-decisions.md) — CA + CB ACCEPTED;
  CC follows.
- [`comparative/hylo.md`](./comparative/hylo.md) — the
  parameter-mode model A7 most closely follows.
- [`comparative/swift.md`](./comparative/swift.md) — production
  reference for borrowing/consuming/inout.
- [`comparative/pony.md`](./comparative/pony.md) — the
  alternative (reference capabilities) A7 is NOT adopting.
- [`comparative/inko-koka-verona.md`](./comparative/inko-koka-verona.md)
  — Inko's isolated-heap model that informed A7's concurrency
  choice.

## Estimated Cluster CC decision count

Ownership / params: ~10 decisions (D.040 — D.049)
Concurrency: ~4 decisions (D.050 — D.053)

Total: ~14 decisions.
