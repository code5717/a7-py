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

## Indexing through fixed-array references

Indexing through `ref [N]T` uses the declared fixed-array length and requires a
non-nil reference proof as well as a bounds proof. Supported operations read
primitive elements or update them with simple or compound assignment, including
nested fixed arrays and `usize` indices with a proven bound. The Zig backend
keeps the optional reference and unwraps it at the indexed use.

Known calls, forwarding and stable unwritten, uncaptured local callable copies
retain indexed access requirements. Borrowed arrays and guards that avoid the
access on nil remain valid. Reachable nil accesses and out-of-bounds indices
fail at semantic exit 6, in executable and library modes.

Resolved functions whose body contains one Boolean-literal return supply indexed
guard facts. This covers direct and forwarded calls and stable unwritten,
uncaptured local aliases. The checker preserves call and argument evaluation;
indexed uses retain optional-reference unwraps. Conditional, effectful and
deferred helpers remain unknown.

Eligible local Boolean cells and value parameters supply indexed guard facts
from bare or negated conditions and comparisons with Boolean literals. Early
returns retain the surviving branch fact; copies retain their evaluated value.
Captured or reference-exposed cells, fields and globals are excluded. Assignments
replace facts; joins require matching values. Loop write invalidation also
clears affected Boolean facts.
True or unknown guards with nil reject at semantic exit 6. An unguarded symbolic
`read(nil, b)` wrapper still rejects even if its only caller passes false.
Effectful index expressions, indexing through selected reference-array fields,
mutable or captured callable origins, ref slicing and general reference-element
ownership
remain outside this support. Access requirements do not certify that a function
is pure or that its effects are fully modeled.

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

An inferred slice binding retains the slice type even when its initializer
views a fixed array. A mutable binding can select a view of a different length:

```a7
backing: [3]i32 = [7, 8, 9]
state := backing[0..3]
state = backing[1..2]
// state.len is 1; state[0] is 8.
```

An immutable `::` binding cannot be reassigned. Initializers execute once.
The backing storage must still remain alive for each use.

## Strings and characters

`string` stores bytes from UTF-8 source literals. A `char` holds one byte from 0 through 255. A string literal uses double quotes; a character uses single quotes. String slicing returns `[]char`, not a new `string`. Escape syntax is listed in [syntax](syntax.md#literals-and-escapes).

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

Status: limited for current arrays and slices. Tensor types, broadcasting, reshaping, reductions, matrix libraries, autodiff, neural-network primitives, memory-layout controls, SIMD annotations, GPU movement, and advanced multi-axis indexing are planned. The [array programming proposal](https://github.com/code5717/a7-py/blob/master/docs/design/array-programming.md) preserves the historical sketches. SPEC section 9 now points to that document. Proposed tensor API spellings are not current executable APIs.

`new [N]T` is unavailable. Use stack fixed arrays or supported slice operations. Do not substitute a heap-array example from an older specification passage.

## Evidence

- [examples/012_arrays.a7](https://github.com/code5717/a7-py/blob/master/examples/012_arrays.a7)
- [examples/034_string_utils.a7](https://github.com/code5717/a7-py/blob/master/examples/034_string_utils.a7)
- [examples/035_matrix.a7](https://github.com/code5717/a7-py/blob/master/examples/035_matrix.a7)
- [docs/SAFETY_CONTRACT.md](https://github.com/code5717/a7-py/blob/master/docs/SAFETY_CONTRACT.md)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
