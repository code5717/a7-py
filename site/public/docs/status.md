# Implementation Status

What works, what's incomplete, and what's deferred. This page is the
canonical roadmap. Keep `docs/CHANGELOG.md` short and release-facing;
this is where the longer story lives.

## Current surface

- **Backend:** Zig is the only supported public backend.
- **Pipeline:** tokenizer, parser, semantic analysis, internal safety
  proof planning, AST preprocessing, and Zig code generation are all in
  place.
- **Source recursion:** banned across direct, mutual, and
  function-pointer-alias-cycle forms.
- **Example suite:** 46 programs, verified against golden output
  fixtures. Run `uv run python scripts/project_status.py` for current
  counts.

## Active priorities

1. Keep status and release facts **script-derived**, not hard-coded.
2. Add practical multi-file A7 support that always emits one combined
   Zig file.
3. Write the numeric design brief before adding `int`, `uint`, `number`,
   or any new `cast()` behaviour.
4. Split safety proofing into internal CFG, fact, obligation,
   proof-discharge, and backend-plan stages.
5. Finish generic specialization before broad cross-module generic
   workflows.
6. Add workflow commands: `a7 check`, `a7 build`, `a7 run`, `a7 doctor`,
   `a7 --version`.

## Known gaps

These exist in code but are incomplete. Treat them as caveats when
relying on the listed feature.

- **File-backed imports** target one combined Zig output file. Selected
  imports, `using import`, broad cross-module type checking, and generic
  module workflows are follow-up work.
- **Fixed-width overflow** on `+ - *` is not proven by the safety pass.
- **Shift amount obligations** are not yet enforced.
- **Union discriminant access** is not lowered.
- **Full `ref` / `del` alias behaviour** has edge cases the planner
  doesn't cover.
- **Ownership and lifetime guarantees** are not modelled beyond
  use-after-`del`.
- **Generic specialization** and call-chain propagation are incomplete
  past simple cases.
- **Multiple return values, destructuring, tagged union tag workflows,
  variadic runtime lowering** are not current backend features.

## Stdlib gaps

- `Option<T>`, `Result<T, E>` — planned.
- Collections (`Vec`, `HashMap`, etc.) — planned.
- File and network IO — out of current scope.
- Concurrency primitives — deferred.

See [Standard Library](/a7-py/ref/stdlib) for what is shipped today.

## Deferred tracks

These need design documents and prerequisites before any code lands. We
are not accepting PRs that take a position on them yet.

- Tensor / array-programming primitives for AI.
- GPU code generation.
- Performance annotations and runtime profiling.
- Package registry / lockfile resolution.
- Concurrency runtime.

## How to read this page

If a feature is listed under **Active priorities** or **Known gaps**, it
is partially implemented — you can call it, but expect edges. If a
feature is listed under **Deferred tracks**, treat it as out of scope
for the current repository — open a design discussion before any code
attempt.

If a feature is listed in [Features](/a7-py/ref/features) under
**Supported**, it's covered by tests and golden outputs.

## Versioning

A7 is pre-1.0. Minor version bumps may break source. Major version bumps
intentionally do.

The version is `0.16.x` — the digit tracks the pinned Zig toolchain
version, not the language. When Zig moves to 0.17, A7 follows.
