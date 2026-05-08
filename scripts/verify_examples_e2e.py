#!/usr/bin/env python3
"""Compile, build, run, and verify outputs for all A7 examples."""

from __future__ import annotations

import sys

from verify_examples_common import BackendConfig, MAIN_PY, main_for_backend


ZIG_BACKEND = BackendConfig(
    name="zig",
    generated_suffix=".zig",
    temp_prefix="a7-e2e-",
    validation_field="ast_ok",
    validation_error_label="zig ast-check",
    summary_label="Examples verified",
    compile_args=lambda example, generated: [
        sys.executable,
        str(MAIN_PY),
        str(example),
        "-o",
        str(generated),
    ],
    validation_args=lambda generated, _intermediate, _binary: ["zig", "ast-check", str(generated)],
    build_args=lambda generated, _intermediate, binary: [
        "zig",
        "build-exe",
        str(generated),
        f"-femit-bin={binary}",
    ],
)


if __name__ == "__main__":
    raise SystemExit(main_for_backend(ZIG_BACKEND))
