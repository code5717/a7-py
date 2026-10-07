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

Local file aliases use forms such as `helper :: import "./helper"` or `helper :: import "subfolder/helper"`. Simple alias-qualified calls are supported and emit into the same generated Zig source. Paths resolve relative to the importing file. A nested file may use `../utils`
when the target stays inside the entry file's folder. Paths and symlinks that
escape that folder are rejected. Directory fallback through `path/mod.a7`
remains supported.

Canonical real paths identify loaded file modules. Importing one file twice in
the same importer is an error, including alternate relative spellings and
symlinks. Different importing files can share one cached dependency.

A local binding cannot reuse an import alias from its own file, including a
stdlib alias. Parameters, loop bindings and match captures follow this rule;
violations fail with semantic exit 6. Record fields and another file's aliases
do not reserve local names.

## Public and private declarations

The approved model makes top-level `_name` private and other top-level names
public; `__name` is reserved for the compiler. L69 authorizes separate file
scopes. Complete scope isolation and underscore visibility enforcement remain
unfinished. Current `pub` parsing does not enforce a private/public boundary.
Struct fields remain visible to importers; field `pub` has no access-control
effect. See the [decision ledger](https://github.com/code5717/a7-py/blob/master/docs/plan/decisions.md).

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
- [test/test_module_path_identity.py](https://github.com/code5717/a7-py/blob/master/test/test_module_path_identity.py)
- [examples/018_modules.a7](https://github.com/code5717/a7-py/blob/master/examples/018_modules.a7)
- [test/test_module_alias_shadowing.py](https://github.com/code5717/a7-py/blob/master/test/test_module_alias_shadowing.py)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)
- [docs/SPEC.md](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
