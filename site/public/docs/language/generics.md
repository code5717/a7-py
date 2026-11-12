---
title: Generics and type sets
nav: Generics
group: Reference
summary: Type parameters, concrete specialization, type sets, and current limits.
order: 18
---

# Generics and type sets

Generic type parameters use `$T`. Concrete call arguments can infer a function's type parameters. A function may declare its parameters in a list (`identity($T) :: fn(x: $T) $T`) or inline (`identity :: fn(x: $T) $T`); both compile and run.

```a7
identity($T) :: fn(value: $T) $T {
    ret value
}
```

Calls `identity(7)` and `identity("ok")` select concrete specializations. The full repository example also instantiates nested generic structs.

Generic local literal, array and scalar `if`/`match` initializers must fit each concrete
instantiation. A bound callback keeps that instantiation's signature through
local aliases, assignments and branch selection; calls do not infer fresh types.
For example, a callback instantiated with an i8 argument rejects the value 300.
Callback values selected through record fields or array elements remain incomplete.
Declared fixed arrays such as `values: [2]$T = [1, 2]` fit each element after
concrete substitution, including nested arrays. An i8 instantiation accepts
1 and 2 and rejects 128; typed i32 values do not narrow implicitly to i8.
Concrete wrappers retain fitting checks through ordinary function aliases and
parameters. An unrelated generic parameter does not reopen a concrete check.
An unresolved source or destination type still requires a supported generic
callable origin; unsupported escapes of these newly deferred initializers reject
at semantic exit 6.

Nested array-literal arms inside generic `if`/`match` initializers receive
contextual fitting. An immutable generic function alias carries its
declaration's body checks when the alias and its copy chain are never
reassigned, passed by reference or captured by another function, including
same-file, imported, module-global and selected-import origins. Parameter,
mutable, captured and aggregate origins still have checking gaps. Runtime
generic dispatch is not implemented by this repair.

`$N` value parameters accept declared scalar kinds. Instantiation accepts named
constants (`Buf(SIZE)`) and literals (`Buf(4)`). Calls infer `$N` when the
binding is unique. Matching forwarding such as `inner: Buf($N)` is accepted
under kind checks.

Numeric match patterns are checked after concrete substitution. Each
instantiation retains its own fitted values and overlap checks. Named constants
resolve in the defining scope. Runtime ranges require numeric or character
subjects. Unsupported callable origins cannot discard these deferred checks.

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

A file-scope alias such as `IntOnly :: @type_set(i32, i64)` works as a
constraint (`$T: IntOnly`). It exists only at compile time and emits no Zig.

The constraint shape `name($T: Numeric) :: fn(value: $T) $T { ... }` checks inferred call arguments against the declared constraint. Minimal conjunctions such as `where T: Numeric, U: Float` also work for functions, structs and unions. Richer predicates remain unsupported.

A constrained generic argument can be forwarded when its admitted set is
nonempty and every member belongs to the destination constraint. For example,
`Float` satisfies `Numeric`; `Numeric` does not satisfy `Float`. Unconstrained arguments still reject. The
same rule applies to constrained struct and union construction and type
annotations. For example, `b: Box(i32)` rejects when `Box` requires `Float`,
even when no value is constructed. Signatures, fields and aliases are checked
where their annotations are written.

Record constraints resolve after named type aliases in their defining file.
A type-set member can name a later alias. Imported owners keep their own
constraints rather than using a same-named alias in the importing file.

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
example. A file-scope `@type_set` alias works the same way.

## Status and restrictions

Status: limited. Concrete function and struct examples are implemented, including
`$N` literals, unique inference and matching forwarding. Deeper call-chain
propagation and unresolved destinations such as `[2]$T` remain incomplete.
Generic tagged unions specialize positionally. Canonical prelude types
`Option(T)` and `Result(T, E)` are available in every file. Their names cannot
be redeclared; module imports remain explicit. Generic enums remain unsupported.

Generic names start with a letter after `$` and may contain digits and underscores after that letter, so `$T1` is a valid spelling and `$123` is not. The tokenizer uses Unicode-aware character checks; ASCII names are the documented forms.

Some specification examples mix separate `$T` parameters and plain `T` references. Prefer the consistent spellings in the repository's generic example. This documentation does not authorize a syntax change.

## Evidence

- [examples/014_generics.a7](https://github.com/code5717/a7-py/blob/master/examples/014_generics.a7)
- [a7/generics.py](https://github.com/code5717/a7-py/blob/master/a7/generics.py)
- [test/test_semantic_generics.py](https://github.com/code5717/a7-py/blob/master/test/test_semantic_generics.py)
- [a7/tokens.py](https://github.com/code5717/a7-py/blob/master/a7/tokens.py)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)

Exact numeric pattern fitting and emitted float-width conversions share the
compilation budget and original initializer account. The checker also accounts
for emitted unused widths and templates. It keeps each instantiation's fitted
values separate and releases temporary copies. Resource failures remain semantic
errors; this does not change math-call output or add runtime generic dispatch.

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
