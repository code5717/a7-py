> **Source:** OpenCode `zai-coding-plan/glm-5.3` review of memory plan revision 2; focus: tasks, resources, failure and native boundaries. Prompt in [review-prompt.md](../review-prompt.md).  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

Now let me read the supporting material: synthesis, review index, and the safety contract.
Now let me verify key compiler facts cited in audit-3 against the actual source.
Let me verify the mutable-global and native-declaration probes first-hand (compile-only, writing only to the pre-approved tmp dir):
# External review: concurrency, resources, failure, native boundaries

**Scope:** gates M2, M7, M10, M12, M16, M26, M27, M36; corpus 10, 12, 20, 23; audit-3. Read-only; no code executed by me. I verified compiler facts by reading source; probe claims from the audits are labeled as their recorded compile-only evidence.

## Verified facts

- `new T` lowers to `allocator.create(T) catch null` — allocation failure is nil-recoverable today (`a7/backends/zig.py:1913`).
- `io.println`/flush lowers to `catch @panic("a7 ... write failed")` — output failure aborts today (`a7/backends/zig.py:170-171`).
- Stdlib has only `io`, `math`, `mem`, `string`; `mem.py` is a 9-line stub. No `List`/`Map`/`Table`, tasks, channels, files, or native surface exists in the compiler (`a7/stdlib/`).
- No native declaration syntax: `extern fn` fails (recorded compile-only, audit-3 p05; `edge-case-audit.md:134-135`). I did not re-run it (my file writes were blocked); source inspection confirms no extern path exists.
- Mutable globals compile today with no data-race story (recorded compile-only, audit-3 p04; `audit-3-concurrency-failure-native.md:54`). Untyped globals emit `var counter = 0` that Zig rejects (`edge-case-audit.md:117-118`).
- Revision 2 of the memory plan applied most of audit-3: M2 by extent, M7 move-only + reverse order + fallible close, M10 structured cancel-then-join, M12 seven descriptor fields, M27 no sender counting, M36 read-only sharing, plus contract 6's deadlock honesty (`memory.md:70-72`), contract 2's descriptor assumption (`memory.md:56-57`), defer rules (`memory.md:446-449`), the `new`→M2 breaking-change row (`memory.md:266`), and checked-size arithmetic in residual work (`memory.md:529`).
- All nine GLM reviews, including concurrency, security (L12) and the contract review behind M16, produced no output and must be rerun (`review/README.md:31-33`).

## Gate-by-gate findings

**M2 (out-of-memory by extent)** — Sound core (audit-3 G-5 applied: failure class follows the owning extent, `try_append` added). Unresolved:
- The abort cliff: outside task/step/session extents one transient allocation kills the process; corpus 1's request loop is exactly this. Both external reviewers contest extent-kind recoverability (Qwen M-5 proposes fallible-signature recoverability; Kimi M-2 demands a corpus program showing the recoverable pattern). No such corpus program exists.
- Spawn failure (EC3-04): the task extent does not exist yet when the spawn allocates; whether `group.start` failure is recoverable and returns moved arguments unchanged is undecided, and the recoverable set ("bulk-data library calls") is not enumerated (G-5's enumeration half unapplied).
- Abort semantics (EC3-64, audit-3 §4 Q12): "abort runs no defers or releases, flushes std streams only" appears nowhere in the contract or M16.

**M7 (resources)** — G-8/G-15/G-16 partially applied. Missing:
- Implicit-release failure semantics (EC3-56): M7 says fallible `close` + warning, but never defines what automatic release does when a flush/commit fails (audit-3's infallible-release + discarded-error report). As written: data loss with no defined behavior. No corpus entry.
- Drop flags (EC3-59): contract 3 still says "No runtime drop flags" while EC3-59's branch-close case may need one-bit flags in contract 4's residual list. Unresolved tension.
- Blocking release (EC3-66) and resources inside collections (EC3-60/61) have no gate text; layer 5's "handled explicitly" (`memory.md:530`) is not a rule.

**M10 (tasks)** — G-1 applied. Missing: unobserved failed outcomes at implicit scope-finish (EC3-02's "reported"); join outcome taxonomy routed to G7 (fine, but it gates Phase F); "task group"/"channel" extents from G-19 never added — and the extent lists now disagree: contract 5 says "call, iteration, task, training step or process" (`memory.md:69`), M2 adds *session*, M11 adds *session* and *microbatch* (`memory.md:505`).

**M12 (native boundaries)** — G-12 and G-11 applied; the seven descriptor fields match EC3-42–53. But:
- No native declaration surface, syntax proposal, or gate exists in either plan, while corpus 12, Phase F, G8 and the L10 acceptance all sit behind it (Qwen B-4; verified against stdlib and audit-3 p05). Track 10 exists but has no gate.
- Runtime-bounded overlap: the residual-work row makes unproven-distinct buffers a compile-time rejection unless "a gate approves a runtime check" (`memory.md:528`). Fail-closed is consistent, but the user should know BLAS-style runtime-overlap calls won't compile until that gate is approved.
- Descriptor correctness is an assumption qualified only by integration tests; the GLM security review that must examine this (L12, audit-3 §5) has not run.

**M16 (safety-contract amendment)** — Cannot be approved as drafted:
- Residual runtime work is incomplete: no buffer planning for dynamic shapes, plan-cache insert/evict, arena shrink, or compiler-inserted copies whose allocation can fail (Qwen B-1; verified against `memory.md:521-530`).
- The nine-class rejection list is not closed: no use-after-`close`/resource-move, no defer control-flow restriction, no loop-binding writes, and no id-without-store class (Qwen B-2; verified against `memory.md:76-90`). The list is supposed to *be* the M16 content.

**M26 (cancellation points)** — "Channel operations, joins and explicit checks only" drops audit-3's "loop back-edges the compiler marks" (EC3-06). Consequence: a CPU-bound child with no channel ops and no explicit check never observes cancellation, so M10's "scope exit cancels then joins" blocks indefinitely. This is *consistent* with contract 6's honesty about endless loops, but it makes cancel-then-join a non-guarantee for exactly the workload class (compute tasks) users will spawn. This is a real choice, not a wording slip.

**M27 (channel close)** — G-9 applied; consistent with contract 1. Multi-sender drain works via group end under structured concurrency. Send-to-closed returning `unsent` depends on G5 outcome types (routed). No objection.

**M36 (read-only sharing)** — G-20 applied, but:
- The write half is missing for **globals**: layer 0 mentions "effect summaries including globals" (`memory.md:425`) and nothing else. Audit-3 G-21/EC3-22 (reject task functions that write a global another running task writes; task-shared globals immutable after start) was never written into any gate, and there is no data-race-freedom contract item (Qwen M-6). Since globals have no lexical owner, M36's "parent values" wording cannot reach them.
- M10's "values move in" and M36's sharing-without-move contradict each other as literally written; needs one reconciling sentence.

## Corpus programs

- **10** (`memory.md:564`): G-4's restatement was applied (now "typed id", not bare index — good). But the *reject* expectation has no rule behind it: none of the nine rejection classes, M5, nor M10 forbids an `Id(T)` crossing without its store; EC3-13's proposed rule was never adopted. Also the *accept* half should pin down that the worker's registry is task-owned, not a `ref` crossing the boundary (a `ref` into a task is itself ungoverned).
- **12** (`memory.md:566`): consistent with M12 + rejection class 8 + the overlap row; the strongest current falsifier for native boundaries. Missing companions: native-returned storage (EC3-44) and cancelled-task native borrow (EC3-07) have no corpus entry (G-23 only partially applied).
- **20** (`memory.md:574`): good M2 step-extent falsifier; tests store release before retry. It does not cover task-extent OOM with surviving siblings (EC3-32), spawn failure, or the abort path.
- **23** (`memory.md:577`): exercises M10 scope-exit and M27/EC3-09 queue release. It only works if the child reaches a cancellation point, so it must be authored with a channel-reading child — and it therefore does not falsify the unresponsive-child hole in M26.

## Ranked findings

**Blockers**
1. No GLM concurrency/security/contract evidence exists (all nine runs died); M12, M16 and native-boundary qualification cannot go to the user until they are rerun (L12; `review/README.md:31-33`).
2. M16's two closed-list claims are false as written (incomplete residual-work table; non-closed rejection list). The amendment is against a moving target.
3. No native declaration surface or gate exists while corpus 12, Phase F, G8 and L10 acceptance depend on it.
4. M2's recoverability model is contested (extent kind vs fallible signature) with a demonstrated L19 cliff (server-loop abort) and undecided spawn-failure semantics.

**Major**
5. Cross-task writes to mutable globals are rejected by no gate or contract item; mutable globals compile today; no data-race-freedom statement anywhere.
6. Implicit-release failure (flush at extent end) has undefined behavior and no corpus entry (EC3-56 half-applied).
7. Corpus 10's "reject" case has no backing rule (id-without-store class missing).
8. M26 makes cancel-then-join unenforceable for CPU-bound children; loop-back-edge cancellation is an unmade decision with a performance dimension (L20).
9. Contract 3's "no runtime drop flags" vs EC3-59's branch-close case is unresolved.

**Minor**
10. Extent lists disagree across contract 5, M2 and M11; no group/channel extent (G-19).
11. M10 "values move in" vs M36 sharing wording conflict.
12. Abort semantics (no defers/releases on abort) unstated.
13. G-23 corpus additions only partially applied (EC3-03, EC3-04, EC3-32, EC3-44, EC3-56 missing).
14. Compiler-inserted-copy OOM diagnostics (EC3-27) not in residual work or M8.

## Decisions for the user

1. **M2 recoverability: extent boundaries (current) or fallible signatures (Qwen)?** Extent-based preserves L19 (no annotation) but a plain request loop aborts on transient OOM; signature-based survives it but every recovering function must declare fallibility. *Recommend: keep extent boundaries, adopt the task-per-request pattern as the documented server idiom, and add the corpus program Kimi requested — but see the signature alternative demonstrated side by side before choosing.*
2. **M26: add compiler-marked loop back-edges as cancellation points?** *Recommend: yes — a flag test per back-edge is compatible with C-like performance and makes M10's promise real for compute tasks; add it to residual runtime work.*
3. **Globals across tasks: adopt audit-3 G-21 (task-shared globals immutable after start; writing/reading conflicting globals in concurrent tasks rejected)?** *Recommend: yes, plus a contract item "A7 code has no data races: cross-task sharing is a move or read-only until join."*
4. **M7: complete G-16 — automatic release is infallible; flush/commit errors go to a discarded-error report; keep the writable-resource warning?** *Recommend: yes, and add an EC3-56 corpus row.*
5. **M27 and M36 as written?** *Recommend: approve both after adding the M36 write-prohibition sentence, the globals rule (item 3), and reconciling M10's wording.*
6. **Open a native-declaration-surface gate in Phase A** (new syntax, needs before/after examples under the approval rule). *Recommend: yes — it is the critical path for Phase F and G8.*
7. **M16 sequencing: complete both lists first, then rerun GLM reviews, then approve.** *Recommend: approve nothing in this focus area before the GLM concurrency and security reviews are rerun.*
8. **Corpus additions (EC3-03, EC3-04, EC3-32, EC3-44, EC3-56, plus the recoverable-pattern program).** *Recommend: add all six.*
