> **Source:** Claude Code reading subagent, group F, full read of saved repository research.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../decisions.md).

# F. Plan memory research notes (for the L15/L16 brainstorm)

Sources read in full (every line): 
- `docs/plan/research/memory-design-codex.md` (695 lines) — cited as **CX:line**
- `docs/plan/research/memory-security-glm.md` (345 lines) — cited as **MS:line**
- `docs/plan/research/ownership-zig-odin-glm.md` (222 lines; lines 152-222 are the corrected follow-up that supersedes parts of 9-146) — cited as **OW:line**
- `docs/plan/research/numerical-policy-glm.md` (169 lines) — cited as **NP:line**
- Context: `docs/plan/decisions.md` L1-L16 (lines 33-48), scope limits (52-59), O2 open (66).

All four reports are dated 2026-09-14 and **predate L15 and L16** (both recorded 2026-09-15, decisions.md:47-48). None of them answers "automatic memory management without a runtime collector, resolved at compile time" directly. Where a statement below is my own reading rather than the report's text, it is marked **(inference)**.

---

## 1. Per-file summaries

### 1.1 memory-design-codex.md (Codex CLI)
- **Recommendation:** "an affine ownership core with temporary checked access, deterministic cleanup on defined exits, and explicit allocation failure. Arenas should supplement that model." (CX:13). "Alternative A is the best starting point for A7" (CX:148). Autodiff storage needs a separate choice between T1 session ownership and T2 retained shared storage (CX:13, 506-511).
- **Key idea:** ownership, allocation, and access are three separate choices (CX:61-65). It compares nine models: stack, manual, affine, linear, arena, regions, RC, tracing GC, and COW (CX:67-77). It also covers four whole-language alternatives: A affine, B general borrows, C RC-centred, D tracing GC (CX:141-146).
- **Scope of claims:** "A small source vocabulary is feasible. A small compiler analysis is not." (CX:15). It lists 14 compiler analyses (CX:584-599) that must run over "a typed control-flow representation with stable identities" (CX:601).
- **Lifecycle contract:** covers allocation failure, checked allocation arithmetic, initialization, partial construction, move, replace, partial move, Copy, clone, share, cleanup, fallible close, and abrupt termination (CX:184-198).
- **Status:** "advisory research… approves no language change" (CX:5-6, 11). None of the acceptance scenarios was executed (CX:628).
- **Limits:** Zig 0.16 source came from the local toolchain, not a verified fetch (CX:57). On Jai, "No ownership guarantee or current syntax recommendation is derived" (CX:55). Floats are "unapproved" (CX:25, 561), which L16 has since superseded. GLM owns security validation (CX:662).

### 1.2 memory-security-glm.md (GLM whole-language security)
- **Recommendation:** Q1 option (a), which is "Minimal, syntax-free (recommended first step)" (MS:254). It combines provenance-checked `del` (I-3), scheduled-deletion conflicts (I-4), affine refs with auto-drop (I-5), a no-stack-escape rule (I-6), and rejection of ref-typed copies (MS:131, 254-266). Regions are "(c)… phase-2" (MS:278).
- **Evidence:** it verified soundness holes in today's proof engine. MS-1 has unsound joins (MS:49). MS-2 has calls with no effects (MS:50). MS-3..MS-11 accept unsafe programs (MS:58-66).
- **Proposed invariants:** I-1..I-26 (MS:124-170). There is also a feasibility table separating compile-time, runtime-typed, and environmental cases (MS:178-195).
- **Concurrency:** move-only channels (I-18). Cancellation is "deferred to v2" (MS:158). Deadlock freedom is not claimed (MS:159).
- **Status:** advisory. Code evidence is compile-only, and "no memory-corruption payload was compiled… or run" (MS:338).
- **Limits:** everything in section 6 beyond current checks is "proposed invariants, not implemented behavior" (MS:341). Float policy was open as Q4 (MS:306), which L16 has since resolved.

### 1.3 ownership-zig-odin-glm.md (GLM, two parts)
- **Part 1 (OW:9-146):** argued that Zig/Odin parameter immutability is binding-only with "zero aliasing safety" (OW:28). It recommended choice B, read-only pointee by default (OW:50, 123), and "No storable refs (D.049)" (OW:124).
- **Part 2 correction (OW:152-222) supersedes these points:**
  - It withdraws "binding-only immutability makes safety unfixable" (OW:160).
  - It withdraws "B is uniquely coherent". Ownership is an orthogonal axis (OW:161).
  - Call-effect invalidation is needed "regardless" (OW:162).
  - `p += 1` through `ref` is referent mutation, so SPEC `swap` is legal (OW:163).
  - A blanket ban on `del` for parameters is "policy, not safety necessity" (OW:164).
  - I/O and channel state is mutable memory and needs declared effects (OW:165).
  - Functional-update in-place lowering is conditional (OW:166).
- **Evidence table (OW:173-177):** Zig, Odin and Jai all use **manual** ownership with no aliasing check. The Jai evidence is a "Feb 2023 closed-beta practitioner report — not official" (OW:177).
- **Final framing:** R1 binding immutability; R2 deep immutability of by-value args, enabling "maybe by reference" passing; R3 is the open referent-write fork (OW:187-191).
- **Status and limits:** advisory. Jai claims come from a single 2023 source (OW:179). Nothing in it covers allocation or reclamation. It is about the parameter and permission surface only.

### 1.4 numerical-policy-glm.md (GLM numerics and tensor security)
- **Recommendation:** "IEEE-with-poisoning semantics + f32 master weights/accumulation + bf16-unscaled/f16-dynamic-scaled training with skip-on-nonfinite recovery" (NP:170). N-1..N-4 are at NP:81-92.
- **Memory-relevant requirements R-1..R-12 (NP:98-120):**
  - R-1 checked allocation-size arithmetic.
  - R-2 shape validation.
  - R-3 A7 owns all buffers, with ≥64B alignment and scratchpad sized from native descriptor queries.
  - R-4 threading contract for oneDNN and OpenBLAS.
  - R-5 no storable mutable views, plus a version counter for saved tensors.
  - R-8 typed allocation failure, or runtime arenas with explicit shrink control.
  - R-9 iterative backward pass.
- **Evidence:** PyTorch 2.14 sources (GradScaler, EmptyTensor checked nbytes), oneDNN v3.14 scratchpad and thread rules, OpenBLAS FAQ, ONNX Runtime BFCArena, safetensors, and CVEs (NP:31-75, 165).
- **Status:** advisory. "no tests were run" (NP:165). Items tagged [V] are verified, [I] inferred, [P] proposed (NP:12).
- **Limits:** oneDNN fpmath and accumulation details and OpenBLAS int32 ceilings are unverified (NP:166). A7 facts are at `701c679` (NP:168). Under L16 its IEEE default (NP:24, 90) is now aligned with a locked decision.

---

## 2. Memory-management mechanisms relevant to L15

L15 target (decisions.md:47): "Automatic memory management without a runtime collector, designed for data-oriented programs, resolved at compile time, in the style of Jai, Odin and Zig".

| Mechanism | What the reports say (file:line) | Compile-time vs runtime | Cost | Limits called out |
|---|---|---|---|---|
| **Affine ownership plus generated cleanup** | Model row: "At most one usable owner… Explicit drop or generated cleanup" (CX:71). Alternative A (CX:143, 148). I-5: "scope exit auto-emits `del` for live non-`Copy` bindings in reverse declaration order" (MS:131) | Compile time: move, init, and cleanup-plan analyses (CX:586-595). Runtime: only the generated frees | "Move, initialization, alias, and control-flow analysis. Some shared structures require another representation." (CX:71) | "Existing ref copies change meaning… Arbitrary observer graphs need handles or explicit sharing" (CX:143). Automatic cleanup does not mean no leaks: "Cycles, nontermination, abrupt process death…" (CX:126) |
| **Cleanup ordering and `defer del`** | "reverse declaration order for local owners, LIFO for explicit deferred actions, and a documented field order" (CX:206). `defer del` reserves cleanup and rejects later transfer or duplicate delete (CX:208). I-4 pending scheduled deletion (MS:130) | Compile time | Some accepted programs stop compiling (CX:416) | A deferred action that reads an owner must run before that owner is destroyed (CX:206) |
| **Generated destruction of deep structures** | "Compiler-generated drop functions can accidentally reintroduce unbounded native recursion" (CX:462). "Automatic cleanup cannot assume allocating a worklist will succeed during out-of-memory recovery" (CX:210) | Compile-time plan. The runtime traversal needs a strategy | "pre-reserved work storage, intrusive traversal state, bounded representation, or an allocation-free traversal" (CX:210) | Koka 3.2.3 still has recursive handling for large scanned vectors (CX:212). **(inference)** Arenas and bulk release avoid per-node traversal, which is a strong DOD argument |
| **Provenance-restricted `del`** | I-3: "`del x` compiles only when the value… provably flows from `new` on every path… Emitted `del` nulls the binding" (MS:129) | Compile time, path-sensitive | `del` is limited to straight-line post-`new` code unless alias work lands (MS:129) | A flow-insensitive "ever assigned from new" rule "is unsound and must not ship" (MS:129) |
| **Arenas** | "Allocations remain until reset or arena destruction… Bulk release" (CX:73). "Arenas should supplement that model" (CX:13). "Arenas can support any alternative" (CX:150). I-23: arenas and pools as stdlib ownership types; "arena-allocated storage may not escape the arena's scope" (MS:165). I-22: "per-step scratch allocated from arenas" (MS:162) | Runtime bulk free. Escape checking is compile time (extends I-6) | Cheap alloc and free. Memory is retained until reset | "An arena alone does not prevent escaped pointers. Coarse lifetimes retain memory; resource finalization is separate." (CX:73). ORT BFCArena "never returns memory to the system" and arena growth is a "security-relevant resource-exhaustion knob" (NP:51) |
| **Typed or inferred regions** | "Types and effects constrain cross-region access… Region end" (CX:74). MLKit shows regions can coexist with GC (CX:150). Cyclone is "the proven ancestor of I-23's arena-tied provenance" (MS:211). Regions are "the highest-leverage optional phase-2 add-on" (MS:211). Q1(c) "only if (a)/(b) leave real ergonomic gaps" (MS:278) | Compile time (inference or annotation). Runtime is region-end bulk free | "More analysis and possible annotations" (CX:74) | "Region lifetimes can be too coarse for long training jobs" (CX:74). **(inference)** Pure Tofte–Talpin inference is known to leak on loops, which is why MLKit added GC. That matters for L15's "no runtime collector" |
| **Reference counting / Perceus** | "Every strong reference extends storage lifetime… Count traffic, cycles, destruction cascades, and possible atomic costs" (CX:75). Koka "Precise compiler-inserted RC and uniqueness-based reuse" (CX:91). "Perceus-style drop-timing analysis is the eventual optimization for I-5's auto-drop" (MS:213) | Compile-time insertion. Runtime count operations | RC traffic, atomic costs | "published proof and performance results do not automatically apply to A7's mutation, concurrency, or native kernels" (CX:91) |
| **Tracing GC** | Alternative D (CX:146). Go: GC "does not provide exclusive mutation, deterministic native-resource cleanup, or hard memory bounds" (CX:88, 106) | Runtime | "Collector/runtime implementation, memory headroom, foreign roots, nondeterministic storage reclamation" (CX:146) | Excluded by L15 |
| **Copy-on-write / functional update** | "Mutation can allocate and fail. Hidden copies conflict with predictable allocation unless exposed." (CX:77). `x = f(x)` "may lower in place only when uniqueness… and value semantics are proven; otherwise it copies (or is rejected)" (OW:166) | Compile-time uniqueness analysis, with runtime copy as fallback | Hidden allocation | Codex: "Silently allocating a copy is not an acceptable compatibility fix" (CX:305) |
| **Handles / indices with generations (data-oriented)** | "Use checked indices or generation-bearing handles for shared graph relationships" (CX:157). "A graph can have one owning node container and non-owning indices" (CX:460). "Generation exhaustion must have defined behavior. Silently wrapping a generation counter… is not acceptable" (CX:464). "prefer indices and opaque stable native-buffer owners over general user-authored self-referential structures" (CX:468) | Runtime checked lookup "unless lifetime is statically established" (CX:615) | A generation compare per lookup | Stale-handle rejection needs a runtime check or proof |
| **Escape and borrow restrictions** | "Permit local slices whose lifetimes the compiler can establish. Initially reject borrowed views stored in independently escaping user aggregates" (CX:154-155). I-6 (MS:132). "no storable mutable views — view/borrow objects live only in expression/call scope" (NP:106) | Compile time | Some ergonomics lost (zero-copy parsers need Alternative B, CX:144) | "'No escaping borrowed references' must not become 'no owned linked structures.'" (CX:148) |
| **Exclusivity** | I-16 "enforced **compile-time only**… deliberately stronger than Swift's production model" (MS:152). Swift uses dynamic checks for globals and closures (NP:44). Storage identity, not names: `swap_i32(values[i], values[j])` (CX:317-327) | Compile time. Codex allows recoverable dynamic checks "before the conflicting operation's effects" (CX:454) | Conservative rejection | NP:45: static-only enforcement is "acceptable only if no storable mutable aliases exist" |
| **Allocation failure** | "Return a failure value before publishing a usable owner" (CX:186). `new` is "runtime, typed: `?ref T`" (MS:189). R-8: "All tensor allocations return `Result`/optional… OOM mid-training must leave a clean error, run `defer` cleanups" (NP:112). Container growth and clone keep the original usable (CX:194, 635-636) | Runtime result. Compile time enforces handling | Failure paths everywhere: "Constructors, clone, container growth, tasks, channels, and tensor operations" (CX:186) | "Allocation succeeds — Environmental result; cannot generally be proved" (CX:616) |
| **Checked allocation arithmetic** | "Approved ordinary wrapping arithmetic cannot silently wrap allocation sizes" (CX:187). I-9 size-critical contexts (MS:141). R-1: ordinary `+ - *` results are "ineligible as allocation sizes" and need `checked_mul/checked_add` (NP:98). PyTorch mobile compiles the checks out, "exactly the hazard A7 must never have" (NP:55) | Compile-time obligation or runtime checked op | Checked-op overhead at size computation only | Depends on MS-1, MS-2 and MS-10 being fixed first (NP:98) |
| **Tensor/autograd saved storage** | T1 "A session owns graph nodes, saved storage, and intermediates. Tensor IDs identify session entries" (CX:508). T2 "Tensor objects and tape records retain shared backing storage" with "RC traffic, cycle avoidance, storage-version tracking" (CX:509). Four mutation policies (CX:519-524); "explicit mutation with rejection or recoverable preflight failure… Snapshotting should be explicit, because it allocates" (CX:526). PyTorch version counters (NP:40). R-5 version check at backward (NP:106). I-22 "autograd graph nodes must be heap objects under I-5's drop discipline" (MS:162) | T1: compile-time session ownership plus runtime checked IDs. T2: runtime RC | T1: "Coarse retention, session-oriented APIs, checked IDs" (CX:508) | "A version counter can detect invalidation, but detection after mutation is not equivalent to preventing it" (CX:526). Test: "Graph storage returns to the stated retained baseline after each step" (CX:653) |
| **Native kernel buffers** | "Native kernels should borrow A7-owned storage for a documented interval" with an 8-item contract (CX:563-572). DLPack deleter provenance (CX:576). R-3 "A7 owns all buffers (one allocator…)… alignment contract: ≥64B… Scratchpad/workspace buffers are sized exclusively from descriptor queries" (NP:102). oneDNN: "executing a primitive in a different thread than creation results in segmentation fault" (NP:49). OpenBLAS buffer pool fixed at build time and "exceeding it terminates the program" (NP:50) | Runtime borrow interval with a compile-time contract | Validation at the shim | Workspace "persists between forward/backward" (NP:49). It is a lifetime spanning two calls |
| **Concurrency transfer** | "'Task-private heap' is not sufficient. A receiver must not retain an allocation whose allocator state dies with the sender" (CX:488). Options: "transferable allocator owners, longer-lived shared allocator infrastructure, whole-region transfer, or explicit copying" (CX:488). Failed send returns ownership (CX:398-404). Structured task lifetimes (CX:492). I-18 "Cross-task data crosses by move only" (MS:156). "move-on-spawn, move-on-send… needed regardless" (OW:62, 201) | Compile-time reachable-graph check (CX:597). Runtime queue ownership state machine (CX:476-486) | Channels hold synchronized shared state (CX:490) | "Moving a root variable alone does not establish isolated transfer" (CX:89) |
| **Stack budget** | I-14: with recursion banned, "compile-time maximum stack depth is computable" (MS:148). Codex disagrees: D.053's "exact native stack size" is wrong because of "Native kernels, callbacks, generated destruction, ABI frames" (CX:129, 692) | Compile time plus target qualification | — | Compare CX:619 with MS:188 |
| **Maybe-by-reference passing (Zig/Jai)** | R2: "a by-value argument's bytes are read-only in the callee; the compiler may pass large ones by pointer" (OW:189). Odin "allows Odin to optimize how procedure values are passed" (MS:153) | Compile time | None | I-17: "must not lower immutable params as `noalias` unless an approved exclusivity model holds" (MS:153). Jai's no-alias is "a philosophy, not a check" (OW:179) |

**Data-oriented design coverage gap (inference).** None of the four reports discusses struct-of-arrays layout, bulk or pool allocation per archetype, frame or step allocators as a language default, or Jai/Odin `context.allocator` / `temp_allocator` as an *automatic* mechanism. Odin appears only as "Context conventions do not prove that an allocator or its returned storage outlives its users" (CX:85) and "custom allocators/arenas via context" (MS:208). The DOD-leaning pieces that do appear are generation handles (CX:157, 464), T1 session ownership (CX:508), per-step arenas (MS:162), and ORT arenas (NP:51).

---

## 3. Fit and conflict with L15 and L16

All reports predate L15 and L16. Items are grouped by fit.

### 3.1 Fits L15
- **Codex's baseline:** Alternative A is affine ownership plus automatic cleanup on defined exits (CX:148, 682: "Does cleanup become automatic? Yes, on explicitly defined language exits"). This is a compile-time, no-collector form of automatic memory management. **(inference)** It is the closest match to L15's "like garbage collection… resolved compile-time".
- **GLM's option (a) with I-5 auto-drop:** "This is the SAFETY_CONTRACT 'next ownership phase' expressed without new syntax" (MS:131). This fits both "automatic" and "no new syntax".
- **I-16 compile-time-only exclusivity:** "the A7 contract has no runtime fallback slot" (MS:152). This fits "everything is resolved compile-time".
- **Regions and arenas:** Cyclone-style regions (MS:211, 278) and arena-tied provenance (MS:165). **(inference)** L15's DOD and compile-time emphasis probably promotes regions and arenas from "phase-2 add-on" to a first-class design axis.
- **Per-step scratch arenas for autograd:** I-22 (MS:162), CX:653 retained baseline, and T1 bulk cleanup (CX:508) are DOD-style lifetime grouping.

### 3.2 Conflicts or tensions with L15
1. **RC and GC alternatives.** Alternative C (RC, CX:145) and D (tracing GC, CX:146) are ruled out or constrained by "without a runtime collector". **(inference)** Compile-time-inserted RC (Perceus, CX:91, MS:213) is arguably not a "collector" but still has runtime count traffic. L15 wording does not decide whether it is allowed.
2. **T2 retained tensor storage** relies on "RC traffic, cycle avoidance, storage-version tracking, mutation uniqueness, possible atomic costs" (CX:509). This is in tension with L15. T1 session ownership (CX:508) fits better **(inference)**.
3. **MLKit precedent.** "A checked region system can also coexist with GC, as MLKit research demonstrates" (CX:150). MLKit needed a GC to cover region-inference leaks. That is a direct warning for a pure compile-time region design under L15 **(inference; the reports do not state the leak problem explicitly, though CX:74 notes coarseness)**.
4. **Jai as a precedent.** L15 names Jai. Codex says "Insufficient current authoritative evidence established. No ownership guarantee or current syntax recommendation is derived from Jai" (CX:55). OW:177 quotes Jai as "explicitly 'NOT memory safe'" with manual ownership. Zig and Odin are also "manual" (OW:175-176), and Zig "does not supply A7's ownership proof" (CX:84). **(inference)** "as jai, odin and zig" most plausibly means performance and control style (no hidden runtime, explicit allocators, DOD), not their manual memory-safety model. That reading needs user confirmation.
5. **Hidden allocation.** COW and functional update cause it: "Hidden copies conflict with predictable allocation" (CX:77), and in-place lowering is conditional "otherwise it copies" (OW:166). This conflicts with L15's Zig/Odin-style predictability.
6. **Regions too coarse for long training.** "Region lifetimes can be too coarse for long training jobs" (CX:74). A purely lexical compile-time lifetime scheme may over-retain memory in training loops. This is a tension, not a contradiction.
7. **Runtime arenas.** R-8 "tensors use runtime-managed arenas (ORT-style) with explicit shrink control and a documented never-shrinks-by-default posture" (NP:112). This is not a collector, but its reclamation policy is runtime-configured rather than compile-time resolved **(inference)**.
8. **Runtime generation checks.** "A runtime graph handle still names its entry — Checked lookup unless lifetime is statically established" (CX:615). Dynamic exclusivity preflights appear at CX:454 and CX:526 ("recoverable preflight failure"). These are runtime checks inside a "compile-time resolved" story. They are consistent with L15 only if L15 means "no collector", not "no runtime checks at all" **(inference, open question)**.
9. **Odin/Jai context allocators versus proof.** Odin's "Context conventions do not prove that an allocator or its returned storage outlives its users" (CX:85). Adopting Odin-style implicit allocators under L15 needs an escape and provenance analysis on top (MS:165).
10. **Cancellation disagreement.** The reports disagree with each other. MS:158 defers cancellation to v2. CX:492 proposes structured lifetimes with cooperative cancellation for full v1. This affects what "automatic cleanup" must cover.
11. **Leak claim.** MS:184 classifies "Use-after-free / double-free / leak" as "compile-time via affine ownership + provenance + auto-drop". CX:126 says D.046's "no leaks" is false: "Cycles, nontermination, abrupt process death, forgotten external obligations". Any L15 "like GC" promise must not claim leak freedom.

### 3.3 L16 fit
- **NP N-4 matches L16:** "floats are IEEE-754 with NaN/±Inf representable and propagated… No fast-math/reassociation defaults: any reassociation… must be opt-in and documented as changing results" (NP:90). Compare L16: "strict arithmetic by default; optimizations that change results only by explicit opt-in" (decisions.md:48).
- **Loss scaling needs IEEE:** GradScaler detects inf/NaN (NP:32, 87). Finite-only is "incompatible with NaN-as-signal loss-scaling" (NP:92). This is resolved in favour of L16.
- **Superseded text:**
  - CX:25 "IEEE versus finite-only behavior remains unapproved"
  - CX:561 "Float policy remains unresolved. Ownership research does not authorize NaN rejection, finite-only storage, fast-math assumptions"
  - MS:33 "IEEE-754 vs finite-only semantics are **not approved**"
  - MS:306 Q4
  - NP:24 "Not approved — treat as open"

  L16 settles all of these.
- **Remaining float tensions with L16:**
  1. **Literal Zig/C UB.** "Follow Zig and C" could be read literally, and `@intFromFloat` out of range is UB in Zig (MS:39, 141, 187). NP:90 requires "float→int casts of non-finite/out-of-range values are **checked errors**… never Zig `@intFromFloat` UB". **(inference)** L16 is about values and arithmetic, and casts are separately proof-obligated, but the user should confirm.
  2. **Narrowing facts under IEEE.** MS:141 "any narrowing-fact machinery must treat float comparisons as non-facts until semantics are decided". Under IEEE, comparisons with NaN are false, so float guards still cannot become range facts (MS:306 "comparisons non-total — narrowing must treat float guards as non-facts, `Fin<T>` unavailable").
  3. **Native kernels and strictness.** OpenBLAS "FMA/vectorization/reassociation changes LAPACK-test numerics" (NP:71). oneDNN has "floating-point math mode, accumulation mode" attributes (NP:34, 81). **(inference)** L16's strict default versus kernel-internal FMA and threading-dependent reductions is an unresolved qualification question. NP:81 "f32 accumulation where the kernel provides it (oneDNN fpmath mode)" may need to be treated as the explicit opt-in.
  4. **NaN poison in autodiff.** "Autodiff must propagate NaN in gradients (poison semantics)… A7 deliberately chooses the stricter, predictable contract" than PyTorch (NP:90). This goes beyond L16 and is a separate choice.
  5. **Parallel backward.** NP:35 says multithreaded backward with shared inputs is nondeterministic, which is in tension with strictness if parallel backward is ever allowed **(inference)**.

### 3.4 Other locked-decision drift inside the reports
- **Mode syntax.** NP:106 R-5 says "mutation… requires explicit `inout` permission". L6's scope limit is "No parameter-mode syntax is approved" (decisions.md:55). OW:90 marks `inout` as "NOT approved".
- **D.049.** OW:124 "No storable refs (D.049)" was partly walked back in the correction (OW:161). MS:15 marks D.049 "not approved (it conflicts with the accepted `ref`-struct-field surface)".
- **Heap arrays.** NP:128 "`new [N]T` rejected pending design; tensors need a runtime-owned buffer path". This is still an open decision that L15 affects directly **(inference)**.

---

## 4. Hard cases and invariants

### 4.1 Counterexamples and hard cases (memory)
| Case | Source | Why hard for compile-time automatic memory |
|---|---|---|
| Alias double-`del`: `pp := new Pt; qq := pp; del pp; del qq` | MS-3 (MS:58); before/after at MS:256-265 | Needs points-to facts or rejection of ref copies |
| `defer del p` plus explicit `del p` | MS-4 (MS:59); CX:286 | Scheduled cleanup versus explicit cleanup |
| `del` on a `ref` param aliasing a caller stack slot → `allocator.destroy(&stack_var)` | MS-5 (MS:60); OW:57 | `ref` conflates owning heap references and borrowed stack slots (MS:114-116) |
| Return a slice of a stack array: `make_values :: fn() []i32 { values: [3]i32 = …; ret values[0..3] }` | MS-8 (MS:63); CX:292-296 | Escape analysis. The fix is return by value or an owning buffer, not a silent copy (CX:305) |
| Uninitialized struct or slice emits Zig `undefined` | MS-9 (MS:64) | Definite initialization is a prerequisite for generated cleanup (only drop initialized fields, CX:188-189) |
| Callee `del` via `ref` leaves caller `non_nil` proof intact | MS-2 (MS:50) | Call effects |
| Stale facts after `if c { y = 5 }` | MS-1 (MS:49) | Joins. Any compile-time lifetime analysis needs real joins (I-10) |
| `swap_i32(values[i], values[j])`; with slices "`i != j` is insufficient" | CX:317-327 | Storage identity and projections |
| Partial move `extracted := pair.first` | CX:338-355 | Field-sensitive cleanup. Reject if a destructor reads both fields |
| `for item in items { append_item(items, item) }` | CX:379-381; T6 MS:234 | Iteration invalidation, including arena or container growth |
| Callback accesses an active exclusive global | CX:450, 643 | Syntactic exclusivity is defeated by globals |
| Jai: data "might be aliased by an evil global or a pointer… don't do that" | OW:162 | Shows the style L15 cites has no check |
| Deep ownership tree destruction | CX:462, 650; Koka recursion CX:212 | Stack or worklist allocation during OOM (CX:210) |
| Generation counter wraps and revives an old handle | CX:464, 645 | DOD handles need a defined exhaustion policy |
| Integer-backed file descriptor becomes Copy | CX:193, 200 | Semantic, not structural, Copy |
| `Rc::clone` means share, not deep copy | CX:204 | Naming clone versus share |
| Fallible close (flush or commit) inside a destructor | CX:197 | Generated cleanup cannot hide errors |
| Channel send fails and ownership must return | CX:398-404, 647-648 | Transfer failure |
| Allocator state dies with the sending task | CX:488 | Regions or arenas crossing tasks |
| Cancellation during a synchronous native kernel | CX:492, 649 | Buffers must stay live until the kernel acknowledges |
| `loss = x * x` then `tensor_fill(session, x, 0.0)` | CX:502, 532-553 | Saved storage versus mutation |
| Broadcasted writable views: "several logical elements can name one storage element" | CX:557 | Tensor aliasing |
| Repeated training steps must return to a retained baseline | CX:653 | Per-step lifetime grouping |
| ORT BFCArena never shrinks | NP:51 | Arena growth policy and resource exhaustion |
| OpenBLAS buffer pool exhausted terminates the process | NP:50 | Native allocation outside A7 control |
| oneDNN primitive executed on a different thread → segfault; same primitive concurrently → wrong results | NP:49 | Native resource thread affinity |
| PyTorch mobile wrapping nbytes | NP:55 | Wrapped allocation size under L5 wrapping |
| Masked division yields NaN gradients even after masking | NP:35, V-6 NP:150 | IEEE plus autodiff (L16) |
| In-place and `out=` ops not autocast-eligible | NP:31 | In-place interacts with precision and saved storage |
| Failed training allocation before parameter commit | CX:655 | Atomic step commit |

### 4.2 Invariants proposed in the reports
**MS findings (current defects, MS:49-66):** MS-1 unsound joins; MS-2 calls without effects; MS-3 alias double-del; MS-4 defer+del; MS-5 del on ref param to stack; MS-6 untagged-union read; MS-7 recursion-ban bypasses; MS-8 stack-slice escape; MS-9 `undefined` defaults; MS-10 overflow obligations disabled (superseded by L5 for `+ - *`); MS-11 `del` capture shadowing.

**I-invariants (MS:124-170), memory-relevant subset:**
- **I-1** bounds proof or typed `get(i) -> ?T` (MS:125)
- **I-3** `del` heap provenance, path-sensitive; emitted `del` nulls (MS:129)
- **I-4** no use-after-del or double-del, including scheduled deletions (MS:130)
- **I-5** affine heap refs with auto-drop in reverse declaration order; reject ref-typed copies as the minimal sound option (MS:131)
- **I-6** no stack escape (MS:132)
- **I-7** definite assignment; never emit `undefined` (MS:135)
- **I-9** wrapping `+ - *` plus checked size-critical arithmetic (MS:141)
- **I-10** real joins; **I-11** conservative call effects (MS:144-145)
- **I-12** proof preservation under transformation (MS:146)
- **I-13** recursion-ban completeness; **I-14** stack budget (MS:147-148)
- **I-16** compile-time-only exclusivity; **I-17** immutable ≠ noalias (MS:152-153)
- **I-18** move-only cross-task data; **I-19** channel lifecycle; **I-20** task lifecycle (cancellation deferred); **I-21** no deadlock-freedom claim (MS:156-159)
- **I-22** FFI handles opaque and move-only; extern memory never freed by `del`; tensors owning device memory are affine; autograd nodes follow the I-5 drop discipline; per-step scratch comes from arenas (MS:162)
- **I-23** arenas and pools as stdlib ownership types; no arena escape; iteration invalidation rejected via exclusivity (MS:165)

**Other numbered requirements:**
- **NP R-1** alloc-size obligation (NP:98)
- **R-2** shapes, rank ≤ 8, numel and nbytes cached in the header (NP:100)
- **R-3** buffer ownership and ABI (NP:102)
- **R-4** threading (NP:104)
- **R-5** views and in-place (NP:106)
- **R-8** allocation failure or runtime arenas (NP:112)
- **R-9** transform invariance plus iterative backward (NP:114)
- **R-10** synchronous v1, with no borrows across await if async arrives later (NP:116)
- Validation V-1..V-15 (NP:145-159). Codex acceptance scenarios (CX:630-656). GLM test suites T1-T11 (MS:230-240).
- **OW R1/R2/R3** parameter immutability layers (OW:187-191).

---

## 5. Open questions for the user brainstorm

1. **What "like garbage collection" means.** Does it mean (a) no manual `del` ever (fully generated cleanup), (b) generated cleanup plus optional explicit `del` (CX:682 keeps both), or (c) lifetime groups (arenas or regions) as the primary unit and per-object ownership only for resources?
2. **Runtime checks.** Does "everything resolved compile-time" forbid all runtime memory checks? Candidates: generation-handle lookups (CX:615), recoverable exclusivity preflights (CX:454), tensor saved-storage version checks (NP:106, CX:526). Or does it only forbid a runtime collector?
3. **Compile-time RC.** Is compiler-inserted RC with reuse (Perceus, CX:91, MS:213) acceptable under L15, or is any count traffic "runtime GC-like"? This decides T1 versus T2 (CX:508-511).
4. **Region inference role.** Should region inference (Tofte–Talpin/MLKit/Cyclone) be phase-1 or phase-2 (MS:278)? What is the fallback for inference-induced over-retention without a collector (CX:74, 150)?
5. **Jai/Odin/Zig allocators.** Does "as jai, odin and zig" mean explicit and visible allocators (Zig), implicit context allocators (Odin/Jai `context`), or neither? How are allocator lifetimes proven (CX:85)?
6. **Aliasing policy for ref copies.** Reject `qq := pp` (MS:131, 263) or treat it as a move (CX:250)? These are different compatibility breaks.
7. **Borrowed views.** Local only (CX:154), or a lifetime-dependency contract (Alternative B, CX:144) for zero-copy parsers and iterators?
8. **Data-oriented defaults.** Should A7 provide language-level SoA, pools per type, and index/generation handles, or leave them to stdlib? No report covers SoA (gap, section 2).
9. **Deep destruction strategy** without recursion or allocation during OOM (CX:210, 462): pre-reserved worklist, intrusive, or arena-only bulk release?
10. **Custom destructors.** In v1 or not (CX:686)? How do fallible close operations surface (CX:197)?
11. **Tensors.** T1 session ownership versus T2 retained storage (CX:689). Is a per-training-step arena the default lifetime for intermediates (MS:162, CX:653)?
12. **Saved-storage mutation policy.** Reject, preflight failure, explicit snapshot, or op-specific (CX:519-526)?
13. **Cancellation in v1.** Structured cooperative cancellation (CX:492) or deferred (MS:158)? This affects the generated cleanup contract.
14. **Cross-task allocation.** Transferable arenas or regions, a shared allocator, or copy (CX:488)?
15. **Stack budget promise.** Computed from the recursion ban (MS:148) or target-qualified only (CX:692)?
16. **L16 and casts.** Float→int casts: checked error (NP:90) or literal Zig semantics? Native kernel FMA and fpmath modes: forbidden by default or opt-in (NP:71, 81)?
17. **Leak language.** Which exits count as "defined exits" (return, break, propagation, cancellation), and what non-promises apply (cycles, process kill) (CX:126, 198)?
18. **`new [N]T` and heap buffers.** Language surface or runtime-internal allocator (NP:128)?

---

## 6. External references to follow up

### 6.1 Cited in the reports
**Regions, RC, and static memory management:**
- Tofte & Talpin, *Region-based memory management*, Information and Computation 1997: https://web.cs.ucla.edu/~palsberg/tba/papers/tofte-talpin-iandc97.pdf (CX:51). GLM cites Tofte/Talpin region inference at POPL 1994 "per citation trails" (MS:211, 332).
- MLKit, regions with tracing GC: https://elsman.com/mlkit/pdf/tagfreegc.pdf. MLKit docs: https://elsman.com/mlkit/doc (CX:51, 150).
- Grossman et al., *Region-Based Memory Management in Cyclone*, POPL 2002. Swamy et al., *Safe Manual Memory Management in Cyclone*, SCP 2006 (MS:211, 332).
- Crary et al., *Typed Memory Management in a Calculus of Capabilities*, ICFP 1999 (MS:211, 332).
- Reinking, Xie, Leijen, Swamy (GLM lists "Reinking et al."), *Perceus: Garbage Free Reference Counting with Reuse*, PLDI 2021: https://www.microsoft.com/en-us/research/publication/perceus-garbage-free-reference-counting-with-reuse (CX:48, MS:213). Koka 3.2.3 `kklib/src/refcount.c` (CX:48, 212).
- Stoldt et al., *Dynamic Region Ownership for Concurrency Safety*, PACMPL/OOPSLA 2025, doi 10.1145/3729313 (MS:214, 332).
- Verona (regions as concurrent-ownership units), Inko (per-thread heaps and channels), Dala arXiv:2109.07541 (MS:214).

**Value semantics, ownership, and aliasing:**
- Hylo (formerly Val): https://hylo-lang.org/introduction/, spec https://github.com/hylo-lang/specification/blob/main/spec.md, new compiler https://github.com/hylo-lang/hylo-new. Mutable value semantics: https://arxiv.org/abs/2106.12678 (CX:49, 110).
- Vale alpha 0.2: https://vale.dev/, https://vale.dev/guide/structs. "Region borrowing… remain advertised as planned" (CX:50, 92).
- Pony 0.72.1 capabilities and ORCA GC (CX:47, MS:212).
- Swift 6.3.3. SE-0176 (exclusivity), SE-0377, SE-0390, SE-0427, SE-0429, SE-0446, SE-0458 (CX:43-44, MS:206, NP:44).
- Rust 1.98.1. Destructors, Copy, Pin, Rc, Arc, closure types. Tree Borrows, PLDI 2025: https://plf.inf.ethz.ch/research/pldi25-tree-borrows.html (CX:39-40, 94-96).

**Zig, Odin, Jai, and other language baselines:**
- Zig 0.16.0 language docs and release notes. Shipped `Allocator.zig` and `ArenaAllocator.zig` were read locally. 0.16 "changes arena allocation concurrency" (CX:41, 98).
- Odin overview https://odin-lang.org/docs/overview/, allocator source https://raw.githubusercontent.com/odin-lang/Odin/master/core/mem/allocators.odin (unpinned, CX:42), Odin FAQ (MS:208).
- Jai: no authoritative source (CX:55). A single Feb 2023 closed-beta practitioner report is cited without a URL in the file (OW:177, 154 "one fetch of the provided Jai source").
- Go 1.27.1 GC guide and cgo (CX:46). C++ working draft, basic.life and unique.ptr (CX:45). C++ Core Guidelines lifetime profile and "Why Safety Profiles Failed" (MS:210).

**Tensors, autograd, and native kernels:**
- PyTorch 2.14 autograd mechanics and amp. Sources: `grad_scaler.py` and `EmptyTensor.cpp` at v2.14.0 (CX:52, NP:31-40, 55).
- DLPack header 1.3 (CX:53, 576).
- oneDNN v3.14 (scratchpad, bf16 training), OpenBLAS FAQ, ONNX Runtime BFCArena, safetensors README, MLX 0.32.2, JAX async dispatch (NP:34, 49-51, 66, 165).
- CVE-2019-6446, CVE-2025-32434, CVE-2026-24747 (NP:64-65).
- LLVM LangRef alias attributes (CX:54, 452).

### 6.2 Not cited by any of the four reports but directly relevant to L15
These are my own suggestions from background knowledge and were not verified in this session.
- **ASAP ("As Static As Possible") memory management.** Raphaël L. Proust, Cambridge tech report UCAM-CL-TR-908 (2017). It uses compile-time static deallocation without a GC or RC. There is also the "micro-mitten" Rust-subset ASAP experiment.
- **Mojo "ASAP destruction"** policy (values destroyed after last use, not at scope end). This contrasts with the reverse-declaration scope-end order at CX:206 and MS:131.
- **Lobster** (Wouter van Oortmerssen). Compile-time ownership analysis that removes most RC operations, with RC as the fallback. It is the closest shipped "GC-like but mostly compile-time" design to L15.
- **Lean 4, "Counting Immutable Beans"** (Ullrich & de Moura, IFL 2019). Borrow inference and reset/reuse, a precursor to Perceus. **FBIP / FIP** (Lorenzen, Leijen et al., "FP²: Fully in-Place Functional Programming", ICFP 2023).
- **Region retrospectives.** Tofte, Birkedal, Elsman, Hallenberg, *A Retrospective on Region-Based Memory Management* (HOSC 2004). Aiken, Fähndrich, Levien, *Better Static Memory Management* (PLDI 1995).
- **Vale** "generational references" and "hybrid-generational memory" blog posts. These are the runtime-check counterpart of the DOD generation handles at CX:464.
- **Carp** (static ownership inference, no GC) and **Cone/Pinecone** (gradual memory management).
- **Jai and Odin DOD allocators.** Odin `core:mem` (Arena, Scratch, Pool, `context.temp_allocator`) is the rolling source already referenced at CX:42. Jai `Temporary_Storage` / `context.allocator` has no authoritative public spec. Also Andrew Kelley's "Practical DOD" talk and Zig `std.MultiArrayList` (SoA), which is the DOD precedent missing from every report.
- **Verona "Reggio"** regions paper (Arvidsson et al., OOPSLA 2023) for region transfer across tasks (CX:488).
