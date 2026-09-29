#!/usr/bin/env bash
# Run from any directory. Fail before packaging if a tag identifies another version.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

uv run --locked python scripts/verify_release_version.py "$@"
uv sync --locked --all-groups
./run_all_tests.sh

(
    cd site
    bun install --frozen-lockfile
    bun run check
    bun audit --audit-level=moderate
)

audit_dir="$(mktemp -d)"
trap 'rm -rf "$audit_dir"' EXIT
uv export --locked --all-groups --no-emit-project --format requirements-txt \
    --output-file "$audit_dir/requirements.txt"
uvx --from pip-audit==2.10.0 pip-audit --strict -r "$audit_dir/requirements.txt"
# Trusted verifier scripts execute generated programs; keep all other checks enabled.
uvx --from bandit==1.9.4 bandit -r a7 scripts main.py -q --skip B404,B603

echo "Release checks passed. Native language and performance qualification remain separate."
