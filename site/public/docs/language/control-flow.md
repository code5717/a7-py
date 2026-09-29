---
title: Control flow
nav: Control flow
group: Reference
summary: Conditions, loops, match patterns, labels, and restricted fallthrough.
order: 14
---

# Control flow

A7 has statement and expression forms of `if` and `match`, plus `while` and `for` loops. Conditions use boolean expressions. Blocks use braces.

## Conditions

```a7
if value < 0 {
    io.println("negative")
} else if value > 0 {
    io.println("positive")
} else {
    io.println("zero")
}
```

This is a syntax excerpt; `value` and `io` must be declared by the enclosing program. An `if` expression supplies values through its branches, for example `if x > 0 { x } else { -x }`.

## Loops and iteration

Use `while condition { ... }`, an infinite `for { ... }`, or a C-style `for initialization; condition; update { ... }`. Iterate arrays and slices with `for value in values`. Add an index with `for index, value in values`; that index has type `usize`.

```a7
numbers: [3]i32 = [10, 20, 30]
sum := 0
for index, value in numbers {
    sum += value
}
```

A C-style loop can keep initialization, condition, and update together:

```a7
total := 0
for i := 1; i <= 5; i += 1 {
    if i % 2 == 0 {
        continue
    }
    total += i
}
```

This excerpt from `021_control_flow.a7` leaves `total` equal to 9.

An index is a position, not an arbitrary signed integer. Bounds-dependent operations still need a compiler proof.

## Labels and jumps

`ret` exits a function. `break` exits a loop; `continue` starts its next iteration. Name a loop with `@outer` immediately before `for` or `while`, then use `break outer` or `continue outer`. The old `outer: for` spelling is rejected.

For example, this excerpt from `036_control_flow_edges.a7` stops before 7:

```a7
numbers: [5]i32 = [3, 5, 7, 9, 11]
break_total := 0
@outer_break for value in numbers {
    if value == 7 {
        break outer_break
    }
    break_total += value
}
```

`break_total` is 8. Replacing the break with `continue outer_break` skips only
that element and leaves the sum at 28.

Statements after a terminating `ret`, valid jump, or fully terminating branch are unreachable and can be rejected.

## Matching

`match value { case pattern: body ... else: body }` supports literal, enum, range, wildcard, and identifier patterns. A visible identifier names an existing constant or value pattern. An otherwise unresolved identifier captures the matched value as an immutable branch-local binding and covers the remaining values. A capture must be the only pattern in its case.

A comma separates alternatives in one case; `4..10` is a range pattern:

```a7
value := 5
match value {
    case 0: io.println("zero")
    case 1, 2, 3: io.println("small")
    case 4..10: io.println("range")
    else: io.println("other")
}
```

The fragment assumes an `io` import and an enclosing function. It prints
`range`. A match expression supplies a value. This function captures the
scrutinee in its only branch:

```a7
score :: fn(x: i32) i32 {
    ret match x {
        case value: value + 1
    }
}
```

`score(4)` returns 5. Do not confuse a new capture name with an existing visible
binding used as a value pattern.

`fall` enters the next case body. It must be the final statement of a non-final case. It is unavailable in a match expression and cannot appear in a nested context that violates that restriction. Ordinary cases do not fall through automatically.

This complete program prints `one`, then `two`, each on its own line. The
second case body runs even though the original value is 1:

```a7
io :: import "std/io"

main :: fn() {
    value := 1
    match value {
        case 1: {
            io.println("one")
            fall
        }
        case 2: {
            io.println("two")
        }
        else: {
            io.println("other")
        }
    }
}
```

## Unmatched statement cases

A statement `match` without `else` executes no arm when none of its patterns match. The compiler preserves this with conditional lowering. A match expression must supply a result; this statement rule does not supply a missing expression value.

## Status and restrictions

Status: supported for the example-backed loop and match forms, limited for safety proofs derived from arbitrary control flow. Recursion is unavailable. Rewrite recursive traversal with loops and an explicit worklist.

## Evidence

- [examples/021_control_flow.a7](https://github.com/code5717/a7-py/blob/master/examples/021_control_flow.a7)
- [examples/036_control_flow_edges.a7](https://github.com/code5717/a7-py/blob/master/examples/036_control_flow_edges.a7)
- [a7/passes/semantic_validator.py](https://github.com/code5717/a7-py/blob/master/a7/passes/semantic_validator.py)
- [docs/SPEC.md](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
