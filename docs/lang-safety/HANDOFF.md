# A7 Safety Design — Handoff Document

Status: historical handoff for the safety-design research, last updated
2026-05-11, with audit notes added 2026-09-16. Several directions and open
questions here are now settled or replaced. Current user decisions are in the
[v1 decision ledger](../plan/decisions.md); the current plan is in
[docs/plan/README.md](../plan/README.md); what the compiler enforces today is in
[SAFETY_CONTRACT.md](../SAFETY_CONTRACT.md) and [STATUS.md](../STATUS.md).

This file was the entry point for anyone (Codex, another agent, a human) picking
up the safety work. It summarizes the state of `docs/lang-safety/` and links to
details, so you do not need to reread the whole directory.

The 2026-05-11 update was a mechanical pass over `08-decisions.md`. The design
session had produced about 14,000 lines of research and decisions. The Phase C
decisions document (`08-decisions.md`) was partly complete and still had
inconsistencies that needed user decisions (§5).

> Note (2026-09-16): plan track 0 ("Authority reconciliation") now owns this
> clean-up: mark superseded entries in `08-decisions.md`, this file, STATUS and
> the safety contract without deleting them. See
> [docs/plan/README.md](../plan/README.md) "Work tracks".

---

## 1. Project goal

A7 is a Python compiler (in `a7/`) that emits Zig source and uses the Zig
toolchain to build native binaries. This work aims to add compile-time memory
safety under this contract:

> **Zero runtime errors.** The A7 compiler statically rejects every program
> that would exhibit a memory-safety violation at runtime. The emitted Zig
> remains memory-safe when compiled with `zig build-exe -O ReleaseFast`
> (every Zig runtime safety check disabled). Memory safety is a property
> of the emitted source, not of the backend's flags. The language has no
> `unsafe` escape hatch.

Three practical constraints from the user:

- **Python/JS-feel ergonomics.** User code should read like TypeScript or Swift,
  not Rust.
- **Native performance.** Emitted code should be as fast as hand-written safe
  Zig.
- **Small language.** Few new keywords; complexity lives in the compiler.

The full contract paragraph is in [`05-for-a7.md`](./05-for-a7.md) §7.

> Note (2026-09-16): the contract is still the research goal, not the
> enforced state. [SAFETY_CONTRACT.md](../SAFETY_CONTRACT.md) states the
> fail-closed rule and lists which proofs are enforced today. The
> [memory plan](../plan/memory.md) §1 proposes amending this contract (gate
> M16), and plan gate G9 leaves open whether releases use ReleaseFast or
> ReleaseSafe. The ergonomics constraint now appears as ledger L17, L19 and L20.

## 2. Current state

State as of 2026-05-11.

| Phase | Status | Notes |
| --- | --- | --- |
| **A — Edge-case enumeration** | Done | 12 files in `edge-cases/`, 103 numbered open questions |
| **B — Comparative deep-dives** | Done | 12 files in `comparative/`: Ada, Rust, Hylo, Zig, Cyclone, Pony, Austral, Swift, Mojo, Vale, Inko/Koka/Verona |
| **C — Decisions document** | In progress; needs fixes | `08-decisions.md`, see §5 |
| **D — Spec** (`docs/A7_SAFETY_DESIGN.md`) | Not started | Depends on Phase C |
| **E — Implementation roadmap** | Not started | Depends on Phase D |

> Note (2026-09-16): `docs/A7_SAFETY_DESIGN.md` and
> `docs/lang-safety/09-implementation-roadmap.md` still do not exist. The
> [v1 plan](../plan/README.md) and [memory plan](../plan/memory.md) have taken
> over the role of Phases D and E.

### What's accepted

- **Cluster CA** — type-system foundations and numeric vocabulary (23
  decisions). Marked ACCEPTED, but D.001 and D.003 have soundness issues that
  need amendment (§5).
- **Cluster CB** — cast and conversions (16 decisions). The index and the
  section trailer both say ACCEPTED. D.024 and D.038 still conflict until the
  user answers Q2 (`cast()` syntax).

> Note (2026-09-16): ledger L3, L4 and L16 supersede D.001–D.004. The conversion
> and parsing decisions written for `int`, `uint` and `number` (D.005, D.022,
> D.025–D.027, D.029, D.033–D.037, D.039) must be restated for explicit widths
> under gate G3. D.024 and D.038 are both set aside pending G3. See the ledger's
> "Superseded material" table.

### What's proposed

- **Cluster CC** — ownership and parameter modes (14 decisions). The user asked
  for inferred parameter modes; Codex pushed back. The recommended resolution
  (§6) is: public functions require explicit modes; private functions allow
  inference.

> Note (2026-09-16): not accepted. Ledger L6 approves immutable argument
> bindings only, with no mode syntax. Proposed D.040, D.041 and D.049 are set
> aside. Open decision O2 was replaced by the [memory plan](../plan/memory.md),
> which makes ownership internal.

### What's not started

- Clusters **CD** (flow analysis details), **CE** (numerics specifics), **CF**
  (Ada inspirations), **CG** (FFI and concurrency).
- Phase D (the canonical spec).
- Phase E (implementation roadmap).

## 3. User directions to honor

These came out of the design conversation. Status notes from 2026-09-16 follow
each item where the ledger or plan changed it.

1. **`cast(T, x)` is A7's conversion operator.** The user directed that
   `cast()` stays. Codex pushed back; the agreed compromise was "keep cast() but
   restrict it to primitive numeric conversions" (§6).
   *Note (2026-09-16): still open under plan gate G3. The compiler already
   restricts casts to primitive numeric types (`a7/cast_classifier.py`).*
2. **Three primary numeric types** (`int`, `uint`, `number`) at the user level,
   for a Python/JS feel with no `i32`/`u64` zoo in normal code.
   *Note (2026-09-16): superseded by ledger L3 and L4. `number` is removed;
   integers have explicit widths only.*
3. **Bit-width types** (`i8`...`u64`, `f32`, `f64`) are FFI-only, with warnings
   outside FFI shims.
   *Note (2026-09-16): superseded by L4 (replaces D.002). Width types are the
   ordinary types.*
4. **`nil` keyword stays** (existing A7 syntax). An earlier draft replaced it
   with `none`; reverted by the user.
   *Note (2026-09-16): `nil` is still current. The proposed memory plan (§2)
   uses optionals for absence instead of `nil` references; not approved.*
5. **Users should not need to write parameter mode keywords.** Inference is
   preferred. Codex pushed back; the compromise was public explicit, private
   inferred.
   *Note (2026-09-16): superseded. L6 approves no mode syntax, and the memory
   plan makes ownership internal. `ref` remains the working parameter form.*
6. **Few new keywords.** Push complexity into the compiler.
   *Note: consistent with L20.*
7. **Function parameters are immutable by default** (Odin/Zig style).
   *Note: matches L6.*
8. **No storable references** in v1.
   *Note (2026-09-16): the proposed memory plan keeps this for `ref` (a `ref`
   cannot be stored or returned) and adds typed ids `Id(T)`; not approved.*
9. **Recursion stays banned** (existing A7 rule). *Still current.*
10. **No `unsafe` block**, ever. *Still current.*
11. **Concurrency model committed**: channels plus isolated owned data (no
    reference capabilities).
    *Note (2026-09-16): concurrency details are open under gate G7; the memory
    plan proposes structured tasks.*
12. **Existing A7 syntax** to honor: `name :: fn(args) RetType { ... }`, `ret`
    (not `return`), `{...}` blocks, `match` arms `case X: { ... }`, `:=` for
    inferred declaration, `: T = v` for typed declaration, `and`/`or`/`not`,
    `//` comments.
    *Note: L22 keeps the current syntax for now; later changes need approval.*

## 4. Codex's review findings — what's actually wrong

Codex (the OpenAI Codex CLI) ran two critical-review rounds. The first round is
saved in [`codex-review.md`](./codex-review.md). The high-severity findings:

### 4.1 Soundness holes

| # | Hole | Where |
| --- | --- | --- |
| S1 | **D.003 bignum allocation.** "int / uint never overflows; compiler transparently bignum-promotes." Bignum allocates, and allocation can fail, but arithmetic returns `int`, not `?int`. The contract breaks. *Superseded 2026-09-16 by L4 (no arbitrary precision) and L5 (wrapping).* | `08-decisions.md` D.003 |
| S2 | **`number` semantics undefined.** D.001 says "real number with infinite precision; no NaN, no inf". That needs a concrete representation (bigfloat, rational, decimal) or is magic. Equality, ordering and floor are undecidable in general. *Superseded 2026-09-16 by L3 (`number` removed) and L16 (IEEE floats).* | `08-decisions.md` D.001 |
| S3 | **D.024 vs D.038 contradiction.** D.024 says `cast(T, x)` is the universal conversion operator (ACCEPTED). D.038 says `cast(T, x)` is removed (also ACCEPTED). *Still open 2026-09-16: gate G3.* | `08-decisions.md` D.024, D.038 |
| S4 | **Resolved 2026-05-11.** D.025 treats `EnumT::from_discriminant(i)` as statically resolvable with a direct `EnumT` return, matching D.032. | `08-decisions.md` D.025, D.032 |
| S5 | **Resolved 2026-05-11.** D.041 uses the public/private compromise: public and API-boundary functions require explicit modes; private functions may infer. D.042 refers to the resolved signature. *2026-09-16: the compromise itself is not accepted (L6, memory plan).* | `08-decisions.md` D.041, D.042 |
| S6 | **Resolved 2026-05-11.** Cluster CB index and section trailer both say ACCEPTED. | `08-decisions.md` line ~48 and Cluster CB trailer |

### 4.2 Design problems

- **"The compiler does invisible work" is too strong.** Without a visible proof
  surface (`NonZero`, `Index`, etc.), the compiler will reject safe programs.
  SPARK proves 95–98% of checks automatically, with a full annotation
  vocabulary. A7 claims the same outcome with less surface.
- **"One pass, few hundred lines" is far too optimistic.** Realistic: 6–10
  passes, 4–8 weeks for a v1 prototype, longer for diagnostics.
  *Note (2026-09-16): today one `SafetyProofPass` (`a7/safety.py`) does this
  work in a limited form; STATUS priority 4 is to split it into stages.*
- **No storable refs blocks many patterns**: observers, graphs, parsers,
  intrusive collections. This fights the Python/JS-feel goal.
- **Arbitrary precision performance is JIT-shaped, but A7 is AOT.** LuaJIT and
  V8 can deoptimize; A7 cannot. Range-tracked specialization with bignum
  promotion forces tagged values and slow paths everywhere.
- **Swift moved away from purely static exclusivity.** Swift 5 enabled runtime
  checks. A7's static-only `inout` is more aggressive than Swift's production
  model.

### 4.3 Inconsistencies in the docs

| # | Inconsistency |
| --- | --- |
| I1 | "nil → being removed (D.013)" in the directive list at the top of `08-decisions.md` — verified gone on 2026-05-11. D.013 keeps `nil` as the no-value literal. *Note (2026-09-16): plan track 0 still lists `08-decisions.md:700-705` as saying `nil` is removed, contradicting revised D.013.* |
| I2 | Some code blocks still use `let x = ...`, `return` or Python-style colons instead of A7 syntax (`x := ...`, `ret`, `{...}`). Files: `narrowing.md` (partly fixed), `conversions.md` (partly fixed), `compile-time-knowledge.md` (mostly fixed), `05-for-a7.md` (not swept), `06-compile-time-safety.md` (not swept). *Note (2026-09-16): examples also use `s.length`; current A7 slices use `.len` (`a7/passes/type_checker.py:1796`).* |
| I3 | D.024 (method-style) text contradicts D.038 (cast removed), as in S3. |
| I4 | **Resolved 2026-05-11.** CC D.041 and D.042 encode the public/private split. |

## 5. The 4 design questions (user must decide)

In each question Codex's recommendation conflicted with the user's earlier
direction, so the user had to choose before edits could be applied.

> Status (2026-09-16):
>
> | Question | State | Source |
> | --- | --- | --- |
> | Q1 Bignum | Resolved: no arbitrary precision | Ledger L3, L4 (O4 superseded) |
> | Q2 `cast()` | Open | Plan gate G3 |
> | Q3 `number` | Resolved: `number` removed; IEEE floats with NaN and infinity | Ledger L3, L16 (O3 superseded) |
> | Q4 Path A | No ledger entry. SAFETY_CONTRACT treats facts as internal compiler data, not public types, which matches option (a) for now | [SAFETY_CONTRACT.md](../SAFETY_CONTRACT.md) "Internal Facts" |

### Q1 — Bignum allocation hole

> The user wants `int` to be arbitrary precision ("-inf to inf as long as
> memory can handle it"). Codex says this creates a soundness hole because
> bignum allocation can fail.

Options:
- **(a)** Drop arbitrary precision; v1 is `int = i64`, `uint = u64`, `number = f64`. `BigInt` is a stdlib type with `Result<T, AllocError>` operations. **Codex's recommendation.**
- **(b)** Keep arbitrary precision; arithmetic returns `?int` so allocation failure surfaces. Honest but verbose at every operation.
- **(c)** Keep arbitrary precision; allocator failure is a runtime panic. Abandons "zero runtime errors" for this case.

### Q2 — `cast()` syntax

> The user explicitly directed `cast()` stays. Codex first said remove it
> entirely (review-hostile per Rust Clippy precedent), then conceded a
> hybrid.

Options:
- **(a)** Keep `cast()` universal but restricted to safe conversions (the version before Codex).
- **(b)** Remove `cast()` entirely; named methods only (`x.to_uint()`, `s.parse_int()`). **Codex's first preference.**
- **(c)** Hybrid: `cast()` for primitive numeric value conversions only; named methods or constructors for everything else (slice↔array, enum↔int, `NonZero` construction). **Codex's settled recommendation.**

### Q3 — `number` semantics

> The user said `number` is "real number with infinite precision; no NaN,
> no inf." Codex says that's either magic or needs a concrete heavyweight
> representation.

Options:
- **(a)** Pick a concrete arbitrary-precision representation (bigfloat, decimal, rational) and accept the cost.
- **(b)** `number = f64` with NaN/inf as values; drop the "no NaN" claim. **Codex's recommendation.**
- **(c)** `number = f64` for v1; add a `Fin<f64>` refinement later for code that needs total arithmetic.

### Q4 — Path A (visible proof surface)

> The user wants the compiler to do invisible heavy lifting. Codex says
> without some visible surface, the language rejects too many safe programs.

Options:
- **(a)** Keep all refinements compiler-internal (the direction at the time).
- **(b)** Full Path A: bring back `NonZero<T>`, `Index<n>`, `Bounded<T, lo, hi>`, `Positive<T>`, `NonEmptySlice<T>`, plus preconditions and loop invariants.
- **(c)** Path A-lite: only `NonZero<T>` is user-visible in v1. Range tracking stays compiler-internal. Other refinements wait for v2. **Codex's settled recommendation.**

What option (c) would look like:

```a7
// Proposed (Q4 option (c)); not approved or implemented.
// NonZero::new returns an optional, so the zero case is handled as data.
safe_div :: fn(a: i64, b: i64) i64 {
    match NonZero::new(b) {
        case some(d): { ret a / d }
        case nil: { ret 0 }
    }
}
```

## 6. Codex's full settled recommendation (after two iterations)

| Issue | Recommendation |
| --- | --- |
| Q1 Bignum | **(a)** `int=i64`, `uint=u64`, `number=f64` in v1. `BigInt` is a library type. |
| Q2 cast() | **(c)** Hybrid: `cast()` for primitive numeric conversions only. Boundary table in §7. |
| Q3 `number` | **(b)** IEEE 754 `f64` with NaN/inf. Drop the "no NaN, no inf" claim. |
| Q4 Path A | **(c)** `NonZero<T>` is the only visible v1 refinement. Range tracking stays compiler-internal. |
| Parameter modes | Public/private split. `pub fn` requires explicit modes; private functions allow inference. Public generics require explicit modes, because each instantiation imposes different pressure. |
| Diagnostics | Adopt the **CT-1/CT-2/CT-3 blame taxonomy** from axon-lang: CT-1 compiler bug, CT-2 user error, CT-3 infrastructure error. |
| Storable refs | Stay banned in v1, except possibly safe handles (`Index<T>`, `Handle<Arena, T>`) in v2+. |
| Implementation scope | 9 passes for v1, not one. 4–8 weeks for a v1 prototype, longer for diagnostics. |

> Note (2026-09-16): the ledger went further than Codex on Q1 and Q3. There are
> no `int`, `uint` or `number` aliases at all (L3, L4). The parameter-mode row
> is not accepted (L6, memory plan). The memory plan's typed ids `Id(T)` are
> close to the "safe handles" idea; proposed only.

## 7. The cast() classifier table (codex's settled boundary)

If Q2(c) is adopted:

| Cast | Verdict | Reason |
| --- | --- | --- |
| `cast(i64, i32_val)` | Allowed: lossless widening | Always safe |
| `cast(u64, u32_val)` | Allowed: lossless widening | Always safe |
| `cast(uint, int_val)` | Allowed only if `int_val >= 0` is proved | Statically resolvable |
| `cast(int, number_val)` | Allowed only if finite, integral and in range are proved | Statically resolvable |
| `cast(f64, i64_val)` | Allowed: explicit lossy numeric | Document the precision loss; not a safety error |
| `cast(EnumT, i)` | Rejected — use `EnumT::from_discriminant(i)` | Structural invariant |
| `cast([N]T, s)` | Rejected — use `[N]T::from(s)` | Structural invariant |
| `cast(NonZero<T>, x)` | Rejected — use `NonZero::new(x)` | Refinement constructor |
| `cast(?T, x)` for `x: T` | Implicit upcast | Does not need `cast()` |
| `cast(T, x)` for `x: ?T` | Rejected — use `match` | Narrowing via `match` only |
| `cast(ref T, i_val)` | Rejected, never allowed | The audit's int↔ptr hole — closed |
| `cast(usize, ref_val)` | Rejected, never allowed | Same hole, other direction |
| `bit_cast(T, x)` | Separate spelling; FFI-gated only | A different operation, not a cast |

> Note (2026-09-16), read from source, not run: `a7/cast_classifier.py`
> implements a "Phase 1 hybrid cast boundary" over explicit-width types. It
> returns `LOSSLESS`, `EXPLICIT_NUMERIC`, `PROVABLE_NARROWING` or `FORBIDDEN`.
> It forbids any cast involving references or functions and any non-numeric
> cast. Signed-to-unsigned and narrowing casts need a proof. `SafetyProofPass`
> can upgrade a forbidden integer cast when the value's range fits the target
> (`a7/safety.py:522-554`). Float-to-integer casts are proved only for finite,
> integral, in-range literals (`a7/safety.py:654-661`). The `int`/`uint`/`number`
> rows above no longer apply (L3, L4); the Q2 spelling is still open (G3).

## 8. The 9-pass compiler architecture (codex's plan)

Add after the existing name resolution and type checking in `a7/compile.py`:

| # | Pass | Owns | Notes |
| --- | --- | --- | --- |
| 1 | `SignaturePass` | canonical function signatures, parameter modes, generic constraints, exported interface data | Run after name resolution |
| 2 | `ModeInferencePass` | private-only inference of `borrow`/`inout`/`consume`; verification of public modes | Reads the body; writes the inferred mode to an internal signature record |
| 3 | `CFGPass` | per-function basic blocks | Reuse the recursion-graph plumbing style at `a7/passes/semantic_validator.py:501-589` |
| 4 | `NarrowingPass` | path-sensitive facts: nullness, integer intervals, enum discriminant sets, slice length equalities, non-zero facts | Consumes `node_types` from the type checker; produces `facts_in[node_id]` / `facts_out[node_id]` |
| 5 | `ObligationPass` | proof obligations on risky AST nodes (arithmetic, division, indexing, slicing, narrowing conversions, enum conversion) | Per-node obligation records |
| 6 | `ProofDischargePass` | marks each obligation discharged or emits diagnostics | Uses facts from `NarrowingPass` |
| 7 | `OwnershipMovePass` | live / partially-moved / consumed lattice; auto-drop emission points | **Phase 3 only** |
| 8 | `BackendPlanPass` | annotates each AST node with `bare` / `checked` / `forbidden` lowering | Output is the codegen's input |
| 9 | (codegen) Updated Zig backend | emits only operations the safety chain marked proven or checked | Codegen stops deciding safety |

**Design point:** the type checker (`a7/passes/type_checker.py`) should assign
**base types only**. Narrowing should produce a **separate fact map** keyed by
node id. Do not put narrowing into the type checker.

**Cast classifier:** implement as a **table-driven module**, not scattered
checks. Input: source type, target type, current facts. Output: `LOSSLESS` /
`PROVABLE_NARROWING` / `FALLIBLE_DATA` / `FORBIDDEN`. At the time, `visit_cast`
at `a7/passes/type_checker.py:1800` was unsound because it just returned the
target type, and Zig emission at `a7/backends/zig.py:1690` emitted `@as`
blindly.

**Cross-module signatures:** serialize as JSON or a sidecar file:

```json
{
  "name": "fill",
  "params": [{"name": "b", "mode": "inout", "type": "[]u8"}],
  "return": "void",
  "requires": [],
  "ensures": [],
  "generic_params": []
}
```

**Parameter modes** need a `ParamMode` enum in `a7/types.py:229` and
`FunctionType.param_modes: tuple[ParamMode, ...]`.

> Note (2026-09-16), read from source at commit 701c679, not run. Parts of
> this plan exist in a merged form:
>
> - `SafetyProofPass` in `a7/safety.py` combines the roles of passes 4, 5, 6
>   and 8. It keeps a fact map keyed by node id and symbol, records
>   obligations (cast, divisor, index, slice, ref non-nil, overflow, union
>   field, move), and fills a `BackendPlan`. It runs after semantic validation
>   (`a7/compile.py:347`), and the plan is passed to codegen
>   (`a7/compile.py:403`).
> - The type checker still assigns base types; the fact map lives in the safety
>   pass, as recommended.
> - Codegen checks approvals: `_require_backend_approval` guards index, slice
>   and deref lowering (`a7/backends/zig.py:1672`, `1690`, `1716`).
> - The cast classifier is table-driven (`a7/cast_classifier.py`), with
>   `EXPLICIT_NUMERIC` in place of `FALLIBLE_DATA`.
> - Facts are saved and restored per block; there is no CFG pass. There is no
>   `SignaturePass`, `ModeInferencePass` or `OwnershipMovePass`, and no
>   `ParamMode` in `a7/types.py` (`FunctionType` is still at line 229).
> - The integer-overflow check returns before doing anything
>   (`a7/safety.py:631-636`). L5 decides wrapping, but the backend does not
>   lower `+ - *` to wrapping yet (plan gate G3, track 3).
> - The line citations `type_checker.py:1800` and `zig.py:1690` no longer
>   point at cast code (they are slice field lookup and `_emit_slice`).
> - STATUS priority 4 lists splitting the safety pass into CFG, fact,
>   obligation, proof-discharge and backend-plan stages. The mode passes are
>   superseded by L6 and the memory plan.

## 9. Three-phase delivery plan

> Note (2026-09-16): the [v1 plan](../plan/README.md) work tracks replace this
> phasing. Tracks 3 (numeric semantics), 5 (proof repair) and 6 (memory model)
> cover Phases 1–3 below.

### Phase 1 — Close the audit hole; ship working ReleaseFast-safe Zig

**Passes to ship:**

1. Parse / tokenize (existing).
2. Import / module resolution (existing).
3. Name resolution (existing).
4. Type checking with **real cast classification** (rewrite `visit_cast`).
5. **Definite assignment and nil/nullability split** (new pass).
6. **Numeric range-lite proof pass** (new): literals, constants, simple comparisons, loop ranges.
7. **Safety validation pass** (new): rejects int↔ptr casts, unchecked division, opaque indexing, and overflow-prone arithmetic unless proved or explicitly checked.
8. Lowering / preprocess (existing).
9. Zig codegen that **only emits proven or checked operations** (rewrite the unsafe paths in `a7/backends/zig.py`).

**Phase 1 visible surface:**

- `cast()` only for primitive numeric value conversions (§7).
- `NonZero<T>` (the one v1 refinement).
- `s.try_get(i) -> ?T` for dynamic indexing.
- `int = i64`, `uint = u64`, `number = f64`.
- No bignum.
- No ownership or concurrency story beyond simple value/reference restrictions.

**What this rejects:** all the audit's critical hazards. **What it accepts:** a
restricted but useful subset of A7 as it was.

> Note (2026-09-16): `int = i64`, `uint = u64`, `number = f64` is superseded by
> L3 and L4 (no aliases). Item 7's "overflow-prone arithmetic" is superseded by
> L5: `+ - *` wrap. SAFETY_CONTRACT marks cast, division/modulo, index, slice,
> ref deref and direct use-after-`del` as enforced. Plan gate G3 records three
> cases that still break the fail-closed rule: `u8` `x += 1` at 255, `i8`
> `-128 / -1`, and an out-of-range shift count.

### Phase 2 — Expand proof coverage

Add:

- Symbolic interval propagation
- Path-sensitive narrowing across `if`/`match`
- Loop induction recognition
- Safe shift bounds
- Enum discriminant validation
- Slice length facts
- Optional `Bounded<T, lo, hi>` or user-named subtypes (Ada-style)
- `Result` / `Option` ergonomics
- Generic constraint hardening

### Phase 3 — Ownership and concurrency

Add:

- Explicit public parameter modes
- Private mode inference
- Move / borrow checking
- Destructor / drop analysis
- Affine / linear resource modes
- Sendability / isolation
- Channels / tasks
- FFI trust boundaries

> Note (2026-09-16): the first two items are superseded by L6 and the memory
> plan. The memory plan proposes internal ownership with static release points
> and move-only resources; concurrency is gate G7; the native boundary is plan
> track 10 and memory gate M12.

## 10. Blame taxonomy (from axon-lang via codex)

Classify every diagnostic site as CT-1, CT-2 or CT-3:

- **CT-1 (compiler defect):** internal invariant failure, impossible AST or type state, backend produced invalid Zig after semantic success.
- **CT-2 (user program error):** type mismatch, unsafe cast, divisor not proven non-zero, index bound not proven, allocation failure not handled.
- **CT-3 (infrastructure/environment):** missing Zig, unsupported backend import, filesystem failure, package or build failure.

A7 already has staged exit codes and semantic pass reporting in
`a7/compile.py` (cited at line 221; the semantic stage now spans roughly lines
217–383). The cost is mostly taxonomy discipline, not architecture. Update
D.037 to specify the classification.

> Note (2026-09-16): D.037 is among the conversion decisions the ledger says
> must be restated for explicit widths under G3. No CT classification appears in
> the pipeline code read for this note.

## 11. Existing A7 codebase pointers

The Python implementation lives under `a7/`. Key files for the safety work:

| File | Role |
| --- | --- |
| `a7/compile.py` | Main pipeline (`A7Compiler`); orchestrates passes |
| `a7/parser.py` | Recursive-descent parser (~2300 lines) |
| `a7/tokens.py` | Tokenizer with single-token generics (`$T`) and nested comments |
| `a7/ast_nodes.py` | AST node definitions |
| `a7/types.py` | Type model — `ReferenceType` at 210-226, `FunctionType` at 229+, `is_assignable_to` at 108-140 |
| `a7/passes/name_resolution.py` | Name resolution pass |
| `a7/passes/type_checker.py` | Type checker — `visit_cast` at 1800 (unsound), `visit_index_expr` at 1640, match exhaustiveness at 1829-1910 |
| `a7/passes/semantic_validator.py` | Iterative traversal (140-236); recursion check (`_validate_no_recursion` at 501-544, `_collect_function_calls` at 546-589) |
| `a7/safety.py` | *Added to this table 2026-09-16.* `SafetyProofPass`, fact map, obligations, `BackendPlan` |
| `a7/cast_classifier.py` | *Added to this table 2026-09-16.* Table-driven cast classification |
| `a7/ast_preprocessor.py` | 9 existing sub-passes |
| `a7/backends/zig.py` | Zig codegen — cast emission at 1690 (unsound), indexing at 1638-1645, arithmetic at 1566, div/mod at 1550-1558, pointer at 1682-1688 |
| `a7/generics.py` | Generic-type infrastructure |
| `a7/symbol_table.py` | Symbol table |
| `a7/errors.py` | Error types — `INVALID_CAST` at 148 and `UNSAFE_CAST` at 149 (declared but unused) |
| `a7/stdlib/` | Stdlib registry — io, math, mem, string |

> Note (2026-09-16), checked against the source at 701c679:
>
> - The `a7/types.py` citations for `ReferenceType` and `FunctionType` still
>   match.
> - The `type_checker.py` citations at 1800 and 1829-1910 and the `zig.py`
>   citations at 1638-1690 now land on field-access and slice/index emission
>   code. Search by function name instead. Indexing is `_emit_index` at
>   `zig.py:1670`.
> - In `a7/errors.py`, `INVALID_CAST` is at line 149 and `UNSAFE_CAST` at 150.
>   `UNSAFE_CAST` is used by the safety pass (`a7/safety.py:540`, `561`).
>   `INVALID_CAST` usage was not rechecked.
> - Not rechecked: the `semantic_validator.py` lines, `type_checker.py:1640`,
>   `1680-1690` and `1854-1858`, the parser size and the preprocessor sub-pass
>   count.

### Existing safety properties to preserve

- Recursion is banned (`a7/passes/semantic_validator.py:501-544`).
- No `unsafe` block exists.
- No raw pointer arithmetic.
- `new [N]T` (heap fixed arrays) is rejected.
- `match` exhaustiveness is checked for enums and bools
  (`a7/passes/type_checker.py:1854-1858`).
- `usize` is enforced for indices (`a7/passes/type_checker.py:1680-1690`).
- *Added 2026-09-16:* `.adr` and `.val` are rejected as reference syntax
  (`a7/passes/type_checker.py:1784-1791`). Cast, division/modulo, index, slice
  and ref-deref obligations must be proved before codegen (SAFETY_CONTRACT
  "Risky Operations").

### A7 source syntax (must be followed in all examples)

Current A7 syntax sketch. It uses undeclared names (`has_license`, `x`, `day`,
`numbers`), so it is not a compilable program.

```a7
// Current A7 (syntax sketch).
io :: import "std/io"                       // imports

add :: fn(x: i32, y: i32) i32 {             // function declaration
    ret x + y                                // `ret` not `return`
}

Person :: struct {                          // type declaration
    name: string
    age: i32
}

main :: fn() {
    person := Person{name: "Bob", age: 30}  // `:=` declares with inference
    age: i32                                 // declaration without value
    age = 25                                 // assignment

    if age >= 18 and has_license {           // `and`/`or`/`not` keywords
        io.println("Can drive")
    } else {
        io.println("Cannot drive")
    }

    bump(x)                                  // pass lvalues directly to ref params
    person.age += 1                          // use ordinary field access after nil checks

    value_ptr := new i32                    // heap allocation
    if value_ptr == nil {                    // `nil` is the existing keyword
        ret
    }
    defer del value_ptr                     // `defer del`

    match day {                              // match arms use `case X: { ... }`
        case 1: { io.println("Monday") }
        case 2: { io.println("Tuesday") }
        else:   { io.println("Other") }
    }

    for i := 0; i < 5; i += 1 {              // C-style for
        io.println("i = {}", i)
    }

    for value in numbers {                   // range for over slice
        io.println("value = {}", value)
    }

    for i, value in numbers {                // indexed range for
        io.println("[{}] = {}", i, value)
    }
}
```

> Note (2026-09-16): `new` and `defer del` are current syntax. The memory
> direction (ledger L15, L17–L22; [memory plan](../plan/memory.md)) is automatic
> memory with no allocate or free in ordinary source, so `new`/`del` are
> expected to go away. That needs approval under the approval rule.

## 12. File inventory of `docs/lang-safety/`

Status column as of 2026-05-11.

| File | Purpose | Status |
| --- | --- | --- |
| `README.md` | Directory index | Mostly current |
| `01-invisicaps.md` | Fil-C InvisiCaps research | Done |
| `02-sanitizers.md` | ASan/MSan/etc. research | Done |
| `03-hardware.md` | CHERI/MTE/etc. research | Done |
| `04-comparison.md` | Cross-tool comparison | Done |
| `05-for-a7.md` | The contract paragraph and 12-gap roadmap (legacy) | Has stale items; the contract itself is current |
| `06-compile-time-safety.md` | Catalog of compile-time techniques | Done |
| `07-language-review.md` | **Audit of A7 against the contract** | Done; the reference for what was broken in A7 |
| `08-decisions.md` | **Phase C decisions document** | In progress; needs the fixes from §5 |
| `narrowing.md` | Flow-sensitive narrowing research | Done; syntax cleanup partial |
| `conversions.md` | Conversion design research | Done; syntax cleanup partial |
| `compile-time-knowledge.md` | "The cast is allowed because the compiler knows" — central principle | Done |
| `parameter-modes.md` | Ownership / parameter mode research | Done; needs revision per "Q5" (the public/private split, §6; there is no Q5 in §5) |
| `codex-review.md` | Codex's first critical review | Saved |
| `edge-cases/01-12*.md` | Phase A enumerations | Done |
| `comparative/*.md` | Phase B language deep-dives (12 files) | Done |
| `HANDOFF.md` | **This file** | Current |

> Note (2026-09-16): `07-language-review.md` predates `a7/safety.py`. Check its
> gaps against SAFETY_CONTRACT and STATUS before acting. `parameter-modes.md` is
> superseded by L6 and the memory plan. This file is now historical.

## 13. What needs to happen next

The work list as of 2026-05-11. For current work, use the
[v1 plan](../plan/README.md) tracks and gates.

### Immediate (mechanical fixes)

Done on 2026-05-11:

1. Cluster CB status drift fixed: index and section trailer both say ACCEPTED.
2. D.025 and D.032 reconciled on `EnumT::from_discriminant`.
3. D.041 and D.042 reconciled with the public/private parameter-mode split.
4. D.013 state verified: `nil` stays as the no-value literal.

No mechanical-only fixes remained; the next changes needed the user decisions
below.

### Awaiting user decision

5. **Q1 Bignum** — user picks (a)/(b)/(c) per §5. Codex recommends (a). *Resolved by L3, L4.*
6. **Q2 cast()** — user picks (a)/(b)/(c) per §5. Codex recommends (c) hybrid; boundary table in §7. *Open: gate G3.*
7. **Q3 `number`** — user picks (a)/(b)/(c) per §5. Codex recommends (b). *Resolved by L3, L16.*
8. **Q4 Path A** — user picks (a)/(b)/(c) per §5. Codex recommends (c). *No ledger entry.*

Edits to `08-decisions.md` planned after each decision:

- Q1(a) → rewrite D.001 (int/uint/number become i64/u64/f64); rewrite D.003 (no transparent bignum; bare arithmetic only when proved); note `BigInt` as the library type for arbitrary precision.
- Q2(c) → revise D.024 to state the hybrid; promote the §7 boundary table into the decision text; flip D.038 (cast removed) to "cast restricted, not removed".
- Q3(b) → revise D.001's `number` clause; remove "no NaN, no inf".
- Q4(c) → revise D.022 (division) to reference `NonZero<T>`; bring back `NonZero<T>` as a v1 stdlib type with constructor `NonZero::new(x) -> ?NonZero<T>`.

> Note (2026-09-16): the actual outcome differs from Q1(a) and Q3(b): no
> `int`/`uint`/`number` aliases exist. Plan track 0 marks D.001–D.004 superseded
> in place rather than rewriting them.

### After the decisions land

9. Sync `narrowing.md`, `conversions.md`, `compile-time-knowledge.md` and
   `parameter-modes.md` with the resolved decisions.
10. Sweep all code blocks in `docs/lang-safety/` for A7 syntax (§11). Files
    still needing work: `05-for-a7.md`, `06-compile-time-safety.md`, parts of
    `narrowing.md` and `conversions.md`.
11. Run Codex again for a third review after the edits land. Use the same
    prompt template that produced `codex-review.md`, pointed at the updated
    `08-decisions.md`.

### Clusters CD–CG (still to draft)

12. Cluster CD — flow analysis details (narrowing lattice level, recognized
    pattern catalog, invalidation rules, diagnostic format). Most of the content
    is already in `narrowing.md`; turn it into numbered decisions.
13. Cluster CE — numerics specifics (division/modulo method names; stack budget
    defaults).
14. Cluster CF — Ada inspirations (`private` sections, hierarchical modules,
    profiles, aspect specifications).
15. Cluster CG — FFI boundary (per `edge-cases/12-ffi-boundary.md`) and
    concurrency primitives (channels, `go` keyword, per-task stack budget).

> Note (2026-09-16): CE numerics now fall under gates G1 and G3; CG under G7,
> plan track 10 and memory gate M12.

### Phase D and E

16. After all clusters are ACCEPTED, write the canonical spec
    `docs/A7_SAFETY_DESIGN.md` (Phase D).
17. Turn the spec into a per-phase implementation roadmap
    `docs/lang-safety/09-implementation-roadmap.md` (Phase E).
18. Update `docs/STATUS.md` to reflect the implementation phases.

## 14. Conversation style for the user

Observed across the session:

- **Terse and decisive.** Short messages; expects concrete responses.
- **Pushes back on complexity.** "Keep the language simple"; rejects features
  that bloat the surface; "the user shouldn't need to write all these stuff."
- **Iterates.** Re-asks the same question with a small twist and expects the
  design to shift.
- **Pragmatic, not academic.** Values production precedent ("Python / JS / Go
  feel") over theoretical purity.
- **Trusts but verifies.** "Take a second opinion from codex"; "find faults" —
  wants an external sanity check.
- **Approves bundles when they make sense.** "Approve as a whole" was the
  pattern for Cluster CA.

When unsure, ask the user. Do not assume direction; the user prefers choosing
from a short menu of options over an agent's guess.

> Note (2026-09-16): the ledger's approval rule now formalizes this. Every
> change to syntax or behavior needs the current behavior, the proposed
> behavior, A7 examples of both and the compatibility impact, then explicit
> approval. Earlier accepted D.nnn decisions do not count as approval.

## 15. Tooling notes

- `codex exec --skip-git-repo-check --sandbox read-only --cd <repo root> '...'`
  works for non-interactive review. (The original command used the path
  `/home/air/Projects/pl/a7-py`.) Pipe through `tail -300` to get the structured
  response, because the raw output includes Codex reading the input docs.
- Codex runs web searches automatically; no flag needed.
- The Codex review prompt template lives in that session's history. Cite issues
  by decision number (D.NNN) and file path with line number.
- Track the growth of `08-decisions.md` with `wc -l`; it was about 2034 lines at
  handoff.

> Note (2026-09-16): ledger L12 routes cybersecurity reviews to GLM.

## 16. The single most important thing

> **The contract is the thing.** Every other design decision flows from
> "zero runtime errors in emitted Zig under ReleaseFast." If a decision
> would let a runtime trap survive into emitted code, the decision is
> wrong. If a decision would force the user into Rust-level ceremony,
> revisit whether the contract needs softening.

The user's earlier directions are constraints, but they are not the contract. If
a direction makes the contract impossible (for example, bignum without
fallibility), the direction has to yield. Codex's review was useful because it
found where directions and contract collide.

> Note (2026-09-16): the user's later decisions (L3–L5, L15–L22) and the
> approval rule now take precedence over this handoff. The compiler-level
> contract in force is [SAFETY_CONTRACT.md](../SAFETY_CONTRACT.md); the
> [memory plan](../plan/memory.md) §1 proposes its amendment.
