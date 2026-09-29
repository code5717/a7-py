---
title: Arrays, slices, and strings
nav: Arrays and strings
group: Reference
summary: Fixed arrays, slice views, strings, bounds, and planned tensor work.
order: 16
---

# Arrays, slices, and strings

Fixed arrays own a known number of elements. Slices view a range of existing elements. Strings provide character data; their public length access is limited. Use `usize` for all index and bound variables.

## Fixed and nested arrays

```a7
numbers: [5]i32 = [10, 20, 30, 40, 50]
matrix: [2][2]i32 = [[1, 2], [3, 4]]
zeroes: [4]u8
```

A fixed-array bound can name an integer literal constant, including a constant
alias such as `N :: 3`. General constant-expression bounds are not fully qualified.

An array literal must match the declared length and element type, including nested literals. A declaration without an initializer zero-initializes a fixed array; a scalar-fill declaration such as `filled: [3]i32 = 7` is currently rejected
with a type mismatch. Use an exactly sized literal or a loop to fill an array. `nil` cannot initialize an array.

Indexed iteration, `for index, value in numbers`, gives a `usize` index. Same-shape numeric fixed-array addition is implemented. Other tensor operations must not be inferred from this one operation.

## Array storage

1. The fixed array owns four elements, `[10, 20, 30, 40]`, at positions 0 through 3.
2. The slice `array[1..3]` refers to positions 1 and 2 in that same storage.
3. The view contains 20 and 30. Its length is 2, and its end bound excludes position 3.

The slice is a view, not a new owned array. Keep the backing storage alive while using it.

## Slices and bounds

A slice type is `[]T`. `values[start..end]` selects the half-open interval beginning at `start` and ending before `end`. Omitted bounds select the corresponding edge. The compiler requires `0 <= start <= end <= len`. Indexing requires `0 <= index < len`.

| Storage or view | Positions | Meaning |
| --- | --- | --- |
| Array `[10, 20, 30, 40]` | 0, 1, 2, 3 | Four owned elements |
| Slice `array[1..3]` | 1, 2 in the backing array | View containing 20 and 30 |
| Slice length | 2 | Number of elements in the view |

A slice shares its backing storage. It must not outlive that storage. Full lifetime and alias enforcement remain incomplete, so a successful compile is not a complete lifetime proof.

## Strings and characters

`string` is the public ASCII string type. A string literal uses double quotes; a character uses single quotes. String slicing returns `[]char`, not a new `string`. Escape syntax is listed in [syntax](syntax.md#literals-and-escapes).

Slices expose `.len`. Direct string length access such as `text.len` is
currently rejected by the type checker, despite specification descriptions of
string storage. Count characters with a loop as in `034_string_utils.a7` when
you need a string length. Underlying `.ptr` descriptions do not introduce public
pointer arithmetic or dereference operators. Broader string helpers and `std/string` are planned.

## Current operations together

This complete program indexes a slice with `usize`, reads its length, adds two
fixed arrays of the same shape, and iterates a string slice:

```a7
io :: import "std/io"

main :: fn() {
    numbers: [4]i32 = [10, 20, 30, 40]
    middle := numbers[1..3]
    index: usize = 0
    io.println("{} {}", middle[index], middle.len)

    left: [2]f64 = [1.0, 2.0]
    right: [2]f64 = [3.0, 4.0]
    sum: [2]f64 = left + right
    io.println("{} {}", sum[0], sum[1])

    text: string = "A7"
    prefix := text[0..1]
    for ch in prefix {
        io.print("{}", ch)
    }
    io.println(" {}", prefix.len)
}
```

Expected stdout:

```text
20 2
4 6
A 1
```

The final length is the slice length, 1. This example does not use the currently
unavailable direct `string.len` access or scalar-fill array initialization.

## Runtime slice bounds

For a `usize` index, `if index < items.len { ... }` proves an index into the same slice binding inside that branch. Reassigning the slice or passing it for mutation invalidates that relation. Fixed-array bounds and literal bounds remain supported. This does not prove arbitrary relationships between different slices or aliases.

## Planned array programming

Status: limited for current arrays and slices. Tensor types, broadcasting, reshaping, reductions, matrix libraries, autodiff, neural-network primitives, memory-layout controls, SIMD annotations, GPU movement, and advanced multi-axis indexing are planned. Specification section 9 illustrates that proposed design, not executable current APIs.

`new [N]T` is unavailable. Use stack fixed arrays or supported slice operations. Do not substitute a heap-array example from an older specification passage.

## Evidence

- [examples/012_arrays.a7](https://github.com/code5717/a7-py/blob/master/examples/012_arrays.a7)
- [examples/034_string_utils.a7](https://github.com/code5717/a7-py/blob/master/examples/034_string_utils.a7)
- [examples/035_matrix.a7](https://github.com/code5717/a7-py/blob/master/examples/035_matrix.a7)
- [docs/SAFETY_CONTRACT.md](https://github.com/code5717/a7-py/blob/master/docs/SAFETY_CONTRACT.md)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
