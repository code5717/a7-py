---
title: Builtins and keyword index
nav: Builtins
group: Reference
summary: Current intrinsics, reserved operations, and the complete keyword index.
order: 21
---

# Builtins and keyword index

`@type_set(...)` defines a compile-time type set used by [generic constraints](generics.md). `cast(Type, value)` is special compiler syntax for checked conversion. Neither spelling means arbitrary identifiers are callable intrinsics.

## Supported and reserved operations

| Spelling | Status | Qualification |
| --- | --- | --- |
| `@type_set(...)` | Limited | Works inline (`$T: @type_set(i32, i64)`) and as a file-scope alias used as a constraint |
| `cast(Type, value)` | Limited | Primitive conversion needs a safety proof |
| `@size_of`, `@align_of` | Unavailable | Reserved or parsed; not semantically resolved and backend-lowered |
| `@type_id`, `@type_name` | Unavailable | No current executable reflection interface |
| `@unreachable` | Unavailable | Reserved intrinsic spelling |
| `@likely`, `@unlikely` | Unavailable | No current branch-hint lowering |
| `tensor_*` | Planned | Specification design sketches, not registered runtime operations |

The [standard library](../stdlib.md) lists the registered `std/io` and `std/math` functions. Planned assertion, allocation, ASCII, string, and typed math helper names in the specification are not automatically callable.

## Keyword index

The following groups cover every entry in `Tokenizer.KEYWORDS`. They describe lexical reservation, with topic-specific runtime restrictions.

| Words | Reference and disposition |
| --- | --- |
| `and`, `or`, `not` | [Operators](operators.md), logical spellings; prefer example-backed forms |
| `as` | Reserved, broader cast-like use is unverified; use `cast` |
| `bool`, `char`, `string`, `f32`, `f64` | [Types](types.md), current documented types |
| `i8`, `i16`, `i32`, `i64`, `isize` | [Types](types.md), signed types |
| `u8`, `u16`, `u32`, `u64`, `usize` | [Types](types.md), unsigned types |
| `int`, `uint` | Unavailable public integer aliases |
| `float`, `let` | Reserved lexer words; not recommended executable public forms |
| `true`, `false`, `nil` | [Syntax](syntax.md), literals with type restrictions |
| `if`, `else`, `for`, `while`, `in` | [Control flow](control-flow.md), conditions and loops |
| `match`, `case`, `fall` | [Control flow](control-flow.md), matching and restricted fallthrough |
| `break`, `continue`, `ret` | [Control flow](control-flow.md), jumps |
| `fn` | [Functions](functions.md), declarations and function types |
| `struct`, `enum`, `union` | [Aggregates](aggregate-types.md), union restrictions apply |
| `new`, `del`, `defer`, `ref` | [Memory](memory.md), limited safety enforcement |
| `import`, `pub` | [Modules](modules.md), limited cross-file support |
| `where` | Reserved; use the current declared generic constraint form |

## Specification words that are not lexer keywords

`cast`, `const`, `self`, `size_of`, `type`, `using`, and `var` occur in the specification's keyword list but not in the tokenizer's keyword mapping. `cast` has dedicated parser handling; `self` can be a parameter name. The others do not establish public executable features. `number` is rejected as a public numeric type alias.

## Internal grammar and diagnostics

The specification's token enum, AST descriptions, and grammar summary document internal forms. They are not an independent list of supported language operations. The compiler reference describes actual command modes and diagnostics. Proposed error-code categories in the specification should not be mistaken for a promise that every emitted diagnostic has such a code.

## Status and restrictions

Status: limited. This page deliberately separates lexical recognition, semantic acceptance, and native lowering. The feature manifest records evidence links and qualifications; a source revision alone does not verify an operation.

## Evidence

- [a7/tokens.py](https://github.com/code5717/a7-py/blob/master/a7/tokens.py)
- [a7/parser.py](https://github.com/code5717/a7-py/blob/master/a7/parser.py)
- [docs/SPEC.md](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
