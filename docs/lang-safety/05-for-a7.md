# 05 — Take-aways for A7: Zero Runtime Errors

> Part of the `docs/lang-safety/` series. See the
> [README](./README.md) for the full map. Siblings:
> [01 — InvisiCaps](./01-invisicaps.md) ·
> [02 — Sanitizers](./02-sanitizers.md) ·
> [03 — Hardware-assisted safety](./03-hardware.md) ·
> [04 — Comparison](./04-comparison.md) ·
> [06 — Compile-time techniques](./06-compile-time-safety.md).

The design directive — strengthened twice:

> **A7 must catch every safety hazard at compile time. The A7
> compiler must emit Zig source that is memory-safe on its own —
> not because Zig was invoked with any particular flag, not because
> `-O ReleaseSafe` inserts runtime checks. The emitted Zig must be
> safe even when compiled with `-O ReleaseFast` (all Zig safety
> checks disabled).** The A7 compiler is the proof carrier; Zig is
> just the backend.

Anything that could fail becomes either:

1. A **compile error** (the prover discharges the obligation, or the
   user fixes the code), or
2. A **typed value** in the result (`?T`, `Result<T, E>`, ranged
   integers, capability tokens) that the user must consume.

The emitted Zig **never** contains:

- A bare `s[i]` with an unbounded index.
- A bare `p.*` on an optional `?*T` not already unwrapped.
- A bare `a + b` on opaque integers (always `+%`, `+|`,
  `@addWithOverflow`, or proved-safe `+`).
- A bare `a / b` with `b` not proved non-zero at the call site.
- A recursive call (A7 already forbids recursion).
- `unreachable` reached at runtime (only at type-proven dead
  branches).
- `@panic` for any condition the user did not explicitly request.

Nothing the compiler emits traps on its own. The catalog of
compile-time techniques is in [06](./06-compile-time-safety.md); this
file is the A7-specific synthesis under the zero-runtime-error
contract.

The trade is real: A7 becomes a **total** language in the spirit of
SPARK/Ada or F*, not a pragmatic language in the spirit of Rust (which
still panics on bounds, overflow in debug, integer divide-by-zero,
and `unwrap`). The expressiveness ceiling is lower; the guarantee is
stronger.

### The Zig backend is the proof witness, not the proof author

This is the conceptual shift. In the previous draft, A7 was treated as
"a language whose backend conveniently emits safe code." Under the
zero-runtime-error contract, the picture inverts:

- The **A7 frontend and middle-end** discharge every safety
  obligation.
- The **A7 codegen** lowers each obligation to a Zig construct that
  *structurally* cannot violate it — i.e., the safety property is
  encoded in the **shape** of the emitted Zig, not in a runtime
  check.
- The **Zig compiler** is a non-trusted backend. Compiling the
  emitted Zig with `-O ReleaseFast` (all safety checks off) produces a
  binary with identical safety properties to compiling it with `-O
  ReleaseSafe`. This is the test: a fuzz farm builds release-fast
  binaries and observes no crashes that aren't caused by the user
  matching `null` with `unreachable()`.

If a future Zig version weakens its safety story, A7 is unaffected.
If a future Zig version *strengthens* its safety story, A7 is
unaffected. The contract is a property of the emitted code, not of
the Zig compiler.

## 1. The zero-runtime-error contract

Every failure mode below must be either rejected at compile time or
surfaced through the type system as a `Result`/`Option`/refined-int
value the user is forced to handle. **No mechanism in the compiled
output traps, panics, aborts, or invokes UB on its own.**

| Hazard | Compile-time mechanism / typed return |
| --- | --- |
| Uninitialized read | §1 Definite-assignment flow analysis ⇒ compile error |
| Null dereference | §2 Non-null `ptr T` vs nullable `?ptr T` ⇒ compile error or forced match |
| Missed enum variant | §3 Exhaustive pattern matching ⇒ compile error |
| Type confusion | No raw casts admitted at the source level ⇒ unreachable by construction |
| Use-after-free | §4 Affine ownership + §6 region inference ⇒ compile error |
| Double-free | §4 Affine ownership ⇒ compile error (moved value cannot be `del`d) |
| Leak (in scope) | §4 + scope-exit `Drop` ⇒ compile error if a value is unconsumed |
| Slice out-of-bounds | §10 Pattern-proved indexing OR `try_get(i) -> ?T` ⇒ compile error or forced match |
| Integer overflow | Typed arithmetic: `checked_add` (`-> ?T`), `wrap_add`, `sat_add`, or ranged types whose ranges prove non-overflow ⇒ compile error if user uses bare `+` on opaque values |
| Integer division by zero | Divisor must be a `NonZero<T>`; constructed by `NonZero::new(x) -> ?NonZero<T>` ⇒ compile error if a bare `int` is passed |
| Integer division remainder of `INT_MIN / -1` | Same `NonZero<T>` + `NonNegOne<T>` discipline, or use `wrap_div` ⇒ compile error |
| Floating-point NaN / inf | Operations return `?f64` (None on non-finite result) OR `Fin<f64>` typed values ⇒ compile error if propagated as plain `f64` |
| Pointer arithmetic OOB | No pointer arithmetic at the source level ⇒ unreachable |
| Stack overflow | Compile-time max-stack-depth analysis (A7's call graph is a DAG, no recursion) ⇒ compile error if static budget exceeded |
| Heap allocation failure | `new T{...}` returns `?ptr T`; user must match ⇒ no silent trap |
| Data race | Currently N/A (no threads). When added: §8 mutable value semantics or §9 capabilities ⇒ compile error |
| Foreign code (FFI) | Out-of-language. FFI shim is the **only** site where a typed boundary is drawn explicitly and the user opts in to whatever the foreign function promises; nothing the language can prove. |

The right column is the **complete** safety contract. There is no
hidden "but also..." list of runtime traps.

### 1.1 The narrow exception: FFI

The one boundary the language cannot police is calls into foreign
code (C libraries, OS syscalls). A7 must mark FFI shims explicitly
(an `extern` declaration or similar) and document that everything
beyond the shim is the user's responsibility. The shim's *return
type*, however, must still be a typed `Result` — a foreign function
that "might fail" returns `Result<T, ForeignError>`, and the
compiler enforces the match.

Even here there is **no silent trap from the language itself**. If
the foreign function corrupts memory, the OS may segfault — but
that's not the language emitting code that panics; that's hardware
catching a foreign-induced violation.

## 2. What A7 already proves statically

A quick audit against `a7/types.py`, `a7/passes/`, `docs/SPEC.md`:

| Property | Status |
| --- | --- |
| No raw pointer arithmetic in source | ✅ |
| No `inttoptr` syntax | ✅ |
| No `unsafe` block | ✅ |
| No untagged unions | ✅ |
| Recursion banned (semantic validator) | ✅ |
| `usize` enforced for indices/sizes | ✅ |
| Slices/arrays carry length in the type | ✅ |
| Exhaustive `match` checking | 🔍 Verify and document. If absent, add (§3 in [06](./06-compile-time-safety.md); cheap) |
| Definite assignment of locals | 🔍 Verify and document. If absent, add (§1; cheap) |
| Non-null pointer types | ❌ Not yet — `ptr T` is currently nullable |
| Compile-time UAF prevention | ❌ Not yet — `del` is unrestricted |
| Compile-time bounds proof | ❌ Not yet — relies on Zig's runtime check |

The four "checks" are the four items that move A7 from "C with a
better type system" to "compile-time memory-safe."

## 3. The compile-time toolbox A7 should adopt

Lean version of the §06 menu. Four mechanisms, all small.

### 3.1 Definite-assignment flow analysis  ── [06 §1](./06-compile-time-safety.md#1-definite-assignment--flow-analysis)

Reads of an unassigned local are a **compile error**, not a runtime
trap. Single data-flow pass over the CFG, ~200 LoC in
`a7/passes/`. Already shipped by Java, C#, Kotlin, Rust, Swift, Zig.

**A7-specific note:** A7 already has CFG plumbing in
`a7/passes/semantic_validator.py` for the recursion check. The same
pass machinery handles definite assignment.

### 3.2 Non-null pointer types  ── [06 §2](./06-compile-time-safety.md#2-non-null-pointer-types)

```text
ptr  T   ; non-null, deref always safe
?ptr T   ; nullable, must be matched/unwrapped to deref
```

Implementation:

- Parser: recognise `?ptr T` (one token in `a7/tokens.py`).
- Types: add `nullable: bool` to `PointerType` in `a7/types.py`.
- Type checker: deref of `?ptr T` is an error; comparison or
  `if x is null` narrows.
- Backend: emits `*T` vs `?*T` to Zig — the rest is free.

This is the highest leverage / lowest cost change. Kills the entire
null-deref bug class.

### 3.3 Affine ownership for heap allocations  ── [06 §4](./06-compile-time-safety.md#4-linear--affine-types)

A `new` expression produces a value that can be **moved** but not
**aliased**. After a move, the source is unbindable.

```text
fn handoff()
    p := new Buf{...}        ; p owns the allocation
    consume(p)               ; ownership moved into consume()
    print p.size             ; compile error: use of moved value
end
```

A7's existing rules already disallow most of the patterns that make
this hard:

- No recursion → no cyclic ownership graphs to worry about.
- No raw pointer arithmetic → no aliases manufactured behind the
  type checker's back.
- No `unsafe` → no escape hatch.

The implementation is a "moved" flag per binding tracked in the same
CFG pass as definite assignment. It is *not* a full borrow checker;
sharing is not allowed except as an explicit "borrow for the call's
duration" parameter mode (see §3.4).

### 3.4 `inout` / `borrow` parameter passing  ── [06 §8](./06-compile-time-safety.md#8-mutable-value-semantics-hylo--val)

To let two callers see the same allocation without copying or
aliasing-then-UAF, A7 needs a way to pass a value *by reference*
without storing the reference. The Hylo / Swift / Mojo answer is to
make this **only a parameter-passing mode**, never a storable value:

```text
fn fill(buf: inout Buf, value: u8)
    buf.bytes[0] = value          ; mutates the caller's buf
end

fn read(buf: borrow Buf) -> u8
    return buf.bytes[0]           ; read-only access
end
```

Exclusivity is checked at each call site: an `inout` argument cannot
alias any other argument of the same call. Because references are
never stored, the analysis is purely intra-procedural — **no lifetime
annotations needed**.

This combination (§3.3 owned values + §3.4 inout/borrow modes)
delivers compile-time UAF and aliasing safety without a Rust-style
borrow checker. The whole machinery is in
[06 §8](./06-compile-time-safety.md#8-mutable-value-semantics-hylo--val).

### 3.5 Bound-proved slice indexing  ── [06 §10](./06-compile-time-safety.md#10-refinement-types)

A7 should compile every slice access `s[i]` against a *static proof*
that `0 ≤ i < s.length`. The simplest implementation is **pattern
recognition**, not a full SMT integration:

| Pattern | Static proof | Notes |
| --- | --- | --- |
| `for i in 0..s.length: s[i]` | Trivial | The loop bound *is* the slice length |
| `s[0]` after `if s.length > 0` | Flow-sensitive | Same pass as definite assignment |
| `s[i]` with `i: Index(s.length)` (named refinement) | Constructor proves bound | One refinement type, not the whole solver |
| `s[i]` with opaque `i: usize` | ❌ Compile error: bound not proved | Force the user to use a checked iterator or an explicit `try_get` |

This is **refinement-types-lite**. A handful of recognised patterns
covers ~95 % of real code. The rest must be rewritten to use one of
the recognised forms, or surface as an explicit
`s.try_get(i) -> ?T` that returns a nullable (closes back into §3.2).

There is **no `unsafe { s[i] }` escape hatch**. If the prover can't
discharge the bound, the user fixes the code.

### 3.6 (Optional) Region scopes for the cases moves don't fit

A handful of allocation patterns don't compose cleanly with affine
ownership — e.g., a function building several values and returning
all of them by reference. For those, the [Cyclone-style region
form](./06-compile-time-safety.md#6-region-inference-tofte-talpin--cyclone)
is the standard answer:

```text
fn parse(input: []u8) -> []Token
    region tokens
        ; all allocations in this scope live in tokens
        first := new Token{...}
        ; ...
    end                      ; the region frees here unless `return`ed
end
```

A7's already-DAG call graph (no recursion) makes the region lattice
trivially bounded.

This is a Phase-2 item; ship §3.1–§3.5 first.

## 4. Closing every remaining hazard — the typed-result discipline

Under the zero-runtime-error contract, the residual hazards from the
earlier draft of this file become **typed values** the user must
handle. None of them is a runtime trap.

### 4.1 Integer division — `NonZero<T>`

```text
type NonZero<T: Int> = {x: T | x != 0}    ; refinement (compile-time)

fn NonZero.new(x: int) -> ?NonZero<int>
    if x == 0 then return null end
    return some(NonZero.unchecked(x))     ; only constructor; private
end

fn divide(a: int, d: NonZero<int>) -> int
    return a / d                           ; safe by construction
end
```

The bare `/` operator is **only defined when the right-hand operand
has type `NonZero<T>`**. Dividing by an opaque `int` is a compile
error. If the user knows the value statically (a literal `5`), the
compiler refines the type automatically.

Same discipline for `%` (modulus) and `INT_MIN / -1` (which traps on
x86_64); the latter needs `NonNegOne<T>` in addition. In practice this
collapses to a single `SafeDivisor<T>` refinement.

### 4.2 Slice indexing — pattern-proved or `try_get`

The four-pattern catalog in §3.5 covers the bulk. The opaque-index
case becomes:

```text
fn lookup(s: []int, i: int) -> ?int
    return s.try_get(i)                    ; returns null if OOB
end
```

`try_get(i: int) -> ?T` is the **only** indexing operation defined on
a slice when the index is opaque. The square-bracket operator `s[i]`
requires a statically discharged bound; failing that, it's a compile
error. No runtime trap path.

### 4.3 Integer overflow — explicit arithmetic mode

```text
let a: u32 = read_input()
let b: u32 = read_input()

let c1 = a + b                  ; compile error: overflow not proved
let c2 = a.checked_add(b)       ; -> ?u32, must match
let c3 = a.wrap_add(b)          ; defined wrap; never traps
let c4 = a.sat_add(b)           ; saturates at MAX; never traps
```

The bare `+` operator is allowed only when both operands have ranges
the type checker can prove will not overflow (e.g., literals, ranged
types, induction variables of a bounded loop). For anything else, the
user picks `checked_*` / `wrap_*` / `sat_*` explicitly.

Same rule for `-`, `*`, `<<`, type narrowings, and float→int casts
(which use `?int_from(f)` returning null for NaN/inf/out-of-range).

### 4.4 Stack overflow — static budget proof

A7 already bans recursion, so the call graph is a DAG and the
maximum stack depth of any program is computable at compile time.

```text
$ uv run a7 examples/big.a7
error[E0501]: program exceeds configured stack budget
  function chain `main -> work -> deep_helper` uses 1.2 MiB,
  budget is 1.0 MiB (configure with --stack-budget BYTES)
```

The compiler emits the max-stack annotation in the binary and the
runtime sets `RLIMIT_STACK` (or the equivalent thread attribute) to
exactly that value at start-up. **The program cannot stack-overflow
because the OS would only give it what it statically requires.**

The budget covers: every function's frame size (computed from local
types), the deepest path through the call DAG, plus a small constant
for FFI shims. A function whose frame depends on a dynamic
allocation (`buf: [N]T` with non-constant `N`) is rejected unless `N`
has a refined upper bound.

### 4.5 Heap allocation — typed `Result`

```text
let p: ?ptr Buf = new Buf{...}             ; -> null on allocator failure

match p
    case some(buf): use(buf)
    case null:      handle_oom()
end
```

`new` *always* returns a nullable; there is no infallible `new`. The
user must match. For convenience, a `must_new` macro can be provided
that expands to `new` + `match ... null: unreachable()` — but
`unreachable()` is itself a *compile-time-only* term whose presence
requires a proof obligation the user satisfies (typically: the
allocation size is statically bounded and the program's stack budget
already accounts for it).

### 4.6 NaN and infinity — typed floats

```text
type Fin<f> = {x: f | !is_nan(x) && !is_inf(x)}

fn sqrt(x: Fin<f64>) -> ?Fin<f64>
    if x < 0.0 then return null end
    return some(...)                       ; safe by construction
end
```

Arithmetic on `Fin<f64>` returns `?Fin<f64>` whenever the result can
be non-finite (division, sqrt of negative, log of zero, …).
Arithmetic on bare `f64` is allowed but `f64` itself is a sum type
whose `nan` and `inf` cases must be matched before downstream use.

### 4.7 FFI — explicit boundary

```text
extern fn libc_read(fd: i32, buf: inout []u8) -> Result<usize, Errno>
```

Foreign declarations *must* return a `Result`. The user matches; the
compiler enforces. The shim implementation (a thin Zig wrapper) is
the one place the toolchain trusts an external promise — and that
trust is checked by static analysis of the wrapper's signature, not
by language guarantees beyond it.

If foreign code corrupts memory, the OS may kill the process. That is
not the A7-generated code trapping; it's the kernel responding to a
foreign violation. The language's claim is: **no instruction A7 itself
emits can cause an unhandled trap**.

### 4.8 Codegen discipline — what the emitted Zig must look like

The compile-time obligations of §4.1–§4.7 are nothing unless the
**generated Zig source** preserves them structurally. This section
specifies the safe lowering pattern for every operation that *could*
have been unsafe. Every pattern below must be safe under
`-O ReleaseFast` (all Zig safety checks disabled).

The discipline is enforced in `a7/backends/zig.py`. A code review
checklist for backend changes is at the end of this section.

#### 4.8.1 Non-null pointer deref

```text
A7:           let x: int = get_checked(p) ; p: ref int
emitted Zig:  const x: i64 = p.*;          // p: *i64, NOT ?*i64
```

The emission types `p` as Zig's non-optional `*T`. There is **no
nullness check at runtime** because the A7 type system guarantees
`p` is non-null at this point. Compiling with `-O ReleaseFast` removes
nothing; there was nothing to remove.

#### 4.8.2 Nullable pointer deref

```text
A7:           let x: ?int = nullable_deref(p)   ; p: ?ptr int
              match p
                  case some(v): use(v)
                  case null:    handle_empty()
              end
emitted Zig:  if (p) |v| { use(v.*); } else { handle_empty(); }
```

The Zig `if (p) |v|` form unwraps `?*T` structurally. Even with all
safety checks disabled, you can't reach the unwrapped value through
the `else` branch. **There is no Zig runtime null-check.**

#### 4.8.3 Slice indexing — bounded loop

```text
A7:           for i in 0..s.length: use(s[i])
emitted Zig:  var i: usize = 0;
              while (i < s.len) : (i += 1) {
                  // s[i] is safe-by-construction here
                  use(s.ptr[i]);
              }
```

**Note:** the emission uses `s.ptr[i]`, not `s[i]`, so Zig does not
insert a bounds-check at all (Zig only checks `s[i]` for `[]T`-typed
slices). Because the A7 compiler has already verified `i < s.len`,
the bounds check is **structurally dead code** and is simply not
emitted.

When the loop bound is something else (e.g., a constant `8`), the
backend emits `for (0..8) |i| { use(s.ptr[i]); }` only after proving
`8 <= s.len`. If it can't, the program does not compile.

#### 4.8.4 Slice indexing — opaque index via `try_get`

```text
A7:           match s.try_get(i)
                  case some(v): use(v)
                  case null:    handle_oob()
              end
emitted Zig:  if (i < s.len) {
                  use(s.ptr[i]);
              } else {
                  handle_oob();
              }
```

The bounds check is explicit and visible — it's an `if`, not a Zig
safety-check trap. The user already wrote it (via `try_get`); the
backend just lowers it.

#### 4.8.5 Integer division

```text
A7:           let q = a / d                    ; d: NonZero<i64>
emitted Zig:  const q: i64 = @divTrunc(a, d.value);
```

`d.value` is `i64` but the only way to obtain a `NonZero<i64>` was
through `NonZero.new(x: i64) -> ?NonZero<i64>` which already
inspected for zero. The emission therefore uses `@divTrunc`, which is
Zig's unchecked division — and that's safe because the input was
checked at the A7 level. **No Zig `divisor != 0` trap.**

For `INT_MIN / -1`, the `SafeDivisor<T>` refinement also excludes
`-1` when the dividend type is signed and the divisor is unconstrained;
the same lowering applies.

#### 4.8.6 Integer overflow — wrap

```text
A7:           let c = a.wrap_add(b)
emitted Zig:  const c: i64 = a +% b;
```

Zig's `+%` is wrapping; it cannot trap. **No overflow check exists in
the emission at all.**

#### 4.8.7 Integer overflow — checked

```text
A7:           match a.checked_add(b)
                  case some(v): use(v)
                  case null:    handle_overflow()
              end
emitted Zig:  const result = @addWithOverflow(a, b);
              if (result[1] == 0) {
                  use(result[0]);
              } else {
                  handle_overflow();
              }
```

Zig's `@addWithOverflow` returns a tuple `(value, overflow_flag)`;
no trap involved. The branch on the flag is explicit user-written
control flow.

#### 4.8.8 Integer overflow — proved-safe `+`

```text
A7:           ; both i and 1 are bounded by the loop; i < s.len <= MAX-1
              for i in 0..s.length-1: use(s[i + 1])
emitted Zig:  while (i < s.len - 1) : (i += 1) {
                  use(s.ptr[i + 1]);     // i + 1 cannot overflow
              }
```

The A7 type checker has proved that `i + 1 ≤ s.len ≤ usize::MAX`. The
emission uses bare `+`. Because the value can't overflow, Zig's
`+` semantics (wrap on `-O ReleaseFast`, trap on `-O ReleaseSafe`)
are both correct — neither code path is reached. **Safety is in the
source-level proof, not in Zig's flag.**

#### 4.8.9 Heap allocation

```text
A7:           let p: ?ptr Buf = new Buf{...}
emitted Zig:  const p: ?*Buf = allocator.create(Buf) catch null;
              if (p) |buf| { buf.* = .{...}; }
```

The `catch null` discharges Zig's allocation error type into the
`?*Buf` that A7's type system already requires. **Allocation failure
is a typed value, not a propagated panic.**

#### 4.8.10 Match exhaustiveness

```text
A7:           match shape
                  case circle{r}:  ...
                  case rect{w,h}:  ...
              end                          ; A7 already proved exhaustive
emitted Zig:  switch (shape) {
                  .circle => |c| { ... },
                  .rect   => |r| { ... },
              }                            ; no else clause needed
```

If A7 proved exhaustiveness, Zig's `switch` over a tagged union also
covers all cases. No `else => unreachable` is emitted because there
is no unreached case. If a code generator bug ever causes a missing
arm, the Zig compiler itself rejects the emission at *Zig*
compile-time (Zig requires exhaustive `switch`). **Two layers of
defense.**

#### 4.8.11 Stack depth

The compile-time max-stack-depth analysis (§4.4) annotates the
emitted Zig with a `comptime` assertion:

```text
emitted Zig:  comptime { @import("std").debug.assert(MAX_STACK <= 1 << 20); }
              // thread spawn passes the same constant as the stack size
```

The OS gives the program exactly the budget it needs. There is no
runtime stack overflow check (none is emitted by A7), and there
cannot be one (the kernel cannot grow the stack past the requested
size). The program **physically cannot** stack-overflow.

#### 4.8.12 No `unreachable` reached at runtime

`unreachable()` in the emitted Zig source corresponds to one of:

- An A7 `match` arm the type checker proved dead (e.g., the `null`
  arm of an `Option<T>` that's been pattern-matched along a
  refined-type path).
- A user-written `unreachable` whose proof obligation the type
  checker discharged.

The emission uses Zig's `unreachable` keyword in these contexts.
Under `-O ReleaseFast`, Zig treats `unreachable` as UB (the
optimizer assumes the branch is taken). **This is sound only because
the A7 compiler has already proved the branch is dead.**

#### 4.8.13 No `@panic`, no `@trap`, no `__builtin_trap`

The backend has a hard rule, enforced by a codegen test:

> **`a7/backends/zig.py` may not emit `@panic`, `@trap`, `unreachable`
> (except as per §4.8.12), or any other Zig form that produces a
> runtime trap. Any contributor change that adds such an emission
> fails the test.**

Suggested test (to add in `test/test_codegen_zig.py`):

```python
def test_emitted_zig_has_no_traps():
    for example in EXAMPLE_FILES:
        zig = compile_to_zig(example)
        for forbidden in ("@panic", "@trap", "__builtin_trap",
                          "@breakpoint", "unreachable"):
            # unreachable allowed only on lines tagged "// proof-dead"
            offenders = [
                line for line in zig.splitlines()
                if forbidden in line and "proof-dead" not in line
            ]
            assert not offenders, f"{example}: {forbidden} emitted at {offenders}"
```

This is the operational definition of the zero-runtime-error
contract.

#### Backend review checklist

For any change to `a7/backends/zig.py`:

- [ ] Does the change introduce a new Zig construct that can trap at
      runtime? If yes, the corresponding A7 source-level rule must
      ensure the construct is unreachable.
- [ ] Does the change emit `s[i]` on a Zig slice (`[]T`)? If yes,
      switch to `s.ptr[i]` and ensure the A7 type system proves the
      bound.
- [ ] Does the change emit `+`, `-`, `*`, `<<` on opaque values? If
      yes, switch to the typed-arithmetic form (`+%` / `+|` /
      `@addWithOverflow`) or add a proof obligation.
- [ ] Does the change emit `p.*` on an optional `?*T`? If yes, the
      A7 type checker must have unwrapped `p` already; if not, that's
      a bug.
- [ ] Does the change emit `unreachable`? If yes, add a
      `// proof-dead: <reason>` comment so the no-trap test passes
      and so future readers know the obligation.
- [ ] Does the change emit `@panic` or `@trap`? If yes, **revert**.

### 4.9 Summary — the residual runtime-trap list is empty

After §4.1–§4.7, no A7 toolchain output emits a `panic` / `unreachable`
/ `trap` / `ud2` / `brk` / `udf` / `__builtin_trap` instruction that
the user did not explicitly opt into via `unreachable()` with a
discharged proof obligation. Compile-time checks reject every program
that would otherwise fail at runtime.

The user-visible failure modes a running A7 program can exhibit are
limited to:

- Returning a typed error to the caller (a `Result` / `Option` /
  refined value that the user already matched).
- Returning successfully and producing a wrong answer because of a
  logic bug (out of scope for memory safety).
- Being terminated by an external party (OS OOM-killer, SIGKILL,
  power loss).
- A foreign function corrupting memory outside the language's
  enforcement perimeter (FFI hazard, documented in §4.7).

## 5. Phased plan (zero-runtime-error ordering)

This replaces the earlier ordering. Each phase is gated by an
automated test: the no-trap codegen test from §4.8.13 must pass at
the end of every phase. A phase is not "done" until the test passes
for the full example suite under `-O ReleaseFast`.

### Phase 0 — Audit existing static guarantees + add the no-trap codegen test (1 week)

- Confirm the ✅ rows in §2 are actually enforced, not assumed. Add
  explicit tests in `test/test_semantic_*.py` for each rule.
- Add the no-trap codegen test from §4.8.13 to
  `test/test_codegen_zig.py`. **This is the operational definition of
  the zero-runtime-error contract.** It will fail at the start of
  Phase 0; closing it is the work of Phases 1–4.
- Add a CI job that builds every example with `zig build-exe -O
  ReleaseFast` and runs the test corpus. Any crash is a regression.
- Update `docs/SPEC.md` with the contract list from §1 and the
  emitted-Zig discipline from §4.8.

### Phase 1 — Definite assignment + exhaustive `match` (1–2 weeks)

Both are single-pass static analyses sharing the CFG plumbing already
used for the recursion check. Add to
`a7/passes/semantic_validator.py`. Failing them is a `SemanticError`,
not a warning.

### Phase 2 — Non-null pointer types (2–3 weeks)

§3.2 above. Single biggest user-visible safety win for the smallest
language-design delta.

### Phase 3 — Affine ownership + `inout` / `borrow` parameter modes (4–8 weeks)

§3.3 + §3.4. The hardest of the four core mechanisms but still much
simpler than a borrow checker. Two passes:

- **Move analysis:** mark a binding as "consumed" when it is passed by
  value to anything other than `borrow`/`inout`, returned, or assigned
  into a field. Re-using a consumed binding is an error.
- **Call-site exclusivity:** at each call, verify that no two
  `inout`/`borrow` arguments name the same allocation. (For literal
  values this is structural; for opaque values you can require the
  arguments to be syntactically distinct.)

### Phase 4 — Bound-proved slice indexing (3–4 weeks)

§3.5. Implement the four-pattern catalog first; add `try_get` as the
escape hatch. Defer general refinement-type machinery indefinitely.

### Phase 5 — Hardware safety flags through the backend (1 day)

Pass `-mbranch-protection=pac-ret+bti` (AArch64) or
`-fcf-protection=full` (x86_64 with CET) through `scripts/build_examples.py`'s Zig invocation. Free production hardening. See
[03 §6](./03-hardware.md#6-putting-hardware-into-a-software-language-design).

These flags harden against **non-A7 code** in the same process
(linked C libraries, the kernel, JIT'd payloads). A7-emitted code is
already safe; the hardware hardening protects the rest of the
address space. Independent of, and complementary to, the
zero-runtime-error contract above.

### Phase 6 — Region scopes for escape cases (optional, ~1 month)

§3.6. Only ship if Phase 3 leaves real ergonomic gaps in idiomatic A7
code. The Cyclone literature is the reference design.

### Phase 7 — Concurrency story (deferred)

When threads are added, pick a single model up front:

- **Channels + value-only sharing** (Go/Erlang). Simplest.
- **Mutable value semantics extended with actor isolation** (Hylo/Pony
  lite). Composes cleanly with §3.3–§3.4.

Don't pick now. Note in `docs/STATUS.md`.

## 6. Anti-recommendations

Same list as before, sharpened for the compile-time framing:

| Don't | Why |
| --- | --- |
| Build a borrow checker | Lifetime annotations are the largest cost in Rust's language spec. §3.4's `inout` mode catches the same bugs without them. |
| Build a tracing GC | Compile-time analysis (§3.3 + §3.6) eliminates UAF; GC is unnecessary. |
| Build a Fil-C-style runtime | A software capability model only helps if the source language admits pointer forgery. A7 doesn't. |
| Add `unsafe { ... }` blocks | Once present, libraries depend on them and the compile-time guarantee evaporates. |
| Insert silent runtime traps instead of compile errors | If the prover can't discharge a check, reject the code. Don't degrade silently to a runtime trap — that's the bug the whole design avoids. |
| Adopt refinement-types-full / dependent types as the primary mechanism | The cost-to-coverage is poor. Take the 95 % via the four §3.5 patterns; route the rest through `try_get`. |
| Try to be CHERI / MTE compatible at the source level | These are backend / ABI concerns, not source-language features. |
| Conflate "memory safety" with "correctness" | A7 is not aiming to prove functional correctness. Stay in scope: out-of-bounds, UAF, type confusion, races. |

## 7. The contract paragraph (for `README.md` / `docs/SPEC.md`)

> A7 is a **total memory-safe** language. The compiler statically
> rejects every program that would exhibit uninitialized reads, null
> dereferences, type confusion, use-after-free, double-free, leaks
> in scope-bounded code, slice out-of-bounds, integer overflow,
> integer division by zero, NaN/inf propagation, pointer arithmetic
> out-of-bounds, stack overflow, or unhandled allocation failure.
> The hazards that cannot be discharged statically (opaque indices,
> opaque divisors, possible overflow on opaque operands, allocation
> success) are exposed as typed values (`?T` / `Result<T, E>` /
> refinement types) that the user is forced to handle. **The Zig
> code emitted by the A7 compiler is memory-safe on its own; it
> remains memory-safe when compiled with `zig build -O ReleaseFast`,
> i.e., with every Zig runtime safety check disabled. Memory safety
> is a property of the emitted source, not of the backend's flags.**
> The language has no `unsafe` escape hatch.

## 8. Cross-references

If you are implementing one of these, the prior art to consult is
catalogued in [06](./06-compile-time-safety.md):

| Mechanism | Read |
| --- | --- |
| Definite-assignment / flow analysis | [06 §1](./06-compile-time-safety.md#1-definite-assignment--flow-analysis) |
| Non-null pointer types | [06 §2](./06-compile-time-safety.md#2-non-null-pointer-types) |
| Exhaustive pattern matching | [06 §3](./06-compile-time-safety.md#3-sum-types--exhaustive-pattern-matching) |
| Affine ownership | [06 §4](./06-compile-time-safety.md#4-linear--affine-types) |
| `inout`/`borrow` modes (no lifetimes) | [06 §8](./06-compile-time-safety.md#8-mutable-value-semantics-hylo--val) |
| Region inference (fallback for escape) | [06 §6](./06-compile-time-safety.md#6-region-inference-tofte-talpin--cyclone) |
| Pattern-based bound checking | [06 §10](./06-compile-time-safety.md#10-refinement-types) (the lite version) |
| Hardware flag plumbing | [03 §6](./03-hardware.md#6-putting-hardware-into-a-software-language-design) |
| When you absolutely need runtime fallback | [02 §6 UBSan-trap mode](./02-sanitizers.md#6-undefinedbehaviorsanitizer-ubsan) |

## 9. Suggested order of work, one-line each

1. **Phase 0** — audit & document the existing static rules. (1–2 days)
2. **Phase 1** — definite assignment + exhaustive `match`. (1–2 weeks)
3. **Phase 2** — non-null pointer types `?ptr T` vs `ptr T`. (2–3 weeks)
4. **Phase 5** — hardware safety flags (PAC, BTI, CET) via Zig. (1 day)
5. **Phase 3** — affine ownership + `inout` / `borrow` parameter modes. (4–8 weeks)
6. **Phase 4** — bound-proved slice indexing via the four-pattern catalog. (3–4 weeks)
7. **Phase 6** — region scopes for escape cases, if §3.3–§3.4 leave gaps. (optional, ~1 month)
8. **Phase 7** — concurrency. (deferred; not before the rest is solid)

Each phase is independently shippable. Phase 5 is dropped in
opportunistically wherever a release goes out — it's a flag, not a
project.
