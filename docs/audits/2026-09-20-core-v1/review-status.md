# External review status

Four GLM-5.3 reviews completed through OpenCode. Every prompt included the
required recursion guard. Tools and sub-agents stayed enabled. No execution or
turn limit was set. None of these reviews qualifies V1 for production.

1. [Backend and release review](glm-review-1.md) required changes. OpenCode read
   the changing main checkout despite the intended candidate directory. Findings
   were independently reproduced. D1 and D3 are repaired; D2 remains open.
2. [Renderer review](glm-review-2.md) required changes. Its initial attempt ended
   after an external-directory permission rejection, without a verdict. Explicit
   `--dir` selected the isolated repository for the successful retry. Baseline
   comparisons corrected several original-versus-regression attributions.
3. [Integrated follow-up](glm-review-3.md) passed its D1, SAF-4, installed
   workflow and input-path scope. It also found the existing unused-loop-label
   defect, independently confirmed and left open.
4. [Formatter closure](glm-review-4.md) passed type-set display and bounded
   type/defer traversal. The reviewed formatter and regression-test hashes match
   main. The reviewer did not independently repeat the 43-example comparison.

See [dispositions](review-disposition.md) for unresolved findings and scope limits.
Raw logs remain in `tmp/v1-core-implementation-tycajqwt/`; prompts, verdicts and
source identity records are preserved with this report. Exit 0 alone was not
used as evidence of a review verdict.
