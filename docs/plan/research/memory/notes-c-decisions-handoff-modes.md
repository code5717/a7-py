> **Source:** Claude Code reading subagent, group C, full read of saved repository research.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../decisions.md).

# Notes C — lang-safety decisions, handoff, parameter modes, README

Scope: full reads of
- `docs/lang-safety/08-decisions.md` (2129 lines)
- `docs/lang-safety/HANDOFF.md` (564 lines)
- `docs/lang-safety/parameter-modes.md` (490 lines)
- `docs/lang-safety/README.md` (158 lines; working-tree copy, which has 15 uncommitted added lines)

Cross-checked against `docs/plan/decisions.md` L1-L16 (lines 33-48).
Line refs are `file:line`. Short file tags: `DEC` = 08-decisions.md,
`HO` = HANDOFF.md, `PM` = parameter-modes.md, `RM` = README.md.
"(inference)" marks my own reading, not something the source says.

---

## 1. Per-file summaries

### 08-decisions.md (DEC): Phase C decisions document. Mixed status.
- Numbered decisions D.001-D.053 in clusters CA (types and numerics), CB (casts and
  conversions), and CC (ownership, parameter modes, concurrency). CD-CG are still
  pending (DEC:43-53, 2115-2129).
- Guiding rule is "Zero runtime errors": emitted Zig must be safe under ReleaseFast,
  with no `@panic`/`@trap` (DEC:24-27). Other goals: "Python/JS-feel ergonomics"
  (DEC:28) and "Keep the language simple" (DEC:35).
- CA is **ACCEPTED** (DEC:727-729). It includes arbitrary-precision `int`/`uint`/`number`
  and FFI-only bit-width types. All of that is now overridden by L3/L4/L5/L16.
- CB is **ACCEPTED**, but D.024 ("cast is the universal conversion operator") and
  D.038 ("cast is removed") contradict each other. The file admits this (DEC:1453-1457).
- CC (ownership) is **PROPOSED** only (DEC:49, 2102): D.040-D.053 were never accepted.
- Status overall: **historical/superseded** for numerics. **Proposal** for ownership.

### HANDOFF.md (HO): handoff snapshot from 2026-05-11 (HO:8). Historical.
- Restates the zero-runtime-error contract (HO:22-27) and the user directions of the time (HO:78-102).
- Summarises Codex's review. Soundness holes S1-S6 (HO:112-119), including the bignum
  allocation hole (S1) and undefined `number` (S2). Design problems (HO:123-141), including
  "No storable refs blocks too many patterns" (HO:133-135).
- Four open user questions, Q1-Q4 (HO:149-196), plus Codex's settled recommendations (HO:198-211).
  Relevant here: storable refs stay banned "except potentially safe handles (`Index<T>`,
  `Handle<Arena, T>`) in v2+" (HO:211).
- Proposes a 9-pass architecture (HO:233-275), with `OwnershipMovePass` deferred to Phase 3 (HO:245).
  Three-phase delivery: ownership, drop analysis and concurrency all land in Phase 3 (HO:319-330).
- Status: **historical handoff**. Q1 and Q3 are effectively settled by L3/L4/L16 (inference).
  Its stale `/home/air/...` path (HO:541) and "~2034 lines" (HO:548) show its age.

### parameter-modes.md (PM): research input for Cluster CC. Research/proposal.
- Proposes immutable params, modes `borrow`/`inout`/`consume` inferred from the body
  (PM:31-43), no call-site sigils (PM:161-173), and a move lattice live/partial/consumed (PM:175-198).
- Also proposes Hylo-style call-site exclusivity (PM:218-280), no storable refs (PM:304-308),
  and channels plus isolated owned data per task (PM:310-394).
- Lists what is NOT provided: shared mutability, storable refs, self-referential structs
  (PM:296-308). Deferred to v2+: Arc-like sharing, user-defined destructors, select (PM:459-467).
- Has internal wobble: the transition table says "wait, see note below" (PM:192).
  Its call-site examples use `borrow p` / `consume p` (PM:360-361), which contradicts "no sigils".
- Header says "all public inference" but the HO:446 note says it "needs revision per Q5
  (public/private split)". The PM text was never revised (PM:15-18 vs DEC:1545).
- Status: **research** (never revised after the D.041 amendment).

### README.md (RM): directory index plus contract. Reference/index.
- The new (uncommitted) "Reading status" says: "Acceptance of a design decision does not
  establish that the compiler implements it" (RM:5-9). It points to STATUS/SAFETY_CONTRACT.
- Restates the contract, including "The language has no `unsafe` escape hatch" (RM:20-26), and indexes files.
- Stale: says "Cluster CA ... ACCEPTED. Clusters CB-CG pending" (RM:39), but DEC marks CB accepted.
- The quick-recommendations list claims "use-after-free, slice bounds, integer overflow, division
  by zero, allocation failure, stack overflow — each is rejected statically or surfaced as a
  typed value" (RM:138-141).
- Cites Fil-C FUGC (a runtime GC) as the thing A7 "doesn't need" (RM:32, 147-149).
- Status: **index/reference**. Its contract framing is still load-bearing. Its status table is stale.

---

## 2. Memory-management ideas relevant to L15

L15 asks for automatic memory management, resolved at compile time, data-oriented, with no
runtime collector, in the Jai/Odin/Zig style.

### 2.1 Decision ID roll-call (ownership / drop / del / defer / Copy / clone / arena / region)

| ID | Title | Status | Loc |
| --- | --- | --- | --- |
| D.021 | Compiler-inferred `Copy` marker | ACCEPTED (CA) | DEC:605-623 |
| D.025 | `new T{...}` is data-dependent → `?T` | ACCEPTED (CB) | DEC:813, 1425 |
| D.040 | Params immutable by default | PROPOSED | DEC:1494-1542 |
| D.041 | Modes explicit if public, inferred if private | REVISED — PROPOSED | DEC:1545-1625 |
| D.041b | Declared vs inferred mode discrepancy table | PROPOSED | DEC:1627-1656 |
| D.042 | No caller-side sigils | PROPOSED | DEC:1660-1685 |
| D.043 | Move analysis live/partial/consumed | PROPOSED | DEC:1689-1727 |
| D.044 | Call-site exclusivity inout/borrow | PROPOSED | DEC:1731-1764 |
| D.045 | `del p` consumes; double-free compile-time | PROPOSED | DEC:1768-1790 |
| D.046 | Auto-drop at scope exit (+ `defer del` precedence) | PROPOSED | DEC:1794-1826 |
| D.047 | `Copy` structural inference | PROPOSED | DEC:1829-1859 |
| D.048 | Partial moves out of struct fields | PROPOSED | DEC:1863-1890 |
| D.049 | No storable references | PROPOSED | DEC:1894-1923 |
| D.050 | Channels + isolated owned data (per-task heap) | PROPOSED | DEC:1929-1973 |
| D.051 | `go` spawn | PROPOSED | DEC:1976-1996 |
| D.052 | Cross-task by move only | PROPOSED | DEC:2000-2021 |
| D.053 | Per-task static stack budget | PROPOSED | DEC:2025-2053 |

The four files contain no decision about **arenas, regions, or clone**. Arenas appear only as
Codex's future `Handle<Arena, T>` (HO:211). "Region inference" is mentioned only as a technique
catalogued elsewhere: `06-compile-time-safety.md` (RM:37) and Cyclone (RM:83). No `.clone()`
method is proposed anywhere in these files (inference: an explicit copy of a non-Copy value has
no spelling).

### 2.2 Ideas in detail

**A. Affine move analysis (D.043).** DEC:1693-1714, PM:175-198.
- Mechanism: each binding is Live, Partially moved, or Consumed at each CFG point.
  `f(x)` for non-Copy consumes (DEC:1708-1709). `del x` consumes (DEC:1711).
  `x = new_value` re-lives and implicitly consumes the old value (DEC:1713-1714).
- Compile-time vs runtime: all compile-time (DEC:1722-1726: "Compile-time UAF,
  double-free, and use-of-moved-value rejection"). No runtime metadata.
- Cost: a new CFG dataflow pass. HO:245 puts `OwnershipMovePass` in Phase 3.
  HO:127-129 estimates 6-10 passes and "4–8 weeks for a v1 prototype".
- Limits:
  - Path-merge states such as "moved on one branch only" are not specified. The lattice has
    no "maybe-moved" state (inference; Rust needs drop flags here).
  - Loops are not discussed.
  - The implicit consume on reassignment (DEC:1713) is really an implicit `del` (inference).

**B. `del` as consuming free (D.045).** DEC:1772-1790, PM:24, 434-436.
- Mechanism: `del p` calls the allocator's destroy and marks `p` consumed (DEC:1789-1790).
- Compile-time: double-del and UAF become "use of consumed value" (DEC:1779-1780).
  Runtime: an ordinary free call.
- Cost: zero runtime overhead beyond the free.
- Limits:
  - Only catches the *same binding*. Aliasing through copies of a `ref T` is excluded only
    because `ref T` is non-Copy (DEC:1842).
  - `new` returns `?ref T` (DEC:1425, PM:78-81), so a nil narrowing is needed before `del`
    (inference).

**C. Auto-drop at scope exit (D.046).** DEC:1798-1826, PM:437-446.
- Mechanism: the compiler emits `del` for live non-Copy bindings at scope exit, in reverse
  declaration order (DEC:1824-1825). "`defer del p` ... if both ... the explicit form takes
  precedence" (DEC:1812-1814).
- Compile-time: placement of the drop. Runtime: the free calls themselves.
- Cost: cheap. The source claims "purely a compile-time codegen feature" (DEC:1818-1819).
- Limits:
  - Justified as "Matches Rust's `Drop` trait and Hylo's scope-exit semantics" (DEC:1816-1817).
    That is RAII, not the Jai/Odin/Zig style.
  - User-defined destructors are deferred (PM:465), so drop is only `del` of heap allocations.
    Nested owned graphs (a struct of refs of refs) need drop glue. Because A7 bans recursion,
    that glue must be iterative (inference).
  - PM:437-446 lists two alternatives: "Explicit-only" and "Compile error (unconsumed value at
    scope exit)", the linear-types option. Worth revisiting for L15.

**D. Structural `Copy` (D.021 accepted, D.047 proposed).** DEC:605-623, 1833-1859.
- Mechanism: primitives, enums, `[N]T` of Copy, and structs/unions of Copy fields are Copy.
  `string` is not Copy ("owns a heap allocation", DEC:1837-1838). `[]T` is not Copy
  ("borrows a backing storage", DEC:1840-1841). `ref T` is not Copy (DEC:1842).
- Compile-time only.
- Limits:
  - DEC:1852-1854 admits "adding a non-`Copy` field to a `Copy` struct silently breaks the
    inference".
  - For DOD this is important: POD struct-of-arrays stays Copy only if it holds fixed arrays,
    not slices (inference).

**E. Parameter modes as the only references (D.040-D.042, D.049).** DEC:1498-1685, 1898-1923, PM:88-112.
- Mechanism: `borrow` lowers to `*const T` and `inout` to `*T`. `consume` is a by-value move.
  The default is borrow; small Copy values pass by value and non-Copy values get an Odin-style
  auto-pointer (PM:92-97, 105-108).
- Mode inference lattice: `borrow < inout < consume` (DEC:1586-1591, PM:36-43).
- Compile-time: mode inference plus exclusivity. Runtime: plain pointers.
- Cost: zero-cost lowering. Requires cross-module signature sidecars (HO:260-272; DEC:1620-1621).
- Limits:
  - "Idioms that store references (callbacks, observers, linked structures) use heap-allocated
    `ref T` instead" (DEC:1920-1922).
  - "Linked data structures use indices into an owning container" (DEC:1922-1923; PM:304-308).
  - This is the direct bridge to DOD handles (inference).

**F. Call-site exclusivity (D.044).** DEC:1735-1764, PM:218-280.
- Mechanism: two inouts, or an inout plus a borrow, on the same path is an error.
  `swap(arr[i], arr[j])` requires a proved `i != j` (DEC:1750).
- Compile-time only.
- Limits: Swift needed runtime exclusivity checks: "Swift moved AWAY from purely static
  exclusivity (Swift 5 enabled runtime checks)" (HO:139-141). Tensor/index-heavy DOD code
  (`a[i]`, `a[j]`) will hit the proof wall often (inference).

**G. Handles / indices instead of pointers.** DEC:1922-1923, PM:304-308, HO:211.
- Mechanism: `Index<T>` and `Handle<Arena, T>` are named only as v2+ candidates (HO:211).
  No design is given.
- Compile-time vs runtime: not specified. Generational handles would need runtime generation
  checks, as in Vale (RM:87, "runtime-tinged fallback") (inference).
- This is the most L15/DOD-aligned idea in these files, but it is undeveloped.

**H. Per-task isolated heaps + move-only channels (D.050, D.052).** DEC:1933-1973, 2004-2021, PM:310-394.
- Mechanism: "Each task has its own stack and conceptually its own private heap region"
  (DEC:1937-1938). Values cross channels by move (DEC:1940-1941).
- Compile-time: sendability via the move checker. Runtime: a scheduler, "delegated to Zig's
  async or a custom scheduler" (DEC:1969-1970), and per-task allocators.
- Cost stated: "immutable shared snapshots must be copied at the channel boundary" (PM:387-389).
- Limits: no shared immutable data across tasks (PM:386). `Arc<T>` is deferred (PM:394, 461-462).
  For tensors or model weights this means copying or moving big buffers (inference).

**I. Static stack budget (D.053).** DEC:2029-2053.
- Mechanism: "Tasks have bounded stack needs because A7 has no recursion" (DEC:2043-2044).
  The runtime allocates exactly the computed stack.
- Compile-time analysis, runtime allocation. This is the one place where the recursion ban is
  explicitly used as a memory enabler.
- Limits: depends on the CE/D.062 stack-budget decision, which was never drafted (DEC:2031).

**J. Allocation failure as a typed value.** DEC:813, 1425, RM:139-141, HO:337.
- `new T{...}` returns `?ref T` (OOM is data-dependent). Codex's CT-2 includes "allocation
  failure not handled" (HO:337).
- Relevance: any automatic scheme that allocates implicitly (f-strings, string concatenation)
  must surface OOM somewhere. See §4.

**K. Hidden allocations already in accepted text.**
- D.008 f-strings lower to "a runtime concat helper" / "`std.fmt.allocPrint`" (DEC:292-293, 304).
- D.007: "`string + string` concatenation requires allocation" (DEC:273-275).
- No owner, lifetime, or free point is specified for either (inference). Both are compile-time
  auto-memory hard cases.

---

## 3. Conflicts with L15, L16, and other locked decisions

### L3 (remove `number`) / L4 (explicit widths) / L5 (wrapping arithmetic)

- **D.001 [ACCEPTED], DEC:76-92.** "exactly three primary numeric types: `int` ... `uint` ...
  `number`". `int` is a "mathematical integer; range is whatever memory allows" (DEC:81-82).
  Conflicts with L3 and L4.
- **D.002 [ACCEPTED], DEC:115-137.** Bit-width types "Produce a **compiler warning**" outside
  FFI (DEC:122-124). Conflicts with L4, which makes widths the ordinary types.
- **D.003 [ACCEPTED], DEC:141-175.** "Bare arithmetic ... is **always defined** ...
  **Transparent bignum-promotion**" (DEC:143-150). Conflicts with L4 and L5. It is also a hidden
  heap allocation, which conflicts with L15's compile-time, no-hidden-runtime goal. HO:114
  flags it as S1.
- **D.004 [ACCEPTED], DEC:179-196.** `uint - uint` returns `int`. Conflicts with L4 and L5.
- **D.005, D.026, D.027, D.029, D.035 [ACCEPTED].** All are phrased over `int`/`uint`/`number`,
  e.g. the "Round half to even (banker's)" method family (DEC:908). They need re-expression over
  explicit widths.
- **D.020 [ACCEPTED], DEC:579-584.** The range tracker exists for "Specialisation to native
  machine ops" and overflow discharge. Under L5, overflow is not a safety obligation (inference).
- **RM:138-141.** "integer overflow ... rejected statically or surfaced as a typed value".
  Conflicts with L5 (defined wrapping).
- **HO:81-85.** Directions 2 and 3 ("Three primary numeric types"; bit-width "FFI-only") are
  superseded by L3 and L4.
- **HO:162, 204, 298.** Codex's `int = i64`, `uint = u64`, `number = f64`. Partially aligned,
  but L4 keeps no `int` alias at all.
- **DEC:1107-1131, D.033 [ACCEPTED].** Inverse `int → i32` casts require range proof. Under L4
  that cast family is ordinary, not FFI-special.

### L16 (IEEE floats, NaN/inf are values)

- **D.001, DEC:86-88.** "`number` — real number with infinite precision. ... No NaN, no inf —
  those are not values of `number`." Direct conflict.
- **D.034 [ACCEPTED], DEC:1160-1172.** `f32.bits()` etc. "only available inside FFI-shim
  contexts". Conflicts with L3, L4, and L16 (floats are ordinary types).
- **D.027, DEC:905-909.** `.to_int_*` on `number` has no NaN/inf case. Under IEEE, trunc/floor
  of NaN/inf needs a defined result or a fallible form (inference).
- **HO:177-190, Q3.** Option (b) "`number = f64` with NaN/inf as values" matches L16, with the
  type named f32/f64 per L3. Q3 is resolved by L16.
- **RM:66.** `edge-cases/11-finite-floats.md` "`Fin<F>` and NaN/inf discipline" is still listed
  as live research (not read here).

### L15 (automatic, compile-time, data-oriented, Jai/Odin/Zig style)

- **D.046, DEC:1816-1817.** "Matches Rust's `Drop` trait and Hylo's scope-exit semantics."
  This is RAII-style implicit destruction. Jai, Odin, and Zig have no destructors; they use
  explicit `defer` plus allocators/arenas. This is a **tension**, not necessarily a conflict:
  L15 does say "automatic" (inference).
- **D.049 / D.050.** No storable refs, plus per-object `new`/`del` and per-task "private heap
  region" (DEC:1937-1938). The model is object-at-a-time ownership (Rust/Hylo lineage), while
  DOD favours bulk arenas, SoA, and handles.
  - The only handle idea is deferred to v2+ (HO:211).
  - The only multi-writer answer is "`Arc<Mutex<T>>` analog (deferred to v2+)" (PM:302-303).
    That is refcounting, which is runtime memory management and in tension with L15 (inference).
- **PM:394 / PM:461-462.** "`Arc<T>` analog" for shared immutable data across tasks. It is
  runtime refcounting, in tension with L15's no-runtime-collector goal.
- **D.050, DEC:1968-1970.** "Runtime support for task scheduling". This is not a GC, but it is
  runtime machinery (inference; not strictly an L15 conflict).
- **DEC:38-41, directive 5.** "A7 already has ... `new`/`del`". It assumes a single global
  allocator. Zig/Odin-style allocator parameters or context allocators are absent (inference).

### L6 (explicit mutation; argument bindings immutable)

- **D.041, DEC:1554-1569.** Private functions infer `inout` from a body write: "fill :: fn(b: []u8)
  ... Compiler infers: fill :: fn(b: inout []u8)". Mutation of referenced data becomes implicit
  at the signature, which conflicts with L6's "explicit mutation" and "a separately approved
  interface".
- **D.042, DEC:1672-1673.** "`fill(buf)` // implicit inout-pass; reads as plain call". Same
  tension, at the call site.
- **PM:15-18.** "The user shouldn't need to write parameter modes — inference is the default".
  Conflicts with L6.
- **D.040 (DEC:1506-1509)** is compatible with L6's binding-immutability half: `x = 10` and
  `s[0] = 0` are both errors without `inout`.

### Recursion ban, public syntax, and other locked rules

- **PM:157.** `// use_p_again := p.val`. Uses `.val` deref syntax, which the CLAUDE.md public
  syntax rules ban.
- **PM:360-361 and DEC:2010-2012.** `ch.send(consume p)` / `ch.send(borrow p)` use call-site
  mode keywords. That contradicts D.042 "No caller-side sigils" (internal conflict).

### Internal contradictions and doc drift

- **DEC:700 and 705 vs D.013 (DEC:401-426).** The CA summary still says "`none` stdlib identifier
  (replaces `nil` keyword)" and "Removed: `nil` keyword (D.013)". HO:144 says I1 was "verified
  gone", but it is still present in the summary.
- **D.024 (DEC:760) vs D.038 (DEC:1290).** Both ACCEPTED: cast universal vs cast removed
  (DEC:1453-1457, HO:116).
- **D.043 vs D.040/D.047.**
  - D.043: "`f(x)` for non-`Copy` `T` ⇒ `x` becomes consumed" (DEC:1708-1709).
  - D.040: default mode is read-only borrow (DEC:1500-1502).
  - D.047: slices and strings are non-Copy (DEC:1837-1841).
  - So a read-only call on a slice would consume it. PM:192 notices this ("wait, see note below").
- **D.022 / D.037 examples (DEC:632, 1263-1268).** Use `if b == 0: ... end` and `let`/`return`,
  i.e. non-A7 syntax.
- **RM:39.** "Clusters CB-CG pending" is stale versus DEC CB ACCEPTED.

---

## 4. Hard cases and counterexamples mentioned

- **Storable refs.** "observer pattern, graph structures, parsers, intrusive collections" are
  blocked (HO:133-135). Callbacks, observers and linked structures move to `ref T` or indices
  (DEC:1920-1923). "Self-referential structures: ... not expressible. Use indices." (PM:307-308).
- **Aliasing / indices.**
  - `swap(arr[i], arr[j])` is a compile error unless `i != j` is proved (DEC:1750, PM:274-280).
  - `f(x.field, x)` overlapping paths (DEC:1740-1741, PM:270-271).
  - Recommended rule: `f(x.a, x.a)` rejected but `f(x.a, x.b)` allowed (PM:431-433).
- **Shared mutable state within a task.** Not expressible. "the application architecture must
  change — typically using an `Arc<Mutex<T>>` analog" (PM:298-303).
- **Partial moves.** `pair.first` moved, then `take(pair)` is an error until reassigned
  (DEC:1874-1879).
- **Scope-exit choices.** Auto-drop vs explicit-only vs unconsumed-is-error (PM:437-446).
  Interaction with `defer del` (DEC:1812-1814).
- **Allocation failure.**
  - `new T{...}` returns `?ref T` (DEC:1425).
  - Bignum allocation can fail while arithmetic returns direct `int` (HO:114, 155-164).
  - Hidden allocations in f-strings (DEC:292-304) and `string + string` (DEC:273-275), with no
    stated OOM path (inference).
- **Escapes.** Consume is triggered by "returned, stored in a struct field" (PM:40). There is no
  escape analysis beyond that, and no discussion of returning slices into callee-owned storage
  (inference: returned `[]T` has no owner story, since slices "borrow a backing storage",
  DEC:1840-1841).
- **Cycles.** Not addressed. Cycles are impossible to build without storable refs, except via
  indices, whose staleness is unchecked (inference).
- **Concurrency.**
  - Cross-task borrow is forbidden (DEC:2012, PM:357-362).
  - Shared immutable snapshots must be copied (PM:386-390).
  - No locks in v1 (DEC:1971-1972).
  - Async cancellation deferred (PM:466).
  - Per-task stack sizes are computed statically (DEC:2029-2053).
- **Iterator invalidation.** Claimed safe because borrow prevents a mutating call during
  iteration (PM:290-292). Assumes iterators are parameter-scoped (inference).
- **Tensors / arenas / handles.** Tensors are not mentioned in these four files. Arenas and
  handles appear only as `Handle<Arena, T>` v2+ (HO:211). Big-buffer transfer is move-only
  across tasks (DEC:1940-1944).
- **AOT vs JIT.** "Arbitrary-precision performance is JIT-shaped, A7 is AOT. LuaJIT and V8 can
  deopt; A7 can't." (HO:136-138). This is the same argument against any speculative runtime
  memory scheme (inference).
- **Proof burden.** "without some visible surface, the language rejects too many safe programs"
  (HO:190-191); SPARK gets 95-98% automatic proof only with full annotations (HO:125-126).
  Applies equally to a fully inferred ownership or region system (inference).
- **Static exclusivity.** Swift fell back to runtime checks (HO:139-141).
- **Copy fragility.** Adding a non-Copy field silently changes the Copy property (DEC:1852-1854).
- **`[N]ref T` must be fully initialised** (D.015, DEC:460-474). Relevant to pools and SoA of
  handles.

---

## 5. Open questions for the brainstorm

1. **Drop style.** Should L15 mean RAII-like auto-drop (D.046, Rust/Hylo), or Jai/Odin/Zig-style
   explicit `defer` with compiler-checked "no leak / no double free" (the PM:441-444 "compile
   error on unconsumed value" option)? Or should auto-drop apply only to arena/scope-owned
   allocations?
2. **Unit of ownership.** Individual `new`/`del` objects (D.043-D.046), or **allocation regions/arenas**
   whose lifetime is inferred at compile time (bulk free, DOD-friendly)? None of the four files
   decides this. The only hint is `Handle<Arena, T>` (HO:211).
3. **Handles.** Should `Index<T>` / `Handle<Arena, T>` move from v2+ into v1 as the primary
   replacement for storable refs? If so, is stale-handle detection compile-time (typed
   arena/region lifetimes) or runtime (generations, Vale-style; RM:87)? A runtime generation check
   conflicts with the zero-runtime-check contract.
4. **Allocators.** Allocator passing: Zig-style explicit parameters, Odin/Jai implicit `context`
   allocator, or fully compiler-chosen? And how does an OOM surface under automatic allocation
   (DEC:1425 `?ref T` vs hidden f-string/concat allocations)?
5. **Mode inference vs L6.** Does L6 kill private `inout` inference (D.041/D.042)? Must mutation of
   referents always be written in the signature? Is some call-site marker needed?
6. **Slices and strings.** Are they Copy (views) or non-Copy (D.047)? This decides whether ordinary
   read calls "consume" (the D.043 vs D.040 contradiction), and how returned slices get an owner.
7. **Tensors (L7-L10) under move-only concurrency.**
   - Shared immutable weights across tasks need `Arc`-like refcounting (runtime) or a
     compile-time frozen/static region.
   - Autodiff tapes need per-step arenas with a bulk reset: is that a language feature or a
     stdlib pattern?
8. **Is Cluster CC dead?** Should CC (D.040-D.053) be re-opened wholesale under L15, given it is
   still PROPOSED and was designed for the superseded "Python/JS-feel" directive (DEC:28-30)?
9. **The recursion ban.** Should it be treated as an explicit enabler (static stack budget D.053,
   bounded drop glue, simpler region inference), and stated as such in the memory design?
10. **Contract vs L5/L16.** Should the "zero runtime errors" contract be reworded now that wrapping
    and IEEE NaN/inf are defined behaviour? Does L15 need a named escape for FFI-owned memory
    (RM:66 edge-case 12)?

---

## 6. External references cited (to follow up)

**Languages / systems explicitly cited in these files**
- Hylo: modes `let`/`inout`/`sink`/`set`, static exclusivity, no storable refs (PM:402; DEC:1719, 1918; RM:81 "A7's target model")
- Swift: `borrowing`/`consuming`/`inout`, Law of Exclusivity static plus runtime (PM:401; HO:139-141; RM:85)
- Mojo: `borrowed`/`inout`/`owned`, no call-site sigils, `Reference[lifetime]` (PM:403, 408-410; DEC:1676; RM:86)
- Rust: affine ownership, Drop, partial moves, `Arc<Mutex<T>>` (DEC:1719, 1784-1785, 1816, 1882; PM:303, 400)
- Odin: immutable params, auto-pointer for large args (DEC:1531; PM:14, 94, 404)
- Zig: immutable params, ReleaseFast safety removal, `comptime_int` (PM:405; DEC:1197; RM:82)
- Pony: six reference capabilities, `recover` (PM:377-390; RM:84)
- Inko / Koka / Verona: isolated heaps, effects, region-based concurrency (PM:481-483; RM:88)
- Vale: generational references (RM:87)
- Cyclone: region inference, 8% migration cost (RM:83)
- Austral: linear types, "600-line borrow checker" (RM:85)
- Ada/SPARK: SPARK ownership, 95-98% auto-proof (DEC:640-641; HO:125-126; RM:77-78)
- LuaJIT, V8, SBCL (tagged ints/deopt), GMP/MPFR (DEC:101-102, 157-158, 175; HO:136-138)
- Go/Erlang (channels), Kotlin (smart-narrow), Python/JS/Ruby/Lisp/Haskell numerics (DEC:437, 1963; 97-100, 155)
- axon-lang CT-1/CT-2/CT-3 blame taxonomy (HO:209, 332-342)
- Codex review (`codex-review.md`) (HO:106-108)

**URLs / papers (RM:95-116)**
- Fil-C: https://fil-c.org/invisicaps.html, https://fil-c.org/fugc.html (FUGC GC),
  https://fil-c.org/gimso.html, https://fil-c.org/compiler.html,
  https://github.com/pizlonator/fil-c/blob/deluge/Manifesto.md
- Google sanitizers: https://github.com/google/sanitizers
- Clang: https://clang.llvm.org/docs/BoundsSafety.html, UBSan, CFI, HWASAN design pages
- HWASAN, arXiv 1802.09517
- SoftBound (PLDI 2009), CETS
- Dijkstra concurrent GC, Doligez-Leroy-Gonthier, Fiji VM, Schism (GC background literature)
- CHERI/Morello, ARM MTE, Intel LAM/CET, SPARC ADI

**In-repo follow-ups referenced**
- `06-compile-time-safety.md`: region inference, generational references, mutable value semantics (RM:37)
- `comparative/hylo.md`, `comparative/vale.md`, `comparative/cyclone.md`, `comparative/inko-koka-verona.md`, `comparative/austral.md`
- `edge-cases/10-affine-ownership.md` (AO-06, AO-08, AO-25..28, Q10a-i), `edge-cases/05-stack-budget.md`,
  `edge-cases/11-finite-floats.md`, `edge-cases/12-ffi-boundary.md`

**Not cited in these four files, but directly relevant to L15** (suggestion, inference)
- Jai itself: context allocator, temporary storage
- Odin `context.allocator` / `temp_allocator`
- Zig `std.heap.ArenaAllocator` / explicit allocator params
- Tofte-Talpin region inference / MLKit
- Lobster compile-time reference counting
- Koka Perceus
- Proust ASAP (as static as possible)
- Rust-style generational-arena / slotmap handles
- Data-oriented design talks (Mike Acton, Andrew Kelley)
