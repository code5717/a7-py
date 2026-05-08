# Security Policy

## Supported Versions

`a7-py` is pre-1.0. Security fixes are made on `master` unless a release branch
is created later.

## Trust Boundary

`a7-py` is not a sandbox.

The compiler reads A7 source, emits Zig or C, and the verification scripts build
and execute native binaries. Compiled A7 programs can do anything the generated
program and host runtime allow. Only compile and run A7 source you trust.

## Local Verification

Before release or broad testing, run:

```bash
./run_all_tests.sh
uv build
uvx --from pip-audit==2.10.0 pip-audit --strict
uvx --from bandit==1.9.4 bandit -r a7 scripts main.py -q --skip B404,B603
uv run python scripts/check_no_secrets.py
(cd site && npm run build)
(cd site && npm audit --omit=dev --audit-level=moderate)
```

The full gate includes parser/tokenizer tests, semantic tests, Zig and C backend
tests, example runtime verification, selected Zig/C backend parity checks,
debug/release artifact builds, error-stage checks, docs style checks, and full
pytest.

## Known Security-Relevant Limitations

- No sandboxing for compiled programs.
- No ownership or borrow-style lifetime model yet.
- `fall` is supported only as the final direct statement of a non-final match
  case; other placements are rejected during semantic validation.
- Built-in stdlib imports are virtual and not yet unified with file-based module semantics.
- File-backed imports are restricted to configured module search paths; absolute
  paths and parent-directory traversal are rejected.
- C and Zig backend parity checks exist for examples but are not a proof for all
  possible programs.
- The current release workflow builds package distributions and attaches them
  to draft GitHub releases; it does not publish to a package registry.
- Tag-created release artifacts receive GitHub artifact attestations; verify
  them with `gh attestation verify <file> --repo code5717/a7-py` before
  publishing or consuming a release.
- Workflow actions are pinned to immutable commits resolved from current
  upstream release tags on 2026-05-08.
- Dependency audits check known advisories, not unknown vulnerabilities.
- The committed-secrets check is pattern- and filename-based and should be
  treated as a guard, not a complete data-loss prevention system.

These limitations are tracked in `MISSING_FEATURES.md`, `TODO.md`, and
`RELEASE.md`.

## Reporting

Open a private security advisory or contact the repository owner before opening
public issues for exploitable crashes, unsafe generated code, or release
pipeline compromise.
