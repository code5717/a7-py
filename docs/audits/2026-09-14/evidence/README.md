# Verification evidence

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../../plan/decisions.md) supersede parts of the audit; these records are unchanged evidence.

These records belong to the 2026-09-14 audit of baseline revision
`701c67936c70ad2b0608326e23e56cc5d38c9fdb` and its uncommitted documentation and
regression-test additions. They do not certify a tagged release.

## Gate environment

The configured runs used Python 3.13.15, uv 0.12.6 and Zig 0.16.0. The local
Mise shim initially had no selected uv version. Selecting the existing uv binary
for the process resolved that setup failure without changing global configuration.

The Zig archive came from the URL pinned by repository CI:

```text
https://ziglang.org/download/0.16.0/zig-x86_64-linux-0.16.0.tar.xz
SHA256 70e49664a74374b48b51e6f3fdfbf437f6395d42509050588bd49abe52ba3d00
```

The coordinator verified that hash. The extracted toolchain lived in a temporary
directory and must not be assumed to survive a future session. The audit command
was:

```sh
MISE_UV_VERSION=0.12.6 \
A7_TEST_ZIG=/tmp/a7-audit-20260914/zig/zig \
PATH="/tmp/a7-audit-20260914/zig:/home/cx89/.local/share/mise/installs/uv/0.12.6/uv-x86_64-unknown-linux-musl:$PATH" \
./run_all_tests.sh
```

Use the documented gate with an equivalently qualified toolchain for subsequent
work. The temporary path is a run record, not a new installation requirement.

## Records

| Record | What it establishes |
| --- | --- |
| `baseline-release-gate.log` | Original gate passed 12/12 before new regressions |
| `current-release-gate.log` | Changed test suite yields 11/12, with 12 failures and 2,515 passes |
| `new-regressions.log` | Focused new-test results, including genuine known failures |
| `root-pipeline-probes.json` | Main/imported diagnostics and exact-integer probe evidence |
| `root-stage-validation.json` | Additional public-pipeline validation and native compile observations |
| `parser-recovery-coordinator.json` | Successful CLI exit despite dropping main after a source error |
| `docs-preservation-coordinator.json` | Existing document preservation and exact changed-line inventory |
| `site-check-after-cleanup.log` | Successful local site build and lint after documentation cleanup |
| `site-links-after-cleanup.json` | 259 generated internal links across 10 HTML files checked |
| `audit-navigation-check.json` | Local targets in the new report/index navigation exist |
| `pdf-inventory.json`, `pdf-text/` | Seven original PDFs, hashes, structural checks and text extractions |
| `pip-audit-target-inventory.json` | The passing audit targeted the isolated tool environment |
| `pip-audit.log`, `bandit.log`, `bun-audit.log` | Command outputs with scope limits described in the coordinator report |
| `provider-limitations.json` | Recorded provider rate limits, safety filter and tool-access failures |
| `review-ledger.json` | Saved report identities and the incomplete Codex memory-review run |

The new tests use no mocks. Their compile-only cases do not establish native
runtime behavior. Native arithmetic cases cover their stated defined values in
two profiles; they do not prove all arithmetic or memory safety.

The original security command's exit zero does not qualify project dependencies.
The corrected target inventory and cybersecurity disposition must be supplied by
the GLM workstream before release acceptance. Likewise, local site build and link
checks do not establish browser accessibility or production deployment status.
