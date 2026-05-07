# A7 Language Spec and Docs Review

Date: 2026-05-07
Last verified: 2026-05-07 (all source-code citations re-checked against the current tree; corrections and new findings appended)

Scope reviewed:

- `docs/SPEC.md`
- `README.md`
- `MISSING_FEATURES.md`
- `TODO.md`
- compiler source under `src/`
- current local verification commands
- official references for comparable language-design surfaces

## Executive Summary

A7 has a working compiler pipeline and a useful set of examples, but the public language story is ahead of the implementation in several places. The biggest problem is not one missing feature; it is that `docs/SPEC.md`, `README.md`, `TODO.md`, and the compiler source disagree about what is implemented, what is planned, and what the language actually guarantees.

The highest-risk areas are:

1. The specification file is structurally corrupted — sections 3 through 8 are duplicated wholesale between lines 1334 and 2143, the real `## 10. Modules and Visibility` heading is missing, and every numbered section after the duplication is off-by-one.
2. The docs claim backend and semantic completeness that the source does not support.
3. Memory safety promises are not backed by a real ownership, lifetime, aliasing, or nullable-reference model.
4. Array/tensor/AI features read like a separate numerical framework, but they are not implemented.
5. Imports, stdlib, visibility, generics, variadics, slices, multi-value declarations, and C backend parity all need decisions or fixes before the language can be presented as coherent.
6. A 9-step AST preprocessing stage (constant folding, struct-init normalization, function hoisting, sugar lowering) runs between semantic analysis and codegen but is invisible to the language spec.
7. The AGENTS.md Post-Change Checklist is not enforced — most of the drift in this review would be caught by it.

## Verification Snapshot

Commands run locally:

```bash
PYTHONPATH=. uv run pytest --tb=no -q
```

Result:

```text
1074 passed in 29.88s
```

Zig version:

```bash
zig version
```

Result:

```text
0.15.2
```

The Zig example verifier passed:

```bash
uv run python scripts/verify_examples_e2e.py
```

Result:

```text
Examples verified: 36/36
```

The C example verifier passed:

```bash
uv run python scripts/verify_examples_e2e_c.py
```

Result:

```text
Examples verified (C backend): 36/36
```

This means the current example suite verifies successfully on both backends, but it does not cover every spec feature claimed by the docs. The unsupported or partial features listed below are source- and docs-backed gaps, not failures of the existing example set.

## Critical Findings

### 1. `docs/SPEC.md` is structurally corrupted

The table of contents says section 10 is modules, section 11 is built-ins, section 12 is tokens/AST, and section 13 is grammar. But `## 10. Modules and Visibility` starts at `docs/SPEC.md:1334` and immediately repeats lexical structure from section 2. The actual module content does not appear until `docs/SPEC.md:2143`.

Evidence:

- `docs/SPEC.md:14-28` lists the intended table of contents.
- `docs/SPEC.md:1334-1375` starts "Modules and Visibility" but repeats source encoding, whitespace, comments, identifiers, and keywords.
- `docs/SPEC.md:2143-2217` finally contains the real module and visibility section.
- `docs/SPEC.md:2220` starts another `## 10. Built-in Functions and Operators`, creating duplicate numbering.

The corruption is wider than a single mis-numbered heading. Re-pasted second copies of every section from §3 through §8 sit between the misplaced "Modules and Visibility" header and the real module content:

- `docs/SPEC.md:1489` — duplicate `## 3. Type System`
- `docs/SPEC.md:1663` — duplicate `## 4. Declarations and Expressions`
- `docs/SPEC.md:1758` — duplicate `## 5. Control Flow`
- `docs/SPEC.md:1865` — duplicate `## 6. Functions`
- `docs/SPEC.md:1989` — duplicate `## 7. Generics`
- `docs/SPEC.md:2074` — duplicate `## 8. Memory Management`

Consequence: there is no real `## 10. Modules and Visibility` heading at all (the actual `### 10.1 File-Based Module System` at `docs/SPEC.md:2143` is a level-3 heading with no parent), and every numbered section after the duplication block is off-by-one — `## 10. Built-in Functions and Operators` at `:2220` should be §11, `## 11. Tokens and AST Components` at `:2315` should be §12, and `## 12. Grammar Summary` at `:2597` should be §13.

Impact:

The spec is not safe to treat as canonical. Any site page generated from it will inherit duplicate, stale, or misplaced language rules. Roughly 800 lines of duplicated content sit in the middle of the document.

Recommendation:

Rewrite `docs/SPEC.md` as a clean single-pass document. Use one status table per feature with these states: implemented, partial, planned, descoped.

### 2. Status claims are stale and conflict with current reality

`docs/SPEC.md` claims a complete language design and implemented C/Zig codegen. The README also says the parser is complete for the A7 spec and that the Zig backend handles all AST node types.

Evidence:

- `docs/SPEC.md:3-12` claims tokenizer, parser, semantic pipeline, Zig codegen, and C codegen are implemented.
- `docs/SPEC.md:2835-2839` says `1067 passed, 0 failed, 0 skipped`.
- Current local test run is `1024 passed, 50 skipped`.
- `README.md:100-106` says parser is 100% complete for the A7 specification, Zig backend handles all AST node types, and C backend is validated with `zig cc`.
- `TODO.md:20-34`, `TODO.md:44-63`, and `TODO.md:73-100` list major missing or partial features.
- `src/backends/c.py:1007-1008` raises `CodegenError("C backend: match expressions are not implemented")`.
- `src/backends/zig.py:1017-1018` can emit `@compileError("unsupported: ...")` instead of failing compiler-side.

Impact:

The docs overpromise. A newcomer will assume features are implemented because the README and spec say so, then hit unsupported or partial behavior.

Recommendation:

Make `TODO.md` and `MISSING_FEATURES.md` the source for implementation status, or merge that status into `docs/SPEC.md`. Remove absolute claims such as "parser is 100% complete" unless verified by a conformance suite.

### 3. Memory safety is promised but not specified enough to be sound

The spec promises no dangling pointers, no double-free, no use-after-free, and compiler-tracked lifetimes. The current docs also show nullable allocation checks with `new`.

Evidence:

- `docs/SPEC.md:930-936` shows `new` followed by `if large == nil`.
- `docs/SPEC.md:963-968` claims no dangling pointers, double-free protection, use-after-free protection, and debug bounds checks.
- `MISSING_FEATURES.md:36-38` says ownership/borrow-style lifetime guarantees are not implemented.
- `TODO.md:157-158` classifies memory/lifetime modeling as a big language-design research problem.

Source-level issue:

The language has `ref`, `.adr`, `.val`, `new`, `del`, and `nil`, but it does not define nullable vs non-null references, pointer provenance, aliasing, alignment, escape rules, lifetime regions, or what happens after `del` through aliases.

External comparison:

- The Rust Reference treats dangling or misaligned pointer access, invalid values, and aliasing rule violations as undefined behavior, and requires references/boxes to be aligned, non-null, non-dangling, and valid.
- The Zig language reference separates slices, pointers, and optional pointers, and says null pointers should be represented with optional pointers.

Impact:

Without a clear memory model, A7 cannot honestly claim compile-time memory safety. The same source may be safe in one backend and undefined or invalid in another.

Recommendation:

Decide one of these:

- Make `ref T` always non-null and introduce `?ref T` or `T | nil` for nullable references.
- Treat references as unchecked C-like pointers and remove "compiler tracks lifetimes" claims.
- Design an ownership/borrow model and implement escape/lifetime/alias analysis.

### 4. Tensor and AI sections are far beyond the implemented language

The spec contains a large numerical-computing and AI subsystem: tensors, broadcasting, vectorized ops, reshaping, reductions, linear algebra, neural-network primitives, autograd, GPU transfers, and performance annotations.

Evidence:

- `docs/SPEC.md:36-45` lists array programming for AI and multidimensional tensors as language features.
- `docs/SPEC.md:1041-1266` specifies broadcasting, vectorized operations, reshaping, linalg, autograd, neural-network ops, GPU/device functions, and advanced indexing.
- `TODO.md:144-161` says tensors, AI-specific operations, GPU support, and performance annotations are big bets and not started.

External comparison:

- NumPy broadcasting has explicit compatibility rules over trailing dimensions and defined shape-result behavior.
- NumPy indexing distinguishes basic slicing views from advanced-indexing copies, includes boolean/integer indexing rules, and documents shape, bounds, and layout consequences.

Impact:

This is not a small stdlib feature. It requires a tensor type model, dtype promotion, memory layout rules, broadcasting rules, view/copy semantics, shape errors, runtime support, and likely BLAS/LAPACK or GPU bindings.

Recommendation:

Move the whole tensor/AI section out of the core language spec into `docs/FUTURE_TENSORS.md`, or rewrite it as a non-implemented proposal. Keep only arrays and slices in the current core spec.

## Major Findings

### 5. `defer` is parsed one way and checked another way

The parser stores deferred work in `statement`, but both semantic passes read `expression`.

Evidence:

- `src/parser.py:2255-2264` creates `NodeKind.DEFER` with `statement=statement`.
- `src/passes/semantic_validator.py:257-267` checks `node.expression`.
- `src/passes/type_checker.py:658-660` checks `nd.expression`.
- `TODO.md:12-14` already calls this out.

Impact:

Deferred calls and deferred `del` statements can skip validation. This weakens one of the language's main resource-management features.

Recommendation:

Normalize the AST schema: either `defer statement` everywhere, or lower deferred calls/deletes into a canonical deferred expression node before semantic analysis.

### 6. `ret` payload validation has the same schema risk in semantic validation

The parser stores return payloads in `value`, and the type checker correctly reads `value`, but the semantic validator reads `expression`.

Evidence:

- `src/parser.py:953-959` calls `create_return_stmt(value, ...)`.
- `src/ast_nodes.py:389-391` stores `value=value`.
- `src/passes/type_checker.py:854-859` correctly reads `node.value`.
- `src/passes/semantic_validator.py:244-255` reads `node.expression`.
- `TODO.md:16-18` lists this as open.

Impact:

Semantic-only checks can miss invalid constructs inside return payload expressions.

Recommendation:

Change semantic validation to traverse `node.value` and add a regression test that uses a semantically invalid expression inside `ret`.

### 7. `fall` exists syntactically but has no complete semantics

Evidence:

- `src/parser.py:981-986` parses `fall` into `NodeKind.FALL`.
- `TODO.md:20-22` says semantic validation and backend lowering are pending.
- `MISSING_FEATURES.md:29-30` says the same.
- `docs/SPEC.md:538` and `docs/SPEC.md:1791` mention that full behavior is still being finalized.

Impact:

`fall` should not be advertised as a usable control-flow feature until the language defines where it is legal, what it can fall into, and how it interacts with variable scopes and defers.

Recommendation:

Either implement it end-to-end or make parsing it a hard semantic error with a clear "not implemented" diagnostic.

### 8. Slice and string behavior conflicts with the spec

The spec documents array `.len`, slice `.ptr`, slice `.len`, and string slicing. The type checker does not implement all of that.

Evidence:

- `docs/SPEC.md:254-266` documents array and slice properties.
- `docs/SPEC.md:583` shows `for char in string[2..5]`.
- `src/passes/type_checker.py:1230-1250` allows slice expressions only on arrays and slices, not strings.
- `src/passes/type_checker.py:1252-1296` field access supports structs, enums, and module symbols, but not `slice.ptr` or `slice.len`.
- `TODO.md:44-50` lists both as missing.

Impact:

Code copied from the spec will not type-check.

Recommendation:

Implement these exactly as source-language properties, or remove them from the current spec and keep them as future work.

### 9. Generics are partially implemented but underspecified

Generic syntax, constraints, and specialization are spread across parser/type checker/generics helper code, but the implementation is incomplete.

Evidence:

- `docs/SPEC.md:856-871` defines `@type_set`.
- `docs/SPEC.md:1246-1253` uses tensor signatures with generic constraints.
- `src/generics.py:246-251` only substitutes bare generic parameters, not nested generic types.
- `src/generics.py:285-311` returns `None` for inline type-set constraints.
- `TODO.md:52-54` says constraint resolution is still a stub.
- `TODO.md:99-100` says generic specialization is spec'd but not implemented.

Impact:

Simple generics can work, but the spec reads like a more powerful generic system than the compiler currently enforces.

Recommendation:

Define the MVP generic model:

- exact declaration syntax,
- whether generic params are inferred or explicit,
- allowed constraints,
- monomorphization timing,
- type identity for generic instances,
- recursive substitution for arrays/slices/refs/functions.

Then remove examples that require unsupported specialization or constraint solving.

### 10. Variadic functions are inconsistent

`TODO.md` says variadics are not parsed or implemented, but parser and type structures include variadic support. The type checker still does not fully validate extra arguments against the variadic element type.

Evidence:

- `docs/SPEC.md:754-763` documents typed and untyped variadics.
- `src/parser.py:704-725` parses variadic parameters.
- `src/types.py:222-223` models `is_variadic` and `variadic_type`.
- `src/passes/type_checker.py:1083-1097` checks argument counts and then only zips actual args with declared param slots.
- `TODO.md:93-95` still says variadics are spec'd but not parsed or implemented.

Impact:

The backlog itself is stale, and the implementation may accept or skip-check cases it should reject.

Recommendation:

Update the backlog to "partial", then add tests for:

- too few fixed arguments,
- many extra typed variadic arguments,
- wrong typed variadic argument,
- untyped variadic arguments,
- backend emission in Zig and C.

### 11. Imports and stdlib need one coherent model

The spec describes file-based modules and stdlib files. The implementation also has a virtual stdlib registry. These two models are not reconciled.

Evidence:

- `docs/SPEC.md:2172-2195` documents several import forms.
- `docs/SPEC.md:2197-2204` says stdlib files include `math.a7`, `io.a7`, `string.a7`, `memory.a7`, and `collections.a7`.
- `src/module_resolver.py:57-81` resolves imports to `.a7` files or `mod.a7`.
- `src/stdlib/__init__.py:37-42` registers only `io` and `math`.
- `src/stdlib/string.py:8-15` and `src/stdlib/mem.py:8-13` are stubs and are not auto-registered.
- `src/compile.py:236-239` swallows module resolution failures.
- `TODO.md:73-89` lists the import/stdlib reconciliation as open.

External comparison:

- The Go specification defines package source organization, import declarations, exported identifiers, import dependency relations, and import-cycle illegality.

Impact:

Users cannot know whether `io :: import "io"` is a real file import, a virtual builtin, or both. Broken imports may also be under-reported.

Recommendation:

Choose one model:

- virtual builtin modules only,
- file-based stdlib modules only,
- or virtual modules that behave exactly like loaded modules.

Then make unresolved imports fatal in semantic modes.

### 12. Visibility rules contradict examples and parser behavior

The spec example marks struct fields with `pub`, while the visibility rules say struct fields cannot be public. The parser accepts `pub` on fields.

Evidence:

- `docs/SPEC.md:2151-2156` shows `pub Vec3 :: struct { pub x: f32 ... }`.
- `docs/SPEC.md:2208-2216` says `public` only applies to top-level declarations and struct fields cannot be public.
- `src/parser.py:1998-2012` parses `pub` on struct fields.

Impact:

The language cannot simultaneously forbid and demonstrate public struct fields.

Recommendation:

Decide whether field visibility exists. If yes, document field-level visibility. If no, remove parser support and fix the examples.

### 13. C backend semantic parity is not real yet

The C backend is useful, but the docs overstate parity.

Evidence:

- `src/backends/c.py:1007-1008` rejects match expressions.
- `TODO.md:59-71` lists missing C backend match expressions, range patterns, identifier-capture patterns, and function-typed declarations.
- `README.md:105-106` says Zig handles all AST node types and C is validated with `zig cc`.
- Current C example verifier passes `36/36`, but that does not cover the documented missing C backend surfaces.

Impact:

"A7 -> Zig and A7 -> C backends" is accurate as a broad project goal, but "validated" and parity claims are not accurate for the current local state.

Recommendation:

Document C backend as partial until every spec-supported frontend feature either lowers to C or fails before codegen with a language diagnostic.

### 14. Numeric semantics are underdefined

The spec lists primitive integer/float types and operators, but it does not clearly define:

- signed overflow,
- unsigned overflow,
- division by zero,
- modulo sign,
- shift bounds,
- narrowing casts,
- float NaN/Inf comparisons,
- literal inference,
- target-dependent `isize`/`usize` behavior,
- endian/ABI layout for structs/unions.

Evidence:

- `docs/SPEC.md:240-244` defines `isize` and `usize` sizes.
- `docs/SPEC.md:108-132` lists operators.
- No matching section defines overflow, cast, shift, or ABI semantics.

Impact:

Since A7 lowers to both Zig and C, unspecified numeric behavior can diverge by backend or optimization level.

Recommendation:

Add a "Core Semantics" chapter before codegen claims. Explicitly choose trap, wrap, saturate, checked, or undefined behavior for every numeric edge case.

### 15. ASCII-only source and strings may be too restrictive

The spec requires ASCII source, ASCII identifiers, and ASCII strings. That may be intentional, but it has real consequences.

Evidence:

- `docs/SPEC.md:61-66` says source files must be ASCII and tabs are compilation errors.
- `docs/SPEC.md:81-93` restricts identifiers to ASCII.
- `docs/SPEC.md:269-275` defines string as ASCII.

Impact:

This blocks Unicode user text in string literals unless all non-ASCII data is represented manually through escapes or bytes. It also makes docs/examples less friendly for real-world paths, names, messages, and international projects.

Recommendation:

If ASCII-only is intentional, say whether `string` is a byte string and how UTF-8 bytes are represented. If not, use UTF-8 source and keep identifiers ASCII-only as a separate rule.

### 16. AST preprocessing pass is invisible to the language spec

A 9-step AST rewrite stage runs after semantic analysis and before code generation, but `docs/SPEC.md` never describes it. Some of those steps change observable behavior, not just internal representation, so the spec is missing a stage that affects what the program means.

Evidence:

- `src/ast_preprocessor.py:1-18` documents the nine sub-passes: lower `.adr`/`.val` sugar to `ADDRESS_OF`/`DEREF`, resolve stdlib calls, normalize struct inits, mutation analysis, usage analysis, type-annotation inference, variable-shadowing resolution, nested-function hoisting, and constant folding.
- `src/compile.py:22` imports `ASTPreprocessor`.
- `src/compile.py:315-320` runs `preprocessor.process(ast)` between semantic passes and codegen.
- `README.md:7` calls out "AST preprocessing" as a pipeline stage.
- `docs/SPEC.md:2837` mentions "AST preprocessing" once in passing.
- The body of `docs/SPEC.md` (sections 1-13 and Appendices A-E) never defines what the preprocessor does, what it is allowed to rewrite, or what guarantees survive it.

Impact:

Constant folding and nested-function hoisting are observable. A user reading the spec cannot predict whether `1 + 2` is folded before codegen, whether nested functions can capture, or whether a struct literal is normalized to positional or named fields. Users debugging codegen output will see transformed AST that does not match the source-level rules in the spec.

Recommendation:

Add a "Compilation Pipeline" section to `docs/SPEC.md` that names every pass (tokenize, parse, name resolution, type check, semantic validation, AST preprocessing, codegen), and for each preprocessing sub-pass state which language guarantees it preserves and which sugar it lowers. If any sub-pass is internal-only, say so explicitly.

### 17. Multiple declarations and multi-value assignment are spec'd but not parsed

The same shape of bug as variadics: the spec shows the syntax, the backlog admits it isn't implemented, and the cited line range matches.

Evidence:

- `docs/SPEC.md:400-405` shows `a, b, c: i32 = 1, 2, 3` and `x, y := 10, 20` under `### 4.1` "Variable Declarations".
- `docs/SPEC.md:1681` repeats the same example in the duplicated §4 block (see Critical Finding 1).
- `TODO.md:96-97` lists "Multiple return values / destructuring (`a, b, c := 1, 2, 3`). Notes: spec'd in §4.1, not parsed."
- A grep across `src/parser.py`, `src/ast_nodes.py`, and `src/types.py` for `destructur`, `multiple return`, or `tuple_assign` returns no hits.

Impact:

Code copied from `### 4.1` will not parse. A user cannot return more than one value from a function despite the spec implying it.

Recommendation:

Either implement parser support and lower it (most likely as an anonymous tuple plus pattern destructure), or remove the multi-value examples from `### 4.1` and the spec's introductory tour, and mark it explicitly as "future work" inline.

### 18. Process drift: AGENTS.md mandates a Post-Change Checklist that is clearly not enforced

`AGENTS.md` requires every major change to update CHANGELOG, README, SPEC, MISSING_FEATURES, and TODO together. The drift documented across this review (stale test counts, stale "spec'd but not parsed" backlog items where the parser already supports them, duplicated SPEC sections, status overclaims) is direct evidence that this checklist is not being applied.

Evidence:

- `AGENTS.md` "Post-Change Checklist" lists CHANGELOG.md, README.md, docs/SPEC.md, MISSING_FEATURES.md, TODO.md as required updates.
- `TODO.md:93-94` says variadics are "spec'd but not parsed or implemented", but `src/parser.py:704-727`, `src/types.py:222-223`, and `src/passes/type_checker.py:1083-1097` all already implement them — confirmed by live compilation of `sum :: fn(values: ..i32) i32 { ret 0 }` through Zig codegen.
- `docs/SPEC.md:2839` reports `1067 passed, 0 failed, 0 skipped`; current count is `1074 passed`.
- The duplication described in Critical Finding 1 has survived multiple rounds of changes that should have triggered the spec update step.

Impact:

The checklist exists but is invisible. Future contributors cannot rely on the docs to reflect the implementation, which is the same root cause as Critical Findings 1 and 2.

Recommendation:

Either enforce the checklist with a CI step (e.g., a script that diffs the test count in `docs/SPEC.md` against the actual `pytest` output and fails when they disagree, or a check that fails when `docs/SPEC.md` contains repeated `## ` headings), or move spec/status into one canonical generated source so it cannot drift.

## Verification Audit Trail (added 2026-05-07)

Every numbered citation in this review was re-verified against the current tree using a combination of direct file reads and four parallel sub-agents (one for `defer`/`ret`/`fall`, one for slice/generics/variadics, one for imports/visibility/C-backend/memory/ASCII, one for tensor/AI), plus an independent live-compilation re-verification of the variadics finding.

- All 16 cited TODO.md ranges and both MISSING_FEATURES.md ranges land on exactly the content quoted. No off-by-one errors.
- `README.md:100-106` is the broader `## Project Status` block; the three specific bullets actually live at `README.md:104-106`. Cosmetic.
- The duplication described in Critical Finding 1 understates the problem — see the strengthened evidence in that section. Sections 3-8 are also duplicated.
- The Major Finding 10 verdict ("backlog stale, parser/types/checker partial") is confirmed: variadics compile end-to-end today.
- The Critical Finding 4 surface area is correct: `docs/SPEC.md:1041-1266` contains §9.2-§9.9 covering vectorized ops, reshape, reductions, linalg (SVD/QR/LU/eigen), conv2d/pooling/autograd, `@vectorize`/`@parallel`/`@prefetch`, advanced indexing, and `tensor_to_gpu` — none of which are implemented.

## External Research Notes

Official references used:

- Zig language reference: https://ziglang.org/documentation/master/
- Rust Reference, behavior considered undefined: https://doc.rust-lang.org/reference/behavior-considered-undefined.html
- Go language specification: https://go.dev/ref/spec
- NumPy broadcasting: https://numpy.org/doc/stable/user/basics.broadcasting.html
- NumPy indexing: https://numpy.org/doc/stable/user/basics.indexing.html

Relevant takeaways:

- Zig distinguishes arrays, slices, pointers, and optional pointers. Slices have pointer-plus-length behavior and a `.len` property. Nullability is explicit through optional pointers.
- Rust's memory model shows why "no dangling pointers" and "no use-after-free" are not just syntax features. The language must define alignment, validity, liveness, aliasing, and FFI behavior.
- Go's package spec shows that imports need precise rules for file organization, exported identifiers, dependency relations, import cycles, and initialization.
- NumPy's tensor behavior is large because broadcasting, indexing, views/copies, shape inference, and out-of-bounds behavior all need explicit semantics. A7's current tensor section lacks this level of precision and has no implementation.

## Recommended Cleanup Order

1. Fix docs truth first: rewrite `docs/SPEC.md` status and remove duplicated/corrupted sections.
2. Split current language from future proposals: move tensors/AI/GPU/performance annotations out of the core spec.
3. Fix AST schema mismatches: `defer` and `ret` semantic traversal.
4. Make unsupported syntax fail early: `fall`, unsupported C match expressions, unsupported generic specialization, and unsupported tensor syntax should not drift into backend errors.
5. Decide the memory model: nullable vs non-null refs, aliasing, ownership, lifetime/escape rules, and post-`del` behavior.
6. Decide imports/stdlib: virtual registry vs file modules, with fatal unresolved imports.
7. Define numeric semantics and backend parity rules.
8. Document the AST preprocessing pipeline (Finding 16) so users know what is rewritten between source and codegen.
9. Reconcile multi-value declaration syntax (Finding 17) — either parse it or remove it from §4.1.
10. Wire the AGENTS.md Post-Change Checklist into CI (Finding 18) so doc/code drift fails the build instead of waiting to be caught by review.
11. Add a conformance matrix that maps every spec feature to tokenizer, parser, type checker, semantic validator, Zig backend, C backend, examples, and tests.
