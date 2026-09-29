> **Source:** Claude Code reading subagent, group B, full read of saved repository research.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../decisions.md).

# Brainstorm notes B: lang-safety 05, 06, 07, codex-review, compile-time-knowledge

Source dir: `/home/cx89/Projects/pl-dev/a7-py/docs/lang-safety/`. All five files
read in full. Line numbers refer to the files as of 2026-09-15.
Short names: **05** = `05-for-a7.md` (822 lines), **06** = `06-compile-time-safety.md`
(567), **07** = `07-language-review.md` (568), **CX** = `codex-review.md` (152),
**CTK** = `compile-time-knowledge.md` (576).
Locked decisions come from `docs/plan/decisions.md:33-48` (L1-L16).
"(inference)" marks my own reasoning. Everything else is sourced.

---

## 1. Per-file summaries

### 05-for-a7.md: "Take-aways for A7: Zero Runtime Errors" (status: proposal/contract. The contract text is repeated in `lang-safety/README.md:20-26`; README:5-8 says acceptance does not mean it is implemented)
- Defines the "zero-runtime-error contract". Every hazard must be a compile error or a typed value (`?T`, `Result`, ranged ints, capability tokens) (05:21-26). Emitted Zig must be safe under `-O ReleaseFast` (05:13-19).
- Hazard table (05:82-100). UAF/double-free/leak are handled by "Affine ownership + region inference". Overflow, div-by-zero and NaN/inf are compile errors unless proved, or typed returns.
- Toolbox (05:142-269): definite assignment; non-null `ptr T` vs `?ptr T`; affine ownership for `new`; `inout`/`borrow` parameter modes (no stored refs); pattern-proved slice indexing; optional Cyclone-style `region` scopes (Phase 2 / Phase 6).
- Codegen discipline for every risky op (05:412-661): `s.ptr[i]`, `+%`, `@addWithOverflow`, `@divTrunc` on `NonZero`, `allocator.create(..) catch null`. Also a proposed "no-trap" codegen test (05:625-636).
- Phased plan (05:682-757) and anti-recommendations (05:759-772), which say no borrow checker, no tracing GC and no Fil-C runtime.
- Internal inconsistency: Phase 0 is "1 week" at 05:689 but "1-2 days" at 05:811. Examples use `int` indices (05:307) and `NonZero<int>` (05:282), which predates L4.

### 06-compile-time-safety.md: technique catalogue (status: research reference)
- A taxonomy of 13-14 static techniques ordered by cost (06:19-33). Covers definite assignment, non-null, sum types, linear/affine, borrow+lifetimes, regions, generational refs (Vale), mutable value semantics (Hylo), reference capabilities (Pony), refinement, dependent, effects, SPARK, comptime.
- Each entry gives what it catches, the mechanism, languages that ship it, the cost, and "For A7" notes. Examples: borrow checking is "out of scope" (06:193-194); regions are "the most natural fit" (06:229-231); MVS is "the model to study" (06:316-318); Pony is "probably overkill" (06:348-350).
- Synthesis (06:530-535): the minimum viable set is "§1 + §2 + §3 + §4 + §6 (or §8) + §10 (focused on bounds)".
- Numbering drift: the table row #13 is Comptime (06:33), but section 13 is SPARK (06:449) and section 14 is Comptime (06:480). The 06:231 link targets "05 §3 Phase 2 make del optional", an anchor that does not exist in the current 05.

### 07-language-review.md: codebase audit against contract (status: historical audit snapshot. Its file:line pointers into `a7/` describe the code at the time it was written)
- Finds that current emission is **not** safe under ReleaseFast (07:16-19). It lists 11 gaps (07:27-39). The critical ones are nullable `ref T` lowered to `?*T` with `.?.*`, unrestricted `cast` including int<->ptr, bare `s[i]`, bare `+ - *`, and unchecked `@divTrunc`.
- `del` has no move or alias check (07:272-310). The proposed fix is a move-analysis pass plus `inout`/`borrow` modes that are "Allowed as parameter types only, never as variable / field types" (07:295-296). Codegen already emits `defer if (value_ptr) |p| allocator.destroy(p)` (07:279-280).
- Proposes `Option`/`Result`, a small set of named refinements (`Index($n)`, `NonZero`, `Fin`, `Bounded`) (07:356-361), a stack-budget pass, and `Fin<f64>`.
- Change order puts cast restriction first and affine ownership 10th (07:495-513). Open questions: `?ref T` vs `Option<ref T>`, consume syntax, and where refinements live (07:522-551).
- Minor slip: "The four **Critical** rows (1, 2, 3, 4, 5)" lists five (07:43).

### codex-review.md: external critical review (status: historical review snapshot. README:45 calls it "Saved output of codex's first critical review")
- The file holds the same review **twice**: lines 1-75 and 78-152 are identical, with a stray "tokens used 163,141" at 76-77. Links use another machine's path (`/home/air/Projects/pl/...`) and cite `08-decisions.md` and `parameter-modes.md`.
- Soundness: the contract is aspirational. The D.003 bignum `int` allocates on arithmetic with no failure story (CX:5). `number` as exact reals is "promising magic" (CX:7). Narrowing without cross-variable facts rejects many safe programs, and any analyzer bug becomes UB (CX:9). `borrow` narrowing is only sound with deep immutability (CX:11). FFI breaks "zero runtime errors" (CX:13).
- Ergonomics: users get "SPARK rejection without SPARK's explicit proof vocabulary" (CX:17). Body-inferred parameter modes are "a code-review trap" (CX:21). No storable references blocks graphs, observers, arenas with direct links and views (CX:23).
- Implementation and precedent: the "one pass, few hundred lines" estimate is not credible (CX:37). The stack model is undefined (CX:39). Auto-drop with partial moves is real engineering (CX:41). Swift needed runtime exclusivity checks (CX:61). Inko has a runtime panic when an owner is dropped while borrowed (CX:65).
- Verdict: either add visible proof/API surface, or weaken the guarantee to "no unchecked A7-originated traps for accepted proven patterns; otherwise typed runtime checks" (CX:75).
- Several targets are now resolved by locked decisions: the `int`/`number` critiques by L3/L4, and the inferred modes by L6.

### compile-time-knowledge.md: "the cast is allowed because the compiler knows the number" (status: research principle / proposal. It depends on the CA/CB clusters of `08-decisions.md`)
- Principle (CTK:14-27): an op compiles iff accumulated static knowledge discharges its precondition. Otherwise it is a compile error: "No runtime check is inserted; no `?T` is silently returned".
- Three tiers: sufficient knowledge gives bare emission; recoverable gaps give an error with a fix-it guard; irrecoverable cases give a hard error, e.g. int to ref (CTK:87-159).
- Knowledge-effect table (CTK:68-79): `f(inout x)` resets knowledge and `f(borrow x)` does not. Only data-dependent ops (I/O, parse, FFI, allocation) return `?T`/`Result` (CTK:191-224).
- Theory: abstract interpretation, S4 modal logic, refinement-lite with disjunctive intervals, flow typing (CTK:226-292). Limits in v1: no inter-procedural facts, no relations like `x<y`, no range across pointer derefs (CTK:310-325).
- Written against the pre-L3/L4 type set (`int`, `uint`, `number`) and uses `p.val` (CTK:435). The claimed implementation is "one analysis pass" of "a few hundred lines" plus a new `a7/passes/preconditions.py` (CTK:332-351). That file does not exist (checked `a7/passes/`).

---

## 2. Memory-management ideas relevant to L15

L15, from `decisions.md:47`: automatic memory management, no runtime collector, designed for data-oriented programs, resolved at compile time, in the style of Jai/Odin/Zig.

Note on sources: none of the five files discusses data-oriented design (SoA, arenas as the default, handles) or tensors by name. DOD mappings below are inference.

### 2.1 Affine ownership of heap allocations (move semantics)
- Where: 05:174-198, 05:714-725, 06:133-161, 07:291-294.
- Mechanism: `new` yields an owned value. Passing by value, returning, assigning into a field, or `del` "consumes" it. Reusing a consumed binding is a compile error (07:291-294). The proposal says "a 'moved' flag per binding tracked in the same CFG pass as definite assignment. It is *not* a full borrow checker" (05:195-197).
- Compile time: moved-state dataflow and the double-free/UAF rejection. Runtime: the actual `free` at the consumption point. No header, no count.
- Cost: "Small" language complexity (06:24). The diagnostics are the hard part: "telling the user *which* prior use moved the value" (06:159-160).
- Limits: "The cost in expressiveness: no aliasing. If you need two readers, you need a deeper mechanism" (06:151-154). CX:41 lists partial moves, drop flags at CFG joins, drop order, and interaction with loops and channels.
- (inference) Conditional moves (`if c { consume(p) }`) need either a runtime drop flag, as in Rust, or a rule that rejects them. A runtime drop flag is a tiny runtime residue. Whether that violates "everything resolved compile-time" is a question for the user.

### 2.2 Scope-exit Drop (automatic free)
- Where: 05:90 ("Leak (in scope) | §4 + scope-exit `Drop` ⇒ compile error if a value is unconsumed"); 06:522 ("Leak | §4 (affine + `Drop` on scope exit) | §6 Regions"); 07:306-308 ("Examples with manual `del` need to be rewritten to either rely on scope-exit `Drop` or to move through return-value chains").
- Existing seed: current codegen already emits `defer if (value_ptr) |p| allocator.destroy(p)` (07:279-280).
- Compile time: drop insertion points, driven by ownership state. Runtime: the free calls themselves, the same as hand-written `defer`.
- This is the closest thing in these files to "automatic, GC-like, but compile-time" (inference). It matches Zig's `defer allocator.free` idiom, with the compiler writing the `defer`.
- Limits: 05:90 is ambiguous. It says both "Drop" (automatic) and "compile error if a value is unconsumed", which reads more like linear types. CX:41: "destructor failure must also be impossible or typed."

### 2.3 `inout` / `borrow` parameter modes (mutable value semantics, no stored references)
- Where: 05:200-225, 06:274-318, 07:295-304, CTK:78-79.
- Mechanism: references exist only as parameter-passing modes. Hylo has four modes: `let`, `inout`, `sink`, `set` (06:283-288). An exclusivity check at each call means "an `inout` argument cannot alias any other argument of the same call" (05:217-218). The analysis is "purely intra-procedural — **no lifetime annotations needed**" (05:219-220).
- Compile time: all of it. Runtime: none. The emitted Zig is just `*T` / `*const T` (07:302-304).
- Cost: "Medium" (06:312-314). CX:37 says the combined analysis is far larger than claimed.
- Limits: "you give up free-standing reference values entirely" (06:318-319). CX:23 lists "observer patterns, graph structures, arenas with direct links, callback state, intrusive collections, views into buffers, and many parsers". CX:61 notes that Swift shipped runtime exclusivity checks in Release builds. For opaque values, 05:724-725 falls back to requiring arguments to be "syntactically distinct" (inference: this is weak for `a[i]` vs `a[j]`).
- Relation to L6 (explicit referent mutation): directly relevant. L6 needs an explicit mutation interface. `inout` is one candidate spelling, but mode names still need user approval (decisions.md:21-27).

### 2.4 Region scopes (Tofte-Talpin / Cyclone): arena-style, compile-time escape check
- Where: 05:248-269 (`region tokens ... end ; the region frees here unless returned`), 05:744-747 (Phase 6, optional), 06:198-231, 07:309-310.
- Mechanism: every allocation belongs to a region, regions nest, and a region's allocations are "freed en bloc when the region's scope ends. The type checker proves that no pointer escapes its region" (06:203-205).
- Compile time: region assignment/inference, escape proof, region subtyping. Runtime: bump allocation plus a single bulk free. No per-object headers.
- Cost: "Medium" and "Much smaller than borrow checking" (06:224). The hard part is region subtyping (06:225-227). Evidence: Cyclone porting altered "about 8 % of the code; of the changes, only 6 % (of the 8 %) were region annotations" (06:209-211).
- A7 fit: "the most natural fit given A7's existing 'no recursion ⇒ bounded scope depth' property" (06:229-230). "A7's already-DAG call graph (no recursion) makes the region lattice trivially bounded" (05:266-267).
- Limits: only for "stack-shaped (last-in-first-out, no escape)" lifetimes (06:200-201). 05:269 defers it: "Phase-2 item; ship §3.1–§3.5 first."
- (inference) This is the strongest match to Jai/Odin/Zig practice: temporary allocators, per-frame arenas, arena-per-request. It is also DOD-friendly because contiguous bump allocation gives cache locality. Open problems: (a) memory growth inside long loops until the region ends; (b) the syntax question at 05:262, "unless `return`ed", which implies the region can be promoted to the caller. How that promotion works is unspecified.

### 2.5 Generational references (Vale): mostly static, residual runtime check
- Where: 06:235-270.
- Mechanism: each heap object has a generation word, and each reference remembers the generation it saw. Before a dereference the compiler either proves the generation is unchanged and emits a bare load, or "Falls back to a runtime check (`expected_gen == obj.gen` ? proceed : panic) — cold case" (06:246-249).
- Compile time: the owned-vs-loose analysis. Runtime: "one word per heap object and a compare-and-branch on cold derefs" (06:266-267).
- Result: "compile-time safety is achievable for ~90 % of accesses with a narrow runtime safety net for the rest" (06:268-269). Quoted perf claim: "over twice as fast as reference counting" (06:260-262).
- Conflicts: the runtime check and panic violate the 05 contract (05:769) and arguably L15's "everything resolved compile-time". (inference) Generational *handles* into pools (slot maps) are, however, the standard DOD answer to the "no stored references" limit. A7 could expose handle lookup as a data-dependent op returning `?T` (CTK:191-224 style) instead of a panic. That keeps the runtime check but makes it a typed branch, not a trap.

### 2.6 Indices / handles instead of references
- Where: CX:23 ("The docs admit users must rewrite with indices [parameter-modes.md:249]"). The repo CLAUDE.md points to `examples/025_linked_list.a7` and `examples/026_binary_tree.a7`, which use index-based structures.
- Compile time: type-level distinction of handle types (inference). Runtime: bounds/generation validation. Under 05 rules that would be a `try_get` (05:301-315) returning `?T`.
- (inference) This is the natural DOD substrate (Odin/Jai-style SoA + handles). Its interaction with the bounds-proof system matters: a handle's validity is data-dependent, so every lookup is Tier "data-dependent" → `?T`, unless the pool's lifetime and length are statically tied to the handle.

### 2.7 Reference capabilities (Pony) / isolated heaps for concurrency
- Where: 06:322-350, 05:749-757, CX:33, CX:63, CX:65.
- Mechanism: `iso/trn/ref/val/box/tag` (06:330-337) give race freedom with no GC and no borrow checker.
- Compile time: all capability checks.
- Limits: "six options is a lot" (06:344-346). The planned design drops `val`, so "Large immutable snapshots cannot be shared across tasks in v1 ... config tables, ASTs, bytecode, intern pools, and caches" (CX:33). Inko needs `recover` and has a runtime panic on drop-while-borrowed (CX:65).
- (inference) This bears on L15 whenever tensors or weights are shared across worker threads (L7-L10).

### 2.8 Heap-allocation failure as a typed value
- Where: 05:98, 05:360-377, 05:551-561, CTK:199.
- Mechanism: "`new` *always* returns a nullable; there is no infallible `new`" (05:371). This lowers to `allocator.create(Buf) catch null` (05:555).
- Compile time: forcing the match. Runtime: the allocator call and the branch.
- Limits and friction: (inference) automatic allocations (growable arrays, tensor results, string formatting per CX:31) would each need a failure path. That is ergonomically heavy for an "automatic" model. Alternatives to discuss: preallocated arenas with a statically sized budget, or an OOM-as-process-policy exception.

### 2.9 Static stack budget
- Where: 05:337-358, 05:583-596, 07:375-400.
- Mechanism: recursion is banned, so the call graph is a DAG. The compiler sums frame sizes along the deepest path, enforces `--stack-budget`, and sets the thread stack size to that value.
- Compile time: frame sizes and the DAG longest path. Runtime: setting the stack size at start-up.
- Limits: frames with non-constant `N` are rejected unless bounded (05:356-358). CX:39 adds "large stack arrays, nested generic expansion, backend helper calls, spawned task stack sizes" and notes there is "no computable stack model". (inference) Zig/LLVM frame sizes are only known after backend codegen, so an A7-level estimate cannot be exact. It needs a conservative bound.
- L15 relevance (inference): with DOD stack arrays (`buf: [N]T`, and heap `new [N]T` is rejected per 07:454-456), the stack budget becomes a real memory-planning tool.

### 2.10 Definite assignment (no silent zero-init)
- Where: 05:146-154, 06:41-65, 07:243-270.
- Relevance (inference): for large DOD buffers, the fix at 07:264-266 ("emit a variable's storage only at its assignment site ... `var x: i32 = undefined`") avoids zeroing costs while keeping reads safe. The whole cost is at compile time.

### 2.11 Effect systems: an allocation effect
- Where: 06:420-445. "allocation in a real-time path" (06:423-424) and `| io, alloc` (06:433). "For A7: orthogonal to memory safety ... Defer" (06:443-445).
- (inference) This is relevant to Zig-style "no hidden allocations". An inferred `alloc` effect could let the compiler prove that a hot loop or kernel does not allocate, which is a DOD guarantee.

### 2.12 Comptime / staged evaluation
- Where: 06:480-509. "whether A7 should have a *source-level* `comptime` keyword ... a language-design decision" (06:507-509).
- (inference) L15 names Jai/Zig, both comptime-heavy. Comptime could size arenas, compute SoA layouts, and fix tensor shapes, turning more allocation into static layout.

### 2.13 Explicit anti-recommendations touching memory
- "Build a tracing GC | Compile-time analysis (§3.3 + §3.6) eliminates UAF; GC is unnecessary." (05:766). This is consistent with L15's "no runtime collector".
- "Build a borrow checker | Lifetime annotations are the largest cost in Rust's language spec." (05:765).
- "Build a Fil-C-style runtime" rejected (05:767).
- "Insert silent runtime traps instead of compile errors" rejected (05:769).
- 06:193-194: borrow checking "out of scope unless the language commits to shared mutable state."

---

## 3. Conflicts with L15, L16, and other locked decisions

### vs L16 (IEEE floats; NaN/inf are ordinary values; strict arithmetic)
- 05:95: "Floating-point NaN / inf | Operations return `?f64` (None on non-finite result) OR `Fin<f64>` typed values ⇒ compile error if propagated as plain `f64`"
- 05:379-393 (§4.6): "Arithmetic on bare `f64` is allowed but `f64` itself is a sum type whose `nan` and `inf` cases must be matched before downstream use." (05:392-393)
- 05:779-781 contract paragraph lists "NaN/inf propagation" among the statically rejected hazards.
- 07:38 gap #9 "Floats freely produce NaN / inf | Silent propagation" is treated as a defect. 07:402-426 (§1.11) proposes `Fin<f64>` and `?Fin<T>` returns. 07:511-512 change order item 11.
- 07:356-361 `Fin<$F>` refinement.
- Partially compatible: 05:334-335 float→int casts "use `?int_from(f)` returning null for NaN/inf/out-of-range". (inference) This is compatible with L16 as long as it only guards the conversion, not float arithmetic.

### vs L5 (Odin-style defined wrapping for `+ - *`)
- 05:32-33: the emitted Zig never contains "A bare `a + b` on opaque integers (always `+%`, `+|`, `@addWithOverflow`, or proved-safe `+`)". The emission side is compatible with `+%`. The source rule is not:
- 05:92: "compile error if user uses bare `+` on opaque values"
- 05:323: "`let c1 = a + b                  ; compile error: overflow not proved`"
- 05:329-332: bare `+` only when ranges prove no overflow; otherwise "the user picks `checked_*` / `wrap_*` / `sat_*` explicitly."
- 05:779-780 contract: "integer overflow" is statically rejected.
- 07:200-204: "Otherwise, **compile error** suggesting the user pick one of `a.checked_add(b)`, `a.wrap_add(b)`, `a.sat_add(b)`."
- 06:524 "Integer overflow | §10 Refinement".
- `docs/plan/README.md:229-230` already flags this: "The safety contract's fixed-width arithmetic proof row conflicts with L5 and must change when wrapping lowering lands."
- (Division by zero and `MIN / -1` stay open under G3, `plan/README.md:144`. The `NonZero`/`SafeDivisor` proposal (05:277-299) does not conflict with L5 but is still undecided.)

### vs L3 / L4 (no `number`; explicit-width ints only)
- CTK:62-64: "A declared type like `int` is the initial knowledge: 'this value is a mathematical integer of unknown range.'"
- CTK:167-185 cast table uses `int`, `uint`, `number` (e.g. CTK:171 "`cast(int, n: number)` | none — defaults to trunc").
- 05:280-307 examples: `NonZero<int>`, `fn lookup(s: []int, i: int) -> ?int` with `try_get(i: int)` (05:312). The `int` index also contradicts the repo's `usize` index rule.
- CX:5, CX:7, CX:27, CX:29, CX:31 criticise D.003 bignum `int` and `number`. Those critiques are **resolved/superseded** by L3/L4 and do not need re-litigating.

### vs L15 (automatic, compile-time, no runtime collector)
- 06:235-270 generational references rely on a runtime generation check with panic (06:248-249). That is not "everything resolved compile-time". The file presents it favourably ("a useful compromise", 06:269-270).
- 05:363, 05:371: "`new` *always* returns a nullable; there is no infallible `new`." (inference) This creates friction with *automatic* memory: every implicit allocation would need a surfaced failure path.
- 07:272-310 and 05:88-89 keep `del` as the user-facing consumption primitive. L15 "automatic" suggests `del` becomes optional or rare. (inference) Not a hard conflict, but the default should flip from manual `del` to compiler-inserted drop.
- 05:190: "No recursion → no cyclic ownership graphs to worry about." (inference) **Questionable claim.** Banning recursive *functions* does not ban cyclic *data*: doubly-linked lists, graphs, parent pointers via refs or indices. An automatic compile-time scheme must still say how it handles cycles.
- CX:23 notes "arenas with direct links" are blocked by no-stored-references. (inference) This is in tension with the Jai/Odin/Zig arena style L15 cites, which freely stores pointers into arenas.

### vs L6 (immutable argument bindings; explicit, separately approved referent mutation)
- CX:21 and CX:55 describe a then-"newest direction" where "parameter modes should be inferred from the body". Implicit modes conflict with L6's "explicit" mutation. CX argues against it too.
- 06:296-300 Hylo `swap(x: inout T, y: inout T)` writes `x = y` inside the callee. (inference) Under L6 the *binding* is immutable and only the referent changes, so A7 spelling must distinguish rebinding from writing through. This is a syntax question for approval.
- CTK:78: "`f(inout x)` | `x`'s knowledge reset — `f` may have changed it". This is compatible with L6 if the mutation interface is explicit at the call site. CX:21 argues call-site sigils matter.

### vs "no public address-of / dereference operators"
- 06:302: `swap(&a, &a)    ; compile error: two inout aliases of the same value`. Uses prefix `&`. It is an illustrative Hylo-like snippet, but it should not be copied into A7 docs.
- CTK:435: `ret p.val` uses `.val`, which the repo rules forbid.

### vs "no A7 source recursion"
- No conflict. 06:402-405 shows a recursive Idris `get`, but it is a foreign-language example. 05 and 07 rely on the ban (05:35, 05:339-341, 07:445-447).

### vs L7-L10 (CPU-first A7-owned tensors + autodiff)
- No file mentions tensors, autodiff, SIMD, or accelerator memory. (inference) Latent conflicts:
  - "no stored references" (05:204-206, 07:295-296) vs tensor **views/strides** and an autodiff **tape** that holds references to forward activations;
  - "compile error unless bound proved" (05:238, CTK:23-27) vs runtime-shaped tensors (batch size read from data), where a bounds or shape mismatch is data-dependent;
  - `new` returning `?ptr` (05:371) vs many intermediate tensor allocations per step.

### vs plan-level open items
- 05:13-19 (ReleaseFast as the invariant) vs `plan/README.md:189`: "Choose ReleaseFast after proofs are sound, or ReleaseSafe until memory-model work". The build-mode choice is open in the plan, but 05 treats it as settled.
- CTK:23-27 ("no `?T` is silently returned ... the program does not compile") vs CX:19, which argues that bias makes APIs brittle (slice→array, enum-from-discriminant). CX:49/51 report `08-decisions.md` D.025 vs D.031/D.032 contradicting each other on exactly this.

---

## 4. Hard cases and counterexamples mentioned

Lifetimes / escapes
- "a function building several values and returning all of them by reference" (05:250-252) is the motivating case for regions.
- "Several existing patterns (e.g., transient buffers built up and then handed off) will need region-style scopes" (07:308-310).
- The region escape "unless `return`ed" (05:262) means region promotion to the caller is unspecified.
- Region subtyping, i.e. "when can a `*T in r2` be used where `*T in r1` is expected?" (06:225-227).
- Stack frames with non-constant array sizes (05:356-358); generic expansion and task stacks (CX:39).

Aliasing
- Two readers of an affine value (06:151-154).
- `inout` exclusivity for opaque values forces "syntactically distinct" arguments (05:724-725). (inference) `swap(a[i], a[j])` is the classic hard case.
- `borrow` narrowing is unsound with "aliases, globals, callbacks, FFI, async effects, or interior mutable cells" (CX:11). The Crystal precedent there is repeated method calls after a nil check.
- "Range across pointer dereferences (if the pointer's target was mutated by another path the compiler can't see)" (CTK:320-321).
- Swift needed runtime exclusivity enforcement (CX:61).

Moves / drops
- Partial moves, "precise drop flags at CFG joins, reverse drop order, explicit `del` precedence, moved-field handling, panic-free destructors, and interaction with `return`, loops, and channels" (CX:41).
- Inko: "a runtime panic case when an owned value is dropped while borrows exist" (CX:65).

Cycles / graphs / handles
- "observer patterns, graph structures, arenas with direct links, callback state, intrusive collections, views into buffers, and many parsers" (CX:23).
- (inference) The 05:190 "no cyclic ownership graphs" claim does not cover cyclic data.

Concurrency
- Throughput cliff when sharing large immutable data across tasks without Pony `val` (CX:33).
- Pony needs six capabilities plus `recover` (CX:63). Inko's depth (CX:65).
- 05:753-755 offers two options (channels + value-only sharing, or MVS + actor isolation) and says "Don't pick now" (05:757).

Allocation
- Allocation failure is data-dependent (CX:5, 05:360-377, CTK:199). Formatting may allocate (CX:31).

Proof-system limits that bite memory code
- No cross-function facts in v1 (CTK:312-319, CTK:526-528). Worked counterexample with `x < y` and `y <= s.length` (CTK:463-497).
- "any implementation bug becomes UB because codegen emits bare operations" (CX:9).
- A corrupt FFI call invalidates all proofs (CX:13; 05:105-118).

Tensors
- Not mentioned in any of the five files (see §3 inference).

---

## 5. Open questions for the brainstorm

1. **Default memory shape under L15.** Should the default be compiler-inserted scope-exit drop of owned values (2.2), compile-time-checked regions/arenas (2.4), or both? Examples: arena per function or loop iteration as the default, owned values for anything that escapes.
2. **Is a residual runtime check allowed?** Generational handles (2.5) and conditional-move drop flags (2.1) need a small runtime bit or compare. Does "everything resolved compile-time" forbid these? Or does it only forbid a *collector*, with typed `?T` handle lookups acceptable?
3. **Stored references.** Keep the 05/07 rule that references are parameter modes only (07:295-296)? Or allow region-scoped stored references so arenas can hold direct links (CX:23)? Handles/indices are the alternative. Which one is the DOD primitive?
4. **Cycles.** With no GC, how are cyclic structures expressed: handles into a pool, region-owned graph freed en bloc, or rejected? 05:190's claim needs correcting.
5. **Allocation failure.** Keep "`new` always returns `?ptr`" (05:371)? Or adopt a policy for automatic/implicit allocations: static arena budgets, abort-on-OOM as a documented exception, or allocator-parameter style à la Zig/Odin context allocator?
6. **Explicit allocators (Zig/Odin/Jai style).** Should allocators be visible (context allocator, temp allocator) while freeing is inferred? Or fully hidden? And an `alloc` effect (2.11) to prove hot paths allocation-free?
7. **Region promotion.** How does a value built in an inner region survive to the caller ("unless `return`ed", 05:262): copy-out, region-parameter inference, or caller-supplied arena?
8. **Mutation interface under L6.** `inout`/`borrow` names vs Hylo's `let/inout/sink/set` (06:283-288)? Are modes explicit in signatures and/or at call sites (CX:21)? The approval rule requires examples.
9. **Tensors.** Views, strides, in-place ops, and the autodiff tape all want stored references and aliasing. Are tensors a runtime-managed exception (A7-owned runtime per L9) with their own arena/refcount? Or must they fit the same compile-time scheme?
10. **Concurrency sharing.** Is an immutable-shared (`val`-like) capability needed from day one for model weights and caches (CX:33)?
11. **Contract wording.** Adopt CX:75's weaker guarantee ("no unchecked A7-originated traps for accepted proven patterns; otherwise typed runtime checks")? Keep the 05 absolute contract? And ReleaseFast vs ReleaseSafe (`plan/README.md:189`)?
12. **Stack budget.** Is it worth defining a conservative stack model (2.9, CX:39) now that large stack arrays are the recommended buffer form (heap `new [N]T` is rejected)?
13. **Comptime.** Should A7 add source-level comptime (06:507-509) as a lever for static layout and arena sizing, given L15 names Jai and Zig?

---

## 6. External references worth following up

Papers
- Tofte & Talpin, region inference: <https://www.cs.cmu.edu/~rwh/courses/refinements/papers/TofteTalpin94/region.pdf> (06:554-555)
- Cyclone regions (PLDI '02): <https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf> (06:207, 06:543-544)
- Racordon et al., "Why Mutable Value Semantics?": <https://www.jot.fm/issues/issue_2022_02/article2.pdf> (06:556-557)
- Maranget, "Warnings for Pattern Matching" (06:128-129, no URL)
- Cousot, *Types as Abstract Interpretations*: <https://www.irif.fr/~mellies/mpri/mpri-ens/articles/cousot-types-as-abstract-interpretations.pdf> (CTK:239)
- Liquid Haskell tutorial: <https://ucsd-progsys.github.io/liquidhaskell-tutorial/book.pdf> (06:550-551)

Memory-model practitioner sources (highest priority for L15)
- Vale grimoire of memory-safety techniques: <https://verdagon.dev/grimoire/grimoire> (06:541-542)
- Vale generational references: <https://verdagon.dev/blog/generational-references> (06:263, 06:545-546)
- Hylo intro: <https://hylo-lang.org/introduction/> (06:310, 06:547); CX:69 also cites the Hylo spec/tour
- Pony reference capabilities: <https://tutorial.ponylang.io/reference-capabilities> (06:548-549); CX:63 "passing/sharing"
- Inko memory management + concurrency/recover (CX:65, no URL)
- Mojo ownership docs (CX:69, no URL)
- Swift exclusivity enforcement (Swift 5 runtime checks) (CX:61, no URL)
- Memory Safety without Lifetime Parameters (safecpp): <https://safecpp.org/draft-lifetimes.html> (06:562-563)
- Rust NLL RFC <https://rust-lang.github.io/rfcs/2094-nll.html> and Polonius <https://rust-lang.github.io/polonius/> (06:558-561); Niko Matsakis Polonius update <https://smallcultfollowing.com/babysteps/blog/2023/11/15/polonius-update/> (06:566-567)
- OCaml 2024-era `local_` stack allocation (06:221-222, no URL)
- MLKit (06:220)

Proof / narrowing
- F* tutorial <https://www.fstar-lang.org/tutorial/> (06:552-553); SPARK user guide / proof manual / loop invariants (CX:59, no URL)
- TypeScript narrowing <https://www.typescriptlang.org/docs/handbook/2/narrowing.html> (CTK:286); Crystal <https://crystal-lang.org/> (CTK:282)
- Haskell-for-all Liquid Haskell post <https://www.haskellforall.com/2015/12/compile-time-memory-safety-using-liquid.html> (06:380)
- Sigfpe S4 and partial evaluation <http://blog.sigfpe.com/2006/04/s4-and-partial-evaluation.html> (CTK:254)
- Abstract interpretation (Wikipedia) (CTK:238); Refinement type (Wikipedia) (CTK:263)
- John Regehr blog <https://blog.regehr.org/> (06:564-565)
- V8 BigInt docs, Python C API integers, Rust Clippy `as_conversions` / `cast_possible_truncation` (CX:27, CX:67). These are mostly moot after L3/L4.

In-repo follow-ups referenced but not in this batch
- `docs/lang-safety/08-decisions.md` (D.003, D.020, D.024, D.025, D.031, D.032, D.038, D.039, D.042; CX line refs), `parameter-modes.md` (CX:23 cites :249 for indices and CX:33 cites :330 for lost `val`), `narrowing.md`, `conversions.md`, `HANDOFF.md`, `docs/SAFETY_CONTRACT.md`, `03-hardware.md` §6, `02-sanitizers.md` §6.
- Note for L15 (inference): none of these five files cites Jai, Odin or Zig *memory* practice (arenas, temp/context allocators, SoA). Jai and Zig appear only under comptime (06:499-500, CTK:508). A separate research pass on those is needed.
