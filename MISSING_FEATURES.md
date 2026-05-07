# A7 Compiler — Language-Core Gap Snapshot

**Compiler Status**: Full pipeline runs (Tokenizer -> Parser -> Semantic -> Preprocessor -> Codegen).  
**Current Test Status**: check with `PYTHONPATH=. uv run pytest --tb=no -q`.  
**Examples**: 36/36 pass end-to-end compile + build + run + output verification.

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

---

## Remaining Language-First Gaps

1. **`fall` statement semantics**
   - `fall` is parsed (`NodeKind.FALL`) but not yet validated or lowered in semantic/codegen passes.

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

---

## Out of Scope for This Snapshot

- Package ecosystem, registry/distribution workflows, and broader tooling are intentionally secondary to language-core correctness.
