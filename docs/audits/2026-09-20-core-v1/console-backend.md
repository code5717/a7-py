# Console and backend verification

Date: 2026-09-20. The focused checks pass. This batch repairs four backend
triggers and removes two console-formatting recursion groups. It does not
qualify core V1, automatic memory or the complete compiler pipeline.

## Backend repairs

| Trigger | Before | After |
| --- | --- | --- |
| `a = [a[1], a[0]]` with initial values `1, 2` | Native output `2 2` | Native output `2 1` |
| Character literal `'\x01'` | A7 accepts; Zig rejects an invalid literal byte | Zig builds; output contains byte `01` |
| Deferred call returning `i32` | A7 accepts; Zig rejects the ignored result | Call executes at scope exit; result is discarded |
| Unused local constant | A7 accepts; Zig rejects the unused binding | Zig builds; initializer effects remain |

The [before](console-backend-evidence/backend-before.json) and
[after](console-backend-evidence/backend-after.json) records contain exit codes,
stdout and stderr. The [source record](console-backend-evidence/backend-probe-sources.json)
contains each trigger and its safe control. The before run used an isolated
package copy with the saved pre-edit backend. Other compiler files came from
the working tree at reproduction time.

Native regressions in `test/test_v1_backend_regressions.py` run through the CLI
and real Zig in Debug and ReleaseFast. They check array reads before writes,
call order, nested array targets, nonaliasing assignment, control characters,
deferred LIFO execution and unused initializer effects. No mocks are involved.

Integration found a regression in the first unused-constant repair. An `Alias`
used only in `[Alias]i32` was incorrectly discarded, and Zig rejected the
pointless discard. The backend's AST walk omitted array-size expressions.
Adding `size` to that walk fixed the failure. The native regression now includes
constants used only through an array-size alias. See the
[failure](console-backend-evidence/constant-size-before.log) and
[follow-up results](console-backend-evidence/constant-size-after.log).

## Console conversion

`ConsoleFormatter.format_type` and `format_statement_label` now use explicit
stacks or loops. Tree attachment was already iterative and remains unchanged.
The [depth record](console-backend-evidence/console-depth.json) shows both old
helpers raising `RecursionError` at depth 400 with Python's recursion limit 100.
The converted helpers produce complete labels under the same limit.

Tests also build and render 400 nested blocks. They verify the full tree before
rendering and preserve Rich's clipping when indentation consumes terminal width.
Literal detail still truncates after 20 characters.

All 43 checked-in examples produced byte-identical before/after source, token
and AST output at width 100, with color disabled. The
[comparison record](console-backend-evidence/console-example-snapshots.json)
includes SHA-256 hashes for each rendered pair. The
[shallow baseline](console-backend-evidence/console-shallow-before.txt) is also
an exact expected-output regression in `test/test_iterative_console.py`.

Separate probes reproduced Rich markup errors for `[/oops]` in token values,
literal details and source-panel filenames. Those three paths now render the
text literally. This is not a review of every diagnostic or Rich output path.

## Checks and source identity

| Command | Result and scope |
| --- | --- |
| `uv run pytest test/test_v1_backend_regressions.py -q` | Initial four repair cases pass in both profiles, 8 passed; before the Alias follow-up |
| `uv run pytest test/test_no_recursion.py test/test_codegen_zig.py test/test_zig_backend_runtime.py test/test_audit_backend_repairs.py -q` | 205 passed before the Alias follow-up and console conversion; [log](console-backend-evidence/backend-related-tests.log) |
| `uv run pytest test/test_v1_backend_regressions.py test/test_audit_type_boundaries.py -q` | 27 passed after the Alias repair; [log](console-backend-evidence/constant-size-after.log) |
| `uv run pytest test/test_iterative_console.py test/test_cli_failures.py test/test_iterative_traversal.py -q` | 68 passed after console conversion; [log](console-backend-evidence/console-tests.log) |
| `git diff --check` on the edited compiler files | Pass |

[Source hashes](console-backend-evidence/source-hashes.json) identify the four
edited compiler and test files after the focused checks. They are not a manifest
of the entire concurrently edited checkout. The evidence includes the
[backend patch](console-backend-evidence/backend.patch) and
[console patch](console-backend-evidence/console.patch) against saved pre-edit
files. The console conversion requires removal of its two old recursion groups
from the central scanner inventory; this worker did not edit that inventory.

The full release gate, independent GLM review, installed-artifact qualification
and browser acceptance belong to separate coordinating-session evidence. These
checks do not close general alias/lifetime safety or every historical audit ID.
