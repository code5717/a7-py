# Ada deep dive: the whole language as input for A7

Status: Phase B research from before 2026-09-14. Where it conflicts with the
ledger in [`../../plan/decisions.md`](../../plan/decisions.md) or the
[memory plan](../../plan/memory.md), those documents win.

Companion to [`ada.md`](./ada.md), which covers only the 12 safety gaps. The
user asked for this broader study: the whole Ada language, searched for design
ideas A7 should consider.

## Summary

Ada is the longest-running production systems language with strong static types.
It was first standardised in 1983 (Ada 83) and revised in 1995, 2005, 2012 and
2022. It has run avionics, rail signalling, nuclear control and financial
systems for four decades. Many features later adopted elsewhere, including
algebraic types, design by contract, parametric polymorphism, distinct types and
built-in tasks, were in Ada by 1983 or 2012.

This file is organised by feature area, not by gap. Where a feature relates to a
gap in [`../07-language-review.md`](../07-language-review.md), the section says
so. Section 19 maps the features back to the gaps.

The three highest-value ideas are distinct types (I-01), static value
parameters for generics (I-04) and a uniform aspect syntax (I-05).

### About the A7 sketches in this file

Note (2026-09-16): the A7 snippets below are proposals written before the
ledger. None is supported syntax, and several use forms current A7 does not
have: `mod ... end` blocks, `pub`, `let`, colon-indented blocks, the `mod`
operator, `fn name<$T>` and `::` paths. They also use `int`, which L4 removes in
favour of explicit widths, and `inout`, which L6 does not approve. They are kept
as recorded. Current A7 declares items as `name :: ...`, returns with `ret` and
uses braces (see `docs/SPEC.md`).

## Contents

1. Language design overview
2. Strong typing: distinct types and subtypes
3. Packages: Ada's module model
4. Generics
5. Tagged types: object orientation without merging data and behaviour
6. Tasks and protected objects
7. Aspect specifications
8. Aggregates, ranges and literals
9. Iterators and containers
10. Exceptions, and why A7 will not have them
11. Compile-time evaluation and elaboration
12. Representation and layout
13. Library structure and child packages
14. Ravenscar and SPARK subsets
15. Naming and lexical conventions
16. What A7 should adopt
17. What to avoid
18. Open questions Ada can inform
19. Cross-reference to the 12 gaps

## 1. Language design overview

Ada's design pillars have held across every revision:

- Strong typing with named distinct types. `type Meters is new Float;` makes
  `Meters` and `Float` incompatible, and mixing them is a compile error. This
  encourages modelling the domain in types.
- Readability over brevity: keywords, named ends (`end Foo`), explicit type
  names. Verbose by modern standards, but structurally clear.
- Compile-time enforcement wherever possible: constraints, contracts, generic
  parameter restrictions and aspects.
- Explicit failure paths. Ada used exceptions; SPARK uses typed errors only.
  Either way, control flow is visible.
- Hardware awareness: representation clauses, alignment, `pragma Pack` and
  bit-level layouts.
- Concurrency in the language, not a library: tasks and protected objects are
  syntax.

In 1983 Ada decided that nearly every property worth checking should be checked
by the compiler. C made the opposite bet. Rust revived Ada's bet in 2010 and
added affine ownership. A7 is on the same path.

## 2. Strong typing: distinct types and subtypes

### Distinct types

Ada has named distinct types:

```ada
type Celsius is new Float;
type Kelvin  is new Float;

C : Celsius := 20.0;
K : Kelvin  := 293.15;

C := K;  -- compile error: type mismatch (despite both being Float)
```

`new Float` creates a new type with the same representation that the type
system treats as separate. Converting between them takes an explicit conversion,
which becomes part of the type's API:

```ada
function To_Kelvin (X : Celsius) return Kelvin is
  begin return Kelvin (Float (X) + 273.15); end To_Kelvin;
```

### Subtypes and derived types

- `subtype S is T range 1..10;` makes `S` a constrained subtype of `T`. Values
  of `S` are values of `T` with a range constraint. Conversion is implicit in
  both directions.
- `type S is new T range 1..10;` makes `S` a new type derived from `T`, with the
  same operations and a distinct identity. Conversion needs `S(x)` or `T(s)`.

The question "is this a flavour of the type or a new type?" is one of Ada's
sharpest tools. Most languages merge the two.

### For A7

A7 has type aliases (`Handle :: u64`, SPEC section 3.4) but no distinct types.
Earlier text wrote the alias form as `type Foo = i32`; that is not A7 syntax.

This is a real expressiveness gap. Primitive types keep `usize` (lengths),
`isize` (offsets) and `i32` apart, but users cannot declare their own distinct
types.

Proposal: a declaration that produces a distinct type with the same
representation and explicit conversion. Candidate spellings were
`newtype Foo = i32;`, `distinct type Foo = i32;` and `type Foo is new i32;`.

```a7
// Proposed syntax; not supported. Spelling undecided.
RowIndex :: distinct usize
ColIndex :: distinct usize

get :: fn(m: ref Matrix, row: RowIndex, col: ColIndex) f64 {
    ret m.cells[usize(row) * m.cols + usize(col)]
}

// get(m, col, row) is a compile error: ColIndex is not RowIndex
```

Uses in the current codebase:

- `examples/035_matrix.a7`: separate `RowIndex`, `ColIndex` and `usize` would
  catch index mix-ups in the type system.
- `examples/030_calculator.a7`: currencies and units of measurement.
- Compiler internals: `TokenId`, `NodeId` and `TypeId` as distinct types instead
  of bare integers.

Effort: small, about one week. Touches `a7/parser.py`, `a7/types.py` and
`a7/passes/type_checker.py`.

## 3. Packages: Ada's module model

An Ada package has a specification and a body:

```ada
-- Specification (.ads file): public interface
package Stack is
   type Stack_Type is private;
   procedure Push (S : in out Stack_Type; X : Integer);
   function  Pop  (S : in out Stack_Type) return Integer;
private
   type Stack_Type is array (1..100) of Integer;
end Stack;

-- Body (.adb file): implementation
package body Stack is
   procedure Push (S : in out Stack_Type; X : Integer) is
     begin ...; end Push;
   ...
end Stack;
```

Properties:

- The specification and body are separate. Clients see the specification; the
  body is hidden. The build only recompiles dependents when a specification
  changes, not when a body changes.
- The specification has a private section. Items after `private` are visible to
  the compiler, for layout, but not to clients. Ada hides representation this
  way without separate header files.
- Child packages. `package Stack.Logging is ... end;` creates a child that sees
  `Stack`'s private part. Private children (`private package Stack.Internal`)
  are visible only to other `Stack.*` units.

This gives:

- An interface boundary that can be documented and reviewed apart from the
  implementation.
- Build dependency tracking on specifications only.
- Privacy that scales: the parent-child relationship is the unit of trust for
  private parts.

### For A7

A7 modules are single files imported by path, for example
`io :: import "std/io"`. Compared with Ada:

- No specification/body split. Compilation depends on the whole file. A
  specification-only file could speed up parsing if the project grows.
- No private section. Visibility of top-level items is not specified in these
  terms. Ada's `private` section is worth adopting: declare the type publicly and
  put its representation in a section the compiler sees and clients do not.
- No child packages. Worth considering if A7 grows large enough.

Proposal: start with a `private` section and a way to hide a type's
representation:

```a7
mod stack
    pub type Stack          ; type name visible to clients
    pub fn push(s: inout Stack, x: int)
    pub fn pop(s: inout Stack) -> int
private
    type Stack = struct {data: [100]int, top: usize}
end
```

The `private` keyword states plainly that the representation is hidden, without
a separate specification and body. It is the simplest part of Ada's package model
that gives real value.

## 4. Generics

Ada generics are explicit and declaration-based. A generic is a template that
must be instantiated:

```ada
generic
   type Element_Type is private;          -- formal type parameter
   Size : Positive;                       -- formal value parameter
package Bounded_Stack is
   type Stack is private;
   procedure Push (S : in out Stack; X : Element_Type);
   ...
end Bounded_Stack;

-- Instantiation site:
package Int_Stack is new Bounded_Stack (Element_Type => Integer, Size => 100);
```

### Formal parameter kinds

- Formal types with constraints: `type T is private` (any type),
  `type T is range <>` (any integer type), `type T is digits <>` (any float),
  `type T is array (...) of ...`, and others.
- Formal subprograms: `with procedure Compare (X, Y : T)`. The instantiator
  supplies the comparison.
- Formal packages: a generic can take another generic package as a parameter,
  giving higher-order generics.
- Formal values: constants such as `Size : Positive`.

### Signatures

A generic package can act as a signature: a set of names the user must supply,
treated as a structural type. Instantiation must match the signature.

### For A7

A7 has generics with inline `$T` and type sets through `@type_set`. Compared with
Ada:

- Formal types: A7 has them.
- Type-set constraints: roughly equivalent to Ada's `range <>` and similar.
- Formal subprograms: A7 lacks them. Generic code that needs an operation on `$T`
  relies on function resolution or passes a function value by hand.
- Formal values (compile-time `usize` parameters): A7 lacks them. Gap 09
  question Q09b needs them.
- Formal packages: A7 lacks them; less important.

Proposal: an equivalent of formal subprograms:

```a7
fn sort<$T>(arr: inout []$T, cmp: fn($T, $T) -> Ordering)
```

A7 already has function-value parameters, so this is the same mechanism. Ada's
lesson is to declare it as a generic parameter, so the constraint is explicit in
the signature.

Also add `comptime $N: usize` value parameters, needed for
`Bounded<T, lo, hi>`, `Index<n>` and similar.

Note (2026-09-16): function values are under plan gate G4 and memory plan gate
M6. Capture-free function values stay; capturing ones may not escape.

## 5. Tagged types: object orientation without merging data and behaviour

Ada 95 added object orientation through tagged types:

```ada
type Shape is tagged record
   X, Y : Float;
end record;

type Circle is new Shape with record
   Radius : Float;
end record;

function Area (S : Shape) return Float is
  begin return 0.0; end Area;          -- "abstract" base

function Area (S : Circle) return Float is
  begin return 3.14 * S.Radius ** 2; end Area;

-- Class-wide type for polymorphism:
procedure Print (S : Shape'Class) is
  begin Put (Area (S)); end Print;     -- dispatches to Circle.Area for a circle
```

Properties:

- A tagged record stores a tag that identifies its runtime type.
- Primitives of a tagged type are subprograms declared in the same package with
  a parameter of that type. They can dispatch.
- Class-wide types (`T'Class`) are the polymorphic form. Calls through
  class-wide values dispatch.
- No `virtual` keyword. Every primitive of a tagged type dispatches.
- Single inheritance. Ada 2005 interface types give multiple inheritance of
  interfaces.

### For A7

A7 has structs, tagged unions and methods. Methods are ordinary functions with a
receiver parameter such as `self: ref Vec2` (SPEC section 6.5), and calls do not
dispatch. A7 has no inheritance or subtype polymorphism. Earlier text hedged on
whether A7 had methods; SPEC section 6.5 settles it.

Ada's tagged types are a clean model if A7 ever wants inheritance. The more
useful lesson is the separation of data and behaviour:

- A record is data.
- Primitives are subprograms associated with the record by living in the same
  package.
- Dispatch is opt-in through class-wide types, not on every call.

This is the opposite of C++ and Java, where methods live inside the class. In
Ada:

- Composition is the default. Declare a struct and some procedures beside it;
  both are clients of the type.
- Inheritance is opt-in (`tagged` plus `is new T with record ...`).
- Polymorphism is opt-in (`T'Class`).

A7's receiver-parameter functions already follow the Ada model. Adding
inheritance is a major language change and probably not worth it without a clear
use case.

Recommendation: keep the procedural model with tagged unions, and do not add
inheritance. Ada's experience suggests tagged unions plus parametric
polymorphism cover about 95% of what people use object orientation for.

## 6. Tasks and protected objects

Ada is one of the few mainstream languages with threading syntax built in.

### Tasks

```ada
task Worker is
   entry Start (X : Integer);
   entry Done;
end Worker;

task body Worker is
   Local_X : Integer;
begin
   accept Start (X : Integer) do
      Local_X := X;
   end Start;
   -- do work
   accept Done;
end Worker;

-- Caller:
Worker.Start (42);
Worker.Done;
```

- `task` declares a thread. A task type can be instantiated many times.
- `entry` declares a synchronisation point. A call to an entry blocks until the
  task `accept`s it.
- Rendezvous: the caller's `Worker.Start(42)` and the callee's
  `accept Start do ... end` run as one synchronised step.
- `select` lets a task wait for any of several entries, with optional timeout
  and termination.

### Protected objects

```ada
protected type Counter is
   procedure Increment;
   function Value return Integer;
private
   N : Integer := 0;
end Counter;

protected body Counter is
   procedure Increment is
     begin N := N + 1; end Increment;
   function Value return Integer is
     begin return N; end Value;
end Counter;
```

- A protected object wraps data and synchronises access without a separate task.
  The runtime enforces mutual exclusion.
- Protected procedures get exclusive write access, protected functions get
  shared read access, and protected entries block until a guard such as
  `when N > 0` holds.

### Ravenscar profile

Ravenscar is a restricted tasking subset for safety-critical systems. It removes
features that would block static analysis of worst-case execution time and stack
use. DO-178C avionics software uses it.

### For A7

A7 had no concurrency model. When it arrives (gap 10, deferred), Ada is a
benchmark:

- Built-in syntax is worth considering. Library concurrency (Go channels, Rust
  `mpsc`) works, but built-in syntax is clearer for safety analysis.
- Protected objects fit affine ownership well. A protected object owns its data,
  access goes through its primitives, and nothing aliases across tasks. A7's
  ownership gives the same property for single-thread data.
- Avoid rendezvous. It is powerful but surprising; channel message passing is
  simpler.
- Ravenscar is the model for proved-safe concurrency.

Recommendation when concurrency lands: start with channels and owned data. Do not
ship rendezvous or arbitrary task synchronisation. If real-time guarantees are
needed later, use Ravenscar as the reference.

Note (2026-09-16): concurrency is in v1 scope (L1). The memory plan proposes
structured tasks, values moved into tasks, channels with explicit close, and
read-only sharing with child tasks (gates M10, M26, M27, M36). This matches the
channels-plus-owned-data recommendation. Plan gate G7 holds the decision.

## 7. Aspect specifications

Ada 2012 introduced aspect specifications as a uniform attribute system:

```ada
function Sqrt (X : Float) return Float
  with Pre  => X >= 0.0,
       Post => Sqrt'Result * Sqrt'Result >= X - 0.001
            and Sqrt'Result * Sqrt'Result <= X + 0.001;
```

A `with` clause attaches aspects to a declaration. Aspects encode:

- preconditions and postconditions (`Pre`, `Post`)
- type invariants (`Type_Invariant`)
- predicates (`Static_Predicate`, `Dynamic_Predicate`)
- storage (`Storage_Size`, `Storage_Pool`)
- calling convention (`Convention => C`)
- `Inline`, `Pure` and others

Before Ada 2012 these were `pragma` directives. Aspects put them in one form next
to the declaration, which is easier to read.

### For A7

A7's only annotation today is `@type_set(...)`. Ada's aspect model generalises
it:

```a7
fn sqrt(x: f64) -> f64
    with pre  => x >= 0.0,
         post => result * result ~= x
```

`with pre =>` would be a precondition checked at compile time. If it is checkable
it falls under refinement-lite; otherwise it would need a runtime fallback, which
A7's contract rejects.

Recommendation: add a uniform `with attr => value` syntax to replace ad hoc `@`
attributes. At first this changes syntax only. Later attributes (`Pre`, `Post`,
`Pure`, `Inline`, `Repr`) can be added one at a time. Without a uniform form,
each new attribute pulls the syntax in a different direction.

Note (2026-09-16): under L16, `x >= 0.0` does not exclude NaN; a float
precondition would need an explicit NaN rule (plan gate G1).

## 8. Aggregates, ranges and literals

Ada's literal syntax for compound types is unusually expressive:

```ada
-- Array aggregate with named indices and ranges
Days_Per_Month : array (Month) of Integer :=
   (Jan => 31, Feb => 28, Mar => 31, Apr | Jun | Sep | Nov => 30,
    others => 31);

-- Record aggregate
P : Point := (X => 1.0, Y => 2.0);

-- Range expressions
for I in 1 .. 100 loop
   ...
end loop;

for M in Month'Range loop  -- iterates over the enum
   ...
end loop;
```

Features:

- Named association in aggregates (`X => 1.0`), not only positional.
- `others =>` for the default.
- Positional and named association can mix, within rules.
- Ranges as first-class expressions: `1..100`, `Month'Range`,
  `A'First .. A'Last`.

### For A7

A7 has struct literals (`Person{name: "Bob", age: 30}`) and array literals. It
lacks `others =>`, which is worth adding:

```a7
let days = [12]int{ jan: 31, feb: 28, others: 31 }
```

It saves a lot of typing for sparse initialisation. Recommended.

Also worth taking: `Month'Range`, an attribute for "the range of values of this
type". A7's `for i in 0..s.length` is a special case. A general form such as
`for m in Month::range` gives clean enum iteration.

## 9. Iterators and containers

Ada 2012 added generalised iteration:

```ada
for E of Collection loop
   ...
end loop;
```

`of` iterates over elements; `in` iterates over keys. `Ada.Containers.*`
implements this through the `Iterable` aspect.

Ada 2022 added iterator filters:

```ada
for I in 1 .. 100 when I mod 2 = 0 loop
   ...
end loop;
```

### For A7

A7 has `for value in array` and `for i, value in array`. Ada 2022's `when`
filter is a clean addition:

```a7
for i in 0..100 when i mod 2 == 0:
    use(i)
```

It lowers to a normal loop plus `if` and saves one indentation level in the
common case. Worth adding.

## 10. Exceptions, and why A7 will not have them

Ada has exceptions:

```ada
begin
   ...
exception
   when Constraint_Error => ...
   when others           => ...
end;
```

Exceptions are named identifiers that propagate up the call stack until caught.
SPARK forbids them because they break flow analysis. Modern Ada moves toward
typed error returns, `Result`-like records.

A7's contract is zero runtime errors with typed failure only. Exceptions hide
control flow from the type checker; A7 uses `Result<T, E>` (gap 08).

Ada's experience is the main argument: SPARK, the verified subset, has to
exclude exceptions to work. A7 starts from that conclusion.

## 11. Compile-time evaluation and elaboration

Ada separates elaboration, the runtime initialisation of package-level state,
from compile-time evaluation of static expressions.

### Static expressions

Some expressions are always evaluated at compile time:

- integer literal arithmetic
- constants declared as `:= literal_expression`
- `Type'Size`, `Type'First`, `Type'Last`

Static expressions can appear in constraints; for example, subtype range bounds
must be static.

### Elaboration order

Ada 2012 has `pragma Pure`, `pragma Preelaborate`, `pragma Elaborate` and related
pragmas to declare and check elaboration order at compile time. This removes
C++'s static initialisation order problem.

### For A7

A7 folds constants (`ast_preprocessor.py`) but exposes no compile-time or static
concept to users. Ada's model suggests:

- Make "static expression" a type-system concept. A parameter declared
  `static N: usize` needs a static value at instantiation. `Bounded<T, lo, hi>`
  uses it (gap 09).
- Avoid elaboration-order problems by having no package-state initialisation.
  A7 has no initialisers before `main`, so the problem does not arise.

Recommendation: add `static` for generic value parameters (`static N: usize`),
but do not copy Ada's elaboration machinery.

Note (2026-09-16): whether constant expressions are typed or exact is open under
plan gate G3.

## 12. Representation and layout

Ada controls record layout precisely:

```ada
type IP_Header is record
   Version : Integer range 0..15;
   IHL     : Integer range 0..15;
   ...
end record;

for IP_Header use record
   Version at 0 range 0..3;
   IHL     at 0 range 4..7;
   ...
end record;

for IP_Header'Size use 20 * 8;          -- 20 bytes
for IP_Header'Alignment use 4;
```

`for X use ...` clauses, or the aspect form `with ...`, control:

- component placement at bit level
- record size
- alignment
- bit order (`Bit_Order`)

### For A7

A7 has no representation control. For network protocols, file formats and
hardware registers, this is a real gap.

Proposal: a `@repr` attribute on structs:

```a7
@repr(packed, endian: big)
struct IpHeader {
    version: u4,
    ihl: u4,
    ...
}
```

Bit-field types such as `u4` are a separate decision; `@repr` is the framework.

Effort: medium. It brings in bit-field types, layout rules and codegen changes.
Probably defer until after the safety work.

Note (2026-09-16): L4 lists the integer types as `i8`–`i64`, `u8`–`u64`, `isize`
and `usize`, so `u4` would need its own approval. The memory plan chooses
structure-of-arrays layout per type but excludes types that reach native code
(section 4, layer 8); `@repr` types would need the same exclusion.

## 13. Library structure and child packages

Ada organises large libraries as child packages:

```
Ada.Strings           -- parent
Ada.Strings.Maps      -- child
Ada.Strings.Maps.Constants  -- grandchild
Ada.Strings.Unbounded -- another child
```

Children see the parent's private part; clients of the parent see only its
public part. The namespace is hierarchical.

### For A7

A7's standard library has a flat set of modules (`std/io`, `std/math`,
`std/mem`, `std/string`). Hierarchical modules are worth adopting once the
standard library grows past about five modules. The syntax change is small:

```a7
mod std::io
mod std::io::buffered
mod std::io::utf8
```

Import paths are strings such as `"std/io"`, so nested paths may already parse;
this needs checking. If not, the parser change is small.

## 14. Ravenscar and SPARK subsets

Ada is one of few languages with officially defined subsets:

- Full Ada: every feature.
- SPARK: the provable subset, with no exceptions, no aliasing and no unbounded
  recursion.
- Ravenscar: real-time, statically analysable concurrency.

These are not lints. A program declares a profile, for example
`pragma Profile (Ravenscar);`, and the compiler rejects code outside it.

### For A7

A7 is roughly "the SPARK-like subset of an Ada-like language". It could still
use tighter subsets:

- `embedded`: no heap, no recursion (already banned), no foreign code.
- `realtime`: no allocation, no garbage-collector interaction, bounded loops
  only.

A module would declare its profile at the top, and the compiler would enforce
it. Worth doing when a real use case appears. "Declare your discipline and let
the compiler enforce it" is useful even in a language with one profile.

Note (2026-09-16): under L19 users do not see allocations, so a no-heap or
no-allocation profile would have to be checked against the compiler's placement
decisions, which the optional memory report shows (memory plan gate M8).

## 15. Naming and lexical conventions

Ada is case-insensitive: `Foo` and `foo` are the same identifier. Capitalisation
is a style matter:

- `Capitalize_Snake_Case` for identifiers (functions, packages, types) is the
  official style.
- All-caps reserved words are old style; lowercase since Ada 95.
- Underscores are allowed, but not leading, trailing or doubled.

Case insensitivity is a historical mistake that most modern languages avoid.

### For A7

Nothing to take. A7 is case-sensitive (SPEC section 2.3) and should stay so.

Consistent conventions are worth keeping. Earlier text said A7 already uses
`Capitalize_Snake_Case` for types. The SPEC and examples use `PascalCase` for
types (`Node`, `Vec2`) and `snake_case` for functions.

## 16. What A7 should adopt

| # | Feature | Effort | Where in the spec |
| --- | --- | --- | --- |
| I-01 | Distinct types (`newtype Foo = T`) | Small | New section in the design doc |
| I-02 | `private` section in modules | Small | Module system |
| I-03 | Formal subprograms in generics | Small | Generics |
| I-04 | `static N: usize` generic value parameters | Small | Generics |
| I-05 | Uniform aspect syntax for attributes | Medium | Attributes and annotations |
| I-06 | `others =>` in struct and array aggregates | Small | Literals |
| I-07 | `for x in seq when cond` filters | Small | Loops |
| I-08 | Hierarchical modules (`std::io::buffered`) | Small | Modules |
| I-09 | `@repr` for layout control | Medium | Types and foreign code |
| I-10 | Profiles (`@profile(embedded)`) | Medium | Compilation directives |
| I-11 | `Type'Range` or `Type::range` attribute | Small | Built-in attributes |
| I-12 | Subtype and refinement vocabulary (from gap 09) | — | Refinement |

I-01, I-04 and I-05 are the highest-value additions. Each fills a real
expressiveness gap in A7 today, and each is small.

Five of these go beyond the 12 gaps:

- I-01 distinct types improve type safety beyond what the gaps require.
- I-02 `private` sections fill an encapsulation gap.
- I-04 `static` value parameters are a small, real need for gap 09's
  `Bounded<T, lo, hi>`.
- I-05 aspects unify attribute syntax.
- I-10 profiles declare stricter subsets.

These five, plus the 12 safety gaps, were the next language-design
conversation. Phase C was to add them to the decision list, and Phase D to the
specification.

Note (2026-09-16): every item here changes syntax, so each needs the approval
rule in the ledger. Plan gate M15 defers syntax simplification until the memory
model settles.

## 17. What to avoid

| Feature | Why not |
| --- | --- |
| Case-insensitive identifiers | Historical mistake; A7 is already case-sensitive |
| Verbose `procedure` / `function` / `end` syntax | A7's `fn` is shorter |
| Exceptions as control flow | Breaks flow analysis; A7 uses `Result` |
| Package elaboration before `main` | Not needed; complicates initialisation |
| Single-inheritance object orientation with tagged types | Tagged unions and parametric polymorphism cover the cases |
| Rendezvous as a concurrency primitive | Powerful but surprising; channels are simpler |
| `pragma Suppress` | A7 has no equivalent escape hatch |
| Separate specification and body files per module | Adds friction; single-file modules are simpler |
| `'Class` polymorphism (class-wide types) | Same reason as tagged-type object orientation |
| Runtime constraint checks | A7 wants compile-time discharge |

## 18. Open questions Ada can inform

- Q-A. How to write a generic that takes a struct with a specific layout? Ada
  uses constrained formal types. A7 needs a design, possibly type-set
  predicates.
- Q-B. Should A7 have interfaces, like Ada 2005's? Probably not at first.
- Q-C. How to type units of measure (`Meters * Seconds = Meter_Seconds`)?
  Distinct types go part of the way; full unit arithmetic needs more.
- Q-D. How to express function purity (no globals, no foreign calls)? Ada has
  `pragma Pure`; A7 could use an aspect.
- Q-E. Should A7 have assertions (`assert X > 0`)? Ada has `pragma Assert` and
  the `Assertion_Policy` aspect. A7 would treat assertions as compile-time
  obligations, matching the contract.
- Q-F. Conditional compilation. Ada supports it only a little; build systems
  usually handle it. A7 could use build attributes.

## 19. Cross-reference to the 12 gaps

How this study adds context to the gap files in
[`../edge-cases/`](../edge-cases/):

| Gap | Ada feature | Also in `ada.md` |
| --- | --- | --- |
| 01 Cast | Checked conversion versus `Unchecked_Conversion` | Yes |
| 02 Nullable pointers | `not null` | Yes |
| 03 Definite assignment | SPARK flow analysis | Yes |
| 04 NonZero division | Predefined `Positive` and `Natural` subtypes | Yes |
| 05 Stack budget | `Storage_Size` aspect | Yes |
| 06 Typed arithmetic | Ranged subtypes, the core inspiration | Yes |
| 07 Bounded indexing | `'Range`, `'First`, `'Last` | Yes |
| 08 Option and Result | Discriminated records as the failure shape | Yes |
| 09 Refinement-lite | Ada subtypes correspond directly | Yes |
| 10 Affine ownership | SPARK's Rust-inspired ownership model | Yes |
| 11 Finite floats | `'Valid` attribute | Yes |
| 12 FFI | `pragma Import` and convention aspects | Yes |

Note (2026-09-16): gap 06 overflow is settled by wrapping (L5), gap 11 is
withdrawn by IEEE floats (L16), and gap 10 ownership is internal under the
memory plan. See the notes in [`ada.md`](./ada.md).

## Sources

- [Ada Reference Manual 2022](https://www.adaic.org/ada-resources/standards/ada22/)
- [Ada 2012 Rationale (Barnes)](https://www.ada-europe.org/manuals/Rationale_2012.pdf)
- [Learn Ada (AdaCore)](https://learn.adacore.com/)
- [Ada Programming wikibook](https://en.wikibooks.org/wiki/Ada_Programming)
- [SPARK User's Guide](https://docs.adacore.com/spark2014-docs/html/ug/en/)
- [GNAT Reference Manual](https://docs.adacore.com/gnat_rm-docs/html/gnat_rm/)
