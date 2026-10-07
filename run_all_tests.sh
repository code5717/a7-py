#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

TOTAL_CHECKS=0
FAILED_CHECKS=0
SKIPPED_CHECKS=0

# Kill switch: per-check timeout plus check selection.
# A7_CHECK_TIMEOUT (seconds, default 3600, 0 disables) bounds each check so a
# hung suite fails fast instead of hanging the gate. --timeout SECS overrides
# it. --only SUB (repeatable) runs only matching checks. --skip SUB
# (repeatable) skips matching checks. Match is a case-insensitive substring
# of the check title.
CHECK_TIMEOUT="${A7_CHECK_TIMEOUT:-3600}"
PYTEST_WORKERS="${A7_PYTEST_WORKERS-8}"
ONLY_FILTERS=()
SKIP_FILTERS=()

usage() {
    echo "Usage: $0 [--timeout SECS] [--only SUB]... [--skip SUB]..."
    echo "  A7_CHECK_TIMEOUT env sets the default per-check timeout (0 disables)."
    echo "  A7_PYTEST_WORKERS env sets pytest workers (1..8, default 8)."
}

# Every flag that takes a value fails loudly without one, and an unknown
# argument is an error: a typo must not turn into a green run.
need_value() {
    if (( $# < 2 )); then
        echo "error: $1 needs a value" >&2
        usage >&2
        exit 2
    fi
}

while (( $# > 0 )); do
    case "$1" in
        --timeout=*) CHECK_TIMEOUT="${1#--timeout=}"; shift ;;
        --timeout)   need_value "$@"; CHECK_TIMEOUT="$2"; shift 2 ;;
        --only=*)    ONLY_FILTERS+=("${1#--only=}"); shift ;;
        --only)      need_value "$@"; ONLY_FILTERS+=("$2"); shift 2 ;;
        --skip=*)    SKIP_FILTERS+=("${1#--skip=}"); shift ;;
        --skip)      need_value "$@"; SKIP_FILTERS+=("$2"); shift 2 ;;
        --help|-h)   usage; exit 0 ;;
        *)
            echo "error: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if ! [[ "$CHECK_TIMEOUT" =~ ^[0-9]+$ ]]; then
    echo "error: timeout must be a whole number of seconds, got '$CHECK_TIMEOUT'" >&2
    exit 2
fi

if ! [[ "$PYTEST_WORKERS" =~ ^[1-8]$ ]]; then
    echo "error: A7_PYTEST_WORKERS must be an integer from 1 to 8, got '$PYTEST_WORKERS'" >&2
    exit 2
fi

should_run() {
    local title="$1"
    local lower
    lower="$(printf '%s' "$title" | tr '[:upper:]' '[:lower:]')"
    local f
    if (( ${#ONLY_FILTERS[@]} > 0 )); then
        local hit=0
        for f in "${ONLY_FILTERS[@]}"; do
            case "$lower" in
                *"$(printf '%s' "$f" | tr '[:upper:]' '[:lower:]')"*) hit=1; break ;;
            esac
        done
        (( hit == 0 )) && return 1
    fi
    for f in "${SKIP_FILTERS[@]}"; do
        case "$lower" in
            *"$(printf '%s' "$f" | tr '[:upper:]' '[:lower:]')"*) return 1 ;;
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
    if (( CHECK_TIMEOUT > 0 )) && command -v timeout >/dev/null 2>&1; then
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
    uv run pytest --tb=short -q -n "$PYTEST_WORKERS"

run_check "Examples E2E Verification (compile/build/run/output):" \
    uv run python scripts/verify_examples_e2e.py

run_check "Debug Artifact Build Verification (Zig):" \
    uv run python scripts/build_examples.py --profile debug --backend zig --clean

run_check "Release Artifact Build Verification (Zig):" \
    uv run python scripts/build_examples.py --profile release --backend zig --clean

run_check "Fast Artifact Build Verification (Zig):" \
    uv run python scripts/build_examples.py --profile fast --backend zig --clean

run_check "Bench Perf (timing ratios report-only):" \
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

if (( TOTAL_CHECKS == 0 )); then
    echo "error: no check ran; --only/--skip matched nothing to run" >&2
    exit 2
fi

if (( FAILED_CHECKS > 0 )); then
    exit 1
fi
