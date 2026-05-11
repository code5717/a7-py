# A7 Compiler — Language-Core Gap Snapshot

**Compiler Status**: Full pipeline runs (Tokenizer -> Parser -> Semantic -> Preprocessor -> Codegen).  
**Current Test Status**: check with `PYTHONPATH=. uv run pytest --tb=no -q`.  
**Examples**: 38/38 pass end-to-end compile + build + run + output verification.

---

## Recently Completed (Language Core)

1. **Labeled loops** — `@outer while`, `@outer for`, `@outer for-in` with `break outer` / `continue outer` in the Zig backend.
2. **C backend retired** — Zig is the only supported code generation target.
3. **Type checker: slice and index validation** — `visit_slice_expr` returns `SliceType`; `visit_index_expr` rejects non-integer indices.
4. `match` expressions are type-checked and participate in expression typing.
5. `@type_set(...)` parses in value context.
6. Generic arithmetic and generic local literal initialization are relaxed where valid.
7. Generic struct literal field checks substitute concrete type arguments.
8. Field access resolves concrete struct layout for generic instances.
9. Variadic parameter syntax is parsed and partially type-checked in semantic
   mode, and codegen modes now fail closed until runtime iteration/ABI lowering
   is implemented.
10. Match semantics now enforce:
   - pattern type compatibility with the scrutinee,
   - bool/enum exhaustiveness (or explicit `else` / wildcard),
   - wildcard pattern parsing (`case _:`),
   - return-path correctness for exhaustive enum/bool `match` without `else`.
11. Deferred statement payloads are traversed by type checking and semantic validation.
12. `ret` payloads are traversed through the semantic validator's `value` field.
13. `for-in` and indexed `for-in` reject scalar/non-iterable expressions during type checking.
14. Constant folding covers arithmetic, boolean logic, literal comparisons, and integer bitwise expressions.
15. Installed CLI entrypoint (`a7`) is wired through `pyproject.toml`.
16. Debug/release example artifact verification is available through `scripts/build_examples.py`.
17. `run_all_tests.sh` includes Zig example E2E verification, debug/release artifact builds, the error-stage matrix, docs style checks, and full pytest.
18. Local file-based imports now fail closed during codegen modes instead of emitting unresolved backend code. Semantic mode still validates resolver loading.
19. Zig unsupported expression fallbacks now fail as compiler-side codegen errors instead of generated `@compileError` expressions.
20. `fall` now lowers in Zig when used as the final direct
    statement of a non-final match case.
21. Zig generation is the current optimization focus; C parity work has been removed from the active support matrix.
22. String literal tokenization now rejects unknown escapes and malformed `\xHH` escapes; valid escapes are decoded into AST literals and re-escaped for backend output.
23. Return type mismatches inside if branches, match branches, and nested blocks are covered by semantic regression tests.
24. Bool and enum match statements/expressions now report non-exhaustive coverage unless an else or wildcard branch is present.
25. `slice.ptr` and `slice.len` now type-check and lower in Zig.
26. `string[start..end]` and `string[start..]` now type-check as `[]char` and lower in Zig.
27. The removed C backend no longer defines project status or release readiness.
31. Semantic validation reports block-local unreachable statements after `ret`, valid `break`/`continue`, `fall`, and fully-terminating `if`/`match` statements.
32. Semantic validation rejects direct, mutual, local function-pointer alias, and higher-order callback trampoline recursion; repeated work must use loops, explicit stacks, or index-based worklists.
33. Index and slice-bound variables must be `usize`; non-negative integer literals remain valid for simple indexing.
34. `new [N]T` heap fixed arrays fail closed until the allocation model is defined.
35. Ordering comparisons reject non-ordered types, and signed variables no longer implicitly assign to unsigned integer types.
36. Match identifier capture patterns bind the scrutinee in branch-local scope
    when no existing symbol with that name is visible. Existing identifier
    patterns keep value-comparison semantics.
37. Fixed-size numeric arrays with the same length and element type support
    element-wise `+` assignment in Zig.
38. Zig stdio lowering uses shared buffered stdout/stderr writers, generated
    print helpers, and `main`-scoped deferred flushes instead of per-print
    flush calls.
39. Internal safety proof planning now owns risky-operation approval for casts,
    division/modulo, array/slice/string indexing and slicing, and reference
    dereferences. Zig codegen consumes the resulting backend plan instead of
    deciding those checks independently.

---

## Remaining Language-First Gaps

0. **Spec-only syntax and parsed-only features**
   - Variadic parameters are parsed and partially type-checked in semantic mode,
     but runtime iteration and backend ABI lowering are not implemented.
     Codegen modes reject them before target emission.
   - Multiple return values / destructuring (`a, b, c := 1, 2, 3`) are planned
     syntax, not current parser support.
   - `@type_set(...)` is implemented for generic constraints. Other `@...`
     intrinsic names such as `@size_of`, `@align_of`, `@type_id`,
     `@type_name`, `@unreachable`, `@likely`, and `@unlikely` are reserved or
     tokenized but not semantically resolved/lowered yet.
   - Array/tensor programming syntax, performance annotations, and control-flow
     narrowing remain tracked backlog items in `TODO.md`.

1. **Advanced match diagnostics**
   - Exact duplicate bool, enum, and scalar literal case patterns are diagnosed.
   - Wildcard-first and fully covered bool/enum cases make later case patterns and else branches unreachable.
   - Literal and compile-time constant numeric/char range overlaps are diagnosed.
   - Conservative non-constant symbolic interval overlaps are diagnosed when
     inclusive ranges share an endpoint symbol.
   - Identifier capture patterns are implemented for branch-local bindings;
     arbitrary symbolic inequality reasoning remains open.

2. **Memory/lifetime model**
   - Current validation covers basic `del` reference checks.
   - Ownership/borrow-style lifetime guarantees are not implemented.
   - Heap fixed arrays (`new [N]T`) are rejected until the language defines
     whether they are fixed-array references or heap slices.

3. **Zig generation hardening**
   - Core conformance is green for the current example suite.
   - Keep expanding mandatory Zig compile/run cases for new language features.
   - Untagged union field construction/access now type-checks and lowers in Zig.
   - Tagged/discriminated union tag workflows are still reserved syntax and not implemented.

4. **Release publishing activation**
   - Local package builds and artifact checks exist.
   - Tag-triggered draft GitHub releases are configured.
   - Package-registry publishing is not part of the current release workflow.

6. **Module-system parity**
   - Missing or broken local imports now fail closed.
   - Existing file-backed local imports resolve for semantic validation but are rejected before backend codegen until multi-file lowering/linking exists.
   - Selected import metadata parses and serializes, but selected imports do not
     currently introduce direct unqualified names for backend-runnable code.
     `using import` remains planned syntax, not a current parser form.
   - Built-in stdlib imports are virtual modules, but now participate in `ModuleResolver`/`ModuleTable` symbol registration like file-based modules.
   - `std/string`, `std/mem`, and `std/collections` are planned but not current public stdlib modules.

---

## Out of Scope for This Snapshot

- Broader package ecosystem and tooling work remain secondary to language-core correctness.
