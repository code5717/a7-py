---
title: Language
nav: Language
group: Reference
summary: Syntax, implementation qualifications, and evidence for the A7 language.
order: 10
---

# Language

Start with the [tour](/a7-py/docs/tour.md) for a guided introduction. Use the
reference topics below for syntax, restrictions, and implementation evidence.
The [specification](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md)
contains the broader language design. It also contains proposals and examples
that the current compiler cannot execute.

## Reference topics

| Topic | What it covers |
| --- | --- |
| [Syntax](/a7-py/docs/language/syntax.md) | Comments, names, keywords, literals, and punctuation |
| [Declarations](/a7-py/docs/language/declarations.md) | Bindings, initialization, scope, and visibility |
| [Types](/a7-py/docs/language/types.md) | Numeric types, inference, conversions, and nil |
| [Operators](/a7-py/docs/language/operators.md) | Arithmetic, logic, precedence, and evaluation |
| [Control flow](/a7-py/docs/language/control-flow.md) | Conditions, loops, labels, matching, and jumps |
| [Functions](/a7-py/docs/language/functions.md) | Parameters, returns, callbacks, and recursion restrictions |
| [Arrays and strings](/a7-py/docs/language/arrays-strings.md) | Storage, slices, indexing, bounds, and text |
| [Aggregate types](/a7-py/docs/language/aggregate-types.md) | Structs, enums, unions, and fields |
| [Generics](/a7-py/docs/language/generics.md) | Type parameters, inference, constraints, and limits |
| [Memory](/a7-py/docs/language/memory.md) | Values, references, allocation, deletion, and safety |
| [Modules](/a7-py/docs/language/modules.md) | Imports, aliases, file modules, and visibility |
| [Builtins](/a7-py/docs/language/builtins.md) | Intrinsics, keyword index, and unavailable operations |

## Reading support labels

- **Supported** means the stated form has implementation and executable evidence.
- **Limited** means a form works with explicit restrictions or known gaps.
- **Unavailable** means the current implementation rejects or cannot execute it.
- **Planned** means it is a design intention without a supported current path.
- **Unverified** means evidence does not establish executable behavior.

A label applies to its stated form, not to every program involving the feature.
The [manifest](/a7-py/docs/manifest.json) records qualifications and evidence.
The [coverage matrix](https://github.com/code5717/a7-py/blob/master/site/docs/coverage.md)
maps the specification and implementation inventory to these topics.

## Program shape

Top-level bindings and functions use `::`. Functions use `fn`, explicit
`ret`, and typed parameters.

```a7
io :: import "std/io"

greet :: fn(name: string) {
    io.println("Hello, {}!", name)
}

main :: fn() {
    greet("A7")
}
```

## Declarations

- Top-level constants and functions: `name :: value`
- Mutable locals with inference: `count := 0`
- Explicit type: `count: i32 = 0`

## Float remainder

Float `%` uses a quotient truncated toward zero and retains the dividend's sign.
`-5.5 % 2.0` is `-1.5` in constant expressions and at runtime. The compiler still
requires a nonzero divisor.

## Control flow

Use `if`, `while`, `for`, `break`, `continue`, and `match`. A7 source
recursion is rejected at compile time. Rewrite recursive algorithms with loops,
index worklists, or explicit stacks.

```a7
sum_to :: fn(n: usize) usize {
    total: usize = 0
    i: usize = 0
    while i <= n {
        total = total + i
        i = i + 1
    }
    ret total
}
```

Indexed iteration:

```a7
for index, value in items {
    // index is usize
}
```

## Types

Examples and docs may use:

- Integers and floats
- `bool`, `char`, strings
- Fixed arrays and slices
- Structs, enums, and untagged unions
- References with nil checks
- Simple generic functions and structs

Reserved or incomplete areas belong in [Status](/a7-py/docs/status.md), not in
examples that pretend they are complete.

## Imports

Standard library imports use virtual module paths:

```a7
io :: import "std/io"
math :: import "std/math"
```

Local file imports produce combined single-file Zig output. Cross-module typing
and generic specialization have restrictions. See [modules](/a7-py/docs/language/modules.md).

## Hard rules

- A7 source recursion is rejected. Use loops, index worklists, or explicit
  stacks.
- Use `usize` for sizes, lengths, capacities, and indexes.
- Reserve `isize` for signed pointer-sized offsets and position differences.
- `new [N]T` is rejected. Use stack arrays or slices.
- Public reference syntax does not expose address-of or dereference operators.
  Pass lvalues directly to `ref` parameters.
