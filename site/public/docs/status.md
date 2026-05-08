# Status

## Current State

- Tokenizer, parser, semantic pipeline, AST preprocessing, and Zig/C code generation are implemented.
- Direct and mutual source recursion are semantic errors.
- Debug/release artifact verification is available for both backends.
- Example end-to-end verification is available for both Zig and C.
- Selected Zig/C backend parity verification is available, including contextual array literal assignment, defer unwinding, untagged unions, generic function specialization, enum match expressions, heap structs, and 2D/3D nested fixed arrays.
- Simple top-level generic function calls lower in the C backend through concrete specialization.
- Array literal assignment validates declared lengths and nested element types.

## Known Gaps

- `fall` is parsed but rejected until fallthrough semantics are designed.
- Advanced match diagnostics still have incomplete symbolic interval overlap handling.
- Ownership/borrow-style lifetime guarantees are not implemented.
- Full generic specialization is incomplete beyond simple top-level generic functions.
- Untagged union construction/access works; tagged/discriminated union tag workflows are not implemented yet.
- `std/string`, `std/mem`, and collections are planned but not current public stdlib modules.
- Package-registry publishing is not part of the current release workflow.

See [`MISSING_FEATURES.md`](https://github.com/code5717/a7-py/blob/master/MISSING_FEATURES.md) for the source-of-truth gap list.
