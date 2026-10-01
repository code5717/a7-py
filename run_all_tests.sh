#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

TOTAL_CHECKS=0
FAILED_CHECKS=0
SKIPPED_CHECKS=0

# Kill switch: per-check timeout plus check selection.
# A7_CHECK_TIMEOUT (seconds, default 1200, 0 disables) bounds each check so a
# hung suite fails fast instead of hanging the gate. --timeout SECS overrides
# it. --only SUB (repeatable) runs only matching checks. --skip SUB
# (repeatable) skips matching checks. Match is a case-insensitive substring
# of the check title.
CHECK_TIMEOUT="${A7_CHECK_TIMEOUT:-1200}"
ONLY_FILTERS=()
SKIP_FILTERS=()

for arg in "$@"; do
    case "$arg" in
        --timeout=*)
            CHECK_TIMEOUT="${arg#--timeout=}"
            shift
            ;;
        --timeout)
            CHECK_TIMEOUT="$2"
            shift 2
            ;;
        --only=*)
            ONLY_FILTERS+=("${arg#--only=}")
            shift
            ;;
        --only)
            ONLY_FILTERS+=("$2")
            shift 2
            ;;
        --skip=*)
            SKIP_FILTERS+=("${arg#--skip=}")
            shift
            ;;
        --skip)
            SKIP_FILTERS+=("$2")
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--timeout SECS] [--only SUB]... [--skip SUB]..."
            echo "  A7_CHECK_TIMEOUT env sets the default per-check timeout."
            exit 0
            ;;
    esac
done

should_run() {
    local title="$1"
    local lower
    lower="$(printf '%s' "$title" | tr '[:upper:]' '[:lower:]')"
    local f
    if (( ${#ONLY_FILTERS[@]} > 0 )); then
        local hit=0
        for f in "${ONLY_FILTERS[@]}"; do
            case "$lower" in
                *$(printf '%s' "$f" | tr '[:upper:]' '[:lower:]')*) hit=1; break ;;
            esac
        done
        (( hit == 0 )) && return 1
    fi
    for f in "${SKIP_FILTERS[@]}"; do
        case "$lower" in
            *$(printf '%s' "$f" | tr '[:upper:]' '[:lower:]')*) return 1 ;;
        esac
    done
    return 0
}

run_check() {
    local title="$1"
    shift

    if ! should_run "$title"; then
        SKIPPED_CHECKS=$((SKIPPED_CHECKS + 1))
        echo "$title"
        printf 'SKIP: filter\n\n'
        return 0
    fi

    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo "$title"

    local output
    local status
    if [[ "$CHECK_TIMEOUT" =~ ^[0-9]+$ ]] && (( CHECK_TIMEOUT > 0 )) && command -v timeout >/dev/null 2>&1; then
        output="$(timeout --signal=TERM --kill-after=60 "$CHECK_TIMEOUT" "$@" 2>&1)"
        status=$?
        if (( status == 124 )); then
            printf 'FAIL: TIMEOUT after %ss (A7_CHECK_TIMEOUT/--timeout kill switch)\n\n' "$CHECK_TIMEOUT"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
            return 0
        fi
    else
        output="$("$@" 2>&1)"
        status=$?
    fi

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

run_check "All Pytest Tests:" \
    uv run pytest --tb=short -q

run_check "Examples E2E Verification (compile/build/run/output):" \
    uv run python scripts/verify_examples_e2e.py

run_check "Debug Artifact Build Verification (Zig):" \
    uv run python scripts/build_examples.py --profile debug --backend zig --clean

run_check "Release Artifact Build Verification (Zig):" \
    uv run python scripts/build_examples.py --profile release --backend zig --clean

run_check "Bench Perf (report-only, no gate):" \
    uv run python scripts/bench_perf.py

run_check "Error Stage Verification (mode/format matrix):" \
    uv run python scripts/verify_error_stages.py --mode-set all --format both

run_check "Docs Style Check:" \
    uv run python scripts/check_docs_style.py

run_check "Secrets Check:" \
    uv run python scripts/check_no_secrets.py

run_check "Package Build:" \
    bash -lc 'rm -rf dist && uv build'

run_check "Wheel and Source Distribution Native Verification:" \
    uv run python scripts/verify_wheel_install.py --skip-build --verify-sdist

PASSED_CHECKS=$((TOTAL_CHECKS - FAILED_CHECKS))
echo "============================================================"
echo "Summary: ${PASSED_CHECKS}/${TOTAL_CHECKS} checks passed (${SKIPPED_CHECKS} skipped, timeout ${CHECK_TIMEOUT}s, 124 means kill switch fired)"

if (( FAILED_CHECKS > 0 )); then
    exit 1
fi
