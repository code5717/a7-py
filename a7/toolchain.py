"""Native build commands for the supported Zig toolchain."""

from __future__ import annotations

import shutil
import subprocess

ZIG_VERSION = "0.16.0"


def find_zig() -> tuple[str | None, str]:
    executable = shutil.which("zig")
    if executable is None:
        return None, f"Zig {ZIG_VERSION} required: zig was not found on PATH"
    try:
        result = subprocess.run([executable, "version"], text=True, capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"Cannot run Zig: {exc}"
    version = result.stdout.strip()
    if result.returncode != 0 or version != ZIG_VERSION:
        return None, f"Zig {ZIG_VERSION} required; found {version or result.stderr.strip() or 'unknown version'}"
    return executable, f"Zig {version}: {executable}"
