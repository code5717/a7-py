---
title: Operators and evaluation
nav: Operators
group: Reference
summary: Arithmetic, logic, precedence, assignment, and numeric restrictions.
order: 13
---

# Operators and evaluation

Arithmetic uses `+`, `-`, `*`, `/`, and `%`. Comparisons use `==`, `!=`, `<`, `<=`, `>`, and `>=`. Boolean composition uses `and`, `or`, and `!`; the lexer also recognizes `not`. Prefer the forms used in the runnable examples.

## Precedence

This is the specification's binary precedence, from tightest to loosest. Parentheses make intended grouping explicit.

| Level | Operators | Meaning |
| --- | --- | --- |
| 1 | `* / %` | Product, quotient, remainder |
| 2 | `+ -` | Sum and difference |
| 3 | `<< >>` | Shifts |
| 4 | `< > <= >=` | Ordered comparison |
| 5 | `== !=` | Equality |
| 6 | `&` | Bitwise AND |
| 7 | `^` | Bitwise XOR |
| 8 | `\|` | Bitwise OR |
| 9 | `and` | Logical AND |
| 10 | `or` | Logical OR |

Unary operations include `-value`, `!flag`, and `~bits`. Postfix calls, indexing, slicing, and field access bind to their operand.

## Assignment

`=` updates a mutable binding. Compound forms are `+=`, `-=`, `*=`, `/=`, `%=`, `&=`, `|=`, `^=`, `<<=`, and `>>=`. They remain subject to the same type and safety restrictions as their underlying operations.

```a7
a := 10
b := 3
sum := a + b
remainder := a % b
bits := a & b
```

## Division, remainder, and numeric limits

Division and remainder need proof that the divisor is nonzero. Guard a possibly zero divisor before use. Floating remainder truncates the quotient toward zero: `-5.5 % 2.0` produces `-1.5`, and exact negative division preserves negative zero in the folded remainder.

Integer `+`, `-`, and `*`, including compound assignments, wrap at the destination
width. Release builds emit non-wrapping operators when the safety pass proves the
result fits the type range; proven cases cannot wrap, so results are unchanged.
`--no-nonwrap` forces wrapping in both profiles. Signed division truncates toward
zero. Negating an unsigned value is rejected. Constant shift counts must be
non-negative and less than the operand width. Dynamic shift proofs and other
numeric edge cases remain incomplete.

Arithmetic uses a compatible wider type when operands have different widths.
A representable literal can take its peer's type. An explicit narrower result
binding is rejected. Use an explicit cast when no safe compatible type exists.

Status: limited. Basic operator support does not guarantee freedom from every
target-language trap.

## Evaluation order

The specification states left-to-right argument and binary-expression evaluation, right-to-left assignment, and declaration-order field initialization. These are specification requirements; this reference does not claim an exhaustive runtime qualification of side-effect ordering. Avoid making correctness depend on unverified order interactions.

Logical conditions can establish safety facts, but mutations and calls can invalidate facts. Use explicit guards when proving bounds, nonzero divisors, or non-nil references.

## Arrays and references

One-dimensional same-shape numeric fixed-array addition is a supported narrow array operation. It is not tensor broadcasting. Bitwise `&` and arithmetic `*` are not public address-of or dereference syntax. Use [reference parameters](memory.md) instead.

## Evidence

- [a7/parser.py](https://github.com/code5717/a7-py/blob/master/a7/parser.py)
- [a7/exact_constants.py](https://github.com/code5717/a7-py/blob/master/a7/exact_constants.py)
- [examples/020_operators.a7](https://github.com/code5717/a7-py/blob/master/examples/020_operators.a7)
- [docs/SAFETY_CONTRACT.md](https://github.com/code5717/a7-py/blob/master/docs/SAFETY_CONTRACT.md)
- [docs/SPEC.md](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
