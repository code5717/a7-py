# Controller review of the first isolated candidate

Date: 2026-09-20. This is an experiment, not the production compiler.
The Codex CLI completed with exit 0. Its [report](REPORT.md) states the narrow
slice it implemented. The controller's broader checks below prevent those
passing cases from being mistaken for the full P-TYP contract.

## What passed

The CLI matrix checks 29 valid source programs through A7 and native
Debug/ReleaseFast execution, plus 18 rejection cases with diagnostics and no new
artifact. Two additional probes record inherited behavior without claiming a
requirement passed. Exact large-integer fitting, both global declaration orders,
string formatting, multiple destinations and typed runtime rejection have
observable evidence in [the full matrix](final-results.json).

The selected existing tests produced 50 passes and one stale-allowlist failure.
The same failure occurred on the frozen baseline. The controller then removed
the two obsolete return-analysis groups from the main checkout's recursion
allowlist. Its scanner and return-analysis tests passed, 41 total. This changes
test bookkeeping only; it does not apply the constant prototype to production.

## Broader corpus comparison

The controller froze the first candidate and compiled the same 255 source files
as [the baseline](../untyped-corpus-baseline-2026-09-20.json). Source hashes match.
Baseline acceptance is 135; candidate acceptance is 136. No accepted source
became rejected in this inventory.

[Six files differ](corpus-comparison.json). One existing literal-fitting
reproducer changes from semantic rejection to emitted Zig. Five accepted
sources have changed generated text: substitution of known constant values,
unused-binding discards, or decimal spelling. This is a compile-only comparison.
It does not establish native behavior for the audit reproducers, and none of
those reproducers was executed by this corpus comparison.

The inventory omits test-source strings, temporary probes and dependencies.
These counts cannot establish complete compatibility.

## Independently confirmed failures against the full proposal

[Twenty-five context and numeric probes](context-results.json) used the frozen
candidate. Successful A7 cases were built and run in both native profiles.

| Requirement | Observed first-candidate result |
| --- | --- |
| Reject finite `1e100` fitting into `f32` | Fails: builds and prints `inf` |
| Reject finite `1e400` fitting into `f64` | Fails: builds and prints `inf` |
| Round the exact f32 midpoint to the even lower neighbor | Passes |
| Round a decimal just above that midpoint to the upper neighbor | Fails: rounds down |
| Round a decimal just below the midpoint to the lower neighbor | Passes |
| Compare `(9007199254740993.0 / 1.0) == 9007199254740992.0` exactly | Fails: prints `true`; required result is `false` |
| Accept exact-fit named constants in arguments, returns, struct fields and array elements | Tested examples pass and print `2` |
| Apply fitting to array indices, array lengths and match patterns | Tested examples still reject; these contexts remain unsupported |
| Keep typed u8 wrapping | Passes and prints `0` |
| Keep a runtime f64 value typed rather than implicitly fitting it to i32 | Rejects as required |

The midpoint probes use exact decimal spelling within the existing token-length
limit. The source and output are recorded, not inferred from an implementation
helper. These results confirm the read-only review's warnings about intermediate
rounding and the fallback to host floats for unsupported exact division.

The controller assigned those numeric failures to a separate Codex CLI
follow-up. This report and its evidence stay unchanged as the first-candidate
record. No resource-enforcement or security qualification is claimed.

## Reproduction and preservation

[The manifest](archive-manifest.json) hashes the copied reports, scripts,
evidence and source archives. The baseline and first-candidate source archives
preserve the compiler inputs needed to interpret the recorded source diff.
Commands in JSON retain their original workspace paths. Copied scripts also
retain their original directory assumptions; reconstruct that layout or adjust
paths explicitly before rerunning them. Native binaries and caches remain in
the temporary workspace; sources and observed outputs are preserved here.

Raw reviewer A7/Zig fixtures are preserved byte-for-byte in
`reviewer-source-fixtures.tar.gz`. Packaging keeps archived research cases from
changing the repository source-file inventory. The original copy manifest is
retained; the current archive manifest describes the packaged files.
