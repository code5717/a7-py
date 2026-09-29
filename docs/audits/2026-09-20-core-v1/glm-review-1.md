All verification complete. Compiling the final review.

---

# External Review — A7 candidate-1 batch (V1 core implementation)

**Verdict up front: CHANGES REQUIRED for this batch** — two narrow backend gaps and one docs-sync item. Everything else in the batch verifies correct, truthful, and well-tested. This verdict is for the batch only, not for V1 production.

## What I verified (evidence)

Tree state = baseline HEAD `701c679` + full batch; `candidate-1.patch` is this batch's delta. Zig 0.16.0 available locally.

Focused tests run, all passing: `test_iterative_module_loading.py` (5), `test_v1_backend_regressions.py` (8, native Debug+ReleaseFast), `test_cli_workflows.py` (11), `test_release_version.py` (3), `test_release_tooling.py` wheel+sdist test + no-zig test, `test_no_recursion.py` (36), `test_iterative_traversal.py` (44), `test_module_resolver.py` + `test_module_alias_shadowing.py` (10), `test_cli_failures.py` (20), `test_zig_backend_runtime.py` + `test_codegen_zig.py` (151). Plus `check_no_secrets.py` (ok), `check_docs_style.py` (ok), `verify_release_version.py` (pass/fail modes), `a7 doctor`, and the wheel→sdist→clean-venv→native verification end to end. Full `run_all_tests.sh`/`run_release_checks.sh` not run, per instruction.

**Verified sound:**
- **Iterative module loading** (`a7/module_resolver.py:113-168`): enter/exit event stack preserves DFS source order (reversed-import push), cycle detection checks the active set before the cache so cycles can't masquerade as completed imports, import-origin error wrapping matches prior behavior, `BaseException` cleanup evicts only in-progress modules while completed dependencies keep identity (tested), `finally` resets the stack. Virtual modules register into `loaded_modules` (line 330) so the final return can't KeyError. 1100-module chain compiles at Python recursion limit 100. Removing `module_resolver` from `test_no_recursion.py`'s allowlist is justified — no recursion remains in the file.
- **Array RHS snapshot** (`a7/backends/zig.py:1455-1461`): labeled-block materialization defeats Zig result-location forwarding; nested `rows[0] = [rows[0][1], rows[0][0]]` verified natively; the block form is legal Zig in all three emission contexts (I probe-verified the while-continue position directly). Slice targets are unreachable — the semantic layer rejects array→slice assignment first (reproduced).
- **Char escaping** (`zig.py:1649-1650`): control chars <0x20 and 0x7f now `\xNN`; verified natively through the full CLI.
- **CLI** (`a7/cli.py`): additive (legacy path intact, 20 failure tests pass); exit codes consistent with the `ExitCode` IntEnum; signal deaths map to 128+SIGNUM (`128 - negative_rc`); atomic same-filesystem `os.replace` after building in a temp dir under the destination's parent; output protection covers entry, imports, symlinks, hardlinks, directories with byte-immutability assertions; `--` forwarding, cwd, and exit code verified through a fake-zig process boundary. `find_zig` uses an absolute path, exact version pin, timeout, clear diagnostics.
- **Release gate**: `run_release_checks.sh` is a strict superset of the old inline release.yml steps; tag/package/changelog agreement runs *before* any build and engages via `GITHUB_REF` on `v*` tag pushes (`workflow_dispatch` stays untagged qualification — correct). Wheel/sdist verifier checks venv isolation via `a7.__file__`, runs a multi-file program natively in both profiles with exact stdout/stderr/exit assertions, verifies invalid-source rejection (exit 6, no artifact), uses `tarfile filter="data"`, and enforces exactly-one-artifact invariants. CI's condensation to `bun run check` loses nothing (`check` = lint+typecheck+coverage+test+build+exports+links, site/package.json:10).
- **Docs truth**: P-TYP packet claims reproduce exactly (forward string prints `{ 104, 101, ... }`; forward float assignment accepted, prints `2`); type_checker.py is untouched by this delta (its tree diffs are baseline); README's "not implemented yet" is truthful; memory.md correctly demoted to historical vs L37-L42; ledger L37 accurately characterizes L15; CHANGELOG entries match shipped behavior; README clone URL matches the actual remote.

## Findings

### Current defects (fix before accepting the batch)

**D1 — Medium — non-void for-update still fails Zig build** — `a7/backends/zig.py:2559-2560` (`_emit_statement_as_expr`, EXPRESSION_STMT branch returns the raw expression). Repro (compiles `status ok`, then Zig fails):
```
step :: fn() i32 { ret 1 }
main :: fn() {
    i: i32 = 0
    for i = 0; i < 3; step() { io.println("{}", i); i = i + 1 }
}
```
Emits `while ((i < 3)) : (step())` → `error: value of type 'i32' ignored`. No A7-level workaround exists (no discard syntax). The batch fixed this exact defect class in `_visit_defer` (1425) and `_emit_statement_inline` (2568-2574) but missed this third site. I probe-verified `_ = step()` is legal in continue position. Fix: mirror the void-guarded discard here. Not a regression (pre-existing), but it's the same mechanism as the batch's "deferred nonvoid discard" scope item.

**D2 — Low — unused-const discard misses cross-scope name collisions** — `a7/backends/zig.py:708` uses the flat per-function `_used_identifiers` set. An unused const whose name is *used in a sibling scope* gets no discard → Zig `unused local constant`. Repro: `y :: 2` in one `if` block, `y :: 3` used in another — accepted by A7, fails Zig. Const shadowing also fails Zig (`local constant shadows`), pre-existing. Note: this mirrors the established `_visit_var`/preprocessor `is_used` mechanism (`ast_preprocessor.py:381-391` has the identical flat-set limitation), so it's a codebase-wide known limitation rather than a new design error — but the batch's "unused const emission" item is incomplete until usage is scope-aware (or consts get `_declare_var_in_scope`-style renaming like vars).

**D3 — Low — docs drift on the pre-tag command** — `site/public/docs/project.md:71` (and `site/public/llms-full.txt:1988`) still instruct "before tagging, run `./run_all_tests.sh`", while this batch moved pre-tag verification to `./run_release_checks.sh` (docs/RELEASE.md, AGENTS.md). AGENTS.md treats cross-doc drift as a bug. Fix the wording and regenerate exports (`bun run sync:exports`).

### Advisory (not blocking)

- **A1**: `candidate-1.patch`'s cli.py hunk is stale vs the tree (patch re-parses modules with a fresh resolver; the tree uses `result.input_paths` — the tree's approach is better: one source of truth, no search-path divergence). This review's verdict applies to the tree.
- **A2**: P-TYP packet cites `/tmp/...` evidence paths and mandates archiving them before temp cleanup; no in-repo archive exists yet. Do it before the packet approval decision.
- **A3**: `docs/STATUS.md` cites "L36-L44"; the ledger now runs to L46.
- **A4**: Tiny TOCTOU window between the conflict check and `os.replace` in `cli.py:103-122` — acceptable. Char literals ≥0x80 pass through raw (pre-existing; fine if A7 chars are Unicode code points — worth one sentence in SPEC).
- **Deferred, correctly handled**: forward-globals packet is properly pending approval with reproducible claims; new memory runtime and safety fallback are documented as unimplemented, not claimed.

### Review limits

Did not run the full native gate or release script (per instruction), the site/bun build, or real GitHub Actions. The sdist→wheel build used a warm uv cache (build-backend fetch not tested offline). Baseline (non-delta) tree changes were not re-reviewed. ~330 focused tests executed; no provider/capability failures.

## Recommendation

CHANGES REQUIRED for this batch: land the one-line discard fix at `zig.py:2559-2560` (with a regression case like `for_call.a7` added to `test_v1_backend_regressions.py`), address or explicitly defer D2 with a recorded scope decision, and sync `project.md`/llms exports (D3). With those three items resolved, this batch passes on its own merits.
