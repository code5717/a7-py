# Bench

Pin-based perf gate for the A7 bench workloads in this directory.

Run from the repo root:

```bash
uv run python scripts/bench_perf.py [--pin|--gate]
```

Default compares available release medians against the pin and checks output
hashes. A timing threshold violation is reported but does not fail a default
run. When no pin is loaded, the default run reports timings only.

`--gate` requires a complete host pin before building: every workload needs a
positive finite release median and a nonempty output hash string. A missing,
unreadable, malformed or incomplete pin exits 1. With a usable pin, any release
median above pin x 1.15 exits 1.

`--pin` rewrites the pin from the current run. Combining `--pin` and `--gate`
exits 2 before building or changing the pin. Update with `--pin`, then check
with `--gate` in a separate run. `--runs N` sets runs per binary, default 7.
Pin and gate modes require at least 5 samples. The harness drops the fastest
and slowest sample for its trimmed median with 5 or more samples. Symmetric
trimming does not change the median. CV is calculated from all samples;
CV above 0.10 rejects pin/gate measurements and leaves an existing pin unchanged.
Report-only mode warns about noisy measurements without qualifying them.

`--taskset CPU` must select one CPU in the inherited affinity mask. Pin/gate
choose the lowest allowed CPU when omitted. Missing taskset or an invalid
requested CPU fails before native work. Effective CPU is printed and recorded
with sample count and raw-sample CV in new pins. Older complete pins remain
readable. They lack these measurement-validity fields. CPU pinning and low CV do not prove host idleness;
re-pin only in a controller-confirmed idle window. These host pins use the 1.15
regression ratio; L38's 1.10 C-relative runtime and live-memory limit is separate.

## Pins

`pins/<hostname>.json` holds one entry per workload:

- `release`: pinned release median, seconds
- `output_sha256`: pinned stdout hash for the run
- `zig`: Zig version that produced the pin

Output must hash-match the pin; a mismatch fails the run.

## Memory workloads

The October 8 L67 promotion added three workloads, each with 10,000,000
iterations:

| Workload | Operation | Expected result line |
| --- | --- | --- |
| `mem_shared` | Write through one reference and read through its alias | `result: 49999995000000` |
| `mem_returned` | Return a heap allocation from a helper, read it and delete it | `result: 50000005000000` |
| `mem_cleanup` | Count explicit-deletion paths and paths that omit deletion | `result: 9999900 100` |

`mem_cleanup` intentionally takes 100 paths without `del`. Its counters describe
control flow; they do not measure physical frees, retained bytes or automatic
cleanup. Native correctness across Debug, ReleaseSafe and ReleaseFast does not
establish optimized work retention or L38's C-relative time and memory limits.
The [promotion record](../docs/audits/2026-10-08-l67-promotion.md) links the
native correctness evidence and its source identity.

The October 16 promotion adds four unchanged public-input workloads for host
regression checks. The harness sends `A\n` to each and requires stdout to be
exactly the result line below followed by a newline, with empty stderr. Extra
output, a different numeric result or `input failed` fails validation, even
without a host pin.

| Workload | Original count | Operation | Expected result line for A |
| --- | --- | --- | --- |
| `mem_cache` | 100,000,000 requests | Replace entries in three named heap slots | `result: 6616666665 49999999 50000001` |
| `mem_copy` | 50,000,000 rounds | Copy 64 words, mutate the source and check the snapshot | `result: 942376503` |
| `mem_text` | 1,000,000 rounds | Mutate and scan a 4,096-byte heap buffer | `result: 98811553` |
| `mem_cyclic` | 30,000,000 rounds | Update two heap records linked by integer peer IDs | `result: 757942091` |

The [promotion record](../docs/audits/2026-10-16-l67-promotion.md)
verified 24 exact outputs: these four sources at their original counts, with
both `A\n` and `B\n`, across Debug, ReleaseSafe and ReleaseFast. The host
harness uses only `A\n`; the B-seed evidence remains a separate correctness
check. The optimized inspection
traces workload allocation pointers, payload operations, loop bounds and
successful release paths in all eight ReleaseSafe/ReleaseFast binaries.
Dynamic allocator counts, all failure paths and memory costs remain unmeasured.

Cache uses three named slots. Text is a buffer-scan proxy without retained
parser output. The integer-ID cycle has no reference cycle or cyclic ownership.
All four use explicit `new` and `del`. Their promotion does not qualify an
automatic-memory mechanism or L38's per-workload C runtime and live-memory
limits. The eight inspected optimized binaries use `smp_allocator`; the Debug
builds use `page_allocator`. This profile difference supplies no performance
comparison.

The suite now contains 17 workloads. The existing `cx89` host pin remains
unchanged and lacks seven entries: `mem_shared`, `mem_returned`, `mem_cleanup`,
`mem_cache`, `mem_copy`, `mem_text` and `mem_cyclic`. `--gate` rejects that
incomplete pin before building. Calibrate all 17 workloads in a
controller-confirmed idle window before using the expanded suite as a timing
gate. No such measurement window or new pin is established by the promotion.
The default run can report unpinned entries.

## Host-specific note

Pins are per host. `pins/cx89.json` records one machine only; timings from
another host are not comparable against it. Add a pin file per machine.
