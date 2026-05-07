#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

TOTAL_CHECKS=0
FAILED_CHECKS=0

run_check() {
    local title="$1"
    shift

    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo "$title"

    local output
    output="$("$@" 2>&1)"
    local status=$?

    local summary
    summary="$(printf '%s\n' "$output" | tail -n 1)"
    if [[ -z "$summary" ]]; then
        summary="(no output)"
    fi

    if (( status == 0 )); then
        printf 'PASS: %s\n\n' "$summary"
        return 0
    fi

    printf 'FAIL: %s\n' "$summary"
    echo "---- recent output ----"
    printf '%s\n' "$output" | tail -n 20
    echo "-----------------------"
    echo ""
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    return 0
}

echo "============================================================"
echo "A7 COMPILER - COMPLETE TEST RESULTS"
echo "============================================================"
echo ""

run_check "Parser & Tokenizer Tests:" \
    uv run pytest test/test_parser*.py test/test_tokenizer*.py --tb=no -q

run_check "Semantic Analysis Tests (All):" \
    uv run pytest test/test_semantic*.py --tb=no -q

run_check "Compiler/CLI/Backend Tests:" \
    uv run pytest \
    test/test_ast_preprocessor.py \
    test/test_cli_failures.py \
    test/test_iterative_traversal.py \
    test/test_stdlib_registry.py \
    test/test_codegen_zig.py \
    test/test_codegen_c.py \
    --tb=no -q

run_check "Examples E2E Verification (compile/build/run/output):" \
    uv run python scripts/verify_examples_e2e.py

run_check "Examples E2E Verification (C backend compile/build/run/output):" \
    uv run python scripts/verify_examples_e2e_c.py

run_check "Backend Parity Verification (Zig vs C runtime output):" \
    uv run python scripts/verify_backend_parity.py

run_check "Debug Artifact Build Verification (Zig and C):" \
    uv run python scripts/build_examples.py --profile debug --backend both --clean

run_check "Release Artifact Build Verification (Zig and C):" \
    uv run python scripts/build_examples.py --profile release --backend both --clean

run_check "Error Stage Verification (mode/format matrix):" \
    uv run python scripts/verify_error_stages.py --mode-set all --format both

run_check "Docs Style Check:" \
    uv run python scripts/check_docs_style.py

run_check "Secrets Check:" \
    uv run python scripts/check_no_secrets.py

run_check "TOTAL (All Pytest Tests):" \
    uv run pytest --tb=no -q

PASSED_CHECKS=$((TOTAL_CHECKS - FAILED_CHECKS))
echo "============================================================"
echo "Summary: ${PASSED_CHECKS}/${TOTAL_CHECKS} checks passed"

if (( FAILED_CHECKS > 0 )); then
    exit 1
fi
