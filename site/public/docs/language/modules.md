---
title: Modules and visibility
nav: Modules
group: Reference
summary: File imports, aliases, visibility, and combined Zig output.
order: 20
---

# Modules and visibility

Each `.a7` file is a module. Supported file imports are resolved by the frontend and lowered into one combined Zig output file. This is not separate object linking or a package manager.

## Imports and aliases

```a7
io :: import "std/io"
math :: import "std/math"
console :: import "std/io"
```

An alias is local: `console.println(...)` calls the same virtual module as `io.println(...)`. `std/io` and `std/math`, along with their short `io` and `math` module names, are compiler-backed virtual modules.

Local file aliases use forms such as `helper :: import "./helper"` or `helper :: import "subfolder/helper"`. Simple alias-qualified calls are supported and emit into the same generated Zig source. Import paths with parent traversal such as `../utils` are rejected by the resolver.

## Public and private declarations

`pub` applies to top-level functions, variables, constants, and types. Items without `pub` are file-private. `pub` cannot decorate a local, parameter, or individual struct field. There is no protected or internal visibility level.

```a7
pub answer :: fn() i32 {
    ret 42
}
```

This declaration belongs in the imported module. The caller qualifies it through its own module alias.

## Status and restrictions

Status: limited. File-backed imports support the current simple combined-output workflows. Broad cross-module type checking, aggregate interaction, generic propagation, and selected imports remain follow-up work.

Selected-import syntax such as `import "helper" { answer }` has resolver metadata but is not backend-runnable. `using import` is not a supported public workflow. Parser routines alone are insufficient evidence that a spelling reaches native execution.

`std/string`, `std/mem`, and `std/collections` are planned. There is no current package registry. See the [standard library](../stdlib.md) for the actual registered operations.

## Evidence

- [a7/module_resolver.py](https://github.com/code5717/a7-py/blob/master/a7/module_resolver.py)
- [examples/018_modules.a7](https://github.com/code5717/a7-py/blob/master/examples/018_modules.a7)
- [test/test_module_alias_shadowing.py](https://github.com/code5717/a7-py/blob/master/test/test_module_alias_shadowing.py)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)
- [docs/SPEC.md](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
