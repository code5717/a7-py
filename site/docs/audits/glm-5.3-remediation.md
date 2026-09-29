# GLM language audit repairs

The repaired compiler rejects the original six accepted-crashing programs before
Zig output. It also rejects four deletion variants where a fresh nil guard had
restored permission to access freed storage. Parser failures no longer emit
partial programs. Native regressions check the repaired lowering in Debug and
ReleaseFast. These results do not establish complete language safety.

## Implemented repairs

| Area | Change | Direct evidence |
| --- | --- | --- |
| Parser and lexer | Fail-closed declarations, located numeric/ellipsis diagnostics, multiline arrays, unused nested recursion rejection | `test_language_audit_parser_fixes.py` |
| Safety | Branch joins, block effects, loop invalidation, ref-call checks, deletion state, bounded arithmetic facts, slice-length relations | `test_audit_safety_repairs.py`, `test/fixtures/safety_regressions/` |
| Types | Wider compatible arithmetic types, contextual literals, constant array aliases, invalid operand/struct checks | `test_audit_type_boundaries.py` |
| Backend | Wrapping integers, compound division/remainder, escaped braces, signed abs result type, names/scopes, string arrays, wrapped generic fields, optional statement-match fallback and exhaustive expression matches | `test_audit_backend_repairs.py`, `test_language_audit_match_coverage.py` |
| CLI and modules | Root main signature and cycle diagnostics; JSON match fallback serialization | `test_audit_type_boundaries.py`, `test_language_audit_json_formatter.py` |
| Evidence | Independent cast-policy expectations and exit-8 JSON contract | `test_cast_safety_matrix.py`, `test_error_stage_matrix.py` |

The binary-tree example states capacity bounds. The calculator guards its updated
divisor. The prime example uses `d > n / d` to stop at the square-root boundary
without multiplying `d * d`. Existing golden output files were not changed.

## Verification

The [final release gate](glm-5.3-final-repair-gate.log) passed all 9 checks.

- 2,087 pytest tests passed.
- All 43 examples passed compile/build/run/output verification.
- All 43 debug and 43 release artifacts passed verification.
- All 61 error-stage checks passed.
- Documentation style, secrets, package build, and clean wheel installation passed.
- The [site check](glm-5.3-final-site-check.log) passed, including current generated
  exports, 23 pages, 428 coverage records, 1,476 local resources, 175 search
  targets, and 12 site tests.
- All 133 compiler, test, and example file hashes matched the pre-gate snapshot.
  The result is recorded in `glm-5.3-final-verification.json`.

No check in this final run failed. Earlier failures remain recorded below.
The [GLM repair review](glm-5.3-repair-review.md) independently verified the core
repairs. Its match and slice-guard findings were repaired afterward. The
[same-session closure review](glm-5.3-repair-closure.md) verified those changes
and found one remaining non-exhaustive match-expression failure. The
[final match review](glm-5.3-match-closure.md) confirmed that repair with native
execution and rejection checks. These reviews cover their stated cases, not
complete language soundness. The original reports are unchanged.

An earlier gate found a positional-struct regression, an outdated bool type
assertion, and generated Zig formatting failures. All three were corrected
before the current gate started. The failed run remains in
`glm-5.3-initial-repair-gate.log`.

Reviewer repro sources and text outputs are preserved in
`glm-5.3-repair-evidence/`. The reviewers used HEAD and dirty-path counts when
describing an unchanged tree. Those counts do not prove unchanged file contents.
The controller instead captured SHA256 hashes of compiler, test, and example
sources in `glm-5.3-final-source-snapshot.json` for final comparison.

## Remaining limits

The audit is not a request to invent unresolved language semantics. Signed
`abs(MIN)`, signed division overflow, dynamic shift proofs, full alias and lifetime
analysis, module-qualified types, generic reference read/write behavior,
array-to-slice coercion, char operations, scalar-filled arrays, `string.len`, and
named type-set specialization still have documented limits or open decisions.
Range-loop syntax is unavailable. Research examples are not evidence of current
executable syntax. Current public docs distinguish these cases from support.

Some conservative proof checks reject safe programs whose invariants the compiler
cannot express. Passing this gate does not justify a global fail-closed claim.

## Process and authorization

The user said "go fix it" after receiving the full audit and corrected concrete
examples. Decision L35 records the repair scope. Unrelated working-tree changes
were preserved; no commit or deployment was requested or performed.

One internal subagent stopped with a provider content-filter error after writing
its loop-scope patch. The controller checked the patch and completed its local
verification. OpenCode's independent GLM-5.3 reviewer remained available. Its
prompts, raw events, stderr and process results are saved alongside this report.
