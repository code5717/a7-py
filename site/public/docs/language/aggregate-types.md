---
title: Structs, enums, and unions
nav: Aggregate types
group: Reference
summary: Structs, enums, unions, initialization, and payload restrictions.
order: 17
---

# Structs, enums, and unions

Aggregate declarations use `Name :: struct`, `Name :: enum`, or `Name :: union`. Structs group fields, enums name alternatives, and unions store one selected payload.

## Structs and initialization

Struct literals must initialize every field, either by name or declaration-order position exactly once. Missing, unknown, and
duplicate fields are rejected. A declaration without an initializer is a
separate default-initialization operation.

```a7
Counter :: struct {
    value: i32
}
counter := Counter{value: 0}
counter.value = 1
```

Named initializers identify their field. Supported positional initializers follow declaration order. Nested structs contain other value structs; copying values does not imply a deep copy of heap references inside them. Field access uses `value.field`, including nil-proved references.

## Enums

```a7
Color :: enum {
    Red,
    Green,
    Blue
}
```

Plain enum members receive integer values beginning at zero; explicit values use `Name = integer`. Access members through the enum name, such as `Color.Red`, and match them with `case` patterns. Do not infer payload-carrying `Option` or `Result` support from plain enum support.

Enums with explicit values use the first tag type in `i32`, `u32`, `i64`,
`u64` that fits all variants, including implicit successors. For example,
`Big :: enum { A = 4294967295, B }` uses `i64` because `B` is 4294967296.
If no single supported tag type fits all values, code generation rejects the
enum. See [wide-enum tests](https://github.com/code5717/a7-py/blob/master/test/test_enum_tag_types.py).

## Unions

```a7
Value :: union {
    int_val: i32
    float_val: f64
}
int_value := Value{int_val: 42}
```

An untagged union literal requires exactly one named field. The field must exist and its initializer must match its type. Field access type-checks against declared union fields. Current union safety does not prove every active payload, so do not access another field on the assumption that the compiler has checked its discriminant.

## Status and restrictions

Status: supported for example-backed value structs and plain enums; limited for unions. `union(tag)` supports leading-dot match arms and copyable payload capture; broader lifetime and payload-safety guarantees remain incomplete. Multiple return values and destructuring remain unavailable; use a named result struct.

`pub` on a struct field is accepted without changing field visibility. Broader cross-module aggregate checking is limited. Generic aggregate specialization is covered in [generics](generics.md).

## Evidence

- [examples/009_struct.a7](https://github.com/code5717/a7-py/blob/master/examples/009_struct.a7)
- [examples/010_enum.a7](https://github.com/code5717/a7-py/blob/master/examples/010_enum.a7)
- [examples/016_unions.a7](https://github.com/code5717/a7-py/blob/master/examples/016_unions.a7)
- [examples/023_inline_structs.a7](https://github.com/code5717/a7-py/blob/master/examples/023_inline_structs.a7)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
