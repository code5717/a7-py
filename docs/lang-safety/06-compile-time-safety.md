# 06 — Compile-time Safety Techniques

> Status: research catalog written before 2026-09-14, audited 2026-09-16. It
> describes techniques, not A7 decisions. Current decisions are in
> [`docs/plan/decisions.md`](../plan/decisions.md).

> Part of the `docs/lang-safety/` series. See the [README](./README.md) for the
> full map. Siblings: [01 — InvisiCaps](./01-invisicaps.md) ·
> [02 — Sanitizers](./02-sanitizers.md) ·
> [03 — Hardware-assisted safety](./03-hardware.md) ·
> [04 — Comparison](./04-comparison.md) ·
> [05 — Take-aways for A7](./05-for-a7.md).

This file catalogs techniques that catch memory-safety bugs **at compile time**,
before the program runs. They are the only techniques that give a guarantee
rather than a probability of detection, and the only ones with zero runtime CPU
cost.

Sections are ordered roughly by the type-system machinery each technique needs,
from cheapest to most expressive.

| # | Technique | Catches | Language complexity | User effort |
| --- | --- | --- | --- | --- |
| 1 | Definite-assignment / flow analysis | Uninitialized reads, missing return | Tiny | None |
| 2 | Non-null pointer types | Null deref | Tiny | Annotations on optional cases |
| 3 | Sum types + exhaustive match | Type confusion, missed enum case | Small | Pattern matches |
| 4 | Linear / affine types | Use-after-free, double-free, leak | Small | Move semantics |
| 5 | Borrow checking + lifetimes | UAF + aliasing under shared mutation | Large | Lifetime annotations (often inferred) |
| 6 | Region inference | UAF for stack-shaped lifetimes | Medium | Region annotations at function signatures |
| 7 | Generational references | UAF (mostly elided at compile time) | Small | None, but one runtime check remains on cold paths |
| 8 | Mutable value semantics | UAF + aliasing without lifetime annotations | Medium | `inout` parameter mode |
| 9 | Reference capabilities | UAF + races without GC | Medium | Capability annotations on types |
| 10 | Refinement types | Bounds, overflow, arbitrary predicates | Large | Predicate annotations + SMT |
| 11 | Dependent types | Anything provable | Very large | Proofs |
| 12 | Effect systems | IO/alloc/exception purity, ordering | Medium | Effect annotations |
| 13 | SPARK / proved subset | Every specified property, when fully applied | Very large | Contracts (pre/postconditions) |
| 14 | Comptime / staged metaprogramming | Whatever can be computed at compile time | Medium | None; comptime is opt-in |

Each section covers the bug class, the mechanism, an example, languages that ship
it, and the cost to the implementer. Most sections end with a note on A7.

Code blocks marked "Proposed (pseudocode)" use an older A7-like notation (`fn ... end`,
`int`, `;` comments). They illustrate the technique and are not A7 syntax.
Blocks marked "Current A7" were checked with
`python main.py --mode pipeline` on 2026-09-16.

---

## 1. Definite-assignment / flow analysis

**Catches:** reads of an uninitialized local, falling off the end of a non-`void`
function, and use of a variable in a branch where it is not assigned.

**Mechanism.** Walk the CFG. For each variable, compute the program points where
it is definitely assigned. A read at any other point is a compile error.

```text
Proposed (pseudocode)
fn f(c: bool) -> int
    x: int            ; not yet assigned
    if c
        x = 1
    end
    return x          ; compile error: x not definitely assigned on c=false
end
```

It is a standard data-flow pass over the AST or basic blocks. Languages: **Java**,
**C#**, **Kotlin**, **Rust**, **Swift**, **Zig**, **Go** (return paths).

**Cost.** A few hundred lines in the type checker. No user annotations.

> Note (2026-09-16): A7 does not have this analysis yet. The program below is
> accepted today. The memory plan proposes rejecting such reads with no implicit
> zero initialization (gate M34), not yet approved.

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

---

## 2. Non-null pointer types

**Catches:** null-pointer dereference. The original text claimed this is roughly
30 % of remotely exploitable CVEs in C/C++ code; no source was given.

**Mechanism.** Split the pointer type in two:

- `T*` (non-null): built only by allocation or by a checked conversion from a
  nullable. Always safe to dereference.
- `T?` (nullable): must be pattern-matched or unwrapped before use.

```text
Proposed (pseudocode)
fn first(xs: []T) -> T?
    if xs.length == 0 then return null end
    return xs[0]          ; coerces T → T?
end

fn use(xs: []T)
    match first(xs)
        case some(v): print v
        case null:    print "empty"
    end
end
```

Languages: **Kotlin**, **Swift**, **TypeScript strict**, **C# 8+ NRT**, **Rust**
(`Option<T>` rather than a special pointer variant), **Zig** (`?T`), **Pony**.

**Cost.** One bit in the pointer type and one narrowing rule in the type checker.
A large gain for a small language.

> Note (2026-09-16): A7's `ref T` is still nullable, but the safety pass requires
> a non-nil proof before field access through a reference
> (`a7/safety.py:610-630`). `docs/SAFETY_CONTRACT.md` plans a `ref T` /
> optional `ref T` split. The memory plan replaces `nil` references with
> optionals (not yet approved).

```a7
// Current A7: accepted; without the nil check, `c.value` is rejected
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

---

## 3. Sum types + exhaustive pattern matching

**Catches:** type confusion through untagged unions, and forgotten enum cases.

**Mechanism.** A `union` (sum, variant, ADT) is tagged: its runtime
representation carries a discriminator. The type checker requires every `match`
to cover all variants or have a wildcard.

```text
Proposed (pseudocode)
type Shape = circle{r: f64} | rect{w: f64, h: f64}

fn area(s: Shape) -> f64
    match s
        case circle{r}:  return 3.14159 * r * r
        case rect{w, h}: return w * h
        ; compile error if a new variant is added and forgotten here
    end
end
```

Languages: **OCaml**, **Haskell**, **Rust**, **Swift**, **Scala**, **TypeScript**
(discriminated unions).

**Cost.** Match-coverage checking is a standard algorithm (Maranget, "Warnings for
Pattern Matching"). Modest.

The original text said A7 already has tagged unions (`docs/SPEC.md`), so only
exhaustiveness needed checking.

> Note (2026-09-16): partly stale. A7 checks exhaustiveness for `bool` and enum
> scrutinees (`a7/passes/type_checker.py:2685-2705`; error
> `NON_EXHAUSTIVE_MATCH`). SPEC also documents untagged unions, and tagged-union
> tag inspection is reserved syntax that is not implemented
> (`docs/SPEC.md:329-350`).

---

## 4. Linear / affine types

**Catches:** use-after-free, double-free, leaked resources, double-send.

**Mechanism.** A linear value must be consumed exactly once; an affine value at
most once. After a value is used by a destructive operation such as `del`, or
moved into another variable, the source binding is invalid. Using it again is a
type error.

```text
Proposed (pseudocode)
fn handoff()
    p := new Buf{...}        ; p is owned
    receive(p)               ; p is moved into receive(); now invalid
    print p.size             ; compile error: use of moved value
end
```

This is the minimum machinery to catch UAF statically without a borrow checker.
The cost is expressiveness: no aliasing. Two readers need a deeper mechanism
(borrows, capabilities, or clone).

Languages: **Rust** (affine by default; the `Copy` trait opts out),
**Linear Haskell**, **Idris 2**, **ATS**, **Austral**, **Granule**.

**Cost.** The type checker tracks a "moved" flag per binding. Diagnostics are the
hard part: telling the user which earlier use moved the value.

> Note (2026-09-16): A7 rejects a direct read after `del` today
> ("moved/deleted values cannot be read"; `a7/safety.py:724-730`). The memory
> plan removes `del` from ordinary code (gate M3) and makes only resources such as
> files and tasks move-only (gate M7). Not yet approved.

---

## 5. Borrow checking + lifetimes

**Catches:** UAF, concurrent mutation and iterator invalidation, while still
allowing sharing.

**Mechanism.** On top of affine ownership, allow temporary **borrows**. A borrow
is `&T` (immutable, many allowed) or `&mut T` (mutable, exclusive). Each borrow
has a **lifetime**, a region of the program. The type checker verifies that no
borrow outlives its referent and that `&mut` is never aliased.

Rust's current formulation (NLL, then Polonius) infers most lifetimes. Explicit
`'a` annotations are needed mainly in function signatures.

```rust
fn longest<'a>(a: &'a str, b: &'a str) -> &'a str {
    if a.len() > b.len() { a } else { b }
}
```

Languages: **Rust**; partial in **C++** ("safe C++" proposals; the original text
also cited a `-fsanitize=safety` flag, not verified in this audit); **Mojo**
(maturing at the time of writing).

**Cost.** Very large. Borrow checking is the largest source of language-spec
complexity in Rust. It needs a region algebra, a lifetime constraint solver and
substantial diagnostic tooling. Inference quality makes the model usable; without
it, every signature carries lifetime variables.

**For A7:** out of scope unless the language commits to shared mutable state.
Lighter alternatives (§7, §8) catch most of the same bugs.

> Note (2026-09-16): ledger L19 and L21 point the same way: users should not
> manage memory, and A7 must not carry Zig's manual memory load.

---

## 6. Region inference (Tofte-Talpin / Cyclone)

**Catches:** UAF for programs whose lifetimes are stack-shaped (last in, first
out, no escape).

**Mechanism.** Every allocation belongs to a **region**. Regions nest, and a
region's allocations are freed together when its scope ends. The type checker
proves that no pointer escapes its region.

Cyclone's experience
([region paper](https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf))
shows that inference, defaults and a few annotations keep user effort low:
"porting legacy C to Cyclone has required altering about 8 % of the code; of the
changes, only 6 % (of the 8 %) were region annotations."

```text
Proposed (pseudocode)
region r1
    p: *T in r1 = ralloc(r1, T)
    ...
end       ; entire r1 freed here; p cannot escape
```

Languages: **Cyclone** (the canonical reference), **MLKit** (Tofte-Talpin),
partial in **OCaml** through stack allocation analysis (2024-era `local_`
annotations).

**Cost.** Much smaller than borrow checking. The hard part is subtyping between
regions: when can a `*T in r2` be used where a `*T in r1` is expected? Cyclone
uses a partial order on regions plus region subtyping. It is well documented and
replicable.

**For A7:** the most natural fit, given that no recursion means bounded scope
depth. See the region-scope item in
[05 §3.6 and §5 Phase 6](./05-for-a7.md#5-phased-plan-zero-runtime-error-ordering).

> Note (2026-09-16): the link previously pointed to a "Phase 2 — make `del`
> optional" heading that no longer exists in 05. The memory plan keeps the
> region idea but infers extents inside the compiler (layers 4 and 5); users never
> write `region` (contract item 9). Not yet approved.

---

## 7. Generational references (Vale)

**Catches:** UAF. Most checks are removed at compile time; a small runtime check
remains on cold paths.

**Mechanism.** Every heap object has an integer **generation** in its header.
Every reference records the generation when it was taken. `free` (or `del`)
increments the generation. Before a dereference, the compiler either:

- proves the generation cannot have changed (through ownership tracking, regions
  or "linear style") and emits a plain load, the common case; or
- falls back to a runtime check (`expected_gen == obj.gen` ? proceed : panic),
  the cold case.

The static analysis is not a borrow checker. Roughly:

- An owning reference cannot have its generation invalidated while you hold it.
- A copy of a reference must be checked unless analysis shows the owner is still
  live in scope.

Languages: **Vale**.

> "Generational references are over twice as fast as reference counting, and
> could get even faster when we add our planned region borrow checker and
> hybrid-generational memory features."
> — [Vale design notes](https://verdagon.dev/blog/generational-references)

**Cost.** Small. The compiler tracks which references are "owned" and which are
"loose". The runtime cost is one word per heap object and a compare-and-branch on
cold dereferences. The original estimate was that about 90 % of accesses get
compile-time safety, with a narrow runtime net for the rest. That is a useful
compromise when a full borrow checker is unwanted.

> Note (2026-09-16): the memory plan adopts a related idea for collections with
> removal: a generation-tagged `Id(T)` whose lookup returns an optional, so a
> stale id never reads another record (gate M5). The outcome is a value, not a
> panic. Not yet approved.

---

## 8. Mutable value semantics (Hylo / Val)

**Catches:** UAF and aliasing bugs, with no lifetime annotations and no borrow
checker.

**Mechanism.** Every value is a value: assignment copies or moves, and there are
**no stored references**. Parameters use one of four modes:

| Mode | Semantics |
| --- | --- |
| `let`   | Immutable borrow for the call's duration |
| `inout` | Exclusive mutable borrow |
| `sink`  | Ownership transfer (consume) |
| `set`   | Output (uninitialized in, initialized out) |

References exist only as parameter modes, not as storable values, so aliasing
analysis is intra-procedural. At each call site the compiler checks that `inout`
arguments do not alias other arguments. No lifetime annotations are ever needed.

```text
Proposed (Hylo-style pseudocode; Hylo marks inout arguments with a sigil at the call site)
fn swap(x: inout T, y: inout T)
    let tmp = x
    x = y
    y = tmp
end

swap(&a, &a)    ; compile error: two inout aliases of the same value
```

Languages: **Hylo** (formerly Val), strongly influenced by **Swift**'s exclusivity
rules.

> "In Hylo, functions have no lifetime annotations despite achieving semantics
> identical to Rust's borrow checking."
> — [Hylo intro](https://hylo-lang.org/introduction/)

**Cost.** Medium. The type system needs the four modes and an exclusivity check at
call sites. The user-facing impact is much smaller than Rust's lifetimes.

**For A7:** the model to study for compile-time UAF safety without lifetimes. The
trade is giving up free-standing reference values.

> Note (2026-09-16): parameter-mode keywords for A7 (D.040, D.041, D.049) were not
> accepted; ledger L6 approves immutable arguments only. The memory plan follows
> this model internally: assignment copies, `ref` parameters cannot be stored or
> returned, and aliased `ref` arguments are rejected. Today an aliased call such
> as `both(x, x)` compiles (memory plan §3). A generic swap in current A7 is
> `swap :: fn($T, a: ref T, b: ref T)` (`docs/SPEC.md:698`).

---

## 9. Reference capabilities (Pony)

**Catches:** UAF, data races, and mutation without synchronization, all at compile
time, with no GC and no borrow checker.

**Mechanism.** Every reference type carries one of six capabilities:

| Capability | Read | Write | Aliasable in same actor | Sendable to other actor |
| --- | --- | --- | --- | --- |
| `iso` | Yes | Yes | No | Yes |
| `trn` | Yes | Yes | Yes (read-only aliases) | No |
| `ref` | Yes | Yes | Yes | No |
| `val` | Yes | No | Yes | Yes |
| `box` | Yes | No | Yes (read-only) | No |
| `tag` | No | No | Yes | Yes |

The type system only allows combinations that preserve race freedom.

Languages: **Pony**. Related concepts appear in **Vault** and **Cogent**.

**Cost.** Medium to large. Six capabilities are a real cognitive load, but the
soundness story is clean.

**For A7:** probably too much unless concurrency becomes central. It is the model
for race freedom without a runtime.

> Note (2026-09-16): ledger L1 puts concurrency in v1. The memory plan proposes
> structured tasks, values moved into tasks, and read-only sharing with child
> tasks (gates M10, M36), not capabilities. Not yet approved.

---

## 10. Refinement types

**Catches:** any predicate an SMT solver can decide, including bounds, integer
overflow, divide-by-zero and custom invariants.

**Mechanism.** Base types carry logical predicates:

```text
Proposed (pseudocode)
type Nat = {x: int | x >= 0}
type Index(n: int) = {x: int | 0 <= x && x < n}

fn get(xs: []T, i: Index(xs.length)) -> T
    return xs[i]              ; compile-time-proven safe
end
```

The compiler sends verification conditions to an SMT solver (Z3, CVC5). If the
solver discharges them, compilation succeeds. Otherwise the user gets a type
error at the unprovable obligation.

Languages: **Liquid Haskell**, **F\***, **Dafny**, **Idris** (with elaboration),
partial in **Scala** (Stainless), partial in **Rust** (Prusti, Creusot, Flux).

> "With Liquid Haskell, the bound checks are moved from runtime to compile time,
> semi-automatically handled by SMT-solvers." —
> [Haskell for all blog](https://www.haskellforall.com/2015/12/compile-time-memory-safety-using-liquid.html)

**Cost.** Large. The SMT solver becomes a build-time dependency. Diagnostics are
hard: "the solver said no" does not tell the user why. Once in place, any safety
property expressible as a predicate comes at no extra language cost.

**For A7:** useful for one focused case, bounds on slice indexing, without the
full machinery. [05 §3.5](./05-for-a7.md) describes that pattern-based version.

> Note (2026-09-16): the current safety pass is a lightweight form of this idea.
> It tracks integer intervals, non-zero facts and known lengths internally
> (`a7/safety.py`; `docs/SAFETY_CONTRACT.md`, "Internal Facts") without an SMT
> solver or refinement syntax. Verified examples:

```a7
// Current A7: rejected, "divisor must be non-zero: divisor may be zero"
divide :: fn(a: i32, d: i32) i32 {
    ret a / d
}
```

```a7
// Current A7: accepted; the guard gives the fact d != 0
div_or_zero :: fn(a: i32, d: i32) i32 {
    if d != 0 {
        ret a / d
    }
    ret 0
}
```

---

## 11. Dependent types

**Catches:** anything provable in higher-order logic. This is the upper bound of
static safety.

**Mechanism.** Types can depend on terms, and proofs are first-class values. To
call `index(xs, i)` you supply a term of type `Proof(i < length xs)`.

```idris
get : (xs : Vect n T) -> (i : Fin n) -> T
get (x :: _) FZ     = x
get (_ :: xs) (FS k) = get xs k
```

Languages: **Idris**, **Agda**, **Coq**, **Lean**, **F\***, **ATS** (industrial),
**Cedille**.

**Cost.** Very large. Beyond the type system, the compiler must support tactic
proofs and type-level computation. Verification effort grows with code
complexity.

**For A7:** out of scope as a primary mechanism. It marks the ceiling: dependent
types can express what refinement types cannot.

---

## 12. Effect systems

**Catches:** IO in a "pure" function, allocation in a real-time path, exceptions
across an FFI boundary, and ordering constraints on side effects.

**Mechanism.** Function types list the **effects** they may perform. The type
checker propagates effect sets and rejects calls that exceed the caller's
allowed set.

```text
Proposed (pseudocode)
fn parse(s: string) -> Tree | pure                  ; no side effects
fn read_file(p: string) -> string | io              ; performs IO
fn report(x: int) -> unit | io, alloc               ; both
```

Languages: **Koka**, **Eff**, **OCaml 5** (algebraic effects), **Haskell** (via
monads), **Frank**, **Unison**, partial in **Scala 3** (capture checking).

**Cost.** Medium. Inference is essential for usability; without it, every
signature carries an effect set.

**For A7:** orthogonal to memory safety, but useful for nearby guarantees such as
no allocation in signal handlers or no exception across a given boundary. Defer.

> Note (2026-09-16): the memory plan's typed IR includes effect summaries,
> including globals (layer 0), as internal compiler data rather than source
> annotations. Not yet approved.

---

## 13. SPARK / proved subset

**Catches:** every specified property of a program, when fully applied.

**Mechanism.** A restricted dialect of a host language (Ada, for SPARK) that
admits formal proof. The user writes Hoare-style pre- and postconditions, and the
toolchain discharges them through SMT or interactive proof.

```ada
function Divide (X, Y : Integer) return Integer
  with Pre  => Y /= 0,
       Post => Divide'Result = X / Y;
```

Languages: **SPARK / Ada**, **Frama-C / ACSL**, **Why3**, **Dafny**.

**Cost.** Very large for the language. Small for the user in one sense: they write
the contract, and the proof is automatic in the common case.

Used in avionics (DO-178C), nuclear control and secure cryptography.

**For A7:** evidence that compile-time safety for all properties is achievable in
industry. Probably too heavy for a general-purpose language, but its techniques
(preconditions, assertions promoted to proofs) carry over.

---

## 14. Comptime / staged metaprogramming

**Catches:** anything computable at compile time: bounds checks against constant
lengths, type-level enums, table-driven parser correctness.

**Mechanism.** A subset of the language runs at compile time. Runtime values are
those the compile-time evaluator produced. A function can check its own
arguments at compile time.

```zig
fn at(comptime N: usize, arr: [N]u8, comptime i: usize) u8 {
    if (i >= N) @compileError("index out of bounds");
    return arr[i];
}
```

Languages: **Zig** (`comptime`), **D** (CTFE), **C++** (`constexpr`), **Nim**
(macros), **Jai**, **Terra**.

**Cost.** Medium. The compiler needs an interpreter for the language. Zig shows
this is a substantial but bounded project.

**For A7:** A7 lowers through Zig, so it inherits `comptime` at the Zig level.
Whether A7 should have a source-level `comptime` keyword is a language-design
question, not a safety question.

---

## 15. Synthesis — what catches what

| Bug class | Cheapest static catcher | Stronger alternatives |
| --- | --- | --- |
| Uninitialized read | §1 Definite assignment | §11 Dependent types |
| Null deref | §2 Non-null types | §10 Refinement |
| Missed variant | §3 Sum types + exhaustive match | — |
| Use-after-free | §4 Affine types | §5 Borrow, §6 Regions, §7 Generational, §8 MVS |
| Double-free | §4 Affine types | Same |
| Leak | §4 (affine + `Drop` on scope exit) | §6 Regions |
| Slice OOB | §10 Refinement (focused) | §11 Dependent |
| Integer overflow | §10 Refinement | §11 Dependent, runtime trap |
| Data race | §5 + Send/Sync, or §8 MVS, or §9 Capabilities | §11 Dependent |
| Iterator invalidation | §5 Borrow check | §8 MVS |
| Aliasing under mutation | §5, §8, §9 | — |
| Type confusion through casts | Disallow the cast (no `inttoptr`, no raw `union`) | §11 Dependent |

The cheapest combination that closes nearly every common bug class:

> **§1 + §2 + §3 + §4 + §6 (or §8) + §10 (focused on bounds)**

That is the minimum viable compile-time-safe language. Sections 5, 7, 9 and
11–14 are options when their extra power is needed.

> Note (2026-09-16): for A7, integer overflow is no longer a bug class to catch
> for `+ - *`; ledger L5 defines them as wrapping. Division, shifts and casts are
> still open (gate G3).

---

## 16. Further reading

- Vale's grimoire of memory-safety techniques, a practitioner's survey:
  <https://verdagon.dev/grimoire/grimoire>
- Cyclone region paper (PLDI '02):
  <https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf>
- Vale generational references:
  <https://verdagon.dev/blog/generational-references>
- Hylo (Mutable Value Semantics): <https://hylo-lang.org/introduction/>
- Pony reference capabilities:
  <https://tutorial.ponylang.io/reference-capabilities>
- Liquid Haskell tutorial:
  <https://ucsd-progsys.github.io/liquidhaskell-tutorial/book.pdf>
- F\* tutorial:
  <https://www.fstar-lang.org/tutorial/>
- Tofte / Talpin region inference (original):
  <https://www.cs.cmu.edu/~rwh/courses/refinements/papers/TofteTalpin94/region.pdf>
- "Why Mutable Value Semantics?" (Racordon et al.):
  <https://www.jot.fm/issues/issue_2022_02/article2.pdf>
- Rust NLL RFC:
  <https://rust-lang.github.io/rfcs/2094-nll.html>
- Polonius (next-gen borrow checker):
  <https://rust-lang.github.io/polonius/>
- Memory Safety without Lifetime Parameters (safecpp):
  <https://safecpp.org/draft-lifetimes.html>
- John Regehr's tour of compile-time checks in C/Rust:
  <https://blog.regehr.org/>
- Niko Matsakis on lifetime-free safety (Aria):
  <https://smallcultfollowing.com/babysteps/blog/2023/11/15/polonius-update/>
