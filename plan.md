# A7 Language-Core Implementation Plan

## Objective
Ship a language-focused preview where syntax, semantics, typing, and backend behavior are stable and conformance-tested.

## Acceptance Criteria
- Core grammar/AST forms are stable and tested.
- Type checker enforces generic + control-flow semantics for supported features.
- Match semantics are type-safe and exhaustive where required.
- C and Zig backend outputs are behaviorally aligned on language conformance tests.
- Debug and release example artifacts can be built and verified locally.
- Documentation and CI release gates describe the same commands users run.

## Milestones

### M1. Grammar and AST Stability
- Freeze core syntax forms in parser tests.
- Keep AST node contracts explicit for declarations, expressions, and patterns.

### M2. Name Resolution and Scope Semantics
- Ensure scope transitions are deterministic for blocks, loops, and match branches.
- Keep symbol-table behavior stable under nested control flow.

### M3. Type-System Completion
- Finalize generic constraints, substitutions, and inference behavior.
- Enforce assignment/call/operator compatibility without unsound fallbacks.

### M4. Match Semantics
- Enforce pattern type compatibility.
- Enforce bool/enum exhaustiveness (or else/wildcard branch).
- Ensure exhaustive match contributes to return-path analysis.

### M5. Memory/Lifetime Semantics
- Move beyond basic `new`/`del` shape checks to explicit ownership/lifetime rules.
- Define boundary behavior for references and FFI interactions.

### M6. IR/Backend Semantic Parity
- Keep semantic behavior consistent across C and Zig backends.
- Add differential checks for language features as they are added.

### M7. Release Readiness
- Keep `a7` installable as a Python console script.
- Build debug and release artifacts for both backends.
- Run package, docs, E2E, and error-stage checks before tagging.

## Implemented in This Iteration
- Added compiler handling fixes for deferred statement payloads, return payload traversal, non-iterable `for-in`, constant folding, and semantic diagnostics.
- Added `a7` as an installed CLI entrypoint.
- Added debug/release artifact verification through `scripts/build_examples.py`.
- Expanded `run_all_tests.sh` and CI to cover Python tests, error stages, Zig/C examples, debug/release artifacts, package build, and docs build.
- Updated README, SPEC, release docs, site docs, changelog, TODO, and missing-feature status.

## Next Implementation Slice
- Add `fall` semantic rules and backend lowering.
- Add unreachable/overlap diagnostics for match patterns.
- Start explicit lifetime rule design and validation tests.
