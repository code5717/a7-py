# V1 foundation batch, 2026-09-20

The first delivery batch repairs recursion enforcement and removes three compiler
helper cycles. V1 is not delivered. No language contract changed, no memory
mechanism was selected, and no commit or deployment was performed.

## Source state

The starting revision is `701c67936c70ad2b0608326e23e56cc5d38c9fdb`, with substantial
tracked and untracked repairs. [Baseline status](baseline-status.txt) and
[1,055 path hashes](baseline-inputs.json) identify that working state.
The [baseline verification](baseline-content-verification.json) confirms no path
changed during the gate. A complete local source archive, including untracked
files, remains at `tmp/v1-delivery-2026-09-20/baseline-source.tar.gz`; its SHA256 is
in the verification file. The tracked patch is in the same local directory.
Neither HEAD alone nor dirty-path counts identify these inputs.

The [environment record](environment.json) names Linux x86-64, AMD Ryzen AI 9 HX
370, the kernel and installed toolchains. These checks do not qualify another
platform.

## Implementation and evidence

| Change | Verification |
| --- | --- |
| Follow callable dictionaries at module, class, instance and local scope; distinguish constant and dynamic keys | Expanded scanner suite passes 35 tests; the same suite exposes 15 failures in the old scanner |
| Model lambdas as separate functions and distinguish queuing from invocation | Positive synchronous-recursion cases and a queued-continuation control |
| Keep unknown instance delegation unresolved rather than inventing self-recursion | Normal/conservative scan agreement plus explicit delegation tests |
| Exclude `_Func.parent` from recursive representation and test scanner-generated methods | Scanner self-scan finds no recursive generated dataclass methods |
| Iterate safety integer-literal extraction and mutation-base extraction | 5,000-level helper inputs at Python recursion limit 100 |
| Iterate symbol-table dumping, preserving order and text | Exact shallow output and 2,000 nested scopes at recursion limit 100 |

The [before-helper failures](helpers-before.log) reproduce `RecursionError` in all
three old helpers. The [isolated candidate run](helpers-candidate.log) passes all
three tests. Scanner before/after evidence is in
[the candidate report](verification-v2.md), [before log](before-v2-pytest.log),
[after log](candidate-v2-pytest.log), [patch](norec0b-v2.patch) and
[source hashes](norec0b-v2-hashes.json).

After applying the batch, 82 focused scanner, helper and existing traversal tests
pass. The scanner lists shrink from 31 to 28 function groups; one `deepcopy`
caller and 44 generated dataclass methods remain. No new exception was added.
The helper tests do not establish deep full-pipeline support. Dynamic Python
features outside the scanner's model remain listed in its header.

## Release verification

The [baseline gate](baseline-gate.log) passed all nine checks: 2,087 tests, all
43 examples, 43 debug artifacts, 43 release artifacts, 61 diagnostic cases,
document style, secrets scan, package build and clean wheel installation.
The [site baseline](site-baseline.log) passed `bun run check`, including export
freshness, 1,476 resources and 175 search targets. Site source is unchanged by
this batch; no fresh visual or accessibility qualification is claimed.

The [final gate](final-gate.log) passed all nine checks with 2,106 tests, 43
examples, 43 debug and 43 release artifacts, 61 diagnostic cases, document style,
secrets scan, packaging and clean wheel installation. The
[final source verification](final-source-verification.json) distinguishes the
gate's inputs from subsequent documentation edits. Executable compiler and test
code remained unchanged during verification; the scanner header changed only its
module docstring. Focused checks also passed after that clarification.

[GLM review](glm-review.md), [closure review](glm-closure.md) and
[module review](glm-module-review.md) are advisory. The controller verified
findings and corrected inaccurate provenance claims in the
[review disposition](review-disposition.md). The module packet remains a draft.
The gate does not close known compiler gaps or qualify V1.

## Roadmap and memory research

The [delivery roadmap](../../plan/delivery-roadmap.md) retains the entire V1
boundary and groups the unresolved contracts. The
[critical/high inventory](critical-high-inventory.md), also available as
[JSON](critical-high-inventory.json), reconciles 49 IDs in the original six
compiler audits. It separates historical closure from current revalidation and
records the SAF-11 numbering collision. It does not enumerate every later finding
or close the correctness-first gate.

The [memory reconciliation](../../plan/research/memory/delivery-reconciliation.md)
records competing designs, ten application workloads and proposed measurement
budgets. No candidate has been benchmarked under that protocol. The proposed
ordinary/advanced distinction remains unapproved. Typed IR, production memory
analysis, modules, concurrency and CPU AI retain their documented dependencies
and decision gates.


## Original-probe follow-up

An independent agent reran 45 compiler-only checks from six original findings.
[Sources and results](original-probes/summary.md) distinguish repaired JSON and
column failures from remaining parser ambiguity, lexical decisions and the
1,100-module recursion failure. All compiler hashes stayed unchanged. No compiled
program ran. This is additional diagnostic evidence, not full native closure.


## Module compatibility packet

The [P-MOD draft](../../plan/packets/P-MOD-modules.md) now shows eleven current
fixtures, including seven harmless native executions. It preserves L25-L31 and
makes the proposed compatibility breaks explicit. It is not implementation
approval. A full compatibility scan, file-identity details and observable module
initialization order still need resolution before approval is requested.
