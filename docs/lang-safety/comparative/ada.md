# Comparative: Ada and SPARK

Status: Phase B research from before 2026-09-14. Where it conflicts with the
ledger in [`../../plan/decisions.md`](../../plan/decisions.md) or the
[memory plan](../../plan/memory.md), those documents win.

Companion to the Phase A edge-case files in [`../edge-cases/`](../edge-cases/)
and to the whole-language study [`ada-deep-dive.md`](./ada-deep-dive.md).

## Summary

Ada is at revision Ada 2022, and Ada 2012 is widely deployed. With its formally
verified subset SPARK 2014+, it is the industrial reference for static memory
safety in systems programming. Ada had ranged subtypes, definite assignment,
design-by-contract aspects and exhaustive `case` statements decades before
mainstream languages named them.

SPARK takes the part of Ada that can be proved statically. Since SPARK 2018 it
adds a Rust-inspired ownership model for access types. It proves absence of
runtime errors for the verified subset, which was A7's target.

This file walks the 12 gaps from
[`../07-language-review.md`](../07-language-review.md).

## Per-gap findings

### Gap 01: Cast

Ada separates checked type conversion (`Integer(X)`) from unchecked conversion
(`Ada.Unchecked_Conversion`):

```ada
-- Numeric conversions are checked
Y : Integer := Integer(X);  -- may raise Constraint_Error

-- Unchecked reinterpretation is opt-in
function To_Int is new Ada.Unchecked_Conversion (
    Source => My_Float, Target => Integer);
```

Reinterpreting a pointer as an integer needs `Ada.Unchecked_Conversion`
explicitly. SPARK forbids `Ada.Unchecked_Conversion` because it cannot be
analysed statically, unless a precondition the prover discharges wraps it.

- Adopt: a named operator for each kind of conversion. A7's proposed `cast` /
  `truncating_cast` / `bit_cast` split follows Ada's split between checked
  conversion and `Unchecked_Conversion`. The unchecked form is flagged and
  forbidden in the proved subset.
- Avoid: checked numeric conversion that raises `Constraint_Error` at run time.
  A7 requires compile-time discharge or an optional return.

Note (2026-09-16): the cast vocabulary is open under plan gate G3, including
the D.024/D.038 contradiction. Earlier text called the Ada family
"`Conversion` / `Checked_Conversion` / `Unchecked_Conversion`"; only
`Ada.Unchecked_Conversion` is a named Ada unit in the examples above.

### Gap 02: Nullable pointers

Ada access types are nullable by default. Ada 2005 added `not null` as a subtype
constraint:

```ada
type Acc is access Integer;            -- nullable
subtype Non_Null_Acc is not null Acc;  -- non-null

procedure Foo (X : not null Acc);      -- non-null parameter
```

Every access variable starts as `null`, so an uninitialised pointer is a null
pointer, never an undefined one. SPARK enforces `not null` wherever it is
declared and rejects assigning `null` to such a variable.

- Adopt: the non-null constraint, inverted. A7's `ref T` is non-null by default
  and `?ref T` is the opt-in nullable form. Ada shows non-null parameters are
  usable.
- Avoid: nullable by default.

Note (2026-09-16): the memory plan makes `ref` parameter-only and replaces `nil`
with optionals over values (gates M4, M6). There is no planned `?ref T`.

### Gap 03: Definite assignment

Ada initialises access types to `null` (gap 02) and initialises most other
declarations where they are declared. Reading an uninitialised non-access
variable is a bounded error: the compiler may supply a value, or the program may
raise `Program_Error`.

SPARK adds flow analysis: every variable must be initialised before use.
`gnatprove` reports a flow error for any read of an uninitialised variable.

```ada
procedure Bad is
   X : Integer;
begin
   Put (X);  -- SPARK: error, X may not be initialised
end Bad;
```

SPARK flow analysis also tracks `Global` (data a subprogram reads and writes)
and `Depends` (which inputs affect which outputs). A7's definite-assignment pass
is a strict subset of it.

- Adopt: SPARK's flow-analysis approach for all types, not just access types.
  Reject reads before initialisation instead of silently initialising.
- Avoid: implicit `null` initialisation for access types.

The memory plan keeps this direction: reading a variable no path initialised is
rejected (gate M34).

### Gap 04: NonZero division

Ada raises `Constraint_Error` on division by zero. SPARK proves absence of
division by zero through a precondition:

```ada
function Divide (A, D : Integer) return Integer
  with Pre  => D /= 0,
       Post => Divide'Result = A / D;
```

The prover discharges `Pre` at every call site. A literal divisor such as `5`
discharges trivially. An opaque divisor needs the caller to have proved
`D /= 0`, usually through its own subtype.

A common pattern defines a subtype that excludes zero:

```ada
subtype Nonzero_Int is Integer range -Integer'Last .. Integer'Last
   with Static_Predicate => Nonzero_Int /= 0;

function Divide (A : Integer; D : Nonzero_Int) return Integer is
  begin return A / D; end Divide;
```

- Adopt: the subtype approach. A7's `NonZero<T>` is Ada's `Nonzero_Int` made
  explicit, with a constructor that returns an optional instead of raising
  `Constraint_Error`.
- Avoid: runtime constraint checks.

```a7
// Proposed syntax; not supported
average :: fn(total: i64, count: NonZero(i64)) i64 {
    ret total / count.value
}

main :: fn() {
    n: i64 = 4
    maybe_count := NonZero(i64).new(n)   // ?NonZero(i64); none when n is 0
    if count := maybe_count {
        avg := average(100, count)
    }
}
```

Note (2026-09-16): L5 does not decide division. Integer division rules,
including signed `MIN / -1`, are open under gate G3. L16 implies float division
needs no divisor proof; removing that proof is still to decide under gate G1.

### Gap 05: Stack budget

Ada has the `Storage_Size` aspect for tasks:

```ada
task type Worker
  with Storage_Size => 65_536;
```

Ada does not compute stack budgets statically; the user sizes each task. SPARK
does not guarantee absence of stack overflow either, although `gnatstack`
analyses stack use after compilation.

- Adopt: the per-thread annotation idea. A7's `--stack-budget` flag extends it
  to the whole program, using the no-recursion rule.
- Avoid: relying on the user to pick the number. A7 computes the budget from the
  call graph; user overrides are rare.

### Gap 06: Typed arithmetic with range tracking

Ranged subtypes are Ada's strongest feature. The type system encodes integer
bounds:

```ada
subtype Buffer_Size is Natural range 0 .. 1023;
B : Buffer_Size := 100;
B := B + 1000;  -- raises Constraint_Error at runtime
                 -- SPARK rejects at compile time
```

Predefined subtypes:

- `Natural` is `Integer range 0 .. Integer'Last`.
- `Positive` is `Integer range 1 .. Integer'Last`.

Ada 2012 subtypes can carry static predicates:

```ada
subtype Even is Integer with Static_Predicate => Even mod 2 = 0;
```

SPARK proves absence of overflow by tracking subtype constraints through
arithmetic. For `X : Positive`, the result of `X + 1` must still satisfy
`Positive`. When the prover cannot show this, the check becomes a verification
condition the user must prove or refactor away.

- Adopt: the ranged-subtype model. A7's proposed `Bounded<T, lo, hi>`,
  `Index<n>`, `NonZero<T>`, `Positive<T>` and `Natural<T>` (gap 09) translate it
  directly. SPARK's discharge by static predicate is what A7's pattern
  recognition attempts.
- Avoid: runtime constraint checks. Ada inserts them by default and SPARK proves
  them away. A7 goes straight to the proof. Anything unprovable must be
  rewritten, for example with `checked_add`, not checked silently at run time.

Note (2026-09-16): ordinary `+`, `-`, `*` now wrap (L5), so overflow no longer
needs a range proof or `checked_add`. Proofs remain for division, casts, shifts
and sizes (gate G3).

### Gap 07: Bounded indexing

Ada array indices use ranged subtypes:

```ada
type Buffer is array (Natural range 0 .. 1023) of Octet;
B : Buffer;
B (i) := 0;  -- i must be in 0..1023
```

The index type encodes the bounds. A statically out-of-range index is a compile
error; otherwise an out-of-range index raises `Constraint_Error`.

For dynamic indices, Ada provides `'First`, `'Last` and `'Range`:

```ada
for I in B'Range loop
   B (I) := Compute (I);  -- I provably in B'Range
end loop;
```

SPARK proves every index is in range.

- Adopt: `'Range` corresponds to A7's `for i in 0..s.length: s[i]` pattern.
  Carrying the bound in the index type is the basis of A7's `Index<n>`.
- Avoid: the runtime `Constraint_Error` fallback. A7 requires the proof.

A7's indexed loop form gives the proof without extra annotation:

```a7
// Proposed pattern in current loop syntax; not compile-checked
fill :: fn(buf: ref [16]u8) {
    for i, value in buf {
        buf[i] = 0      // i: usize, always in range
    }
}
```

### Gap 08: Option and Result

Ada has no built-in option or result type. Its standard failure mechanism is
exceptions:

```ada
function Lookup (Key : K) return V;  -- raises Not_Found
```

SPARK forbids exceptions as control flow because they break flow analysis. SPARK
code uses one of two shapes:

- A status plus an `out` parameter:
  `procedure Lookup (Key : K; Value : out V; Found : out Boolean)`.
- A discriminated record, Ada's tagged union:

```ada
type Result_T (Ok : Boolean := False) is record
  case Ok is
    when True  => Value : V;
    when False => Error : E;
  end case;
end record;
```

- Adopt: the discriminated record is the same shape as `Result<T, E>`. SPARK's
  finding that exceptions do not compose with flow analysis is the reason A7
  uses `Result` instead of exceptions.
- Avoid: exceptions as a fallback. Every failure must be typed.

### Gap 09: Refinement-lite types

Ada subtypes are refinement-lite types. The predicate vocabulary:

- `Static_Predicate`: checkable at compile time.
- `Dynamic_Predicate`: checked at run time.
- Range constraint: a special case of a static predicate.
- `'Valid`: checks that a value's representation is valid.

```ada
subtype Even is Integer with Static_Predicate => Even mod 2 = 0;
subtype Positive_Square is Natural
  with Dynamic_Predicate => Positive_Square = Ada.Numerics.Elementary_Functions.Sqrt
                                                 (Float (Positive_Square)) ** 2;
```

SPARK restricts predicates to those that do not depend on runtime input, so they
can be discharged statically.

- Adopt: a closed vocabulary (`Natural`, `Positive`, ranged subtypes) with a
  constructor as the only entry point. A7's
  `Bounded<T, lo, hi>::new(x) -> ?Bounded<T, lo, hi>` is that entry point; in
  Ada, assignment triggers the constraint check.
- Avoid: runtime predicate checks. A7 admits only predicates the prover can
  discharge, following SPARK's static-predicate restriction.

### Gap 10: Affine ownership

SPARK 2018 adopted an ownership model for access types, inspired by Rust:

- Assignment between access objects is a move. The source loses permission; the
  destination gains it.
- Read-only sharing is allowed: several aliases that only read.
- Read-write access needs exclusive ownership: one active reference.
- Pool-specific access types point only at heap data; stack pointers are
  forbidden.
- Deallocation transfers ownership to the deallocator; later use is a flow
  error.

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
extends the model to linked lists and trees, the hardest cases.

- Adopt: the whole model. SPARK's move semantics on access types is the closest
  production example of the affine ownership A7 needs. It is proved at compile
  time with no runtime cost, and its ergonomics are workable.
- Avoid: Ada's unrestricted access types, which remain available outside the
  proved subset. A7 requires the strict form everywhere.

A7 was also to take Hylo-style parameter modes (gap 10, question Q10a), which
Ada lacks, to avoid storable references entirely.

Note (2026-09-16): the memory plan keeps SPARK's compile-time checks but hides
them. Ownership is internal; assignment copies, and the compiler removes copies
only when unobservable (contract item 4). Users never write `new` or `del`
(gate M3). Exclusivity and non-storable `ref` survive as the only visible rules
(contract items 8.1 and 8.3). No parameter-mode syntax is approved (L6).

### Gap 11: Finite floats

Ada has `Float`, `Long_Float` and `Long_Long_Float`. The `'Valid` attribute
checks that a scalar is in its subtype's range. On most implementations it also
rejects NaN and infinity:

```ada
if X'Valid then
   -- X is finite (on most implementations)
   ...
end if;
```

Ada has no `Fin<F>` refinement; the user checks `'Valid` at the boundary.
SPARK's prover tracks `'Valid` through flow.

- Adopt: `'Valid` is the runtime form of A7's `Fin::new`. Both guard NaN and
  infinity at boundaries.
- Avoid: the runtime form. A7 puts `Fin<F>` in the type.

Note (2026-09-16): superseded by L16. A7 floats follow IEEE 754 as in Zig and C;
NaN and infinity are ordinary values, and `Fin<F>` is withdrawn (plan gate G1).

### Gap 12: FFI

Ada has rich foreign-function support:

```ada
function malloc (Size : size_t) return System.Address
  with Import, Convention => C, External_Name => "malloc";
```

`pragma Convention(C, ...)` controls calling convention and record layout.
`pragma Import` declares foreign symbols; `pragma Export` exposes Ada symbols.

SPARK summarises imported functions by their contracts (`Pre`, `Post`, `Global`,
`Depends`) and trusts those contracts. The user must get them right.

- Adopt: an explicit boundary. A7's `extern fn ... -> Result<T, E>` rule is a
  SPARK summary with a mandatory typed return. The trust model is the same.
- Avoid: Ada's pragma syntax. A7 uses attributes consistent with the rest of the
  language.

Note (2026-09-16): the memory plan adds native descriptors that declare
borrowing, retention and returned storage (gate M12).

## What A7 should adopt

1. Ranged subtypes as the base of the refinement system (gaps 06, 07, 09). The
   `Bounded<T, lo, hi>`, `Index<n>`, `Natural<T>` and `Positive<T>` vocabulary
   ports directly.
2. SPARK's static-predicate restriction: allow only predicates the prover can
   discharge.
3. Named conversions, informing the `cast` / `truncating_cast` / `bit_cast`
   split (gap 01; open under G3).
4. `not null` access types, informing non-null references with the default
   flipped (gap 02; see the gap 02 note).
5. SPARK flow analysis, informing definite assignment and move analysis as one
   control-flow pass (gaps 03, 10).
6. SPARK's ownership model for access types, the production reference for
   compile-time affine ownership (gap 10; now internal, see the gap 10 note).
7. Discriminated records as the failure shape (gap 08). A7's `Option` and
   `Result` are tagged unions with the same discipline.
8. Per-task `Storage_Size`, informing a per-thread stack budget (gap 05).
9. `pragma Import` discipline and contract-summary trust for foreign code
   (gap 12).
10. Exhaustive `case`. Ada has always had it; A7 already enforces it, and
    SPARK's experience confirms the value.

## What to avoid

1. Runtime `Constraint_Error`. A7 wants compile-time discharge or typed returns,
   never runtime traps.
2. Exceptions as control flow. A7 follows SPARK and uses `Result`.
3. Implicit `null` initialisation for access types. Uninitialised reads are hard
   errors.
4. `pragma Suppress(All_Checks)`. A7 has no such escape hatch.
5. Ada's tasking model. It is sophisticated; A7 will pick a simpler shape when
   concurrency is added.
6. Heavyweight contract proof. A7 stops at refinement-lite; full Hoare-style
   preconditions and postconditions are out of scope.

Note (2026-09-16): on item 1, the memory plan permits listed residual runtime
checks with defined outcomes, such as `Id(T)` lookup and allocation failure
(section 6, gate M16). None of them is an unhandled trap. On item 5, the memory
plan proposes structured tasks and channels (gates M10, M26, M27).

## Where SPARK is ahead of A7

A7's contract is zero runtime errors. SPARK's contract is zero runtime errors
plus functional correctness when enough annotation is provided. SPARK can prove
that a sort returns a sorted permutation of its input. A7 does not aim for
functional correctness; its contract is memory safety.

This is a deliberate scope choice. A7 takes two lessons from SPARK:

- The mechanisms (subtypes, ownership, flow analysis) work and are tractable.
- The proof discipline scales because most code does not need the full SPARK
  toolkit.

SPARK's bronze, silver, gold and platinum levels map to this. Bronze, absence of
runtime errors only, corresponds to A7's target.

## Sources

- [Ada Reference Manual (ARM 2022)](https://www.adaic.org/ada-resources/standards/ada22/)
- [SPARK Reference Manual](https://docs.adacore.com/spark2014-docs/html/lrm/)
- [SPARK User's Guide](https://docs.adacore.com/spark2014-docs/html/ug/en/)
- [Learn Ada (AdaCore)](https://learn.adacore.com/)
- [Learn Ada: Intro](https://learn.adacore.com/courses/intro-to-ada/)
- [Learn Ada: Advanced](https://learn.adacore.com/courses/advanced-ada/)
- [Memory Safety in Ada and SPARK (AdaCore blog)](https://www.adacore.com/blog/memory-safety-in-ada-and-spark-through-language-features-and-tool-support)
- [Pointer Support, Ownership, and Dynamic Memory Management (SPARK UG section 5.9)](https://docs.adacore.com/spark2014-docs/html/ug/en/source/access.html)
- [Recursive Data Structures in SPARK (Dross et al., 2020)](https://link.springer.com/chapter/10.1007/978-3-030-53291-8_11)
- [Type Contracts in SPARK](https://docs.adacore.com/spark2014-docs/html/ug/en/source/type_contracts.html)
- [Subprogram Contracts in SPARK](https://docs.adacore.com/spark2014-docs/html/ug/en/source/subprogram_contracts.html)
