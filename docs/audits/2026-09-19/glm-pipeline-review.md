# Review report: source preservation and artifact provenance fix

## Verdict

No blocking findings. The fix is correct for the stated failure modes, fails closed, and is verified by meaningful tests plus my independent probes. One followup item (the `/tmp/` gitignore entry) is implemented but **not actually committed yet**, and two realistic limitations remain (TOCTOU window; deliberate write-through of symlinks that do not alias an input).

## Fix correctness (a7/compile.py)

- Destination validation runs before codegen and any write (a7/compile.py:395-406), against `input_files` = main file plus every loaded module file (a7/compile.py:258-261). Transitive coverage is real: `ModuleResolver.load_module` recurses into module imports (a7/module_resolver.py:191-202) and stores resolved absolute file paths (a7/module_resolver.py:109); virtual stdlib paths (`<stdlib:...>`) are correctly excluded.
- `_artifact_path_conflict` (a7/compile.py:529-541) uses two independent checks: `resolve()` equality (catches identical paths, `..`/relative-vs-absolute aliasing, symlink chains, dangling symlinks, parent-dir symlinks) and `samefile()` (catches hardlinks and existing symlinks by inode). Each accepted destination is appended to `protected`, so output-vs-output collisions (`--output X --doc-out X`) are rejected too. Validation errors (`OSError`, `RuntimeError`) convert to an IO failure — fail closed (a7/compile.py:398-406).
- Provenance: `result.output_path` is assigned only after a successful write (a7/compile.py:467), `doc_path` likewise (a7/compile.py:496), and `_to_json_payload` requires both a set path and existence on disk (a7/compile.py:949-952). The old bug — `output_path` set before compilation, then advertised because an old file happened to exist — is gone. A directory destination fails at `open()` with IO exit and no artifact advertised; directory contents are not damaged.

## Test evidence

`uv run pytest test/test_pipeline_artifacts.py` + the two secrets tests: **12 passed**. The artifact tests are real-subprocess, real-filesystem, no mocks, and each asserts an observable requirement: source bytes unchanged, exit codes, artifact absence, sentinel preservation. The alias test (test_pipeline_artifacts.py:85-107) covers symlink, hardlink, imported module, and transitive module; the destinations-must-differ test also proves validation precedes the first write (`not output.exists()`, test_pipeline_artifacts.py:117).

My independent probes (all with the project venv, disposable dirs under /tmp/opencode): 2-deep symlink chain → exit 3, source intact; relative alias `--output ./main.a7` → exit 3, intact; path-through-file `main.a7/x.zig` → exit 3 (ENOTDIR), intact; absolute parent-dir symlink onto input → exit 3, intact; `--doc-out helper.a7` (imported module) → exit 3, both sources intact.

## Secrets-checker followups

1. `/tmp/` in `.gitignore` (line 25): present and effective (`git check-ignore` resolves `tmp/probe.a7` to it). **Not committed**: `git show HEAD:.gitignore` has no `tmp/` entry and `git diff --cached` is empty; the change is an unstaged working-tree modification. Claim was "committed" — that is currently false; it must ride the next commit.
2. Git enumeration failures expose stderr: implemented at scripts/check_no_secrets.py:127-130. Manually verified in a non-repo: exit 2, stderr contains git's own `fatal: not a git repository...` text.
3. Exit-2-without-repository test exists and passes (test_release_tooling.py:518-522). Minor gap: it asserts only the `cannot enumerate repository files` prefix, not that git's stderr text propagates — that propagation is currently verified only by manual probe, not by a committed test.

## Limitations (realistic, non-blocking)

- **TOCTOU window.** Validation precedes codegen; writes happen later (a7/compile.py:465, 494). A concurrent local process can swap the destination for a symlink/hardlink to a source file between check and `open(..., "w")`. Mitigation if ever needed: `os.open` with `O_NOFOLLOW`/`O_EXCL` plus `fstat` st_dev/st_ino comparison against the opened inputs. Exposure is low (hostile concurrent actor on the same filesystem during compilation), acceptable for a local compiler tool.
- **Hardlink detection requires both paths to exist at check time** (`destination.exists() and other.exists()`); hardlinks created after validation fall into the same TOCTOU class. Pre-existing hardlinks are caught (test + probe).
- **Symlinks to non-input files are deliberately followed and truncated** (probe: `--output out.zig` with `out.zig -> target.zig` succeeded and rewrote `target.zig`). This preserves normal Unix semantics and does not over-block, but means the fix confines itself to input/other-output preservation, not general output confinement (e.g., a symlink chain to `~/.bashrc` would be truncated). Consistent with the stated scope.
- Cosmetic: a destination containing an embedded NUL raises `ValueError`, which escapes the `(OSError, RuntimeError)` net and lands in the generic INTERNAL handler (a7/compile.py:514) — exit 8 instead of IO, still no write. Fails closed.
- Doc-write failure after a successful compile write leaves the compile artifact on disk and advertised in the error payload's `artifacts`; the file was genuinely produced by this invocation, so the provenance claim stays truthful.
- `_artifact_path_conflict` is iterative; no new recursion introduced (no-recursion rule respected).

Scope note: unrelated working-tree changes (module alias annotation, parser, backends, docs) were not audited, per instructions. No files were edited.


## Controller disposition

All edits remain uncommitted, including the tracked `.gitignore` file. The review
prompt's word "committed" meant repository-managed rather than local-only, but
was inaccurate. No commit was created. The fixed checks do not claim protection
against a hostile concurrent process replacing output paths during compilation.
