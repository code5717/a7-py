# Contract & Release Review — Z.AI GLM-5.3 (language contract, documentation, release)

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it.

- **Reviewer**: external GLM-5.3 reviewer invoked by the controlling Codex session. Advisory only.
- **Date**: 2026-09-14. The initial review, a bounded documentation-qualification follow-up and a final report-quality correction pass all finished that day (§1a).
- **Revision audited**: commit `701c679` (`Bump anthropics/claude-code-action ...`) plus the working-tree documentation-cleanup diff and untracked files present at audit time (`docs/README.md`, `docs/audits/`, three new `test/test_pipeline_*.py` files).
- **Scope**: repository-level contract and release review excluding detailed compiler-pass internals and website CSS/JS (separate reviews exist for memory safety and website). Audit only — no implementation edits, no commits, no deployment, no full release gate run.
- **Toolchain used**: `.venv/bin/python` (CPython 3.13.15), Zig 0.16.0 at `/tmp/a7-audit-20260914/zig/zig`, direct uv binary at `/home/cx89/.local/share/mise/installs/uv/0.12.6/uv-x86_64-unknown-linux-musl/uv`.
- **Independence note**: sibling reports in `docs/audits/2026-09-14/` were **not** read before the initial report was written, per instruction. `/tmp/a7-audit-20260914/pip-audit-inventory.json` was read because the coordinator supplied it as gate evidence for independent assessment.

## 1. Unavailable capabilities and environment limits

| Capability | Status | Impact |
| --- | --- | --- |
| Visual PDF inspection (`docs/POINTER_SYNTAX_ANALYSIS*.pdf`, 7 files) | **Not performed** — the Read tool returns "this model does not support pdf input" | Figures, tables, and layout of the PDFs remain unreviewed. Extracted-text qualification (§5) is **not** a substitute for visual review: pdftotext demonstrably garbles the feature-matrix tables (e.g. `Zig: value = ptr.*..*;` artifacts) and the follow-up below relies on text only. |
| Docs-site rebuild verification (`bun run build`) | **Not performed by this reviewer** — the tool call was rejected by an external-directory/permission approval; not retried per instruction | My own rebuild verification is unavailable. The coordinator subsequently ran the rebuild successfully (`site-lint: ok`, `bun run build`, 9 docs built) and an internal-link check over 10 pages / 259 links with zero errors — see `evidence/site-check-after-cleanup.log` and `evidence/site-links-after-cleanup.json` (**coordinator-attributed evidence**, not independently re-run by me). |
| Full release gate (`./run_all_tests.sh`, wheel build/install smoke, bun audits) | Not run by design (coordinator owns the gate) | Gate results in §6 are the coordinator's numbers plus my independent pytest runs. |
| Network vulnerability lookups for pip-audit re-execution | Not re-run; coordinator's JSON used as evidence | pip-audit conclusion rests on the supplied inventory JSON plus command-form analysis. |

### 1a. Follow-up log

1. **PDF qualification follow-up** (coordinator-requested): all seven PDFs had been extracted by the coordinator with `pdftotext` into `docs/audits/2026-09-14/evidence/pdf-text/` with `evidence/pdf-inventory.json` alongside. I read all seven extracted texts and the inventory; qualification in §5. PDFs themselves were not modified.
2. **Recursion-test correction** (coordinator-requested): the initial report called the `test_nested_expressions_10_levels` failure "environment-independent". That was wrong: it is **invocation-sensitive** — the coordinator reproduced the failure under `python -m pytest` while the `uv run pytest` full gate passes it, and I reproduced both outcomes locally (see F3). §6.2 and §7.3 are corrected accordingly.
3. **Final report-quality corrections** (2026-09-14, coordinator plus independent review; corrections only, no reruns):
   - (a) The failing `test_large_integer_folding_preserves_exact_quotient_and_remainder` is a **separate constant-folding precision defect**, not overflow-policy evidence. Its value 9007199254740993 fits `i64`, and division by 1 is exact (F3 and F7 separated).
   - (b) My proposals to xfail or soften the recursion-boundary test, and to make missing-tool suites skip, were **rejected** under the AGENTS.md test-quality rule for a required gate. Failing closed on missing tools or unmet behavior is correct (F3, §6.2, §6.3, §7.3).
   - (c) Pub-only emission is **not** a sound visibility fix. Private helpers that public functions reference must be retained (F6, §7.5).
   - (d) The two rejecting safety fixtures prove only those cases, not universal enforcement (§4 verified-correct items).
   - (e) The cleanup diff removes **13** TOC anchor strings, not six (§2).
   - (f) The seven PDFs are **not** interchangeable. The beamer variant is a subset, token-set similarity cannot prove full semantic equivalence, and all originals should be kept (§5, §7.7).
   - (g) The coordinator's successful post-cleanup site rebuild and 259-link check are recorded as coordinator-attributed evidence (§1, §2).

## 2. Documentation cleanup diff — record and assessment

Working tree at audit time (relative to `701c679`):

- Modified: `AGENTS.md`, `README.md`, `docs/SPEC.md`, `docs/lang-safety/README.md`, `site/public/docs/index.md`, `site/public/llms-full.txt` (43 insertions, 13 deletions total).
- Untracked: `docs/README.md` (new documentation index), `docs/audits/` (this audit round), `test/test_pipeline_artifacts.py`, `test/test_pipeline_diagnostics.py`, `test/test_pipeline_native.py`.

Assessment of the cleanup for preserved information:

1. `docs/SPEC.md` — only the Table of Contents anchors changed (`#introduction` → `#1-introduction` etc.). This is a **correctness fix**: headings are numbered (`## 1. Introduction`), so the old anchor form did not resolve on GitHub. No prose removed.
2. `docs/lang-safety/README.md` — purely additive "Reading status" section: acceptance of a design decision does not establish implementation; pointers to README/RELEASE/STATUS/SAFETY_CONTRACT. This materially improves authority clarity (the HANDOFF "zero runtime errors under ReleaseFast" goal is future design, not a shipped property). No prior content removed.
3. `README.md` — additive "Learn More" pointer to `docs/README.md`.
4. `site/public/docs/index.md` and `site/public/llms-full.txt` — additive, mirrored paragraphs stating research does not establish implementation coverage. Consistent with the repo-side edits.
5. New `docs/README.md` — coherent task-oriented index; anchor targets verified correct for GitHub's anchor format (`SPEC.md#35-reference-semantics` for `## 3.5 Reference Semantics`; `SAFETY_CONTRACT.md#reference-surface` for `## Reference Surface`). It correctly marks `ERROR_ANALYSIS.md` as a historical 36-example snapshot and the PDFs as historical.
6. `AGENTS.md` — additive "Test quality" section (coverage-illusion prohibition). Conformance of the new tests is assessed in §6.3.
7. `scripts/check_docs_style.py` passes on the modified tree (exit 0, `docs-style: ok`).

**No information loss detected.** The only deletions are the 13 superseded ToC anchor strings in the 13-entry numbered list; their replacements are the correctness fix above. This reviewer could not run the site rebuild (§1). The coordinator's post-cleanup rebuild succeeded, and its 259-link internal check reported zero errors (coordinator-attributed evidence: `evidence/site-check-after-cleanup.log`, `evidence/site-links-after-cleanup.json`). That covers regeneration validity at the build level. I did not byte-compare the regenerated `llms-full.txt`.

## 3. Coverage matrix

Depth legend: **R** = read fully; **P** = partial/targeted read; **X** = executed/verified empirically; **–** = not covered (with reason).

| Area | Files | Depth | Notes |
| --- | --- | --- | --- |
| Core docs | `README.md`, `docs/SPEC.md` (2220 ln), `docs/STATUS.md`, `docs/SAFETY_CONTRACT.md`, `docs/RELEASE.md`, `docs/CHANGELOG.md`, `docs/SECURITY.md`, `docs/README.md` | R | SPEC read section-by-section; README/RELEASE commands spot-executed |
| Research/archive authority | `docs/lang-safety/README.md` (+ diff), `HANDOFF.md` (head), `docs/archive/README.md`, `docs/ERROR_ANALYSIS.md` (head), dir inventories (`lang-safety/`, `comparative/`, `edge-cases/` = 12 files confirmed) | P | Disclaimers verified; deep research content out of scope |
| Pointer-syntax PDFs (7) | `evidence/pdf-text/*.txt` (all seven) + `evidence/pdf-inventory.json` | R (extracted text only) | Follow-up qualification in §5; **visual PDF review not performed** |
| CLI + pipeline | `a7/cli.py`, `a7/compile.py` | R | Modes/exit codes verified against README |
| Module system | `a7/module_resolver.py`, `a7/symbol_table.py` (ModuleTable), `a7/passes/name_resolution.py` (import handling), parser import forms (`a7/parser.py:372-416`) | R + X | Cycle/visibility/identity/dual-spelling fixtures executed |
| Type checking of module/stdlib calls | `a7/passes/type_checker.py:1300-1429` | P | file_module_call and stdlib resolution paths |
| Stdlib registry | `a7/stdlib/__init__.py`, `io.py`, `math.py`, `mem.py`, `string.py` | R | Function inventory vs SPEC §11.2 |
| Tokenizer keywords | `a7/tokens.py:178-227` | P | Diffed vs SPEC §2.4; behavioral probes run |
| Examples | all 43 `examples/*.a7` names; banned-syntax grep over all; full read of `001_hello`, `018_modules`; compile of 5 samples | P | `project_status.py`: 43 examples / 43 goldens |
| Packaging | `pyproject.toml`, `uv.lock` (rich/pytest/build entries) | R | No wheel build executed |
| Scripts | `build_examples.py`, `verify_wheel_install.py`, `verify_release_manifest.py`, `verify_archive_contents.py`, `generate_release_manifest.py`, `project_status.py`, `check_no_secrets.py` (head), `check_docs_style.py` (head), `error_stage_common.py` (head), `verify_error_stages.py` (head) | R / P | Style check executed; artifact scripts read |
| CI/release workflows | `.github/workflows/ci.yml`, `release.yml` | R | `deploy-docs.yml`, `claude*.yml` not reviewed (aux automation) |
| Test suite | new `test_pipeline_{artifacts,diagnostics,native}.py` (full read); `test_module_resolver.py`, `test_parser_error_handling_improvements.py`, `test_iterative_traversal.py:219-249` (targeted); full pytest run both invocation forms | R / P / X | See §6.2 |
| Gate evidence | `/tmp/a7-audit-20260914/pip-audit-inventory.json` | R | See F2 |
| Emitted-Zig semantics | fixtures compiled and (for a trivial print program) built with zig 0.16.0 in Debug+ReleaseFast | X | Overflow/eval-order probes; no memory-corruption payloads executed |

Not covered (explicitly): compiler passes beyond the module/call-path excerpts named above (`semantic_validator.py`, `safety.py`, `generics.py`, `ast_preprocessor.py`, full `parser.py`/`backends/zig.py` internals), website source, PDFs **as visual documents**, `main.py` beyond invocation, `site/scripts/*.ts` beyond the llms-generation lines, GitHub workflow runtime behavior (static YAML review only).

## 4. Findings (prioritized)

Legend: **Defect** = confirmed misbehavior with repro; **Gap** = documented/acknowledged limitation (severity is about doc accuracy or risk); **Nit** = minor. All repro commands use the fixtures preserved in `docs/audits/2026-09-14/repros/`.

### P1 — confirmed defects

**F1. Parser error recovery can silently discard whole declarations — including `main` — and report success.**
- Evidence: `a7/parser.py:171-199` (recovery only re-raises when zero declarations parsed, or for `Expected declaration` with exactly one decl, or `"Expected expression after"`), `a7/parser.py:235-264` (`synchronize()` resumes at `IMPORT`/declaration keywords, discarding the partially parsed enclosing function).
- Repro: `repros/a7glmr_silent_drop.a7` → exit 0, "Compiled ..." message, emitted Zig contains only `good()`; `grep -c 'pub fn main' *.zig` = 0. Without the leading `good` declaration the same body re-raises (exit 5), so the failure mode is order-dependent and therefore easy to hit accidentally.
- Contract impact: contradicts the fail-closed wording of `docs/SAFETY_CONTRACT.md` (compiler "must fail closed ... rejects the program before Zig code is emitted") at the parse stage. Also emits a Zig file with no entry point while the CLI advertises success. Not covered by the new failing tests (they target spans and artifact advertising, not silent drops).
- Suggested completion criterion: any recovery that drops a top-level declaration must either fail the compile or emit an explicit diagnostic; add a regression test for declaration-dropping recovery.

**F2. The documented dependency-audit gate command audits the ephemeral tool environment, not project dependencies.**
- Documented in `docs/RELEASE.md:63`, `docs/SECURITY.md:23`, `.github/workflows/release.yml:67`, `.github/workflows/ci.yml:53` as auditing "Python dependencies".
- Evidence: `/tmp/a7-audit-20260914/pip-audit-inventory.json` (from `uv tool run --from pip-audit==2.10.0 pip-audit --strict -f json`) lists 30 dependencies — pip-audit's own closure (`pip-api`, `cyclonedx-python-lib`, `pip-requirements-parser`, `requests`, ...). `pytest` and `build` (project dev-group deps per `pyproject.toml`/`uv.lock`) are absent; `rich` appears only because pip-audit itself happens to depend on it, at the tool env's resolved version (15.0.0), not the project's locked resolution. `uv tool run`/`uvx` builds an isolated environment, and pip-audit's default mode audits the environment it runs in.
- Conclusion: **the current command does not qualify project dependencies**; the step provides false assurance in CI and in the release gate.
- Correct project-input forms (either is acceptable; verify one and update all four doc/workflow sites together):
  1. `uv run --with pip-audit==2.10.0 pip-audit --strict` — runs pip-audit inside the project environment overlay (audits the locked `rich` plus the dev group: `pytest`, `build` and transitive deps).
  2. `uv export --frozen --format requirements-txt -o <tmp>/requirements.txt && uvx --from pip-audit==2.10.0 pip-audit --strict -r <tmp>/requirements.txt --no-deps` — audits exactly the locked resolution without an environment audit.
- Note `docs/SECURITY.md:51` already and correctly states audits cover known advisories only; that caveat stays true after the fix.

**F3. Twelve deliberately-failing regression tests document open compiler defects; one additional invocation-sensitive failure exists beyond them.**
- My independent full-suite run (zig 0.16.0 and uv on PATH): **13 failed, 2514 passed**. The 12 intended failures match the new test files' "Known failures deliberately remain visible" docstrings:
  - `test_pipeline_artifacts.py` (4): `--output`/`--doc-out` pointing at the input file is not rejected; failed compiles advertise stale `output_path`; write-failure advertises a directory as artifact.
  - `test_pipeline_diagnostics.py` (4): parse-diagnostic span column; missing-import diagnostic has no/poor location; imported parse/semantic errors lose the origin module file (consistent with F8).
  - `test_pipeline_native.py` (4): three valid-A7 binding programs (zig-keyword locals, loop-capture shadowing) emit Zig that fails to build; large-integer constant folding loses exactness — a **separate folding-precision defect**, distinct from the overflow-policy gap in F7 (see R1 note in §1a: the test's `9007199254740993 / 1` operand fits `i64` and the division is exact, so nothing in it exercises range/overflow).
- The 13th failure, `test_iterative_traversal.py::TestLowRecursionLimit::test_nested_expressions_10_levels`, is **invocation-sensitive, not environment-independent** (correcting this report's initial wording):
  - Reproduced by the coordinator under `python -m pytest` and by me under `PYTHONPATH=. .venv/bin/python -m pytest <test> -q` → **FAILED** (`maximum recursion depth exceeded`, compile exits 8 INTERNAL).
  - Passes under `uv run pytest` — the coordinator's full gate and my local check (`uv run --no-sync pytest <test> -q` → **passed**) both confirm. `run_all_tests.sh` uses `uv run pytest` (e.g. `run_all_tests.sh:50`), so gate integrity is unaffected.
  - Mechanism (from `test/test_iterative_traversal.py:219-232`): the test compiles in-process under `sys.setrecursionlimit(100)`; the remaining stack headroom depends on the harness entry point's frame depth (`python -m pytest` vs the `pytest` console script that `uv run` executes), so a representative 10-level nested expression sits within a few frames of the boundary.
  - Residual issue for `README.md:140` ("low-recursion coverage validates the supported pipeline at Python recursion limit 100 for representative programs"): the claim is only marginally true — one harness-entry difference flips a representative case. The test must keep asserting the required behavior (softening it to xfail/skip was proposed here initially and is **rejected** per AGENTS.md test quality — a required gate property stays asserted); the resolution is to reduce residual recursion or otherwise make the pipeline genuinely fit the documented limit, and to align the README wording with measured headroom.

### P2 — contract/design inconsistencies

**F4. File-import cycles are not detected, while the resolver claims cycle handling.**
- `a7/module_resolver.py:40` docstring claims "Circular dependency detection"; the `loading_stack` check (`:131`) is unreachable for the plain A→B→A case because the module is cached in `loaded_modules` **before** its dependencies load (`:187`), so the recursive re-entry returns the in-progress module at `:124`. `topological_sort()` (`:310`) does detect graph cycles but is dead code — no caller anywhere in `a7/`, `scripts/`, or `test/`.
- Repro: `repros/a7glmr_cycle_main.a7` (+ moda/modb fixtures) → no "Circular dependency detected" error is produced; the compile instead fails later on the unresolved in-module alias with spans rendered against the main file (F8).
- `test_module_resolver.py` contains no cycle test. Neither SPEC §10 nor SECURITY promises cycle rejection, so this is an implementation/docstring-vs-behavior inconsistency and a missing guard, not a user-doc breach.

**F5. SPEC §2.4 keyword list is wrong in both directions (behaviorally verified).**
- Tokenizer keywords (`a7/tokens.py:178-227`) omit SPEC-listed `cast`, `const`, `var`, `type`, `self`, `size_of`, `using` — e.g. `cast := 5` compiles (exit 0) although §2.4 reserves `cast`.
- Tokenizer reserves `float`, `int`, `uint`, `let`, `not` which SPEC omits — e.g. `float := 5` fails (exit 5). `docs/STATUS.md:20-22` acknowledges `int`/`uint` design is pending but the reservation itself is undocumented.
- Fix: regenerate §2.4 from `tokens.py` KEYWORDS (script-derived, matching the project's own "script-derived facts" priority in `docs/STATUS.md:18`), and state explicitly which spellings are reserved-but-inert.
- Note (2026-09-16): the pending `int`/`uint` design is superseded by ledger L3 and L4 (explicit widths only; no `int`, `uint` or `number`).

**F6. Module visibility (`pub`) is declared in SPEC §10.4 but not enforced in the merged-file import model, and cross-module calls skip signature checking.**
- `a7/compile.py:597-627` merges every non-import declaration of each imported file (pub or not); `a7/passes/type_checker.py:1318-1321` returns UNKNOWN for `file_module_call` calls after only visiting arguments — no arity/type check against the callee.
- Repro: `repros/a7glmr_mod_private_call.a7` → exit 0; emitted Zig contains `module___a7glmr_mod_helper__private_fn`; calling a non-`pub` function through the alias succeeds.
- SPEC §10.4 states "Non-`pub` items are file-private" without an implementation-status qualifier, unlike most other SPEC sections. Either qualify §10.4 (visibility is declarative until per-module scopes exist) or enforce visibility at the reference boundary: reject alias-qualified references from the importing file to non-`pub` items, while **retaining** private declarations in the merged emission when public functions reference them internally (pub-only emission is not a sound fix — it would break modules whose public API calls private helpers). STATUS's "broad cross-module type checking ... remain follow-up work" only partially covers this.

**F7. Fixed-width integer overflow: acknowledged gap, now with concrete divergence evidence.**
- `repros/a7glmr_overflow_i32.a7` (`big := 2147483647; wrapped := big + 1`) compiles (exit 0) and the built binary prints **2147483648** under both `-ODebug` and `-OReleaseFast` — literal-seeded arithmetic keeps Zig `comptime_int` precision, so an out-of-`i32`-range value flows through the pipeline rather than being rejected (SAFETY_CONTRACT) or wrapping.
- STATUS (`docs/STATUS.md:33-34`) and SAFETY_CONTRACT (`:59-60`) acknowledge this class as open; recording as Gap-with-evidence, not a new defect. Note the failing `test_large_integer_folding_preserves_exact_quotient_and_remainder` is a **different defect** (constant-folding precision: an exactly representable-in-`i64` value and exact division lose precision through the folder) and must not be counted as overflow-policy evidence — the two should be tracked separately. Related design note: release artifacts build with `-OReleaseFast` (`scripts/build_examples.py:25`), which disables Zig runtime safety checks in shipped binaries; that profile choice is defensible for artifacts but should be stated in RELEASE.md when the arithmetic proofs land.
- Note (2026-09-16): for integer `+`, `-` and `*`, the reject-or-wrap question is superseded by ledger L5: these operators wrap. Division, shifts and casts remain open under gate G3 in the [v1 plan](../../plan/README.md). The release profile stays open under gate G9.

**F8. Diagnostics for imported-module code use the importing file's source lines, and module identity is the import string.**
- Repro: `repros/a7glmr_dual_spelling_main.a7` — importing one file as `./a7glmr_mod_helper` and `a7glmr_mod_helper` parses the file twice and merges it twice; the resulting "Already defined" errors underline the main file's import lines and even the call statement (`x := a.pub_fn(1)`), not the duplicated declarations. `a7/compile.py:605-611` keys `seen_paths` by module-path string; `loaded_modules` likewise (`a7/module_resolver.py:53`).
- Same rendering mismatch appears in the cycle repro (module-file spans shown against main-file context). The four failing diagnostics tests in `test_pipeline_diagnostics.py` partially encode the desired behavior (origin-file preservation).

### P3 — minor defects / hygiene

**F9. Non-ASCII bytes are accepted in string literals** although SPEC Appendix D (`docs/SPEC.md:2153`) says characters outside ASCII "are not supported in string literals". `s := "é"` compiles (exit 0). Identifiers are correctly rejected with the SPEC B.2 message (exit 4). Fix SPEC D or the tokenizer, consistently.

**F10. Division-by-zero proof failure is reported under the "Unsafe type cast" heading with a cast-specific hint** ("This cast may lose information..."), and without a source span in the observed case. Message body is correct; taxonomy/hint are misleading for div/mod obligations.

**F11. SECURITY.md action-pinning claim is inaccurate for one action.** `docs/SECURITY.md:49-50` says workflow actions are "pinned to immutable commits"; `oven-sh/setup-bun@v2` in `release.yml:52` and `ci.yml:98` is tag-pinned. Also `python -m pip install uv` (both workflows) is unpinned. Pin `setup-bun` to a commit SHA or soften the SECURITY wording.

**F12. Dead/vestigial code that misleads readers about supported surface.**
- `a7/stdlib/string.py` / `mem.py` register empty modules but are never registered anywhere (`a7/stdlib/__init__.py:45-50` registers only io/math) — consistent with SPEC §10.3 but the files suggest existence.
- `a7/compile.py:251` `backend_import_errors` is initialized and reported as a pass ("Backend Import Support") but can never gain an entry — vestigial always-green pass.
- Third module search path `Path(__file__).parent.parent / "stdlib"` (`a7/compile.py:242`) points at a nonexistent root `stdlib/` in both repo and wheel layouts.
- Parser `using`-import machinery (`a7/parser.py:374-383`) is unreachable from both call paths (top-level dispatch enters `parse_import` with `IMPORT` current; the `name ::` path consumes the name first); empirically `using import "std/io"` is a ParseError (exit 5). SPEC §10.2 correctly calls it "not a current parser form" — but the dead branch contradicts the code's own suggestion.

**F13. JSON output mode prints a traceback when stdout is closed early** (`BrokenPipeError` observed when piping `--format json` into `head`). Cosmetic for automation; standard behavior for unhandled SIGPIPE-adjacent errors, but a JSON CLI aimed at automation may want graceful handling.

### Verified-correct items (positive evidence)

- Exit-code contract (README `:64-66`): usage=2, io=3 (missing file), tokenize=4 (tab character, exact SPEC B.2 message; non-ASCII identifier), parse=5, semantic=6 all reproduced.
- All README mode/format/doc-out invocations ran successfully (`--mode tokens/ast/semantic/pipeline/doc`, `--format json` schema 2.0, `--doc-out auto`/custom).
- Safety-proof spot checks behaved as SAFETY_CONTRACT describes for the two cases probed — divisor-may-be-zero division rejected, and signed→unsigned cast without non-negative proof rejected (`cast(u8, n)` with `n := -1`). These two rejecting fixtures prove **only those cases**; they are not evidence of universal enforcement of the contract's proof obligations.
- Stdlib inventory matches SPEC §11.2 exactly: io `print/println/eprintln`; math `sqrt/abs/floor/ceil/sin/cos/tan/log/exp/min/max`; typed spellings (`sqrt_f32` etc.) resolve as bare builtins to the same Zig builtin (note: the typed spellings do not type-check their argument width).
- Examples: 43 examples / 43 golden fixtures (script-derived); no `.adr`/`.val`/prefix-`&`/`*` reference operations (initial grep hits were substrings like `.value`); no `new [N]T`; recursion-free style per AGENTS.md.
- Release workflow matches RELEASE.md's prose step-for-step (manifest generation with `--require`, archive member checks incl. script-derived example count, attestations, permission split `contents: read` vs `write`, no registry publishing). Archive/manifest scripts are hardened (traversal-safe member checks, manifest path safety, commit-stamped manifest).
- `verify_wheel_install.py` checks the right things for a clean-wheel smoke (fresh venv, sanitized env, JSON schema check, Zig generation from the installed CLI) — not executed in this audit, but the coordinator's gate runs it.
- `run_all_tests.sh` step list matches RELEASE.md's claimed contents.

## 5. Historical pointer-syntax PDFs — extracted-text qualification

Basis: all seven extracted texts in `docs/audits/2026-09-14/evidence/pdf-text/` (read in full) plus `evidence/pdf-inventory.json` (sha256, pdfinfo, qpdf checks per PDF). **This is text extraction only and must not be equated with visual PDF review** (§1): pdftotext visibly mangles the comparative tables (e.g. `value = ptr.*..*;` artifacts in the readability table, and the feature matrix collapses into run-together rows), and figure/layout information is entirely absent.

**Provenance (from the inventory):** all seven PDFs were produced on **2025-09-23** (+03 timezone): base/wkhtmltopdf via `wkhtmltopdf 0.12.6` (PDF 1.4); compact/dark/latex via `LaTeX via pandoc`/`pdfTeX-1.40.25` (PDF 1.5); beamer carries metadata Title "A7 Pointer Syntax Analysis", Author "A7 Language Team". qpdf found no syntax/stream errors in any file. This dates them roughly eight months before the 2026-05-11 SPEC implementation snapshot (SPEC Appendix E) and before the current no-pointer-syntax reference surface.

**Content relationship (bounded by method):** `POINTER_SYNTAX_ANALYSIS` and `..._wkhtmltopdf_direct` are normalized-identical; after ligature/case normalization, `..._compact`, `..._dark`, `..._html_styled`, and `..._latex` show no unique word-level content versus the base (only "Different/different" and one stray `(x);` fragment). `..._beamer` is an 8-page slide **subset** of the base document, not equivalent content. Two limits of this comparison: token-set similarity after normalization cannot prove full semantic equivalence (ordering, dropped clauses, or table-only content could differ undetected), and pdftotext artifacts themselves obscure comparison. All seven originals should be kept as-is; no consolidation is recommended.

**Historical claims versus current authority:**

1. The document's "A7 Current Syntax" section presents `.adr`/`.val` property access (`ptr: ref i32 = x.adr`, `ptr.val = 100`, `swap(x.adr, y.adr)`) as the then-current implementation. **This is obsolete and now explicitly contradicted**: SPEC §3.5 ("Public address-of and dereference operators are not part of A7"), SAFETY_CONTRACT "Reference Surface" (`.adr`, `.val`, prefix `&`, prefix `*` are not public; ref arguments are passed as ordinary lvalues), and AGENTS.md A7 Source Rules ban exactly these spellings from examples/tests/docs. The repository's examples contain no such operations (verified by grep). The PDF must never be used as syntax guidance.
2. The document's primary recommendation is a **hybrid**: quick syntax `&x` / `ptr^` alongside retained `.adr`/`.val`, plus auto-deref for struct fields. **None of this was adopted**: the current surface has no address-of or dereference operators at all — not the hybrid, not the Zig-style alternative, not the Odin-style alternative. The recommendation carries zero current authority and no current doc promises it (STATUS does not list pointer-syntax operators as planned work).
3. Its feature matrix rates A7 "Null safety: Yes, Arithmetic: TBD". Today the accurate statement is different in shape: nil-ness is handled by the safety pass requiring proof before ref field access/deref (SAFETY_CONTRACT "Reference Surface" — `new`/`nil` refs treated as maybe-nil), and public pointer arithmetic does not exist. The historical row is not a current guarantee.
4. Its cross-language survey (C, C++, Rust, Zig, Odin, Jai, Go, Swift, D, Nim, V, Carbon, Pascal, Ada, Modula-2) is background research of the same nature as `docs/lang-safety/comparative/`; useful as design history only.

**Consistency check (positive):** the repository's current framing survives this qualification. `docs/README.md` labels the PDFs "historical design material" and points to SPEC §3.5 and SAFETY_CONTRACT for current reference syntax; `docs/lang-safety/README.md`'s added reading-status note states acceptance ≠ implementation. Nothing in the extracted texts needs a doc change. (An earlier draft of this report suggested noting in `docs/README.md` that the seven PDFs are one document in multiple renderings; that suggestion is **withdrawn** — the beamer variant is a subset, token similarity does not establish interchangeability, and the originals should remain listed and preserved individually.)

## 6. Gate-evidence assessment

### 6.1 pip-audit evidence

See F2. Verdict: the documented command form (`uvx --from pip-audit==2.10.0 pip-audit --strict`, identically `uv tool run --from ...`) **does not qualify project dependencies**; the supplied JSON proves it audited 30 tool-environment packages with zero project coverage (no `pytest`, no `build`, `rich` present only incidentally). Adopt correction (1) or (2) from F2 and wire it into `ci.yml`, `release.yml`, `RELEASE.md`, and `SECURITY.md` in one change.

### 6.2 pytest / gate state

- Coordinator reported 11/12 gate checks with pytest 12 failed / 2515 passed.
- My independent runs: without zig/uv on PATH: 18 failed / 2444 passed / 60 skipped / 5 errors (codegen Zig-validation tests and release-tooling tests shell out to `zig`/`uv` and fail when the tools are absent — correct fail-closed behavior for a required gate; a plain-venv invocation without the required toolchain should fail, not skip). With zig 0.16.0 and uv on PATH: **13 failed / 2514 passed**.
- Delta from the coordinator's 12: `test_iterative_traversal.py::TestLowRecursionLimit::test_nested_expressions_10_levels`. It is **invocation-sensitive**, not environment-independent (corrected; F3 gives both reproduction paths and the stack-headroom mechanism). The full gate's `uv run pytest` sees the passing variant. The coordinator's 12/2515 count is therefore consistent with my 13-failure `python -m pytest`-style run minus this flip. Recommendation: triage the boundary condition explicitly (F3) instead of relying on one invocation form. The README low-recursion claim is marginal.

### 6.3 New regression tests vs AGENTS.md "Test quality"

The three `test/test_pipeline_*.py` files conform well: no mocks at any boundary (real CLI subprocesses, real disposable files), each test states an observable requirement (input bytes preserved; exit codes; JSON payload fields; artifact presence/absence; cross-profile output equality), docstrings honestly scope what is not qualified ("do not qualify native execution or memory safety"), and the deliberately-failing tests encode real failure modes instead of snapshot mirroring. Two notes: (a) the native module fails (fixture assert) rather than skipping when zig is absent — appropriate fail-closed behavior for a gate-required capability (an earlier skip suggestion in this report is rejected per AGENTS.md test quality); (b) none of the new tests cover F1 (silent declaration drop), which is the most contract-damaging parse behavior found in this review.

## 7. Conservative completion criteria (proposed roadmap inputs)

1. **Parse fail-closed (F1)**: recovery may never silently drop a parsed-away declaration; failing test + fix + SPEC/README note on recovery semantics. Blocked-by-none; highest contract value per effort.
2. **Dependency audit correction (F2)**: one command change replicated to 4 sites; then the gate's "Audit Python dependencies" step actually audits `rich`/`pytest`/`build`.
3. **Recursion-limit boundary (F3, corrected)**: keep the boundary test asserting the required behavior (no xfail/skip softening); fix the pipeline's residual recursion so the documented limit 100 holds regardless of harness entry, or record the true measured limit and align `README.md:140`'s "representative programs at limit 100" wording with it.
4. **Keyword list regeneration (F5)**: script-derived SPEC §2.4.
5. **Module semantics decision (F4, F6, F8)**: either (a) declare the current single-file-merge model as the v0.x module contract in SPEC §10 with explicit non-goals (no visibility enforcement, no signature checks, string identity, cycles unguarded), or (b) enforce: canonical file identity for `loaded_modules`, cycle rejection via the existing `loading_stack` (move the cache write after dependency loading) or by wiring `topological_sort`, visibility enforced at the reference boundary (reject external references to non-`pub` items while retaining internally referenced private declarations — not pub-only emission), and origin-file spans. (a) is documentation work; (b) is the real feature STATUS already ranks as priority #2.
6. **Numeric brief (F7)**: STATUS already gates `int`/`uint`/`cast()` work on a design brief; feed it two separately tracked items — the overflow/range-proof gap (F7) and the constant-folding precision defect (the failing large-integer folding test) — plus the ReleaseFast artifact-profile decision.
   Note (2026-09-16): the `int`/`uint` design brief is superseded by ledger L3, L4 and L5; gate G3 replaces the brief for the remaining rules. The profile decision is gate G9.
7. **PDF originals (from §5)**: keep all seven pointer-syntax PDFs as individual preserved artifacts; no consolidation or interchangeability claim.

## 8. Unresolved design decisions (owner input needed)

- Should module cycles be errors or supported ( mutual merge )? Current behavior is accidental (neither).
- Is visibility (`pub`) a v0.x contract or a post-multi-file-redesign property?
- Release artifact profile: stay `-OReleaseFast` (fast, no runtime checks) or move to `-OReleaseSafe` until arithmetic proofs exist?
- Should the parser keep error recovery at all for multi-declaration programs, or fail on first error (simplest fail-closed)?
- Typed math builtin spellings (`sqrt_f32` on an f64) — intended loose behavior or to be typed?

Note (2026-09-16): module cycles and visibility are still open under gate G6, and the release profile under gate G9, in the [v1 plan](../../plan/README.md).

## 9. Reviewed-file inventory (explicit)

Fully read: `README.md`; `AGENTS.md` (system-prompt copy + diff); `docs/README.md`, `SPEC.md`, `STATUS.md`, `SAFETY_CONTRACT.md`, `RELEASE.md`, `CHANGELOG.md`, `SECURITY.md`; all seven `docs/audits/2026-09-14/evidence/pdf-text/*.txt` (extracted text; **not** visual PDF review), `evidence/pdf-inventory.json`, `evidence/site-check-after-cleanup.log` and `evidence/site-links-after-cleanup.json` (coordinator-attributed evidence, cited not re-run); `a7/cli.py`, `a7/compile.py`, `a7/module_resolver.py`, `a7/stdlib/{__init__,io,math,mem,string}.py`; `scripts/{build_examples,verify_wheel_install,verify_release_manifest,verify_archive_contents,generate_release_manifest,project_status}.py`; `.github/workflows/{ci,release}.yml`; `test/test_pipeline_{artifacts,diagnostics,native}.py`; `run_all_tests.sh`; `pyproject.toml`; `/tmp/a7-audit-20260914/pip-audit-inventory.json`.
Partially read (cited ranges): `a7/parser.py:160-430`; `a7/symbol_table.py:93-120,331-465`; `a7/passes/name_resolution.py:1-209`; `a7/passes/type_checker.py:1300-1429`; `a7/tokens.py:178-227`; `scripts/check_no_secrets.py:1-60`; `scripts/check_docs_style.py` (head); `scripts/{verify_error_stages,error_stage_common}.py` (heads); `test/test_module_resolver.py` (grep), `test/test_parser_error_handling_improvements.py:60-134`, `test/test_iterative_traversal.py:219-249`; `docs/lang-safety/{README.md,HANDOFF.md}` (heads/diff); `docs/{archive/README.md,ERROR_ANALYSIS.md}` (heads); `site/scripts/build.ts` (llms generation lines); `examples/{001_hello,018_modules}.a7`; `uv.lock` (three package entries).
Directory inventories: `docs/`, `docs/lang-safety/` (+`comparative/`, `edge-cases/`), `docs/archive/`, `a7/` tree, `scripts/`, `test/`, `examples/`, `site/public/docs/`, `docs/audits/2026-09-14/evidence/`.
Not read: PDFs **as visual documents** (model limitation; extracted texts stand in, qualified in §5), sibling audit reports (independence), remaining compiler-pass internals, website sources, `site/` content beyond cited lines, `.github/workflows/{deploy-docs,claude,claude-code-review}.yml`.

*This report documents reviewed areas and evidence, not exhaustive verification of the repository.*
