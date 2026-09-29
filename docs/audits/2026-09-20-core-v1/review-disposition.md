# Review disposition

The reports are advisory. This table separates reproduced findings from reviewer
attribution and scope claims. It does not qualify V1 for production.

| Review item | Disposition |
| --- | --- |
| Review 1 D1, nonvoid loop-update result | Reproduced and repaired. Native tests cover void/nonvoid calls, continue and break in both profiles. Included in the second full gate. |
| Review 1 D2, constant bindings | Reproduced and open. Scope identity is missing from usage/shadowing handling. No blanket-discard workaround was added. Recorded in STATUS and the decision ledger. |
| Review 1 D3, old release command | Corrected in the project page and regenerated exports. |
| Review 1 A1, changing reviewed tree | Confirmed. The first review read the main tree instead of its intended candidate. Its findings were independently checked. Later reviews use separate Git roots with explicit --dir. |
| Review 1 A2, temporary P-TYP evidence | Native and corpus results plus experiment source are archived here. The packet links to them. |
| Review 1 A3, ledger range | STATUS now cites L36-L46. |
| Review 2 F1, type-set AST display | Reproduced. Baseline comparison shows this crash predates the conversion. The formatter-only follow-up passes 106 integrated checks and GLM review 4. |
| Review 2 F2, cyclic formatter input | Generic/function type and defer cycles regress from RecursionError to unbounded traversal. Slice and statement-tree cycles already looped in the pre-conversion formatter. The applied follow-up adds bounded type/defer rendering; existing tree-cycle behavior remains separate. |
| Review 2 F3, unescaped semantic table messages | Latent direct-formatter defect remains open. Current CLI semantic failures use the safe error formatter, not this success-path table. |
| Review 2 F4, nil displayed with None | Existing cosmetic behavior, outside the required correction. |
| Review 2 F5, exponentially large type spelling | Inherent output growth, also present before conversion. No output-size limit is claimed. |
| Review 4, formatter closure | PASS for type-set display and bounded type/defer cycles. Reviewed formatter and test hashes match main. Existing tree cycles, markup, nil display and output growth remain open. |
| Review 3, integrated follow-up | PASS for D1, SAF-4, installed workflows and input_paths. The unused-loop-label failure was independently reproduced with a valid targeted-label control and remains open. |

Reviewer 2's frozen copy did not include Git history, so its provenance caveat is
material. The saved baseline archive and worker before/after copies establish
the attribution corrections above. Raw model output remains unchanged.

The initial renderer-review attempt ended after an OpenCode external-directory
permission rejection. An explicit project directory resolved that connection
problem. The retry produced its full review. No model time or turn limit was set.
