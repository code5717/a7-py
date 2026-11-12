# Scalar-reference reads

Research date: 2026-10-16. Recommendation only; no scalar-read language change
is approved or implemented. The user requested deeper research on P-REF.
The [revised decision packet](../packets/P-REF-scalar-read.md) contains the
proposed contract and compatibility examples.

## Recommendation

Add one checked scalar load wherever a specified operation consumes a scalar.
Keep reference creation, rebinding, ref-typed arguments and comparisons
reference-based. Unconstrained inferred generic arguments retain reference types.
An inferred binding remains an alias; an explicitly scalar binding takes a copy:

```a7
q := p          // Alias, as today.
v: i32 = p      // Proposed checked scalar copy.
io.println("{}", p) // Proposed value print.
```

Require non-nil and live-allocation proof at every load, including loads inside
functions with ref parameters. Preserve existing numeric conversion rules.
Do not introduce public dereference syntax, pointer arithmetic, recursive loads,
new memory management or automatic conversions that satisfy generic constraints.

Compared with the earlier packet, keep all reference comparison rules unchanged.
`p == q` compares identity, `p == nil` compares nullness, mixed reference/scalar
equality stays rejected, and references do not acquire ordering. Use a typed
scalar copy for value comparisons. Arithmetic has no reference-arithmetic meaning
in this proposal, so `p + 1` and `p + q` can consume scalar loads.

This deliberately separates arithmetic from reference comparison. It preserves
existing identity checks and avoids a new mixed equality relation where two
references can each equal 5 but differ from each other. A print-only patch would
leave ordinary scalar reads unavailable. Making all reference expressions act
like values would change inferred aliasing and existing identity comparisons.

## What current A7 establishes

The earlier packet reproduced typed copy and arithmetic rejection. Current
source still lowers a scalar write as a dereference but passes the reference
itself to ordinary printing. The strict `heap_scalar_write_through` test retains
its expected failure. It is not evidence that a general scalar-read mechanism
already exists.

This research ran 12 compile-only probes against the current compiler. The
record preserves 34 compiler source hashes before and after, five import origins,
commands, raw streams and generated Zig identities. Owner 2159 terminated with
exit 0 after recording individual compiler outcomes. No native program ran.

| Probe | Observed result | What this establishes |
| --- | --- | --- |
| Print a ref parameter, called with literal nil | Exit 0; emits reference printing | A ref parameter is not an unconditional non-nil boundary |
| Guard ref parameter, then return it as i32 | Exit 6, return type mismatch | The scalar return conversion is absent |
| Rebind a local ref to another ref | Exit 0 | Current local reference assignment must remain distinct from scalar copying |
| Rebind a ref parameter to another ref | Exit 6, immutable binding | Parameter-binding restrictions must remain |
| Typed scalar copy, then delete source | Exit 6, type mismatch | Current rejection precedes lifetime analysis of a new load |
| Print after deletion | Exit 6, use after move | Existing lifetime checks still matter even before the proposal |
| Short-circuit expression comparing ref i32 to zero | Exit 6, operator mismatch | Comparison rejection; no load or short-circuit proof established |
| Scalar argument before or after a deleting argument | Both exit 6, argument mismatch | These probes do not establish safe evaluation ordering |
| Generic equality with ref arguments | Exit 6, unconstrained operator | It cannot serve as a passing generic equality control |
| Generic equality with mixed ref/scalar arguments | Exit 6, constraint/operator and binding errors | Do not silently retry inference with loaded scalar types |
| Print a reference held in a struct field | Exit 0; emits reference printing | Coverage must include expression occurrences beyond local identifiers |

The first probe invocation used `python -m a7`, which has no `__main__`.
That startup failure is preserved separately. The corrected invocation calls
`a7.cli.main`; source and import-origin checks describe that actual run.
Raw evidence remains in `tmp/scalar-reference-research-2026-10-16/probes/`.

## What other languages clarify

C# ref locals read and write the referent, while alias creation and rebinding
use explicit `ref` forms. Transparent scalar access is coherent when aliasing
has a distinct spelling. A7's existing inferred alias syntax means adopting
that entire model would change accepted programs. See Microsoft's
[reference-variable documentation](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/statements/declarations#reference-variables)
and [ref assignment](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/assignment-operator#ref-assignment).

Rust defines specific coercion sites, including typed bindings, call arguments,
returns and typed aggregate fields. Its deref coercion usually converts one
reference type to another; it is not a general reference-to-scalar copy rule.
The useful precedent is to define conversion sites precisely. See the
[Rust Reference](https://doc.rust-lang.org/reference/type-coercions.html).

Rust reference equality compares referent values; `ptr::eq` compares addresses.
A7 already uses reference identity for equality. Copying Rust's equality rule
would therefore be a compatibility change beyond repairing scalar reads.
See [Rust pointer equality](https://doc.rust-lang.org/core/ptr/fn.eq.html).

Zig distinguishes optional unwrapping from pointer dereferencing. A7 already
emits optional pointers, so a scalar read requires both a non-nil proof and
access to the referent. Zig's runtime checks cannot replace A7's semantic
rejection contract. See the versioned
[Zig 0.16.0 reference](https://ziglang.org/documentation/0.16.0/#Optional-Pointers).

These are comparisons, not authority for A7 behavior. Some direct web opens
failed; indexed official documentation and the independent review supplied the
cited sections. No claim depends on a third-party tutorial or executing these
other languages.

## Three problems the implementation must solve

### Reference parameters carry obligations

SPEC section 6.3 states that references cross calls without a boundary unwrap.
Guarded nil calls are allowed. The old packet's claim that ref parameters already
have a non-nil boundary proof was wrong and has been corrected.

Safety currently seeds some parameter facts optimistically, then relies on
caller and reachable-use analysis. Adding a DEREF node alone could consume that
assumption without adding the corresponding caller obligation. Each new load
must be covered by a local proof or a sound call requirement. Test literal nil,
wrappers, saved callable aliases and conditional reads. A callee that returns
before touching a nil argument must remain valid.

### A load needs its own typed occurrence

`a7/ast_nodes.py` already has an internal `DEREF` node. The type checker, safety
pass and Zig backend already traverse it. Use that representation for each
approved consuming occurrence before safety runs. Keep the original reference
child and its type intact; changing the identifier's type globally would turn
aliases into values and corrupt nil checks.

The backend should emit a checked load and select the scalar formatter from its
result type. It must not guess when to dereference inside the printing helper.
Every inserted node must keep a source span, scalar type and proof identity.
Use the existing iterative worklists and preserve the empty recursion allowlist.

Generic bodies can be shared across instantiations. A load selected for one
instantiation must not mutate another instantiation's AST. First investigate an
instance-specific conversion record within the existing generic machinery.
If that cannot represent the obligations, use instance-owned typed expressions;
do not add broad cloning infrastructure without that evidence. Test the same
function with scalar and reference instances in both call orders.

### Loading and borrowing happen at different times

A scalar argument captures the value when that argument is evaluated. A ref
argument preserves access to storage, which a later argument may change.
An effectful reference-producing expression must execute once. Short-circuit
operators load only reached operands, and matching loads its scrutinee once.
Deferred expressions use cleanup-time state. A nil fact cannot revive a deleted
allocation, and a copied scalar remains valid after its source is deleted.

A7's existing left-to-right argument rule remains authoritative. This research
does not approve the separate callable-selection proposal P-CALL. Generated Zig
text alone cannot prove sequencing; native side-effect controls must verify it.

## Proposed acceptance boundary

The packet includes concrete scalar destinations, typed aggregate elements,
scalar function results and arguments, arithmetic and unary operations, casts,
indices and slice bounds, bool conditions, scalar matching and printing. Typed
conditional branches load only the selected branch. Inferred aliases, aggregate
elements and generic parameters retain their inferred reference types. Do not
invent a common scalar type by loading references to reconcile incompatible
inferred branches or generic arguments.

Verification must cover successful copies and aliases, both comparison domains,
all scalar families, nil and deleted reads, guarded nil calls, generic instance
isolation, ordered call effects, compound assignments and deep traversal.
Unsafe cases must fail semantic stage 6. Valid native cases must pass Debug,
ReleaseSafe and ReleaseFast. Remove the original strict xfail only after those
requirements pass; a formatter-only repair cannot close the contract.

Three independent built-in reviewers covered language precedent, compiler
feasibility and adversarial cases. Their local reports are preserved beside the
probes. External GLM review remains unavailable because of the recorded OpenCode
log permission failure. No scalar-read implementation, full gate or native
acceptance is claimed by this research. The user must approve the revised
behavior under AGENTS.md before dependent compiler edits.
