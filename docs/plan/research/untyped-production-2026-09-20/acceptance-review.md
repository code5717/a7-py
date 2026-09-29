# Independent production constant acceptance

The acceptance module is [test_untyped_constants_acceptance.py](../../../../test/test_untyped_constants_acceptance.py).
It states observable requirements from the approved
[P-TYP packet](../../packets/P-TYP-forward-globals.md).
Compiler implementation and GLM resource review run separately.

## Requirements and observation

The suite checks declaration order, aliases, independent fitting of a shared
binding, large exact binding cancellation, arithmetic categories, integer
boundaries and typed wrapping. It also checks concrete argument, return, field,
array element, length, index, pattern and generic destinations. Negative cases
cover fitting failures, concrete runtime types, invalid bitwise operands, shifts,
default overflow and duplicate patterns after fitting.

Each negative case requires a semantic CLI failure, one located cause in the
public error list and no newly emitted Zig artifact. The JSON protocol repeats
errors in its stage history. The test does not mistake that representation for
duplicate reporting within the public error list.

Accepted sources run through the real CLI, then Zig 0.16.0 in Debug and
ReleaseFast. Programs print values that have fixed expected results. Nothing is
mocked. Tests reuse existing CLI and native execution helpers.

The IEEE case batches 17 independently specified values into one native program.
Its expected bits come from the
[earlier mathematical cases](../untyped-ieee-acceptance-2026-09-20.md).
The observer changes only each final print argument in generated Zig to expose
the stored bits. It checks the count of those substitutions to detect an invalid
observer. That count is an instrumentation check, not evidence that materialization
is correct. Native output must match every fixed bit pattern in both profiles.
The observer does not verify ordinary A7 float formatting. Two separate rejection
cases cover float overflow thresholds.

## First run

Command:

```sh
.venv/bin/python -m pytest -q test/test_untyped_constants_acceptance.py --tb=short
```

The first run is in progress. Results will be recorded here after completion.
This is a focused language acceptance suite. It does not establish resource
policy enforcement, security or full release readiness.
