---
title: Types and conversions
nav: Types
group: Reference
summary: Numeric types, inference, casts, compatibility, and nil.
order: 12
---

# Types and conversions

Choose explicit-width integers for data. Use `usize` for lengths, capacities, allocation sizes, array indices, and slice bounds. Reserve `isize` for signed pointer-sized offsets and position differences.

## Primitive types

| Type | Width | Values or purpose |
| --- | --- | --- |
| `bool` | Logical | `true` or `false` |
| `i8` | 8 bits | -128 to 127 |
| `i16` | 16 bits | -32768 to 32767 |
| `i32` | 32 bits | -2^31 to 2^31 - 1 |
| `i64` | 64 bits | -2^63 to 2^63 - 1 |
| `u8` | 8 bits | 0 to 255 |
| `u16` | 16 bits | 0 to 65535 |
| `u32` | 32 bits | 0 to 2^32 - 1 |
| `u64` | 64 bits | 0 to 2^64 - 1 |
| `usize` | Target pointer width | Non-negative sizes and indices |
| `isize` | Target pointer width | Signed offsets |
| `f32` | 32 bits | IEEE 754 single precision |
| `f64` | 64 bits | IEEE 754 double precision |
| `char` | Byte representation | Public ASCII character model |
| `string` | Composite | Character data and length |

`int`, `uint`, and `number` are not accepted public alternatives to explicit-width integers. Although the lexer reserves `float`, use the documented `f32` and `f64` spellings. This index makes no runtime-support claim for `float`.

## Inference and compatibility

`name := expression` infers a variable's type. Explicit declarations check the initializer against the declared type. Integer literals can adopt an integer destination type when their value fits, including arguments and return values. Arrays and slices are different types. Implicit array-to-slice argument conversion is unavailable; create a view with slice syntax. Ordinary lvalues can satisfy `ref T` function parameters through compiler-inserted reference operations.

Do not expect arbitrary implicit numeric widening. Use an explicit cast when a numeric conversion is required.

## Casts

```a7
converted := cast(f64, 42)
```

The compiler classifies a primitive cast and requires a range proof before lowering it. Merely naming the destination type does not make a narrowing conversion valid. Cast behavior is limited by the current safety analysis; an unproved conversion can be rejected even when a programmer believes it is safe.

## Composite and nullable types

Arrays use `[N]T`, nested arrays use `[N][M]T`, slices use `[]T`, and references use `ref T`. Structs, enums, unions, function types, and generic instantiations have their own reference topics.

Currently `nil` belongs to references. It cannot initialize a scalar, array, or value struct. `new T` results require nil proof before field access. A proposed separation between non-null and optional references is planned, not current syntax.

## Status and restrictions

Status: limited. Core scalar types and value aggregates are implemented, but shift safety, signed numeric edge cases, full union safety, and some generic compatibility paths remain incomplete. Numeric representation alone does not establish that every operation is safe.

## Evidence

- [a7/types.py](https://github.com/code5717/a7-py/blob/master/a7/types.py)
- [a7/cast_classifier.py](https://github.com/code5717/a7-py/blob/master/a7/cast_classifier.py)
- [test/test_cast_safety_matrix.py](https://github.com/code5717/a7-py/blob/master/test/test_cast_safety_matrix.py)
- [docs/SAFETY_CONTRACT.md](https://github.com/code5717/a7-py/blob/master/docs/SAFETY_CONTRACT.md)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
