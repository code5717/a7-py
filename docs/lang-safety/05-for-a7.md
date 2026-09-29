# 05 — Take-aways for A7: Zero Runtime Errors

> Status: research proposal written before 2026-09-14, audited 2026-09-16. It is
> not the current plan. Current decisions are in
> [`docs/plan/decisions.md`](../plan/decisions.md).

> Part of the `docs/lang-safety/` series. See the [README](./README.md) for the
> full map. Siblings: [01 — InvisiCaps](./01-invisicaps.md) ·
> [02 — Sanitizers](./02-sanitizers.md) ·
> [03 — Hardware-assisted safety](./03-hardware.md) ·
> [04 — Comparison](./04-comparison.md) ·
> [06 — Compile-time techniques](./06-compile-time-safety.md).

## Audit summary (2026-09-16)

The text below is kept as written, with dated notes where later decisions or the
current compiler differ. The main differences:

| Topic in this file | Current position | Source |
| --- | --- | --- |
| `int`, `number` types in examples | Removed; explicit widths only (`i8`–`i64`, `u8`–`u64`, `isize`, `usize`) | Ledger L3, L4 |
| Bare `+` on unproved operands is a compile error | Ordinary `+ - *` wrap. Division, remainder, shifts and casts are still open (gate G3) | Ledger L5 and its scope limit |
| NaN and infinity rejected through `Fin<f64>` | IEEE 754 floats as in Zig and C; NaN and infinity are ordinary values | Ledger L16 |
| `new`, `del`, affine ownership, `inout`/`borrow`, region syntax | Proposed direction: automatic memory resolved at compile time, no memory vocabulary in source, no `del` | Ledger L15, L17–L22; [memory plan](../plan/memory.md) (not yet approved) |
| No runtime check of any kind | The memory plan allows a listed set of residual checks with defined outcomes. Amending the contract is gate M16, pending | [memory plan §6](../plan/memory.md) |
| Parameter-mode keywords (D.040, D.041, D.049) | Not accepted; `ref` stays the working form | Ledger L6 scope limit, "Superseded material" |

Compiler facts used in the notes below were checked on 2026-09-16 against
`a7/`, `docs/SAFETY_CONTRACT.md`, and by running
`python main.py --mode pipeline` on small probe programs.

## The directive

> **A7 must catch every safety hazard at compile time. The A7 compiler must emit
> Zig source that is memory-safe on its own — not because Zig was invoked with
> any particular flag, not because `-O ReleaseSafe` inserts runtime checks. The
> emitted Zig must be safe even when compiled with `-O ReleaseFast` (all Zig
> safety checks disabled).** The A7 compiler is the proof carrier; Zig is just
> the backend.

Anything that could fail becomes one of two things:

1. A **compile error**. The prover discharges the obligation, or the user fixes
   the code.
2. A **typed value** in the result (`?T`, `Result<T, E>`, ranged integers,
   capability tokens) that the user must consume.

The emitted Zig never contains:

- A bare `s[i]` with an unbounded index.
- A bare `p.*` on an optional `?*T` that is not already unwrapped.
- A bare `a + b` on opaque integers. It is always `+%`, `+|`,
  `@addWithOverflow`, or a proved-safe `+`.
- A bare `a / b` where `b` is not proved non-zero at the call site.
- A recursive call. A7 already forbids recursion.
- `unreachable` reached at runtime. It appears only in type-proven dead branches.
- `@panic` for any condition the user did not explicitly request.

> Note (2026-09-16): the `a + b` item is superseded by ledger L5; ordinary
> `+ - *` wrap. The backend today also emits `@panic` when the `std/io` writer
> fails to write or flush (`a7/backends/zig.py:170-171`).

[06](./06-compile-time-safety.md) catalogs the compile-time techniques. This file
applies them to A7 under the zero-runtime-error contract.

The trade: A7 becomes a **total** language in the spirit of SPARK/Ada or F\*. It
is not a pragmatic language like Rust, which still panics on bounds, on overflow
in debug builds, on integer divide-by-zero, and on `unwrap`. The expressiveness
ceiling is lower and the guarantee is stronger.

### The Zig backend is the proof witness, not the proof author

- The **A7 frontend and middle-end** discharge every safety obligation.
- The **A7 codegen** lowers each obligation to a Zig construct that cannot
  violate it by its shape. The safety property is in the structure of the
  emitted Zig, not in a runtime check.
- The **Zig compiler** is an untrusted backend. Building the emitted Zig with
  `-O ReleaseFast` gives the same safety properties as `-O ReleaseSafe`.

The test: a fuzz farm builds ReleaseFast binaries and sees no crashes, except
where the user matched `null` with `unreachable()`.

The contract is a property of the emitted code. A future Zig version that weakens
or strengthens its own safety checks does not change it.

## 1. The zero-runtime-error contract

Every failure mode below is either rejected at compile time or surfaced as a
`Result`, `Option` or refined-integer value the user must handle. **Nothing in
the compiled output traps, panics, aborts, or invokes UB on its own.**

| Hazard | Compile-time mechanism or typed return |
| --- | --- |
| Uninitialized read | §1 Definite-assignment flow analysis ⇒ compile error |
| Null dereference | §2 Non-null `ptr T` vs nullable `?ptr T` ⇒ compile error or forced match |
| Missed enum variant | §3 Exhaustive pattern matching ⇒ compile error |
| Type confusion | No raw casts at the source level ⇒ unreachable by construction |
| Use-after-free | §4 Affine ownership + §6 region inference ⇒ compile error |
| Double-free | §4 Affine ownership ⇒ compile error (a moved value cannot be `del`d) |
| Leak (in scope) | §4 + scope-exit `Drop` ⇒ compile error if a value is unconsumed |
| Slice out-of-bounds | §10 Pattern-proved indexing or `try_get(i) -> ?T` ⇒ compile error or forced match |
| Integer overflow | Typed arithmetic: `checked_add` (`-> ?T`), `wrap_add`, `sat_add`, or ranged types that prove no overflow ⇒ compile error for bare `+` on opaque values |
| Integer division by zero | Divisor must be `NonZero<T>`, built by `NonZero::new(x) -> ?NonZero<T>` ⇒ compile error if a bare `int` is passed |
| `INT_MIN / -1` | Same `NonZero<T>` plus `NonNegOne<T>`, or `wrap_div` ⇒ compile error |
| Floating-point NaN / inf | Operations return `?f64` (none on a non-finite result) or `Fin<f64>` ⇒ compile error if propagated as plain `f64` |
| Pointer arithmetic out of bounds | No pointer arithmetic in source ⇒ unreachable |
| Stack overflow | Max-stack-depth analysis over the call DAG (no recursion) ⇒ compile error if the static budget is exceeded |
| Heap allocation failure | `new T{...}` returns `?ptr T`; the user must match ⇒ no silent trap |
| Data race | N/A today (no threads). When added: §8 mutable value semantics or §9 capabilities ⇒ compile error |
| Foreign code (FFI) | Outside the language. The FFI shim is the only place a typed boundary is drawn explicitly; the language proves nothing beyond it |

Section numbers in the table refer to [06](./06-compile-time-safety.md). The
right column was meant as the complete contract, with no hidden list of runtime
traps.

> Note (2026-09-16): rows superseded or redirected by later decisions:
> - Integer overflow: ledger L5; ordinary `+ - *` wrap.
> - NaN / inf: ledger L16; IEEE floats.
> - `int` in the division row: ledger L4; explicit widths.
> - Use-after-free, double-free, leak, allocation failure: the memory plan
>   removes `new` and `del` from ordinary code (gates M2, M3), not yet approved.
> - "No runtime trap": the memory plan lists residual checks with defined
>   outcomes (gate M16, pending).
> - A7 spells references `ref T`, not `ptr T`.

### 1.1 The narrow exception: FFI

The language cannot police calls into foreign code such as C libraries or OS
syscalls. A7 must mark FFI shims explicitly, with an `extern` declaration or
similar. Everything beyond the shim is the user's responsibility.

The shim's return type must still be typed. A foreign function that might fail
returns `Result<T, ForeignError>`, and the compiler enforces the match.

If foreign code corrupts memory, the OS may segfault. That is hardware catching a
foreign violation, not the language emitting a trap.

> Note (2026-09-16): the memory plan puts native boundaries under descriptors
> (gate M12), not yet approved.

## 2. What A7 already proves statically

Original audit against `a7/types.py`, `a7/passes/` and `docs/SPEC.md`. The last
column records the 2026-09-16 re-check.

| Property | Original status | Checked 2026-09-16 |
| --- | --- | --- |
| No raw pointer arithmetic in source | Yes | Not re-checked |
| No `inttoptr` syntax | Yes | Not re-checked |
| No `unsafe` block | Yes | Not re-checked |
| No untagged unions | Yes | Stale: SPEC §3.3 documents untagged `union` literals and field access; tagged-union tag inspection is reserved and not implemented (`docs/SPEC.md:329-350`) |
| Recursion banned (semantic validator) | Yes | Yes: `_validate_no_recursion`, `a7/passes/semantic_validator.py:501-544` |
| `usize` enforced for indices and sizes | Yes | Yes for indices: the index proof requires `usize` or a non-negative literal (`docs/SAFETY_CONTRACT.md:49`); sizes not re-checked |
| Slices and arrays carry length in the type | Yes | Not re-checked |
| Exhaustive `match` checking | Verify and document; if absent, add (06 §3, cheap) | Partial: enforced for `bool` and enum scrutinees (`a7/passes/type_checker.py:2685-2705`) |
| Definite assignment of locals | Verify and document; if absent, add (06 §1, cheap) | Absent: a read after a zero-iteration loop is accepted (probe; memory plan gate M34) |
| Non-null pointer types | No: `ptr T` is nullable | Type split not landed. `ref T` stays nullable, but field access needs a non-nil proof (`a7/safety.py:610-630`) |
| Compile-time UAF prevention | No: `del` is unrestricted | Partial: direct use after `del` is rejected (`a7/safety.py:724-730`; `docs/SAFETY_CONTRACT.md:53`) |
| Compile-time bounds proof | No: relies on Zig's runtime check | Partial: every index needs a proof of `0 <= index < len` (`a7/safety.py:567`), but guards such as `if i < xs.len` are not yet recognized |

The four items marked "verify" or "no" were the ones that move A7 from "C with a
better type system" to "compile-time memory-safe."

## 3. The compile-time toolbox A7 should adopt

A short version of the 06 catalog: a few small mechanisms.

### 3.1 Definite-assignment flow analysis  ── [06 §1](./06-compile-time-safety.md#1-definite-assignment--flow-analysis)

Reading an unassigned local is a **compile error**, not a runtime trap. It is a
single data-flow pass over the CFG, about 200 lines in `a7/passes/`. Java, C#,
Kotlin, Rust, Swift and Zig already ship it.

A7-specific note: the original text said `a7/passes/semantic_validator.py`
already has CFG plumbing for the recursion check, and that the same machinery
handles definite assignment.

> Note (2026-09-16): the recursion check walks a function call graph with an
> explicit stack (`semantic_validator.py:501-544`). It is not a per-function CFG.
> The memory plan lists a typed IR with a CFG as a prerequisite (layer 0).

Current A7 (accepted today; this is the gap):

```a7
// Current A7: accepted today, although no path assigns x
io :: import "std/io"

main :: fn() {
    x: i32
    n: usize = 0
    for i := 0; i < n; i += 1 {
        x = 1
    }
    io.println("{}", x)
}
```

### 3.2 Non-null pointer types  ── [06 §2](./06-compile-time-safety.md#2-non-null-pointer-types)

```text
Proposed (older pseudocode)
ptr  T   ; non-null, deref always safe
?ptr T   ; nullable, must be matched or unwrapped to deref
```

Implementation:

- Parser: recognize `?ptr T` (one token in `a7/tokens.py`).
- Types: add `nullable: bool` to `PointerType` in `a7/types.py`.
- Type checker: dereferencing `?ptr T` is an error; a comparison or
  `if x is null` narrows.
- Backend: emit `*T` or `?*T`; the rest follows.

This is the highest-leverage, lowest-cost change. It removes the null-deref bug
class.

> Note (2026-09-16): A7 spells references `ref T`. `docs/SAFETY_CONTRACT.md:69-78`
> plans the split as `ref T` (non-null) and optional `ref T`. Until then, the
> safety pass requires a non-nil proof before field access. The memory plan
> replaces `nil` references with optionals and removes stored `ref` (gate M4),
> not yet approved.

Current A7 (verified 2026-09-16): field access through a `new` result is rejected
until a nil check narrows it.

```a7
// Current A7: accepted
io :: import "std/io"

Counter :: struct {
    value: i32
}

main :: fn() {
    c := new Counter
    if c != nil {
        c.value = 1
        io.println("{}", c.value)
    }
    del c
}
```

Removing the `if c != nil` guard gives "reference must be proven non-nil before
field access through it."

### 3.3 Affine ownership for heap allocations  ── [06 §4](./06-compile-time-safety.md#4-linear--affine-types)

A `new` expression produces a value that can be **moved** but not **aliased**.
After a move, the source binding cannot be used.

```text
Proposed (older pseudocode)
fn handoff()
    p := new Buf{...}        ; p owns the allocation
    consume(p)               ; ownership moved into consume()
    print p.size             ; compile error: use of moved value
end
```

A7's existing rules already rule out most of what makes this hard:

- No recursion, so no cyclic ownership graphs.
- No raw pointer arithmetic, so no aliases created behind the type checker.
- No `unsafe`, so no escape hatch.

The implementation is a "moved" flag per binding, tracked in the same CFG pass as
definite assignment. It is not a full borrow checker. Sharing is allowed only
through a "borrow for the call's duration" parameter mode (§3.4).

> Note (2026-09-16): today the safety pass rejects direct use after `del`
> (verified: "moved/deleted values cannot be read"). The memory plan makes
> ownership internal to the compiler and removes `del` from ordinary code (gate
> M3), not yet approved.

### 3.4 `inout` / `borrow` parameter passing  ── [06 §8](./06-compile-time-safety.md#8-mutable-value-semantics-hylo--val)

Two callers need to see the same allocation without copying it and without
aliasing that leads to UAF. A7 needs a way to pass a value by reference without
storing the reference. Hylo, Swift and Mojo make this **only a parameter-passing
mode**, never a storable value:

```text
Proposed (older pseudocode)
fn fill(buf: inout Buf, value: u8)
    buf.bytes[0] = value          ; mutates the caller's buf
end

fn read(buf: borrow Buf) -> u8
    return buf.bytes[0]           ; read-only access
end
```

Exclusivity is checked at each call site: an `inout` argument cannot alias any
other argument of the same call. References are never stored, so the analysis is
intra-procedural and needs **no lifetime annotations**.

Owned values (§3.3) plus these modes give compile-time UAF and aliasing safety
without a Rust-style borrow checker. Details are in
[06 §8](./06-compile-time-safety.md#8-mutable-value-semantics-hylo--val).

> Note (2026-09-16): parameter-mode keywords (D.040, D.041, D.049) were not
> accepted; ledger L6 approves immutable arguments only, and `ref` remains the
> working form. The memory plan keeps `ref` parameters, forbids storing or
> returning them, and rejects aliased arguments such as `both(x, x)` as an
> exclusivity conflict. That call compiles today (memory plan §3).

### 3.5 Bound-proved slice indexing  ── [06 §10](./06-compile-time-safety.md#10-refinement-types)

Every slice access `s[i]` compiles against a static proof that
`0 ≤ i < s.length`. The simplest implementation is **pattern recognition**, not
full SMT:

| Pattern | Static proof | Notes |
| --- | --- | --- |
| `for i in 0..s.length: s[i]` | Trivial | The loop bound is the slice length |
| `s[0]` after `if s.length > 0` | Flow-sensitive | Same pass as definite assignment |
| `s[i]` with `i: Index(s.length)` (named refinement) | The constructor proves the bound | One refinement type, not a whole solver |
| `s[i]` with opaque `i: usize` | Compile error: bound not proved | Use a checked iterator or `try_get` |

This is refinement-types-lite. The original estimate was that a handful of
patterns covers about 95 % of real code (unsourced). Other code is rewritten into
a recognized form or uses `s.try_get(i) -> ?T`, which returns an optional (back
to §3.2).

There is **no `unsafe { s[i] }` escape hatch**. If the prover cannot discharge
the bound, the user fixes the code.

> Note (2026-09-16): the current safety pass requires an index proof but does not
> yet recognize the first two patterns. Verified with `--mode pipeline`:
> `for i, v in buf { ... buf[i] ... }` and `if i < xs.len { ret xs[i] }` are both
> rejected with "index bounds are not proven."

Current A7 (verified 2026-09-16):

```a7
// Current A7: rejected, "index bounds are not proven"
get_or_zero :: fn(xs: []i32, i: usize) i32 {
    if i < xs.len {
        ret xs[i]
    }
    ret 0
}
```

```a7
// Current A7: accepted; element iteration needs no index proof
sum :: fn(xs: []i32) i32 {
    total: i32 = 0
    for v in xs {
        total += v
    }
    ret total
}
```

### 3.6 (Optional) Region scopes for the cases moves don't fit

Some allocation patterns do not fit affine ownership. One example is a function
that builds several values and returns all of them by reference. The standard
answer is the
[Cyclone-style region form](./06-compile-time-safety.md#6-region-inference-tofte-talpin--cyclone):

```text
Proposed (older pseudocode)
fn parse(input: []u8) -> []Token
    region tokens
        ; all allocations in this scope live in tokens
        first := new Token{...}
        ; ...
    end                      ; the region frees here unless returned
end
```

A7's call graph is already a DAG (no recursion), so the region lattice is
bounded. This is a Phase 6 item; ship §3.1–§3.5 first.

> Note (2026-09-16): ledger L17 and L19 and memory plan contract item 9 keep
> regions, arenas and pools inside the compiler. Users do not write `region`.
> Extents are inferred (memory plan layer 4), not yet approved.

## 4. Closing every remaining hazard — the typed-result discipline

Under the contract, the remaining hazards become **typed values** the user must
handle. None is a runtime trap.

### 4.1 Integer division — `NonZero<T>`

```text
Proposed (older pseudocode; uses the removed `int` type)
type NonZero<T: Int> = {x: T | x != 0}    ; refinement (compile-time)

fn NonZero.new(x: int) -> ?NonZero<int>
    if x == 0 then return null end
    return some(NonZero.unchecked(x))     ; only constructor; private
end

fn divide(a: int, d: NonZero<int>) -> int
    return a / d                           ; safe by construction
end
```

The bare `/` operator is **only defined when the right operand has type
`NonZero<T>`**. Dividing by an opaque integer is a compile error. When the value
is known statically, such as the literal `5`, the compiler refines the type.

The same rule applies to `%`. `INT_MIN / -1` traps on x86_64, so it also needs
`NonNegOne<T>`. In practice both collapse into one `SafeDivisor<T>` refinement.

> Note (2026-09-16): the current compiler has no `NonZero` type. It proves the
> divisor non-zero from internal facts such as guards (`a7/safety.py:559`,
> `docs/SAFETY_CONTRACT.md:48`). Division, remainder and `MIN / -1` policy is
> open under gate G3 (ledger L5 scope limit).

Current A7 (verified 2026-09-16):

```a7
// Current A7: rejected, "divisor must be non-zero: divisor may be zero"
divide :: fn(a: i32, d: i32) i32 {
    ret a / d
}
```

```a7
// Current A7: accepted; the guard proves d != 0
div_or_zero :: fn(a: i32, d: i32) i32 {
    if d != 0 {
        ret a / d
    }
    ret 0
}
```

### 4.2 Slice indexing — pattern-proved or `try_get`

The §3.5 patterns cover most cases. The opaque-index case becomes:

```text
Proposed (older pseudocode; uses the removed `int` type)
fn lookup(s: []int, i: int) -> ?int
    return s.try_get(i)                    ; returns null if out of bounds
end
```

`try_get(i) -> ?T` is the **only** indexing operation on a slice when the index
is opaque. `s[i]` requires a discharged bound; otherwise it is a compile error.
There is no runtime trap path.

> Note (2026-09-16): A7 index variables must be `usize` (project rule), so a
> current form would take `i: usize`.

### 4.3 Integer overflow — explicit arithmetic mode

```text
Proposed (older pseudocode)
let a: u32 = read_input()
let b: u32 = read_input()

let c1 = a + b                  ; compile error: overflow not proved
let c2 = a.checked_add(b)       ; -> ?u32, must match
let c3 = a.wrap_add(b)          ; defined wrap; never traps
let c4 = a.sat_add(b)           ; saturates at MAX; never traps
```

Bare `+` is allowed only when the type checker can prove the operand ranges do
not overflow, for example literals, ranged types, and induction variables of a
bounded loop. Otherwise the user picks `checked_*`, `wrap_*` or `sat_*`.

The same rule covers `-`, `*`, `<<`, narrowing conversions and float-to-int casts.
Float-to-int uses `?int_from(f)`, which returns null for NaN, infinity or an
out-of-range value.

> Note (2026-09-16): superseded by ledger L5 for `+ - *` and their compound
> assignments; they wrap. `docs/SAFETY_CONTRACT.md:54` (range proofs for these
> operators) is listed as superseded. The overflow proof in the current safety
> pass returns early (`a7/safety.py:631-636`). Shifts, narrowing casts and
> float-to-int remain open under gate G3.

### 4.4 Stack overflow — static budget proof

A7 bans recursion, so the call graph is a DAG and the maximum stack depth is
computable at compile time.

```text
Proposed diagnostic (not implemented)
$ uv run a7 examples/big.a7
error[E0501]: program exceeds configured stack budget
  function chain `main -> work -> deep_helper` uses 1.2 MiB,
  budget is 1.0 MiB (configure with --stack-budget BYTES)
```

The compiler records the maximum stack size in the binary. At start-up the
runtime sets `RLIMIT_STACK`, or the equivalent thread attribute, to that value.
The program cannot overflow its stack because it receives what it statically
needs.

The budget covers every function's frame size (from local types), the deepest
path through the call DAG, and a small constant for FFI shims. A function whose
frame depends on a dynamic size (`buf: [N]T` with non-constant `N`) is rejected
unless `N` has a refined upper bound.

> Note (2026-09-16): the memory plan bounds call depth only if stored function
> values stay non-recursive (gate G4) and moves large values off the native stack
> by a per-target threshold (gate M35). Both are not yet approved.

### 4.5 Heap allocation — typed `Result`

```text
Proposed (older pseudocode)
let p: ?ptr Buf = new Buf{...}             ; -> null on allocator failure

match p
    case some(buf): use(buf)
    case null:      handle_oom()
end
```

`new` always returns a nullable; there is no infallible `new`. The user must
match.

A `must_new` macro could expand to `new` plus `match ... null: unreachable()`.
`unreachable()` is a compile-time term with a proof obligation. Typically the
user shows that the allocation size is statically bounded and already counted in
the program's budget.

> Note (2026-09-16): today `new T` lowers to `allocator.create(T) catch null`
> (`a7/backends/zig.py:1913`) and yields a nullable `ref T`. The memory plan
> removes `new` and routes out-of-memory through gate M2: recoverable extents
> report an error, and other allocations stop the program. Not yet approved.

### 4.6 NaN and infinity — typed floats

```text
Proposed (older pseudocode)
type Fin<f> = {x: f | !is_nan(x) && !is_inf(x)}

fn sqrt(x: Fin<f64>) -> ?Fin<f64>
    if x < 0.0 then return null end
    return some(...)                       ; safe by construction
end
```

Arithmetic on `Fin<f64>` returns `?Fin<f64>` wherever the result can be
non-finite: division, square root of a negative, log of zero, and so on.
Arithmetic on bare `f64` is allowed, but `f64` is a sum type whose `nan` and `inf`
cases must be matched before later use.

> Note (2026-09-16): superseded by ledger L16. Floats follow IEEE 754 as in Zig
> and C; NaN and infinity are ordinary values. Sub-decisions remain in gate G1.

### 4.7 FFI — explicit boundary

```text
Proposed (older pseudocode)
extern fn libc_read(fd: i32, buf: inout []u8) -> Result<usize, Errno>
```

Foreign declarations must return a `Result`. The user matches and the compiler
enforces it. The shim, a thin Zig wrapper, is the one place the toolchain trusts
an external promise. That trust is checked against the wrapper's signature only.

If foreign code corrupts memory, the OS may kill the process. That is the kernel
responding to a foreign violation. The language's claim is: **no instruction A7
itself emits can cause an unhandled trap**.

### 4.8 Codegen discipline — what the emitted Zig must look like

The obligations in §4.1–§4.7 only hold if the **generated Zig** preserves them
structurally. This section gives the safe lowering for every operation that could
be unsafe. Every pattern must be safe under `-O ReleaseFast`.

In every block below, the `A7:` lines are Proposed syntax, not current A7. The
`emitted Zig:` lines show the proposed lowering.

The discipline belongs in `a7/backends/zig.py`. A review checklist for backend
changes follows the patterns.

> Note (2026-09-16): the current backend follows a different, fact-based design.
> `docs/SAFETY_CONTRACT.md` requires `BackendPlan.require(node, operation)`
> before each risky lowering (`a7/backends/zig.py:1793`). It does not follow the
> patterns below where noted.

#### 4.8.1 Non-null pointer deref

```text
A7:           let x: int = get_checked(p) ; p: ref int
emitted Zig:  const x: i64 = p.*;          // p: *i64, NOT ?*i64
```

`p` is emitted as Zig's non-optional `*T`. There is **no runtime nullness
check**, because the A7 type system guarantees `p` is non-null here. ReleaseFast
removes nothing because there is nothing to remove.

#### 4.8.2 Nullable pointer deref

```text
A7:           let x: ?int = nullable_deref(p)   ; p: ?ptr int
              match p
                  case some(v): use(v)
                  case null:    handle_empty()
              end
emitted Zig:  if (p) |v| { use(v.*); } else { handle_empty(); }
```

`if (p) |v|` unwraps `?*T` structurally. Even with safety checks off, the `else`
branch cannot reach the unwrapped value. There is no Zig runtime null check.

#### 4.8.3 Slice indexing — bounded loop

```text
A7:           for i in 0..s.length: use(s[i])
emitted Zig:  var i: usize = 0;
              while (i < s.len) : (i += 1) {
                  // s[i] is safe-by-construction here
                  use(s.ptr[i]);
              }
```

The emission uses `s.ptr[i]`, not `s[i]`, so Zig inserts no bounds check (Zig
checks `s[i]` only on `[]T` slices). The A7 compiler has already verified
`i < s.len`, so the check would be dead code and is not emitted.

When the loop bound is something else, such as the constant `8`, the backend
emits `for (0..8) |i| { use(s.ptr[i]); }` only after proving `8 <= s.len`.
Otherwise the program does not compile.

> Note (2026-09-16): the current backend emits `obj[idx]` (`a7/backends/zig.py:1681-1685`)
> after the index proof. Under ReleaseFast Zig removes its own check, so safety
> rests on the A7 proof. The memory plan removes slice `.ptr` from the public
> surface; this rule concerns emitted Zig only.

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

The bounds check is an explicit `if`, not a Zig safety trap. The user asked for
it through `try_get`; the backend lowers it.

#### 4.8.5 Integer division

```text
A7:           let q = a / d                    ; d: NonZero<i64>
emitted Zig:  const q: i64 = @divTrunc(a, d.value);
```

`d.value` is an `i64`. The only way to get a `NonZero<i64>` is
`NonZero.new(x: i64) -> ?NonZero<i64>`, which already checked for zero. So the
emission uses `@divTrunc`, and there is no Zig `divisor != 0` trap to rely on.

For `INT_MIN / -1`, `SafeDivisor<T>` also excludes `-1` when the dividend is
signed and the divisor is unconstrained. The lowering is the same.

> Note (2026-09-16): the current backend emits `@divTrunc` for integer `/` and
> `@rem` for `%` (`a7/backends/zig.py:1576-1585`) after a non-zero divisor proof.
> `MIN / -1` handling was not verified.

#### 4.8.6 Integer overflow — wrap

```text
A7:           let c = a.wrap_add(b)
emitted Zig:  const c: i64 = a +% b;
```

Zig's `+%` wraps and cannot trap. The emission has no overflow check.

> Note (2026-09-16): under ledger L5 this is the lowering for ordinary `+`.
> The current backend does not emit `+%` (no match in `a7/backends/zig.py`).

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

`@addWithOverflow` returns a tuple `(value, overflow_flag)` and never traps. The
branch on the flag is explicit control flow.

#### 4.8.8 Integer overflow — proved-safe `+`

```text
A7:           ; both i and 1 are bounded by the loop; i < s.len <= MAX-1
              for i in 0..s.length-1: use(s[i + 1])
emitted Zig:  while (i < s.len - 1) : (i += 1) {
                  use(s.ptr[i + 1]);     // i + 1 cannot overflow
              }
```

The type checker has proved `i + 1 ≤ s.len ≤ usize::MAX`, so the emission uses
bare `+`. Zig's `+` wraps under ReleaseFast and traps under ReleaseSafe; both are
correct because neither path is reached. Safety comes from the source-level
proof, not from Zig's flag.

> Note (2026-09-16): with L5 wrapping, ordinary `+` is emitted as `+%`, so this
> pattern matters only where a proof is still needed, such as index arithmetic.

#### 4.8.9 Heap allocation

```text
A7:           let p: ?ptr Buf = new Buf{...}
emitted Zig:  const p: ?*Buf = allocator.create(Buf) catch null;
              if (p) |buf| { buf.* = .{...}; }
```

`catch null` turns Zig's allocation error into the `?*Buf` that A7 already
requires. Allocation failure is a typed value, not a propagated panic.

> Note (2026-09-16): matches the current backend (`a7/backends/zig.py:1912-1913`).
> See the §4.5 note for the planned change.

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

If A7 proved the match exhaustive, Zig's `switch` over the tagged union covers
all cases, and no `else => unreachable` is emitted. If a codegen bug drops an
arm, Zig rejects the emission at Zig compile time, because Zig requires an
exhaustive `switch`. That gives two layers of defense.

> Note (2026-09-16): A7 checks exhaustiveness for `bool` and enum scrutinees
> today. Tagged-union tag matching is reserved syntax (`docs/SPEC.md:349-350`).

#### 4.8.11 Stack depth

The max-stack-depth analysis (§4.4) adds a `comptime` assertion to the emitted
Zig:

```text
emitted Zig:  comptime { @import("std").debug.assert(MAX_STACK <= 1 << 20); }
              // thread spawn passes the same constant as the stack size
```

The OS gives the program exactly the budget it needs. A7 emits no runtime stack
check, and none is possible: the kernel cannot grow the stack past the requested
size. The program **cannot** overflow its stack.

#### 4.8.12 No `unreachable` reached at runtime

`unreachable` in emitted Zig corresponds to one of:

- A `match` arm the type checker proved dead, such as the `null` arm of an
  `Option<T>` already matched along a refined path.
- A user-written `unreachable` whose proof obligation was discharged.

Under ReleaseFast, Zig treats `unreachable` as UB: the optimizer assumes the
branch is never taken. **This is sound only because A7 has already proved the
branch dead.**

#### 4.8.13 No `@panic`, no `@trap`, no `__builtin_trap`

The backend has a hard rule, enforced by a codegen test:

> **`a7/backends/zig.py` may not emit `@panic`, `@trap`, `unreachable` (except as
> in §4.8.12), or any other Zig form that produces a runtime trap. Any change
> that adds such an emission fails the test.**

Suggested test for `test/test_codegen_zig.py`:

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

This test is the operational definition of the zero-runtime-error contract.

> Note (2026-09-16): this test does not exist; no file under `test/` mentions
> `proof-dead`. The backend emits `@panic` when the `std/io` writer fails to write
> or flush (`a7/backends/zig.py:170-171`), so the test would fail today. The
> memory plan also stops the program on non-recoverable out-of-memory (gate M2),
> which needs the M16 contract amendment.

#### Backend review checklist

For any change to `a7/backends/zig.py`:

- [ ] Does it add a Zig construct that can trap at runtime? If yes, an A7
      source-level rule must make that construct unreachable.
- [ ] Does it emit `s[i]` on a Zig slice (`[]T`)? If yes, switch to `s.ptr[i]`
      and make sure A7 proves the bound.
- [ ] Does it emit `+`, `-`, `*` or `<<` on opaque values? If yes, use a typed
      form (`+%`, `+|`, `@addWithOverflow`) or add a proof obligation.
- [ ] Does it emit `p.*` on an optional `?*T`? If yes, A7 must already have
      unwrapped `p`; otherwise it is a bug.
- [ ] Does it emit `unreachable`? If yes, add a `// proof-dead: <reason>` comment
      so the no-trap test passes and readers see the obligation.
- [ ] Does it emit `@panic` or `@trap`? If yes, **revert**.

> Note (2026-09-16): under ledger L5, `+ - *` lower to wrapping forms. The
> current backend requires a `BackendPlan` approval per risky operation
> (`docs/SAFETY_CONTRACT.md`, "Backend Rule").

### 4.9 Summary — the residual runtime-trap list is empty

After §4.1–§4.7, no A7 toolchain output contains a `panic`, `unreachable`, `trap`,
`ud2`, `brk`, `udf` or `__builtin_trap` instruction, unless the user opted in
through `unreachable()` with a discharged proof. Compile-time checks reject every
program that would otherwise fail at runtime.

A running A7 program can fail visibly only by:

- Returning a typed error to the caller: a `Result`, `Option` or refined value
  the user already matched.
- Returning a wrong answer because of a logic bug (outside memory safety).
- Being terminated externally: OS OOM killer, SIGKILL, power loss.
- Foreign code corrupting memory outside the language's perimeter (§4.7).

> Note (2026-09-16): the memory plan adds residual runtime work with defined
> outcomes (memory plan §6): allocator calls, id lookups returning optionals,
> checked size arithmetic treated as allocation failure, and tensor shape
> preflight. Non-recoverable out-of-memory stops the program. This list changes
> only if gate M16 is approved.

## 5. Phased plan (zero-runtime-error ordering)

This replaced an earlier ordering. Each phase is gated by the no-trap codegen
test from §4.8.13. A phase is done only when that test passes for the full
example suite under `-O ReleaseFast`.

> Note (2026-09-16): the current plan is the [v1 plan](../plan/README.md) and
> the [memory plan](../plan/memory.md) phases A–G. The phases below are kept as
> research history.

### Phase 0 — Audit existing static guarantees + add the no-trap codegen test (1 week)

- Confirm the "yes" rows in §2 are enforced, not assumed. Add explicit tests in
  `test/test_semantic_*.py` for each rule.
- Add the no-trap codegen test from §4.8.13 to `test/test_codegen_zig.py`. It
  fails at the start of Phase 0; Phases 1–4 close it.
- Add a CI job that builds every example with `zig build-exe -O ReleaseFast` and
  runs the test corpus. Any crash is a regression.
- Add the §1 contract list and the §4.8 emitted-Zig discipline to `docs/SPEC.md`.

> Note (2026-09-16): release artifacts already build with `-OReleaseFast`
> (`scripts/build_examples.py:25`), and `test/test_pipeline_native.py:71,92` runs
> Debug and ReleaseFast. The no-trap test is not present.

### Phase 1 — Definite assignment + exhaustive `match` (1–2 weeks)

Both are single-pass static analyses. The original plan was to share CFG
plumbing with the recursion check (see the §3.1 note) and add them to
`a7/passes/semantic_validator.py`. Failing either is a `SemanticError`, not a
warning.

> Note (2026-09-16): exhaustiveness exists for `bool` and enum
> (`a7/passes/type_checker.py:2685`). Definite assignment is memory plan gate M34.

### Phase 2 — Non-null pointer types (2–3 weeks)

§3.2. The largest user-visible safety gain for the smallest language change.

### Phase 3 — Affine ownership + `inout` / `borrow` parameter modes (4–8 weeks)

§3.3 and §3.4. The hardest core mechanism, but much simpler than a borrow
checker. Two passes:

- **Move analysis:** a binding is "consumed" when passed by value to anything
  other than `borrow` or `inout`, returned, or assigned into a field. Using a
  consumed binding again is an error.
- **Call-site exclusivity:** at each call, no two `inout`/`borrow` arguments may
  name the same allocation. For literal values this is structural; for opaque
  values the arguments can be required to be syntactically distinct.

> Note (2026-09-16): parameter modes were not accepted (see §3.4 note). The
> memory plan keeps ownership internal (layer 2) with exclusivity checks.

### Phase 4 — Bound-proved slice indexing (3–4 weeks)

§3.5. Implement the four-pattern catalog first, with `try_get` as the escape
hatch. Defer general refinement types indefinitely.

### Phase 5 — Hardware safety flags through the backend (1 day)

Pass `-mbranch-protection=pac-ret+bti` (AArch64) or `-fcf-protection=full`
(x86_64 with CET) through the Zig invocation in `scripts/build_examples.py`. See
[03 §6](./03-hardware.md#6-putting-hardware-into-a-software-language-design).

These flags protect **non-A7 code** in the same process: linked C libraries, the
kernel, JIT payloads. A7-emitted code is already covered by the contract; the
flags harden the rest of the address space.

### Phase 6 — Region scopes for escape cases (optional, ~1 month)

§3.6. Ship only if Phase 3 leaves real ergonomic gaps in idiomatic A7 code. The
Cyclone literature is the reference design.

### Phase 7 — Concurrency story (deferred)

When threads are added, pick one model up front:

- **Channels + value-only sharing** (Go/Erlang). Simplest.
- **Mutable value semantics with actor isolation** (Hylo/Pony lite). Composes
  with §3.3–§3.4.

Do not pick now; record the question in `docs/STATUS.md`.

> Note (2026-09-16): ledger L1 puts concurrency in v1. The memory plan proposes
> structured tasks where values move in (gate M10), not yet approved.

### Suggested order of work

Each phase ships independently. Phase 5 is a flag, not a project; add it with any
release.

| Order | Phase | Work | Estimate |
| --- | --- | --- | --- |
| 1 | 0 | Audit and document the existing static rules | 1–2 days (the Phase 0 heading says 1 week) |
| 2 | 1 | Definite assignment + exhaustive `match` | 1–2 weeks |
| 3 | 2 | Non-null pointer types `?ptr T` vs `ptr T` | 2–3 weeks |
| 4 | 5 | Hardware safety flags (PAC, BTI, CET) via Zig | 1 day |
| 5 | 3 | Affine ownership + `inout` / `borrow` parameter modes | 4–8 weeks |
| 6 | 4 | Bound-proved slice indexing via the four-pattern catalog | 3–4 weeks |
| 7 | 6 | Region scopes, if §3.3–§3.4 leave gaps | optional, ~1 month |
| 8 | 7 | Concurrency | deferred until the rest is solid |

## 6. Anti-recommendations

| Don't | Why |
| --- | --- |
| Build a borrow checker | Lifetime annotations are the largest cost in Rust's spec. §3.4's `inout` mode catches the same bugs without them. |
| Build a tracing GC | Compile-time analysis (§3.3 + §3.6) removes UAF; a GC is unnecessary. |
| Build a Fil-C-style runtime | A software capability model helps only if the source language allows pointer forgery. A7 does not. |
| Add `unsafe { ... }` blocks | Libraries come to depend on them, and the compile-time guarantee is lost. |
| Insert silent runtime traps instead of compile errors | If the prover cannot discharge a check, reject the code. Falling back to a runtime trap is the bug this design avoids. |
| Make full refinement or dependent types the primary mechanism | Poor cost-to-coverage. Take about 95 % (unsourced estimate) with the four §3.5 patterns; route the rest through `try_get`. |
| Aim for CHERI / MTE compatibility at the source level | These are backend and ABI concerns, not language features. |
| Conflate memory safety with correctness | A7 does not aim to prove functional correctness. Stay in scope: out-of-bounds, UAF, type confusion, races. |

> Note (2026-09-16): ledger L15 agrees on no runtime collector. The memory plan
> proposes compiler-inserted releases, arenas and pools instead of user-visible
> ownership (§3.3) or regions (§3.6).

## 7. The contract paragraph (for `README.md` / `docs/SPEC.md`)

> A7 is a **total memory-safe** language. The compiler statically rejects every
> program that would exhibit uninitialized reads, null dereferences, type
> confusion, use-after-free, double-free, leaks in scope-bounded code, slice
> out-of-bounds, integer overflow, integer division by zero, NaN/inf propagation,
> pointer arithmetic out-of-bounds, stack overflow, or unhandled allocation
> failure. The hazards that cannot be discharged statically (opaque indices,
> opaque divisors, possible overflow on opaque operands, allocation success) are
> exposed as typed values (`?T` / `Result<T, E>` / refinement types) that the user
> is forced to handle. **The Zig code emitted by the A7 compiler is memory-safe on
> its own; it remains memory-safe when compiled with `zig build -O ReleaseFast`,
> i.e., with every Zig runtime safety check disabled. Memory safety is a property
> of the emitted source, not of the backend's flags.** The language has no
> `unsafe` escape hatch.

> Note (2026-09-16): this paragraph was never adopted. Integer overflow is
> superseded by L5 (wrapping), NaN/inf by L16 (IEEE floats), and the "no runtime
> check" wording is under review in gate M16. The current published contract is
> [`docs/SAFETY_CONTRACT.md`](../SAFETY_CONTRACT.md).

## 8. Cross-references

Prior art for each mechanism, catalogued in [06](./06-compile-time-safety.md):

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
| When a runtime fallback is unavoidable | [02 §6 UBSan-trap mode](./02-sanitizers.md#6-undefinedbehaviorsanitizer-ubsan) |
