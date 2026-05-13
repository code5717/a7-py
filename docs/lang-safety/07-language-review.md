# 07 — A7 Language Review against the Zero-Runtime-Error Contract

> Part of the `docs/lang-safety/` series. See the
> [README](./README.md) for the full map. Siblings:
> [01 — InvisiCaps](./01-invisicaps.md) ·
> [02 — Sanitizers](./02-sanitizers.md) ·
> [03 — Hardware-assisted safety](./03-hardware.md) ·
> [04 — Comparison](./04-comparison.md) ·
> [05 — Take-aways for A7](./05-for-a7.md) ·
> [06 — Compile-time techniques](./06-compile-time-safety.md).

This file audits **the current A7 language**, as of the codebase
inventory taken from `a7/` and `docs/SPEC.md`, against the
zero-runtime-error contract in [05](./05-for-a7.md). The contract
required that the emitted Zig be memory-safe under `-O ReleaseFast`
(every Zig runtime check disabled). The audit finds **the current A7
emission is not safe under `-O ReleaseFast`** — the language has
substantial gaps. This file catalogues them, prioritises them, and
proposes minimal source-level changes.

A note on intent: the previous files described the *target*. This file
describes the *current state* and the *delta*. Implementations should
treat the "Priority" column as the change order.

## 0. Executive summary

| # | Gap | Today's behaviour | Severity | Effort |
| --- | --- | --- | --- | --- |
| 1 | `ref T` is nullable by default | Emits `?*T`, every deref is `.?.*` (Zig safety-panic if null) | **Critical** | S |
| 2 | `cast(T, x)` is unrestricted, including int↔ptr | UB under `-O ReleaseFast` | **Critical** | S |
| 3 | Slice / array indexing emits bare `s[i]` with no bound proof | Zig safety-panic in safe, UB in fast | **Critical** | M |
| 4 | Integer arithmetic emits bare `+`, `-`, `*` | Wrap or trap depending on Zig flag; UB under `-O ReleaseFast` | **Critical** | M |
| 5 | Integer division emits `@divTrunc` / `@rem` with no `NonZero` proof | Zig safety-panic in safe, UB in fast | **Critical** | S |
| 6 | No definite-assignment check | Uninit reads return zero silently | High | S |
| 7 | `del` has no aliasing / move check | Double-free + UAF possible | High | L |
| 8 | No `Option<T>` / `Result<T, E>` types | Failure cannot be modelled except via `ref T` nullable abuse | High | M |
| 9 | Floats freely produce NaN / inf | Silent propagation through arithmetic | Medium | M |
| 10 | No stack-budget proof | Stack overflow can occur even though recursion is banned | Medium | S |
| 11 | No FFI boundary at all | Out of scope today; documented for future | Low | n/a |

S = small (1–2 weeks), M = medium (3–6 weeks), L = large (months).

The four **Critical** rows (1, 2, 3, 4, 5) are the prerequisites to
make any honest "zero runtime errors" claim. Until they ship, the
emitted Zig is not safe under `-O ReleaseFast` and the contract is
aspirational.

## 1. Per-feature audit

For each numbered item below: today's behaviour (with file:line
citations into the current codebase), the contract requirement, and
the proposed change.

### 1.1 Pointer types — `ref T` is nullable by default

**Today.** `ref T` is parsed as `TYPE_POINTER`
(`a7/parser.py:743-751`), modelled by `ReferenceType` (`a7/types.py:210-226`),
allowed to hold `nil` (`a7/passes/type_checker.py:727-733`), and lowered
to Zig's optional pointer `?*T` (`a7/backends/zig.py:1682-1688`). Every
deref is emitted as `.?.*`
(`build/debug/zig/src/013_pointers.zig:9` example). Under
`-O ReleaseSafe`, the `.?` traps on null; under `-O ReleaseFast`,
dereferencing a null `?*T` is **undefined behaviour**.

**Contract requirement.** [05 §1, §4.8.1–4.8.2](./05-for-a7.md).
Non-null pointer types must lower to Zig's `*T`; the deref must be
`p.*` with no `.?` involved. Nullable pointers must be a distinct
type whose deref is impossible without an explicit pattern match.

**Proposed change.**

1. Introduce `?ref T` (nullable) and keep `ref T` (non-null).
   Token-level change in `a7/tokens.py`; grammar change in
   `a7/parser.py` (one extra optional `QUESTION` before `REF`).
2. Extend `ReferenceType` with a `nullable: bool` flag, or add
   `OptionalReferenceType`. Update `equals`, `is_assignable_to`,
   `unify`.
3. Type-check: only `?ref T` can hold `nil`. `nil` literal has type
   `?ref Never` and unifies with any `?ref T`.
4. Type-check: dereferencing `?ref T` is an error; the user must
   `match` it.
5. Codegen (`a7/backends/zig.py`): emit `*T` for `ref T`, `?*T` for
   `?ref T`. `match` on `?ref T` becomes Zig's `if (p) |val| ... else
   ...` form. Deref of `ref T` becomes `p.*` with no `.?`.

**Migration.** Every existing `ref T` that today can be `nil`
becomes `?ref T`. This is a breaking change to the surface
language. `a7/stdlib/*.py` and `examples/013_pointers.a7` need to be
audited.

### 1.2 Cast — unrestricted and admits int↔ptr

**Today.** `cast(T, x)` is parsed as a general cast expression and
type-checks the target type and operand. There is **no validation
that the cast is safe**: integer-to-pointer and pointer-to-integer
both compile (`a7/passes/type_checker.py:1800-1805`). The error types
`INVALID_CAST` and `UNSAFE_CAST` are defined in `a7/errors.py:148-149`
but are not enforced. The Zig backend emits `@as(TargetType, value)`,
which performs reinterpretation or coercion depending on the types
(`a7/backends/zig.py:1690-1695`).

This is the most serious finding of the audit. Earlier docs (and
parts of `01-invisicaps.md` §17 / `05-for-a7.md` §2) claim "A7 has no
`inttoptr` operation." **That claim is false today.** `cast(ref T,
some_usize)` compiles and emits a reinterpret cast that produces an
arbitrary pointer.

**Contract requirement.** [05 §1, §4.8](./05-for-a7.md). The language
must not admit operations that forge pointers or that admit
type-confusion across pointer/integer boundaries.

**Proposed change.**

1. Classify casts. Introduce a small table in
   `a7/passes/type_checker.py`:
   - **Allowed** (lossless widening): `i32 → i64`, `u8 → u16`,
     `i32 → f64`, etc.
   - **Allowed with explicit `truncating_cast(T, x)`**: lossy
     narrowing, with a runtime check that the value fits (which
     becomes a compile error if the prover can discharge it
     statically) — or returns `?T`, see below.
   - **Allowed with explicit `bit_cast(T, x)`**: same-size
     non-pointer reinterpretation (`f32 ↔ u32`, etc.). Never for
     pointers.
   - **Forbidden**: any cast involving a pointer type other than
     `ref T → ?ref T` (always allowed) and `?ref T → ref T` (only
     after a `match` discharges the null case).
2. Make `cast(T, x)` a synonym for the allowed-widening kind only.
   Anything else uses the explicit variant. Promote
   `INVALID_CAST` / `UNSAFE_CAST` from declared-but-unused to
   actually emitted.
3. Backend (`a7/backends/zig.py`): widening uses `@as`; truncating
   uses `@truncate`; bit_cast uses `@bitCast`. Reinterpret of
   integer ↔ pointer is **not emitted**, because it is rejected at
   the front-end.

**Migration.** Audit every `cast(...)` in the example corpus
(`examples/015_types.a7` and others) and classify it. Most should
fall into the allowed-widening bucket; pointer↔integer casts (if
any) must be removed.

**This should be done first.** A language that claims memory safety
while admitting a reinterpret cast from `usize` to `ref T` has no
safety claim at all.

### 1.3 Slice / array indexing — no bound proof

**Today.** `s[i]` for `s: []T` is type-checked to require `i: usize`
or non-negative integer literal (`a7/passes/type_checker.py:1680-1690`).
The Zig backend emits direct `s[i]` (`a7/backends/zig.py:1638-1645`)
with no bounds analysis. Same for `[N]T` arrays. The example
`build/debug/zig/src/012_arrays.zig` uses `numbers[i]` directly.
Under `-O ReleaseSafe`, Zig traps on OOB; under `-O ReleaseFast`,
the access is **undefined behaviour**.

**Contract requirement.** [05 §3.5, §4.8.3–4.8.4](./05-for-a7.md).
Every slice access must either be statically bound-proved (so the
emitted Zig can use `s.ptr[i]` and skip the check entirely) or go
through a `try_get(i) -> ?T` form that emits an explicit `if`.

**Proposed change.**

1. Implement the four-pattern recogniser in `a7/passes/type_checker.py`:
   - `for i in 0..s.length: s[i]` — bound `i < s.length` is the loop
     condition.
   - `s[k]` where `k` is a literal and the slice has a refined upper
     bound.
   - `s[i]` after `if i < s.length` (flow-sensitive narrowing on the
     same `usize`).
   - `s[i]` where `i: Index(s.length)` (constructor-checked refinement
     type; see §1.9 below).
2. Any other `s[i]` is a **compile error**. The user rewrites using
   `s.try_get(i)` which returns `?T`.
3. Backend (`a7/backends/zig.py`): for the proved cases, emit
   `s.ptr[i]` (no bounds check). For `try_get`, emit
   `if (i < s.len) some(s.ptr[i]) else null`.

**Migration.** Every existing `s[i]` in `examples/` and tests must
be rewritten to one of the proved forms or use `try_get`. Most loops
already use `for i in 0..s.length` patterns; the audit may be
mechanical.

### 1.4 Integer arithmetic — bare `+`, `-`, `*` emit Zig `+`

**Today.** Binary ops `ADD`, `SUB`, `MUL` lower to Zig's `+`, `-`,
`*` (`a7/backends/zig.py:1566`). Under `-O ReleaseSafe` these trap on
overflow; under `-O ReleaseFast` they wrap silently and the result
may be observed as `INT_MIN + 1` or similar without warning.

**Contract requirement.** [05 §4.3, §4.8.6–4.8.8](./05-for-a7.md).
Bare `+` is allowed only when both operands have ranges the prover
can show won't overflow. Otherwise the user picks `checked_add`,
`wrap_add`, or `sat_add` explicitly.

**Proposed change.**

1. Track integer **ranges** in the type checker (a tiny refinement
   lattice — concretely, `{u32}` becomes `{u32 ∈ [0, 2^32-1]}` and
   refines along loop induction, `if` narrowing, and arithmetic).
2. For each `+` (and `-`, `*`, `<<`):
   - If the ranges of operands prove the result fits the target
     type, emit Zig `+` (or `-`, `*`, `<<`).
   - Otherwise, **compile error** suggesting the user pick one of
     `a.checked_add(b)`, `a.wrap_add(b)`, `a.sat_add(b)`.
3. Stdlib methods (`a7/stdlib/math.py` or a new module) provide the
   three forms. Backend lowers each to the corresponding Zig form
   (`@addWithOverflow`, `+%`, `+|`).

**Migration.** Hot. Most arithmetic in examples is in proved-range
contexts (loop counters, small constants); a non-trivial subset will
need explicit `checked_*` annotations.

### 1.5 Integer division — emits `@divTrunc(a, b)` with no `NonZero` proof

**Today.** `a / b` for integers emits `@divTrunc(a, b)`
(`a7/backends/zig.py:1550-1558`). `a % b` emits `@rem(a, b)`. Neither
the type checker nor the backend verifies `b != 0`. Under
`-O ReleaseSafe`, Zig traps; under `-O ReleaseFast`, dividing by zero
is UB.

**Contract requirement.** [05 §4.1, §4.8.5](./05-for-a7.md). The
divisor must be of type `NonZero<T>`. A bare `int` cannot be used as
a divisor.

**Proposed change.**

1. Introduce `NonZero<T>` as a refinement type (the lite version —
   no SMT, just a constructor that returns `?NonZero<T>`).
2. `/` and `%` are defined only when the right-hand operand has type
   `NonZero<T>`. Bare `int` rhs is a compile error suggesting
   `NonZero::new(b)` and a `match` on the `?NonZero<T>`.
3. For signed division, also exclude `-1` to avoid `INT_MIN / -1`.
   Wrap in `SafeDivisor<T>` or add an extra constructor check.
4. Backend (`a7/backends/zig.py`): emit `@divTrunc(a, d.value)` /
   `@rem(a, d.value)` where `d.value` is the inner field of the
   `NonZero<T>`. No `b != 0` check at runtime; the static type
   discharges it.

**Migration.** Audit every `/` and `%` in `examples/` and tests; most
are over literal denominators (free) or loop-invariant denominators
that can be hoisted into a `NonZero` construction.

### 1.6 Definite assignment — currently absent

**Today.** Variables can be declared without initialisers
(`buffer: [1024]u8` is valid); the Zig backend lets Zig handle
default initialisation. There is **no analysis tracking whether a
variable has been written before read**
(`a7/passes/type_checker.py` has no definite-assignment pass). The
example `build/debug/zig/src/002_var.zig:22-23` shows
`const value: i32 = 0;` for an uninitialized A7 variable —
silently zero-initialized.

**Contract requirement.** [05 §3.1, 06 §1](./06-compile-time-safety.md#1-definite-assignment--flow-analysis).
Reading an unassigned local is a compile error.

**Proposed change.**

1. Add a definite-assignment pass in
   `a7/passes/semantic_validator.py` (reuses the CFG plumbing the
   recursion check already has).
2. Per variable, compute the assignment lattice on each basic
   block; a read at a point not definitely-assigned is an error.
3. Drop the silent zero-initialisation in the Zig backend; emit a
   variable's storage only at its assignment site (Zig already
   supports `var x: i32 = undefined; x = compute();` patterns).

**Migration.** Examples that declare `buf: [1024]u8` and then loop
over `buf` work fine because the loop writes before reading. Any
example that reads an uninitialised local must add the initialiser.

### 1.7 `del` — no aliasing, no move check

**Today.** `del p` deallocates a heap reference. The type checker
verifies the operand is a reference; **there is no check that `p`
is unique, that no other reference aliases the same allocation, or
that `p` has not already been deleted** (`a7/docs/SPEC.md:1067`
explicitly says lifetime analysis "not yet implemented").
`build/debug/zig/src/011_memory.zig:17` shows `defer if (value_ptr)
|p| allocator.destroy(p)` — the `defer` is generated by Zig codegen,
but A7 has no UAF prevention.

**Contract requirement.** [05 §3.3–§3.4](./05-for-a7.md). Affine
ownership: `del` consumes the value, and subsequent uses are
compile errors. Aliasing is prevented by making references
non-storable except through the type system (typically: `inout` /
`borrow` parameter modes only).

**Proposed change.** (Large; see [05 §5 Phase 3](./05-for-a7.md#5-phased-plan-zero-runtime-error-ordering).)

1. **Move analysis pass** in `a7/passes/`: each `ref T` binding has
   a "consumed" flag. Passing by value, returning, assigning into a
   field, or `del`-ing consumes. Re-using a consumed binding is an
   error.
2. **Parameter passing modes**: `inout`, `borrow`. Allowed as
   parameter types only, never as variable / field types. A
   `borrow`-ed reference is read-only and cannot escape the
   function; an `inout`-ed reference is unique within the function's
   scope.
3. **Call-site exclusivity check**: at each call, verify no two
   `inout`/`borrow` arguments name the same allocation.
4. Backend: no codegen change needed beyond emitting `*T` /
   `*const T` for `inout` / `borrow`. The static guarantee is what
   matters; the emission is identical.

**Migration.** This is the biggest design change. Examples with
manual `del` need to be rewritten to either rely on scope-exit
`Drop` or to move through return-value chains. Several existing
patterns (e.g., transient buffers built up and then handed off)
will need region-style scopes (see §1.10).

### 1.8 No `Option<T>` / `Result<T, E>` — fallibility is unmodelled

**Today.** A7 has **no `Option<T>` or `Result<T, E>` generic type**.
The only nullability in the language is via `ref T` (which is
implicitly nullable, see §1.1). There is no way to model "this
operation may fail" except by abusing nullable references.

**Contract requirement.** [05 §1, §4.1–§4.7](./05-for-a7.md). Every
fallible operation returns `?T` or `Result<T, E>`. The user
unwraps via `match`.

**Proposed change.**

1. Add two generic types to `a7/stdlib/`:
   - `Option<$T>` with variants `some($T)` and `none`.
   - `Result<$T, $E>` with variants `ok($T)` and `err($E)`.
2. Introduce `?T` syntax as sugar for `Option<T>` (separate from
   `?ref T`, which can be either sugar for `Option<ref T>` or a
   distinct shape — design decision).
3. Type-check: `?T` and `Result<T, E>` must be `match`ed before
   their inner value is used.
4. Backend: lower to tagged Zig unions. `?T` lowers to Zig's `?T`
   directly when `T` is a pointer; otherwise to a Zig tagged union
   `union(enum) { some: T, none: void }`.

**Migration.** Every example that currently uses `ref T` to mean
"might be null" should switch to `?T` or `?ref T`. New stdlib
functions for fallible ops (parse, divide, allocate, slice index)
return `Option<T>` / `Result<T, E>`.

### 1.9 Refinement types — currently absent

**Today.** A7's type system has primitives, slices, arrays,
references, structs, enums, tagged unions, function types, and
generics (`a7/types.py`). There are **no refinement types** —
nothing of the form `{x: int | x > 0}`.

**Contract requirement.** [05 §3.5, 06 §10](./06-compile-time-safety.md#10-refinement-types).
A narrow refinement vocabulary is needed for bound-proved indexing,
non-zero divisors, finite floats, and proved-range arithmetic.

**Proposed change.** Implement the **lite** version — *not* a full
SMT integration:

1. Add a few named refinements to `a7/types.py`:
   - `Index($n)` — `{i: usize | i < $n}` where `$n` is a
     compile-time-bound `usize`.
   - `NonZero<$T>` — `{x: $T | x != 0}`.
   - `Fin<$F>` — `{x: $F | !is_nan(x) && !is_inf(x)}`.
   - `Bounded<$T, $lo, $hi>` — for arithmetic ranges.
2. Each refinement is a `struct` with a private `value` field and
   one or more constructors. Constructors return `?Self` (i.e.,
   either a valid refinement or `none`).
3. Operators (`+`, `/`, `[]`) are extended to consume the refined
   types where appropriate.
4. The type-checker's job is **pattern recognition**, not theorem
   proving. The four `[]` patterns and the `+` range-tracker in
   §1.3 / §1.4 fall out of this.

**Why not full refinement types?** Liquid-Haskell-style refinement
requires bundling an SMT solver, which conflicts with "keep it
simple." The lite version covers the 95 % case directly.

### 1.10 Stack budget — no proof, can still overflow

**Today.** A7 bans recursion (`a7/passes/semantic_validator.py:501-544`),
so the call graph is a DAG. But the compiler **does not compute the
maximum stack depth** of a program, and the runtime doesn't set
`RLIMIT_STACK` to a static bound. A program with deeply-nested
non-recursive calls or large stack arrays can still overflow.

**Contract requirement.** [05 §4.4](./05-for-a7.md). The compiler
computes the max stack depth at compile time and the program physically
cannot stack-overflow.

**Proposed change.**

1. Add a stack-budget pass after type-checking. For each function,
   compute the frame size (sum of local types' sizes + spill
   estimate). Walk the call DAG; the program's max stack is the
   maximum sum-of-frame-sizes along any path.
2. Configure a budget (`--stack-budget BYTES`, default 1 MiB).
   Reject programs exceeding it.
3. Emit a `comptime` assertion in the generated Zig and pass the
   computed budget as the thread stack size in `main`.

**Migration.** Should be transparent for almost all current
examples. A deliberately deep example might fail; that's the
intended behaviour.

### 1.11 Floating-point — NaN / inf flow silently

**Today.** Floats are primitives (`f32`, `f64`); arithmetic uses
direct Zig operators (`a7/backends/zig.py:1556-1557`). NaN and
infinity are valid `f64` values and propagate through arithmetic
without any signal. Comparisons with NaN return false; reads of NaN
into `int` are UB under `-O ReleaseFast`.

**Contract requirement.** [05 §4.6](./05-for-a7.md). Either `f64`
itself is a sum type whose `nan` / `inf` cases must be matched, or
there's a `Fin<f64>` refined type for use in code that wants the
total-arithmetic guarantee.

**Proposed change.**

1. Add `Fin<f64>` and `Fin<f32>` refinements (§1.9).
2. Float operations on `Fin<T>` return `?Fin<T>` when the result
   can be non-finite (division, sqrt of negative, log of zero,
   subtraction `inf - inf`).
3. Bare `f64` continues to work but only inside arithmetic that
   stays inside `f64`; conversion to `int` is `int_from(f: f64) ->
   ?int`.

**Severity** is "Medium" because most A7 examples don't do float
arithmetic; this is a forward-looking gap.

### 1.12 FFI — explicitly absent

**Today.** A7 has no `extern` keyword and no syntax for foreign
function declarations.

**Contract requirement.** [05 §4.7](./05-for-a7.md). FFI is the
single allowed boundary at which the language stops enforcing. Each
foreign function must return a `Result<T, ForeignError>`; the shim
is a small Zig wrapper that the compiler treats as opaque.

**Proposed change.** Defer. Document in `docs/STATUS.md` that
when FFI is added, it must conform to the §4.7 boundary discipline.

## 2. What A7 already does right

Worth being explicit about, so future contributors don't undo it:

- **Recursion is banned** at `a7/passes/semantic_validator.py:501-544`.
  Keep it that way; the stack-budget analysis (§1.10) depends on
  the call graph being a DAG.
- **No `unsafe` block or escape hatch** exists. Adding one would
  break the contract.
- **No `inttoptr` syntax**. (But see §1.2 — `cast` currently
  admits the equivalent; that's the gap.)
- **No raw pointer arithmetic.** Public A7 does not expose address-of or
  dereference syntax; reference lowering is compiler-internal.
- **Heap fixed arrays (`new [N]T`) are rejected** (`a7/CLAUDE.md`,
  `docs/STATUS.md`). Keep that until the language model is
  defined.
- **`match` exhaustiveness is checked** for enums and bools
  (`a7/passes/type_checker.py:1854-1858`). Extend to tagged unions
  and option/result when those land.
- **Type sets / generic constraints** via `@type_set(...)` give a
  good basis for the refinement-lite system in §1.9.
- **`usize` is enforced for indices** (`a7/passes/type_checker.py:1680-1690`).
- **No FFI** today, which means there's no boundary leakage to
  worry about yet.

## 3. Things parsed-only / reserved that interact with safety

From `docs/STATUS.md` and `CLAUDE.md`:

- **Variadic parameters** are parsed but codegen-rejected. When
  implemented, they must use a typed `va_list` shape and not the
  C-style anything-goes form. Fil-C's experience
  ([01 §7 examples 27–29](./01-invisicaps.md#7-worked-examples-from-invisicaps_by_examplehtml))
  shows the hazards.
- **Intrinsics other than `@type_set`** (`@size_of`, `@align_of`,
  `@unreachable`, `@likely`) are reserved. `@unreachable` in
  particular needs the proof-obligation discipline from
  [05 §4.8.12](./05-for-a7.md#4812-no-unreachable-reached-at-runtime).
- **Multi-decl / destructuring** is parsed but not implemented.
  When it lands, the definite-assignment pass (§1.6) must extend
  to handle partial destructuring writes.
- **Multi-file lowering** (`docs/STATUS.md`) — when imports
  link across files, the type-confusion / ODR-mismatch hazards
  Fil-C catalogues ([01 §7 examples 22–26](./01-invisicaps.md#7-worked-examples-from-invisicaps_by_examplehtml))
  apply. The language already discards ODR assumptions by design,
  but the linker must trap (or, better, the compiler must validate
  that re-declarations match).

## 4. Recommended change order

This is the order in which the work in §1 should ship. Each row
moves A7 closer to the contract; each row depends on the rows above
having shipped.

1. **§1.2 — Restrict `cast`.** Highest priority. A claim of memory
   safety while admitting reinterpret casts to pointer types is
   self-defeating. This is a one-week task.
2. **§1.1 — Split `ref T` and `?ref T`.** The largest single
   safety win.
3. **§1.6 — Definite assignment.** Easy and removes a silent-zero
   footgun.
4. **§1.5 — `NonZero` for division.** Small.
5. **§1.10 — Stack budget.** Small; closes the "but the program can
   stack-overflow anyway" objection.
6. **§1.4 — Typed arithmetic with range tracking.** Medium.
7. **§1.3 — Bound-proved indexing + `try_get`.** Medium.
8. **§1.8 — `Option<T>` / `Result<T, E>`.** Medium.
9. **§1.9 — Refinement-lite types** (drops out of §1.3, §1.4, §1.5,
   §1.11). Medium.
10. **§1.7 — Affine ownership.** Large; the most expressive change
    and the most invasive.
11. **§1.11 — Float NaN / inf** through `Fin<f>`. Medium.
12. **§1.12 — FFI boundary** when FFI is finally needed.

After (1)–(7), the operational test from
[05 §4.8.13](./05-for-a7.md#4813-no-panic-no-trap-no-__builtin_trap)
— build every example with `zig build-exe -O ReleaseFast`, run the
test corpus, observe zero crashes — should pass for the existing
example set. Items (8)–(10) extend the contract to more expressive
programs; (11)–(12) close residual gaps.

## 5. Open design questions

These do not block the early phases but should be settled before
§1.7 lands:

- **Should `?ref T` be a separate type, sugar for
  `Option<ref T>`, or both?** Zig's choice was "separate type with
  special syntax." Rust's was "Option, with niche-optimisation."
  The Zig approach is simpler to implement (it's already what the
  current `ref T → ?*T` lowering does); the Rust approach is more
  uniform.
- **How do refinement types compose with generics?** If a function
  takes `xs: []T` and indexes `xs[i]`, the function needs to take
  `i: Index(xs.length)`. Does the generic `T` propagate through?
  Probably not — `Index($n)` is over `usize`, not `T`. Worth
  documenting.
- **What's the syntax for the affine-ownership consume?** Rust
  has implicit move; Hylo has `consume`. Picking one early avoids
  a future syntactic churn.
- **Where do range / refinement annotations live — on the type,
  or as separate constraints?** Liquid Haskell puts them in
  comments. F* / Dafny put them on types. A7's parser already
  handles `@type_set(...)` annotations on type parameters; the
  same machinery could carry `@range(lo, hi)`, `@nonzero`, etc.
- **Diagnostics.** The single biggest determinant of how usable a
  compile-time-safe language is. Plan to invest in
  source-location-anchored, suggestion-bearing messages
  ("`s[i]` cannot be proved in-bounds; consider
  `s.try_get(i)` or wrap the loop in `for i in 0..s.length`")
  from the start of §1.3 and §1.4.

## 6. Closing

The A7 codebase is well-positioned for the contract in
[05](./05-for-a7.md): the type system, semantic-validation
machinery, and Zig codegen are in place; the gaps are about
*tightening* what already exists, not building new infrastructure.

The single most urgent change is **restricting `cast`** (§1.2).
Until that lands, A7 cannot honestly claim to be memory-safe
under any backend flag. Everything else is incremental.

The Zig backend should be re-tested under `-O ReleaseFast` after
each numbered change. The no-trap codegen test from
[05 §4.8.13](./05-for-a7.md#4813-no-panic-no-trap-no-__builtin_trap)
is the operational definition of "did this change preserve the
contract."
