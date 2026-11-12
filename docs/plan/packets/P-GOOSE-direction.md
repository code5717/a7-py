# Goose-informed A7 preparation

Status: research and design preparation. No production memory mechanism, new
syntax or changed language behavior is approved by this packet. Zig remains the
backend. C export and TinyCC integration are deferred.

The user requested Goose's feature outcomes and then asked for deep research of
aardappel/goose. The [research report](../research/goose-2026-10-17.md) reconciles
the specification, implementation, fixtures and performance claims at one
revision. This packet defines proposed acceptance contracts. The current task
list remains in the [delivery roadmap](../delivery-roadmap.md) and
[STATUS](../../STATUS.md).

## Preserve these decisions

- L37 permits runtime memory help without selecting a mechanism. Add data stacks
  to the comparison; do not discard arena/RC evidence or select tracing.
- L38 requires each equivalent workload's median runtime and peak live memory
  to be at most 1.10 times reviewed C, including bookkeeping.
- L42 makes growable-list assignment share identity. Goose's value-copy rules
  must not replace that decision.
- L68 selects canonical Result/Option and the stdlib architecture. A nonlocal
  error mechanism needs a separate compatibility decision.
- L74 invalidates deleted allocations and their aliases. Same-address slot reuse
  must not make a deleted alias valid again.
- Source recursion remains banned; new compiler analyses and validators use
  explicit stacks/worklists. Sizes and indices remain usize.
- GPU execution remains deferred. This preparation chooses no GPU memory,
  tensor ownership, FFI resource or concurrency policy.

## Proposed architecture

The frontend should retain ownership and representation facts until lowering,
rather than asking Zig to recover them from pointers.

1. Typed operations identify allocation identity, root sets, initialized bytes,
   copy/alias/consume effects and cleanup edges.
2. A placement analysis assigns simultaneous owners to regions and records
   return destinations and nested construction constraints.
3. A layout description distinguishes fixed stride, variable sequential values,
   offsets and external-resource handles.
4. Zig lowering consumes the checked plan and emits explicit destination and
   region operations. It keeps checks required by the selected A7 contract in
   every supported profile.
5. A verifier checks the plan before code generation; qualification measures the
   generated program rather than only the analysis result.

This is a proposed internal design. It does not settle the public collection
API or require changing all existing layouts. Implementation must fit the
approved typed-IR work rather than introduce a second conflicting IR.

## Candidate experiments and exit conditions

| Candidate | Concrete workload | Required observations before a decision |
| --- | --- | --- |
| Root and stack placement | Two simultaneous growers; sequential scratch scopes; a returned container; aliases through branches and calls | Deterministic region assignments; rejected escaping/shrunk/deleted aliases; valid independent owners preserved; finite analysis |
| Zig data-stack runtime | Append while retaining typed element references; restore nested scopes; repeat long-running churn | Every retained value remains correct; region/committed/RSS/live-byte counts; reservation refusal, reduced actual capacity, later commit failure and cleanup; no hidden per-element allocation |
| Compact values and ADTs | Same logical records in fixed and variable layouts; mixed variants; separate optional index | Independent decoded oracle; exact offsets and lengths; index cost included; incompatible variant replacement rejected |
| Relative-link images | Explicit versioned record image with cycles and links of selected widths | Iterative validation; malformed tag/length/interior link/overflow rejected before exposure; bounded work; schema and endian contract |
| Fresh-result construction | Nested constructors into a container, selected branches, returned locals and early failure | Initializers once in defined order; explicit copy paths; final destination identity; bytes copied; partial cleanup once |
| Static callbacks | Known and runtime-selected callbacks with the same constrained generic body | Saved-target behavior and diagnostics unchanged; direct dispatch only where proven; code-size/compile-time budget |
| Isolated transfer | Two same-typed channels, owned flat records, failed start/send and parent shutdown | Distinct channel identity; backpressure; payload retained on failure; child cleanup; no borrowed memory shared across workers |
| Error/control propagation | Nested fallible calls with inner and outer cleanup, indirect callbacks and module boundaries | Exact cleanup/event traces; target validity; Result compatibility; no implicit crossing of foreign or worker boundaries |

These experiments are not implementations or completed results. A small fixed
record cannot stand in for nested dynamic ownership. A successful sequential
memory prototype cannot qualify concurrency. Inspect optimized code where the
claim concerns eliminated copies or retained work.

## Compatibility examples to settle

These examples identify existing A7 behavior that a new design must preserve
unless a later explicit decision changes it. They are contract examples, not a
new set of executed probes.

An inferred reference binding aliases an allocation:

```a7
p := new i32
if p == nil { ret }
q := p
del p
// q must not regain validity if storage at p's old address is reused.
```

A saved runtime callable retains its original target:

```a7
first :: fn(x: i32) i32 { ret x + 1 }
second :: fn(x: i32) i32 { ret x + 2 }
main :: fn() {
    f := first
    saved := f
    f = second
    // saved(40) is 41; f(40) is 42.
}
```

Compact storage must distinguish these desired outcomes before choosing syntax:

| Operation | Proposed requirement | Decision still needed |
| --- | --- | --- |
| Append to a stable growable collection | Existing element references keep identity and values | Placement, failure and reference validity across replacement/shrink |
| Assign a growable list to another binding | Retain L42 shared identity | Owning root representation and explicit-copy spelling |
| Append a freshly parsed record | Construct in its receiving storage where the selected guarantee applies | Capacity failure, rollback, ordering and allowed relocation |
| Save/load a relative-link image | Validate bytes before typed access | Schema version, widths, validation budget and public API |
| Propagate an error through nested calls | Preserve cleanup and observable error values | Existing Result propagation, inferred propagation or separately approved nonlocal return |
| Send a value to a worker | Sender cannot retain an unauthorized reference into worker-owned storage | Copy versus transfer, variable buffers, failed-send ownership and shutdown |

Do not use Goose's public reference spellings in A7 examples. The scalar-read
proposal P-REF remains its own pending decision; this research does not approve it.

## Measurement contract

Use the established memory workloads and add an independent-lifetime workload:
open two buffers, grow both, close the older one, keep the younger alive, then
repeat. Include actual retained text and actual reference graphs; integer-ID
and byte-buffer proxies remain labeled.

Use the same inputs, algorithms, required identity, outputs and failure contract
in the C controls. Compare layouts separately from memory mechanisms. Include
alignment-sensitive numeric kernels and account for any compact-to-compute copy.
Keep virtual reservation, commitment, peak live bytes and RSS as separate metrics.

Record exact source/tool/binary hashes, every warmup and measured result,
independent expected output, full raw samples, complete failure accounting and
idle-host qualification. Preserve the roadmap's five warmups and thirty measured samples.
A geometric mean cannot hide a failed workload. No new performance promise is
made by this packet.

## Decisions required before production work

The first decision should specify lifetime/placement rules and allocation-failure
behavior, including whether independent owners need a fallback and how that cost
is charged. Its proposal must show accepted and rejected A7 programs and the
new/deletion migration, if any.

Later decisions cover compact-layout mutation/indexing, relative-image APIs,
construction guarantees, transferability/channel lifecycle and nonlocal control.
Each names compatibility impacts and tests. A changed lifetime rule must preserve
valid controls; a backend optimization must preserve current behavior.

The candidate phases in the roadmap keep these decisions separate. No blanket
approval to copy Goose's syntax, restrictions, benchmark thresholds or runtime
failure policy is requested here.
