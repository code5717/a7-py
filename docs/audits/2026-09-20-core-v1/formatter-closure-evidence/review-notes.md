# Formatter closure review

This patch changes debug AST display only. It prints parsed type sets as `@type_set(i32, i64)` and uses `<cycle>` for malformed cyclic internal type or defer nodes. Parser-produced ASTs do not contain these cycles. Shared children retain their repeated display. No parser or language changes.

All commands ran in `/tmp/a7-console-review-isolated`, using `/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python`, version Python 3.13.15.

Focused command:
`/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python -m pytest -q test/test_console_review_regressions.py test/test_iterative_console.py test/test_cli_failures.py test/test_cli_workflows.py`
Result: 38 passed, 22.23s. See focused-tests.log.

Broader command:
`/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python -m pytest -q test/test_console_review_regressions.py test/test_iterative_console.py test/test_cli_failures.py test/test_iterative_traversal.py`
Result: 70 passed, 1 failed, 2.47s. See broad-tests.log. Failure: TestLowRecursionLimit.test_nested_expressions_10_levels, maximum recursion depth exceeded. This remains an isolated-copy result, not a claim that the integrated main gate fails.

Baseline and candidate standalone command:
`/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python -m pytest -q test/test_iterative_traversal.py::TestLowRecursionLimit::test_nested_expressions_10_levels`
Both failed. See depth-before.log and depth-rerun.log. The baseline run temporarily restored console.before.py inside this copy. No parser changes were attempted. Root reports this test passed in the main integrated gate. Cause of isolated difference remains unverified.

43 examples produce byte-identical rendered text before and after this patch, using Console(width=100, color_system=None), AST mode. See example-comparison.json. This comparison also caught and corrected a tentative fallback change for string-valued inline struct type names. The regression suite now asserts that string handling directly.

baseline-comparison.json separates the original pre-conversion behavior from the candidate before this patch. The type-set error existed before conversion too. TYPE_SLICE and AST attachment cycles already looped before conversion. Generic type and defer cycles previously raised RecursionError and looped after conversion. This patch guards type and defer formatting only. General tree attachment cycle handling remains unchanged and unqualified.

formatter-closure.patch applies cleanly to the active checkout with git apply --check. No active compiler or test files were edited by this task. hashes.json pins the candidate, baseline and patch.
