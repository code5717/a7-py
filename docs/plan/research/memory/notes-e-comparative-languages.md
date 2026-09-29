> **Source:** Claude Code reading subagent, group E, full read of saved repository research.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../decisions.md).

# E. Comparative languages — notes for the L15 memory brainstorm

Source set: every file in `docs/lang-safety/comparative/` (README, ada,
ada-deep-dive, austral, cyclone, hylo, inko-koka-verona, mojo, pony, rust,
swift, vale, zig), read in full. Locked decisions from
`docs/plan/decisions.md:33-48`. All paths below are relative to
`docs/lang-safety/comparative/` unless noted.

Global framing (applies to every section):

- Every comparative file predates L15/L16/L5/L6. They were written against the
  old contract: "zero runtime errors", affine ownership, Hylo-style parameter
  modes, explicit `del`, and Cyclone regions as a *fallback* (README.md:112-126,
  cyclone.md:168-171, rust.md:321-326). Their "A7 can steal" verdicts are partly
  stale under L15 ("automatic memory management without a runtime collector,
  designed for data-oriented programs, resolved at compile time, in the style of
  Jai, Odin and Zig", decisions.md:47).
- **Odin and Jai have no comparative file.** L15 names them explicitly. The
  directory's only Jai/Odin/Zig-style memory content is zig.md:248-251, which
  dismisses the allocator pattern as "the programmer's problem". Arenas,
  temporary allocators, context allocators, SoA, and handle tables are
  essentially absent from the directory. This is the biggest gap relative to L15.
- "Data-oriented design" appears nowhere by name in the set. The DOD-relevant
  threads are: indices/owning containers (hylo.md:228-231), generational
  references (vale.md:30-60), regions (cyclone.md:146-189), and layout control
  (ada-deep-dive.md:688-738).

---

## 1. Per-language summaries

### README.md (index + cross-cutting insights)

- Index of 11 languages plus the Ada deep-dive (README.md:8-21).
- Claims consensus for non-null by default (39-47), parameter modes over
  lifetimes (49-56), `Option`/`Result` over exceptions (58-66), ranged subtypes
  (68-76), compile-time over runtime checks (78-88), no borrow checker needed
  (90-99), FFI as the only safety boundary (101-110).
- Memory: no memory model of its own. It endorses "parameter modes only" and
  "no borrow checker" (55-56, 98-99). It calls A7 "SPARK Lite" (125-126).
- Status: pre-L15 synthesis. Insight B (49-56) conflicts with L6's scope limit
  (see section 4). Insight E (80-88), "compile-time discipline beats runtime
  checks", aligns with L15's "resolved at compile time".

### ada.md (Ada/SPARK, 12-gap walk)

- Memory model: Ada access types are nullable by default (69-81). SPARK 2018
  adds a Rust-inspired ownership model: "Assignment between access objects is a
  **move**" (344-345), read-only sharing is allowed (347), read-write needs
  exclusive ownership (348), and "Deallocation transfers ownership to the
  deallocator; subsequent use is a flow-analysis error" (351-352). Freeing is
  explicit (`Unchecked_Deallocation`, implied at 351). The proof is
  compile-time.
- Compile-time vs runtime: Ada inserts runtime `Constraint_Error` checks. SPARK
  proves them away (228-232). Stack overflow is "one of the few runtime errors
  SPARK does not guarantee to be absent" (179-181).
- Borrow: the whole SPARK ownership model (368-372), flow analysis (121-123),
  ranged subtypes (222-226), and bronze/silver/gold tiers (514-516).
- Avoid: runtime constraint checks (487-488), implicit null init (491-492), and
  `Suppress` (493-494).
- Status: reference file. It does not address automatic freeing or arenas.
  Recursive structures (lists, trees) are called "the hardest cases"
  (364-366).

### ada-deep-dive.md (whole Ada language)

- Memory model: not a memory file. Relevant pieces are protected objects that
  "compose with affine ownership beautifully" (459-462), `Storage_Pool` as an
  aspect (492), representation clauses for layout (688-714), and profiles
  (`embedded` = no heap; `realtime` = no allocation) (793-799).
- Compile-time vs runtime: static expressions (650-660), elaboration order
  (662-667), and profiles enforced by the compiler (783-785).
- Borrow: distinct types (I-01; 128-138 names `TokenId`, `NodeId`, `TypeId`),
  `static N` generics (682-684), `@repr` (722-731), profiles (793-803), and
  `others =>` aggregates (564-568).
- Avoid: exceptions, tagged-type OO, rendezvous, `pragma Suppress`, and runtime
  constraint checks (858-869).
- Status: pre-L3/L4/L6. The A7 samples use the removed `int` type and the
  unapproved `inout` mode (216-218, 565).
- DOD relevance (inference): distinct index types plus `@repr` are the
  typed-handle and layout primitives a data-oriented memory model would need.
  `Storage_Pool` is Ada's per-type allocator hook, the closest thing in the file
  to Odin/Zig allocators, but the file does not develop it.

### austral.md

- Memory model: strict linear types. A linear value "must be used exactly once"
  and "Cannot be discarded silently" (31-35). "a linear value cannot be
  discarded by going out of scope" (152). Freeing is explicit: `destroy(buf)`
  is required or it is a compile error (156-160). References `&T`/`&!T` have
  lexical lifetimes (166-169).
- Compile-time vs runtime: all linearity checking is compile-time. The checker
  is "about **600 lines of code**" (10-11, 173-177). Capabilities are linear
  values for effects (60-79).
- Borrow: the claim that a small checker is tractable (220-222), and an
  explicit destruction discipline that forbids silent leaks (223-224).
- Avoid: strict linearity as "too verbose" (230-231), lexical lifetimes
  (232), and capability effects for v1 (233).
- Status: its "`del p` ... analog of Austral's `destroy(p)`" (181-183) assumes
  explicit freeing. That is in tension with L15's "automatic".

### cyclone.md

- Memory model: lexically scoped regions. `region r; ... rnew(r, 0)`, and "region
  r is freed" at scope end (148-154). Region annotations are "**inferred by
  default**" (156-157). Fat pointers `T ?` carry `(ptr, size)` (100-103).
  The file also cites "Safe Manual Memory Management in Cyclone" (27), but does
  not detail it. (inf, external: that paper covers unique pointers and dynamic
  regions.)
- Compile-time vs runtime: region lifetimes are checked statically. Bulk free
  happens at scope exit (runtime, O(1) per region, inference). Fat-pointer
  bounds checks are runtime: "~5–10 % runtime overhead" (105-106).
- Borrow: lexical regions with inference as the "fallback for allocations that
  don't fit affine ownership" (168-171). "Combine with the recursion ban to get
  a bounded region tree" (222-224). Annotate at signatures and infer bodies
  (251-255). The 8% porting cost is a benchmark (161-163).
- Avoid: full region polymorphism (185-189, 235-237), `_unsafe_cast` (238),
  and runtime fat-pointer checks (239-240).
- Status: the most L15-relevant file (inference). Regions and arenas are the
  Jai/Odin/Zig idiom made safe at compile time. The file frames them as a
  secondary fallback, and L15 may promote them to primary.

### hylo.md

- Memory model: mutable value semantics. The four modes are `let`, `inout`,
  `sink`, and `set` (128-133). "**references exist only at function
  boundaries.** You cannot store a reference in a variable or field" (135-136).
  The file does not describe freeing. Inference: values are destroyed at scope
  end or on `sink`, so freeing is automatic and deterministic.
- Compile-time vs runtime: exclusivity is "checked at the call site,
  intra-procedurally. No borrow checker needed" (150-151). The model is
  intra-procedural (223-224).
- Borrow: "essentially **the whole model**" (164-166, 200-207).
- Cost: "references cannot be stored. Most idioms that need stored references
  (callbacks, observers, linked structures) need to be rewritten using indices
  or owning containers" (228-231).
- Avoid: the `unsafe` escape (211), and its lack of refinement and stack
  budgets (213-214).
- Status: the headline pre-L15 model. The mode syntax is not approved under L6
  (decisions.md:55-56, 87). Hylo's value semantics (inference: no shared
  mutable graph, so no cycles) plus indices is a natural fit for DOD.

### inko-koka-verona.md

- **Inko:** single ownership, "isolated heap" per thread, "**No GC** —
  deterministic destruction at scope exit", and no borrow checker (17-22). Borrow
  isolated heaps with move-only channels (26-29) and deterministic destruction
  (33-35).
- **Koka / Perceus:** "at compile time, every value has a use count; the
  compiler inserts the minimal number of refcount adjustments. Many adjustments
  are statically elided. No tracing GC" (67-70). Borrow compile-time refcount
  elision (78-82). The file advises against "Reference counting as the
  memory-management strategy (A7 uses ownership + region scopes)" (86-87).
- **Verona:** "Regions as first-class — every object belongs to a region;
  regions can be sent between threads" (109-111). "Compile-time concurrency
  safety" (114-115). Paused as of 2024 (103).
- Cross-cut: "**The 'no GC, no borrow checker' design point is real and
  reachable.**" (174-175). "Compile-time elision for whatever runtime mechanism
  is chosen" (170-173).
- Status: pre-L15. Perceus is the closest thing in the whole set to "like
  garbage collection ... resolved compile-time". Under L15 the "don't use RC"
  advice (86-87) may invert (inference). Perceus still pays runtime increments
  where elision fails, and is blind to cycles (inference, not stated in file).

### mojo.md

- Memory model: `borrowed` (default), `inout`, and `owned` conventions (32-36),
  argument exclusivity (64-69), and `Lifetime[...]` inferred at signatures
  (126-129). Freeing is not described. Inference: ASAP destruction of owned
  values.
- Compile-time vs runtime: exclusivity is static "where possible. Runtime
  fallback is rare" (68-69). OOB and div-by-zero are runtime traps (91-92,
  104).
- Borrow: no call-site sigils (43-45, 133-136), the `owned` keyword (136), and
  the existence proof that this is productizable (171-173).
- Avoid: Python syntax, MLIR, and default-borrowed params (140-145, 177-179).
- Status: "doing exactly what A7 plans" (183), meaning the pre-L15/L6 plan. No
  DOD, arena, or cycle content.

### pony.md

- Memory model: six reference capabilities (`iso`, `trn`, `ref`, `val`, `box`,
  `tag`) (30-37). `iso` is consumed explicitly (158-173). The file claims
  concurrency safety "without locks, without a GC pause, without lifetimes"
  (8-9). **External fact to verify:** Pony has a per-actor tracing GC (ORCA).
  The file does not mention it, and "without a GC pause" is not "without a GC".
- Compile-time vs runtime: capability checks are compile-time, "no runtime
  cost" (62-63). Collection is runtime (external).
- Borrow: capabilities for concurrency (220-222), `recover` blocks (80-86),
  `consume` (175-177), and a reduced four-cap set `iso`, `val`, `ref`, `tag`
  (246-248).
- Avoid: all six caps, since learning takes "weeks" (204-206, 230-231), and
  unions in place of `Option`/`Result` (234-235).
- Status: a concurrency reference, not a memory-freeing reference. Division by
  zero "returns zero" (109-110), which is a precedent for defined-value
  semantics.

### rust.md

- Memory model: affine by default, `Copy` opt-out, `&T`/`&mut T` borrowing,
  lifetimes, and a `Drop` destructor at scope exit (289-299).
- Compile-time vs runtime: borrow checking is compile-time. OOB panics at
  runtime (203-211). Overflow panics in debug and wraps in release (174-175).
- Borrow: affine-by-default plus `Copy` opt-out, "ownership is a property of
  *bindings*" (309-312), and `Send`/`Sync` (321-323).
- Avoid: lifetimes and the borrow checker (314-317), `unsafe`, `as`, and
  `unwrap` (410-417).
- Hard edge: Rust "accepts strictly more programs": stored `&mut T`, returned
  `&T`, borrowing iterators, and `Rc<T>`/`Arc<T>` (426-433).
- Status: "The `Drop` trait — A7's `del` operator is explicit; auto-drop via
  `Drop` is opt-in convenience. Decision: probably keep explicit `del` for now"
  (324-326). Under L15, automatic scope-exit drop seems required, so this
  verdict is likely stale (inference).

### swift.md

- Memory model: reference counting for class types (15-16, 267-268).
  `borrowing`/`consuming`/`inout` modes (32-38) and noncopyable types (SE-0390)
  (40-44). A consumed-but-unused parameter is "Dropped at end of scope
  (triggers deinit)" (56).
- Compile-time vs runtime: the Law of Exclusivity is "Enforced statically where
  possible, dynamically (with a runtime check) otherwise" (67-71). Overflow,
  OOB, and div-by-zero trap (128, 140, 151-153).
- Borrow: keyword names (240-241), `if let`/`??` (245-246), and `indices`
  (247-248).
- Avoid: `!` force-unwrap, the default overflow trap, default-copyable types,
  and the runtime exclusivity fallback (256-262).
- Status: a production reference for modes, pre-L6. RC is runtime cost, so it
  is not L15-compatible as the primary mechanism (inference).

### vale.md

- Memory model: generational references. A heap object header holds a
  generation that "increments on each free" (32-33). A reference remembers the
  generation, and a mismatch on deref causes a panic (38-46). Ownership tracking
  elides most checks (40-42, 106-110). "Region borrow checking" elides all
  checks inside a region (112-114).
- Compile-time vs runtime: mostly compile-time, with a residual runtime check
  that "survives for a small fraction of accesses" (48-50). Reported cost is
  "over 2× faster than reference counting" (59-60).
- Borrow: the grimoire taxonomy (143-166, 183-185), check elision via ownership
  (186-188), and region borrow checking (189-190).
- Avoid: "The runtime generational check" (194-195).
- Status: an explicitly rejected fallback "not a Phase A–E target" (200-212).
  Its claim that OOB is caught by the generation check (92-94) looks doubtful
  (inference: generation checks validate object liveness, not index bounds).
  Verify before citing. Generational *indices* into arrays are the DOD handle
  pattern (inference, not stated).

### zig.md

- Memory model: "Zig **has no ownership system**. Manual allocator pattern:
  every allocation takes an `Allocator` argument; the user calls `destroy`
  explicitly. Aliasing and UAF are the programmer's problem" (248-251).
- Compile-time vs runtime: Debug and ReleaseSafe check overflow, OOB, null, and
  casts at runtime. ReleaseFast turns these checks into UB (27-50). `comptime`
  covers static parameters (227-242).
- Borrow: `*T`/`?*T` lowering (100-103), `+%`/`+|`/`@addWithOverflow` (171-174),
  `s.ptr[i]` after a proof (187-192), `undefined` (126-128), `try` (215-217),
  and `@cImport` (269-275).
- Avoid in emission: bare `.?`, `s[i]`, `+`, `-`, `*`, and `<<` on opaque
  operands, `@panic`, `unreachable`, and unproved `@intCast` (305-315).
- Status: backend contract (317-326). Its memory section is one paragraph. The
  allocator-parameter style that L15 names is not analyzed for safety or
  automation.

---

## 2. Comparison table

"n/a" means not addressed in the file. `(inf)` marks my inference or general
knowledge outside the file.

| Language | Automatic freeing mechanism | Compile-time vs runtime cost | Aliasing rule | Cycles handling | Regions / arenas | Handles / generational refs | Annotation burden | DOD friendliness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ada / SPARK | n/a in file; explicit deallocation described (ada.md:351-352) (inf: Ada has Controlled/Finalize types, not in file) | SPARK proof compile-time; Ada runtime `Constraint_Error` (228-232) | Move on assign; many readers or one writer (344-348) | n/a; recursive structures "hardest" (364-366) | `Storage_Pool` aspect named only (ada-deep-dive.md:492) | n/a; distinct index types possible (ada-deep-dive.md:128-138) | High for proof tiers; bronze tier lower (ada.md:514-516) | `@repr`/rep clauses, profiles (ada-deep-dive.md:688-738, 793-799); DOD n/a |
| Austral | None. Explicit `destroy`, compile error if forgotten (austral.md:156-160) | All compile-time; ~600-line checker (10-11) | Linear: no dup, no share; `&T`/`&!T` lexical (31-35, 166-169) | n/a (inf: linearity makes cycles hard to form) | n/a | n/a | High: every linear value handled; "too verbose" (230-231) | n/a |
| Cyclone | Region bulk free at scope exit (cyclone.md:148-154) | Region check compile-time; fat pointers 5–10% runtime (105-106) | n/a in file; region-typed pointers, aliasing unrestricted inside a region (inf) | n/a (inf: a region frees whole cycles together) | **Yes**, lexical regions, inferred (146-166) | n/a | Low: ~0.5% of lines; 8% porting (161-163, 244-249) | n/a in file (inf: regions are arenas, good for batch/frame data) |
| Hylo | n/a in file (inf: scope-end destruction of values) | Compile-time, intra-procedural (150-151, 223-224) | No storable refs; call-site exclusivity (135-138, 147-151) | n/a (inf: value semantics, no reference cycles) | n/a | Indices / owning containers replace stored refs (228-231) | Modes on params only; no lifetimes (220-222) | n/a (inf: indices + values fit SoA) |
| Inko | Deterministic destruction at scope exit, no GC (inko-koka-verona.md:17-22) | n/a detail; "no borrow checker" (21) | Single owner; isolated per-thread heaps (17-20) | n/a | Per-thread isolated heap (17-18) | n/a | n/a ("no lifetime annotations", 21) | n/a |
| Koka (Perceus) | RC with compile-time inserted, elided ops (67-70) | Runtime RC ops where elision fails; no tracing GC (69-70) | n/a (functional purity, 152-153) | n/a (inf: RC leaks cycles) | n/a | n/a | n/a (inf: none for memory) | n/a |
| Verona | Region ownership (109-111) | Compile-time concurrency safety (114-115) | Single-owner regions; cross-region refs restricted (112-113) | n/a | **Yes**, first-class regions sent between threads (109-111) | n/a | n/a ("research-grade", 129-130) | n/a |
| Mojo | n/a in file | Static exclusivity; "runtime fallback is rare" (68-69) | `inout` excludes other refs (64-66) | n/a | n/a | n/a | Low: no caller sigils (43-45) | n/a |
| Pony | n/a in file (external: per-actor GC, ORCA) | Caps compile-time, "no runtime cost" (62-63) | Six caps; `iso` unique, `val` immutable shared (30-60) | n/a | n/a | n/a | High: six caps, "weeks" (204-206) | n/a |
| Rust | `Drop` at scope exit (rust.md:298-299) | Borrow check compile-time; OOB/overflow runtime (174-175, 203-211) | Many `&T` xor one `&mut T` (294-295) | n/a (inf: `Rc` cycles leak, `Weak` needed) | n/a | n/a (`Rc`/`Arc` mentioned, 432-433) | Lifetimes at some signatures (296-297) | n/a |
| Swift | RC classes; noncopyable deinit at scope end (swift.md:15-16, 56) | Static exclusivity plus runtime fallback (67-71) | Law of Exclusivity (67) | n/a (inf: RC cycles need `weak`) | n/a | n/a | Modes required for noncopyable (40-44) | n/a |
| Vale | n/a detail (owning refs); gen check guards non-owning (30-46) | Mostly elided; residual runtime check, >2× faster than RC (48-60) | Owning vs non-owning refs (inf); region borrow (112-114) | n/a | Region borrow checking (112-114) | **Yes**, generational references (30-46) | n/a ("no lifetime annotations", 208) | n/a (inf: gen indices are the DOD handle idiom) |
| Zig | **None.** Explicit `Allocator` + `destroy` (zig.md:248-251) | No ownership checks; runtime safety in Debug/ReleaseSafe, UB in ReleaseFast (27-50) | None ("programmer's problem", 250-251) | n/a | n/a in file (inf: stdlib `ArenaAllocator`) | n/a | Allocator threading (inf) | n/a in file (inf: high, the reference DOD systems language) |

---

## 3. Memory ideas relevant to L15 (automatic, compile-time, data-oriented, no runtime GC)

1. **Lexical regions with inference (Cyclone).**
   - Where: cyclone.md:146-166, 175-183, 222-224, 244-249.
   - Mechanism: allocate into a named region, freed in bulk at scope end.
     Inference picks the region, and signatures carry cross-region annotations.
   - Costs: 8% of lines changed, "only 6 % (of the 8 %) were region
     annotations" (161-163). Runtime cost is O(1) bulk free (inference).
   - Limits: no region polymorphism in the proposed form (185-189). Objects that
     outlive their region must be copied out or allocated higher (inference).
   - L15 fit (inference): the most direct compile-time-safe version of the
     Jai/Odin/Zig arena and temp-allocator idiom. The recursion ban gives "a
     bounded region tree" (222-224).
2. **Mutable value semantics plus indices (Hylo).**
   - Where: hylo.md:126-151, 228-231.
   - Mechanism: no storable references. Values own their storage, and "linked
     structures ... rewritten using indices or owning containers" (229-231).
   - Costs: all checks intra-procedural (223-224). Some Rust idioms are
     unportable (rust.md:426-438).
   - Limits: callbacks, observers, and graphs need index or handle rewrites.
   - L15 fit (inference): automatic scope-based destruction with no runtime
     machinery. Indices into owning arrays are the core DOD pattern. The mode
     syntax is still gated (decisions.md:55-56, 87).
3. **Perceus compile-time RC elision (Koka).**
   - Where: inko-koka-verona.md:65-70, 78-82.
   - Mechanism: the compiler computes use counts and inserts "the minimal number
     of refcount adjustments", and many are "statically elided" (67-70).
   - Costs: residual runtime increments and decrements plus a count word per
     object (inference).
   - Limits: the file says A7 should not use RC (85-87). Cycles leak (inference).
   - L15 fit (inference): the most "GC-like" automatic model in the set.
     "Everything resolved compile-time" is only partly true, since residual RC
     ops are runtime. The elision *technique* is reusable even without RC
     (80-82).
4. **Generational references and handles (Vale).**
   - Where: vale.md:30-60, 104-114, 200-208.
   - Mechanism: a generation header plus a remembered generation, with a check
     on deref unless ownership or region analysis proves liveness.
   - Costs: "one load + comparison" per unelided deref (205). ">2× faster than
     RC" (59-60).
   - Limits: the residual check "*can* panic" (129-130). The file rejects it
     under the old contract (194-195).
   - L15 fit (inference): generational indices into pooled arrays are the
     standard DOD handle. Whether one cold-path check is acceptable under
     "everything resolved compile-time" is a user question.
5. **Region borrow checking (Vale), overlapping with Cyclone.**
   - Where: vale.md:112-114, 189-190.
   - Mechanism: a region-scoped discipline "proves swaths of code free-free,
     eliding all generation checks within the region".
   - Costs and limits: n/a in file.
   - L15 fit (inference): lets handle checks vanish in hot loops over frozen
     data, which suits DOD batch passes.
6. **Deterministic scope-exit destruction without GC (Inko, Rust `Drop`, Swift
   noncopyable).**
   - Where: inko-koka-verona.md:17-22, 33-35; rust.md:298-299; swift.md:56.
   - Mechanism: a single owner, and destruction at scope end or on move.
   - Costs: none at runtime beyond the destructor itself (inference).
   - Limits: requires ownership tracking. Shared ownership needs something extra
     (`Rc`, rust.md:432-433).
   - L15 fit (inference): this is "automatic" at compile time. It conflicts with
     the explicit-`del` verdicts (rust.md:324-326, austral.md:181-183).
7. **Isolated heaps and sendable regions (Inko, Verona).**
   - Where: inko-koka-verona.md:17-29, 109-122, 166-169.
   - Mechanism: each thread or region owns its objects, and ownership transfers
     in bulk.
   - Costs and limits: n/a in file. Verona is paused (103).
   - L15 fit (inference): unifies arenas with concurrency (L1 includes
     concurrency). A tensor arena could move between workers as one transfer.
8. **Linear types forbidding silent leaks (Austral).**
   - Where: austral.md:147-164, 220-224, 245-247.
   - Mechanism: use-count tracking, requiring exactly one use at scope exit
     (53-54).
   - Costs: a ~600-line checker (173-177). User-side verbosity (230-231).
   - L15 fit (inference): contrary to "automatic" unless destruction is
     auto-inserted. The small-checker lesson still applies.
9. **SPARK move semantics on access types.**
   - Where: ada.md:339-376.
   - Mechanism: move on assign and flow-analysis use-after-free detection, fully
     compile-time.
   - Limits: deallocation is still explicit (351-352). Recursive structures are
     hard (364-366).
10. **Profiles restricting allocation (Ada).**
    - Where: ada-deep-dive.md:787-803.
    - Mechanism: `embedded` (no heap) and `realtime` (no allocation) profiles
      enforced by the compiler.
    - L15 fit (inference): a way to declare per-module "arena-only" or
      "no-heap" disciplines for DOD hot paths.
11. **Layout control and distinct index types (Ada).**
    - Where: ada-deep-dive.md:128-138 (`NodeId`, `TypeId`), 688-738 (`@repr`).
    - L15 fit (inference): typed handles plus explicit layout are prerequisites
      for SoA and pool-based DOD.
12. **Proof-driven check elision in emission (Zig contract).**
    - Where: zig.md:184-192, 317-326; inko-koka-verona.md:170-173.
    - Mechanism: A7 proves the condition, then emits unchecked Zig.
    - L15 fit (inference): whatever memory model is chosen, the emitted Zig must
      stay ReleaseFast-clean. Memory-safety proofs must lower to plain
      allocator calls.

---

## 4. Claims that conflict with L15 / L16 / other locked decisions

### L15: automatic, compile-time, Jai/Odin/Zig style

- **Tension (explicit freeing vs automatic):**
  - rust.md:324-326: "A7's `del` operator is explicit; auto-drop via `Drop` is
    opt-in convenience. Decision: probably keep explicit `del` for now."
  - austral.md:181-183: "A7's `del p` consuming `p` is the analog of Austral's
    `destroy(p)`." austral.md:223-224: "`del p` is the analog; forbid silent
    leak."
  - austral.md:187-189 describes A7's plan as "`del`-then-drop-on-scope-exit",
    which is partly automatic. The tension is with `del` as the main tool, not a
    hard conflict.
- **Tension (RC dismissed, though it is the most GC-like compile-time-elided
  option):** inko-koka-verona.md:85-87: "Reference counting as the
  memory-management strategy (A7 uses ownership + region scopes)." Not an
  outright conflict. L15 does not pick a mechanism, but the premise
  "A7 uses ownership + region scopes" is unapproved.
- **Tension (regions as fallback, not primary):** cyclone.md:168-171: "the
  **fallback for allocations that don't fit affine ownership**".
- **Tension (Zig-style allocation dismissed):** zig.md:248-251: "Aliasing and
  UAF are the programmer's problem." zig.md:253-254: "the ownership system ...
  lives at the A7 level only." L15 names Zig as the style target.
- **Conflict (runtime checks in the mechanism):**
  - vale.md:7-9: "a few survive as cold-path runtime checks"
  - swift.md:67-71: exclusivity "dynamically (with a runtime check) otherwise"
  - swift.md:198-203: "Swift uses runtime exclusivity checks as a fallback"
  - inko-koka-verona.md:57-60: Koka's "reference-counted runtime"
  - All of these contradict "everything is resolved compile-time" if adopted.
    The files themselves reject Vale and Swift runtime checks, which is
    consistent with L15.
- **External fact to verify (not a file claim):** pony.md:8-9, "without a GC
  pause". Pony uses a runtime per-actor GC (ORCA), so Pony is not a
  no-GC precedent.

### L16: IEEE floats, NaN/inf ordinary values

- ada.md:402-407: "the `'Valid` check is the runtime form of A7's `Fin::new`"
  and "A7 wraps in `Fin<F>` at the type level."
- rust.md:346-347: "the silent propagation of NaN/inf. A7 requires `Fin<f64>`
  for code that wants total arithmetic."
- zig.md:263: "`Fin<F>` is A7-level only."
- ada-deep-dive.md:921 ("Gap 11 finite floats") and ada.md:384-388 frame NaN/inf
  as something to guard.
- decisions.md:79 already supersedes D.001's "No NaN, no inf". An opt-in
  `Fin<F>` library type might survive L16. A mandatory one does not (inference).
- Not conflicts (neutral IEEE mentions): hylo.md:176, swift.md:217, mojo.md:149,
  vale.md:133, pony.md:183, cyclone.md:195.

### L5: Odin-style defined wrapping for `+ - *`

- ada.md:228-232: "A7 skips straight to the proof — anything not provable must
  be rewritten by the user (via `checked_add` etc.)"
- rust.md:195-197: "Rust defaults to 'wrap in release' — A7's contract requires
  either a range proof or an explicit method." rust.md:418-419:
  "Default-wrap-in-release arithmetic — A7 requires explicit discipline."
- swift.md:257-258: "Default-trap-on-overflow with no static proof — A7 wants
  the proof or the explicit operator."
- zig.md:176-178: "emitting bare `+` on opaque operands. A7's range tracker
  proves the operands fit; if it can't, the user picks one of the explicit
  forms." zig.md:309: "Bare `+`/`-`/`*`/`<<` on opaque integers."
- README.md:68-76 treats ranged arithmetic as the plan.
- Already superseded in part: decisions.md:86 (SAFETY_CONTRACT.md:54). Note
  that zig.md:171-174 (`+%` lowering) is *compatible* with L5. Wrapping `+`
  would lower to `+%`. The `<<` part is outside L5's scope (decisions.md:52-54).

### L6: explicit mutation principle only; no mode syntax approved

- hylo.md:164-166: "essentially **the whole model**. The four modes, the
  no-storable-references rule". hylo.md:200-203.
- swift.md:190-194: modes map to "A7's `borrow`/`consume`/`inout`".
- mojo.md:187-190: "Three parameter modes (`borrowed` / `inout` / `owned`)".
- README.md:49-56: "A7's plan to skip lifetimes and use parameter modes only".
- ada-deep-dive.md:217-218: `pub fn push(s: inout Stack, x: int)`, which uses
  unapproved `inout`.
- decisions.md:87: "Proposed D.040, D.041 and D.049: parameter-mode keywords,
  inferred modes, no storable references | Not accepted".
- Related (project rule, CLAUDE.md "no public address-of/deref operators"):
  hylo.md:147 `swap(&a, &a)` is Hylo syntax, not an A7 sample. It is fine as a
  quote, but should not be copied into A7 examples.

### L3 / L4: no `int`/`number`; explicit widths

- ada-deep-dive.md:217-218: `x: int`, `-> int`.
- ada-deep-dive.md:565: `let days = [12]int{ jan: 31, feb: 28, others: 31 }`.
- ada-deep-dive.md:122-126 discusses `i32` "general integers", which is fine.

### Other drift vs current direction (not locked decisions, but stale premises)

- README.md:120 "no `unsafe`" and rust.md:410 "A7 has no escape hatch". These
  are consistent with the old contract. L15 does not decide them.
- README.md:109-110: "`extern fn ... -> Result<T, E>` discipline matches the
  industry consensus". Not locked anywhere in decisions.md.

---

## 5. Hard cases and counterexamples mentioned

- **Stored references, callbacks, observers, and linked structures** need
  indices or owning containers under Hylo (hylo.md:228-231).
- **Linked lists and trees** are "the hardest cases" for SPARK ownership
  (ada.md:364-366). The repo already ports them without recursion
  (`examples/025_linked_list.a7`, `026_binary_tree.a7` per CLAUDE.md).
- **Rust-only programs:** storing `&mut T` in a struct, returning `&T`,
  borrowing iterator adapters, and `Rc`/`Arc` shared ownership (rust.md:426-433).
  "Heavy uses of iterators with borrowed-state may need rewrites" (437-438).
- **Cross-region references and region polymorphism** (cyclone.md:156-157,
  185-189). A7 would ship lexical regions without polymorphism, so a function
  that returns data allocated in the caller's region is the hard case
  (inference).
- **Exclusivity that static analysis can't discharge.** Swift falls back to
  runtime (swift.md:67-71). Mojo's fallback is "rare" (mojo.md:68-69). A7 has
  no fallback, so these programs must be rejected (inference).
- **Unelidable liveness checks:** the Vale cold path (vale.md:48-50, 118-122).
- **Stack overflow** is not proved absent even by SPARK (ada.md:179-181). Zig
  offers no max-stack analysis (zig.md:149-151).
- **Six-capability learning curve of "weeks"** (pony.md:204-206).
- **Strict linearity verbosity:** leaks become compile errors, but every value
  needs explicit handling (austral.md:152-164, 187-189).
- **Fat-pointer runtime overhead of 5–10%** (cyclone.md:105-106).
- **The generation check catching OOB** (vale.md:92-94) is a questionable
  claim, possibly a counterexample to its own accuracy (inference).
- **Protected objects** "compose with affine ownership" (ada-deep-dive.md:
  459-462). Shared mutable state across tasks is the open hard case for any
  arena or ownership model (inference).
- **Not in the files (inference):** reference cycles (graphs, doubly linked
  lists, parent pointers) under RC or ownership, and long-lived large buffers
  such as tensors, optimizer state, and checkpoints (L7-L10) that do not fit
  lexical scopes.

---

## 6. Open questions for the user brainstorm

0. L15's wording pulls two ways: "something like garbage collection" vs "as
   jai, odin and zig", which use manual allocators and no GC. Does the user
   mean GC *ergonomics* (the programmer never writes free) delivered through
   Jai/Odin/Zig *mechanics* (arenas, allocator parameters,
   compiler-inserted frees)? Or something else?
1. Does L15's "automatic" retire explicit `del`
   (rust.md:324-326, austral.md:181-183)? Or does `del` stay as an early-release
   option on top of automatic scope-exit destruction?
2. What is the primary mechanism: (a) ownership plus scope-exit destruction
   (Hylo/Inko), (b) lexical regions/arenas with inference (Cyclone), (c)
   Perceus-style RC with compile-time elision (Koka), or (d) a layered
   combination? Should regions be primary rather than the "fallback" of
   cyclone.md:168-171?
3. Does "everything resolved compile-time" allow *any* residual runtime cost:
   RC increments (Perceus), one generation compare (Vale), or a bulk arena
   reset? Where is the line between "runtime collector" (forbidden) and
   "compiler-inserted deterministic frees" (allowed)?
4. What is the cycle policy? Forbid shared-reference cycles by construction
   (value semantics, handles), free them with their region, or require weak
   handles?
5. What is the public reference form, given no address-of/deref and no stored
   refs yet? Should it be typed indices or handles (hylo.md:228-231,
   ada-deep-dive.md:128-138), generational handles (vale.md:30-46), or neither?
   If generational, is a checked deref acceptable, or must a proof elide it?
6. How should Jai/Odin/Zig allocator style surface? Choices include an explicit
   `Allocator` parameter (zig.md:248-251), an implicit context allocator, or
   compiler-chosen arenas. Is a "temporary allocator" reset per frame, request,
   or training step a language concept?
7. DOD layout: should the memory model come with SoA/`@repr` layout control
   (ada-deep-dive.md:688-738) and pooled collections as first-class citizens?
8. AI (L7-L10): tensors, grads, optimizer state, and checkpoint buffers are
   large and long-lived, while autodiff tapes are per-step and arena-shaped
   (inference). Does the memory model need a "step arena" plus a "persistent
   parameter store" split?
9. Concurrency (L1): should arenas or regions be the unit sent between threads
   (Verona, inko-koka-verona.md:109-122; Inko 26-29)?
10. Should leaks be compile errors (Austral linearity, austral.md:152-160), or
    can drop be implicit?
11. Should profiles restrict allocation per module, such as `@profile(no_heap)`
    for hot loops (ada-deep-dive.md:793-799)?
12. Should Odin and Jai comparative files be written before deciding, given
    L14 ("research belongs in repository docs") and the absence of both from
    `comparative/`?
13. Should the stale "A7 can steal" verdicts in these files (sections 4 above)
    be annotated as superseded by L5/L6/L15/L16, as decisions.md already does for
    other material?

---

## 7. External references worth following up

Cited in the files:

- Perceus: "Garbage Free Reference Counting with Reuse" (PLDI 2021).
  https://www.microsoft.com/en-us/research/uploads/prod/2020/11/perceus-tr-v1.pdf
  (inko-koka-verona.md:96). This is the key reference for GC-like
  compile-time-resolved RC.
- Cyclone regions (Grossman et al., PLDI 2002).
  https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf
  (cyclone.md:26, 213).
- "Safe Manual Memory Management in Cyclone" (Swamy et al.).
  https://www.cs.umd.edu/projects/PL/cyclone/scp.pdf (cyclone.md:27).
  (inf, external: covers unique pointers and dynamic regions.)
- "Cyclone: A safe dialect of C" (USENIX 2002) (cyclone.md:28). Grossman's
  thesis (cyclone.md:29).
- Racordon et al., "Implementation Strategies for Mutable Value Semantics"
  (JOT 2022). https://www.jot.fm/issues/issue_2022_02/article2.pdf (hylo.md:20).
- "Borrow Checking Hylo" (SPLASH/IWACO 2023) (hylo.md:194).
  "Memory Safety without Lifetime Parameters" (safecpp.org) (hylo.md:21).
- Vale generational references. https://verdagon.dev/blog/generational-references
  (vale.md:23).
- Vale grimoire, 14 approaches. https://verdagon.dev/grimoire/grimoire
  (vale.md:24, 145-161). Items 7 (regions), 8 (Higher-RAII), and 10 (hybrid
  generational memory) are directly relevant.
- "Making C++ Memory-Safe Without Borrow Checking, RC, or Tracing GC"
  (vale.md:25).
- Project Verona papers.
  https://www.microsoft.com/en-us/research/project/project-verona/
  (inko-koka-verona.md:141).
- Inko docs. https://docs.inko-lang.org/ (inko-koka-verona.md:50).
- Dross et al., "Recursive Data Structures in SPARK" (2020) (ada.md:29, 364).
  SPARK UG §5.9 on pointers and ownership (ada.md:28).
- Austral linear types tutorial and "What Austral Proves" (austral.md:19, 23).
- Swift SE-0176, SE-0377, SE-0390, SE-0432 (swift.md:22-25). WWDC24
  "Consume noncopyable types" (swift.md:26).
- Mojo manual on ownership and lifetimes (mojo.md:21-22).
- Pony reference capabilities (pony.md:19-22).
- Zig docs, Memory section. https://ziglang.org/documentation/master/#Memory
  (zig.md:19, 284).
- Rust NLL RFC 2094 and Polonius (rust.md:22-23).

Not cited in the files but needed for L15 (my suggestions, unverified here):

- Odin docs on allocators, `context.allocator`, and `context.temp_allocator`.
  Jai's temporary storage and custom allocators.
- Tofte-Talpin region inference / MLKit (the origin of region inference that
  Cyclone builds on).
- Lobster's compile-time reference counting. Pony's ORCA GC paper (to confirm
  that Pony is not a no-GC precedent).
- Rust ECS and arena crates (e.g. slotmap, bumpalo) as DOD handle and arena
  practice.
