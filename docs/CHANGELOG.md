# Changelog

This file tracks only current release-facing changes. Historical review notes
belong in git history, not in long Markdown logs.

## Unreleased

- Resolve bare calls inside imported modules to the defining module and emit
  the module prefix, so sibling calls build. Type-check alias calls `h.f()`
  with generic inference and comptime arguments, and reject calls to functions
  the module does not define with exit 6.
- Load transitive import chains to a fixed point. Enforce struct generic
  constraints at instantiation with exit 6, and raise a codegen error for an
  unresolvable generic return type instead of emitting void.

- Add `a7 check FILE --layout`. It prints each named struct's Zig memory
  layout: alignment-ordered field offsets, size, 64B lines touched, line-use
  percent, and field-access counts as a hot/cold hint. Offsets match Zig
  0.16.0 `@offsetOf` ground truth, pinned by tests.
- Add `aos_walk`, `soa_walk`, `stride_walk`, and `kv_append` benches. The
  AoS/SoA pair runs identical work on identical footprints: parallel arrays
  measure 1.59x faster than a 24-byte struct array (0.174s vs 0.277s,
  ReleaseFast medians of five on one host). `stride_walk` measures line
  utilization; A7 has no threads, so it is not a coherence test.
- Add a six-program bench corpus and `scripts/bench_perf.py`. It times
  ReleaseFast builds as the median of three runs and compares them with
  per-host pins in `bench/pins/<host>.json`. `run_all_tests.sh` runs it
  report-only; `--gate` exits 1 past 1.15 times the pinned median.

- Release builds allocate through `std.heap.smp_allocator`. Debug builds keep
  `std.heap.page_allocator`.

- Buffer stdout print helpers in one persistent 4096-byte writer, flushed at
  program exit and before every stderr write. Stderr keeps per-call flush, so
  stdout content always precedes later stderr content for completed programs.
  Release builds lower proven-range integer `+`, `-`, `*` and compound forms
  to non-wrapping operators; debug builds and unproven cases keep wrapping.
  Add `--no-nonwrap` to force wrapping and `--build-profile` plumbing to
  select the build profile.

- Display type-set AST nodes without crashing. Bound malformed type and defer
  cycles in console output while preserving repeated shared nodes.

- Keep the continuing branch's actual safety facts after an early return. A later
  assignment, mutating call or deferred write cannot restore an old nonzero guard.
- Discard unused loop-update call results while preserving continue/break order.
- Exercise installed check/build/run/doctor/version commands from both wheel and
  source-distribution builds, including exact version identity and error cases.

- Add `a7 check`, `a7 build`, `a7 run`, `a7 doctor`, and `a7 --version`.
  Native builds protect loaded sources and require Zig 0.16.0. Reuse the loaded
  source list instead of parsing imports twice.
- Render nested type names and console labels with explicit stacks. Escape
  token values, AST literal details and source-panel filenames in Rich output.
- Preserve fixed-array assignment evaluation order, escape control bytes in Zig
  character literals, and discard deferred return values and unused constant results.

- Load deep module dependency chains iteratively and discard incomplete cache
  entries after a failed load, so fixing a missing dependency permits a clean retry.
- Verify installed wheels and source distributions by running a multi-file
  program in Zig debug and release profiles outside the checkout.
- Add one local/CI release command with tag/version/changelog checks, docs checks,
  locked dependency audits and static scanning. Resolve Git before the secret scan.
- Record the core V1 scope, automatic runtime memory option, 10% performance
  target, Zig integration and later A7-written compiler direction.

- Replace recursion in integer-literal extraction, mutation-base analysis and
  symbol-table dumps with iteration. Strengthen the internal recursion scanner
  for dispatch dictionaries and deferred callbacks. Full compiler conversion
  remains in progress.

- Reject malformed declarations without dropping source, and report malformed
  numeric separators and unsupported ellipses as tokenizer errors.
- Invalidate safety facts across branches, loops, mutating reference calls,
  and deferred deletion. Reject the audit's accepted-crashing programs before
  native output. Example guards now state the bounds and divisors they require.
- Align arithmetic types with native operands, apply defined wrapping to integer
  addition, subtraction and multiplication, and repair compound division and
  remainder lowering.
- Repair IO brace escaping, signed absolute-value result typing, backend names,
  string array defaults, and generic array/slice field types.
- Accept in-range literals in argument and return contexts and literal constant
  array bounds. Diagnose invalid entrypoint signatures and import cycles.
- Preserve match-expression fallback nodes in JSON output. Replace classifier-
  derived cast test expectations with an independent policy table.

- Rebuilt the documentation site with light and dark themes, persistent navigation,
  a guided tour, an example index, and twelve language reference topics.
- Added Markdown twins, feature metadata, body-text search, and explicit generated
  export checks. Removed invented compiler-success transcripts and documented
  native failures found while checking reference examples.

- A deferred statement that assigns inside a loop no longer leaves a stale
  proof behind, so `while ... { defer x -= 5; y := 10 / x }` is rejected
  instead of dividing by zero at run time.
- Corrected three documents that said typed math spellings such as `sqrt_f64`
  are callable bare builtins; they exit 6.
- Aligned the public status page with `docs/STATUS.md`: six active priorities
  and the three known gaps the page had dropped.
- Pinned `oven-sh/setup-bun` to a commit and `uv` to a version in CI, release
  and docs workflows.
- Prevented output and documentation writes from overwriting source modules or
  each other. Artifact reports now describe files written by the current run.
- Corrected operator-token columns and preserved imported diagnostic locations.
- Corrected Zig keyword escaping and unused or shadowed loop captures.

- Constant float remainder now uses the Zig runtime truncation rule, including negative
  dividends and signed zero.

- Confined docs preview requests and release manifest reads to their allowed
  directories, with regression checks for encoded paths and symlinks.
- Dependency audits now read exported locked project requirements.
- Release packaging reuses gate-verified distributions and native examples.
- Removed repeated pytest subsets from the local gate and duplicate AST child
  enumeration from preprocessing. Parser block errors propagate directly.
- Reconciled public status, recursion limits, and research/audit navigation.
- Render numbered documentation steps as ordered lists.
- Removed six alternate historical pointer PDFs and retained the main report.
- Repository secret checks now honor Git ignore rules for untracked files while
  still checking tracked ignored files.

- Consolidated project-status documentation around the current Zig-only
  compiler surface and removed stale review/audit handoff files.
- Added `scripts/project_status.py` as the source for example counts and small
  release facts.
- Release archive verification now derives example counts from the repository
  instead of duplicating fixed numbers.

## 0.3.0

- Installed `a7` CLI entrypoint.
- Zig is the only supported public backend.
- Added debug and release example artifact verification.
- Added wheel install smoke verification.
- Added checksum and archive-content verification for release artifacts.
- Added internal safety proof planning and operation-specific backend approvals
  for casts, division/modulo, bounds-sensitive indexing/slicing, ref
  dereferences, and direct use after `del`.
- Expanded the verified example suite to 43 runnable programs.
