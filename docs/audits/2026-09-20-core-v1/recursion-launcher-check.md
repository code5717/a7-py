# Low-recursion test depends on its launcher

Both commands used the current main source and Python 3.13.15. The formatter
closure patch was not applied. No compiler or test file changed between them.

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q test/test_iterative_traversal.py::TestLowRecursionLimit::test_nested_expressions_10_levels` | Exit 1, one failed; stderr says `Unexpected error: maximum recursion depth exceeded` |
| `.venv/bin/pytest -q test/test_iterative_traversal.py::TestLowRecursionLimit::test_nested_expressions_10_levels` | Exit 0, one passed |

The full gate uses the pytest entry point and passed this case among 2,171 tests.
The isolated formatter report used `python -m pytest` and reproduced the failure
with both old and patched formatter code. The launcher difference reproduces in
main too. It is not evidence of a formatter regression.

Inference: the extra launcher stack frames exhaust the remaining recursion
budget in the existing recursive compiler pipeline. Exact frame counts were not
measured. The recursion scanner still records 24 explicit recursive groups.
The test was not weakened, skipped or removed. A full no-recursion requirement
needs compiler conversion and deep pipeline evidence independent of this launcher.
