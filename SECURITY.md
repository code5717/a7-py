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
uvx pip-audit --strict
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
- `fall` is rejected until fallthrough semantics and backend lowering are
  designed.
- Built-in stdlib imports are virtual and not yet unified with file-based module semantics.
- C and Zig backend parity checks exist for examples but are not a proof for all
  possible programs.
- The current release workflow builds package distributions and attaches them
  to draft GitHub releases; it does not publish to a package registry.
- Non-`actions/*` release and Claude workflow actions are pinned to immutable
  commits. Most first-party GitHub Actions remain pinned by major version tag.
- Dependency audits check known advisories, not unknown vulnerabilities.
- The committed-secrets check is pattern-based and should be treated as a guard,
  not a complete data-loss prevention system.

These limitations are tracked in `MISSING_FEATURES.md`, `TODO.md`, and
`RELEASE.md`.

## Reporting

Open a private security advisory or contact the repository owner before opening
public issues for exploitable crashes, unsafe generated code, or release
pipeline compromise.
