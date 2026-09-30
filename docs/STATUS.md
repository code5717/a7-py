# A7 Status

This is the single working status document for current gaps, roadmap, and
implementation priorities. Keep `docs/CHANGELOG.md` short and release-facing.

## Current Surface

- Zig is the only supported public backend.
- Constant float remainder follows the runtime truncation rule, including the
  dividend sign and negative zero.
- The compiler pipeline covers tokenization, parsing, semantic analysis,
  internal safety proof planning, AST preprocessing, and Zig code generation.
- Output paths cannot overwrite input modules. Diagnostics retain module origins;
  artifact reports exclude stale files.
- Source recursion is banned. Use loops, explicit stacks, queues, and
  index-based worklists.
- `a7 check FILE --layout` reports struct memory layout (alignment-ordered
  offsets, size, 64B line use, field-access counts), matching the emitted
  Zig binary.
- The bench corpus measures layout effects: the AoS/SoA pair proves
  parallel arrays 1.59x faster than struct arrays for subset-field loops
  (`bench/`, `scripts/bench_perf.py`).
- The example suite is verified against golden output fixtures. Current counts:
  `uv run python scripts/project_status.py`.
- The perf gate times the six-program `bench/` suite as median-of-3
  ReleaseFast runs against per-host pins in `bench/pins/<host>.json`.
  `run_all_tests.sh` runs `scripts/bench_perf.py` report-only; `--gate` exits 1
  past 1.15 times the pinned median.

Selected branch joins, loop mutations, reference calls and deferred effects now
invalidate stale safety facts. These repairs remain incomplete. Current probes
still accept SAF-2 field-name confusion, SAF-3 fallthrough division, SAF-6 global
mutation across calls and SAF-8 repeated field deletion. See the
[revalidation evidence](audits/2026-09-20-core-v1/critical-safety-after-saf4.json).
The SAF-3 and SAF-6 candidate fix is parked in
[the candidate note](audits/2026-09-20-resumed-v1/safety-candidate.md) until
the IR fact engine lands: applying it now would reject alias-call programs
that compile today (user decision, 2026-09-30). The checks do not establish
complete alias or lifetime safety.

## Active implementation priorities

1. Keep status and release facts script-derived, not hard-coded.
2. Add practical multi-file A7 support that always emits one combined Zig file.
3. Resolve the numeric gates in [the v1 plan](plan/README.md) before changing
   arithmetic or casts. Decisions L3 and L4 retain explicit-width integers and
   reject `int`, `uint`, and `number`.
4. Split safety proofing into internal CFG, fact, obligation, proof-discharge,
   and backend-plan stages.
5. Finish generic specialization before broad cross-module generic workflows.
6. Maintain installed-distribution checks for `a7 check`, `a7 build`, `a7 run`,
   `a7 doctor` and `a7 --version`. Wheel and source-distribution workflows pass
   on the current Linux x86-64 target.
7. Finish iterative compiler traversal. Module loading, type display, console
   labels and several helpers now use explicit stacks. The full pipeline still
   contains recursion. See the [delivery roadmap](plan/delivery-roadmap.md).

## Known Gaps

- Exact-fit untyped constants and declaration-order-independent global typing
  are approved and in implementation. See [P-TYP](plan/packets/P-TYP-forward-globals.md).
  Release verification remains open. The earlier strict float-to-integer
  rejection proposal was superseded.
- The low-recursion test fails under `python -m pytest` but passes through the
  pytest entry point. See the [paired check](audits/2026-09-20-core-v1/recursion-launcher-check.md).
  Passing the gate does not qualify the full no-recursion requirement.

- A labeled loop whose label is never targeted no longer emits a label: the
  fix landed with commit `ed0baff`, and the never-targeted case is pinned in
  both profiles by the `unused-labels` case in
  `test/test_resume_backend_bindings.py`.

- Local constant usage is not yet tracked by declaration identity. Sibling-scope
  name collisions can omit required Zig discards; nested constant shadowing can
  emit duplicate bindings. The [review follow-up](audits/2026-09-20-core-v1/backend-glm-followup.md)
  preserves both reproducers.

- File-backed imports target one combined Zig output file. Selected imports,
  `using import`, module-qualified struct literals, and bare entry-file
  references to module functions remain follow-up work.
- Integer `+`, `-`, and `*`, including compound forms, keep wrapping by
  default. Release builds lower proven-range results to non-wrapping
  operators; `--no-nonwrap` forces wrapping everywhere. Shift proofs, signed
  absolute-value limits, union discriminant access, full ref/del alias
  behavior, and ownership/lifetime guarantees remain incomplete.
- Generic specialization and call-chain propagation are incomplete.
- Multiple return values, destructuring, tagged union tag workflows, and
  variadic runtime lowering are not current backend features.
- `Option`, `Result`, collections, and fuller string/memory helpers are planned
  stdlib work.

The focused native probes record these repaired behaviors and remaining limits:

- Escaped IO braces now compile and print literal braces. Signed-integer
  `math.abs` preserves the declared signed result type; its minimum negative
  input has no representable positive result and is not a proven safe case.
- Scalar-filled fixed-array initializers and direct `string.len` access are rejected.
- A top-level local `@type_set` alias can pass semantic checking but fail code generation.

See [documentation verification](../site/docs/content-verification.md) for source,
commands, diagnostics, and supported alternatives. Historical audit reports retain
the earlier failures. Current repairs have regressions in `test/test_audit_type_boundaries.py` and
`test/test_audit_backend_repairs.py`.

## Planned work

Automatic memory belongs to core V1. Runtime help is allowed, but no mechanism
is selected or implemented. The Python compiler remains the V1 implementation;
Zig handles generated code and future runtime/native integration. V2 aims to
implement the compiler in A7.

AI, concurrency, multicore and GPU work remain design constraints and later
qualification tracks under [L36-L46](plan/decisions.md). They are not implemented
features. Core V1 does not claim their qualification. A package registry remains
outside the current scope.

## Audit evidence

The [audit index](audits/README.md) separates dated findings from current checks.
A passing example suite does not establish that all accepted programs are safe
or that the compiler implements the full specification. The
[execution plan](plan/execution.md) tracks correctness repair and approval packets.
