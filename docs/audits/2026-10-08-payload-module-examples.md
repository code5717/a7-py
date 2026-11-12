# Payload and local-module examples

Example 016 preserves its untagged-union demonstration and adds a tagged union
with scalar `i32` and `bool` payloads. Its helper uses exhaustive dot-pattern
bindings. The manually specified output adds `tagged number: -17` and
`tagged flag: true`.

Example 018 preserves its standard-library calls and imports
`modules/geometry.a7`. It uses the module's public `Rectangle` type, constructor
and `area` function. A 6-by-7 rectangle produces `local module area = 42`.
The helper must accompany copied examples. It has no `main` and is excluded
from top-level example discovery. No package-distribution claim is made here.

Both updated examples passed `scripts/build_examples.py` in `debug`, `release`
and `fast` with Zig 0.16.0. Runs were sequential on CPUs 0–3 with inherited HOME
and isolated inputs and outputs. Golden lines were specified before execution.
The combined `scripts/verify_examples_e2e.py` run passed 51/51.

The same E2E run covers example 036's existing labeled `break` and `continue`.
Their expected totals are 8 and 28. Together with the separately verified
[constrained generic example](2026-10-08-generics-example.md), these programs
cover the demonstrations requested by roadmap D1. They do not establish complete
language coverage or release acceptance.

The [payload record](../../tmp/v1-completion-2026-10-07/union-payload-example/REPORT.md)
and [module record](../../tmp/v1-completion-2026-10-07/local-module-example/run.json)
preserve source identities, commands, streams and outcomes. The
[combined E2E report](../../tmp/v1-completion-2026-10-07/local-module-example/e2e.json)
records each example's result. Parent verification checked six profile results,
16 command streams, generated artifacts and all 51 E2E outcomes. Independent
source review confirmed the module qualification and discovery rules.

The runners compare normalized merged stdout/stderr. They do not separately
establish empty runtime stderr. No compiler behavior changed, no full pytest
rerun is claimed, and cyber scans remain excluded.

Site metadata, coverage and exports were synchronized. Build, export and link
checks passed. The full site check passed lint, type checking and coverage,
then reported 11 tests passed and one preview socket-listen failure with
`EPERM`. Browser rendering remains unverified. The
[parent verification](../../tmp/v1-completion-2026-10-07/local-module-example/parent-verification.json)
records the unchanged compiler baseline and the intended example changes.
