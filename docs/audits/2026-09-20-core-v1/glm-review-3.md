All checks complete. Compiling the final review.

---

# External GLM-5.3 closure review — scoped follow-up (frozen root `/tmp/a7-review-closure-wtljwg4_`)

**Verdict up front: PASS for this scoped follow-up** (D1, SAF-4, wheel/sdist verifier, `input_paths`). Not a V1 qualification. One new pre-existing backend gap found by probe (unused Zig loop label), advisory only — it predates and is untouched by these patches.

## Verification performed

Environment: Python 3.13.15, linux/x86_64, Zig 0.16.0, uv 0.12.15. All three patches match the tree exactly (`git apply -R --check` clean on d1, saf4, installed-workflows). Executed: 320 tests passed, 2 pre-existing skips (empty parametrize over the absent `examples/` dir, test_codegen_zig.py:141,174), plus fresh wheel+sdist verification, a tampered-wheel negative control, and 9 probe programs.

### 1. D1 — loop-update nonvoid discard

- Fix at `a7/backends/zig.py:2560-2561` mirrors the established void-guarded discard (`_visit_defer` 1425, `_emit_statement_inline` 2568-2574); sole continue-position caller is line 990. Nonvoid update emits `_ = step()`, void emits bare `step()` (verified in generated Zig).
- Provided tests pass natively in Debug+ReleaseFast with exact output proving `continue` runs the update and `break` skips it (test_glm_for_update.py, 4 cases).
- Independent probes: labeled loops `@outer for …; step()` with `continue outer`/`continue inner` compile and run correctly natively (`step step step done`); `test_v1_backend_regressions` + `test_zig_backend_runtime` + `test_codegen_zig` + `test_semantic_control_flow` all pass (155).
- **Advisory new finding (pre-existing, not a regression)**: an A7-labeled loop whose label is never targeted by `continue`/`break` emits a Zig label → `error: unused while loop label`. Reproduces with a plain `i += 1` update, so it is independent of this patch (label emission at zig.py:923/950/979). Add to the open-findings list; does not block this follow-up.

### 2. SAF-4 — `_learn_after_stmt` removal

- Helper and call site fully removed; no references remain in `a7/` or `test/`. The IF visitor (a7/safety.py:608-630) applies negative-condition facts before the else branch and, when the then branch always returns, keeps the else path's final facts — removal only changes behavior when the else branch overwrote guard facts, which is exactly the defect.
- 7/7 adversarial probes behaved correctly: mirror case (else returns, then zeroes → rejected), ref-call mutation joined with else (rejected), fact flow through assignment (accepted), then-assigns-nonzero when else returns (accepted), no-else join control (rejected), else-assigns-unknown-param (rejected — the sound direction; the old code unsoundly accepted), while-body mutation (rejected). Provided tests (3 mutations incl. `defer`, 4-control native program `5 5 5 0 0` both profiles) pass; `test_audit_safety_repairs` + `test_safety_precursors` pass.
- Limit: the 255-file corpus scan evidence (`saf4-evidence/*.json`) is referenced but not included in the frozen root; I could not re-audit it directly. My probes and suites give independent semantic confidence but do not replace that scan.

### 3. Wheel/sdist verifier

- Fresh `uv build` from this root: wheel and sdist both pass full verification here (two clean venvs) — METADATA identity vs `importlib.metadata`/`a7.__version__`/CLI `--version`, doctor exit 0 with `Zig 0.16.0:` on the qualified target, valid+invalid `check` with `artifacts == {}` and unchanged workdir, debug `build`+execute, release `run` (exact stdout/stderr/exit), invalid source exit 6 with no artifact, path-with-spaces project.
- Negative control: wheel with tampered METADATA version fails with exactly `installed package version disagrees with wheel metadata: '["9.9.9", "0.3.0"]'` — validates the stale-wheel detection class described in `installed-workflows-isolated.md`.

### 4. `CompilationResult.input_paths`

- Additive last field with default (a7/compile.py:87); sole construction site uses keyword args (compile.py:121); formatters do not serialize the dataclass wholesale — no JSON schema impact, positional compatibility holds as claimed.
- Set unconditionally before mode branching (compile.py:160-161), extended with real module paths post-load with `<virtual>` exclusion (compile.py:270-273). The CLI compiles once and reuses `result.input_paths` (a7/cli.py:103) — no duplicate parsing; review-1 concern A1 is resolved in the tree. Entry/import/symlink/hardlink/directory output protection verified by test_cli_workflows.py:71-89 with byte-immutability; `test_no_recursion`, `test_iterative_traversal`, `test_cli_failures` pass (99).

### Context items

- D2 probed: still open exactly as claimed — A7 accepts the sibling-scope const, Zig rejects `unused local constant`. Status accurate, no false claim.
- D3: `site/` is not part of the frozen root, so the regenerated exports could not be checked here (out of scope).

## Review limits

Full gate (`run_all_tests.sh`/`run_release_checks.sh`) not rerun, per instruction. Evidence subdirectories (`saf4-evidence/`, `backend-glm-evidence/`) absent from the frozen root — their JSON records are cited but not directly re-auditable. Wheel verification used a warm uv cache. No provider or capability errors occurred.

**Recommendation:** accept this scoped follow-up as PASS; record the unused-Zig-label gap as a new pre-existing open finding alongside D2.
