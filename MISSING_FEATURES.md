# A7 Compiler — Language-Core Gap Snapshot

**Compiler Status**: Full pipeline runs (Tokenizer -> Parser -> Semantic -> Preprocessor -> Codegen).  
**Current Test Status**: check with `PYTHONPATH=. uv run pytest --tb=no -q`.  
**Examples**: 37/37 pass end-to-end compile + build + run + output verification.

---

## Recently Completed (Language Core)

1. **Labeled loops** — `outer: while`, `outer: for`, `outer: for-in` with `break outer` / `continue outer` in both Zig and C backends.
2. **Slice expressions in C backend** — `arr[1..4]` on arrays and slices, including indexing and `for-in` over slices.
3. **Type checker: slice and index validation** — `visit_slice_expr` returns `SliceType`; `visit_index_expr` rejects non-integer indices.
4. `match` expressions are type-checked and participate in expression typing.
5. `@type_set(...)` parses in value context.
6. Generic arithmetic and generic local literal initialization are relaxed where valid.
7. Generic struct literal field checks substitute concrete type arguments.
8. Field access resolves concrete struct layout for generic instances.
9. Match semantics now enforce:
   - pattern type compatibility with the scrutinee,
   - bool/enum exhaustiveness (or explicit `else` / wildcard),
   - wildcard pattern parsing (`case _:`),
   - return-path correctness for exhaustive enum/bool `match` without `else`.
10. Deferred statement payloads are traversed by type checking and semantic validation.
11. `ret` payloads are traversed through the semantic validator's `value` field.
12. `for-in` and indexed `for-in` reject scalar/non-iterable expressions during type checking.
13. Constant folding covers arithmetic, boolean logic, literal comparisons, and integer bitwise expressions.
14. Installed CLI entrypoint (`a7`) is wired through `pyproject.toml`.
15. Debug/release example artifact verification is available through `scripts/build_examples.py`.
16. `run_all_tests.sh` includes C backend verification, both example E2E verifiers, debug/release artifact builds, the error-stage matrix, docs style checks, and full pytest.
17. Local file-based imports now fail closed during semantic analysis instead of swallowing module loading failures.
18. Zig unsupported expression fallbacks now fail as compiler-side codegen errors instead of generated `@compileError` expressions.
19. `fall` now fails closed with a semantic error instead of being ignored or reaching backend output.
20. C backend `for-in` lowering now caches array/slice iterable expressions so side-effectful iterables are evaluated once.
21. String literal tokenization now rejects unknown escapes and malformed `\xHH` escapes; valid escapes are decoded into AST literals and re-escaped for backend output.
22. Return type mismatches inside if branches, match branches, and nested blocks are covered by semantic regression tests.
23. Bool and enum match statements/expressions now report non-exhaustive coverage unless an else or wildcard branch is present.
24. `slice.ptr` and `slice.len` now type-check and lower in both Zig and C backends.
25. `string[start..end]` and `string[start..]` now type-check as `[]char` and lower in both Zig and C backends.

---

## Remaining Language-First Gaps

1. **`fall` statement lowering**
   - `fall` is parsed (`NodeKind.FALL`) and rejected during semantic validation.
   - Full fallthrough semantics and backend lowering are not implemented yet.

2. **Advanced match diagnostics**
   - No overlap/redundancy diagnostics for case patterns.
   - No unreachable-branch detection for wildcard-first or fully-covered prior patterns.

3. **Memory/lifetime model**
   - Current validation covers basic `del` reference checks.
   - Ownership/borrow-style lifetime guarantees are not implemented.

4. **Generic constraint internals**
   - Inline type-set constraint resolution in `src/generics.py` is still placeholder-level (`resolve_generic_constraint`).

5. **Backend semantic parity hardening**
   - Core conformance is green, but differential/backend-equivalence checks should be expanded and kept mandatory for new language features.

6. **Release publishing automation**
   - Local package builds and artifact checks exist.
   - Tag-triggered draft GitHub releases are configured.
   - PyPI/package-registry publishing is not configured yet.

7. **Module-system parity**
   - Missing or broken local imports now fail closed.
   - Built-in stdlib imports are still virtual and should be unified with file-based module semantics later.

---

## Out of Scope for This Snapshot

- Package ecosystem, registry/distribution workflows, and broader tooling are intentionally secondary to language-core correctness.
