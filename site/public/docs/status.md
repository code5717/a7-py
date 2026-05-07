# Status

## Current State

- Tokenizer, parser, semantic pipeline, AST preprocessing, and Zig/C code generation are implemented.
- Direct and mutual source recursion are semantic errors.
- Debug/release artifact verification is available for both backends.
- Example end-to-end verification is available for both Zig and C.
- Selected Zig/C backend parity verification is available.

## Known Gaps

- `fall` is parsed but rejected until fallthrough semantics are designed.
- Advanced match diagnostics still have incomplete symbolic interval overlap handling.
- Ownership/borrow-style lifetime guarantees are not implemented.
- C backend generic function lowering is not implemented.
- Runtime union construction/access remains incomplete as a source-language workflow.
- Built-in stdlib imports are virtual and should later be unified with file-based module semantics.
- PyPI publishing requires final trusted-publisher setup before the first real release.

See [`MISSING_FEATURES.md`](https://github.com/code5717/a7-py/blob/master/MISSING_FEATURES.md) for the source-of-truth gap list.
