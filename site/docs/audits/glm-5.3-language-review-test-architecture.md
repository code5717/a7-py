<task id="ses_f44deb3d5ffeEvfExUoI45h5V8" state="completed">
<task_result>
# A7 Test Architecture & Evidence Quality Review

**Verdict: the prior findings are mostly still current.** The tautological cast-classifier matrix, the one-assertion-form parser files, and the unfalsifiable `isinstance(result, bool)` tests are all still in the tree; the error-stage matrix is real but has no exit-8 or stderr-separation coverage; the 43 goldens are normalized-string change-detectors (not byte-exact, never stderr-separated) and remain the only definition of `{}` formatting. The gate log is a genuine full 9-check run from today. Details below; I modified nothing and ran no tests.

## What I read

- `run_all_tests.sh` (82 lines); `pyproject.toml` (32)
- `scripts/`: `verify_examples_e2e.py` (36), `verify_examples_common.py` (276), `build_examples.py` (330), `verify_error_stages.py` (82), `error_stage_common.py` (300), `verify_wheel_install.py` (149); listed all 12 scripts
- `test/`: 53 `.py` files, ~66k source lines (excluding `__pycache__`), 1,233 test functions → 2,651 collected tests per gate log; `test/fixtures/golden_outputs/`: 43 `.out` files
- `examples/`: 43 `.a7` files (000–042)
- Deep-read: `test_cast_safety_matrix.py` (322), `test_error_stage_matrix.py` (253), `test_examples_e2e.py` (89), `test_zig_backend_runtime.py` (226, partial), `test_codegen_zig.py` (header/helpers), `test_parser_extreme_edge_cases.py` / `_type_combinations.py` / `_basic.py` / `_edge_cases.py` (partial), `test_semantic_expressions.py:95-139`, `test_semantic_types.py:170-199`, `test_semantic_generics.py` (partial), `a7/parser.py:164-308`, `a7/ast_nodes.py:609-641`, `a7/compile.py:49-57`
- `site/docs/audits/ui-components-evidence/release-gate.log` (33 lines, mtime 2026-09-19 22:12 +0300, **untracked** — `git status` shows `??`)
- `examples/013_pointers.a7`, `017_methods.a7`, `035_matrix.a7`, `037_language_tour.a7`; goldens 035/013/017/019/015/011
- `docs/plan/audit/open-items.md:140-200` (the repo's own claim ledger, for cross-checking only)

Not examined: `test/norec_scan.py` and `test_no_recursion.py` internals, `test_release_tooling.py` body, `test_iterative_traversal.py`, site UI files, `a7/backends/zig.py` body. No mutation testing was run (read-only constraint); mutation-equivalence numbers below are structural estimates, marked as inference.

## 1. Tautology census — prior claims vs current state

| Prior claim | Current state | Status |
|---|---|---|
| `classify_cast` mutation leaves suite passing | `expected_without_proof` still computes expectations by calling `classify_cast` (test/test_cast_safety_matrix.py:80-83) and 4 parametrized classifier tests (lines 108-174, 900 collected cases) compare the function to itself or to internal consistency (`allowed is (kind is not FORBIDDEN)`, line 146; `first == second`, line 137) | **Confirmed, unrepaired** |
| cast matrix ≈ half the suite | ~1,240 of 2,651 collected tests (46.8%) come from this one file (15×15 primitives × 4 classifier tests = 900, plus 340 pipeline tests) | **Confirmed, proportion unchanged** |
| parser files one assertion form each | `test_parser_type_combinations.py`: 35/35 tests end in `assert ast is not None`; `test_parser_creative_cases.py`: 31/31 assert only `result.kind == NodeKind.PROGRAM`; `test_parser_extreme_edge_cases.py`: 57/62 `assert ast is not None` | **Confirmed, unrepaired** |
| `get_binary_precedence` untested | Defined at a7/ast_nodes.py:609 with a 15-operator table; only `+` over `*` is pinned structurally (test/test_parser_basic.py:167-174). test/test_parser_edge_cases.py:52-60 *comments* the full shape `((1+(2*3))+(4*5))+6` but asserts only the top-level operator (line 60). No test pins shift/relational/bitwise ordering or left-associativity of `-` or `/` | **Confirmed, unrepaired** |
| 47% assert nothing | Structural estimate now ~50-53%: 900 self-comparing cast cases + ~124 "parse didn't raise" parser tests + 31 `assert isinstance(result, bool)` (test_semantic_types.py:196, test_semantic_generics.py:145,233,293,428…) | **Confirmed (inference; not re-measured by mutation)** |

Why `assert ast is not None` is nearly unfalsifiable: `Parser.parse()` is annotated `-> ASTNode` (a7/parser.py:164) and always constructs a PROGRAM node on success; worse, parse errors are swallowed by recovery once ≥1 declaration parsed (a7/parser.py:189-218), so these tests pass even when the parser recovers from a real syntax error and drops declarations. They verify only "no exception escaped." `assert isinstance(result, bool)` is literally unfalsifiable — `expect_success` returns `bool` by construction; the surrounding comments ("might be allowed… adjust based on actual behavior", test_semantic_types.py:192-196) show semantics deliberately left unpinned.

What *is* real in the cast file: the semantic pipeline tests (lines 177-218: float→int rejected, guard-forms accepted), the codegen-refusal test (221-230), and the del/reinit behavioral tests (264-296). `test_zig_backend_runtime.py` is the best file in the suite: real CLI, real Zig 0.16.0 Debug+ReleaseFast builds, hand-derived expected values, no mocks (lines 1-67). Mock usage overall is minimal and at named boundaries (monkeypatched git env in the secrets-scanner tests, test_release_tooling.py:497-520).

## 2. Error-stage matrix (61/61)

Arithmetic confirmed: 6 modes × 2 formats for tokenize (12) + parse (5×2=10) + semantic (4×2=8) + deferred-semantic (8) + codegen (3×2=6) + io (12) + skip-mode checks (2+2) + usage (1) = 61 (scripts/error_stage_common.py:179-291).

It checks exit codes 2/3/4/5/6/7, JSON schema 2.0 + category + `details[0]` shape, `artifacts.output_path` absent on failure, and one human-format dedup check (`combined.count("unknown backend") != 1`, error_stage_common.py:267-271).

Gaps, confirmed:
- **Exit 8 (INTERNAL)** is defined (a7/compile.py:57) and set (compile.py:121, 523) but appears in zero tests and zero scripts — no test injects an unexpected exception and asserts exit 8 / category `internal` / traceback suppression.
- **stderr separation is never checked**: every human-format assertion combines streams (`combined = proc.stdout + proc.stderr`, error_stage_common.py:86; same in test/test_error_stage_matrix.py:69,98,143,170,215,240). A compiler that prints diagnostics to *both* streams passes everywhere except the single codegen dedup count. The only stderr-specific assertion in the suite is the usage test (test_error_stage_matrix.py:253).

## 3. Golden outputs (43/43)

- **Match is normalized, not byte-exact**: `normalize_output` collapses CRLF and strips per-line trailing whitespace (scripts/verify_examples_common.py:67-74), then string-compares. `--update-golden` regenerates fixtures from current behavior (lines 151-155), so goldens are change-detectors, not independent expectations.
- **stderr is merged, never separate**: runner uses `stderr=subprocess.STDOUT` (verify_examples_common.py:129; build_examples.py:130). A program writing garbage to stderr still passes as long as stdout matches and exit is 0 — and since the merge puts stderr *into* the comparison, the same blob also can't be distinguished from stdout. There is no golden stream for stderr and no assertion that stderr is empty.
- **No rejected-on-purpose example**: all 43 examples must compile, build, run, and match. Nothing negative exists at the e2e layer except the 5 synthetic stage sources. Confirmed by directory listing and the verifier's `find_examples` (examples glob only).
- **No std/mem or std/string coverage**: grep for `import "std/mem"` / `"std/string"` over examples/ and test/ returns nothing; all 42 imports are `std/io`. No file-I/O example. Confirmed.
- **Goldens are the de facto `{}` format spec**: SPEC.md has no output-formatting section (only incidental `printf` mentions at SPEC.md:617,681,793 and a helper error note at :1580). Formats pinned only by goldens: `{ 6, 8, 10, 12 }` for `[4]f64` (golden 035), `3.14159` float rendering, `char = A`, `nil = null`, `bool = true` (golden 019). The repo's own ledger says the same (docs/plan/audit/open-items.md:151).

## 4. Examples shaped around the ref-mutability defect — confirmed

- 037 (the language tour) states the workaround as a rule: "Split declaration and assignment here so the generated native local is mutable before it is passed by reference" (examples/037_language_tour.a7:111-113).
- 013 does the same split (examples/013_pointers.a7:12-13); 017 has a redundant `c.value = 0` immediately after `Counter{value: 0}` (examples/017_methods.a7:16-17). open-items.md:151 records that the defect "does not reproduce on this tree or at HEAD" — i.e. the workaround may be dead but is still canonized in the tour. Not verified by me (would require compiling).
- **035_matrix**: `c = a + b` on `[4]f64` (examples/035_matrix.a7:12) is the only example use of element-wise `+`. The prior "no test" claim is **partially stale**: semantic accept/reject tests now exist (test_semantic_expressions.py:106-138 — shape mismatch, element-type mismatch). Still missing: any runtime/codegen test of element-wise `+` (test_zig_backend_runtime.py has none; the only runtime evidence is the 035 golden).

## 5. Release-gate log

Contents: all 9 checks from `run_all_tests.sh`, all PASS — 2,651 pytest tests in 589.57s, 43/43 e2e, 43/43 debug artifacts, 43/43 release artifacts, 61/61 error-stage, docs-style ok, secrets ok, wheel built (a7_py-0.3.0) and clean-venv smoke-verified; summary 9/9. No timestamps or environment info inside the log; the only provenance is the file mtime (2026-09-19 22:12 +0300) and that it is **untracked in git**, so it evidences a local run, not a CI artifact. The `testpaths = ["test"]` fix is in place (pyproject.toml:28-32) with a comment referencing the 2026-09-18 gate break — that repair is confirmed.

## 6. Most valuable missing tests (ranked)

1. **Pin `get_binary_precedence` against a hand-written table**: parametrized AST-shape tests for each tier boundary (`1 << 2 < 3`, `1 & 2 ^ 3 | 4`, `a < b == c`) plus left-associativity (`(10 - 3) - 2`, `(10 / 2) / 5` — assert tree shape, and pin runtime values 5 and 1 in test_zig_backend_runtime.py). Today a constant precedence function survives everything except `+`/`*`.
2. **Replace the self-comparing cast matrix with a hand-authored expectation table** (i32→i8 narrowing-with-guard, u8→i32 lossless, i32→u32 forbidden without proof, f64→i32 forbidden) independent of `classify_cast` output; keep the existing pipeline tests.
3. **Narrowing-cast runtime behavior**: out-of-range value (`x: i32 = 300; y := cast(i8, x)` with guard) — nothing pins whether this is rejected, checked, or wraps; add a Debug+ReleaseFast runtime test with the hand-derived value.
4. **Exit-8 INTERNAL contract**: monkeypatch one stage to raise `RuntimeError`, assert exit 8, JSON `category == "internal"`, human stderr (not stdout) carries the message, traceback only with `--verbose`. Zero coverage today.
5. **stderr separation invariants**: for each human-format stage error, assert the diagnostic appears in stderr and stdout is empty (or contains only the declared prefix); mirrors the JSON path where stdout must parse cleanly.
6. **Separate stderr goldens**: run all 43 binaries with `stderr=PIPE`; assert empty stderr (or a recorded `.err` golden). Catches panic-path writes the merged stream conflates, and makes exit codes other than 0 testable.
7. **Element-wise `+` runtime test** in test_zig_backend_runtime.py (Debug and ReleaseFast), including `{}` rendering of float and int arrays beyond the single 035 golden.
8. **`{}` formatting unit tests + SPEC section**: pin float precision, bool/char/nil/array rendering (goldens 019/035 currently define them implicitly); then the goldens stop being the spec.
9. **Rejected-on-purpose examples**: an `examples/invalid/` set with expected exit code and stderr fragment, wired into the e2e verifier — currently no negative program exists between the 5 synthetic stage sources and nothing.
10. **std/mem and std/string e2e**: at least one example each (grep shows zero usage anywhere); same for file I/O.

## 7. Coverage illusions and layer gaps (summary)

- Assertions mirroring implementation: cast matrix lines 80-83/110-146 (confirmed).
- Unfalsifiable assertions: 169× `assert ast is not None`, 51× `assert result.kind == NodeKind.PROGRAM`, 31× `assert isinstance(result, bool)` (counts from grep across test/; confirmed forms, per-file counts above).
- Parser-acceptance vs compile gap: recovery swallowing (a7/parser.py:189-218) means "parsed without raising" does not imply declarations survived; PRD-33 (`x, y := 10, 20` exits 0, emits broken Zig) is the known live instance per open-items.md:200 — I did not re-verify by compiling.
- Zig-compile vs native-behavior gap: test_codegen_zig.py stops at `zig ast-check` + text patterns; only 3 programs in test_zig_backend_runtime.py and the out-of-pytest e2e scripts cross the build/run boundary.
- Suite concentration: one file supplies ~47% of collected tests; three parser files supply 117 tests with a single weak assertion form each. The gate's "2,651 passed" overstates independent evidence by roughly 2× (inference from structure, not measured).
</task_result>
</task>