# Advisory review: secrets-scan git enumeration change

**Verdict.** The change is correct for all three required behaviors, fails closed on git errors, and introduces no regression for any current caller. Three residual gaps are worth recording (F1–F3); none is worse than the old rglob walk. No files were edited; experiments ran in `/tmp/opencode`.

## Verified behaviors

1. **Tracked ignored files remain checked.** `--cached` lists tracked files regardless of ignore rules (ignore applies only to untracked files). Verified empirically: a force-added `*.log` file matching `.gitignore` is listed. The test exercises this via `git add -f .env.local` and asserts membership (test/test_release_tooling.py:508,512).
2. **Nonignored new source remains checked.** Untracked `new.py` listed in probe; asserted at test/test_release_tooling.py:511.
3. **Ignored downloads stay outside the scan.** `downloads/page.html` excluded in probe; asserted at test/test_release_tooling.py:510. On this machine `.git/info/exclude` contains `tmp/` (1.6G of downloads), and a live run prints `secrets-check: ok`, exit 0 — the previously flagged `tmp/toolchain/.../scrypt.zig` class (docs/audits/2026-09-18/examples-tests.md:655) is gone.
4. **Suffix/dir exclusions retained** — `should_skip` still applied in `iter_files` (scripts/check_no_secrets.py:88).
5. **Git errors fail closed.** Copied the script to a non-repo dir: git exits 128, script prints `cannot enumerate repository files`, exits **2** — distinct from exit 1 (findings). Missing git binary → `FileNotFoundError` ⊂ `OSError`, caught at :127. Both callers fail on any nonzero: `run_all_tests.sh:68` (`run_check` counts nonzero as failed) and `.github/workflows/ci.yml:97` (runs inside a checkout, before any toolchain steps, so `tmp/` cannot exist there).

All 3 secret-scan tests pass locally (`3 passed, 14 deselected`).

## Findings

- **F1 (P2, environment-dependent residual false positives; pre-existing, not introduced).** Committed `.gitignore` has no `tmp/` entry; exclusion rests on the *local* `.git/info/exclude` (recorded in docs/plan/execution.md:293, with a `.gitignore` entry proposed in docs/plan/packets/P0-plan-confirmations.md:206 but not landed). On a fresh clone that lacks the local entry, untracked `tmp/` downloads are listed again by `--others --exclude-standard` and the old false positives recur. Advisory: land the P0 `.gitignore` entry.
- **F2 (P3, intended scope narrowing — record as accepted risk).** Untracked-but-ignored files, including genuinely sensitive ones (`.env`, `id_rsa` dropped in an ignored dir), are no longer reported. Old rglob flagged them incidentally. Correct for a commit gate (ignored files can't be committed without `-f`), but local working-tree defense-in-depth is gone. `--exclude-standard` also honors per-user `core.excludesFile`, which can silently narrow coverage (no global ignore file exists on this machine — verified).
- **F3 (P3, enumeration blind spots).** Nested/embedded git repos and submodules are not descended into (`--others` emits the directory as one entry; `is_file()` drops it — verified with a nested repo probe). Old rglob walked them. None exist in this working tree today (verified by search); relevant only if agent worktrees are checked out inside the repo.
- **F4 (P4, observability).** On enumeration failure git's stderr (`fatal: not a git repository`) is captured and discarded; the operator sees only the exit status. Also `.github/workflows/ci.yml:96` step name still says "committed secrets" though scope now includes non-ignored working files.
- **F5 (P3, test gaps).** The new test does not cover the exit-2 branch, so the "fails on git errors" requirement is unverified by tests (easy fix: point a copied module at a non-repo tmp dir). Suffix exclusion through `iter_files` is untested. It shells out to real `git`, so git-less hosts error rather than skip (acceptable; note it). Hermeticity nit: assertions depend on the machine's global excludes not ignoring `new.py`; `-c core.excludesFile=/dev/null` (or `GIT_CONFIG_GLOBAL=/dev/null`) on the test's git calls would isolate it while keeping `.gitignore` semantics under test.
- **F6 (P4, portability change).** Outside a git repo the script now exits 2 instead of scanning (e.g. source exports without `.git`). All current callers run in-repo; the wheel does not ship `scripts/` (pyproject defines entry points only — inference from absence of a scripts inclusion).

## Limits

 Reviewed only the diff to `iter_files`/`main`, the new test, and callers; pattern quality (regexes, dedup logic) was covered by the prior tooling review and was not re-audited beyond confirming behavior is unchanged. Git behaviors were probed on git as installed here; CI runners' git versions are assumed equivalent (unverified).


## Controller disposition

Added `/tmp/` to the tracked ignore file in the working tree; it is not committed. Git enumeration errors now include
stderr, and a real non-repository test checks exit 2. The scanner is a repository
file check, not a whole-machine or ignored-file secret inventory. Tracked ignored
files remain covered. Nested repositories require their own scan.
