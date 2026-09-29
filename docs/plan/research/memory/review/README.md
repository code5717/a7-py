# Reviews of the memory plan

Status: external reviews of [memory plan](../../../memory.md) revision 2 and
everything behind it, started 2026-09-16. Revision 3 applies them. Decisions
are in the [ledger](../../../decisions.md).

## What was reviewed

The ledger, the v1 plan, memory plan revision 2, the edge-case audit, and all
research, advice and audits. Every reviewer received the
[shared prompt](../review-prompt.md) followed by one focus paragraph.

## Reviews

State as of 2026-09-16.

| Review | Reviewer | Focus | State |
| --- | --- | --- | --- |
| [Qwen](qwen.md) | Qwen Code, plan mode | Everything | Complete |
| [Kimi](kimi.md) | Kimi CLI | Everything | Complete |
| [GLM contract](glm-contract.md) | OpenCode `zai-coding-plan/glm-5.3` | Contract soundness, residual runtime work, safety contract amendment | Complete |
| [GLM user model](glm-usermodel.md) | same | Python-simple surface, breaking changes, realistic programs | Complete |
| [GLM architecture](glm-architecture.md) | same | Compiler feasibility against the current source | Complete |
| [GLM performance](glm-performance.md) | same | C-like performance and memory, benchmarks, margins | Complete |
| [GLM AI](glm-ai.md) | same | Tensor and autodiff memory | Complete |
| [GLM concurrency](glm-concurrency.md) | same | Tasks, resources, failure, native boundaries | Complete |
| [GLM consistency](glm-consistency.md) | same | Contradictions across all documents | Complete |
| [GLM security](glm-security.md) | same | Memory safety and cybersecurity (L12) | Complete |
| [GLM docs check](glm-docscheck.md) | same | Accuracy of the 2026-09-16 documentation cleanup | Complete |

A first attempt at these runs on 2026-09-16 was stopped when the machine ran out
of memory and produced no output. They were rerun in smaller groups. The security
review failed a second time with "database is locked", because several runs shared
one session store. It was run again on its own and completed. The L12 obligation
is now met for revision 2.

## Findings so far

### Qwen

Verdict: revision 2 meets L15, L17 (arenas and pools), L18 and L21. It does not
yet meet the Python-simple half of L17 or L19, and L20 is asserted but not
enforceable.

Blockers:

| # | Finding |
| --- | --- |
| B-1 | Contract item 7 says nothing else runs at run time, but the dynamic-shape buffer planner and compiler-inserted copies are missing from the residual runtime work table |
| B-2 | The rejection list is not closed: a second `backward`, use of a closed or moved resource, control flow inside `defer`, and writes to loop bindings are all rejected elsewhere in the plan |
| B-3 | Gate M6 allows stored function values, which reopens the recursion-ban bypass MS-7 from the 2026-09-14 GLM review. The call-graph summaries depend on that ban. MS-7 is missing from the defect list |
| B-4 | AI acceptance needs native declarations, but no native declaration syntax or gate exists |
| B-5 | The L19 metric is never defined, and M14 margins are set after baselines with no action on violation |

Major findings:

| # | Finding |
| --- | --- |
| M-1 | No block or branch extent, so a large temporary in an `if` is held for the whole call |
| M-2 | `defer` that touches the returned value is unsound as written |
| M-3 | Positional removal from a `List` would silently change what a held position refers to |
| M-4 | Copying on every map and list lookup (M33) will miss performance margins; proposes temporary views |
| M-5 | Out-of-memory recoverability by extent kind stops a server on one large request; proposes recoverability by fallible function signature |
| M-6 | Writes to mutable globals from tasks are not covered; no data-race statement |
| M-7 | Gate M11 lacks the rules that identify session, step and microbatch extents (audit 4 G-4) |
| M-8 | Gate M24 does not say what happens when a checkpoint load fails partway |
| M-9 | Audit 4 gate numbers collide with plan numbers (now fixed by the crosswalk in the [edge-case audit](../edge-case-audit.md)) |
| M-10 | v1 track 6 still mentions deletion; tracks 6 and 8 and Phase C form a dependency cycle. Resolved 2026-09-16 by splitting tracks 6, 7 and 8 (`docs/plan/README.md` work tracks) |
| M-11 | Phase C removes the old surface before the new one performs; proposes an additive phase before a subtractive one |
| M-12 | "Generation exhaustion retires the slot" is an undefined silent failure; proposes 64-bit ids and a program stop |

Qwen also lists eleven minor findings and twelve decisions for the user in its
report.

### Kimi

Verdict: revision 2 is the coherent core the three advisors converged on and
resolves blockers B1–B9 from the audit. It still has three blockers and should not
go to the user as gates until audit 2 and the GLM security review are applied.

Blockers:

| # | Finding |
| --- | --- |
| B-1 | L19 is asserted but never measured. About 9 of the 23 corpus programs are expected rejections, and their expected results come from the design itself |
| B-2 | Copy-when-unproven may break C-like memory use on the AI acceptance workloads. No full training step has been hand-traced; M14 baselines have no authorship procedure |
| B-3 | The plan assumes L19 overrides L17's "new concepts" without a user decision. `Id(T)`, `Table(T)` and move-only resources are new concepts users must learn |

Major findings:

| # | Finding |
| --- | --- |
| M-1 | Revision 2 is incomplete while audit 2 and the GLM security review are pending |
| M-2 | Program stop on out-of-memory outside task, step and session extents needs a worked example and a corpus program showing the recoverable pattern |
| M-3 | Training extent identification is unspecified; proposes structural extents only (call, iteration, task, process, value-owned tables) |
| M-4 | Gate M6 presupposes v1 gate G4 option (b) |
| M-5 | Whole-program analysis has no compile-time budget or degradation order |
| M-6 | Gate M32 omits Fable's option of returning views into by-value arguments, which tokenizers need |
| M-7 | The copy fallback order (prove, reuse or move, reported copy, reject) is never stated as one rule, and the synthesis still records "no hidden copy" |
| M-8 | "Bindings copy, places change in place" is the largest silent difference from Python and deserves its own gate |
| M-9 | Gate numbers M25, M28 and M29 were undefined; revision 3 assigns all three |

Kimi also lists seven minor findings and ten decisions for the user.

### GLM, seven focus areas

Verdicts:

| Review | Verdict |
| --- | --- |
| Contract | The shape is close to sound, but item 7's closed world is false, item 8's list is not closed, and M16 is under-scoped |
| User model | The surface is value-simple, not Python-simple. It meets L21 and L17's no-vocabulary aim. L19 leaks at container choice, nested aliasing, iteration and tape rules |
| Architecture | The layer order is right. Layers 0 and 1 are unstarted, and layer 3 assumes a monomorphization step the compiler does not have |
| Performance | L20 is asserted, not enforceable. Copy-when-unproven is the structural gap and is unmeasured on the acceptance workloads |
| AI | Conditionally yes, by inference rather than demonstration. M11 has no extent rules and the native kernel bridge has no surface |
| Concurrency | Revision 2 applied most of audit 3, but no memory gate can go to the user while the security and contract evidence is missing |
| Consistency | Ledger-to-plan fidelity and gate accounting hold. The blockers repeat contract and metric defects found elsewhere |

Twenty blocker-ranked findings. The ones not already listed above:

| Review | Blocker |
| --- | --- |
| Contract | M16 must rewrite the safety contract's preamble and surfaces, not patch individual checks |
| Architecture | Layers 3–8 assume monomorphization, which does not exist; Zig `comptime` does it invisibly |
| Architecture | Phase C prerequisites are unmet: G5 undecided, `?` not tokenized, no collection types |
| Architecture | Layers 0 and 1 (v1 tracks 4 and 5) are unstarted, and everything depends on them |
| Performance | M14 cannot enforce L20: margins are set after the baselines, with no violation action and no authorship rule |
| AI | The rejection list omits a second `backward`, a gradient with respect to a rebound input, and use after move |
| Concurrency | M2's recoverability is contested: a server loop aborts, and failure to spawn is undecided |
| User model | The breaking-change table is missing two rows, which blocks approval of section 3 |

### GLM security (L12)

The reviewer compiled and ran nothing. It states a threat model first: the
untrusted inputs are checkpoint bytes, dataset files and the shapes derived from
them, threading environment variables, native library versions, native
descriptors, and A7 source written to stress the placement analyses.

Blockers:

| # | Finding |
| --- | --- |
| SEC-B1 | Every insertion decision rests on the current fact engine, which joins branches by snapshot and restore and lets calls invalidate nothing. On that engine, "proved unobservable" copy removal and edge releases are unsound, so the compiler itself can create a use-after-free. Nothing gates layers 2–8 on repairing it |
| SEC-B2 | Size arithmetic is checked only inside the compiler. A user expression can wrap before reaching a checked API, a wrapped slice bound can be proved in range, and the standard library's own growth arithmetic has no rule |
| SEC-B3 | Native libraries have no pinning, no version recording and no qualification harness, and descriptors have no gate. A wrong "borrow" descriptor is a lasting use-after-free inside a training loop |
| SEC-B4 | Checkpoint loading is specified for the happy path only. Checkpoints are untrusted bytes: the format needs constraints, a failure partway through the data phase must leave the model hard-invalid, and the file can change between validation and reading |
| SEC-B5 | There is no data-race statement, mutable globals compile today, and M36 does not reach globals |

Major findings include: assignment must read the old value before releasing it,
or the `arr = [arr[1], arr[0]]` defect becomes a use-after-free; the ban on drop
flags conflicts with closing a resource on one branch, which risks a double
release of an OS handle; resources inside a bulk-reset extent leak their handles;
generation exhaustion and wrong-table ids are undefined; reused storage has no
rule against exposing stale bytes; layer-6 reuse could alias a native kernel's
input and output; the runtime planner has no bound, so a stream of distinct
shapes is a resource-exhaustion input; and placement cannot be deterministic
while approvals are keyed by object identity and analyses iterate unordered sets.

SEC-M11 agrees with the other reviewers that gate M16 cannot be approved until
both closed lists are complete and every residual item has a defined failure
outcome.

Its summary: the architecture is sound in shape, and the risk is concentrated
where the compiler becomes the author of allocation, namely insertion, reuse and
planning.

### GLM docs check

An audit of the 2026-09-16 documentation cleanup, using about 40 compile-only
probes. No blockers and no major findings. Every decision record D.001–D.053
survived the reformat with its original status, the new disposition table matches
the ledger, all 691 relative links resolve, and every "Current A7" block the
reviewer probed compiles.

Four minor corrections, all applied:

| # | Finding |
| --- | --- |
| 1 | The `café := 1` diagnostic quotes `'é'`; the tokenizer reports the first UTF-8 byte, `'Ã'` |
| 2 | "Self-referential struct fields are rejected" was imprecise: the field compiles and only assignment fails |
| 3 | The comparative index claimed as current a rule that is design intent; today's output does rely on a Zig overflow check |
| 4 | A line citation into the reformatted decision record now points by cluster name instead |

### Repeated across reviewers

| Finding | Raised by |
| --- | --- |
| Contract item 7 and section 6 describe a false closed world | Qwen, Contract, AI, Concurrency, Consistency |
| Contract item 8's rejection list is not closed | Qwen, Contract, AI, Concurrency, Consistency |
| G4 and M6 must be decided together; MS-7 is missing from the defect list | Qwen, Kimi, Contract, Architecture, Consistency |
| The L19 metric is undefined and M14 sets margins after the fact | Qwen, Kimi, Performance, Consistency |
| Native declaration syntax has no gate | Qwen, AI, Concurrency, Consistency |
| M11 lacks extent-identification rules | Qwen, Kimi, AI |
| No block or branch extent, so large temporaries are held too long | Qwen, Contract, Performance |
| M33's copy per lookup will miss the M14 margins | Qwen, Performance, Consistency |
| M2 recoverability by extent kind is contested | Qwen, Kimi, Concurrency, Consistency |
| Copy-when-unproven may break C-like memory use, with no traced training step | Kimi, Performance, AI |
| Item 5 must release the storage of removed elements, or corpus 1 is not flat | Contract, User model |
| An `Id(T)` crossing a task without its `Table` has no rejection class | Contract, Concurrency |
| Cross-task writes to mutable globals have no rule, and there is no data-race statement | Qwen, Concurrency |
| Item 3's ban on drop flags conflicts with M7's conditional close | Contract, Concurrency |
| M24 leaves a partial checkpoint load undefined | Qwen, AI |

### Decisions the reviewers put to the user

Where reviewers disagree, both positions are recorded. None is decided.

| # | Decision | Recommendation |
| --- | --- | --- |
| 1 | Reword contract item 7 and add the missing rows to section 6 | Adopt (Contract, AI, Concurrency, Consistency) |
| 2 | Re-close the rejection list into four families and freeze it as M16's content | Adopt (Contract, AI, Concurrency, Consistency) |
| 3 | G4 with M6 | Disagreement: G4(b) type-informed call-graph edges (Qwen, Contract, Consistency) against G4(a) no stored function values (Architecture) |
| 4 | M2 recoverability | Disagreement: extent boundaries plus a task-per-request idiom (Concurrency) against fallible signatures (Qwen, Consistency) |
| 5 | M11 extents | Disagreement: audit 4's structural rules (AI) against simpler extents (Kimi) |
| 6 | Fix M14 margins and the violation action before baselines, and author baselines independently | Adopt (Performance, Consistency) |
| 7 | Require hand-traces of both training steps as Phase A exit evidence | Adopt (Performance, AI) |
| 8 | Open a gate for the native declaration surface in Phase A | Adopt; it is the critical path (AI, Concurrency) |
| 9 | M33 lookups return a temporary view, not a copy | Adopt (Qwen, Performance, Consistency) |
| 10 | Add block or branch extents, or a last-use rule for large values | Adopt before Phase D (Qwen, Contract, Performance) |
| 11 | Amend item 5 to release element storage at removal | Adopt (Contract, User model) |
| 12 | Decide index and key validity for dynamic collections | Proof-or-reject for `xs[i]`, optional-returning `get` (Contract) |
| 13 | Resolve item 3 against conditional close | Per-edge release, no drop flags (Contract) |
| 14 | Split Phase C into an additive phase and a later subtractive one | Adopt as the faithful reading of L22 (Qwen, Consistency) |
| 15 | Confirm the L20 reading, and define the L19 metric before any M-gate | Confirm (Performance, Consistency, User model, Kimi) |

The full lists, including the user-model, architecture, concurrency and AI
sub-decisions, are in each review.
