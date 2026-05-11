# Comparative: Ada and SPARK

> Phase B artifact in the `docs/lang-safety/` research process.
> Companion to the Phase A edge-case files in `../edge-cases/`.

Ada (current revision: Ada 2022, with widespread Ada 2012 deployment)
and its formally-verified subset **SPARK 2014+** are the
industrial reference for static memory safety in systems
programming. Ada introduced **ranged subtypes**, **definite
assignment**, **design-by-contract aspects**, and **exhaustive case
statements** decades before any of these were named in mainstream
discourse. SPARK takes the subset that can be statically proved,
adds an ownership model for access types (Rust-inspired, since
SPARK 2018), and proves *absence of runtime errors* for the
verified subset — exactly A7's target.

This file walks each of the 12 gaps from
[`../07-language-review.md`](../07-language-review.md) and records
what Ada/SPARK does, what works, and what A7 can steal.

Primary sources:

- [Ada Reference Manual (ARM 2022)](https://www.adaic.org/ada-resources/standards/ada22/)
- [SPARK Reference Manual](https://docs.adacore.com/spark2014-docs/html/lrm/)
- [SPARK User's Guide](https://docs.adacore.com/spark2014-docs/html/ug/en/)
- [Learn Ada (AdaCore)](https://learn.adacore.com/)
- [Memory Safety in Ada and SPARK (AdaCore blog)](https://www.adacore.com/blog/memory-safety-in-ada-and-spark-through-language-features-and-tool-support)
- [Pointer Support, Ownership, and Dynamic Memory Management (SPARK UG §5.9)](https://docs.adacore.com/spark2014-docs/html/ug/en/source/access.html)
- [Recursive Data Structures in SPARK (Dross et al., 2020)](https://link.springer.com/chapter/10.1007/978-3-030-53291-8_11)

---

## How Ada/SPARK handles each gap

### Gap 01 — Cast

Ada distinguishes **type conversion** (`Integer(X)`) from
**unchecked conversion** (`Ada.Unchecked_Conversion`):

```ada
-- Numeric conversions are checked
Y : Integer := Integer(X);  -- may raise Constraint_Error

-- Unchecked reinterpretation is opt-in
function To_Int is new Ada.Unchecked_Conversion (
    Source => My_Float, Target => Integer);
```

**Pointer-to-integer reinterpretation** requires
`Ada.Unchecked_Conversion` explicitly and is a clear safety
violation when it happens. SPARK **forbids**
`Ada.Unchecked_Conversion` entirely (it cannot be statically
analysed) unless wrapped in a precondition the prover discharges.

**What A7 can steal:** the *named operator* discipline. A7's
`cast` / `truncating_cast` / `bit_cast` split is directly inspired
by Ada's `Conversion` / `Checked_Conversion` /
`Unchecked_Conversion` family. Critically, the unchecked form
is *flagged* and forbidden in the proved subset.

**What A7 should not steal:** Ada's checked numeric conversion
raises `Constraint_Error` at runtime by default. A7 requires
either compile-time discharge or a typed `Option` return.

---

### Gap 02 — Nullable pointers

Ada's access types are nullable by default. Ada 2005 introduced
`not null` as a subtype constraint:

```ada
type Acc is access Integer;            -- nullable
subtype Non_Null_Acc is not null Acc;  -- non-null

procedure Foo (X : not null Acc);      -- non-null parameter
```

`null` is the default value of every access variable, so
"uninitialised pointer" is the same as "null pointer" — it cannot
be undefined.

SPARK enforces non-null access wherever declared and rejects
programs that would assign `null` to a `not null` variable.

**What A7 can steal:** the **opt-in non-null** syntax shape, but
**inverted**: A7's `ref T` is non-null by default and `?ref T` is
the opt-in nullable. The Ada precedent shows non-null parameters
are a usable, ergonomic feature.

**What A7 should not steal:** the default-to-null behaviour. The
A7 contract requires non-null by default; nullability is the
explicit choice.

---

### Gap 03 — Definite assignment

Ada's stance is **implicit zero-initialisation** for access types
(see Gap 02) and **declaration-time initialisation** for most
others. Reading an uninitialised non-access variable is a *bounded
error* — the compiler may give it a value, but the program is
permitted to raise `Program_Error`.

SPARK adds explicit flow analysis: **every variable must be
initialised before use**. The SPARK tool (`gnatprove`) emits a
flow-analysis error for any read of an uninitialised variable.

```ada
procedure Bad is
   X : Integer;
begin
   Put (X);  -- SPARK: error, X may not be initialised
end Bad;
```

SPARK's flow analysis also tracks `Globals` (data the procedure
reads/writes) and `Depends` (input-to-output dependencies). The
DA pass in A7 is a strict subset of SPARK's flow analysis.

**What A7 can steal:** the SPARK flow-analysis approach.
Strictly require initialisation; reject "implicit zero" silently.
Apply to all types, not just access.

**What A7 should not steal:** Ada's default-zero for access
types. A7 makes uninit a hard error.

---

### Gap 04 — `NonZero` division

Ada's `Constraint_Error` raises on division by zero. SPARK
**proves absence of division by zero** by requiring a
precondition:

```ada
function Divide (A, D : Integer) return Integer
  with Pre  => D /= 0,
       Post => Divide'Result = A / D;
```

SPARK's prover discharges the `Pre`-condition at every call site.
A literal divisor `D = 5` discharges trivially; an opaque divisor
requires the caller to have proved `D /= 0` already (typically by
its own subtype).

A common pattern: define a subtype excluding zero, and require it
at the divisor:

```ada
subtype Nonzero_Int is Integer range -Integer'Last .. Integer'Last
   with Static_Predicate => Nonzero_Int /= 0;

function Divide (A : Integer; D : Nonzero_Int) return Integer is
  begin return A / D; end Divide;
```

**What A7 can steal:** the **subtype** approach — A7's `NonZero<T>`
is essentially Ada's `Nonzero_Int` made explicit, with a
constructor returning `Option<NonZero<T>>` (instead of Ada's
runtime `Constraint_Error`).

**What A7 should not steal:** runtime constraint checks. A7 wants
the proof or the typed return, not the trap.

---

### Gap 05 — Stack budget

Ada has the `Storage_Size` aspect for tasks:

```ada
task type Worker
  with Storage_Size => 65_536;
```

But Ada doesn't compute stack-budget statically — it relies on
the user to size each task. SPARK doesn't either: stack-overflow
is one of the few runtime errors SPARK does not guarantee to be
absent (though tooling like `gnatstack` performs static analysis
post-compilation).

**What A7 can steal:** the *per-thread* annotation idea
(`Storage_Size`). A7's `--stack-budget` flag generalises this to
the whole program by exploiting the no-recursion invariant.

**What A7 should not steal:** Ada's reliance on the user picking
the right number. A7's stack budget is *computed* by the compiler
from the call graph; the user override is rare.

---

### Gap 06 — Typed arithmetic with range tracking

**This is Ada's strongest feature.** Ranged subtypes and the
type system encode integer bounds:

```ada
subtype Buffer_Size is Natural range 0 .. 1023;
B : Buffer_Size := 100;
B := B + 1000;  -- raises Constraint_Error at runtime
                 -- SPARK rejects at compile time
```

Predefined subtypes:

- `Natural` is `Integer range 0 .. Integer'Last`
- `Positive` is `Integer range 1 .. Integer'Last`

User-defined subtypes can carry **static predicates** (Ada 2012):

```ada
subtype Even is Integer with Static_Predicate => Even mod 2 = 0;
```

SPARK proves absence of overflow by tracking subtype constraints
through arithmetic. A function with `X : Positive` and `X + 1`
must satisfy `Positive` for the result (i.e., not overflow). The
SPARK prover discharges this; opaque ranges fall through as a
verification condition the user must prove or refactor.

**What A7 can steal:** **the entire ranged-subtype model.** A7's
`Bounded<T, lo, hi>`, `Index<n>`, `NonZero<T>`, `Positive<T>`,
`Natural<T>` refinements (Gap 09) are a direct translation. The
SPARK-prover style of "discharge by static predicate" is also
what A7's pattern-recognition tries to do.

**What A7 should not steal:** the **runtime constraint-check
mechanism**. Ada inserts runtime checks by default; SPARK proves
them away. A7 skips straight to the proof — anything not provable
must be rewritten by the user (via `checked_add` etc.), not
silently checked at runtime.

---

### Gap 07 — Bounded indexing

Ada's array indexing uses ranged subtype indices:

```ada
type Buffer is array (Natural range 0 .. 1023) of Octet;
B : Buffer;
B (i) := 0;  -- i must be in 0..1023
```

The index type itself encodes the bounds; passing an out-of-range
index is a compile error (if the value is statically out of
range) or a runtime `Constraint_Error`.

For dynamic indices, Ada provides the `'First`, `'Last`, and
`'Range` attributes:

```ada
for I in B'Range loop
   B (I) := Compute (I);  -- I provably in B'Range
end loop;
```

SPARK proves the index is in range at every access.

**What A7 can steal:** Ada's `'Range` attribute is a direct
analog to A7's `for i in 0..s.length: s[i]` pattern. The
SPARK pattern of "carry the bound in the index type" is also
the basis for A7's `Index<n>` refinement.

**What A7 should not steal:** the runtime `Constraint_Error`
fallback. A7 requires the proof.

---

### Gap 08 — `Option<T>` / `Result<T, E>`

Ada doesn't have these out of the box. Ada's standard fallibility
mechanism is **exceptions**:

```ada
function Lookup (Key : K) return V;  -- raises Not_Found
```

SPARK **forbids exceptions** as control flow (they break flow
analysis); the SPARK style is either:

- Return a status code plus an out-parameter:
  `procedure Lookup (Key : K; Value : out V; Found : out Boolean)`.
- Use a discriminated record (Ada's tagged union):

```ada
type Result_T (Ok : Boolean := False) is record
  case Ok is
    when True  => Value : V;
    when False => Error : E;
  end case;
end record;
```

**What A7 can steal:** the discriminated-record approach is
exactly the sum-type / tagged-union shape `Result<T, E>` uses.
SPARK's experience of "exceptions don't compose with flow
analysis" is the *reason* A7 uses `Result` instead of an
exception system.

**What A7 should not steal:** exceptions as a fallback. A7's
contract requires every fallibility to be typed.

---

### Gap 09 — Refinement-lite types

**Ada subtypes are refinement-lite types**, exactly. The
predicate vocabulary:

- `Static_Predicate` — compile-time-checkable predicate
- `Dynamic_Predicate` — runtime-checkable predicate
- Range constraint — special case of static predicate
- `'Valid` attribute — verify a value's representation

```ada
subtype Even is Integer with Static_Predicate => Even mod 2 = 0;
subtype Positive_Square is Natural
  with Dynamic_Predicate => Positive_Square = Ada.Numerics.Elementary_Functions.Sqrt
                                                 (Float (Positive_Square)) ** 2;
```

SPARK restricts predicates to those that don't depend on runtime
input (so they can be discharged statically).

**What A7 can steal:** the closed-set vocabulary (`Natural`,
`Positive`, ranged subtypes) plus the constructor-driven entry
point. A7's `Bounded<T, lo, hi>::new(x) -> ?Bounded<T, lo, hi>`
is the constructor-only entry; Ada's equivalent is assignment
that fires the constraint check.

**What A7 should not steal:** runtime predicate checking. A7
only admits predicates the prover can discharge statically (the
SPARK static-predicate restriction is the model).

---

### Gap 10 — Affine ownership

**SPARK 2018 adopted an ownership model for access types,
explicitly inspired by Rust.** The rules:

- Assignment between access objects is a **move**: the source
  loses permission, the destination gains it.
- Read-only sharing is permitted (multiple aliases that can only
  read).
- Read-write requires exclusive ownership (one active reference).
- Pool-specific access types only point at heap-allocated data;
  stack pointers are forbidden.
- Deallocation transfers ownership to the deallocator; subsequent
  use is a flow-analysis error.

```ada
declare
   P : access Integer := new Integer'(42);
   Q : access Integer := P;  -- move: P loses permission
begin
   Put (Q.all);  -- OK
   Put (P.all);  -- SPARK error: P has been moved
end;
```

[Recursive Data Structures in SPARK (Dross et al., 2020)](https://link.springer.com/chapter/10.1007/978-3-030-53291-8_11)
describes the work to extend this model to handle linked lists
and trees — the hardest cases.

**What A7 can steal:** essentially **the whole model**. SPARK's
move semantics on access types is the closest production
deployment of the affine-ownership model A7 needs. Crucially,
SPARK proves it at compile time (no runtime cost), and the
ergonomics are tractable.

**What A7 should not steal:** Ada's *un*-restricted access
types (the pre-2018 form) remain available outside the proved
subset. A7's contract requires the strict form everywhere.

A7 will additionally take Hylo-style parameter modes (Gap 10
Q10a), which Ada doesn't have, to avoid storable references
entirely.

---

### Gap 11 — Finite floats

Ada has `Float`, `Long_Float`, `Long_Long_Float`. The `'Valid`
attribute checks whether a scalar value is in its subtype's
range; for floats on most implementations, this also rejects
NaN and inf:

```ada
if X'Valid then
   -- X is finite (on most implementations)
   ...
end if;
```

Ada doesn't have an explicit `Fin<F>` refinement; the user
queries `'Valid` at the boundary. SPARK's prover tracks
`'Valid` flow.

**What A7 can steal:** the `'Valid` check is the runtime form
of A7's `Fin::new`. The principle that float NaN/inf must be
guarded at boundaries is the same.

**What A7 should not steal:** the runtime form. A7 wraps in
`Fin<F>` at the type level.

---

### Gap 12 — FFI

Ada has rich FFI:

```ada
function malloc (Size : size_t) return System.Address
  with Import, Convention => C, External_Name => "malloc";
```

`pragma Convention(C, ...)` controls calling convention and
struct layout. `pragma Import` declares foreign symbols;
`pragma Export` exposes Ada symbols.

SPARK restricts FFI: imported functions are summarised by their
contracts (Pre/Post/Globals/Depends); SPARK trusts these
contracts. The user is responsible for getting them right.

**What A7 can steal:** the **explicit boundary** discipline.
A7's `extern fn ... -> Result<T, E>` discipline is essentially
"SPARK summary, but mandatory typed-return". The trust model is
identical.

**What A7 should not steal:** Ada's pragma syntax. A7 uses
attributes / annotations consistent with the rest of the
language.

---

## Primary sources

Already linked inline. Quick index:

- [Ada Reference Manual (ARM 2022)](https://www.adaic.org/ada-resources/standards/ada22/)
- [SPARK Reference Manual](https://docs.adacore.com/spark2014-docs/html/lrm/)
- [SPARK User's Guide](https://docs.adacore.com/spark2014-docs/html/ug/en/)
- [Learn Ada — Intro](https://learn.adacore.com/courses/intro-to-ada/)
- [Learn Ada — Advanced](https://learn.adacore.com/courses/advanced-ada/)
- [Memory Safety in Ada and SPARK (AdaCore)](https://www.adacore.com/blog/memory-safety-in-ada-and-spark-through-language-features-and-tool-support)
- [SPARK Pointer Support and Ownership](https://docs.adacore.com/spark2014-docs/html/ug/en/source/access.html)
- [Recursive Data Structures in SPARK (Dross et al.)](https://link.springer.com/chapter/10.1007/978-3-030-53291-8_11)
- [Type Contracts in SPARK](https://docs.adacore.com/spark2014-docs/html/ug/en/source/type_contracts.html)
- [Subprogram Contracts in SPARK](https://docs.adacore.com/spark2014-docs/html/ug/en/source/subprogram_contracts.html)

---

## What A7 can steal — consolidated list

1. **Ranged subtypes** as the foundation of the refinement system
   (Gap 06, 07, 09). The `Bounded<T, lo, hi>` / `Index<n>` /
   `Natural<T>` / `Positive<T>` vocabulary is a direct port.
2. **Static-predicate restriction** (SPARK) — only predicates
   the prover can discharge are allowed. A7 enforces the same
   discipline.
3. **Named conversion vocabulary** (`Conversion` /
   `Checked_Conversion` / `Unchecked_Conversion`) — informs the
   `cast` / `truncating_cast` / `bit_cast` split (Gap 01).
4. **`not null` access types** — informs the `ref T` vs
   `?ref T` design, with A7's default flipped to non-null
   (Gap 02).
5. **SPARK flow analysis** — informs definite assignment + move
   analysis as a single CFG pass (Gap 03, 10).
6. **SPARK ownership model for access types** — the production
   reference for affine ownership at compile time (Gap 10).
7. **Discriminated records** as the canonical fallibility shape
   (Gap 08) — A7's `Option<T>` / `Result<T, E>` are tagged unions
   following the same discipline.
8. **Per-task `Storage_Size`** informs A7's stack-budget
   annotation per thread (Gap 05).
9. **`pragma Import` discipline** — informs the FFI boundary,
   including the contract-summarisation trust model (Gap 12).
10. **Exhaustive `case`** — Ada has this since the start. A7
    already does it; SPARK's experience confirms it's worth
    enforcing.

## What A7 should not steal

1. **Runtime `Constraint_Error`** — A7 wants compile-time
   discharge or typed returns, never runtime traps.
2. **Exceptions as control flow** — A7 follows SPARK's "no
   exceptions" line; uses `Result<T, E>` instead.
3. **Implicit zero-initialisation for access types** — A7 wants
   uninit to be a hard error.
4. **`pragma Suppress(All_Checks)`** — A7 has no equivalent
   escape hatch.
5. **Ada's tasking model** — Ada's task/protected-object model
   is sophisticated; A7's concurrency story is deferred and will
   pick a simpler shape when added.
6. **Heavyweight contract proof** — A7 stops at refinement-lite;
   full Hoare-style pre/post-conditions are out of scope.

## Where SPARK is ahead of A7's current direction

A7's contract is "zero runtime errors." SPARK's contract is
**"zero runtime errors *plus* functional correctness, when
sufficient annotation is provided"**. SPARK can prove that a sort
function returns a sorted permutation of its input. A7 doesn't
aim that high — the contract is memory safety, not functional
correctness.

This is a deliberate scope choice. The lessons from SPARK that
A7 incorporates are: (a) the technical mechanisms (subtypes,
ownership, flow analysis) work and are tractable; (b) the proof
discipline scales because *most code doesn't need the full
SPARK toolkit*. SPARK's bronze/silver/gold/platinum tiers (where
bronze means "absence of runtime errors only") map directly to
A7's target.
