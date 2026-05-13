# A7 Status

This is the single working status document for current gaps, roadmap, and
implementation priorities. Keep `docs/CHANGELOG.md` short and release-facing.

## Current Surface

- Zig is the only supported public backend.
- The compiler pipeline covers tokenization, parsing, semantic analysis,
  internal safety proof planning, AST preprocessing, and Zig code generation.
- Source recursion is banned. Use loops, explicit stacks, queues, and
  index-based worklists.
- The example suite is verified against golden output fixtures. Current counts:
  `uv run python scripts/project_status.py`.

## Active Implementation Priorities

1. Keep status and release facts script-derived, not hard-coded.
2. Add practical multi-file A7 support that always emits one combined Zig file.
3. Write the numeric design brief before adding `int`, `uint`, `number`, or new
   `cast()` behavior.
4. Split safety proofing into internal CFG, fact, obligation, proof-discharge,
   and backend-plan stages.
5. Finish generic specialization before broad cross-module generic workflows.
6. Add workflow commands: `a7 check`, `a7 build`, `a7 run`, `a7 doctor`, and
   `a7 --version`.

## Known Gaps

- File-backed imports target one combined Zig output file. Selected imports,
  `using import`, broad cross-module type checking, and generic module workflows
  remain follow-up work.
- Fixed-width overflow, shifts, union discriminant access, full ref/del alias
  behavior, and ownership/lifetime guarantees are incomplete.
- Generic specialization and call-chain propagation are incomplete.
- Multiple return values, destructuring, tagged union tag workflows, and
  variadic runtime lowering are not current backend features.
- `Option`, `Result`, collections, and fuller string/memory helpers are planned
  stdlib work.

## Deferred Tracks

Tensor, AI, GPU, performance annotations, package registry, and concurrency
runtime support need separate design documents and prerequisites before code.
