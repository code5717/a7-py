# Status

## Current State

- Tokenizer, parser, semantic pipeline, AST preprocessing, and Zig/C code generation are implemented.
- Direct, mutual, and local function-pointer alias source recursion are semantic errors.
- Debug/release artifact verification is available for both backends.
- Example end-to-end verification is available for both Zig and C.
- Selected Zig/C backend parity verification is available, including contextual array literal assignment, defer unwinding, fallthrough, untagged unions, generic function specialization, enum match expressions, heap structs, and 2D/3D nested fixed arrays.
- Simple top-level generic function calls lower in the C backend through concrete specialization.
- Array literal assignment validates declared lengths and nested element types.
- Index and slice-bound variables must be `usize`; non-negative integer literals are accepted for simple indexing.
- Invalid ordering comparisons and unsafe signed-to-unsigned integer assignments are rejected during type checking.
- `fall` lowers in both native backends when it is the final direct statement of a non-final match case.

## Known Gaps

- Advanced match diagnostics still lack arbitrary symbolic inequality reasoning;
  shared-endpoint symbolic range overlaps and identifier captures are diagnosed.
- Ownership/borrow-style lifetime guarantees are not implemented.
- Heap fixed arrays (`new [N]T`) are rejected until their language and backend representation is defined.
- Full generic specialization is incomplete beyond simple top-level generic functions.
- Untagged union construction/access works; tagged/discriminated union tag workflows are not implemented yet.
- `std/string`, `std/mem`, and collections are planned but not current public stdlib modules.
- Package-registry publishing is not part of the current release workflow.

See [`MISSING_FEATURES.md`](https://github.com/code5717/a7-py/blob/master/MISSING_FEATURES.md) for the source-of-truth gap list.
