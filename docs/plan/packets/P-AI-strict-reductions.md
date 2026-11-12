# Strict tensor reductions

Status: unapproved arithmetic proposal. This defines default sum, dot and matrix
product behavior for the pending tensor API. It does not select an optimized
kernel, relax L38's cost limits or qualify CPU AI. L16 already requires strict
arithmetic by default and explicit opt-in for result-changing optimization.

## Why an explicit contract is needed

Current `std/tensor` imports fail with exit 3, as recorded by the
[current probes](../../../tmp/v1-completion-2026-10-07/tensor-current-probe/REPORT.md).
There is no implemented tensor reduction to preserve. Fixed-array and scalar
semantics remain unchanged by this proposal.

The [exact arithmetic witnesses](../../../tmp/v1-completion-2026-10-07/tensor-reduction-oracles/vectors.json)
show that several plausible implementations disagree. These are independently
derived mathematical results under nearest-even rounding, not A7 executions.

| Input and format | First computation | Different computation |
| --- | --- | --- |
| F32 `[16777216, 1, -16777216]` | Left-associated sum gives positive zero | Right-associated sum gives 1 |
| F16 `[2048, 1, -2048]` | F16 left accumulation gives positive zero | F32 left accumulation gives 1 |
| BF16 `[256, 1, -256]` | BF16 left accumulation gives positive zero | F32 left accumulation gives 1 |
| F32 `(1 + 2^-23) * (1 - 2^-23) - 1` | Separate multiply/add gives positive zero | Fused multiply-add gives `-2^-46` |

At each first row's large positive endpoint, adding one is a halfway case in
the indicated narrow accumulator. For the final row, the exact product is
`1 - 2^-46`; rounding that product separately removes the difference before
subtraction. A shared dtype name does not settle either ordering or contraction.

## Proposed operations and output types

Use module free functions returning canonical `Result(Tensor, TensorError)`:

| Operation | Shape rule | Traversal for each output |
| --- | --- | --- |
| `tensor.sum_all(value)` | Any rank, scalar output | Source logical row-major order |
| `tensor.dot(left, right)` | Both rank one, equal lengths, scalar output | Paired coordinates in increasing index order |
| `tensor.matmul(left, right)` | Both rank at least two; matching inner dimension; broadcast-compatible leading batch axes | Increasing shared inner index for each output coordinate |

For matmul, shapes `[..., M, K]` and `[..., K, N]` produce `[..., M, N]`.
Leading axes broadcast by the pending value packet's equal-or-one rule. Rank-one
promotion is not implicit; callers explicitly reshape. Shape incompatibility
returns `shape_mismatch`. Dot and matmul require the same input dtype; mismatch
returns `dtype_mismatch` rather than silently promoting mixed inputs.

| Input dtype | Product/accumulator dtype | Output dtype |
| --- | --- | --- |
| F16 | F32 | F32 |
| BF16 | F32 | F32 |
| F32 | F32 | F32 |
| F64 | F64 | F64 |

For low-precision inputs, widen each operand exactly before multiplication or
addition. There is no final implicit narrowing. A caller can request a separate
explicit conversion under the pending [cast contract](P-AI-tensor-casts.md).
This table does not define elementwise arithmetic or convolution accumulation.

## Proposed strict computation

Each output starts with positive zero in the accumulator dtype. Sum adds one
element at a time in the stated order. Dot and matmul first multiply the widened
operands and round the product to the accumulator dtype, then add that product
to the running accumulator and round again. Each rounding is nearest-even.
No reassociation, contraction into FMA, reduced-precision multiplication or
flushing of subnormal inputs/results is permitted by default.

Logical order is independent of physical layout. A transpose or broadcast view
must compute the same result as its row-major materialization. Batch scheduling
and computing independent output elements in parallel are permitted if each
element retains this computation. A parallel reduction tree that changes bits
requires an explicitly approved alternative policy.

Empty sums and zero-length dots produce positive zero. Matmul with `K = 0`
produces positive zero at every existing output coordinate. Zero-sized output
axes produce an empty tensor; no nonexistent element is read. A rank-zero sum
still performs the specified addition to initial positive zero, so summing a
scalar negative zero yields positive zero under nearest-even rules.

Infinity and NaN are ordinary values. Finite overflow becomes signed infinity.
Invalid operations such as infinity times zero or opposite infinities added
produce a canonical positive quiet NaN: F32 `0x7fc00000`, F64
`0x7ff8000000000000`. A NaN operand also yields that canonical result for the
affected output. These NaN encodings are proposed observable policy, not an
assumption about native propagation. No caller floating-point rounding mode,
status flags or traps are exposed through these operations.

## Failure and compatibility rules

For binary operations, validate dtype agreement, rank, contraction dimensions
and batch compatibility in that order. Then check output count and byte size
before allocation. Sum validates its output size before allocation. Input
handles must already satisfy the value contract; callers cannot forge them.
Allocation failure leaves inputs unchanged and publishes no partial output.
Numerical infinity or NaN is a successful value, not an allocation or shape error.

The implementation may reuse inaccessible storage only when it preserves the
immutable value contract and every live alias or saved AD value. This packet
does not approve a memory mechanism or AD mutation rule. Existing A7 scalar
arithmetic, casts, fixed arrays and command exit codes remain unchanged.

## Complete proposed example

With successful construction and reduction, this proposed program prints `0`.
Reassociating its F32 reduction could print `1`, which the default contract rejects.
The empty coordinate list addresses the scalar result. The code is a future API
example, not a currently executable tensor program.

```a7
io :: import "std/io"
tensor :: import "std/tensor"

main :: fn() {
    data: [3]f32 = [16777216.0, 1.0, -16777216.0]
    shape: [1]usize = [3]
    scalar_index: [0]usize = []
    match tensor.from_f32(data[0..3], shape[0..1]) {
        case .ok(value): {
            match tensor.sum_all(value) {
                case .ok(total): {
                    match tensor.at_f32(total, scalar_index[0..0]) {
                        case .ok(number): io.println(number)
                        case .err: io.println("read failed")
                    }
                }
                case .err: io.println("sum failed")
            }
        }
        case .err: io.println("creation failed")
    }
}
```

## Alternatives and required evidence

A second policy could permit specified reduction trees or FMA with selected
accuracy bounds. It needs an explicit API opt-in, exceptional-value rules,
per-operation tolerances and native evidence. A backend name or release profile
is not that opt-in. No relaxed policy is approved by this packet.

Default strict behavior may limit which established kernels can be used directly.
Measure that cost against a reviewed equivalent C implementation with the same
arithmetic order and contraction policy. Do not compare one arithmetic contract
against another and call the difference compiler overhead. L38 remains unchanged;
an unqualified cost result is a blocker, not permission to relax the operation.

Acceptance must include the witnesses above, exact small products, all input
dtypes, special values and signed zeros, empty axes, transposed/broadcast views,
batch broadcasting, shape/dtype rejection priorities, allocation failure and
cross-profile native results. A mathematical oracle and parser acceptance cannot
qualify an A7 kernel. The full V1 still requires established-kernel integration,
AD, classifier/decoder training, checkpoint continuation and separate inference.
