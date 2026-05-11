# A7 Safety Design — Handoff Document

> Self-contained handoff for whoever (codex, another agent, a human contributor)
> picks up this work. **Read this file first.** Everything you need to continue
> is here or linked from here. Do not re-read the entire `docs/lang-safety/`
> directory unless this file points you at a specific section.

Last update: 2026-05-11 mechanical handoff pass over `08-decisions.md`.
The extended design session produced ~14,000 lines of research and decision
documents under `docs/lang-safety/`. The Phase C "Decisions" document
(`08-decisions.md`) is partially complete and still has user-decision-dependent
inconsistencies that need to be fixed (listed in §5 below).

---

## 1. Project goal

A7 is a Python-based compiler (in `a7/`) that emits Zig source and uses the
Zig toolchain to produce native binaries. The design goal of this work is to
add **memory safety to A7 at compile time** with the following contract:

> **Zero runtime errors.** The A7 compiler statically rejects every program
> that would exhibit a memory-safety violation at runtime. The emitted Zig
> remains memory-safe when compiled with `zig build-exe -O ReleaseFast`
> (every Zig runtime safety check disabled). Memory safety is a property
> of the emitted source, not of the backend's flags. The language has no
> `unsafe` escape hatch.

Plus three pragmatic constraints from the user:

- **Python/JS-feel ergonomics**: user code should read like TypeScript/Swift,
  not Rust.
- **Native performance**: backend is Zig; emitted code should be as fast as
  hand-written safe Zig.
- **Keep the language small**: minimal new keywords; complexity lives inside
  the compiler.

The full contract paragraph is in [`05-for-a7.md`](./05-for-a7.md) §7.

## 2. Current state

| Phase | Status | Notes |
| --- | --- | --- |
| **A — Edge-case enumeration** | ✅ Done | 12 files in `edge-cases/`, 103 numbered open questions |
| **B — Comparative deep-dives** | ✅ Done | 12 files in `comparative/`, covers Ada/Rust/Hylo/Zig/Cyclone/Pony/Austral/Swift/Mojo/Vale/Inko-Koka-Verona |
| **C — Decisions document** | 🔧 In progress, **needs fixes** | `08-decisions.md`, see §5 |
| **D — Spec** (`docs/A7_SAFETY_DESIGN.md`) | Not started | Depends on Phase C |
| **E — Implementation roadmap** | Not started | Depends on Phase D |

### What's accepted

- **Cluster CA** — Type-system foundations + numeric vocabulary (23 decisions).
  Marked ACCEPTED but **D.001 and D.003 have soundness issues that need
  amendment** (see §5).
- **Cluster CB** — Cast and conversions (16 decisions). Index and section
  trailer now both say ACCEPTED. D.024 and D.038 still conflict until the user
  resolves Q2 (`cast()` syntax).

### What's proposed

- **Cluster CC** — Ownership and parameter modes (14 decisions). The user
  asked for inferred parameter modes; codex pushed back; recommended
  resolution (in §6 below) is **public functions require explicit modes;
  private functions allow inference**.

### What's not started

- Clusters **CD** (flow analysis details), **CE** (numerics specifics),
  **CF** (Ada inspirations), **CG** (FFI + concurrency).
- Phase D (the canonical spec).
- Phase E (implementation roadmap).

## 3. User directions to honor

These came out of the design conversation and must be respected by anyone
continuing this work:

1. **`cast(T, x)` is A7's conversion operator.** The user explicitly directed
   that `cast()` stay as the syntax. Codex pushed back; the agreed
   compromise is "keep cast() but restrict it to primitive numeric
   conversions" (see §6).
2. **Three primary numeric types** (`int`, `uint`, `number`) at the user
   level. The user wants Python/JS feel: simple names, no `i32`/`u64` zoo
   in normal code.
3. **Bit-width types** (`i8`...`u64`, `f32`, `f64`) are **FFI-only** and
   warned outside FFI shims.
4. **`nil` keyword stays** (existing A7 syntax). Earlier draft proposed
   removing it in favour of `none`; reverted per user direction.
5. **The user shouldn't need to write parameter mode keywords.** Inference
   is preferred. Codex pushed back; the agreed compromise is public functions
   explicit / private inferred.
6. **Don't introduce many new keywords.** Push complexity into the compiler.
7. **Function parameters are immutable by default** (Odin/Zig style).
8. **No storable references** in v1.
9. **Recursion stays banned** (existing A7 rule).
10. **No `unsafe` block** ever.
11. **Concurrency model committed**: channels + isolated owned data (no
    reference capabilities).
12. **Existing A7 syntax** to honour: `name :: fn(args) RetType { ... }`,
    `ret` (not `return`), `{...}` blocks, `match` arms use `case X: { ... }`,
    `:=` for declaration with inference, `: T = v` for declaration with
    type, `and`/`or`/`not` for logical ops, `//` for comments.

## 4. Codex's review findings — what's actually wrong

Codex (the OpenAI Codex CLI) ran two critical-review rounds on the design.
Full output saved at [`codex-review.md`](./codex-review.md). The
high-severity findings:

### 4.1 Soundness holes

| # | Hole | Where |
| --- | --- | --- |
| S1 | **D.003 bignum-allocation hole.** "int / uint never overflows; compiler transparently bignum-promotes" — but bignum allocates and allocation can fail. Arithmetic returns direct `int`, not `?int`. The contract is broken. | `08-decisions.md` D.003 |
| S2 | **`number` semantics undefined.** D.001 says "real number with infinite precision; no NaN, no inf" — that's either a magic claim or needs a concrete representation (bigfloat, rational, decimal). Equality/ordering/floor undecidable in general. | `08-decisions.md` D.001 |
| S3 | **D.024 vs D.038 contradiction.** D.024 says `cast(T, x)` is the universal conversion operator (ACCEPTED). D.038 says `cast(T, x)` is removed (also ACCEPTED). Both are marked ACCEPTED in the file. | `08-decisions.md` D.024, D.038 |
| S4 | **Resolved 2026-05-11.** D.025 now treats `EnumT::from_discriminant(i)` as statically resolvable with direct `EnumT` return, matching D.032. | `08-decisions.md` D.025, D.032 |
| S5 | **Resolved 2026-05-11.** D.041 now uses the public/private compromise: public/API-boundary functions require explicit modes; private functions may infer. D.042 now refers to the resolved signature. | `08-decisions.md` D.041, D.042 |
| S6 | **Resolved 2026-05-11.** Cluster CB index and section trailer both say ACCEPTED. | `08-decisions.md` line ~48 and Cluster CB trailer |

### 4.2 Design problems

- **The "compiler does invisible work" claim is too strong.** Without
  visible proof surface (NonZero, Index, etc.), safe programs will be
  rejected. SPARK gets 95–98% automatic proof with a *full* annotation
  vocabulary. A7 currently claims same outcomes with less surface.
- **"One pass, few hundred lines" is wildly optimistic.** Realistic
  estimate: 6–10 passes, 4–8 weeks for a v1 prototype, longer for
  diagnostics polish.
- **No storable refs blocks too many patterns** — observer pattern, graph
  structures, parsers, intrusive collections. The Python/JS-feel goal
  fights this rule.
- **Arbitrary-precision performance is JIT-shaped, A7 is AOT.** LuaJIT and
  V8 can deopt; A7 can't. Range-tracked specialization with bignum
  promotion would force tagged values + slow paths everywhere.
- **Swift moved AWAY from purely static exclusivity** (Swift 5 enabled
  runtime checks). A7's "static only" `inout` is more aggressive than
  Swift's actual production model.

### 4.3 Inconsistencies in the docs

| # | Inconsistency |
| --- | --- |
| I1 | "nil → being removed (D.013)" line in directive list at top of `08-decisions.md` — verified gone on 2026-05-11. D.013 now keeps `nil` as the no-value literal. |
| I2 | Code blocks in some files still use `let x = ...`, `return`, Python-style colons. Should use A7 syntax: `x := ...`, `ret`, `{...}` blocks. Files affected: `narrowing.md` (partially fixed), `conversions.md` (partially fixed), `compile-time-knowledge.md` (mostly fixed), `05-for-a7.md` (not swept yet), `06-compile-time-safety.md` (not swept yet). |
| I3 | `D.024` (method-style) text contradicts D.038 (cast removed) as noted in S3. |
| I4 | **Resolved 2026-05-11.** CC `D.041` and `D.042` now encode the public/private split. |

## 5. The 4 design questions (user must decide)

These are the substantive design questions where codex's recommendation
conflicts with the user's prior direction. The user must pick a resolution
before any of the four can be applied:

### Q1 — Bignum allocation hole

> The user wants `int` to be arbitrary precision ("-inf to inf as long as
> memory can handle it"). Codex says this creates a soundness hole because
> bignum allocation can fail.

Options:
- **(a)** Drop arbitrary precision; v1 is `int = i64`, `uint = u64`, `number = f64`. `BigInt` is a stdlib library type with `Result<T, AllocError>` ops. **Codex's recommendation.**
- **(b)** Keep arbitrary precision; arithmetic returns `?int` so allocation failure surfaces. Honest but verbose at every operation.
- **(c)** Keep arbitrary precision; allocator failure is a runtime panic. Abandons "zero runtime errors" for this case.

### Q2 — `cast()` syntax

> The user explicitly directed `cast()` stays. Codex first said remove it
> entirely (review-hostile per Rust Clippy precedent), then conceded a
> hybrid.

Options:
- **(a)** Keep cast() universal but restricted to safe conversions (the version before codex).
- **(b)** Remove cast() entirely; named methods only (`x.to_uint()`, `s.parse_int()`). **Codex's first preference.**
- **(c)** Hybrid: cast() for primitive numeric value-domain conversions only; named methods/constructors for everything else (structural conversions like slice↔array, enum↔int, NonZero construction). **Codex's settled recommendation.**

### Q3 — `number` semantics

> The user said `number` is "real number with infinite precision; no NaN,
> no inf." Codex says that's either magic or needs a concrete heavyweight
> representation.

Options:
- **(a)** Pick a concrete arbitrary-precision representation (bigfloat / decimal / rational); accept the cost.
- **(b)** `number = f64` with NaN/inf as values; remove the "no NaN" claim. **Codex's recommendation.**
- **(c)** `number = f64` for v1; add `Fin<f64>` refinement later for code that needs total arithmetic.

### Q4 — Path A (visible proof surface)

> The user wants the compiler to do invisible heavy lifting. Codex says
> without some visible surface, the language rejects too many safe programs.

Options:
- **(a)** Keep all refinements compiler-internal (the current direction).
- **(b)** Full Path A: bring back `NonZero<T>`, `Index<n>`, `Bounded<T, lo, hi>`, `Positive<T>`, `NonEmptySlice<T>`, plus preconditions and loop invariants.
- **(c)** Path A-lite: only `NonZero<T>` is user-visible in v1. Range tracking stays compiler-internal. Other refinements deferred to v2. **Codex's settled recommendation.**

## 6. Codex's full settled recommendation (after two iterations)

Codex's complete recommendation set, consolidated:

| Issue | Recommendation |
| --- | --- |
| Q1 Bignum | **(a)** `int=i64`, `uint=u64`, `number=f64` v1. `BigInt` is a library type. |
| Q2 cast() | **(c)** Hybrid: cast() for primitive numeric conversions only. See §7 for the boundary table. |
| Q3 `number` | **(b)** IEEE 754 `f64` with NaN/inf. Drop "no NaN, no inf" claim. |
| Q4 Path A | **(c)** `NonZero<T>` is the only v1 visible refinement. Range tracking compiler-internal. |
| Parameter modes | Public/private split. `pub fn` requires explicit modes; private fns allow inference. Public generics require explicit modes (each instantiation imposes different pressure). |
| Diagnostics | Adopt **CT-1/CT-2/CT-3 blame taxonomy** from axon-lang: CT-1 compiler bug, CT-2 user error, CT-3 infrastructure error. |
| Storable refs | Stay banned in v1, except potentially safe handles (`Index<T>`, `Handle<Arena, T>`) in v2+. |
| Implementation scope | 9 passes for v1, not one. 4–8 weeks for v1 prototype, longer for diagnostics. |

## 7. The cast() classifier table (codex's settled boundary)

If Q2(c) is adopted:

| Cast | Verdict | Reason |
| --- | --- | --- |
| `cast(i64, i32_val)` | ✅ lossless widening | Always safe |
| `cast(u64, u32_val)` | ✅ lossless widening | Always safe |
| `cast(uint, int_val)` | ✅ only if `int_val >= 0` proved | Statically resolvable |
| `cast(int, number_val)` | ✅ only if finite, integral, in-range proved | Statically resolvable |
| `cast(f64, i64_val)` | ✅ explicit lossy numeric | Document precision loss; not a safety error |
| `cast(EnumT, i)` | ❌ — use `EnumT::from_discriminant(i)` | Structural invariant |
| `cast([N]T, s)` | ❌ — use `[N]T::from(s)` | Structural invariant |
| `cast(NonZero<T>, x)` | ❌ — use `NonZero::new(x)` | Refinement constructor |
| `cast(?T, x)` for `x: T` | implicit upcast | Doesn't need cast() at all |
| `cast(T, x)` for `x: ?T` | ❌ — use `match` | Narrowing via `match` only |
| `cast(ref T, i_val)` | ❌ NEVER | The audit's int↔ptr hole — closed |
| `cast(usize, ref_val)` | ❌ NEVER | Same direction; closed |
| `bit_cast(T, x)` | Separate spelling; FFI-gated only | Different operation, not cast |

## 8. The 9-pass compiler architecture (codex's plan)

Add after the existing name resolution / type checking in `a7/compile.py`:

| # | Pass | Owns | Notes |
| --- | --- | --- | --- |
| 1 | `SignaturePass` | canonical function signatures, parameter modes, generic constraints, exported interface data | Run after name resolution |
| 2 | `ModeInferencePass` | private-only inference of `borrow`/`inout`/`consume`; public modes verified | Reads body; writes inferred mode to internal signature record |
| 3 | `CFGPass` | per-function basic blocks | Reuse the recursion-graph plumbing style at `a7/passes/semantic_validator.py:501-589` |
| 4 | `NarrowingPass` | path-sensitive facts: nullness, integer intervals, enum discriminant sets, slice length equalities, nonzero facts | Consumes `node_types` from type checker; produces `facts_in[node_id]` / `facts_out[node_id]` |
| 5 | `ObligationPass` | attaches proof obligations to risky AST nodes (arithmetic, division, indexing, slicing, narrowing conversions, enum conversion) | Per-node obligation records |
| 6 | `ProofDischargePass` | marks each obligation as discharged or emits diagnostics | Uses facts from `NarrowingPass` |
| 7 | `OwnershipMovePass` | live / partially-moved / consumed lattice; auto-drop emission points | **Phase 3 only** (not Phase 1) |
| 8 | `BackendPlanPass` | annotates each AST node with `bare` / `checked` / `forbidden` lowering | Output is the codegen's input |
| 9 | (codegen) Updated Zig backend | emits only operations the safety-validation chain marked proven or checked | Stops deciding safety in codegen |

**Critical design point:** the type checker (`a7/passes/type_checker.py`)
should assign **base types only**. Narrowing should produce a **separate
fact map** keyed by node id. Do not cram narrowing into the type checker.

**Cast classifier**: implement as a **table-driven module**, not scattered
checks. Input: source type, target type, current facts. Output:
`LOSSLESS` / `PROVABLE_NARROWING` / `FALLIBLE_DATA` / `FORBIDDEN`. Current
`visit_cast` at `a7/passes/type_checker.py:1800` is unsound because it just
returns the target type. Current Zig emission at `a7/backends/zig.py:1690`
blindly emits `@as`.

**Cross-module signature representation**: serialize as JSON or sidecar
file. Shape:

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

## 9. Three-phase delivery plan

### Phase 1 — Close the audit hole; ship working ReleaseFast-safe Zig

**Passes to ship:**

1. Parse / tokenize (existing).
2. Import / module resolution (existing).
3. Name resolution (existing).
4. Type checking with **real cast classification** (rewrite `visit_cast`).
5. **Definite assignment + nil/nullability split** (new pass).
6. **Numeric range-lite proof pass** (new): literals, constants, simple comparisons, loop ranges.
7. **Safety validation pass** (new): rejects int↔ptr casts, unchecked division, opaque indexing, overflow-prone arithmetic unless proved or explicitly checked.
8. Lowering / preprocess (existing).
9. Zig codegen that **only emits proven or checked operations** (rewrite the unsafe paths in `a7/backends/zig.py`).

**Phase 1 visible surface:**

- `cast()` only for primitive numeric value conversions (per §7).
- `NonZero<T>` (the one v1 refinement).
- `s.try_get(i) -> ?T` for dynamic indexing.
- `int = i64`, `uint = u64`, `number = f64`.
- No bignum.
- No ownership/concurrency story beyond simple value/reference restrictions.

**What this rejects:** all the audit's critical hazards. What's accepted: a
restricted but useful subset of A7 today.

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

## 10. Blame taxonomy (from axon-lang via codex)

Adopt CT-1/CT-2/CT-3 classification at every diagnostic site:

- **CT-1 (compiler defect)**: internal invariant failure, impossible AST/type state, backend generated invalid Zig after semantic success.
- **CT-2 (user program error)**: type mismatch, unsafe cast, divisor not proven non-zero, index bound not proven, allocation failure not handled.
- **CT-3 (infrastructure/environment)**: missing Zig, unsupported backend import, filesystem failure, package/build failure.

A7 already has staged exit codes and semantic pass reporting at
`a7/compile.py:221`. The cost is mostly taxonomy discipline, not
architecture. Update D.037 to specify the classification.

## 11. Existing A7 codebase pointers

The Python implementation lives under `a7/`. Key files for the safety
work:

| File | Role |
| --- | --- |
| `a7/compile.py` | Main compilation pipeline (`A7Compiler`); orchestrates passes |
| `a7/parser.py` | Recursive-descent parser (~2300 lines) |
| `a7/tokens.py` | Tokenizer with single-token generics (`$T`), nested comments |
| `a7/ast_nodes.py` | AST node definitions |
| `a7/types.py` | Type model — `ReferenceType` at 210-226, `FunctionType` at 229+, `is_assignable_to` at 108-140 |
| `a7/passes/name_resolution.py` | Name resolution pass |
| `a7/passes/type_checker.py` | Type checker — `visit_cast` at 1800 (unsound), `visit_index_expr` at 1640, match exhaustiveness at 1829-1910 |
| `a7/passes/semantic_validator.py` | Iterative traversal (140-236); recursion check (`_validate_no_recursion` at 501-544, `_collect_function_calls` at 546-589) |
| `a7/ast_preprocessor.py` | 9 existing sub-passes |
| `a7/backends/zig.py` | Zig codegen — cast emission at 1690 (unsound), indexing at 1638-1645, arithmetic at 1566, div/mod at 1550-1558, pointer at 1682-1688 |
| `a7/generics.py` | Generic-type infrastructure |
| `a7/symbol_table.py` | Symbol table |
| `a7/errors.py` | Error types — `INVALID_CAST` at 148 and `UNSAFE_CAST` at 149 (declared but unused) |
| `a7/stdlib/` | Stdlib registry — io, math, mem, string |

### Existing safety properties to preserve

- Recursion banned (`a7/passes/semantic_validator.py:501-544`).
- No `unsafe` block exists.
- No raw pointer arithmetic.
- `new [N]T` (heap fixed arrays) rejected.
- `match` exhaustiveness checked for enums and bools
  (`a7/passes/type_checker.py:1854-1858`).
- `usize` enforced for indices (`a7/passes/type_checker.py:1680-1690`).

### A7 source syntax (must be followed in all examples)

```a7
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

    p: ref i32 = x.adr                      // `.adr` address-of
    p.val += 1                               // `.val` dereference

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

## 12. File inventory of `docs/lang-safety/`

| File | Purpose | Status |
| --- | --- | --- |
| `README.md` | Directory index | Mostly current |
| `01-invisicaps.md` | Fil-C InvisiCaps research | Done |
| `02-sanitizers.md` | ASan/MSan/etc. research | Done |
| `03-hardware.md` | CHERI/MTE/etc. research | Done |
| `04-comparison.md` | Cross-tool comparison | Done |
| `05-for-a7.md` | The contract paragraph + 12-gap roadmap (legacy) | Has stale items; the contract itself is current |
| `06-compile-time-safety.md` | Catalog of compile-time techniques | Done |
| `07-language-review.md` | **Audit of current A7 against the contract** | Done; this is the critical reference for what's broken in A7 today |
| `08-decisions.md` | **Phase C decisions document** | In progress; needs the fixes from §5 |
| `narrowing.md` | Flow-sensitive narrowing research | Done; some syntax cleanup partial |
| `conversions.md` | Conversion design research | Done; some syntax cleanup partial |
| `compile-time-knowledge.md` | "Cast is allowed because the compiler knows" — central principle | Done |
| `parameter-modes.md` | Ownership / parameter mode research | Done; needs revision per Q5 (public/private split) |
| `codex-review.md` | Codex's first critical review | Saved |
| `edge-cases/01-12*.md` | Phase A enumerations | Done |
| `comparative/*.md` | Phase B language deep-dives (12 files) | Done |
| `HANDOFF.md` | **This file** | Current |

Use this file as the entry point. The other files are referenced as needed.

## 13. What needs to happen next

Concrete TODO list for whoever picks this up:

### Immediate (mechanical fixes)

Done on 2026-05-11:

1. Cluster CB status drift fixed: index and section trailer both say ACCEPTED.
2. D.025 and D.032 reconciled on `EnumT::from_discriminant`.
3. D.041 and D.042 reconciled with the public/private parameter-mode split.
4. D.013 state verified: `nil` stays as the no-value literal.

No remaining mechanical-only fixes are known. The next changes require the
user decisions below.

### Awaiting user decision

5. **Q1 Bignum** — user picks (a)/(b)/(c) per §5. Codex recommends (a).
6. **Q2 cast()** — user picks (a)/(b)/(c) per §5. Codex recommends (c) hybrid; the boundary table is in §7.
7. **Q3 `number`** — user picks (a)/(b)/(c) per §5. Codex recommends (b).
8. **Q4 Path A** — user picks (a)/(b)/(c) per §5. Codex recommends (c).

After user decides each Q, apply the corresponding edits to `08-decisions.md`:

- Q1(a) → rewrite D.001 (int/uint/number become i64/u64/f64); rewrite D.003 (no transparent bignum; bare arith only when proved); add note about `BigInt` library type for arbitrary precision.
- Q2(c) → revise D.024 to state the hybrid; promote the boundary table from §7 to the decision text; D.038 (cast removed) needs to be flipped to "cast restricted, not removed".
- Q3(b) → revise D.001's `number` clause; remove "no NaN, no inf" language.
- Q4(c) → revise D.022 (division) to reference `NonZero<T>`; bring back `NonZero<T>` as a v1 stdlib type with constructor `NonZero::new(x) -> ?NonZero<T>`.

### After the decisions land

9. Sync `narrowing.md`, `conversions.md`, `compile-time-knowledge.md`,
   `parameter-modes.md` to the resolved decisions.
10. Sweep all code blocks in `docs/lang-safety/` for A7 syntax (see §11).
    Files still needing work: `05-for-a7.md`, `06-compile-time-safety.md`,
    parts of `narrowing.md` and `conversions.md`.
11. Run codex again for a third review pass after the edits land. Use the
    same prompt template as `codex-review.md` was generated from but
    point at the updated `08-decisions.md`.

### Clusters CD–CG (still to draft)

12. Cluster CD — flow analysis details (narrowing lattice level, recognised
    pattern catalog, invalidation rules, diagnostic format). Most of the
    content is in `narrowing.md` already; turn into numbered decisions.
13. Cluster CE — numerics specifics (division/modulo method names; stack
    budget defaults).
14. Cluster CF — Ada inspirations (`private` sections, hierarchical
    modules, profiles, aspect specifications).
15. Cluster CG — FFI boundary (per `edge-cases/12-ffi-boundary.md`) +
    concurrency primitives (channels, `go` keyword, per-task stack
    budget).

### Phase D and E

16. After all clusters are ACCEPTED, write the canonical spec
    `docs/A7_SAFETY_DESIGN.md` (Phase D).
17. Translate the spec into a per-phase implementation roadmap
    `docs/lang-safety/09-implementation-roadmap.md` (Phase E).
18. Update `MISSING_FEATURES.md` and `TODO.md` to reflect the implementation
    phases.

## 14. Conversation style for the user

The user's communication pattern observed across the session:

- **Terse and decisive.** Short messages; expects concrete responses.
- **Pushes back on complexity.** "Keep the language simple"; reject
  features that bloat the surface; "the user shouldn't need to write
  all these stuff."
- **Iterates.** Re-asks the same question with a small twist; expects
  the design to shift in response.
- **Pragmatic, not academic.** Values production precedent ("Python /
  JS / Go feel") over theoretical purity.
- **Trusts but verifies.** "Take a second opinion from codex"; "find
  faults" — wants external sanity-check.
- **Approves bundles when they make sense.** "Approve as a whole" was
  the pattern for cluster CA.

When unsure, **ask the user**. Don't make large assumptions about
direction; the user prefers picking from a short menu of options to
having an agent guess.

## 15. Tooling notes

- `codex exec --skip-git-repo-check --sandbox read-only --cd
  /home/air/Projects/pl/a7-py '...'` works for non-interactive review.
  Pipe through `tail -300` for the structured response since the
  raw output includes reading the input docs.
- Codex web-searches are automatic; no flag needed.
- Codex review prompt template lives in this session's history; cite
  the issues by decision number (D.NNN) and file path with line number.
- Use `wc -l docs/lang-safety/08-decisions.md` to track the document's
  growth; it was at ~2034 lines at handoff.

## 16. The single most important thing

> **The contract is the thing.** Every other design decision flows from
> "zero runtime errors in emitted Zig under ReleaseFast." If a decision
> would let a runtime trap survive into emitted code, the decision is
> wrong. If a decision would force the user into Rust-level ceremony,
> revisit whether the contract needs softening.

The user's prior directions are constraints, but they are not the
contract. If a direction makes the contract impossible (e.g., bignum
without fallibility), the direction has to yield. Codex's review was
useful precisely because it identified where directions and contract
collide.

Good luck.
