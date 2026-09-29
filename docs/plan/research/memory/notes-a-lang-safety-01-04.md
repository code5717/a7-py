> **Source:** Claude Code reading subagent, group A, full read of saved repository research.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../decisions.md).

# Brainstorm notes A: docs/lang-safety/01-04 vs L15 (compile-time, data-oriented automatic memory)

Scope: `docs/lang-safety/01-invisicaps.md` (970 lines), `02-sanitizers.md` (652),
`03-hardware.md` (300), `04-comparison.md` (140). I read all four files in full.
For context I also checked `docs/lang-safety/README.md` (reading status plus the
contract, lines 1-26) and `docs/plan/decisions.md` (L1-L16).
Citations use `file:line`. "Inference:" marks my own reasoning, not claims made
by the docs.

Series-level status (README.md:3-8): "This directory preserves safety-design research,
proposals, accepted design decisions, and review snapshots. Acceptance of a design
decision does not establish that the compiler implements it." Files 01-04 are
unmodified in the working tree. Only README.md has uncommitted changes.

---

## 1. Per-file summaries

### 01-invisicaps.md: status: research (external system study)
- A deep study of Fil-C. InvisiCaps attach a capability (`lower`, a header holding `upper` and an aux word) to every pointer while keeping `sizeof(T*)==8`. Pointers at rest keep their capabilities in per-object aux allocations (01:30-44, 82-225).
- Temporal safety comes from FUGC, a concurrent, non-moving, accurate collector with Dijkstra store barriers, soft handshakes and pollchecks. `free()` only sets `upper:=lower`, and the GC later repoints stale capabilities to a "free singleton" (01:357-433).
- Cost: "1.5× slower than C in good cases and about 4× slower in worst cases" (01:46-47). A disassembly walkthrough breaks down the per-access cost (01:554-727).
- It self-identifies as "research notes — not affiliated with Fil-C" (01:10-14). The README calls it a study of a runtime system "and why A7 doesn't need one" (README table row 01).
- It closes with take-aways for a designer (01:940-970). #2, "Use-after-free is a GC problem, not a checking problem", is the most direct challenge to L15.

### 02-sanitizers.md: status: research (baseline survey)
- Surveys ASan (1:8 shadow, redzones, quarantine), LSan (mark-sweep at exit), MSan (bit-exact init shadow with origin tracking), TSan, HWASAN, UBSan, CFI, `-fbounds-safety`, SafeStack/SCS/PAC (02:48-609).
- Framing: these are "debug instruments", "*not* full memory-safety languages" (02:10-14).
- §10 draws cross-cutting lessons: sanitizers are dynamic, not static; quarantine gives no UAF guarantee under grooming; concurrency is hardest; tagging is probabilistic; use UBSan-trap as the arithmetic baseline (02:612-648).
- Some A7 advice (02:643-648) is stale with respect to L5 and to the README contract (see §3).

### 03-hardware.md: status: research, with mild proposal content
- Covers CHERI (128+1-bit capabilities, software revocation for temporal safety), ARM MTE (4-bit tags per 16 B granule, probabilistic, retag on free), SPARC ADI, Intel LAM/CET, and ARM PAC (03:35-262).
- §6 proposes emitting PAC/BTI/CET flags through the backend. It calls MTE a "library concern" and CHERI out of scope (03:266-297).
- It asserts A7 "does not let user code mint pointers from integers and *does* control its own allocator (A7 does both: no unsafe casts, runtime owns memory)" (03:292-294). That claim is unverified and in tension with L15 (see §3).

### 04-comparison.md: status: synthesis / proposal-flavored (includes a stale A7 status row)
- Contains a coverage matrix, a cost matrix, a decision tree, and "four ideas worth stealing" (04:14-138).
- Ideas: wide pointers in locals and narrow ones at ABIs (4.1); aux tables keyed by capability (4.2); slices over pointers (4.3); "Use-after-free needs a collector or a sweep" (4.4).
- The decision tree recommends "Optional GC for cycles / lifetimes you can't prove" for new languages (04:70). That directly conflicts with L15.
- The A7 row (04:35) is out of date ("no threads yet", "no shared mutable") and malformed: it has 9 cells against an 8-column header. The cells after "Type" are shifted.

---

## 2. Memory-management ideas relevant to L15

Each entry gives the source, the mechanism, the compile-time vs runtime split, cost, and limits. "Inference:" lines are my adaptation to A7.

**M1. Metadata only for objects that contain pointers.** Source: 01:183-185, 953-955.
- Mechanism: "If an object has no pointer fields, its `aux_word` is NULL… Strings and pixel buffers pay zero space overhead."
- Compile-time vs runtime: the type/layout decision is static, but the aux lookups happen at runtime (one extra load per pointer load, 01:687-692).
- Cost: zero for plain-old-data (POD) buffers.
- Limits: in Fil-C the metadata is kept alive only by the GC.
- Inference: in a DOD language this becomes a static type trait ("contains references: yes/no"). POD structure-of-arrays (SoA) columns and tensor storage need no lifetime tracking at all, so the analysis burden falls only on reference-bearing types. This favors designs where reference-bearing data is rare (indices/handles into columns).

**M2. The capability lives with the pointer, not the address.** Source: 01:945-948; 04:103-110.
- Mechanism: metadata is reachable from the pointer value, which avoids a global shadow table and its synchronization.
- Runtime in Fil-C.
- Inference: the L15 analog is a handle that carries its own static provenance (a type-level arena or pool id) instead of a global lookup. Provenance lives in the type, not at runtime.

**M3. Local escape analysis → stack allocation.** Source: 01:505-506.
- Mechanism: "`alloca`s that SROA cannot promote can still be stack-allocated if FilPizlonator's analysis proves they don't escape."
- Compile-time analysis; the runtime effect is fewer heap allocations.
- Cost: compiler complexity only.
- Limits: intra-procedural and conservative.
- Inference: this is the core L15 primitive, "resolved compile-time", generalized as escape analysis → stack / caller frame / arena placement.

**M4. Provenance lattice (⊥ / Definite(C) / ⊤).** Source: 01:523-546, 957-959.
- Mechanism: an intra-procedural abstract interpretation recovers which allocation an integer came from. Merging different capabilities gives ⊤, and ⊤ is sticky.
- Compile-time, zero runtime cost.
- Limits: a load through a global resets to ⊥ (01:548-551, example 20 at 01:346).
- Inference: the same lattice shape works for "which region/arena does this reference belong to". ⊤ means a compile error under L15 (no runtime fallback). The global-load reset corresponds to references stored in long-lived structures, which is exactly where L15 needs a rule.

**M5. `free()` as a capability narrowing + delayed reclamation.** Source: 01:288-297, 425-433, 949-953.
- Mechanism: `free` sets `upper:=lower`, and the GC repoints heap copies to a singleton before reuse.
- Entirely runtime, requiring a GC.
- Limits: needs a collector. It conflicts with L15 as-is.
- Inference: the non-GC analog is generational handles (index + generation checked at use) or compile-time arena-lifetime typing. Generational checks are still a runtime cost, so L15's "everything compile-time" would need to say whether an O(1) generation check counts as a runtime collector (it does not collect, but it does check at runtime).

**M6. Zero-initialize all allocations.** Source: 01:811, 837.
- Runtime memset. Its cost is not quantified in the doc.
- Inference: definite-assignment analysis (README row, edge-cases/03) is the compile-time alternative. A zero-init default is DOD-friendly for SoA buffers.

**M7. Escaping data promoted to the heap.** Source: 01:351, 814.
- Mechanism: "variadic args live in a heap-allocated readonly object that outlives the frame".
- The decision is static, but lifetime is managed at runtime by the GC.
- Limits: without a GC this becomes a leak or needs an owner.
- Inference: under L15, "promote on escape" must name a destination (the caller's arena or an explicit owner).

**M8. ASan quarantine.** Source: 02:123-131, 623-629.
- Mechanism: freed chunks are poisoned (`0xfd`) and held in a FIFO (default 256 MB) before reuse.
- Runtime, debug only.
- Cost: ~2× CPU and ~3× memory (02:150-154).
- Limits: "Pour 100 million allocations through it and the freed chunk is reused" (02:624-626).
- Inference: this is a candidate debug-profile check for arena reset / pool release in A7, not a v1 safety mechanism.

**M9. Stack redzones for use-after-return and use-after-scope.** Source: 02:94-95, 133-146.
- Runtime shadow bytes `0xf5`/`0xf6`.
- Inference: these are exactly the hazards a no-address-of, no-storable-reference A7 must reject statically. Their existence shows these bug classes are real in C-like code that lets references outlive a frame.

**M10. LSan mark-sweep at exit.** Source: 02:170-198.
- A runtime leak report with conservative roots.
- Limits: "misses leaks of objects still reachable from a global… ('dead' but not 'lost')" (02:197-198).
- Inference: a debug-profile leak check for arenas/pools that are never reset. L15 without a GC must decide whether leaks are safety errors (they are not memory-unsafe) or lint.

**M11. MSan origin tracking.** Source: 02:225-231.
- Runtime propagation of allocation sites.
- Inference: the compile-time analog is diagnostics that name the allocation/arena origin of a rejected reference ("allocated at X, arena reset at Y, used at Z").

**M12. Wide locals, narrow ABI.** Source: 02:567-585; 04:94-101.
- Mechanism: locals are `__bidi_indexable`, ABI-visible pointers are `__single`, and the compiler enforces pointer and bound updates "side by side with no side effects between them."
- Mostly compile-time, with runtime bounds traps.
- Cost: "low (single-digit %)" (04:51).
- Inference: A7 slices already play this role. For L15, arena/lifetime provenance could be "wide" inside a function (inferred) and must be explicit or annotated at ABI and struct-field boundaries. This is the same concentration-of-annotations argument.

**M13. Slices over raw pointers.** Source: 04:112-120.
- Mechanism: "not expose raw pointers to user code at all — keep them inside the runtime where the compiler can prove bounds statically."
- Compile-time plus hoisted checks.
- Consistent with the no-address-of rule. Directly DOD-friendly (index-based access).

**M14. Three options for UAF.** Source: 04:122-138.
- Options: a collector/sweep; forbid the escape (borrow checker); probabilistic hardware.
- It suggests "region-based allocation, or a single-cycle generational collector" (04:136-137).
- Inference: L15 selects option 2 plus regions. The collector half of 04:137 is ruled out.

**M15. Allocator retag on free (MTE) and revocation sweeps (CHERI/Cornucopia).** Source: 03:78-79, 147, 289-290.
- Runtime, hardware- or allocator-assisted.
- Inference: only relevant as an optional hardening layer for an A7-owned allocator. Not an L15 mechanism.

**M16. Non-moving keeps concurrency cheap.** Source: 01:382-383.
- Inference: if L15 uses handles/indices, compaction (moving) becomes possible without invalidating references, which a pointer-based design cannot do cheaply. This is a DOD advantage to raise.

**M17. Static ownership replaces TSan.** Source: 02:630-634.
- Mechanism: "A static ownership / borrow discipline (Rust) avoids the entire shadow-cell apparatus."
- Compile-time. Relevant to L1 concurrency plus L15 (arena ownership across threads).

**M18. What L15 gives up versus Fil-C.** Source: 01:352, 963-967.
- FUGC reclaims a "Pure leak (1 trillion bytes allocated without free)".
- 01:963-967: "The open question is which Fil-C-style guarantees an A7 program *gives up* when it cannot afford the runtime machinery".
- Inference: under L15, arbitrary graphs with unbounded lifetimes and no owner are not automatically reclaimed. The design must restrict or explicitly own them.

---

## 3. Conflicts with L15, L16 or other locked decisions

**C1 (L15).** 04:69-70: "Need runtime checks for unavoidable dynamic cases? … → Optional GC for cycles / lifetimes you can't prove." A runtime GC is excluded by L15.

**C2 (L15).** 04:134-138: "whether a small amount of runtime help (e.g. region-based allocation, or a single-cycle generational collector) buys enough simplicity". The collector option conflicts with L15. The region option fits.

**C3 (L15 tension).** 04:124-125: "No amount of static analysis catches every UAF in code that lets pointers escape into data structures." Under L15 this forces either banning such escapes or using runtime-checked handles. The latter is runtime, though not a collector.

**C4 (L15 tension).** 01:949-953: "**Use-after-free is a GC problem, not a checking problem.** A pure checking pass cannot guarantee that a freed capability stays recognisably freed once its memory is reused, unless an accurate collector is keeping the capabilities reachable."
- Inference: this is true for C-style free-able pointers. L15 must avoid that model entirely (no user-visible free of individually referenced objects), not attempt to check it.

**C5 (L15, factual drift).** 03:292-294: "(A7 does both: no unsafe casts, runtime owns memory)". L15 says no runtime collector, and README.md:21-25 says "no `unsafe` escape hatch". "Runtime owns memory" is unverified and misleading under L15.
- Inference: L9's "A7 runtime" covers tensors and autodiff, not general memory. Needs rewording.

**C6 (L1 concurrency; stale).** 04:35 A7 row: "✅ (no shared mutable) | ✅ (no threads yet)". L1 puts concurrency in v1. The row also has an extra cell (9 values vs 8 header columns), so the per-column claims are misaligned.

**C7 (L5 wrapping).** 02:643-646: "UBSan-trap mode is the right baseline for any AOT compiler that emits unchecked arithmetic… prevents the 'signed overflow turned silent infinite loop' class". L5 defines wrapping for `+ - *`, so a signed-overflow trap would contradict it. Per the L5 scope limit, the advice still applies to division, shifts and casts.

**C8 (internal to the series contract).** 02:646-648: "the corresponding setting in Zig (`-O ReleaseSafe` keeps checks; `-O ReleaseFast` drops them) is the analog". README.md:21-25 says emitted Zig "remains memory-safe when compiled with `zig build -O ReleaseFast`… Memory safety is a property of the emitted source, not of the backend's flags." Relying on ReleaseSafe contradicts that.

**C9 (L16, minor).** 02:418 lists `-fsanitize=float-divide-by-zero` and 02:419 lists float→int overflow as UB checks.
- Under L16 (IEEE; NaN/inf are ordinary values), float division by zero is defined and must not trap. 02:445-446 already excludes it from the `undefined` group, so no direct conflict.
- Float→int conversion of NaN, inf or out-of-range values stays a real hazard. Zig `@intFromFloat` is illegal behavior there (inference from Zig semantics, not stated in the doc).
- Related, outside these four files: README lists `edge-cases/11-finite-floats.md` ("`Fin<F>` and NaN/inf discipline"), which conflicts with L16. decisions.md:79 already supersedes D.001's "No NaN, no inf".

**C10 (A7 recursion ban, overclaim).** 04:133-135: "A7's existing recursion ban is in the spirit of the second option: shrink the set of programs to one where the lifetime analysis can be total." Similar wording at 01:967-970.
- Inference: the recursion ban bounds stack depth and makes call graphs acyclic. It does not make heap/escape lifetime analysis total; loops plus explicit stacks can still build arbitrary graphs. Do not cite the ban as the L15 foundation.

**C11 (no address-of/deref; consistent, noted for completeness).** 04:119-120 ("*not* expose raw pointers to user code") and 03:292 agree with the no-public-address-of rule. 01 §10's inttoptr machinery is irrelevant if A7 never mints references from integers.

**C12 (L15 vs Fil-C adoption).** 01:40-41: "calling `free()` is legal but optional". 01:30-44 as a whole describes GC-backed safety. This is fine as research, but should never be read as an A7 direction. The README row already says "why A7 doesn't need one".

---

## 4. Hard cases / counterexamples mentioned

**Escapes**
- UAF where the pointer escaped into another object (01:343, example 17).
- `va_list` escaping its frame is made legal by heap promotion (01:351).
- Escapes into data structures defeat static UAF analysis (04:124-125).
- Use-after-return and use-after-scope (02:94-95, 02:52).

**Lifetimes / reuse**
- UAF after 100M reallocations (heap grooming) (01:342, example 16).
- Quarantine is bypassable (02:623-629).
- "Dead but not lost" leaks via globals (02:197-198).
- A pure leak of a trillion bytes is reclaimed only thanks to the GC (01:352).

**Aliasing / provenance**
- OOB into another object (01:328).
- Provenance lost through a global `uintptr_t` (01:346, 548-551).
- int↔ptr union ping-pong (01:334-337).
- Overwriting the intval while keeping the capability (01:335).
- Function pointers as data (01:338-340).

**Concurrency**
- Non-atomic pointer race, "panics about once in a hundred runs" (01:259-261, 344).
- The atomic box and "time travel" stale reads (01:253-257).
- TSan sees races only if they occur in the run (02:292-299).
- MTE tag updates "have their own ordering rules" (03:149).
- Races are relations between two accesses, not a single access (02:630-633).

**Cycles**
- Only 04:70 ("Optional GC for cycles") mentions them. There is no worked example.
- Inference: cycles are the classic case where pure ownership fails. L15 needs an answer: index/handle graphs, arena-scoped cycles freed wholesale, or a ban.

**Arenas / regions**
- Mentioned only as "region-based allocation" (04:136). No mechanism is given.
- Inference: the arena reset-while-referenced case (the arena analog of UAF) is not covered in these files.

**Handles / generational references**
- Not mentioned in 01-04. The README says 06-compile-time-safety.md covers "region inference, generational references".

**Tensors / autodiff (L7-L9)**
- Not mentioned in 01-04.
- Inference: tensor buffers are POD (M1), so aliasing and views, not pointer metadata, are the hard case. Autodiff tapes are long-lived, graph-shaped, and grow per step. They are a prime arena-per-step candidate and a likely L15 stress test.

**Stack**
- Stack tagging needs compiler opt-in (03:147).
- The Pizderson-frame workaround (01:863-865).
- Stack-overflow check in the prologue (01:579-580). Inference: this relates to A7's edge-cases/05 stack-budget work.

**Interop**
- Whole-program instrumentation requirements (02:237-241, 294-297, 619-622). Uninstrumented or non-A7 code breaks dynamic guarantees.
- Hardening flags exist for "non-language parts" (02:639-642).

---

## 5. Open questions for the brainstorm

1. **Allowed runtime work.** Does L15's "everything resolved compile-time" permit O(1) runtime checks that are not collection? Examples: generation checks on handles, bounds checks, arena-epoch checks. Or must every lifetime fact be proven statically? (Relates to M5, C3.)
2. **Unit of automatic memory.** Scope-inferred arenas (region inference), explicit arena values passed like Odin's `context.allocator` / Zig's allocator param, per-frame/per-iteration arenas, or typed pools of handles? Which one is "automatic"?
3. **Cycles and graphs.** Should graphs (linked lists, trees, autodiff tapes; see examples/025, 026) be expressed only as index/handle graphs inside a pool that is freed wholesale? Or may references form cycles within one arena?
4. **Escape destination.** When a value escapes a function, is the destination always inferred (caller's arena), or must the signature name it at ABI/struct-field boundaries, like `-fbounds-safety` concentrating annotations at ABIs (M12)?
5. **Stored references.** May struct fields hold references at all under L15 + L6? Or only handles/indices, making M1's "no reference-bearing types" the default?
6. **Leaks.** Is a leak (an arena never reset, a pool that grows forever) a compile error, a lint, or acceptable? LSan's "dead but not lost" shows leaks are not a memory-safety property (02:197-198).
7. **Debug profile.** Should A7 offer a debug-only runtime layer (quarantine-style arena poisoning, leak report at exit) even though release is fully static? Would that contradict the README "no-trap under ReleaseFast" contract?
8. **Concurrency (L1).** How do arenas and handles cross threads? Transfer of an isolated arena, like Pony's `iso` or the README's "isolated owned data" in parameter-modes.md, versus shared immutable pools. Is a race on a handle's generation counter possible?
9. **Tensors (L9).** Should tensor storage be its own allocator class, reference-counted at runtime (which conflicts with L15) or scoped to a training-step arena? How are views/strided aliases of one buffer tracked statically?
10. **Relocation.** With handles, is compaction/relocation (a DOD win, M16) in scope, or are addresses stable?
11. **Doc hygiene.** Should 03:292-294 ("runtime owns memory"), 04:35 (stale, malformed A7 row), 04:70/04:137 (GC suggestions) and 02:646-648 (ReleaseSafe advice) be annotated as superseded by L15/L1/L5 per the approval rule? This would be a docs change and needs approval.

---

## 6. External references worth following up

**Fil-C (for what L15 is choosing not to do, and for reusable static-analysis tricks)**
- https://fil-c.org/invisicaps.html, invisicaps_by_example.html, gimso.html, fugc.html, compiler.html, compiler_example.html (01:18-26)
- Manifesto: https://github.com/pizlonator/fil-c/blob/deluge/Manifesto.md (01:26)
- FilPizlonator.cpp: escape analysis and the inttoptr lattice (01:896)
- Safepoints: https://fil-c.org/safepoints.html (01:888)

**Bounds / metadata**
- SoftBound PLDI'09 (01:739, 925)
- SoftBound+CETS revisited 2024 (01:745, 927)
- Dagstuhl 2015 survey (01:744, 928)
- Checked C fat pointers (01:790, 929)
- No-FAT ISCA'21 (01:794, 930)
- Clang `-fbounds-safety`: https://clang.llvm.org/docs/BoundsSafety.html (02:28). Most relevant to M12.

**GC background (for contrast)**
- Dijkstra concurrent GC (01:931)
- Doligez-Leroy / Doligez-Gonthier (01:932)
- Henderson accurate GC frames (01:933)
- Pizlo, Fiji VM / Schism (01:934)
- WebKit libpas docs (01:938); its allocator design may inform an A7-owned pool allocator (inference)

**Sanitizers**
- ASan ATC'12 paper (02:30); HWASAN arXiv 1802.09517 (02:31)
- google/sanitizers wiki pages (02:18-24)
- UBSan and CFI docs (02:26-27)

**Hardware**
- CHERI project and FAQ (03:24-25); Morello (03:26)
- CheriBSD security analysis https://arxiv.org/html/2601.19074 (01:767)
- Cornucopia revocation (03:79). No URL is given. Worth finding, since it is a sweep-based temporal model (inference).
- ARM MTE intro (03:27); Intel LAM reference (03:29); SPARC ADI (03:30); Linux arm64 tagged pointers (03:31)

**Languages named**
- Rust (borrow checker, Send/Sync): 02:633, 04:34, 04:129
- Cyclone: 01:795. Its region system is directly relevant to L15-style compile-time regions (inference); follow up.
- Go slices: 04:114; Checked C: 01:786

**Not in these files, but L15 names them**
- Jai, Odin, Zig: none of 01-04 mentions them.
- Inference: follow up on Odin `context.allocator` / temp allocator, Zig allocator-parameter conventions, Jai's `temporary_storage`, and Vale generational references / Hylo mutable value semantics (README points to 06-compile-time-safety.md and comparative/hylo.md).
