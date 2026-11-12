# Tensor values, shapes and views

Status: unapproved value-contract proposal. This packet selects no compiler or
runtime implementation. It is a prerequisite to full CPU AI, not a substitute
for training, inference, AD, checkpoint recovery or the required workloads.

## Current behavior and authority

[SPEC section 9](../../SPEC.md#9-planned-array-programming-for-ai) labels tensor
APIs, broadcasting and AD as proposals. The inspected
[default registry](../../../a7/stdlib/__init__.py) registers io and math, not a
tensor module. The [current probes](../../../tmp/v1-completion-2026-10-07/tensor-current-probe/REPORT.md)
on frozen `de578138` reject `std/tensor` with exit 3, `ImportError` at 1:1,
in semantic and compile modes. A fixed-array F32 access control passes both.
All 1,664 source hashes and modes remain unchanged; no native execution ran.

[Ledger L7-L11 and L73](../decisions.md) require CPU-first A7-owned tensor/AD
semantics, classifier and decoder training/inference, checkpoint recovery and
four tensor formats. L16 preserves IEEE values and strict arithmetic. L68 adopts
module free functions, explicit imports and canonical `Result`/`Option`.
None of those decisions selects the value and view rules below. The
[CPU AI boundaries](../research/cpu-ai-contract-boundaries.md) and
[AI research](../research/ai-frameworks-codex.md#5-mixed-precision) identify the
remaining numerical and workload decisions.

## Proposed public model

Import `tensor :: import "std/tensor"`. No methods, new keywords or implicit
imports are proposed. `tensor.Tensor` is an opaque, automatically retained handle
to an immutable tensor value. Assignment, argument passing, return and result
binding retain that value; they do not deep-copy elements or consume the source.
Copying the descriptor shares immutable backing. This is proposed tensor
semantics, not an inference from adopted shared-list identity. Users do not call
`del` or track cleanup obligations for tensors. Every view keeps the storage
needed to observe its elements alive after the source handle leaves scope.
An empty view need not retain inaccessible element storage.

Only module operations create handles. User code cannot construct a Tensor
record literal, inspect storage fields or forge a handle through an integer
cast. These restrictions apply to the new opaque type, not existing A7 records.

This requires an approved retained-handle rule for opaque library types,
including canonical `Result(Tensor, TensorError)` payload binding. Current
by-value string rejection does not establish that rule. Approval of this contract
would select tensor handle behavior only, not general consuming-match semantics.
It must not silently change ordinary records, fixed arrays, refs or slices.

`tensor.DType` has four proposed exported constants: `tensor.F16`, `tensor.BF16`,
`tensor.F32` and `tensor.F64`. They describe element storage formats of 16, 16,
32 and 64 bits. They do not introduce scalar `f16` or `bf16` syntax. Tensor
format support remains required across the later numerical contract; zero-filled
construction alone does not qualify four-format computation.

Rank, extents, element counts, axes, coordinates, slice bounds and steps use
`usize`. Rank is dynamic and has no fixed eight-dimension cap. Resources and
representable metadata remain finite. Construction reports failure rather than
silently truncating rank or extents.

## Proposed operations

Signatures in this table describe future APIs, not accepted declarations.
`shape`, `order`, `coordinates` and `target` are read-only inputs of type `[]usize`.
The functions copy any metadata needed after return and do not retain caller
array/slice storage. Operations returning `Result` use `.ok`/`.err`; `Option`
uses `.some`/`.none`.

| Operation | Proposed result and meaning |
| --- | --- |
| `tensor.zeros(dtype, shape)` | `Result(Tensor, TensorError)`; new contiguous row-major positive-zero value |
| `tensor.from_f32(data, shape)` | `Result(Tensor, TensorError)`; copy `[]f32` bits into an F32 tensor; exact element-count match required |
| `tensor.from_f64(data, shape)` | Same rule for `[]f64` and F64, without narrowing |
| `tensor.rank(value)` | `usize`, number of axes |
| `tensor.count(value)` | `usize`, logical element count |
| `tensor.dtype(value)` | `DType`, unchanged by view operations |
| `tensor.dim(value, axis)` | `Option(usize)`; `.none` when axis is outside the rank |
| `tensor.at_f32(value, coordinates)` | `Result(f32, TensorError)`; F32 only, no implicit cast |
| `tensor.at_f64(value, coordinates)` | Corresponding F64 observation |
| `tensor.transpose(value, order)` | `Result(Tensor, TensorError)`; read-only axis-permutation view |
| `tensor.slice(value, axis, start, stop, step)` | `Result(Tensor, TensorError)`; positive-step half-open view |
| `tensor.reshape(value, target)` | `Result(Tensor, TensorError)`; view under the precise layout rule below; never copies elements |
| `tensor.broadcast_to(value, target)` | `Result(Tensor, TensorError)`; read-only logical expansion with possible overlapping storage |
| `tensor.materialize(value)` | `Result(Tensor, TensorError)`; independent contiguous row-major element copy, even when input is already contiguous |

The exact representation of the dtype constants and error type is part of this
proposed module API. No public storage pointer, writable element accessor,
reference-to-element operation or in-place mutation is included. Low-precision
import/export and conversion operations require the separate cast/precision
contract; this packet does not invent conversion through a host double.

## Shape and layout rules

A rank-zero tensor has empty shape and exactly one element. Its coordinate list
is empty. A shape containing a zero extent has zero elements. Coordinates into
any zero extent fail bounds checking. Empty tensors still retain their dtype and
full shape. They do not permit reading uninitialized storage.

Element count is the mathematical product of extents; the empty product is one.
A zero extent makes the product zero regardless of the other extents. Validate
metadata before arithmetic, and detect zero before multiplying count dimensions.
For a nonempty tensor, every count, byte count, offset and stride computation
needed by the representation must fit `usize`, or return `.size_overflow`.
Empty tensors need no addressable element offsets or fabricated overflowing
strides. Metadata allocation can still fail for an empty tensor.

Constructors use row-major logical order, with the last axis varying fastest.
`from_f32` and `from_f64` preserve input bits, including signed zero and IEEE
special values. Their source length must equal the computed count. Subsequent
writes to the caller's data or shape arrays cannot change the tensor.

Transpose requires an order list containing each source axis exactly once; its
length must equal rank. Result axis `j` corresponds to source axis `order[j]`.
An empty permutation is valid for a scalar. No elements are copied. For a
row-major `[2,3]` tensor containing `1,2,3,4,5,6`, order `[1,0]` produces shape
`[3,2]` and logical order `1,4,2,5,3,6`. Reshaping that view to `[6]` returns
`.layout_incompatible`; materializing it first permits that reshape.

Slice requires a valid axis and `0 <= start <= stop <= extent`, with `step > 0`.
There is no clipping, negative indexing or negative stride. The new extent is
zero when start equals stop; otherwise it is `1 + (stop - start - 1) / step`.
Unchanged axes keep their extents. Chained views compose their mappings and retain
backing lifetime. Element access follows that mapping once per requested value.

Reshape requires equal element counts. For this proposed initial contract,
layout-compatible means the source's logical row-major traversal is one contiguous
sequence in backing storage, ignoring axes of extent one. Its starting offset
may be nonzero. Any zero-element source may reshape to any zero-element target.
A scalar follows the same one-element rule. Other layouts return
`.layout_incompatible`, even if some more general strided reshape could exist.
`materialize` followed by `reshape` is the explicit copy alternative. This rule
must be public; an implementation cannot silently add a copy to make reshape pass.

Broadcast aligns source and target axes from the right. Target rank must be at
least source rank. Each aligned source extent must equal its target or be one;
missing leading source axes act as one. Thus one may expand to zero, while zero
may match zero but cannot expand to a positive extent. Scalar broadcast follows
the same rule. Expanded axes may share an element address, but no writable view
is exposed. Result count and representation arithmetic remain checked.

`materialize` preserves dtype, shape and every logical element's bits. Nonempty
output has independent backing; empty output needs no distinct allocation.
Private kernel packing later must not alter this observable value contract.

## Errors and publication

Proposed copyable `TensorError` variants are `invalid_dtype`, `invalid_axis`,
`invalid_permutation`, `invalid_slice`, `shape_mismatch`, `size_overflow`,
`layout_incompatible`, `dtype_mismatch`, `index_out_of_bounds` and
`allocation_failed`. An error has no partially published tensor. Input handles
and caller arrays remain unchanged. Temporary storage is reclaimed automatically.

An axis outside `[0, rank)` returns `.invalid_axis`; transpose length mismatch
or a repeated valid axis returns `.invalid_permutation`. During transpose order
validation, length is checked first, then entries in order for range and duplicates.
Slice bound/step failures return `.invalid_slice`. Signed negative-axis shorthand
is not proposed. A non-`usize` axis variable is a type error, not an implicit cast.

Check argument metadata in parameter order before allocating. Constructors check
the element count, then source length where applicable, then byte count.
Reshape computes the checked target count first, compares it with source count,
then tests layout. Thus reshaping one element to `[usize_max, 2]` reports
`.size_overflow` rather than `.shape_mismatch`. Broadcast checks rank and aligned
extent compatibility before computing its result count and layout. View offset
and stride arithmetic follow the operation's axis, permutation or slice checks.
For element reads, check dtype, then coordinate count, then coordinates in axis
order; a coordinate-count mismatch returns `.shape_mismatch`. Tests must pin
these priorities where multiple conditions fail. Failures evaluating argument
expressions occur before the operation and are not rolled back.

Queries `rank`, `count` and `dtype` do not allocate. `dim` uses `Option` for absence,
not a sentinel. Invalid access does not panic or return a fabricated element.
No fixed rank cap or memory threshold is selected by this proposal.

## Complete proposed examples

These are future API examples using A7-shaped syntax. They are not current
semantic or native qualification. Parent parser-only checks, if recorded later,
can establish grammar acceptance only. Canonical `Result`/`Option` need no user
declarations. Handle payload binding depends on the retained-handle rule above.

The zero factory creates a 2-by-3 F32 tensor. Success prints `2 6`, then `3`.
Resource failure prints the error message instead.

```a7
io :: import "std/io"
tensor :: import "std/tensor"

main :: fn() {
    shape: [2]usize = [2, 3]
    match tensor.zeros(tensor.F32, shape[0..2]) {
        case .ok(value): {
            io.println("{} {}", tensor.rank(value), tensor.count(value))
            match tensor.dim(value, 1) {
                case .some(extent): io.println(extent)
                case .none: io.println("missing axis")
            }
        }
        case .err: io.println("tensor creation failed")
    }
}
```

The copy constructor preserves `1` after the caller overwrites its first element
with `9`. Transposing a 2-by-2 tensor makes coordinate `[0,1]` read source `[1,0]`,
which is `3`. On successful creation and view construction it prints `1`, `3`,
then `missing axis`. Each fallible read and construction has an error arm.

```a7
io :: import "std/io"
tensor :: import "std/tensor"

main :: fn() {
    data: [4]f32 = [1.0, 2.0, 3.0, 4.0]
    shape: [2]usize = [2, 2]
    match tensor.from_f32(data[0..4], shape[0..2]) {
        case .ok(value): {
            data[0] = 9.0
            origin: [2]usize = [0, 0]
            match tensor.at_f32(value, origin[0..2]) {
                case .ok(element): io.println(element)
                case .err: io.println("read failed")
            }
            order: [2]usize = [1, 0]
            match tensor.transpose(value, order[0..2]) {
                case .ok(view): {
                    position: [2]usize = [0, 1]
                    match tensor.at_f32(view, position[0..2]) {
                        case .ok(element): io.println(element)
                        case .err: io.println("view read failed")
                    }
                }
                case .err: io.println("transpose failed")
            }
            match tensor.dim(value, 2) {
                case .some: io.println("unexpected axis")
                case .none: io.println("missing axis")
            }
        }
        case .err: io.println("tensor creation failed")
    }
}
```

## Compatibility, alternatives and acceptance

Existing arrays, slices and scalar arithmetic retain their behavior. The new
`std/tensor` module does not claim the local bare import `tensor`. No API silently
casts input data, deep-copies a view or exposes mutation. A copy-on-construction
contract costs storage and copying; a borrowing constructor would need a separate
caller-mutation/lifetime contract. Implicit-copy reshape would be more permissive
but would hide allocation and failure; this proposal requires explicit materialize.

Required value-contract acceptance after approval includes rank-zero and empty
values; ranks beyond eight; checked count/byte/offset overflow; exact constructor
length errors; copied data and metadata; all four dtype tags; signed-zero and
special-value bit preservation for F32/F64 input; permutations and positive slices;
chained views surviving source scope exit; compatible and rejected reshapes;
explicit materialization; scalar/zero-extent broadcasting; invalid axes and
coordinates; and injected allocation failures without partial publication.
Native checks must verify values and backing lifetime, not only emitted shape
metadata. Lifetime reclamation and repeated create/view/drop loops need actual
resource evidence once the runtime mechanism is selected.

The proposed value rules are concrete, but the retained opaque-handle rule and
its generic Result binding must be approved and represented before implementation
can satisfy them. Allocation accounting and cleanup must meet L19 without manual
user actions. No allocator, collector, reference-count design or pool policy is
selected here. A passing scalar factory is not general tensor qualification.

Still required in later packets: low-precision casts and observations, operation
and accumulation semantics, mutable parameter updates, AD, optimizer/RNG state,
checkpoint policy, classifier/decoder recipes and thresholds, kernel selection,
native effects and actual CPU performance. L38's adopted cost limits remain in
force. GPU execution remains a separate required milestone subject to its current
deferral. This value packet does not close any of those obligations.
