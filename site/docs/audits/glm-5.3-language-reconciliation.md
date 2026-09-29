# Language review reconciliation

The GLM subreviews are advisory. Their claims below were independently checked against the current checkout and Zig 0.16.0. Compiler behavior was not changed.

## Confirmed with corrected reproductions

- Mixed-width arithmetic: inferred `c := a + b` for `i8` and `i64` builds because Zig infers the wider type. Explicit `c: i8 = a + b` passes A7 but fails Zig with `expected type i8, found i64`. The type checker returns the left operand type at `a7/passes/type_checker.py:1249`. The original subreview's inferred-binding reproduction did not establish its claimed build failure.
- Nested recursion: an unused nested self-calling function passes A7 and Zig, establishing a gap in the source recursion ban. Calling it from its enclosing function fails A7 type checking with exit 6. Reachable recursion and runtime stack overflow are not established by this case. The validator collects top-level functions at `a7/passes/semantic_validator.py:501`.

Sources, compiler output, emitted Zig, and build diagnostics are in [controller evidence](glm-5.3-language-controller-evidence/).

## Qualifications and rejected overclaims

- Python dictionaries use `==`, not A7 type objects' custom `.equals()`. Differing hashes where dataclass equality is false do not violate Python's hash contract. The type subreview establishes inconsistent equality definitions, not dictionary failure.
- The golden runner merges stderr into stdout before comparison. Extra stderr output fails the comparison. It does not, however, identify which stream produced expected text. See `scripts/verify_examples_common.py:123-162`.
- `std/mem` and `std/string` are planned modules. Their lack of executable tests is not missing coverage for currently registered operations.
- Deferred reassignment, compound-assignment typing, overflow gaps, and parameter-shadowing recursion claims already appear in `docs/plan/audit/open-items.md`. They are not all new findings. The opening closure section supersedes historical bullets that repeat closed issues.
- Source inspection does not prove that constant evaluation or cast handling is universally sound. The original type subreview consulted Zig 0.14, while this checkout uses 0.16. Unexecuted backend claims need qualification.

## Process

The first non-Flash run ended after OpenCode rejected access to the temporary reproduction directory. The same session resumed with `--auto`, preserving normal tools and built-in delegation. No model deadline or turn limit was imposed. The exact requested model is `zai-coding-plan/glm-5.3`. The [integrated GLM-5.3 report](glm-5.3-language-full-review.md) is complete. The original report and five subreviews are preserved verbatim. Read them with the qualifications in this file.


## Integrated verdict and evidence

The language audit found real failures despite the passing release gate. The controlling session inspected the six failing sources and their saved native diagnostics. They show two division-by-zero panics, one out-of-bounds panic, two use-after-delete segmentation faults, and one nil-reference unwrap panic after A7 acceptance. The declaration-loss probe emits only `var y = 10;`, dropping `main`. These are actionable correctness and safety findings. The review did not change compiler behavior.

The full report gives both 48 and 50 A7-case counts. These totals are not used as acceptance metrics here. The saved case sources, commands, diagnostics, and results identify what actually ran. The full test suite was not rerun by GLM; it inspected the controller's fresh 9/9 gate evidence.

## Further corrections to the integrated report

- The review's identical HEAD and dirty-path count check does not establish byte-identical files. The controller separately hashed 132 compiler, test, example, and key documentation inputs during the review and compared them after completion. None changed within that interval. That check does not cover every repository file or the period before the snapshot.
- The claim that roughly half the suite cannot fail is too strong. The review identified tautological and weak assertions, but did not rerun mutation testing to measure the current proportion. No current percentage of ineffective tests is established here.
- The report's universal claim that the safety contract holds for straight-line, call-free, defer-free code is unsupported. No such subset has been proved safe. Fixing the listed examples alone would not establish that guarantee either.
- The nested-recursion correction in the integrated report remains too broad. Called nested functions failed in its probes, but the controller's unused nested self-calling function compiles. The source recursion ban is incomplete even though reachable runtime recursion was not demonstrated.
- ReleaseFast outcomes in the report are source/toolchain inferences. The focused native probes used Debug. The audit did not execute every reported counterexample in ReleaseFast.
- The `if`-join runtime case also contains a loop. It demonstrates accepted division by zero, but does not isolate the branch-join defect from stale loop facts. The reviewer separately cites the relevant safety-pass code.
- Missing `main` must be interpreted against compile mode and whether the source is a library/module or an executable. Its absence alone is not enough to establish a defect in every mode.
- Several findings extend known families rather than discover wholly new issues. Braced deferred reassignment already has an entry in the current open-items ledger. Preserve the reproduced trigger and qualification instead of relying on the report's NEW labels.
- The roadmap's claims that some behavior-changing fixes need no approval do not override AGENTS.md. Any change to existing A7 syntax or behavior still requires the user's explicit approval with current/proposed examples and compatibility impact. No such change was made in this task.

## Review boundaries

This was a broad language audit with five subsystem reviews and focused executable checks. It was not a line-by-line review of all 2,651 collected test cases or every example. The report explicitly lists partial reads and unexecuted claims. Original prompts, raw JSON event streams, stderr, process results, subreviews, and text reproduction artifacts are retained in this directory. No deployment occurred.
