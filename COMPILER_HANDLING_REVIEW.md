# Parser, Optimization, and Error Handling Review

Date: 2026-05-07

Scope reviewed:

- `a7/parser.py`
- `a7/ast_preprocessor.py`
- `a7/passes/type_checker.py`
- `a7/passes/semantic_validator.py`
- `a7/errors.py`
- `scripts/verify_error_stages.py`
- parser, semantic, preprocessor, and error-stage tests under `test/`

## Summary

The compiler has broad parser and semantic coverage, an iterative AST preprocessor, and a useful CLI error-stage matrix. The highest-value fixes in this pass were not new syntax; they were making existing AST contracts and diagnostics reliable:

- `defer` payloads are parsed as `statement`, so type checking and semantic validation now traverse `statement`.
- `ret` payloads are parsed as `value`, so semantic validation now traverses `value`.
- `for-in` now rejects scalar/non-iterable expressions during type checking.
- constant folding now covers literal comparisons and integer bitwise expressions.
- semantic error messages now cover several enum values that previously fell back to "Unknown semantic error".
- pytest and the standalone error-stage verifier now include deferred-statement semantic failures.

## External References Used

- ANTLR `DefaultErrorStrategy`: https://www.antlr.org/api/Java/org/antlr/v4/runtime/DefaultErrorStrategy.html
- GCC diagnostic guidelines: https://gcc.gnu.org/onlinedocs/gccint/Guidelines-for-Diagnostics.html
- Rust compiler diagnostics guide: https://rustc-dev-guide.rust-lang.org/diagnostics.html
- LLVM optimization passes: https://llvm.org/docs/Passes.html
- LLVM Kaleidoscope optimizer tutorial: https://llvm.org/docs/tutorial/MyFirstLanguageFrontend/LangImpl04.html

Takeaways applied here:

- Parser/error recovery should have explicit synchronization points and tested stage contracts, not just thrown exceptions.
- Diagnostics should describe the user's source-language problem, not internal enum fallbacks or backend implementation details.
- Optimizations should be staged and testable as transforms. Constant folding is useful, but it should avoid target-semantics traps such as division by zero or invalid shifts.

## Implemented In This Pass

### Parser/semantic AST contract fixes

The parser creates:

- `RETURN.value`
- `DEFER.statement`

The semantic passes were still looking at `expression` in places. That let deferred statements skip checks, and it left semantic return-payload traversal dependent on the wrong field.

Changed:

- `a7/passes/type_checker.py`
- `a7/passes/semantic_validator.py`

Added coverage:

- `test/test_semantic_control_flow.py`
- `test/test_error_stage_matrix.py`
- `scripts/verify_error_stages.py`

### Iterable validation

`for x in 42 {}` no longer falls through with `UNKNOWN`. It now emits a type diagnostic unless the iterable is an array, slice, string, or already-unknown because of an earlier error.

Changed:

- `a7/passes/type_checker.py`

Added coverage:

- plain `for-in` scalar rejection
- indexed `for-in` scalar rejection

### Optimization handling

The AST preprocessor already folded arithmetic and boolean logic. It now also folds:

- numeric comparisons: `<`, `<=`, `>`, `>=`, `==`, `!=`
- same-literal-kind equality/inequality
- integer bitwise `&`, `|`, `^`, `<<`, `>>`

It deliberately does not fold:

- division or modulo by zero
- negative shifts
- expressions involving identifiers

Changed:

- `a7/ast_preprocessor.py`

Added coverage:

- numeric comparison folding
- string equality folding
- integer bitwise folding
- invalid negative-shift non-folding

### Error handling

Several `SemanticErrorType` values existed but had no concrete message/advice mapping, so real user-facing errors could display as "Unknown semantic error". The mappings now cover scope labels, defer-outside-function, immutable assignment, delete-non-reference, and nil/reference misuse.

Changed:

- `a7/errors.py`

Added coverage:

- deferred delete of non-reference through human and JSON CLI output paths
- standalone verifier scenario for the same failure

## Remaining Important Gaps

### Parser handling

- No broad parser recovery/synchronization policy is documented. The parser has many targeted edge-case tests, but it still needs a clear policy for when to fail fast versus recover and continue collecting diagnostics.
- `fall` parses but is still not semantically lowered.
- Destructuring/multiple-return syntax is still documented but not parsed.
- Parser and spec still need a conformance matrix so every grammar production maps to tokenizer, parser, semantic, backend, and tests.

### Optimization handling

- Constant propagation is still missing.
- Dead-code elimination is still missing.
- Strength reduction, inlining, and loop-invariant code motion remain future work.
- Numeric constant folding still depends on currently underspecified language semantics for overflow, shifts, and signed division behavior. More folding should wait until the language spec defines those rules.

### Error handling

- Local file-based import loading now fails closed during semantic analysis; virtual stdlib imports still need a unified design with file-based modules.
- C backend unsupported features should fail earlier with source-language diagnostics instead of surfacing as backend limitations.
- The pytest matrix and standalone verifier still duplicate scenario logic; they are aligned now, but should share fixtures or a manifest.
- Existing success tests prove examples pass, but they are not a full negative conformance suite for every parser and semantic branch.

## Recommended Next Tester Expansion

1. Add a manifest-driven conformance matrix for parser productions and expected compiler stages.
2. Add negative parser-recovery cases for malformed declarations, generics, match cases, imports, and nested blocks.
3. Add semantic tests for `fall`, slice fields, string slicing, and import failures once the intended behavior is decided.
4. Add optimizer tests for constant propagation and dead-code elimination before implementing those passes.
5. Add backend parity tests where the same source must either succeed on both Zig/C or fail before backend selection.
