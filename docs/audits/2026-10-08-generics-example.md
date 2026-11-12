# Constrained generic example verification

`examples/014_generics.a7` now demonstrates `where T: Integer` with `i32`
and `u16` arguments. The existing output stays unchanged. Its manually specified
golden fixture adds `larger signed = 9` and `larger unsigned = 300`.
This documents approved language behavior under L66; it changes no compiler rule.

The example SHA-256 is
`db9af7832e7304c3e9d03056e33bff4d0f45afbff1178fc81d641ec96a177def`.
The golden fixture SHA-256 is
`9d4216c440b1e0a9870e51946a7f22ba684e38c93a57b3410ec5dd0cdcfe728c`.

`scripts/build_examples.py` passed 1/1 for this example in each of `debug`,
`release` and `fast`, using Zig 0.16.0. The runs used private input/output
directories, CPUs 0–3 and inherited HOME. Compilation, native builds, execution
and normalized merged stdout/stderr comparison passed. The runner does not
separately establish empty runtime stderr.

The subsequent full `scripts/verify_examples_e2e.py` run passed 51/51 examples
with the updated fixture. Its [report](../../tmp/v1-completion-2026-10-07/generics-where-e2e/results.json)
records compilation, Zig validation, native build, execution and output matches.
No compiler implementation changed in this example update. Earlier full pytest
qualification remains evidence for its frozen source; pytest was not rerun here.

Comparison against the 388 core paths in `de578138` found only the intended
example, golden fixture and examples README changes. The parent verified eight
profile command streams, six generated artifacts and the E2E results.

Site exports were synchronized. The first site check caught a stale coverage
table row, which was corrected. The retry passed lint, type checking and coverage,
then reported 11 tests passed and one preview failure caused by socket-listen
`EPERM`. Direct build, export and link checks passed. Browser rendering remains
unverified. The [verification record](../../tmp/v1-completion-2026-10-07/generics-where-e2e/verification.json)
retains these boundaries and evidence hashes. Cyber scans were not run.

The [raw record](../../tmp/v1-completion-2026-10-07/generics-where-example/REPORT.md)
preserves commands, streams and artifact hashes. These scoped results do not
qualify all generic programs or establish V1 completion.
