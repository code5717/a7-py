#!/usr/bin/env python3
"""Compile, build, run, and verify outputs for all A7 examples using C backend."""

from __future__ import annotations

import sys

from verify_examples_common import BackendConfig, MAIN_PY, main_for_backend


C_BACKEND = BackendConfig(
    name="zig cc",
    generated_suffix=".c",
    temp_prefix="a7-e2e-c-",
    validation_field="syntax_ok",
    validation_error_label="zig cc syntax check",
    summary_label="Examples verified (C backend)",
    compile_args=lambda example, generated: [
        sys.executable,
        str(MAIN_PY),
        "--backend",
        "c",
        str(example),
        "-o",
        str(generated),
    ],
    validation_args=lambda generated, intermediate, _binary: [
        "zig",
        "cc",
        "-std=c11",
        "-c",
        str(generated),
        "-o",
        str(intermediate),
    ],
    build_args=lambda generated, _intermediate, binary: [
        "zig",
        "cc",
        "-std=c11",
        str(generated),
        "-lm",
        "-o",
        str(binary),
    ],
)


if __name__ == "__main__":
    raise SystemExit(main_for_backend(C_BACKEND))
