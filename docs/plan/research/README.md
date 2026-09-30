# Plan research

Status: advisory evidence behind the [v1 plan](../README.md) and the
[memory plan](../memory.md). No report approves a language change, verifies an
implementation or qualifies a release. User decisions are in the
[ledger](../decisions.md). The v1 plan turns the recommendations into approval
gates.

Current reconciliation: [Research status, 2026-09-20](research-status-2026-09-20.md).

[Global constants and declaration order](global-constants-2026-09-20.md)
compares A7, Odin, Zig, Go and Rust. L47 selects development of exact-fit
untyped constants. The [revised packet](../packets/P-TYP-forward-globals.md)
contains the proposed details. The
[nonfinite baseline](untyped-nonfinite-baseline-2026-09-20.md) verifies existing
typed routes to infinity and NaN. L47 now authorizes production implementation; verification remains open.
The [first candidate review](untyped-candidate-2026-09-20/controller-review.md)
records the isolated implementation, corpus comparison and confirmed gaps.
The [numeric follow-up](untyped-candidate-followup-2026-09-20/controller-review.md)
records fixes, independent verification and remaining implementation work.
[Independent IEEE cases](untyped-ieee-acceptance-2026-09-20.md) define rounding
requirements separately from the implementation. The
[stored-bit verification](untyped-ieee-verification-2026-09-20/README.md)
records the candidate's results and the observer's limits. The
[final GLM code review](untyped-candidate-glm-2026-09-20/README.md) records findings
and their disposition. The
[GLM resource proposal](untyped-constant-resource-policy-2026-09-20.md) remains
advisory and requires implementation and integration verification.

The [GLM memory and security reconciliation](memory/research-status-2026-09-20-glm.md)
separates recorded safety evidence from current decisions. The
[recovered inputs](recovered-inputs/README.md) preserve additional briefs and
research notes, with provenance, hashes, and explicit exclusions.

## 2026-09-18 and later: the concept programmes

Seven research programmes are listed below, starting from material the user supplied on 2026-09-18. They are
organized by concept, not by any product's feature list: the concepts are named
in [CONCEPTS.md](CONCEPTS.md), every supplied idea is deduplicated and ruled in
[CLAIMS.md](CLAIMS.md), and [EVALUATION.md](EVALUATION.md) sets how deeply each
is researched — a report, a section, or a one-paragraph ruling, judging agent
value above human value.

| Programme | What it covers | State |
| --- | --- | --- |
| [tooling](tooling/README.md) | Debug information, testing compilers, static and dynamic analysis, developer tooling, verified compilation, prevention by design, agentic debugging, visualization, proofs | 3 of 10 written |
| [runtime-model](runtime-model/README.md) | Determinism, heterogeneous pipelines, snapshots and arenas, live reload, multi-target IR, loop editing | claims audit written |
| [live-environment](live-environment/README.md) | Continuous evaluation, direct manipulation, bidirectional mapping, value visualization, structural editing | claims audit written |
| [language-facilities](language-facilities/README.md) | Condition systems, compile-time execution, layout control, structural programs, moldable inspection, live targets | not started |
| [optimization](optimization/README.md) | Profile-guided and learned optimization, context profiles, AI in the compiler behind a verifier | 1 of 3 written |
| [hardware-export](hardware-export/README.md) | Compiling software into hardware: HLS, hardware construction languages, the hardware/software split | written |
| [ir](ir/README.md) | An intermediate representation for A7: the design space, and a concrete proposal | not started |

Two single reports sit outside the programmes:
[bend-for-a7.md](bend-for-a7.md) (what A7 might take from Bend 2, with the
Bend analysis in [comparative/bend.md](../../lang-safety/comparative/bend.md)),
[modules-odin-zig-go.md](modules-odin-zig-go.md), and
[cpu-memory-dop.md](cpu-memory-dop.md) (CPU memory path, mmap weight loading,
and data-oriented programming for model inference, with a7 gaps and phased
proposals).

## 2026-09-14 research reports

Codex CLI and OpenCode GLM sessions wrote these reports for the v1 plan on
2026-09-14. Plan Mode blocked the controlling session from writing them into the
repository, so they were recovered from temporary output on 2026-09-15.

| Report | Reviewer | Source session | Scope | Limits |
| --- | --- | --- | --- | --- |
| [AI frameworks](ai-frameworks-codex.md) | Codex CLI | `2026-09-14T23-06-34`, `01a0a187-4fde` | JAX, PyTorch, TensorFlow, numerical libraries, float contract, mixed precision, autodiff, acceptance scenarios | No library built, benchmarked or runtime-qualified |
| [Hardware and providers](hardware-providers-codex.md) | Codex CLI | `2026-09-14T23-10-35`, `01a0a18a-fd95` | CPU, GPU, NPU, TPU, FPGA and custom accelerators; providers; backend roadmap | Vendor pages change; no hardware qualified |
| [Language features](language-features-codex.md) | Codex CLI | `2026-09-14T23-12-26`, `01a0a18c-ae30` | Whole-language inventory, packages A–G, dependencies, milestones | Selective source inspection and in-memory probes only |
| [Memory design](memory-design-codex.md) | Codex CLI | `2026-09-14T23-11-54`, `01a0a18c-3179` | Ownership, allocation, regions, tensor storage lifetime | Existing GLM findings attributed, not revalidated |
| [Memory and security](memory-security-glm.md) | OpenCode `zai-coding-plan/glm-5.3` | `ses_f5e72fdbdffe69uM5qrarD64we` | Whole-language memory safety, security boundaries, approval questions | Compile-only memory evidence; no payload executed |
| [Numerical policy](numerical-policy-glm.md) | OpenCode `zai-coding-plan/glm-5.3` | `ses_f5e785e0affeur2XQ9Cxc2wgdE` | Float semantics, mixed precision, allocation arithmetic, native buffers, checkpoint security | No tests executed; A7 facts from the audited revision |
| [Ownership versus Zig and Odin](ownership-zig-odin-glm.md) | OpenCode `zai-coding-plan/glm-5.3` | `ses_f5e8d4575ffeZ28gnTCHhUeUuP` | Immutable arguments, parameter modes, Zig, Odin and Jai comparison | The second section corrects and withdraws parts of the first. The correction is authoritative |

Codex session identifiers refer to rollout files under `~/.codex/sessions` on the
author's machine. They are provenance records, not repository links.

## Memory design inputs, 2026-09-15 and 2026-09-16

The [memory directory](memory/) supports the
[memory brainstorm record](../memory-brainstorm.md) and the
[memory plan](../memory.md). The brainstorm record explains the order in which
these inputs were produced.

### Summaries by the controlling session

| File | Content |
| --- | --- |
| [Synthesis](memory/synthesis.md) | Agreement, disagreement, decisions and falsifying programs across the advisors; where the plan departed |
| [Edge-case audit](memory/edge-case-audit.md) | Summary, blockers, current-compiler defects and gate crosswalk for the five audits of memory plan revision 1 |
| [Reviews](memory/review/README.md) | State and findings of the Kimi, Qwen and GLM reviews of memory plan revision 2 |
| [Storage reuse study](memory/reuse-languages.md) | Carp, Koka, Lean 4 and Roc: what is static, what the count buys, FP²'s limits, corrections to earlier documents |
| [Functional memory fact check](memory/functional-memory-fact-check.md) | Two user-supplied texts on Perceus, region inference, substructural types and escape analysis; corrections and A7 relevance; six items checked against sources |
| [Gemini comparison](memory/gemini-comparison.md) | Gemini table of Koka, Lean 4, Roc, MLKit and Carp, supplied by the user; annotations checked except MLKit |
| [Advisor prompt](memory/advice-prompt.md) | Prompt sent to GLM, Fable and Grok |
| [Review prompt](memory/review-prompt.md) | Prompt sent to Kimi, Qwen and GLM |

### Evidence, preserved verbatim

| File | Author | Content |
| --- | --- | --- |
| [Notes A](memory/notes-a-lang-safety-01-04.md) | Reading subagent | `lang-safety` 01–04 |
| [Notes B](memory/notes-b-lang-safety-05-07.md) | Reading subagent | `lang-safety` 05–07, Codex review, compile-time knowledge |
| [Notes C](memory/notes-c-decisions-handoff-modes.md) | Reading subagent | Decision register, HANDOFF, parameter modes |
| [Notes D](memory/notes-d-conversions-narrowing-edge-cases.md) | Reading subagent | Conversions, narrowing, 12 edge cases |
| [Notes E](memory/notes-e-comparative-languages.md) | Reading subagent | All 13 comparative language studies |
| [Notes F](memory/notes-f-plan-memory-research.md) | Reading subagent | Plan memory, security, ownership and numerical research |
| [Notes G](memory/notes-g-language-ai-hardware.md) | Reading subagent | Plan language, AI and hardware research |
| [Notes H](memory/notes-h-audits-pdfs-current-memory.md) | Reading subagent | Audits, pointer-syntax PDFs, current memory surface, fixtures |
| [GLM advice](memory/advice-glm.md) | OpenCode `zai-coding-plan/glm-5.3` | Architecture, concepts, hard cases, prior art, plan critique |
| [Fable advice](memory/advice-fable.md) | Claude Fable subagent | Verified codegen facts, analyses, stores and handles, hard cases, prior art, plan critique |
| [Grok advice](memory/advice-grok.md) | Grok CLI | Architecture, concepts, hard cases, prior art, plan critique; contains two successive drafts |
| [Audits 1–5](memory/audit/) | Five audit subagents | Edge cases in memory plan revision 1 |
| [Qwen review](memory/review/qwen.md) | Qwen Code CLI | Review of memory plan revision 2 |
| [Kimi review](memory/review/kimi.md) | Kimi CLI | Review of memory plan revision 2 |
| [Language reports](memory/languages/) | Claude research subagents | Carp (with a re-check of two findings), Koka, Lean 4 and Roc memory management |

## Reading the evidence

- Each evidence file starts with a provenance header: source, session where one
  exists, date and status. The body below it is unchanged, except that nine lines
  of progress narration before the GLM memory-and-security report heading were
  removed.
- Reading notes paraphrase their sources, cite line numbers and mark their
  inferences. They may contain small citation errors; check the cited line before
  relying on it.
- Advisors and audits use their own names for concepts. The
  [synthesis](memory/synthesis.md) maps them to the plan's terms.
- Reports cite absolute paths such as `/home/cx89/Projects/pl-dev/a7-py/...` from
  the author's checkout. Those links do not resolve on other machines. They are
  kept as historical citations, like the broken citations recorded in the
  [2026-09-14 docs cleanup report](../../audits/2026-09-14/docs-cleanup-report.md).
- Code blocks labeled `a7` in these reports include proposed syntax, pseudocode
  and `#` comments. They are not runnable A7 examples.
- Reviewers accessed external sources on 2026-09-14. Their claims were not
  rechecked for the plan.
- The language reports accessed sources on 2026-09-16. Each labels claims that
  come from DeepWiki, search snippets or its own inference.
