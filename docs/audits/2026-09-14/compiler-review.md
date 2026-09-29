# Compiler audit evidence

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it.

Scope: read-only implementation review plus temporary source compilation and native execution. No compiler implementation changed.

Each finding below uses the same fields: priority, location, reproduction, observed result, suggested correction and acceptance.

(docs/plan/research/memory/notes-h-audits-pdfs-current-memory.md cites this report as `C-review:22`, `:28` (C1), `:44` (C2), `:62` (C3) and `:78` (C4), by original numbering; this header added four lines.)

The compiler accepts programs that violate its documented safety contract. Three small programs compile through the full production pipeline, build with Zig 0.16.0, and panic with division by zero in Debug. ReleaseFast executions also show invalid behavior. These are release blockers for the current safety claims.

## Method and environment

- Read `AGENTS.md`, `README.md`, `docs/STATUS.md`, and `docs/SAFETY_CONTRACT.md`.
- Inspected compiler orchestration, type checking, safety analysis, preprocessing, Zig generation, and selected tests.
- Used `A7Compiler.compile_file_detailed` for reproductions, rather than a simplified test helper.
- Initial `uv` invocation failed because the Mise shim had no configured version. Direct executable `/home/cx89/.local/share/mise/installs/uv/0.12.6/uv-x86_64-unknown-linux-musl/uv` created `.venv` with Python 3.13.15 and the project dependencies.
- Zig was absent from PATH. The coordinating audit supplied `/tmp/a7-audit-20260914/zig/zig`, downloaded from the CI-pinned official distribution and verified by the coordinator.
- Native commands used `zig build-exe <generated.zig> -O Debug` and `-O ReleaseFast`. Executables and generated Zig stayed under `/tmp`.
- Small reproduction sources are in `repros/`. Native probe details were recorded in `/tmp/a7-audit-probe-results.json`. This report preserves the relevant outcomes because temporary files are not durable.
- The coordinator subsequently reported a provider safety-filter failure and instructed this reviewer to stop further execution. No blocked operation was retried. Remaining validation is explicitly identified below.

## C1. Compound assignments corrupt proof facts

Priority: P1.

Location: `a7/safety.py:311-328`, particularly the unconditional `set_symbol(node.target.name, rhs)` at line 327.

Reproduction: `repros/a7audit_compound_zero.a7` initializes `d: i32 = 1`, executes `d -= 1`, then prints `10 / d`.

The safety pass records the right-hand value `1` as the resulting value of `d`. The actual value is zero. A7 compilation succeeds and emits `@divTrunc(10, d)`.

Observed native result: Debug builds successfully and terminates with signal 6 and `panic: division by zero`. ReleaseFast builds and exits zero despite the invalid operation. The release result must not be interpreted as successful qualification.

Suggested correction: compute each compound assignment's result facts using the previous target fact and the operator, or invalidate the target facts when the result cannot be established. Account for writes through references separately.

Acceptance: regression cases for every compound operator must either establish the correct post-assignment interval or reject dependent unsafe operations before code generation. Include division, indexing, slicing, and narrowing casts downstream of updates.

## C2. Branch and loop analysis keeps stale facts

Priority: P1.

Location: `a7/safety.py:301-307`, `338-373`.

Reproduction: `repros/a7audit_branch_zero.a7` initializes `d: i32 = 1`, executes `if true { d = 0 }`, then prints `10 / d`.

Block exit restores all saved facts, including facts about outer bindings modified inside the block. Branch processing also restores the prior facts without joining reachable outcomes. A7 accepts the program.

Observed native result: Debug builds and terminates with signal 6 and `panic: division by zero`. ReleaseFast builds and exits zero despite the invalid operation.

Related accepted sources: `a7audit_branch_bounds.a7` changes an index from zero to 100 before indexing three elements. `a7audit_loop_bounds.a7` indexes three elements through an unbounded loop whose break occurs after the index passes three. Both pass A7 safety analysis. Their native builds fail earlier because inferred array literals lower to tuples that cannot use runtime indexing. Runtime bounds failure was therefore not demonstrated. Explicitly typed array follow-ups remain unrun.

Suggested correction: preserve writes to outer bindings across lexical blocks, join only reachable branch outcomes, and compute loop invariants or conservatively invalidate loop-written facts before validating repeated accesses.

Acceptance: branch mutation, loop-carried mutation, nested scope shadowing, early return, break, continue, and zero-iteration cases must have integrated positive and negative tests. No initial iteration fact may justify later iterations without an invariant.

## C3. Calls fail to invalidate facts for mutated reference arguments

Priority: P1.

Location: `a7/safety.py:444-447`.

Reproduction: `repros/a7audit_ref_zero.a7` declares `zero :: fn(x: ref i32) { x = 0 }`, initializes `d: i32 = 1`, calls `zero(d)`, and prints `10 / d`.

The call visitor visits arguments but does not invalidate caller facts affected by reference mutation. A7 emits a real write through `x.?.*` and then divides by the now-zero caller variable.

Observed native result: Debug builds and terminates with signal 6 and `panic: division by zero`. ReleaseFast builds and terminates with signal 11.

Suggested correction: invalidate facts about arguments passed to mutable references and any reachable aliases. A conservative call-effect rule is acceptable before precise interprocedural summaries exist.

Acceptance: direct calls, function pointers, imported functions, nested reference fields, and multiple aliases must not retain pre-call range or nil facts after possible mutation.

## C4. Deleted names leak across function boundaries

Priority: P2.

Location: `a7/safety.py:288-294`, `395-399`, `724-726`.

Reproduction: `repros/a7audit_deleted_name.a7` defines an unused function that allocates and deletes local `p`. A later `main` declares a separate `p: i32 = 1` and prints it.

A7 rejects the unrelated integer in `main` with `Use after move or delete`. The pass resets value facts per function but tracks deletion in a single string-name set. That set is reset only at analysis start, not function entry. New declarations do not clear it either.

Suggested correction: key ownership state by resolved binding identity and maintain function and lexical scope boundaries. Resetting only at function entry would leave same-name nested scope problems.

Acceptance: unrelated locals in separate functions and shadowed locals in nested blocks remain independent, while genuine direct use after deletion still fails.

## C5. Valid A7 identifiers can produce invalid Zig declarations

Priority: P2.

Location: `a7/backends/zig.py:637-690` and `1505-1516`.

Reproduction: `repros/a7audit_reserved.a7` declares `error := 1` and prints it. A7 accepts it, emits declaration `const error = 1`, but escapes the use as `@"error"`.

Observed result: both Debug and ReleaseFast builds fail with `expected 'an identifier', found 'error'`.

Suggested correction: use one complete Zig identifier escaping function for declarations, references, function names, parameters, fields, variants, aliases, and generated bindings.

Acceptance: exercise the full Zig keyword set across all supported A7 binding contexts and compile the generated code with Zig, not only string comparisons.

## C6. Loop capture lowering misses unused and shadowed names

Priority: P2.

Location: `a7/backends/zig.py:920-952`; `a7/ast_preprocessor.py:433-507` only registers ordinary variable declarations while traversing loop nodes.

Reproductions: `repros/a7audit_unused_iterator.a7` and `repros/a7audit_shadow_iterator.a7`.

Observed result: A7 accepts both. Zig rejects the first with `unused capture`, and the second with `capture 'x' shadows local constant from outer scope`. The inferred tuple iterable can also cause an independent comptime iteration failure, so these sources reveal multiple backend issues. The capture diagnostics themselves are explicit.

Suggested correction: treat loop captures as scoped declarations, rename their uses consistently, and emit `_` for unused captures. Resolve inferred array literal lowering independently.

Acceptance: ordinary and indexed loops compile with unused captures, shadowed names, and nested loops. Verify typed arrays and inferred arrays separately.

## C7. Flat expressions can fail with an internal recursion error

Priority: P2.

Location: `a7/passes/type_checker.py:1118`, `1129`, `1194-1195`.

Reproduction source can be generated with:

```python
source = 'main :: fn() { x := ' + ' + '.join(['1'] * 1200) + '\n }'
```

The parser accepts the flat expression. Full compilation returns internal failure with `exception_type='RecursionError'` and `maximum recursion depth exceeded`. Direct stage inspection localizes the failure to recursive binary-expression type checking before safety analysis begins. Safety expression traversal also remains recursive in source, but no independent stress result for that stage was collected.

Suggested correction: use iterative postorder expression typing and audit subsequent passes with the same depth fixtures. If a deliberate language complexity limit is introduced, report it as a source diagnostic rather than an internal exception.

Acceptance: deep valid expressions pass the full pipeline under the intended recursion limit, or fail with a documented bounded-complexity source diagnostic.

## C8. Codegen test helper does not represent the production pipeline

Priority: P2, validation quality.

Location: `test/test_codegen_zig.py:57-92`.

`compile_a7_to_zig` does not raise name-resolution errors, does not inspect type-checking errors, and does not invoke `SemanticValidationPass`. It does inspect safety errors. Consequently, a passing helper-based codegen test does not establish that the same source is valid through the production compiler. Many tests use `zig ast-check`, which establishes syntax and does not establish successful native type checking or execution.

Suggested correction: distinguish deliberate backend unit tests from production pipeline integration tests. Integration tests should call `A7Compiler`, assert stage outcomes, and build and execute meaningful programs when claiming runtime support.

Acceptance: invalid source cannot silently enter production-style codegen tests, and each advertised feature has full-pipeline native success and diagnostic rejection coverage.

## Coverage limits and completion implications

This was a focused adversarial compiler audit, not exhaustive language qualification. It did not complete a formal grammar review, module-system audit, generic specialization matrix, ownership proof, fuzzing campaign, platform matrix, or full numerical semantics review. The coordinating agent owns the separate full release gate result. Passing that gate does not invalidate the reproductions above.

Existing status docs already acknowledge incomplete arithmetic overflow, shifts, union discriminants, ownership, generics, multi-return lowering, and runtime variadics. Those are known design and implementation tracks, not newly discovered regressions. `a7/safety.py:631-636` returns before integer overflow proofing, consistent with the stated gap, but the broad opening safety promise should not be treated as achieved.

Note (2026-09-16): integer `+`, `-` and `*` overflow is decided by ledger L5 (wrapping), and the ownership direction by L15, L17–L19 (see the [memory plan](../../plan/memory.md)). Findings C1–C8 are unaffected.

The completion roadmap should start by repairing proof soundness and isolating compiler state by binding identity, then qualify the advertised supported subset through real native builds. Broader language features should follow explicit semantic decisions and acceptance tests. No finding in this report has been fixed or closed.
