# Bench

Pin-based perf gate for the A7 bench workloads in this directory.

Run from the repo root:

```bash
uv run python scripts/bench_perf.py [--pin|--gate]
```

Default compares release medians against the pin and checks output hashes.
`--pin` rewrites the pin from the current run. `--gate` fails when any
release median exceeds pin x 1.15. `--runs N` sets runs per binary.

## Pins

`pins/<hostname>.json` holds one entry per workload:

- `release`: pinned release median, seconds
- `output_sha256`: pinned stdout hash for the run
- `zig`: Zig version that produced the pin

Output must hash-match the pin; a mismatch fails the run.

## Host-specific note

Pins are per host. `pins/cx89.json` records one machine only; timings from
another host are not comparable against it. Add a pin file per machine.
