# Research status, 2026-09-20

The six original research reports are present and nonempty. Their recovery into
repository documentation is complete. They cover the requested language,
memory, AI, numerical, hardware, and security topics. They do not establish
implementation, runtime correctness, hardware support, or release readiness.

This is a documentation reconciliation. The [decision ledger](../decisions.md)
controls user choices, and the [delivery roadmap](../delivery-roadmap.md)
controls current delivery order. Historical recommendations remain advisory.
No external source was reverified in this review on 2026-09-20.

## Recovered inventory and provenance

The provenance below comes from each report's header and the
[research index](README.md). All six date their research to 2026-09-14 and
record recovery on 2026-09-15 after Plan Mode blocked the original repository
write. This review checked the recovered files, not the original CLI session
logs or temporary outputs. Session identifiers are provenance text, not
portable repository links.

| Report | Recorded reviewer and session | Requested topics covered | Evidence limit recorded by the report |
| --- | --- | --- | --- |
| [AI frameworks](ai-frameworks-codex.md) | Codex CLI, `2026-09-14T23-06-34`, `01a0a187-4fde` | JAX, PyTorch, TensorFlow, MLX, tinygrad, numerical libraries, A7-owned tensors and autodiff, mixed precision, training, checkpoint continuation, inference, acceptance scenarios | No library build, benchmark, training, recovery, ABI, or runtime qualification |
| [Hardware and providers](hardware-providers-codex.md) | Codex CLI, `2026-09-14T23-10-35`, `01a0a18a-fd95` | CPU, GPU, NPU, DSP, TPU, custom accelerators, FPGA, providers, native execution versus hosted APIs, memory and precision constraints, backend order | Public documentation and historical host identification. No hardware workloads, provisioning, account eligibility, stock, quota, or price ranking verified |
| [Language features](language-features-codex.md) | Codex CLI, `2026-09-14T23-12-26`, `01a0a18c-ae30` | Whole-language inventory, packages A-G, source rules, numerics, values, errors, functions, generics, modules, concurrency, libraries, tooling, typed IR, dependencies, milestones | Selective source inspection and in-memory probes. No full release gate, native campaign, fuzzing campaign, or platform qualification |
| [Memory design](memory-design-codex.md) | Codex CLI, `2026-09-14T23-11-54`, `01a0a18c-3179` | Ownership alternatives, allocation, regions, aliases, effects, cleanup, containers, cyclic data, task transfer, native resources, tensor saved-value lifetime | Design comparisons and proposed acceptance scenarios. Existing GLM findings attributed, not independently revalidated |
| [Memory and security](memory-security-glm.md) | OpenCode `zai-coding-plan/glm-5.3`, `ses_f5e72fdbdffe69uM5qrarD64we` | Whole-language safety and security advisory, compiler and artifact boundaries, proposed invariants, approval questions, recovery scenarios | Historical compile-only memory evidence. No memory-corruption payload executed, deployed-site audit, or current release qualification |
| [Numerical policy](numerical-policy-glm.md) | OpenCode `zai-coding-plan/glm-5.3`, `ses_f5e785e0affeur2XQ9Cxc2wgdE` | Float policy, mixed precision, accumulation, master weights, nonfinite recovery, size arithmetic, native buffers, checkpoint and loader requirements | No tests executed. A7 findings belong to the audited revision. Proposed constants and validation rules are not adopted contracts |

The numerical report records recovery through `opencode export`. The memory
security header records removal of nine progress-narration lines before its
report heading. The other headers describe preserved report bodies and omitted
pre-report narration. This review made no further edits to any original report.

The index also preserves a seventh, separate
[ownership comparison and correction](ownership-zig-odin-glm.md), from GLM
session `ses_f5e8d4575ffeZ28gnTCHhUeUuP`. It is not a missing member of the six.
Its second section explicitly withdraws parts of its first section, including
the claim that binding immutability makes safety unfixable. The correction
controls that report; the current ledger still controls A7 decisions.

## Completed research versus open work

The original six assignments have durable report-level outputs. The inventory
does not prove that every suggested follow-up, specialist output, downloaded
source, or experiment was preserved. The language report's suggested `docs/v1/`
tree was a proposal, not a record of files it created. The actual entry point
is [this research index](README.md).

| Requested work | Completed at the report level | Still open, with its evidence class |
| --- | --- | --- |
| Compare frameworks and design CPU AI | Framework and kernel roles, tensor and autodiff contracts, workload decomposition, recovery scenarios in [AI frameworks](ai-frameworks-codex.md) | Design decisions for operators, precision, mutation, and checkpoints. Later qualification needs frozen classifier and decoder recipes, data, seeds, tolerances, quality targets, and resource budgets |
| Survey hardware and providers | Execution taxonomy, vendor and provider matrices, backend candidates in [hardware and providers](hardware-providers-codex.md) | Targeted source refresh and confirmed physical access before a hardware experiment. Actual Zig integration, dispatch, precision, transfers, training, and packaging remain qualification work |
| Cover the whole language | Inventory, comparisons, approval examples, dependencies, and acceptance methods in [language features](language-features-codex.md) | Current compatibility packets and implementation evidence. Historical source observations must be reconciled against the [audit inventory](../audit/open-items.md) and [current batch evidence](../../audits/2026-09-20-core-v1/README.md) |
| Compare memory designs | Alternatives, lifecycle obligations, difficult programs, and proposed checks in [memory design](memory-design-codex.md), followed by the indexed memory studies | Candidate selection remains open. [Memory reconciliation](memory/delivery-reconciliation.md) provides workload proposals, not measured candidates or approved budgets |
| Establish numerical policy | Alternatives and precision/recovery proposals in both numerical and framework reports | L16 settles IEEE values and strict defaults. Details still need the [G1 and G3 decision work](../README.md), current compatibility evidence, and constant/runtime qualification |
| Preserve GLM security work | [Memory and security](memory-security-glm.md), [numerical policy](numerical-policy-glm.md), and later [memory review evidence](memory/review/README.md) | Current security status is unverified by this reconciliation. GLM retains ownership under L12. Historical findings and proposed mitigations are neither newly confirmed nor closed here |

The hardware report says its framework sibling was absent when checked. That is
a historical observation. Both reports now exist. Their remaining contract
disagreements still need reconciliation before a later AI implementation.

## Current decisions and historical conflicts

The following dispositions cite [L36-L45](../decisions.md) and the
[delivery roadmap](../delivery-roadmap.md). They change how research is used;
they do not certify changed compiler behavior.

| Decision | Implication for preserved research |
| --- | --- |
| L36, core V1 | Earlier requirements to complete concurrency and CPU AI before V1 are superseded. Core language, automatic memory, libraries, and installed tools come first. AI and concurrency remain design constraints and later delivery tracks |
| L37, runtime memory help | L15's absolute no-collector restriction is superseded. Reference counting, tracing, static methods, and combinations are eligible candidates. No mechanism is selected |
| L38, measured cost | Each required equivalent workload must meet a 1.10-times reviewed C baseline limit for median runtime and peak live memory, including runtime bookkeeping. Separate RSS, reserved memory, allocations, copies, cleanup, and compiler cost remain required |
| L39, checked execution | Static proof remains preferred. Required runtime checks are permitted and must survive release builds. Changing the current fail-closed behavior still requires a migration packet |
| L40, later parallel execution | Independence may be inferred only with adequate effects and storage information. Unknown effects remain sequential. Bend-inspired ideas do not approve a runtime or qualify GPU execution |
| L41, Zig integration | Zig implements native imports, runtime support, builds, and linking. Historical C ABI bridge proposals need reconciliation with this implementation boundary. Application code does not manage raw native pointers |
| L42, list identity | Growable-list assignment shares identity. Independent copies are explicit. Earlier move-on-assignment or copy-on-assignment proposals cannot define growable-list behavior. Struct and fixed-array value behavior is unchanged by this decision |
| L43, Python V1 | Keeping Zig as the backend does not authorize rewriting the V1 compiler in Zig. Stabilizing the Python compiler remains the V1 path |
| L44, A7 V2 | V1 qualification must include compiler-building workloads. V2 needs an A7 compiler built by the qualified Python compiler, then bootstrap parity before replacing Python |
| L45, implementation | The coordinator has implementation authority within approved scope. Original reports do not approve new syntax, failure behavior, or compatibility changes. Passing aggregate tests alone cannot qualify V1 |

The ledger also contains L46. It places broad comments, diagrams, organization,
and performance cleanup after the agreed V1 plan. Necessary change documentation
remains in scope. This reconciliation grants no new language approval.

Other conflicts remain explicit:

| Historical statement or disagreement | Current disposition |
| --- | --- |
| The original reports call IEEE versus finite-only unresolved | L16 settles IEEE values and strict defaults. Tensor reduction order, conversions, subnormals, and other details do not follow automatically from that choice |
| The language report recommends retaining recursive descent | Current [AGENTS.md](../../../AGENTS.md) bans recursion anywhere in `a7/`. Parser work must use iterative traversal. The roadmap requires deep full-pipeline evidence; a recursion-limit setting alone does not establish it |
| The language report proposes private-by-default `pub` exports and leaves duplicate aliases open | L25-L31 set file modules, underscore privacy, duplicate-import rejection, and related direction. [P-MOD](../packets/P-MOD-modules.md) still needs the required compatibility disposition |
| The [memory plan](../memory.md) retains historical copy semantics and a ban on runtime counting or tracing | Its current supersession note and L37/L42 control. The older body is not a selected memory contract |
| [Memory reconciliation](memory/delivery-reconciliation.md) proposes 1.25-times budgets, looser text budgets, and additive floors | L38's 1.10-times runtime and peak-live-memory limits control required workloads. The draft's date does not approve its looser numbers or substitute a Zig baseline for the required C baseline |
| [EVALUATION.md](EVALUATION.md) describes proof-or-rejection as the intended safety contract | L39 permits checked execution, subject to a migration packet. The older description does not prohibit researching runtime candidates |
| The [numerical report](numerical-policy-glm.md) calls f32 master weights a unanimous framework position; the [framework report](ai-frameworks-codex.md) says ordinary AMP does not universally imply separate f32 masters or moments | This is an unresolved attribution conflict between reports. Neither establishes the A7 contract. A targeted source check and explicit precision proposal are needed before later AI work. No framework source was reopened here |
| Historical reports mark compiler or security findings current, or imply repair from a profile change | Those labels refer to their dated snapshots. The [roadmap](../delivery-roadmap.md) and [open-items inventory](../audit/open-items.md) separate later evidence from remaining findings. This review does not rerun probes or adjudicate GLM security findings |

L3-L6 still control explicit integer widths, wrapping `+`, `-`, and `*`, and
immutable argument bindings. Their scope limits do not settle signed division
overflow, shifts, casts, allocation arithmetic, or new mutation keywords.
The [ledger](../decisions.md) records those limits. Proposed syntax in the
original reports remains proposed syntax.

## Programme inventory and missing research

The programme table below compares the seven current indexes with files on
disk. A present report means a nonempty document exists. It does not mean its
claims were verified again or that the programme passed acceptance. The
historical status entries in [README.md](README.md) remain unchanged.

| Programme | Present report files | Indexed work without a report file |
| --- | --- | --- |
| [Tooling](tooling/README.md) | `01-debug-info.md`, `07-prevention-by-design.md`, `08-agentic-debugging.md` | 7: compiler testing, static analysis, dynamic analysis, developer tooling, verified compilation, visualization, proofs |
| [Runtime model](runtime-model/README.md) | `00-claims-audit.md` | 6: deterministic concurrency, heterogeneous pipelines, snapshots and arenas, reload and schema evolution, multi-target IR, loop editing |
| [Live environment](live-environment/README.md) | `00-claims-audit.md` | 6: live systems, bidirectional mapping, value visualization, performance capture, language requirements, structural editing |
| [Language facilities](language-facilities/README.md) | None | 7: claims audit, condition systems, compile-time execution, data layout, structural programs, moldable inspection, live targets |
| [Optimization](optimization/README.md) | `01-learned-optimization.md` | 2: context profiles and the unnumbered-filename report 03 on model-proposed optimization and verification |
| [Hardware export](hardware-export/README.md) | `01-software-to-hardware.md` | None in this index. Hardware execution and synthesis qualification are separate |
| [IR](ir/README.md) | None | 2: IR design space and concrete A7 proposal |

There are 30 indexed unwritten reports, including optimization report 03, which
has no assigned filename. This is an inventory, not a request to write all 30.
[EVALUATION.md](EVALUATION.md) requires a report, section, or short ruling based
on agent and human value. The [claims register](CLAIMS.md) and
[concept map](CONCEPTS.md) prevent duplicate research.

The following priorities are this review's inference from that inventory and
the current roadmap. They are advisory, not a new delivery commitment.

| Priority | Actual gap | Existing work to reuse |
| --- | --- | --- |
| Core memory decision evidence | Compare eligible mechanisms under shared-list identity, explicit copies, cycles, bounded retention, failure cleanup, and L38's limits. Freeze equivalent C baselines and workload rules before measurements | [Memory reconciliation](memory/delivery-reconciliation.md), [reuse study](memory/reuse-languages.md), and [reviews](memory/review/README.md). Broad memory surveys already exist. Candidate measurements are verification work |
| Concrete IR design | The dedicated comparison and A7 proposal are absent. The remaining work is encoding, invariants, iterative pass design, source and storage identity, effects, proof preservation, and a migration plan | [Language report](language-features-codex.md), [IR index](ir/README.md), and the roadmap. L23's correctness-first exit still controls replacement of compiler passes |
| Compiler verification methods | Dedicated testing, static-analysis, and verified-compilation reports remain unwritten. The useful extension is a current A7 method and evidence plan for adversarial cases, reduction, pass validation, and diagnostics | Existing acceptance scenarios in the [language report](language-features-codex.md) and the [tooling index](tooling/README.md). Repeating the inventory would add little |
| Core language decision packets | Source encoding, numeric edges, errors, collections, modules, and native effects need current examples and compatibility evidence | [Roadmap packet list](../delivery-roadmap.md) and [P-MOD](../packets/P-MOD-modules.md). These are focused decision gaps, not missing whole-language research |
| Later AI and heterogeneous execution | Resolve report disagreements, pin kernel and toolchain versions, demonstrate a Zig integration path, and freeze workload recipes before qualifying a target | Original AI, numerical, and hardware reports. [Bend study](bend-for-a7.md) and the runtime claims audit provide later context. No broad hardware resurvey is needed to complete core V1 |
| Optional programmes | Re-evaluate live tools, visualization, context profiles, hardware export, and remaining facilities against current delivery needs | Programme indexes and [EVALUATION.md](EVALUATION.md). A scoped ruling may close an idea without a dedicated report |

Security follow-up remains assigned to GLM under L12. The existing
[GLM memory review](memory-security-glm.md),
[GLM numerical review](numerical-policy-glm.md), and
[later security review](memory/review/glm-security.md) are evidence pointers
only. Their security conclusions are unverified by this reconciliation.

## Documentation checks and limits

Checks for this reconciliation cover file presence, nonempty content, original
report preservation, local Markdown file targets, and the README insertion.
The six originals contained 47,195, 50,675, 92,810, 62,500, 58,956, and 32,000
bytes respectively, in inventory order. SHA-256 comparison before and after the
documentation edit checks that their bytes did not change during this task.

The programme inventory can be reproduced from repository root with
`rg --files docs/plan/research` and the seven linked programme indexes. Local
link checks resolve paths relative to each document and strip historical
`:line` suffixes and fragments before checking file existence. Absolute checkout
paths in original reports remain historical citations. A resolving path does
not validate its cited line or make it portable.

No compiler tests, release gates, site builds, native programs, benchmarks,
hardware experiments, or security probes ran for this
reconciliation. External URLs, version labels, provider availability, prices,
and security claims were not reverified. Original session recovery fidelity
beyond the repository provenance headers remains unchecked.
