# Independent IEEE materialization cases

These seven cases define expected results for direct rounding of exact untyped
values to `f32` or `f64`. They are acceptance requirements, not test results or
language-change approval. No candidate conversion algorithm was consulted to
derive the answers. No compiler or native program was run for this document.

The proposed contract uses round-to-nearest, ties-to-even, preserves signed zero
and subnormals, and rejects an implicit finite constant conversion whose rounded
result is infinity. Binary32 has 24 significand bits; binary64 has 53. These
format and rounding rules are described in NVIDIA's
[IEEE floating-point guide](https://docs.nvidia.com/cuda/archive/11.4.1/floating-point/index.html).
All expected values below follow from powers of two and midpoint comparisons.
Infinity rejection is the proposed A7 fitting policy, not an IEEE requirement
to reject compilation.

Each table row supplies the literal for its preceding source template. Rows are
separate programs. All literal spellings contain at most 100 characters.
Hexadecimal results describe the numeric IEEE bit pattern, independent of memory
byte order. They do not require adding a public A7 bit-cast operation.

## 1. Binary32 midpoint near one

```a7
value: f32 = LITERAL
```

| Literal | Expected bits | Expected value |
| --- | --- | --- |
| `1.000000059604644775390624` | `0x3f800000` | 1 |
| `1.000000059604644775390625` | `0x3f800000` | 1 |
| `1.0000000596046447753906250000000000000000000000000000000000000000000000001` | `0x3f800001` | `1 + 2^-23` |

Adjacent values are `1` and `1 + 2^-23`. Their exact midpoint is `1 + 2^-24`,
the middle row. At the tie, the lower value has the even significand. The last
row is strictly above the midpoint. Rounding it first to binary64 or binary128
can erase that difference, so this row detects rounding through an intermediate
floating format.

## 2. Binary64 midpoint near one

```a7
value: f64 = LITERAL
```

| Literal | Expected bits | Expected value |
| --- | --- | --- |
| `1.00000000000000011102230246251565404236316680908203124` | `0x3ff0000000000000` | 1 |
| `1.00000000000000011102230246251565404236316680908203125` | `0x3ff0000000000000` | 1 |
| `1.00000000000000011102230246251565404236316680908203126` | `0x3ff0000000000001` | `1 + 2^-52` |

The midpoint is exactly `1 + 2^-53`. The surrounding decimal values differ from
it by `10^-53`, which is smaller than binary128's spacing near one. The upper
row must still round upward when converting directly to binary64.

## 3. Binary32 gradual underflow

```a7
value: f32 = LITERAL
```

| Literal | Expected bits | Expected value |
| --- | --- | --- |
| `7.006492321624085e-46` | `0x00000000` | Positive zero |
| `7.006492321624086e-46` | `0x00000001` | `2^-149` |
| `1.401298464324817e-45` | `0x00000001` | `2^-149` |

The smallest positive subnormal is `2^-149`. The first two literals bracket
half that value, `2^-150`. The third is nearest to the subnormal itself.
Accepting these sources but flushing every subnormal to zero fails the contract.

## 4. Binary64 gradual underflow

```a7
value: f64 = LITERAL
```

| Literal | Expected bits | Expected value |
| --- | --- | --- |
| `2.4703282292062327e-324` | `0x0000000000000000` | Positive zero |
| `2.4703282292062328e-324` | `0x0000000000000001` | `2^-1074` |
| `4.9406564584124654e-324` | `0x0000000000000001` | `2^-1074` |

The smallest positive subnormal is `2^-1074`. Its half is `2^-1075`, between
the first two literals. Both sides of this threshold need observable results.

## 5. Binary32 finite maximum and overflow threshold

```a7
value: f32 = LITERAL
```

| Literal | Expected result |
| --- | --- |
| `340282346638528859811704183484516925440.0` | `0x7f7fffff`, largest finite binary32 |
| `340282356779733661637539395458142568447.0` | `0x7f7fffff`, largest finite binary32 |
| `340282356779733661637539395458142568448.0` | Reject implicit constant fitting |

The largest finite value is `2^128 - 2^104`. The overflow midpoint is
`2^128 - 2^103`. The second literal is exactly one less than that midpoint,
and must round to the largest finite value even though it exceeds that value.
At the midpoint, ties-to-even rounds toward `2^128`, which overflows binary32.
Rejecting every exact value larger than the largest finite value would incorrectly
reject the second row.

## 6. Binary64 finite maximum and overflow

```a7
value: f64 = LITERAL
```

| Literal | Expected result |
| --- | --- |
| `1.7976931348623157e308` | `0x7fefffffffffffff`, largest finite binary64 |
| `1.7976931348623159e308` | Reject implicit constant fitting |

The largest finite value is `2^1024 - 2^971`. The overflow midpoint is
`2^1024 - 2^970`. The first literal is nearest to the largest finite value;
the second lies above the overflow midpoint. Compact decimal exponents keep
both source literals within the existing length limit.

## 7. Negative zero survives materialization

```a7
literal_zero: f32 = -0.0
underflow_zero: f64 = -1e-400
```

Expected bits are `0x80000000` and `0x8000000000000000`, respectively. The first
comes from the explicit negative sign. The second is a negative nonzero value
whose magnitude is below `2^-1075`, so it rounds to negative zero. Both compare
equal to positive zero; equality alone cannot test this requirement.

## How to qualify these cases

Use the real A7 source-to-native path in Debug and ReleaseFast. Observe the
materialized target value with enough precision to distinguish adjacent values,
or use a separate backend test observer to report the stored target bits. Keep
such an observer outside production A7 syntax. Record what it leaves unverified.
Printed text `0` or a coarse decimal approximation cannot qualify negative-zero
or midpoint cases. A rejection must occur at the A7 fitting stage with a located
diagnostic and no usable new artifact; a later Zig failure is insufficient.

The expectations stay fixed if the candidate algorithm changes. Compare outcomes
to these mathematical values rather than recomputing expected values through the
candidate's converter, a host binary64 parse, or a copied conversion algorithm.
