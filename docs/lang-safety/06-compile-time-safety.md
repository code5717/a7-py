# 06 — Compile-time Safety Techniques

> Part of the `docs/lang-safety/` series. See the
> [README](./README.md) for the full map. Siblings:
> [01 — InvisiCaps](./01-invisicaps.md) ·
> [02 — Sanitizers](./02-sanitizers.md) ·
> [03 — Hardware-assisted safety](./03-hardware.md) ·
> [04 — Comparison](./04-comparison.md) ·
> [05 — Take-aways for A7](./05-for-a7.md).

This file catalogs the techniques that catch memory-safety bugs **at
compile time**, before the program ever runs. They are the only
techniques that give a *guarantee* (as opposed to a probability of
detection) and the only ones that cost zero CPU at runtime.

The taxonomy below is ordered roughly by the type-system machinery each
technique requires, from cheapest to most expressive.

| # | Technique | Catches | Lang. complexity | User effort |
| --- | --- | --- | --- | --- |
| 1 | Definite-assignment / flow analysis | Uninitialized reads, missing return | Tiny | None |
| 2 | Non-null pointer types | Null deref | Tiny | Annotations on optional cases |
| 3 | Sum types + exhaustive match | Type confusion, missed enum case | Small | Pattern matches |
| 4 | Linear / affine types | Use-after-free, double-free, leak | Small | Move semantics |
| 5 | Borrow checking + lifetimes | UAF + aliasing under shared mutation | Large | Lifetime annotations (often inferred) |
| 6 | Region inference | UAF for stack-shaped lifetimes | Medium | Region annotations at function signatures |
| 7 | Generational references | UAF (mostly elided at compile time) | Small | None — but 1 runtime check survives in cold paths |
| 8 | Mutable value semantics | UAF + aliasing without lifetime annotations | Medium | `inout` parameter mode |
| 9 | Reference capabilities | UAF + races without GC | Medium | Cap annotations on types |
| 10 | Refinement types | Bounds, overflow, arbitrary predicates | Large | Predicate annotations + SMT |
| 11 | Dependent types | Anything provable | Very large | Proofs |
| 12 | Effect systems | IO/alloc/exception purity, ordering | Medium | Effect annotations |
| 13 | Comptime / staged metaprogramming | Whatever you can compute at compile time | Medium | None — comptime is opt-in |

Each section below: what bug class it catches, mechanism sketch, a
worked example, languages that ship it, and what it costs the
implementer.

---

## 1. Definite-assignment / flow analysis

**Catches:** reads of an uninitialized local, falling off a non-`void`
function, use of a variable in a branch where it isn't assigned.

**Mechanism.** Walk the CFG. For each variable, compute the set of
program points where it is *definitely assigned*. A read at a point not
in the set is a compile error.

```text
fn f(c: bool) -> int
    x: int            ; not yet assigned
    if c
        x = 1
    end
    return x          ; compile error: x not definitely assigned on c=false
end
```

Cheap to implement: a standard data-flow pass over the AST or basic
blocks. Languages that ship it: **Java**, **C#**, **Kotlin**, **Rust**,
**Swift**, **Zig**, **Go** (return paths).

**Cost.** A few hundred lines in the type checker. Zero user
annotation.

---

## 2. Non-null pointer types

**Catches:** null-pointer dereference. Roughly 30 % of remotely
exploitable CVEs in C/C++ codebases historically.

**Mechanism.** Split the pointer type into two:

- `T*` (non-null) — constructed only by allocation or by a checked
  conversion from a nullable. Always safe to dereference.
- `T?` (nullable) — must be pattern-matched / unwrapped to be used.

```text
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

Languages: **Kotlin**, **Swift**, **TypeScript strict**, **C# 8+ NRT**,
**Rust** (`Option<T>` rather than a special variant), **Zig** (`?T`),
**Pony**.

**Cost.** One bit in the pointer type, one narrowing rule in the type
checker. The big win for a small language.

---

## 3. Sum types + exhaustive pattern matching

**Catches:** type confusion via untagged unions, forgotten enum cases.

**Mechanism.** A `union` (sum / variant / ADT) is *tagged* — the
runtime representation carries a discriminator, and the type checker
demands that every `match` covers all variants (or has a wildcard).

```text
type Shape = circle{r: f64} | rect{w: f64, h: f64}

fn area(s: Shape) -> f64
    match s
        case circle{r}:  return 3.14159 * r * r
        case rect{w, h}: return w * h
        ; compile error if a new variant is added and forgotten here
    end
end
```

Languages: **OCaml**, **Haskell**, **Rust**, **Swift**, **Scala**,
**TypeScript** (discriminated unions). A7 already has tagged unions
(`docs/SPEC.md`), so this rule is essentially already in place;
exhaustiveness checking is the part to verify.

**Cost.** Match-coverage checking is a standard algorithm (Maranget,
"Warnings for Pattern Matching"). Modest.

---

## 4. Linear / affine types

**Catches:** use-after-free, double-free, leaked resources, double-send.

**Mechanism.** A linear type **must** be consumed exactly once; an
affine type must be consumed *at most* once. Either way, after a value
is "used" — passed to a destructive operation like `del`, or moved into
another variable — the source binding becomes invalid and re-using it
is a type error.

```text
fn handoff()
    p := new Buf{...}        ; p is owned
    receive(p)               ; p is moved into receive(); now invalid
    print p.size             ; compile error: use of moved value
end
```

This is the minimum machinery needed to catch UAF *statically* without
a borrow checker. The cost in expressiveness: no aliasing. If you need
two readers, you need a deeper mechanism (borrows, capabilities, or
clone).

Languages: **Rust** (affine by default, `Copy` trait opts out),
**Linear Haskell**, **Idris 2**, **ATS**, **Austral**, **Granule**.

**Cost.** Type checker tracks a "moved" flag per binding. Diagnostics
are the hard part: telling the user *which* prior use moved the value.

---

## 5. Borrow checking + lifetimes

**Catches:** UAF *and* concurrent mutation *and* iterator
invalidation, while still allowing sharing.

**Mechanism.** Beyond affine ownership, allow temporary **borrows** of
a value. A borrow is either `&T` (immutable, multiple allowed) or
`&mut T` (mutable, exclusive). Each borrow has a **lifetime** — a
region of the program — and the type checker verifies that no borrow
outlives its referent and that `&mut` is never aliased.

Rust's modern formulation (NLL → Polonius) infers most lifetimes;
explicit `'a` annotations are needed only for function signatures.

```rust
fn longest<'a>(a: &'a str, b: &'a str) -> &'a str
    if a.len() > b.len() { a } else { b }
```

Languages: **Rust**, partial in **C++** (`-fsanitize=safety`,
"safe C++" proposals), **Mojo** (currently maturing).

**Cost.** Very large. Borrow checking is the single largest source of
language-spec complexity in Rust. Implementing it requires a region
algebra, a lifetime constraint solver, and a substantial amount of
diagnostic tooling. Inference quality is what makes the model
ergonomic; without it, every function signature is decorated with
lifetime variables.

**For A7:** out of scope unless the language commits to shared mutable
state. Lighter alternatives (#7, #8) catch most of the same bugs.

---

## 6. Region inference (Tofte-Talpin / Cyclone)

**Catches:** UAF for the subset of programs whose lifetimes are
stack-shaped (last-in-first-out, no escape).

**Mechanism.** Every allocation is assigned to a *region*. Regions
nest; a region's allocations are freed en bloc when the region's scope
ends. The type checker proves that no pointer escapes its region.

Cyclone's experience ([region paper](https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf))
shows region inference plus some defaults plus a sprinkling of
annotations reduces user effort dramatically: "porting legacy C to
Cyclone has required altering about 8 % of the code; of the changes,
only 6 % (of the 8 %) were region annotations."

```text
region r1
    p: *T in r1 = ralloc(r1, T)
    ...
end       ; entire r1 freed here; p cannot escape
```

Languages: **Cyclone** (the canonical reference), **MLKit**
(Tofte-Talpin), partial in **OCaml** via stack allocation analyses
(2024-era `local_` annotations).

**Cost.** Much smaller than borrow checking. The hard part is
*subtyping* between regions (when can a `*T in r2` be used where
`*T in r1` is expected?). Cyclone's solution — a partial order on
regions + region subtyping — is well-documented and replicable.

**For A7:** the most natural fit given A7's existing "no recursion ⇒
bounded scope depth" property. Discussed concretely in
[05 §3 Phase 2](./05-for-a7.md#phase-2--make-del-optional-then-make-it-safe-13-months).

---

## 7. Generational references (Vale)

**Catches:** UAF, with most checks elided at compile time and a tiny
residual runtime check on the cold path.

**Mechanism.** Every heap object carries an integer **generation** in
its header. Every reference to it remembers the generation at the
moment it was taken. `free` (or `del`) increments the generation.
Before dereferencing, the compiler either:

- Proves statically that the generation can't have advanced (via
  ownership tracking, regions, or "linear style") and emits a bare
  load — common case; or
- Falls back to a runtime check (`expected_gen == obj.gen` ?
  proceed : panic) — cold case.

The static analysis is *not* a borrow checker. It's roughly:

- An owning reference cannot have its generation invalidated as long as
  you hold it.
- A copy of a reference must be checked unless analysis can show the
  owner is still live in scope.

Languages: **Vale**.

> "Generational references are over twice as fast as reference
> counting, and could get even faster when we add our planned region
> borrow checker and hybrid-generational memory features."
> — [Vale design notes](https://verdagon.dev/blog/generational-references)

**Cost.** Small. The compiler needs to track which references are
"owned" vs. "loose". The runtime piece is one word per heap object
and a compare-and-branch on cold derefs. Critically, this means
"compile-time safety" is achievable for ~90 % of accesses with a
narrow runtime safety net for the rest — a useful compromise when you
don't want a full borrow checker.

---

## 8. Mutable value semantics (Hylo / Val)

**Catches:** UAF *and* aliasing-based bugs, with no lifetime
annotations and no borrow checker.

**Mechanism.** Every value is a **value** — assignment copies (or
moves) — and there are *no stored references*. Parameters are passed
by one of four modes:

| Mode | Semantics |
| --- | --- |
| `let`   | Immutable borrow for the call's duration |
| `inout` | Exclusive mutable borrow |
| `sink`  | Ownership transfer (consume) |
| `set`   | Output (uninitialized in, initialized out) |

Because references exist only as parameter-passing modes (not as
storable values), aliasing analysis becomes *purely intra-procedural*:
at any call site, the compiler enforces that `inout` arguments don't
alias other arguments. No lifetime annotations, ever.

```text
fn swap(x: inout T, y: inout T)
    let tmp = x
    x = y
    y = tmp
end

swap(&a, &a)    ; compile error: two inout aliases of the same value
```

Languages: **Hylo** (formerly Val), heavily influenced by **Swift**'s
exclusivity rules.

> "In Hylo, functions have no lifetime annotations despite achieving
> semantics identical to Rust's borrow checking."
> — [Hylo intro](https://hylo-lang.org/introduction/)

**Cost.** Medium. The type system needs the four parameter modes and
an exclusivity analysis at call sites. The user-facing impact is much
smaller than Rust's lifetimes.

**For A7:** if A7 wants ergonomic compile-time UAF safety without
lifetimes, this is the model to study. The trade is that you give up
free-standing reference values entirely.

---

## 9. Reference capabilities (Pony)

**Catches:** UAF, data races, mutability-without-synchronization —
all at compile time, with no GC and no borrow checker.

**Mechanism.** Every reference type is tagged with one of six
capabilities:

| Capability | Read | Write | Aliasable in same actor | Sendable to other actor |
| --- | --- | --- | --- | --- |
| `iso` | ✅ | ✅ | ❌ | ✅ |
| `trn` | ✅ | ✅ | ✅ (read-only aliases) | ❌ |
| `ref` | ✅ | ✅ | ✅ | ❌ |
| `val` | ✅ | ❌ | ✅ | ✅ |
| `box` | ✅ | ❌ | ✅ (read-only) | ❌ |
| `tag` | ❌ | ❌ | ✅ | ✅ |

The type system enforces that the combinations possible for any value
preserve race-freedom by construction.

Languages: **Pony**. (Concepts also appear in **Vault**, **Cogent**.)

**Cost.** Medium-large. The capability lattice is a real cognitive
load — six options is a lot — but the formal soundness story is
clean.

**For A7:** probably overkill unless concurrency becomes a first-class
concern. Worth knowing as the model for "race-freedom without a
runtime."

---

## 10. Refinement types

**Catches:** **arbitrary** predicates the SMT solver can decide,
including bounds, integer overflow, divide-by-zero, custom invariants.

**Mechanism.** Annotate base types with logical predicates:

```text
type Nat = {x: int | x >= 0}
type Index(n: int) = {x: int | 0 <= x && x < n}

fn get(xs: []T, i: Index(xs.length)) -> T
    return xs[i]              ; compile-time-proven safe
end
```

The compiler ships verification conditions to an SMT solver (Z3,
CVC5). If the solver discharges them, compilation succeeds; otherwise
the user gets a type error pointing at the unprovable obligation.

Languages: **Liquid Haskell**, **F\***, **Dafny**, **Idris** (with
elaboration), partial in **Scala** (Stainless), partial in **Rust**
(Prusti, Creusot, Flux).

> "With Liquid Haskell, the bound checks are moved from runtime to
> compile time, semi-automatically handled by SMT-solvers." —
> [Haskell for all blog](https://www.haskellforall.com/2015/12/compile-time-memory-safety-using-liquid.html)

**Cost.** Large. You ship an SMT solver as a build-time dependency.
Diagnostics are notoriously hard ("the solver said no" doesn't tell
the user *why*). But the technique is general — once it's in place,
any safety property expressible as a predicate is free.

**For A7:** valuable for a *focused* use case (bounds checking on
slice indexing) without committing to the full machinery. See §11.

---

## 11. Dependent types

**Catches:** anything provable in higher-order logic. The upper bound
of static safety.

**Mechanism.** Types can depend on terms; proofs are first-class
values. To call `index(xs, i)` you produce a term of type
`Proof(i < length xs)`.

```idris
get : (xs : Vect n T) -> (i : Fin n) -> T
get (x :: _) FZ     = x
get (_ :: xs) (FS k) = get xs k
```

Languages: **Idris**, **Agda**, **Coq**, **Lean**, **F\***, **ATS**
(industrial), **Cedille**.

**Cost.** Very large. Beyond the type system, the compiler must
support tactic-style proof construction and type-level computation.
Verification effort scales with code complexity.

**For A7:** out of scope as a primary mechanism. Worth knowing as a
ceiling — anything refinement types can't express, dependent types
can.

---

## 12. Effect systems

**Catches:** IO performed in a "pure" function, allocation in a
real-time path, exceptions across an FFI boundary, ordering
constraints on side effects.

**Mechanism.** Annotate function types with the *effects* they may
perform. The type checker propagates effect sets and rejects calls
that exceed the caller's permitted set.

```text
fn parse(s: string) -> Tree | pure                  ; no side effects
fn read_file(p: string) -> string | io              ; performs IO
fn report(x: int) -> unit | io, alloc               ; both
```

Languages: **Koka**, **Eff**, **OCaml 5** (algebraic effects),
**Haskell** (via monads), **Frank**, **Unison**, partial in **Scala
3** (capture checking).

**Cost.** Medium. Inference is the ergonomic linchpin; without it,
every function signature carries an effect set.

**For A7:** orthogonal to memory safety, but useful for adjacent
guarantees (no allocation in signal handlers, no exception across a
specific boundary). Defer.

---

## 13. SPARK / proved subset

**Catches:** every defined property of a program, when fully
applied.

**Mechanism.** A restricted dialect of a host language (Ada, in
SPARK's case) that admits formal proof. The user writes Hoare-style
pre- and post-conditions; the toolchain discharges them via SMT or
interactive proof.

```ada
function Divide (X, Y : Integer) return Integer
  with Pre  => Y /= 0,
       Post => Divide'Result = X / Y;
```

Languages: **SPARK / Ada**, **Frama-C / ACSL**, **Why3**, **Dafny**.

**Cost.** Very large for the language. *Small* for the user in the
sense that they only annotate the contract — the proof is automatic
in the common case.

Used in: avionics (DO-178C), nuclear control, secure crypto.

**For A7:** read as the proof-of-concept that "compile-time safety
for all properties" is industrially achievable. Probably too heavy
for a general-purpose language, but the techniques (preconditions,
assertions promoted to proofs) generalize.

---

## 14. Comptime / staged metaprogramming

**Catches:** anything that can be computed at compile time — bound
checks against constant lengths, type-level enums, table-driven
parser correctness.

**Mechanism.** A subset of the language runs at compile time. Values
that survive into the runtime are those that the compile-time
evaluator produced. Effectively, the type system becomes
Turing-complete *constructively* — you can write a function that
checks its own argument at compile time.

```zig
fn at(comptime N: usize, arr: [N]u8, comptime i: usize) u8
    if (i >= N) @compileError("index out of bounds");
    return arr[i];
end
```

Languages: **Zig** (`comptime`), **D** (CTFE), **C++** (`constexpr`),
**Nim** (macros), **Jai**, **Terra**.

**Cost.** Medium. You need a compile-time interpreter for the
language. Zig's experience shows this is a non-trivial but bounded
engineering project.

**For A7:** A7 already lowers through Zig, so it inherits `comptime`
*at the Zig level*. The interesting question is whether A7 should
have a *source-level* `comptime` keyword for users — that's a
language-design decision, not a safety question.

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

That's the minimum-viable compile-time-safe language. Sections 5, 7,
9, 11–14 are options if you need their extra expressive power.

---

## 16. Further reading

- Vale's grimoire of memory-safety techniques — practitioner's survey:
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
