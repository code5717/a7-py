---
title: Declarations and scope
nav: Declarations
group: Reference
summary: Mutable variables, constants, initialization, aliases, and scope.
order: 11
---

# Declarations and scope

Use `::` for constants, `:=` for inferred mutable variables, and `name: Type = value` for explicitly typed mutable variables. A typed declaration without an initializer is also a variable declaration.

```a7
limit :: 10
count := 0
index: usize = 0
buffer: [4]u8
count = count + 1
```

## Initialization and assignment

Constants cannot be reassigned. Variables support `=` and the compound assignments listed in [operators](operators.md). Fixed arrays can be zero-initialized or initialized with an exactly sized
literal. Scalar-fill initialization is currently rejected; use a literal or
a loop to fill the elements. Do not infer a general definite-initialization or ownership guarantee from array initialization behavior.

The specification contains contradictory comments that call `x: i32 = 42` immutable. `Parser.parse_declaration` creates a variable declaration for that spelling. Use `::` when immutability is required. This documentation follows that implementation evidence; it does not change the language.

## Scope and shadowing

Blocks create nested scopes. Name lookup searches the current scope, enclosing scopes, file scope, imports, then builtins. Inner bindings can shadow outer bindings. Redeclaring a name in the same scope is a separate error. A shadowed module alias is no longer a route to that module in the inner scope.

Function value parameters are immutable. Create a local `:=` copy to update a value. `ref` parameters can modify caller storage under the [reference rules](memory.md).

## Aliases and visibility

```a7
Handle :: u64
Vector :: [3]f32
```

Aliases name an existing type. They do not establish a separately owned resource or promise a distinct runtime representation.

`pub` marks a top-level function, binding, or type for export. Local bindings, parameters, and individual struct fields cannot be marked `pub`. Cross-file behavior is qualified by the current [module restrictions](modules.md).

## Status and restrictions

Status: supported for ordinary bindings and local shadowing. Multiple declarations, tuple returns, and destructuring are unavailable in the runnable backend. Do not use `var` or `const` as declaration keywords. A7 uses the declaration operators above.

## Evidence

- [a7/parser.py](https://github.com/code5717/a7-py/blob/master/a7/parser.py)
- [a7/passes/semantic_validator.py](https://github.com/code5717/a7-py/blob/master/a7/passes/semantic_validator.py)
- [test/test_semantic_analysis.py](https://github.com/code5717/a7-py/blob/master/test/test_semantic_analysis.py)
- [test/test_module_alias_shadowing.py](https://github.com/code5717/a7-py/blob/master/test/test_module_alias_shadowing.py)
- [examples/002_var.a7](https://github.com/code5717/a7-py/blob/master/examples/002_var.a7)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
