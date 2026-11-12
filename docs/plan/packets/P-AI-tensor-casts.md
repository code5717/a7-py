# Tensor floating conversions

Status: unapproved conversion proposal. It depends on the pending
[tensor value contract](P-AI-tensor-values.md). L11 already requires F16, BF16,
F32 and F64 tensor formats; this packet proposes the observable conversion rules.
It does not approve scalar syntax, arithmetic promotion or mixed-precision
training. No A7 tensor cast implementation has run.

## Current behavior and sources

Current `std/tensor` imports fail with exit 3 in both semantic and compile modes;
the [frozen probes](../../../tmp/v1-completion-2026-10-07/tensor-current-probe/REPORT.md)
include a passing F32 fixed-array control. Tensor dtype tags do not add current
scalar F16/BF16 support. Existing scalar/math precision questions remain separate.

The proposed format parameters match the four semantics definitions in
[LLVM APFloat.cpp](https://llvm.org/doxygen/APFloat_8cpp_source.html), checked
2026-10-08. Precision includes the leading significand bit for normal values.

| Format | Total bits | Precision bits | Minimum normal exponent | Maximum normal exponent |
| --- | --- | --- | --- | --- |
| F16 | 16 | 11 | -14 | 15 |
| BF16 | 16 | 8 | -126 | 127 |
| F32 | 32 | 24 | -126 | 127 |
| F64 | 64 | 53 | -1022 | 1023 |

Format parameters do not select execution behavior. Intel's November 2018
[BF16 numerics proposal](https://cdrdv2-public.intel.com/671279/bf16-hardware-numerics-definition-white-paper.pdf)
describes an FMA design that flushes subnormal inputs and results. That historical
proposal is an example of differing numerical behavior, not evidence about this
machine's CPU or a selected A7 kernel. The gradual-underflow rule below would
require a conforming path, including software conversion where necessary.

## Proposed operation

`tensor.cast(value, dtype)` returns canonical `Result(Tensor, TensorError)`.
It converts each logical element to the requested format, preserving shape.
There is no implicit conversion when calling this operation with another dtype;
the destination tag is explicit. No integer dtype or integer conversion is
introduced here.

When source and destination formats match, return a retained handle to the same
immutable value. Preserve every bit, including NaN payloads. This identity path
does not allocate element or descriptor storage and does not quiet a signaling
NaN through a numerical instruction.

For differing formats, return a contiguous row-major result with new element
storage when nonempty. Read source views in their logical order. Preserve the
source value and its aliases on success and failure. Validate the dtype, then
check destination size, then allocate. Return the existing proposed
`invalid_dtype`, `size_overflow` or `allocation_failed` error as applicable.
No partially converted result escapes after failure. Empty tensors preserve
shape and need no element storage; metadata allocation can still fail.

## Proposed numerical rules

- Convert the exact value represented by each source element directly to the
  destination format with round-to-nearest, ties-to-even. Do not round through
  an intermediate F32 value when converting F64 to a 16-bit format.
- Preserve finite subnormals. Underflow rounds gradually into destination
  subnormal values or signed zero. Do not silently flush subnormals to zero.
- Preserve the sign of zero and infinity. A finite value that overflows under
  nearest-even rounding becomes the corresponding signed infinity.
- A cross-format NaN becomes one fixed positive quiet NaN in the destination:
  F16 `0x7e00`, BF16 `0x7fc0`, F32 `0x7fc00000`, F64
  `0x7ff8000000000000`. This intentionally does not preserve cross-format NaN
  sign, payload or signaling state. Same-format identity retains the source bits.
- Rounding, overflow and NaN conversion do not themselves return an error or
  depend on the caller's floating-point environment. No portable floating-point
  status flags or traps are exposed by this API.

Canonical NaNs and gradual underflow are proposed policy choices, not inferred
from L11 alone. L16's IEEE direction remains in force; this packet does not
silently introduce saturation or finite-only arithmetic. A caller needing a
finite-only validation step needs a separately specified checked operation.

F16 and BF16 conversion is neither universally widening nor universally
narrowing: they have different precision and exponent ranges. Every ordered
source/destination pair therefore needs its own conformance cases. Identity
conversion and cross-format conversion also have different NaN rules by design.

## Complete proposed example

The input `1.00048828125` is exactly `1 + 2^-11`, halfway between F16 values
`1` and `1 + 2^-10`. The proposed nearest-even conversion selects `1`.
Converting that F16 value back to F64 preserves it. With successful allocations,
the program prints `1`. The source tensor still contains the original midpoint.

```a7
io :: import "std/io"
tensor :: import "std/tensor"

main :: fn() {
    data: [1]f64 = [1.00048828125]
    shape: [1]usize = [1]
    index: [1]usize = [0]
    match tensor.from_f64(data[0..1], shape[0..1]) {
        case .ok(source): {
            match tensor.cast(source, tensor.F16) {
                case .ok(low): {
                    match tensor.cast(low, tensor.F64) {
                        case .ok(wide): {
                            match tensor.at_f64(wide, index[0..1]) {
                                case .ok(value): io.println(value)
                                case .err: io.println("read failed")
                            }
                        }
                        case .err: io.println("widen failed")
                    }
                }
                case .err: io.println("narrow failed")
            }
        }
        case .err: io.println("creation failed")
    }
}
```

This uses proposed APIs. A parser check can verify its grammar but cannot prove
that the source literal arrives unchanged, that the module exists or that the
native conversion implements this contract. Qualification must include exact
source bit patterns supplied independently of decimal-literal lowering.

## Alternatives and acceptance

Alternatives include preserving selected NaN payload bits, exposing rounding
modes, flushing subnormals, saturating finite overflow, or returning a checked
conversion error. Each changes an observable result. A backend's instruction
defaults cannot select an alternative without approval.

Required acceptance includes every source/destination pair; signed zeros;
infinities; quiet/signaling NaNs; normal and subnormal boundaries; both sides
of exact midpoints; tie cases with even and odd retained significands;
overflow boundaries; and witnesses where an intermediate F32 rounding changes
the result. Compare logical values on transposed and broadcast views, and verify
unchanged inputs after allocation failure. Preserve bit patterns through the
observation path; formatted decimal output alone is insufficient.

The [exact-value reference cases](../../../tmp/v1-completion-2026-10-07/tensor-cast-oracles/REPORT.md)
contain 33 finite/signed-zero F64-source vectors and two double-rounding
witnesses. A separate nearest-neighbor search over target encodings verified
their proposed outputs. Ten F16 cases also matched Python's half packing;
Python raised an overflow exception for the remaining F16 boundary instead of
validating the proposed infinity result. These are bounded mathematical and
host-library checks, not A7 conformance. NaNs, infinity inputs and the full
source/destination matrix remain outside that reference set.

Use exact integer/rational oracles plus an independent conversion implementation.
Software conversion qualifying the result does not prove native acceleration.
Record the path actually used, temporary storage, CPU/toolchain and all L38 costs.
No reduction, matrix multiply, accumulation width, autodiff rule or training
policy is selected by this cast contract.
