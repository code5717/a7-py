# Ada Deep Dive — The Whole Language, Inspirations for A7

> Phase B+ artifact. Companion to [`ada.md`](./ada.md), which covers
> only the 12 safety gaps. This file is the broader research the user
> requested: the whole Ada language, looking for design ideas A7
> should consider adopting.

Ada is the longest-running production-grade strongly-typed systems
language. First standardised in 1983 (Ada 83), revised in 1995, 2005,
2012, and 2022, deployed in avionics, rail signalling, nuclear
control, and financial systems for four decades. Many features that
younger languages "discovered" — algebraic types, design-by-contract,
parametric polymorphism, distinct types, tasks-as-first-class —
were in Ada by 1983 or 2012.

This file walks the language's major design areas and pulls out
inspiration for A7. The unit of organisation is **language feature
area**, not "12 gaps." Where a feature relates to one of the 12 gaps
in `../07-language-review.md`, the cross-reference is noted.

Primary sources:

- [Ada Reference Manual 2022](https://www.adaic.org/ada-resources/standards/ada22/)
- [Ada 2012 Rationale (Barnes)](https://www.ada-europe.org/manuals/Rationale_2012.pdf)
- [Learn Ada (AdaCore)](https://learn.adacore.com/)
- [Ada Programming wikibook](https://en.wikibooks.org/wiki/Ada_Programming)
- [SPARK User's Guide](https://docs.adacore.com/spark2014-docs/html/ug/en/)
- [GNAT Reference Manual](https://docs.adacore.com/gnat_rm-docs/html/gnat_rm/)

---

## Table of contents

1. Language design overview
2. Strong typing — distinct types and subtypes
3. Package system — Ada's module model
4. Generics — parametric polymorphism done right
5. Tagged types — OO without conflating data and behaviour
6. Tasking and protected objects — concurrency primitives
7. Aspect specifications — modern attribute syntax
8. Aggregates, ranges, and literal syntax
9. Iterators and containers
10. Exception handling — and why A7 won't have it
11. Compile-time evaluation and elaboration
12. Representation and layout
13. Library structure and child packages
14. The Ravenscar profile and SPARK subsets
15. Naming and lexical conventions
16. Inspirations for A7 — consolidated
17. What A7 should not take from Ada
18. Open questions Ada experience can help answer

---

## 1. Language design overview

Ada's design pillars are stable across all revisions:

- **Strong typing with named distinct types.** `type Meters is new
  Float;` makes `Meters` and `Float` incompatible. Mixing them is a
  compile error. Encourages domain modelling at the type level.
- **Readability over brevity.** Keywords, named ends (`end Foo`),
  explicit type names. Verbose by modern standards; structurally
  clearer.
- **Compile-time enforcement of as much as possible.** Constraints,
  contracts, generic-parameter restrictions, aspect specifications.
- **Explicit failure paths.** Exceptions originally; SPARK uses
  typed errors only. Either way, control flow is *visible*.
- **Hardware-aware.** Representation clauses, alignment, pragma
  Pack, bit-level layouts.
- **Concurrency as a language feature, not a library.** Tasks and
  protected objects are syntactic.

The contrast with C and Rust is illuminating: Ada decided in 1983
that nearly every property worth checking should be checked by the
compiler. C made the opposite bet. Rust resurrected the Ada bet in
2010 with affine ownership added. A7 is on the same arc.

---

## 2. Strong typing — distinct types and subtypes

### Distinct types

Ada has **named distinct types**:

```ada
type Celsius is new Float;
type Kelvin  is new Float;

C : Celsius := 20.0;
K : Kelvin  := 293.15;

C := K;  -- compile error: type mismatch (despite both being Float)
```

`new Float` *creates a new type*; the underlying representation is
the same, but the type system treats them as separate. To go
between them you write an **explicit conversion** that's part of
the type's API:

```ada
function To_Kelvin (X : Celsius) return Kelvin is
  begin return Kelvin (Float (X) + 273.15); end To_Kelvin;
```

### Subtypes vs derived types

- `subtype S is T range 1..10;` — `S` is a *constrained subtype of
  `T`*. Values of `S` are values of `T` plus a range constraint.
  Implicit conversion both ways.
- `type S is new T range 1..10;` — `S` is a *new type* derived
  from `T` with the same operations but distinct identity.
  Conversion requires explicit `S(x)` or `T(s)`.

This distinction — "is this a *flavour* of the type or a *new*
type?" — is one of Ada's sharpest design tools. Most other
languages collapse the two.

### Inspiration for A7

A7 currently has `type Foo = i32` (alias) and not "distinct types."
This is a real expressiveness gap. Mixing `usize` (lengths) with
`isize` (offsets) and with `i32` (general integers) is currently
controlled only by primitive distinctness; user-defined newtype-style
distinction doesn't exist.

**Proposal:** Add `newtype Foo = i32;` (or `distinct type Foo = i32;`,
or `type Foo is new i32;`) producing a *distinct type* with the
same representation. Conversion is explicit.

Use cases in the existing A7 codebase:

- `examples/035_matrix.a7` — `RowIndex` vs `ColIndex` vs `usize`
  would prevent indexing errors at the type level.
- `examples/030_calculator.a7` — currencies, units of measurement.
- Compiler internals — `TokenId`, `NodeId`, `TypeId` would each
  be a distinct type instead of bare `int`.

Effort: small (~1 week). Touches `a7/parser.py`, `a7/types.py`,
`a7/passes/type_checker.py`.

---

## 3. Package system — Ada's module model

Ada packages have three parts:

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

Key properties:

- **Specification and body separated.** The spec is what clients
  see; the body is hidden. Build systems only need to recompile
  dependents of a spec when the spec changes (not when the body
  changes).
- **Private section in the spec.** Items declared after `private`
  are *visible to the compiler* (for layout decisions) but *not
  to clients*. This is how Ada handles representation hiding
  without separate header files.
- **Child packages.** `package Stack.Logging is ... end;` creates
  a sibling-of-stack that *sees Stack's private part*. Private
  child packages (`private package Stack.Internal is ...`) are
  visible only to other Stack.* siblings.

### What this gives you

- A clear interface boundary you can document and review
  separately from the implementation.
- The compiler can do build-graph dependency tracking on specs
  only.
- Privacy that scales — the parent-child relationship is the
  unit of "trust" for accessing private parts.

### Inspiration for A7

A7's current module model uses one file per module, with
public/private status implicit. Compared to Ada:

- **No spec/body split.** A7 modules are single files.
  Compilation depends on the whole file. **Possibly worth
  changing** if the project grows — a spec-only file declaring
  the module's API would speed up the parse-only stage.
- **No private section.** Items at the top level of an A7
  module are either visible or not based on `pub` (if A7 has
  that) or unspecified. **Worth adopting Ada's `private` section
  syntax**: declare the type publicly with `private` keyword,
  then put the representation in a `private` section that the
  compiler sees but clients can't.
- **No child packages.** A7 currently doesn't have a hierarchy
  of related modules where children see parent's private state.
  **Worth considering** if A7 grows large enough.

**Proposal for A7:** start with adding `private` to module
declarations, and a syntactic equivalent of "this type's
representation is hidden":

```a7
mod stack
    pub type Stack          ; type name visible to clients
    pub fn push(s: inout Stack, x: int)
    pub fn pop(s: inout Stack) -> int
private
    type Stack = struct {data: [100]int, top: usize}
end
```

The `private` keyword is honest about "I'm hiding the
representation" without requiring a separate spec/body split.
This is the simplest piece of Ada's package model that gives
real value.

---

## 4. Generics — parametric polymorphism done right

Ada's generic system is notable for being **explicit and
declaration-based**. A generic is a *template* that must be
*instantiated*:

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

Ada's generics admit a rich palette of formal parameters:

- **Formal types** with constraints: `type T is private` (any
  type), `type T is range <>` (any integer type), `type T is
  digits <>` (any float), `type T is array (...) of ...`, etc.
- **Formal subprograms**: `with procedure Compare (X, Y : T)` —
  the instantiator must provide the comparison.
- **Formal packages**: a generic can take another generic
  *package* as a parameter. This is "higher-order generics."
- **Formal values**: integer constants like `Size : Positive`.

### Signatures

A generic package can serve as a **signature** — a set of names
the user must instantiate, treated as a structural type.
Instantiation matches the signature; the language enforces.

### Inspiration for A7

A7 has generics (`$T`, type sets via `@type_set`). Compared to
Ada:

- **A7 has formal types.** ✅
- **A7 has type-set constraints.** Roughly equivalent to Ada's
  `range <>` etc.
- **A7 doesn't have formal subprograms.** When generic code needs
  to call a method on `$T`, it relies on method resolution (if A7
  has methods) or threads a function pointer manually. Ada's
  formal subprograms are first-class.
- **A7 doesn't have formal values** (`comptime usize` parameters).
  This is what Gap 09 Q09b needs.
- **A7 doesn't have formal packages.** Less critical.

**Proposal:** Add `formal subprogram` analog. Syntax:

```a7
fn sort<$T>(arr: inout []$T, cmp: fn($T, $T) -> Ordering)
```

A7 already has function-pointer parameters, so this is the same
thing — but Ada's discipline of *declaring it as a generic
parameter* makes the constraint explicit at the signature level.

Also: add `comptime $N: usize` for value parameters. Needed for
`Bounded<T, lo, hi>`, `Index<n>`, etc.

---

## 5. Tagged types — OO without conflating data and behaviour

Ada 95 added object-orientation via **tagged types**:

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

Key properties:

- **Tagged record stores a tag** that identifies the runtime type.
- **Primitives** of a tagged type are subprograms declared in the
  same package with a parameter of that type. They are eligible
  for dispatching.
- **Class-wide types** (`T'Class`) are the "polymorphic" form;
  dispatching happens on operations called via class-wide values.
- **No virtual keyword needed.** All primitives of tagged types
  dispatch automatically.
- **Inheritance is single.** Multiple inheritance is achievable
  via interfaces (Ada 2005 added explicit interface types).

### Inspiration for A7

A7 has structs, methods (presumably), and tagged unions, but
**no inheritance** or polymorphism. The Ada tagged-type model is
a clean way to add inheritance if A7 ever wants it.

**The cleaner inspiration**, though, is the **separation of data
and behaviour**. In Ada:

- A *struct* (record) is data.
- *Primitives* are subprograms *associated* with the record by
  being in the same package.
- Dispatching is opt-in via class-wide types, not on every method.

This is the opposite of C++/Java where methods are inside the class.
Ada's model:

- Composition is the default. You declare a struct, declare some
  procedures next to it; both are clients of the type.
- Inheritance is opt-in (`tagged` + `is new T with record ...`).
- Polymorphism is opt-in (`T'Class`).

**Should A7 do anything here?** Mixed view:

- A7 currently has methods (per the spec). If those are
  *dispatching by default*, that's already more C++-like and
  less Ada-like.
- If A7 doesn't have methods, the Ada model (free functions
  organised in packages) is what A7 already does.
- Adding inheritance to A7 is a major language change; **probably
  not worth it** unless a clear use case emerges.

**Recommendation:** stay with the procedural-with-tagged-unions
model. Don't add inheritance. The Ada experience suggests that
tagged unions + parametric polymorphism cover ~95 % of what people
use OO for.

---

## 6. Tasking and protected objects — concurrency primitives

Ada is one of the few mainstream languages with **threading
syntax built into the language**, not provided by a library.

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

Key concepts:

- **`task`** declares a thread. A task type can be instantiated
  many times.
- **`entry`** declares a synchronisation point. Calls to entries
  block the caller until the task `accept`s.
- **Rendezvous**: caller's `Worker.Start(42)` and callee's
  `accept Start do ... end` execute as a single synchronised
  step.
- **Select statement** lets a task wait for any of several
  entries, with optional timeout and termination conditions.

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

Key concepts:

- **Protected objects** encapsulate data and provide synchronised
  access without blocking on a separate task. The runtime
  enforces mutual exclusion.
- **Protected procedures** get exclusive write access; **protected
  functions** get shared read access; **protected entries** block
  until a condition (`when N > 0`) becomes true.

### Ravenscar profile

A restricted subset of Ada's tasking suitable for safety-critical
systems. Disables features that would prevent static analysis of
worst-case execution time and stack usage. Used in DO-178C
aviation software.

### Inspiration for A7

A7 has **no concurrency model today**. When the time comes
(Gap 10, but deferred), the Ada model is a benchmark:

- **Built-in syntax is worth considering.** Library-based
  concurrency (Go-channels, Rust-mpsc) is fine; built-in syntax
  is *clearer* for safety analysis.
- **Protected objects compose with affine ownership beautifully.**
  A protected object owns its data; access is via its primitives;
  no aliasing across tasks. This is the same property A7's
  ownership system provides for single-thread data.
- **Avoid the rendezvous mechanism.** It's powerful but
  surprising; channels-style message passing is simpler.
- **Ravenscar is the model for proved-safe concurrency.**

**Recommendation when concurrency lands:** start with channels
+ owned data. Don't ship rendezvous or arbitrary task
synchronization. If real-time guarantees are needed later, use
Ravenscar as the design reference.

---

## 7. Aspect specifications — modern attribute syntax

Ada 2012 introduced **aspect specifications** as a uniform
attribute system:

```ada
function Sqrt (X : Float) return Float
  with Pre  => X >= 0.0,
       Post => Sqrt'Result * Sqrt'Result >= X - 0.001
            and Sqrt'Result * Sqrt'Result <= X + 0.001;
```

The `with` clause attaches **aspects** to a declaration. Aspects
can encode:

- **Pre/Post conditions** (Pre, Post).
- **Type invariants** (Type_Invariant).
- **Predicates** (Static_Predicate, Dynamic_Predicate).
- **Storage** (Storage_Size, Storage_Pool).
- **Convention** (Convention => C).
- **Inline / Pure / etc.**

Before Ada 2012, these were `pragma` directives. The aspect syntax
unifies them into a declaration-local form that's easier to read.

### Inspiration for A7

A7 has `@type_set(...)` as the one annotation today. The Ada
aspect-specification model is a clean generalisation:

```a7
fn sqrt(x: f64) -> f64
    with pre  => x >= 0.0,
         post => result * result ~= x
```

Where `with pre =>` is a compile-time-checked precondition
(falls under refinement-lite if checkable; falls under runtime
warning otherwise — but A7's contract rejects runtime fallback).

**Recommendation:** add a uniform `with attr => value` attribute
syntax replacing ad-hoc `@`-attributes. This is a syntactic
change with no semantic impact at first; later attributes
(`Pre`, `Post`, `Pure`, `Inline`, `Repr`) can be added one at a
time.

Worth doing because the user-facing syntax for "attributes" is
otherwise pulled in different directions every time a new
attribute is added.

---

## 8. Aggregates, ranges, and literal syntax

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

- **Named association** in aggregates (`X => 1.0`, not just
  positional).
- **`others =>`** for default.
- **Mixed positional/named** allowed within rules.
- **Range expressions** as first-class values: `1..100`,
  `Month'Range`, `A'First .. A'Last`.

### Inspiration for A7

A7 has struct literals (`Person{name: "Bob", age: 30}` per the
spec) and array literals. The `others =>` form is missing and
worth adding:

```a7
let days = [12]int{ jan: 31, feb: 28, others: 31 }
```

Saves a lot of typing for sparse initialisation. **Recommend adopting.**

Also worth importing: `Month'Range` — the *attribute* form for
"the range of values of this type." A7's `for i in 0..s.length`
is the special case; generalising to `for m in Month::range` (or
similar) gives clean enum iteration.

---

## 9. Iterators and containers

Ada 2012 added **generalised iteration**:

```ada
for E of Collection loop
   ...
end loop;
```

`of` iterates over the elements; `in` iterates over the keys.
Containers (Ada's `Ada.Containers.*` library) implement this via
the `Iterable` aspect.

Ada 2022 added **iterator filters and accumulators**:

```ada
for I in 1 .. 100 when I mod 2 = 0 loop
   ...
end loop;
```

### Inspiration for A7

A7 has `for i in 0..n` and `for v in slice`. The Ada 2022
**`when` filter** is a clean addition:

```a7
for i in 0..100 when i mod 2 == 0:
    use(i)
```

Compiles to a regular for + if. Saves indentation in the common
case. **Worth adding.**

---

## 10. Exception handling — and why A7 won't have it

Ada has exceptions:

```ada
begin
   ...
exception
   when Constraint_Error => ...
   when others           => ...
end;
```

Exceptions are *named* (declared as exception identifiers) and
propagate up the call stack until caught. SPARK forbids them
(they break flow analysis). Modern Ada moves toward typed-error
returns (`Result`-like records).

### Why A7 won't have them

A7's contract is zero runtime errors and **typed fallibility
only**. Exceptions hide control flow from the type checker. The
A7 way is `Result<T, E>` (Gap 08).

The Ada experience is *the* argument for this choice: SPARK,
the formally-verified subset, has to exclude exceptions to do
its job. A7 starts from that conclusion.

---

## 11. Compile-time evaluation and elaboration

Ada has a rich notion of **elaboration** — the runtime
initialisation of package-level state — and a separate
**compile-time evaluation** model for static expressions.

### Static expressions

Some expressions are *guaranteed* to be evaluated at compile
time:

- Integer literal arithmetic.
- Constants declared `:= literal_expression`.
- `Type'Size`, `Type'First`, `Type'Last`.

Static expressions are usable in constraint contexts — e.g., the
range bounds of a subtype must be static.

### Elaboration order

Ada 2012 added `pragma Pure`, `pragma Preelaborate`, `pragma
Elaborate`, etc., to specify and check elaboration ordering at
compile time, eliminating the C++ "static initialisation order
fiasco."

### Inspiration for A7

A7 has constant folding (per `ast_preprocessor.py`) but no
explicit comptime/static notion exposed to users. The Ada
*compile-time evaluation surface* is a model:

- **Make "static expression" a real type-system concept.** A
  parameter declared `static N : usize` requires a static value
  at instantiation. Used for `Bounded<T, lo, hi>` (Gap 09).
- **Avoid elaboration ordering issues** by *not* having package
  state initialisation in the first place. A7 has no
  pre-main initialisers; the issue doesn't arise.

**Recommendation:** add a `static` keyword for generic value
parameters (`static N: usize`), but don't replicate the full
Ada elaboration machinery — A7 doesn't need it.

---

## 12. Representation and layout

Ada lets you control struct layout precisely:

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

`for X use ...` clauses (or modern aspect form `with ...`) control:

- **Component placement** (bit-level positions).
- **Size** of the record.
- **Alignment**.
- **Endianness** (`Bit_Order`).

### Inspiration for A7

A7 has no representation control today. For systems work
(network protocols, file formats, hardware registers), this is
a real gap.

**Proposal:** add `@repr` attribute on structs:

```a7
@repr(packed, endian: big)
struct IpHeader {
    version: u4,
    ihl: u4,
    ...
}
```

`u4` etc. as bit-field-sized types is a separate decision; the
`@repr` attribute is the framework.

**Effort:** medium. Pulls in bit-field types, layout
specification, and codegen changes. Probably defer to a
post-safety phase.

---

## 13. Library structure and child packages

Ada has **child packages** for organising large libraries:

```
Ada.Strings           -- parent
Ada.Strings.Maps      -- child
Ada.Strings.Maps.Constants  -- grandchild
Ada.Strings.Unbounded -- another child
```

Children see parent's private parts; clients of the parent see
only its public part. The library namespace is hierarchical.

### Inspiration for A7

A7 currently has a flat module namespace (`std/io`, `std/math`).
**Worth adopting** Ada-style hierarchical modules when the stdlib
grows beyond ~5 modules. Easy syntactic addition:

```a7
mod std::io
mod std::io::buffered
mod std::io::utf8
```

Already supported syntactically? Worth verifying. If not, a
trivial parser extension.

---

## 14. The Ravenscar profile and SPARK subsets

Ada is **one of the few languages** that has *officially-defined
subsets* for different use cases:

- **Full Ada**: all features.
- **SPARK**: provable subset (no exceptions, no aliasing, no
  unbounded recursion).
- **Ravenscar**: real-time, statically-analysable concurrency.

These subsets are not "lints"; they're declared at the program
level via `pragma Profile (Ravenscar);` and the compiler refuses
to compile programs that step outside.

### Inspiration for A7

A7 itself is essentially "the SPARK-like subset of an Ada-like
language." But A7 could benefit from a similar idea for *tighter*
subsets:

- **`embedded`** — no heap, no recursion (already), no FFI.
- **`realtime`** — no allocation, no GC interactions, bounded
  loops only.

These would be *profiles* the user declares at the top of a
module, restricting what the file is allowed to do. The compiler
enforces.

**Worth doing** when there's a real use case. The pattern of
"declare your discipline; compiler enforces" is good even for
a single-profile language.

---

## 15. Naming and lexical conventions

Ada is case-insensitive (`Foo` and `foo` are the same identifier),
which is unusual. Capitalisation conventions are *style*:

- `Capitalize_Snake_Case` for identifiers (functions, packages,
  types). The official Ada style.
- All-caps reserved words: deprecated; lowercase since Ada 95.
- Underscores allowed but not at start/end or doubled.

The case-insensitivity is a *historical mistake* most modern
languages avoid.

### Inspiration for A7

None — A7 is case-sensitive. Keep it that way.

What's worth borrowing is the *uniformity of conventions* —
`Capitalize_Snake_Case` for types, `snake_case` for functions,
`SCREAMING_SNAKE_CASE` for constants. A7 already does this.

---

## 16. Inspirations for A7 — consolidated

Picking the highest-leverage Ada features for A7:

| # | Feature | Effort | Where in spec? |
| --- | --- | --- | --- |
| I-01 | **Distinct types** (`newtype Foo = T`) | Small | New section in design doc |
| I-02 | **`private` section** in modules | Small | Module system |
| I-03 | **Formal subprograms** in generics | Small | Generics |
| I-04 | **`static N: usize`** generic value parameters | Small | Generics |
| I-05 | **Aspect specifications** uniform attribute syntax | Medium | Attribute / annotation |
| I-06 | **`others =>` in struct/array aggregates** | Small | Literals |
| I-07 | **`for x in seq when cond`** filter syntax | Small | Loops |
| I-08 | **Hierarchical modules** (`std::io::buffered`) | Small | Modules |
| I-09 | **`@repr` for layout control** | Medium | Types / FFI |
| I-10 | **Profiles** (`@profile(embedded)`) | Medium | Compilation directives |
| I-11 | **`Type'Range` / `Type::range` attribute** | Small | Built-in attributes |
| I-12 | **Subtype / refinement vocabulary** (already from Gap 09) | — | Refinement |

Of these, **I-01 (distinct types), I-04 (static value generics),
and I-05 (aspect specifications)** are the three highest-leverage
additions. They each address a real expressiveness gap in A7
today and each is small.

---

## 17. What A7 should not take from Ada

| Feature | Why not |
| --- | --- |
| Case-insensitive identifiers | Historical mistake; A7 already case-sensitive |
| Verbose `procedure`/`function`/`end` syntax | A7's `fn` is cleaner |
| Exceptions as control flow | Breaks flow analysis; A7 uses `Result` |
| Pre-main package elaboration | Not needed; complicates initialisation |
| Tagged-type single-inheritance OO | Tagged unions + parametric polymorphism cover the cases |
| Rendezvous as concurrency primitive | Powerful but surprising; channels are simpler |
| `pragma Suppress` | A7 has no equivalent escape hatch |
| Multiple-file spec/body split per module | Adds friction; A7's single-file modules are simpler |
| `'Class` polymorphism (class-wide types) | Same reason as tagged-type OO |
| Runtime constraint checking | A7 wants compile-time discharge |

---

## 18. Open questions Ada experience can help answer

These are open in A7's design and Ada has *some* answer worth
considering:

- **Q-A.** How to express "a generic that takes a struct with
  a specific layout"? Ada: formal types with constraints. A7:
  needs design — possibly type-set predicates.
- **Q-B.** Should A7 have **interfaces** (Ada 2005's analog of
  Java interfaces)? Probably not initially.
- **Q-C.** How to express *unit-of-measure* style typing
  (`Meters * Seconds = Meter_Seconds`)? Ada's distinct types
  get you part of the way; full unit-aware arithmetic requires
  more.
- **Q-D.** How to express *purity* of a function (no globals,
  no FFI)? Ada's `pragma Pure`. A7 could use an aspect.
- **Q-E.** Should A7 have **assertions** (`assert X > 0`)? Ada
  has `pragma Assert` and aspect `Assertion_Policy`. A7 would
  treat asserts as compile-time obligations (matches the contract).
- **Q-F.** Conditional compilation. Ada has limited support;
  most build systems handle it externally. A7 could use a
  build-attribute system.

---

## 19. Cross-reference back to the 12 gaps

Where this deep-dive adds context to the gap-specific files in
`../edge-cases/`:

- **Gap 01 cast** — Ada's `Conversion` / `Checked_Conversion` /
  `Unchecked_Conversion` split (also covered in `ada.md`).
- **Gap 02 nullable pointers** — Ada's `not null` syntax (also
  in `ada.md`).
- **Gap 03 definite assignment** — SPARK's flow analysis (also
  in `ada.md`).
- **Gap 04 NonZero division** — Ada's predefined `Positive` and
  `Natural` subtypes (also in `ada.md`).
- **Gap 05 stack budget** — Ada's `Storage_Size` aspect.
- **Gap 06 typed arithmetic** — Ada's ranged subtypes — the
  fundamental inspiration.
- **Gap 07 bounded indexing** — Ada's `'Range`, `'First`, `'Last`
  attributes.
- **Gap 08 Option/Result** — Discriminated records as the
  fallibility shape.
- **Gap 09 refinement-lite** — Ada subtypes directly correspond.
- **Gap 10 affine ownership** — SPARK's Rust-inspired ownership
  model (also in `ada.md`).
- **Gap 11 finite floats** — Ada's `'Valid` attribute.
- **Gap 12 FFI** — Ada's `pragma Import` and convention
  attributes.

This file's **additional contributions beyond the 12 gaps**:

- **Distinct types** (I-01) — a brand-new feature for A7 that
  improves type safety beyond what the 12 gaps require.
- **`private` section in modules** (I-02) — addresses an
  encapsulation gap not in the 12.
- **Aspect specifications** (I-05) — a syntactic unification of
  attributes.
- **Profiles** (I-10) — a tool for declaring stricter subsets.
- **The `static` keyword** (I-04) — a small but real need for
  Gap 09's `Bounded<T, lo, hi>`.

These five additions, plus the 12 safety gaps, are the next
language-design conversation. Phase C should incorporate them
into the decision list; Phase D into the spec.
