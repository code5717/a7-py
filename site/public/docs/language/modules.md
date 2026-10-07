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

`Option(T)` and `Result(T, E)` are available without imports. Module operations
and `io.IoErr` still require an explicit import in each file. Literal paths
starting with `std/` select shipped modules; project replacements or unavailable
reserved modules fail with exit 3. Explicit relative paths such as
`./std/helper` keep ordinary file resolution and containment rules.

Local file aliases use forms such as `helper :: import "./helper"` or `helper :: import "subfolder/helper"`. Qualified calls, types, constants and struct literals use each file's own scope and emit into the same generated Zig source. Paths resolve relative to the importing file. A nested file may use `../utils`
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

Top-level `_name` declarations are private to their file. Other ordinary
top-level declarations are public; top-level `__name` declarations are reserved
for the compiler. Local `__` names remain accepted. `pub` does not change these
name-based visibility rules. Nominal types declared in different files retain
distinct identities, even when they have the same name.
Struct fields remain visible to importers; field `pub` has no access-control
effect. See the [decision ledger](https://github.com/code5717/a7-py/blob/master/docs/plan/decisions.md).

```a7
pub answer :: fn() i32 {
    ret 42
}
```

This declaration belongs in the imported module. The caller qualifies it through its own module alias.

## Imports stay local

An import alias belongs to its declaring file. If `a.a7` imports `b`, a caller
that imports `a` cannot use `a.b.value()`. Parsed forwarding fails with semantic
exit 6 and a direct-import example. Import `b` in the caller or expose an
ordinary public wrapper in `a.a7`:

```a7
// a.a7
b :: import "./b"
value :: fn() i32 { ret b.value() }
```

```a7
// main.a7
a :: import "./a"
main :: fn() { result := a.value() }
```

These snippets assume `b.a7` defines `value :: fn() i32`. Ordinary struct fields
remain accessible, including a field named `b`. Unsupported multi-dot type
annotations and literals, such as `x:a.b.Box` and `a.b.Box{}`, already fail
parsing with exit 5; the import-visibility rule does not extend that grammar.

## Status and restrictions

Status: limited. Per-file scopes, underscore privacy, qualified types and
struct literals, constant array lengths and module-owned generic bodies are
implemented. Generic function values reached through imported or module-global
aliases still have checking gaps. Selected imports remain unavailable.

Selected-import syntax such as `import "helper" { answer }` has resolver metadata but is not backend-runnable. `using import` is not a supported public workflow. Parser routines alone are insufficient evidence that a spelling reaches native execution.

`std/string`, `std/mem`, and `std/collections` are planned. There is no current package registry. See the [standard library](../stdlib.md) for the actual registered operations.

## Evidence

- [a7/module_resolver.py](https://github.com/code5717/a7-py/blob/master/a7/module_resolver.py)
- [test/test_module_path_identity.py](https://github.com/code5717/a7-py/blob/master/test/test_module_path_identity.py)
- [examples/018_modules.a7](https://github.com/code5717/a7-py/blob/master/examples/018_modules.a7)
- [test/test_module_alias_shadowing.py](https://github.com/code5717/a7-py/blob/master/test/test_module_alias_shadowing.py)
- [test/test_file_module_scopes.py](https://github.com/code5717/a7-py/blob/master/test/test_file_module_scopes.py)
- [test/test_module_import_local.py](https://github.com/code5717/a7-py/blob/master/test/test_module_import_local.py)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)
- [docs/SPEC.md](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
