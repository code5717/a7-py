# Research status: memory and security reconciliation (GLM), 2026-09-20

> **Source:** OpenCode `zai-coding-plan/glm-5.3`, external reviewer under L12 routing.  
> **Date:** 2026-09-20.  
> **Status:** Advisory. One file created (this one); no other file changed. Research
> reconciliation, not release qualification. No language change is approved or
> implied here. User decisions live in the [ledger](../../decisions.md).

## Answer

The historical memory/security recommendations split into three groups against the
2026-09-20 core-V1 direction (L36-L46):

1. **Preserved and still load-bearing:** the fact-engine soundness prerequisite
   (MS-1/MS-2, SEC-B1, gate M29), the checked size-arithmetic rule (SEC-B2, R-1,
   M41), the untrusted-boundary threat model, and the non-sandbox boundary.
2. **Superseded:** the no-collector/no-counting ban (L37), copy-as-assignment for
   growable lists (L42), compile-time-only enforcement (L39), the open float
   question (resolved by L16), and the broad-V1 AI/concurrency scope (L36).
3. **Reproduced in cited September 20 evidence, not rerun in this review:** two
   memory-unsafety acceptances (alias double-`del`, return of a local array
   slice) were recorded as accepted on the 2026-09-20 batch snapshots. Separately,
   two direct code reads in this review confirm current code paths: the
   untypechecked module call (NEW-1, by inspection, no execution) and the
   `-OReleaseFast` release profile.

The next meaningful security verifications are the four critical safety probes
recorded as accepted in the September 20 batch evidence, the red-first M29
soundness suite, and a determinism double-compile — all before any memory
prototype places a release or removes a copy.

## Method

Read this session: `AGENTS.md`, `docs/plan/decisions.md` (L36-L46 in detail),
`docs/plan/delivery-roadmap.md`, `docs/plan/memory.md`,
`docs/plan/audit/open-items.md`, `docs/SAFETY_CONTRACT.md`, the four assigned
research reports (`research/memory-security-glm.md`,
`research/numerical-policy-glm.md`, `research/memory-design-codex.md`,
`research/memory/review/glm-security.md`),
`research/memory/delivery-reconciliation.md`, `research/memory/review/README.md`,
and the 2026-09-20 evidence (`docs/audits/2026-09-20-core-v1/` README,
`critical-safety-revalidation.md`, `memory-probes.json`;
`docs/audits/2026-09-20-v1-foundations/` README, `critical-high-inventory.md`).

I compiled and executed nothing. Exactly two claims are first-hand code reads
from this session (marked **[read 2026-09-20]**; code paths confirmed by
inspection, no fresh execution). Everything else cites recorded documents. The
memory probes cited below were run by the September 20 batches, not by me:
`memory-probes.json` identifies its compiler snapshot with per-file SHA256
hashes, and I cite those results as recorded evidence, not as a rerun on this
review's tree. Historical findings are attributed to their reports and labeled
historical unless a newer record reproduces them.

## Preserved evidence (still valid under L36-L46)

| Evidence | Why it survives | Citation |
| --- | --- | --- |
| Fact-engine soundness precedes compiler-inserted memory operations | The 2026-09-20 delivery sequence still requires reproducing each critical/high finding before architecture replacement, and the reconciliation draft repeats M29 as a prototype prerequisite | `delivery-roadmap.md:115-121`, `delivery-reconciliation.md:159-165` |
| Checked size arithmetic for every size reaching an allocator, slice bound, capacity or native length | L5 leaves division, shifts, casts and allocation-size arithmetic open; the numerics packet is unsettled; M41 unchanged | `decisions.md:129-133`, `delivery-roadmap.md:141`, `memory.md:637` |
| Untrusted-input threat model (checkpoint bytes, dataset paths/shapes, threading env vars, native descriptors) | W9 and W10 encode the view-mutation and checkpoint-integrity boundaries as measurable workloads; the AI track is later but the boundary discipline transfers | `numerical-policy-glm.md:130-136`, `delivery-reconciliation.md:82-83` |
| Not-a-sandbox boundary | Unchanged and restated in the current contract | `AGENTS.md:149-154`, `SAFETY_CONTRACT.md:13-14` |
| Fail-closed safety contract preamble | L39 explicitly keeps it until a migration packet is approved | `SAFETY_CONTRACT.md:3-6`, `decisions.md:118` |

## Superseded assumptions

| Historical assumption | Superseded by | Consequence |
| --- | --- | --- |
| "No garbage collector, no reference counts, no pauses" (contract item 1; treated as locked in all 2026-09-14 reports) | L37 allows automatic runtime help; RC and tracing are comparison candidates | `decisions.md:116`, `memory.md:3-8`, `delivery-reconciliation.md:56-57` |
| Copy is the meaning of assignment; affine moves for heap refs (I-5; Codex Alternative A) | L42: growable-list assignment shares identity; explicit copy makes independent data. Structs and fixed arrays keep value behavior | `decisions.md:121`, `memory.md:6-7` |
| Exclusivity and memory safety enforced compile-time only (I-16's "no runtime fallback slot"; proof-or-reject reading of M39-era text) | L39: prefer compile-time proof, allow checked execution; required runtime checks stay in release builds; migration packet pending | `decisions.md:118` |
| Float semantics open (Q4 in both 2026-09-14 GLM reports) | L16 settles IEEE 754 values with strict default arithmetic | `decisions.md:51` |
| V1 requires ownership + concurrency + CPU AI (L1/L7 framing) | L36: core language, automatic memory, libraries, tools first; AI and concurrency are later tracks and design constraints | `decisions.md:115`, `delivery-roadmap.md:10-12` |
| Q5/R-11: build `-OReleaseSafe` until repairs land | Never adopted; the release profile is still `-OReleaseFast`, and L39's release-retained checks are the governing direction, packet pending | **[read 2026-09-20]** `scripts/build_examples.py:25`; `decisions.md:118` |
| Native AI kernels through a C ABI surface (R-3/R-4 as written) | L41: minimal checked native interface implemented through Zig; "just Zig for all"; app code never manages raw native pointers | `decisions.md:120` |

## Disposition of historical findings

Labels: **reproduced in cited evidence** (a named September 20 record shows
acceptance on its own hash-identified snapshot; not rerun in this review),
**confirmed by inspection** (code path read first-hand in this review; no fresh
execution), **repaired (trigger-level)** (fixed for covered regression
triggers, family not closed), **superseded** (a decision voided the premise),
**not revalidated** (no newer evidence located; remains historical, not open by
inference).

| Finding (report) | Disposition | Evidence detail | Citation |
| --- | --- | --- | --- |
| MS-1 stale fact joins (`memory-security-glm.md:46`) | repaired (trigger-level) | Contract notes repairs at joins/loops/ref-calls/defers; roadmap row says fixed for covered triggers with alias/lifetime analysis open. SAF-4's trigger now rejects | `SAFETY_CONTRACT.md:8-11`, `delivery-roadmap.md:100`, `critical-safety-revalidation.md:10-12` |
| MS-2 calls invalidate nothing (`:47`) | repaired (trigger-level) for ref-argument cases | The global-mutation case (SAF-6) remained accepted in the cited September 20 revalidation, and MTH-2 remains open | `critical-safety-revalidation.md:14,26`, `open-items.md:111` |
| MS-3 alias double-`del` (`:55`) | **reproduced in cited evidence** | Probe accepted (exit 0) on the September 20 batch snapshot; its emitted Zig destroys through both `pp` and `q`. Snapshot identified by per-file SHA256 in the record. Not rerun in this review; binary not executed by that batch either | `memory-probes.json` case `alias_double_delete` with `compiler_sha256`, `2026-09-20-core-v1/README.md:57-59` |
| MS-4 `defer del` + `del` double destroy (`:56`) | not revalidated | No fresh reproducer located in the 2026-09-20 records read. Neighboring SAF-8 (repeated field deletion) remained accepted in the cited September 20 revalidation | `critical-safety-revalidation.md:14,27` |
| MS-5 `del` on a ref param aliasing stack storage (`:57`) | not revalidated | SAF-1's trigger closed (nil-argument rejection) but the inventory states no complete ref/alias guarantee | `critical-high-inventory.md:48` |
| MS-6 untagged-union inactive read (`:58`) | not revalidated | Contract still lists union discriminant proofs as active work | `SAFETY_CONTRACT.md:66` |
| MS-7 recursion-ban bypasses (`:59`) | repaired (trigger-level); family open | Unused nested-recursion trigger repaired; stored fn-pointer and module-qualified bypasses pending; G4/M6 disagreement unresolved | `critical-high-inventory.md:68`, `memory.md:773` |
| MS-8 returned slice of a stack array (`:60`) | **reproduced in cited evidence** | Probe accepted (exit 0) on the same September 20 batch snapshot; emitted Zig returns `buf[0..4]` from a local. Not rerun in this review; binary not executed by that batch either | `memory-probes.json` case `returned_local_slice` with `compiler_sha256`, `2026-09-20-core-v1/README.md:57-59` |
| MS-9 `undefined` defaults for structs/slices (`:61`) | not revalidated | No newer evidence located; M34 still proposes definite assignment | `memory.md:584` |
| MS-10 overflow proofs disabled (`:62`) | superseded **for `+ - *` and their compound forms only** | L5 and the contract remove the overflow proof for those operators. L5's scope limit leaves division, remainder, signed `MIN / -1`, negation, shifts, narrowing casts and allocation-size arithmetic open; the contract still lists shift checks and signed division edges as active work, so MS-10's remaining scope is not superseded | `decisions.md:40`, `decisions.md:129-133`, `SAFETY_CONTRACT.md:61-67` |
| MS-11 `del p` emits capture-shadowing invalid Zig (`:63`) | repaired (trigger-level); variant resurfaced in a cited September 20 native control | L34 fixed keyword/loop-capture bindings, but a control in the September 20 revalidation hit the same defect again when the allocation was named `p` | `delivery-roadmap.md:103`, `critical-safety-revalidation.md:89-91` |
| NEW-1 module calls bypass type checking (`:71`) | **confirmed by inspection; no fresh execution** | `file_module_call` still returns `UNKNOWN` after visiting only the arguments. Code path read first-hand in this review; no probe compiled or run | **[read 2026-09-20]** `a7/passes/type_checker.py:1388-1391` |
| NEW-2/NEW-3 doc/console content injection (`:72-73`) | not revalidated | No closure evidence located in the records read | — |
| RB-2/SEC-7 output artifacts, H-8 imported diagnostics, R1 float remainder | repaired (verified with regression tests) | Roadmap disposition table rows | `delivery-roadmap.md:101-104` |
| SEC-2/SEC-3/SEC-4/secrets scan | repaired | Recorded closed on 2026-09-19 | `open-items.md:76-88` |
| SEC-1/SEC-5/SEC-6 site preview and build sinks | not revalidated | The 2026-09-18 entry recorded all twelve SEC findings live; later entries close only SEC-2/3/4 and secrets | `open-items.md:222` |
| SEC-B1..B5, SEC-M1..M11 (`review/glm-security.md`) | preserved as gate/plan content, not implemented | Revision 3 absorbed them as M25, M28, M29, M37-M51; M16 still unapprovable per review consensus | `memory.md:26-31`, `memory.md:790-795` |

The repaired rows follow the roadmap's own rule: a repaired trigger does not
establish correctness of the surrounding family (`delivery-roadmap.md:90-93`).

## Unresolved questions

**Proof.** Is the fact engine sound enough to license compiler-inserted releases
and copy removal? No. SAF-2, SAF-3's fallthrough case, SAF-6 and SAF-8 remained
accepted and were recorded as release blockers in the 2026-09-20 core-V1 batch
evidence (its README, `critical-safety-after-saf4.json`); no snapshot examined in
this review revalidates them later, and I reran nothing. Guard facts track
identifier names, not field paths, which blocks the SAF-2 candidate; the loop
fixed-point gap (KNOWN S2) stays open. L39 permits checked execution, but no
migration packet exists, so the recorded behavior is still fail-closed rejection.
`2026-09-20-core-v1/README.md:40-43`, `critical-safety-revalidation.md:52-78`,
`open-items.md:105-109`, `decisions.md:118`.

**Ownership.** No memory mechanism is selected (`delivery-roadmap.md:16-17`).
L42 settled only list identity. The unapproved revision-3 plan predates L42 and
still needs a gate covering shared-identity assignment versus exclusivity and
copy analysis — W2 measures the identity/snapshot distinction, but no rejection
or check rule exists for aliasing created by assignment. The 2026-09-14 invariants
I-3..I-6 were designed for the `new`/`del` surface that plan intends to remove;
their hazard evidence (MS-3/MS-8, both reproduced in the cited September 20
records) transfers to whichever candidate is measured, including the RC and
tracing baselines L37 admits.

**Recovery.** M2 recoverability is still contested (extent-based versus fallible
signatures, `memory.md:774`). W6 (failure injection, exactly-once release) and
W10 (checkpoint partial-failure integrity) state the observable requirements;
nothing is measured (`delivery-reconciliation.md:79,83`, `:154-157`).

**Native boundary.** L41 fixes the shape — Zig implements imports, runtime
support, builds and linking — but no native declaration surface exists (M25 has
no syntax today), the descriptor trust and supply-chain rules (SEC-B3/R-12) are
postponed to the standard-library/native milestone, and the 1,100-module import
chain still fails. NEW-1 leaves cross-file calls untypechecked, which weakens
the module trust boundary P-MOD builds on. `memory.md:630`,
`delivery-roadmap.md:156`, `open-items.md:117`, `critical-high-inventory.md:81`.

## Next meaningful security verification (recommendations, not findings)

1. Close SAF-2, SAF-3 fallthrough, SAF-6 and SAF-8 at an identified source
   snapshot with paired guarded controls. They are recorded release blockers in
   the 2026-09-20 core-V1 batch evidence and the direct successors of MS-1/MS-2.
   SAF-2 needs field-path facts or an
   approval packet for the valid program it currently would reject
   (`critical-safety-revalidation.md:80-88`).
2. Build the M29 adversarial proof-engine suite red-first (T1/T2/T11) before any
   memory prototype places a release or removes a copy, and extend it with an
   L42 case: aliasing created by growable-list assignment must not defeat
   uniqueness or exclusivity reasoning (`delivery-reconciliation.md:159-165`).
3. Add the M40 determinism check: compile one program twice under different
   `PYTHONHASHSEED` and compare emitted Zig byte-for-byte. Cheap, untested, and
   already recommended by the claims audit (`open-items.md:125`, `memory.md:636`).
4. Add a regression for the MS-11 `del`-capture variant recorded in the cited
   September 20 native control (`critical-safety-revalidation.md:89-91`).
5. Fix NEW-1 (type-check module-qualified calls) before P-MOD approval; a module
   API that is trusted rather than checked is the exact safe-API/implementation-
   trust confusion the 2026-09-14 review flagged (`memory-security-glm.md:217`).
6. When the L39 migration packet is drafted, verify no residual check compiles to
   a Zig safety check that ReleaseFast removes, in both profiles
   (`memory.md:741-742`).

## Limitations

- Advisory only; the controlling Codex session owns coordination. The sibling
  research README/index is untouched.
- I compiled and executed no A7 program. The two "reproduced in cited evidence"
  memory probes cite the September 20 recorded runs at their hash-identified
  snapshots; those unsafe binaries were also not executed by that batch, so
  runtime corruption remains an inference from emitted Zig under documented Zig
  semantics (`2026-09-20-core-v1/README.md:59`).
- The two first-hand reads (NEW-1 at `a7/passes/type_checker.py:1388-1391`, the
  release profile at `scripts/build_examples.py:25`) confirm code paths by
  inspection only; neither establishes behavior at any snapshot beyond the
  working tree this review read.
- "not revalidated" means no newer evidence was located in the documents read,
  not that the finding is closed or open.
- This file reconciles research; it qualifies no release, approves no language
  change, and does not update the safety contract.
