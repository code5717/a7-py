#!/usr/bin/env python3
"""Pin-based performance gate for the A7 bench suite.

Emits Zig per bench via main.py with `--build-profile fast` into build/bench/,
builds ReleaseFast native binaries with `zig build-exe`, times them (median of
N runs, stdout captured) and compares the medians against the per-host pin in
bench/pins/<hostname>.json. Every run's stdout sha256 must be stable across
runs and equal the pin's hash when one exists.

Modes:
  default   Compare vs pins, print deltas. Exit 0 unless a build/run fails or
            an output hash mismatches.
  --pin     Write bench/pins/<hostname>.json from this run.
  --gate    Require a complete usable host pin; exit 1 if any median > pin * 1.15.
            Cannot be combined with --pin.
  --runs N  Runs per binary (default 7; pin/gate require at least 5).
  --taskset CPU
            Pin each timed run to one CPU (e.g. 0) with taskset(1) to cut
            scheduler noise. Invalid or unavailable requested affinity fails.
            Pin/gate choose one inherited allowed CPU when omitted.

Timing uses the median for fewer than 5 runs and a trimmed median (fastest
and slowest dropped) for 5 or more. A coefficient of variation above 0.10
rejects pin/gate measurements. Report-only runs warn without qualifying timings.
"""

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = ROOT / "bench"
BUILD_DIR = ROOT / "build" / "bench"
PINS_DIR = BENCH_DIR / "pins"
BENCHES = [
    "arith_loop",
    "alloc_churn",
    "print_lines",
    "array_walk",
    "vector_ops",
    "sort_load",
    "aos_walk",
    "soa_walk",
    "stride_walk",
    "kv_append",
    "mem_shared",
    "mem_returned",
    "mem_cleanup",
    "mem_cache",
    "mem_copy",
    "mem_text",
    "mem_cyclic",
]
# Seed A oracles derived independently at the original workload counts.
MEMORY_OUTPUTS = {
    "mem_cache": b"result: 6616666665 49999999 50000001\n",
    "mem_copy": b"result: 942376503\n",
    "mem_text": b"result: 98811553\n",
    "mem_cyclic": b"result: 757942091\n",
}
GATE_RATIO = 1.15
RUN_TIMEOUT = 300.0


def run_cmd(cmd, timeout=None):
    return subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def host_name():
    name = platform.node() or "unknown"
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def pin_path():
    return PINS_DIR / f"{host_name()}.json"


def zig_version():
    result = run_cmd(["zig", "version"])
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def emit_zig(name):
    source = BENCH_DIR / f"{name}.a7"
    generated = BUILD_DIR / f"{name}.zig"
    result = run_cmd(
        [
            "uv", "run", "python", "main.py", str(source),
            "-o", str(generated), "--build-profile", "fast",
        ]
    )
    if result.returncode != 0:
        return False, f"emit failed: {(result.stderr or result.stdout).strip()}"
    if not generated.exists():
        return False, "emit produced no output file"
    return True, ""


def build_binary(name):
    generated = BUILD_DIR / f"{name}.zig"
    binary = BUILD_DIR / f"{name}_fast"
    result = run_cmd(
        [
            "zig",
            "build-exe",
            str(generated),
            "-OReleaseFast",
            f"-femit-bin={binary}",
        ]
    )
    if result.returncode != 0:
        return False, f"zig build-exe failed: {(result.stderr or result.stdout).strip()}"
    if not binary.exists():
        return False, "zig build-exe produced no binary"
    return True, ""


def robust_center(times):
    """Median for few runs; trimmed median (drop fastest and slowest) for 5+."""
    ordered = sorted(times)
    if len(ordered) >= 5:
        ordered = ordered[1:-1]
    return statistics.median(ordered)


def variation(times):
    """Coefficient of variation (stdev/mean); 0.0 for a single run."""
    if len(times) < 2:
        return 0.0
    mean = statistics.fmean(times)
    if not mean:
        return 0.0
    return statistics.pstdev(times) / mean


def time_binary(name, runs, taskset=None):
    binary = BUILD_DIR / f"{name}_fast"
    times = []
    output_hash = None
    for _ in range(runs):
        start = time.perf_counter()
        cmd = [str(binary)]
        if taskset is not None:
            cmd = ["taskset", "-c", taskset, str(binary)]
        try:
            result = subprocess.run(
                cmd,
                cwd=ROOT,
                capture_output=True,
                timeout=RUN_TIMEOUT,
                **({"input": b"A\n"} if name in MEMORY_OUTPUTS else {}),
            )
        except subprocess.TimeoutExpired:
            return None, None, f"run timed out after {RUN_TIMEOUT}s", 0.0
        elapsed = time.perf_counter() - start
        if result.returncode != 0:
            return (
                None,
                None,
                f"run exited {result.returncode}: {result.stderr.decode('utf-8', 'replace').strip()}",
                0.0,
            )
        out = result.stdout
        if name in MEMORY_OUTPUTS:
            if out != MEMORY_OUTPUTS[name] or result.stderr:
                return None, None, "memory workload output differs from the seed A oracle", 0.0
        last_line = out.rstrip(b"\n").rsplit(b"\n", 1)[-1]
        if not last_line.startswith(b"result: "):
            return None, None, f"last output line is not a result line: {last_line[:60]!r}", 0.0
        digest = hashlib.sha256(out).hexdigest()
        if output_hash is None:
            output_hash = digest
        elif digest != output_hash:
            return None, None, "output differs across runs", 0.0
        times.append(elapsed)
    return robust_center(times), output_hash, "", variation(times)


def load_pin():
    path = pin_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin", action="store_true", help="write pin file from this run")
    parser.add_argument("--gate", action="store_true", help=f"require a complete host pin; fail if a median > pin * {GATE_RATIO}")
    parser.add_argument("--runs", type=int, default=7, help="runs per binary (default 7; pin/gate minimum 5)")
    parser.add_argument("--taskset", default=None, metavar="CPU",
                        help="one inherited allowed CPU; pin/gate select one automatically")
    args = parser.parse_args()
    if args.pin and args.gate:
        parser.error("--pin and --gate cannot be combined; update with --pin, then run --gate separately")
    if args.runs < 1:
        print("perf: --runs must be >= 1", file=sys.stderr)
        return 2
    if (args.pin or args.gate) and args.runs < 5:
        print("perf: --pin and --gate require at least 5 runs", file=sys.stderr)
        return 2
    if args.taskset is not None or args.pin or args.gate:
        try:
            allowed = os.sched_getaffinity(0)
        except (AttributeError, OSError) as error:
            print(f"perf: cannot inspect inherited CPU affinity: {error}", file=sys.stderr)
            return 2
        if args.taskset is None:
            args.taskset = str(min(allowed))
        elif not args.taskset.isdecimal() or int(args.taskset) not in allowed:
            print("perf: --taskset must name one CPU in the inherited affinity mask", file=sys.stderr)
            return 2
        else:
            args.taskset = str(int(args.taskset))
        if shutil.which("taskset") is None:
            print("perf: taskset required for requested or pin/gate affinity", file=sys.stderr)
            return 2

    pin = None if args.pin else load_pin()
    if args.gate:
        unusable = []
        for name in BENCHES:
            entry = pin.get(name) if isinstance(pin, dict) else None
            if not isinstance(entry, dict):
                unusable.append(name)
                continue
            timing = entry.get("release")
            digest = entry.get("output_sha256")
            if (not isinstance(timing, (int, float)) or isinstance(timing, bool)
                    or timing <= 0 or timing > sys.float_info.max or not math.isfinite(timing)
                    or not isinstance(digest, str) or not digest):
                unusable.append(name)
        if unusable:
            print(f"perf: --gate requires a complete usable host pin at {pin_path().relative_to(ROOT)}; "
                  f"missing or invalid timing/hash baseline for: {', '.join(unusable)}", file=sys.stderr)
            return 1
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    zig = zig_version()

    print(
        f"perf: {len(BENCHES)} benches, runs={args.runs}, zig={zig}, host={host_name()}, cpu={args.taskset or 'unpinned'}"
    )
    if not args.pin and pin is None:
        print(f"perf: no usable pin at {pin_path().relative_to(ROOT)}; reporting times only")
    print("")

    results = {}
    failures = []
    for name in BENCHES:
        ok, err = emit_zig(name)
        if not ok:
            print(f"FAIL {name}: {err}")
            failures.append(name)
            continue
        ok, err = build_binary(name)
        if not ok:
            print(f"FAIL {name}: {err}")
            failures.append(name)
            continue
        median, digest, err, cv = time_binary(name, args.runs, args.taskset)
        if median is None:
            print(f"FAIL {name}: {err}")
            failures.append(name)
            continue
        if cv > 0.10:
            print(f"perf: {name}: high run variation (CV {cv:.2f}); measurement is not qualified")
            if args.pin or args.gate:
                failures.append(name)
                continue
        if pin is not None and name in pin:
            pinned = pin[name].get("output_sha256")
            if pinned is not None and pinned != digest:
                print(f"FAIL {name}: output hash differs from pin")
                failures.append(name)
                continue
        # The pin key stays "release": the pins were measured with ReleaseFast
        # under that name, and the same binaries are now the `fast` profile.
        results[name] = {"release": median, "output_sha256": digest, "cv": cv}

    if args.pin and not failures:
        PINS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {}
        for name in BENCHES:
            if name not in results:
                continue
            payload[name] = {
                "release": round(results[name]["release"], 4),
                "output_sha256": results[name]["output_sha256"],
                "zig": zig,
                "runs": args.runs,
                "cpu": int(args.taskset),
                "cv": results[name]["cv"],
            }
        pin_path().write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        print(f"perf: pin written: {pin_path().relative_to(ROOT)}")

    print(f"{'bench':<14}{'median_s':>10}{'pin_s':>10}{'ratio':>8}")
    gate_violations = []
    compared = 0
    for name in BENCHES:
        if name not in results:
            continue
        entry = results[name]
        row = f"{name:<14}{entry['release']:>10.4f}"
        if pin is not None and name in pin and "release" in pin[name]:
            compared += 1
            pin_release = pin[name]["release"]
            ratio = entry["release"] / pin_release if pin_release else float("inf")
            row += f"{pin_release:>10.4f}{ratio:>8.2f}"
            if ratio > GATE_RATIO:
                gate_violations.append(name)
        print(row)

    ok_count = len(results)
    total = len(BENCHES)
    if failures:
        print(f"perf: {ok_count}/{total} benches ok (failures: {', '.join(failures)})")
        return 1
    if gate_violations:
        label = "gate exceeded" if args.gate else "report only, pin threshold exceeded"
        print(f"perf: {ok_count}/{total} benches ok ({label}: {', '.join(gate_violations)})")
        return 1 if args.gate else 0
    if compared:
        print(f"perf: {ok_count}/{total} benches ok (fast profile within pins; compared {compared}/{total})")
    else:
        print(f"perf: {ok_count}/{total} benches ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
