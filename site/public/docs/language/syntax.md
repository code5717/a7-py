---
title: Syntax and lexical structure
nav: Syntax
group: Reference
summary: Source files, comments, identifiers, literals, escapes, and punctuation.
order: 10
---

# Syntax and lexical structure

A7 source files use `.a7`. Use ASCII identifiers and spaces for indentation. Newlines or semicolons end statements. Tabs outside literals are rejected. The tokenizer strips a leading UTF-8 byte-order mark. The specification describes ASCII source; broader Unicode source behavior is not a supported portability guarantee.

## Comments and names

`//` and `#` begin line comments. `/* ... */` comments can nest. The current tokenizer accepts end-of-file as the end of an unclosed block comment, so do not rely on it to diagnose a missing `*/`.

Names are case-sensitive. Ordinary identifiers begin with an ASCII letter or underscore, followed by ASCII letters, digits, or underscores. The specification reserves leading underscores for compiler names. The lexer limits identifiers and numeric literal spellings to 100 characters.

```a7
// A line comment
/* Outer comment /* nested comment */ */
answer := 42
```

## Literals and escapes

| Kind | Spellings | Qualification |
| --- | --- | --- |
| Integer | `42`, `0x2A`, `0o52`, `0b101010`, `1_000` | The destination type must accommodate the value. |
| Float | `3.14`, `.5`, `1.`, `2.71e10` | Numeric conversion and range rules still apply. |
| Boolean | `true`, `false` | Type `bool`. |
| Character | `'a'`, `'\n'`, `'\x41'` | Public character model is ASCII. |
| String | `"hello"`, `"a\nb"` | String slicing produces a character slice. |
| Nil | `nil` | Reference types only, not arrays or other value types. |

Recognized escapes are `\n`, `\t`, `\r`, `\\`, `\'`, `\"`, `\0`, and `\xHH` with exactly two hexadecimal digits. Unknown string escapes are rejected. A literal escape `\t` is different from a tab used for indentation.

## Punctuation and reserved words

Parentheses group expressions and arguments. Braces contain blocks and aggregate initializers. Brackets express arrays, indexing, and slices. `:` introduces a type, `::` declares a constant, and `:=` declares an inferred variable. `.` selects a field or imported member. `..` separates slice bounds and appears in restricted variadic syntax. `$T` denotes a generic type parameter. `@` introduces type-set intrinsics or loop labels.

The [keyword index](builtins.md#keyword-index) lists the tokenizer's actual reserved words. Some specification spellings, including `cast`, are context-sensitive identifiers rather than lexer keywords. A token being recognized does not mean every use can run.

## Status and restrictions

Status: supported for the ordinary ASCII forms shown here. Unicode behavior beyond the documented ASCII model is unverified. Parser grammar and AST node lists describe compiler internals, not additional callable features. Numeric edge cases, diagnostics categories, and implementation limits must be read alongside current compiler evidence.

## Evidence

- [a7/tokens.py](https://github.com/code5717/a7-py/blob/master/a7/tokens.py)
- [a7/parser.py](https://github.com/code5717/a7-py/blob/master/a7/parser.py)
- [examples/003_comments.a7](https://github.com/code5717/a7-py/blob/master/examples/003_comments.a7)
- [examples/019_literals.a7](https://github.com/code5717/a7-py/blob/master/examples/019_literals.a7)
- [docs/SPEC.md](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
