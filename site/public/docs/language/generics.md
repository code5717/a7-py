---
title: Generics and type sets
nav: Generics
group: Reference
summary: Type parameters, concrete specialization, type sets, and current limits.
order: 18
---

# Generics and type sets

Generic type parameters use `$T`. Concrete call arguments can infer a function's type parameters. The current examples use explicit generic declaration lists together with inline parameter types.

```a7
identity($T) :: fn(value: $T) $T {
    ret value
}
```

Calls `identity(7)` and `identity("ok")` select concrete specializations. The full repository example also instantiates nested generic structs.

## Generic structs

```a7
Box :: struct {
    value: $T
}
Pair($A, $B) :: struct {
    first: $A
    second: $B
}
```

Instantiate with concrete types, for example `Box(i32){value: 7}` or `Pair(i32, string){first: 7, second: "ok"}`. Type arguments describe the resulting field types. They do not turn generic containers into an implemented standard collection library.

## Type sets and constraints

`@type_set(i8, i16, i32)` describes allowed types. The semantic layer recognizes predefined sets including `Numeric`, `Integer`, `Float`, `Signed`, and `Unsigned`, and local type-set aliases.

A top-level local alias such as `IntOnly :: @type_set(i32, i64)` passes
semantic checking but currently fails Zig code generation with an unsupported
`TYPE_SET` node. Semantic recognition alone does not make that alias runnable.

The documented current constraint shape is `name($T: Numeric) :: fn(value: $T) $T { ... }`. Inferred call arguments are checked against declared constraints. `where` is a reserved spelling, but broad specification examples using `where` are not a substitute for the example-backed current form.

A predefined constraint works without a local alias. This complete program
prints `42`:

```a7
io :: import "std/io"
identity($T: Numeric) :: fn(value: $T) $T {
    ret value
}
main :: fn() { io.println("{}", identity(42)) }
```

The inline constraint `$T: @type_set(i32, i64)` also works in this direct-call
example. A top-level `@type_set` alias remains a separate codegen limitation.

## Status and restrictions

Status: limited. Concrete function and struct examples are implemented. Composite specialization, deeper call-chain propagation, and cross-module generic workflows remain incomplete. Generic enums and unions appearing in the specification do not establish runnable `Option` or `Result` implementations.

The specification says generic names exclude digits, while the tokenizer accepts digits after the initial letter and delegates further validity to parsing. Use conservative letter-only names such as `$T` or `$ELEMENT` until that discrepancy is resolved. Tokenizer acceptance alone is not execution evidence.

Some specification examples mix separate `$T` parameters and plain `T` references. Prefer the consistent spellings in the repository's generic example. This documentation does not authorize a syntax change.

## Evidence

- [examples/014_generics.a7](https://github.com/code5717/a7-py/blob/master/examples/014_generics.a7)
- [a7/generics.py](https://github.com/code5717/a7-py/blob/master/a7/generics.py)
- [test/test_semantic_generics.py](https://github.com/code5717/a7-py/blob/master/test/test_semantic_generics.py)
- [a7/tokens.py](https://github.com/code5717/a7-py/blob/master/a7/tokens.py)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
