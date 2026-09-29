> **Source:** Codex CLI external reviewer, memory management and ownership research.  
> **Session:** `codex rollout 2026-09-14T23-11-54 (01a0a18c-3179)`  
> **Date:** 2026-09-14. Recovered 2026-09-15 from temporary output after Plan Mode blocked the original write.  
> **Status:** Advisory. Body preserved verbatim except removal of pre-report narration where noted. User decisions are in the [ledger](../decisions.md).

**A7 full-v1 memory-management and ownership design review**

Date: 2026-09-14. Status: advisory research for planning. No language decision, implementation, or release qualification is approved by this report.

The recommended direction is an affine ownership core with temporary checked access, deterministic cleanup on defined exits, and explicit allocation failure. Arenas should supplement that model. CPU tensors and autodiff need a separate storage-lifetime decision: either a training session owns saved storage, or tensor objects retain explicitly shared storage.

A small source vocabulary is feasible. A small compiler analysis is not. Owned containers, slices, callbacks, deferred cleanup, channels, and native kernels interact through storage identity and lifetime. A checker that tracks only variable names or a single parameter-mode label cannot express the required contract.

This review read the requested A7 documents and relevant ownership research and audit reports. It used primary web documentation, language specifications, research papers, official runtime source, and one built-in research sub-agent. It made no repository changes, launched no external model CLI, and performed no vulnerability tests. Existing GLM findings are attributed evidence, not independently revalidated findings.

The examined checkout has HEAD `701c67936c70ad2b0608326e23e56cc5d38c9fdb` and uncommitted documentation and test changes. `pyproject.toml` declares A7 `0.3.0`; the documented backend is Zig `0.16.0`.

The following directions control this review:

- Integer primitives have explicit widths. Sizes and indices use `usize`; signed pointer-sized differences use `isize`.
- Ordinary integer `+`, `-`, and `*` wrap. Arbitrary-precision `int`, `uint`, and `number` are not planned.
- Scalar floats are `f32` and `f64`. AI tensor formats include `f16`, `bf16`, `f32`, and `f64`. IEEE versus finite-only behavior remains unapproved.
- Argument bindings are immutable. Explicitly permitted referent mutation is approved. Parameter-mode syntax is not approved.
- Source recursion and public address-of or dereference operators remain banned.
- Full v1 includes ownership, concurrency, a fuller standard library, and CPU training and inference with A7-owned tensor and autodiff behavior.
- GPU and broader hardware research do not expand CPU-v1 qualification.

---

The source ledger distinguishes released implementations, rolling documentation, research, and local evidence. All web sources were consulted on 2026-09-14, directly or through the delegated research.

| Subject | Version or evidence boundary | Primary sources and use |
|---|---|---|
| A7 | `0.3.0`; HEAD above plus working-tree changes | [README](/home/cx89/Projects/pl-dev/a7-py/README.md), [SPEC](/home/cx89/Projects/pl-dev/a7-py/docs/SPEC.md), [safety contract](/home/cx89/Projects/pl-dev/a7-py/docs/SAFETY_CONTRACT.md), [decisions](/home/cx89/Projects/pl-dev/a7-py/docs/lang-safety/08-decisions.md). Current documented behavior and historical proposals. |
| Existing A7 audit | 2026-09-14 reports; not rerun | [GLM memory review](/home/cx89/Projects/pl-dev/a7-py/docs/audits/2026-09-14/memory-safety-glm-review.md), [coordinator reconciliation](/home/cx89/Projects/pl-dev/a7-py/docs/audits/2026-09-14/root-review.md), [completion roadmap](/home/cx89/Projects/pl-dev/a7-py/docs/audits/2026-09-14/completion-roadmap.md). Design obligations and evidence limits. |
| Rust | Standard-library pages identify `1.98.1`, revision `48a229cea`; Reference is rolling | [Undefined behavior and aliasing limits](https://doc.rust-lang.org/reference/behavior-considered-undefined.html), [destruction](https://doc.rust-lang.org/reference/destructors.html), [Copy](https://doc.rust-lang.org/std/marker/trait.Copy.html), [pinning](https://doc.rust-lang.org/std/pin/index.html), [versioned Rc source](https://raw.githubusercontent.com/rust-lang/rust/1.98.1/library/alloc/src/rc.rs). |
| Rust alias-model research | PLDI 2025 | [Tree Borrows project and paper](https://plf.inf.ethz.ch/research/pldi25-tree-borrows.html). Research model and proof scope, not a completed Rust language specification. |
| Zig | `0.16.0` | [Language documentation](https://ziglang.org/documentation/0.16.0/), [release notes](https://ziglang.org/download/0.16.0/release-notes.html). Shipped `Allocator.zig` and `ArenaAllocator.zig` were also read in the existing local toolchain. |
| Odin | Rolling documentation and `master`; no release pin established | [Overview](https://odin-lang.org/docs/overview/), [allocator source](https://raw.githubusercontent.com/odin-lang/Odin/master/core/mem/allocators.odin). Context, manual allocation, arena and failure conventions. |
| Swift | Released baseline `6.3.3` | [Release announcement](https://forums.swift.org/t/announcing-swift-6-3-3/87888), [memory safety](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/memorysafety/), [versioned exclusivity runtime](https://raw.githubusercontent.com/swiftlang/swift/swift-6.3.3-RELEASE/stdlib/public/runtime/Exclusivity.cpp). |
| Swift ownership evolution | Proposal versions matter | [SE-0377](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0377-parameter-ownership-modifiers.md), [SE-0390](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0390-noncopyable-structs-and-enums.md), [SE-0427](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0427-noncopyable-generics.md), [SE-0429](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0429-partial-consumption.md), [SE-0446](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0446-non-escapable.md). Later proposals supersede some original restrictions. |
| C++ | Current working draft, not a frozen published edition | [Object lifetime](https://eel.is/c++draft/basic.life), [unique ownership](https://eel.is/c++draft/unique.ptr), [construction failure](https://eel.is/c++draft/except.ctor), [allocation](https://eel.is/c++draft/expr.new), [vector invalidation](https://eel.is/c++draft/vector.modifiers). |
| Go | `1.27.1` | [Downloads](https://go.dev/dl/), [versioned GC source](https://raw.githubusercontent.com/golang/go/go1.27.1/src/runtime/mgc.go), [GC guide](https://go.dev/doc/gc-guide), [cgo rules](https://pkg.go.dev/cmd/cgo). |
| Pony | `0.72.1`, released 2026-09-13; pre-1.0 | [Releases](https://github.com/ponylang/ponyc/releases), [capabilities](https://tutorial.ponylang.io/reference-capabilities/reference-capabilities.html), [research](https://www.ponylang.io/learn/papers/), [versioned GC source](https://raw.githubusercontent.com/ponylang/ponyc/0.72.1/src/libponyrt/gc/gc.c). |
| Koka and Perceus | Koka `3.2.3`; research language | [Project](https://github.com/koka-lang/koka), [Perceus paper](https://www.microsoft.com/en-us/research/publication/perceus-garbage-free-reference-counting-with-reuse), [versioned RC source](https://raw.githubusercontent.com/koka-lang/koka/v3.2.3/kklib/src/refcount.c). |
| Val and Hylo | Val is Hylo's former name; evolving implementation | [Introduction](https://hylo-lang.org/introduction/), [specification](https://github.com/hylo-lang/specification/blob/main/spec.md), [former compiler](https://github.com/hylo-lang/hylo), [new compiler](https://github.com/hylo-lang/hylo-new), [mutable value semantics research](https://arxiv.org/abs/2106.12678). |
| Vale | Separate language; site advertises alpha `0.2` | [Project status](https://vale.dev/), [ownership guide](https://vale.dev/guide/structs). Region borrowing and several concurrency features remain advertised as planned. |
| Regions | Tofte–Talpin 1997; later MLKit work | [Original region paper](https://web.cs.ucla.edu/~palsberg/tba/papers/tofte-talpin-iandc97.pdf), [regions with tracing GC](https://elsman.com/mlkit/pdf/tagfreegc.pdf), [MLKit documentation](https://elsman.com/mlkit/doc). |
| Autograd precedent | PyTorch documentation resolves to `2.14` | [Autograd mechanics](https://docs.pytorch.org/docs/2.14/notes/autograd.html). Saved storage and mutation-version precedent only; no proposed dependency on PyTorch. |
| Native tensor exchange | Current DLPack header declares `1.3`; generated docs retain a stale `0.6.0` title | [Official header](https://raw.githubusercontent.com/dmlc/dlpack/main/include/dlpack/dlpack.h), [C API](https://dmlc.github.io/dlpack/latest/c_api.html), [reference DGEMM](https://www.netlib.org/lapack/explore-html/dd/d09/group__gemm_ga1e899f8453bcbfde78e91a86a2dab984.html). |
| Backend alias metadata | Rolling LLVM reference | [LLVM language reference](https://llvm.org/docs/LangRef.html). Optimization contracts must be qualified against the actual backend version. |
| Jai | Insufficient current authoritative evidence established | No ownership guarantee or current syntax recommendation is derived from Jai. Creator demonstrations and community descriptions do not substitute for a versioned specification. |

Attempts to fetch Zig `0.16.0` source through GitHub returned 404. Codeberg retrieval was unavailable through the web tool. The review instead read the existing toolchain's shipped source and checked the official release documentation. That is source inspection, not a fresh toolchain provenance verification.

---

Ownership, allocation, and access are separate choices.

An owner is responsible for a resource's lifetime. A borrow temporarily authorizes access without transferring that responsibility. An allocator supplies storage. A region groups lifetimes. Reference counting and tracing GC reclaim storage according to different reachability rules.

An immutable binding cannot be rebound. That says nothing by itself about whether a referenced object may change. Likewise, read-only access through one reference does not establish global immutability, and neither property establishes `noalias`.

| Model | Lifetime and mutation discipline | Reclamation | Main cost or limitation for A7 |
|---|---|---|---|
| Stack values | Scope or compiler-established temporary lifetime | Scope exit | Escaping access needs rejection, promotion, or another ownership mechanism. Large frames and native calls still need stack qualification. |
| Manual heap | Programmer tracks ownership and aliases | Explicit free | Familiar `new`/`del`, but insufficient for A7's intended static guarantees without additional analysis. |
| Affine ownership | At most one usable owner; temporary access follows separate rules | Explicit drop or generated cleanup | Move, initialization, alias, and control-flow analysis. Some shared structures require another representation. |
| Strict linear ownership | Resource must be consumed exactly once | Explicit obligation | Strong protocol discipline, but burdens error paths, cancellation, and intentionally discarded values. |
| Arena allocator | Allocations remain until reset or arena destruction | Bulk release | An arena alone does not prevent escaped pointers. Coarse lifetimes retain memory; resource finalization is separate. |
| Typed or inferred regions | Types and effects constrain cross-region access | Region end | More analysis and possible annotations. Region lifetimes can be too coarse for long training jobs. |
| Reference counting | Every strong reference extends storage lifetime | Last strong release | Count traffic, cycles, destruction cascades, and possible atomic costs. Mutation still needs a rule. |
| Tracing GC | Reachability preserves storage | Collector scheduling | Runtime work and memory headroom; nondeterministic resource release. Does not prevent data races. |
| Copy-on-write | Shared backing storage until mutation requires separation | Usually RC or another backing owner | Mutation can allocate and fail. Hidden copies conflict with predictable allocation unless exposed. |

The relevant language comparisons reinforce these distinctions.

| Language | Useful precedent | What A7 must not infer |
|---|---|---|
| Rust | Affine moves, shared and exclusive borrows, explicit duplication, structural cleanup | The borrow checker is not a universal proof of bounds, termination, resource availability, or all unsafe-code behavior. |
| Zig | Explicit allocators, fallible allocation, `defer` and error cleanup | Zig does not supply A7's ownership proof. Pointer lifetime remains a programmer obligation. |
| Odin | Immutable parameter bindings, configurable allocation context, containers carrying allocators | Context conventions do not prove that an allocator or its returned storage outlives its users. |
| Swift | Ownership conventions, noncopyable values, exclusivity, nonescapable values | Dynamic exclusivity is not automatically recoverable; class-reference copies do not deep-copy objects. |
| C++ | RAII, move-only resource wrappers, construction rollback | RAII does not prevent dangling borrowed pointers, invalidated iterators, or incorrect object-lifetime operations. |
| Go | Convenient escaping references and cyclic graphs | GC does not provide exclusive mutation, deterministic native-resource cleanup, or hard memory bounds. |
| Pony | Transfer and sharing permissions cover reachable object graphs | Moving a root variable alone does not establish isolated transfer. Channels still need a runtime ownership protocol. |
| Hylo | Mutable value semantics and temporary projections | Restricting stored borrows does not eliminate lifetime reasoning or prohibit owned heap containers. |
| Koka | Precise compiler-inserted RC and uniqueness-based reuse | The published proof and performance results do not automatically apply to A7's mutation, concurrency, or native kernels. |
| Vale | Single ownership with checked reference mechanisms | Alpha and planned features are not evidence of a completed static region system. |

Rust's exact unsafe aliasing rules remain explicitly unsettled in the Reference. Shared references, exclusive references, and `UnsafeCell` have different permissions, but the complete unsafe semantics are not a finished formal contract. Tree Borrows is relevant research that addresses limitations of Stacked Borrows; it is not evidence that A7 can adopt an informal “Rust-like noalias” rule. [Rust aliasing limits](https://doc.rust-lang.org/reference/behavior-considered-undefined.html), [Tree Borrows](https://plf.inf.ethz.ch/research/pldi25-tree-borrows.html).

Rust also makes destruction order observable. Locals generally drop in reverse declaration order, while struct fields drop in declaration order. Partially initialized values drop only initialized fields. A7 needs its own explicit order rather than copying the phrase “Rust-style cleanup.” [Rust destruction rules](https://doc.rust-lang.org/reference/destructors.html).

Zig allocation failure is normally an error result. `defer` and `errdefer` support cleanup, but lifetime correctness remains the caller's responsibility. Version `0.16.0` also adds limited diagnostics for trivial returned local addresses and changes arena allocation concurrency. Neither change constitutes general borrow checking. [Zig memory and errors](https://ziglang.org/documentation/0.16.0/), [0.16.0 changes](https://ziglang.org/download/0.16.0/release-notes.html).

Odin's documentation explicitly defines parameter immutability as inability to assign directly to the parameter. Its context selects default allocators, while dynamic arrays and maps can retain allocator values. These are useful ergonomic precedents, not deep-const or nonaliasing guarantees. [Odin overview](https://odin-lang.org/docs/overview/).

Swift separates noncopyability from nonescapability. Its newer ownership work also restricts partial consumption where destructors or resilient layouts complicate field reasoning. The released `6.3.3` runtime calls `fatalError` for a dynamic exclusivity conflict. A7 would need a different failure contract to make such conflicts recoverable. [SE-0429](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0429-partial-consumption.md), [SE-0446](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0446-non-escapable.md), [Swift runtime source](https://raw.githubusercontent.com/swiftlang/swift/swift-6.3.3-RELEASE/stdlib/public/runtime/Exclusivity.cpp).

C++ distinguishes allocated storage from a live object within that storage. Construction, destruction, union-member activation, and storage reuse affect what operations are permitted. This distinction matters for A7's initialization and native-buffer interfaces even if A7 exposes none of C++'s placement syntax. [C++ object lifetime](https://eel.is/c++draft/basic.life).

Go `1.27.1` implements a concurrent, non-compacting mark-and-sweep collector. Its GC memory limit is soft, and cgo imposes additional provenance and pinning rules. A7 cannot use “GC-managed” as a substitute for native-buffer ownership or CPU-training memory accounting. [Go runtime](https://raw.githubusercontent.com/golang/go/go1.27.1/src/runtime/mgc.go), [GC guide](https://go.dev/doc/gc-guide), [cgo](https://pkg.go.dev/cmd/cgo).

Pony is useful because it distinguishes isolated mutable transfer, immutable sharing, actor-local mutable access, and opaque identity. Those distinctions concern the reachable graph, not merely the outer reference. A7 can adopt the underlying questions without adopting six public capability keywords. [Pony reference capabilities](https://tutorial.ponylang.io/reference-capabilities/reference-capabilities.html).

Hylo's former name is Val. Vale is a different project. Hylo's current compiler transition and Vale's alpha status both require caution when treating their documentation as implementation evidence. Mutable value semantics remains a useful design precedent independently of implementation maturity. [Hylo transition](https://github.com/hylo-lang/hylo), [mutable value semantics research](https://arxiv.org/abs/2106.12678), [Vale status](https://vale.dev/).

---

The existing A7 research needs reconciliation before it can serve as an implementation contract.

| Existing statement | Conflict or missing distinction | Required planning disposition |
|---|---|---|
| D.001 through D.004, D.020 and related conversion tables introduce arbitrary-precision numerics | Superseded by explicit-width types and wrapping arithmetic | Replace their numeric assumptions. Do not preserve them through a generic “accepted research” label. |
| Safety contract requires range proofs for ordinary fixed-width arithmetic | Conflicts with approved wrapping `+`, `-`, `*` | Specify wrapping lowering and wrap-aware analysis. Retain separate checked arithmetic for allocation and layout. |
| SPEC describes IEEE scalar formats; research proposes finite-only behavior | Float behavior is not currently approved | Keep representation choices separate from exceptional-value and arithmetic policy. |
| D.040 permits binding mutation for some modes and treats default access as deeply read-only | Conflicts with immutable argument bindings and unresolved access syntax | State binding immutability independently from referent permissions. |
| D.041 infers a maximum of `borrow < inout < consume` | One label omits escape, globals, callbacks, suspension, allocation, and returned dependencies | Replace with a structured effect and ownership summary. |
| D.043 and cluster summaries say non-Copy arguments move by default | Other sections say default arguments borrow | Choose assignment semantics and call semantics separately. |
| D.049 permits owning `ref T`, but its heading and summary forbid stored references generally | Owning heap references and borrowed references are conflated | Define owner storage, local views, escaping borrows, and handles separately. |
| D.047 says slices cannot be Copy because copying creates aliases | Shared reading can permit aliases; mutable access needs exclusivity | Classify access permissions, not merely pointer-shaped representation. |
| D.046 says automatic cleanup preserves “no leaks” | Cycles, nontermination, abrupt process death, forgotten external obligations, and runtime bugs remain | Promise cleanup on named language exits, with explicit exceptions. |
| D.048 permits unrestricted partial moves | Whole-object destructors may need fields already moved out | Restrict partial moves or define destructor compatibility. |
| D.050 combines task-private heaps and cheap ownership transfer | Allocator state may remain owned by the sending task | Specify allocator lifetime and cross-task deallocation. |
| D.053 derives exact native stack size from the recursion ban | Native kernels, callbacks, generated destruction, ABI frames, and runtime code remain | Treat native stack bounds as a separate target-specific qualification. |
| Parameter research defers cancellation and custom destruction | Full-v1 resource and task behavior still needs a complete lifecycle | Decide supported cancellation and cleanup behavior explicitly. |
| D.024 preserves `cast`; D.038 removes it | Internally acknowledged contradiction | Do not implement either interpretation through ownership work. |
| Old roadmap excludes concurrency and AI | Superseded by current full-v1 scope | Replan dependencies without shrinking v1 silently. |
| Historical comparisons equate missing runtime checks with proof | Absence of checks is not evidence of correct analysis | Require observable requirements, analysis validation, and integrated native evidence. |

The GLM report already records issues involving aliases, deferred deletion, escaping slices, initialization, calls, and indirect recursion. This review uses those categories to identify necessary analyses. It does not validate their vulnerability claims or treat historical compile-only evidence as native runtime evidence. [Existing GLM review](/home/cx89/Projects/pl-dev/a7-py/docs/audits/2026-09-14/memory-safety-glm-review.md).

---

Four coherent alternatives are available. Each is a design choice, not an implementation commitment.

| Alternative | Complete model | Advantages | Costs and compatibility |
|---|---|---|---|
| A. Affine owners with scoped access | Heap owners move; temporary reading or exclusive mutation borrows storage; borrowed views cannot escape their permitted scope; cleanup is automatic on defined exits | Fits current `new`, `del`, ordinary calls, and explicit allocation goals. Works for owned containers and native resources | Existing ref copies change meaning. Local slices need lifetime analysis. Arbitrary observer graphs need handles or explicit sharing |
| B. General borrowed references | Affine owners plus stored and returned borrows with expressible lifetime relationships | Supports zero-copy parsers, borrowed iterators, intrusive APIs, and views that cross function boundaries | Greater type-system and diagnostic complexity. Lifetime relationships must appear somewhere in public interfaces, even if syntax is inferred |
| C. RC-centered value model | Shared backing storage, explicit or implicit retention, mutation through uniqueness or copy-on-write | Convenient escaping tensors and graph-shaped values | Count overhead, cycle policy, mutation allocation failure, and less predictable release costs |
| D. Tracing-GC model with separate resources | Managed object graph; explicit or affine wrappers for files, kernels, and external allocations | Convenient cyclic graphs and broad application programming | Collector/runtime implementation, memory headroom, foreign roots, nondeterministic storage reclamation; concurrency checks remain necessary |

**Alternative A is the best starting point for A7.** It preserves explicit allocation and gives `del` a coherent consuming meaning. It also allows an owned heap reference inside a struct or container. “No escaping borrowed references” must not become “no owned linked structures.”

Arenas can support any alternative. A checked region system can also coexist with GC, as MLKit research demonstrates. These mechanisms are not mutually exclusive language identities. [Typed regions and GC](https://elsman.com/mlkit/pdf/tagfreegc.pdf).

For Alternative A, I recommend evaluating these boundaries:

- Permit local slices whose lifetimes the compiler can establish.
- Initially reject borrowed views stored in independently escaping user aggregates or returned across functions without an approved dependency contract.
- Permit owning heap fields and containers.
- Use checked indices or generation-bearing handles for shared graph relationships.
- Use automatic structural cleanup for owned fields.
- Keep public custom destructor hooks as a separate approval decision.
- Start task transfer with isolated ownership, while deciding immutable sharing separately.
- Provide explicit fallible library operations when dynamic information prevents static proof.

Rejecting all local borrowed values would break ordinary A7 slicing and make the language unnecessarily restrictive. Permitting local views still requires lifetime analysis, even without public lifetime annotations.

The proposed public concepts can remain small:

| Concept | User-facing meaning | Syntax status |
|---|---|---|
| Owner | Responsible for storage or another resource | Existing `ref T` may represent heap ownership, but its overloaded parameter meaning needs resolution |
| Temporary read access | Reads during an established lifetime without taking ownership | No keyword approved |
| Temporary mutation access | Explicit permission to change the referent under exclusivity rules | Existing `ref` examples are precedents; broader mode syntax remains open |
| Transfer | Previous owner becomes unusable; recipient gains responsibility | Assignment and call rules require approval |
| Explicit duplicate | Produces independent contents and may allocate | `clone` is a proposed library concept |
| Explicit share | Retains the same storage under a separate mutation contract | Optional proposal, not equivalent to clone |
| Early release | Ends ownership before normal scope exit | Existing `del`; generalized resource behavior remains open |
| Deferred action | Runs on a defined scope exit | Existing `defer`; capture and move interaction need specification |

The compiler may call its internal categories `Read`, `Mutate`, and `Take`. Those names need not become A7 keywords. Public interfaces nevertheless need a stable way to communicate permissions and ownership effects. Possible forms include declaration syntax, checked attributes, or generated interface contracts. That choice remains with the user.

---

The lifecycle contract must cover more than successful allocation.

| Topic | Proposed obligation | Important consequence |
|---|---|---|
| Allocation failure | Return a failure value before publishing a usable owner | Constructors, clone, container growth, tasks, channels, and tensor operations all need failure paths |
| Allocation arithmetic | Check element-count, byte-count, alignment, and stride calculations | Approved ordinary wrapping arithmetic cannot silently wrap allocation sizes |
| Initialization | Read only initialized fields and valid active payloads | Zero bytes are not a universal valid value |
| Partial construction | Track completed fields and initialized element prefixes | Failure destroys only completed resources |
| Move | Transfer cleanup responsibility without duplicating it | Moved state is an analysis fact, not a readable `nil` value |
| Replacement | Define evaluation and commit order | Prefer constructing a replacement before destroying the old value when failure can occur |
| Partial move | Permit only where remaining fields and cleanup remain well-defined | Initially restrict to plain records without whole-object destruction hooks |
| Copy | Implicit duplication has no ownership bookkeeping or resource duplication requirement | A wrapper around a file descriptor must not become Copy merely because its representation is an integer |
| Clone | Explicit independent duplication with documented failure behavior | Failure leaves the original usable and unchanged |
| Share | Explicit additional ownership of the same storage | Requires cycle, mutation, and cross-task rules |
| Cleanup | Exactly one responsibility for each live resource on every defined exit | Return, branch exit, loop exit, propagation, and cancellation need one shared cleanup model |
| Fallible close | Report errors separately from mandatory storage release | File flush or transaction commit cannot be hidden in an infallible destructor |
| Abrupt termination | No promise of language cleanup after process kill or power loss | Recovery requires persistent protocols where applicable |

`Copy` must be a semantic property. Structural inference can propagate it through ordinary records, arrays, and tagged values, but resource abstractions need a way to prohibit duplication. Otherwise a user-defined handle containing one `u64` can accidentally become freely copyable.

Public Copy status also affects compatibility. Adding an owning field to a public record may invalidate downstream code that previously duplicated it. Exported interfaces should record the property and report changes, rather than describe them as harmless layout edits.

Rust's `Rc::clone` illustrates another naming problem: it adds shared ownership rather than deep-copying the contained value. A7 should not use one undifferentiated “clone” promise for both independent tensor data and shared backing storage. [Rust Rc](https://doc.rust-lang.org/std/rc/index.html).

For cleanup order, a reasonable proposal is reverse declaration order for local owners, LIFO for explicit deferred actions, and a documented field order for structural destruction. The interaction requires examples. A deferred action that reads an owner must run before that owner is destroyed, or the compiler must reject the program.

`defer del x` needs a defined relationship to later assignment, movement, and explicit deletion. It should not immediately consume `x`, because current examples use `x` afterward. A conservative first policy would reserve cleanup of that owner, allow intervening access, and reject later transfer, replacement, or duplicate deletion. A more permissive policy is possible, but needs explicit ownership-token semantics.

Automatic cleanup cannot assume allocating a worklist will succeed during out-of-memory recovery. Deep container destruction therefore needs a strategy such as pre-reserved work storage, intrusive traversal state, bounded representation, or an allocation-free traversal.

The Koka runtime is instructive here. Its ordinary reclamation uses stackless traversal, but the same version contains recursive handling for large scanned vectors. This is comparative source evidence that generated cleanup needs its own stack analysis. [Koka 3.2.3 RC implementation](https://raw.githubusercontent.com/koka-lang/koka/v3.2.3/kklib/src/refcount.c).

---

The following examples make the proposed compatibility changes concrete.

These are design examples, not tested programs. Existing A7 spelling is used where practical. New library functions and result records are placeholders for contracts under discussion. No `borrow`, `inout`, `consume`, `go`, optional-type syntax, or new constructor syntax is approved by these examples.

The first example preserves an approved distinction. Rebinding a value parameter remains invalid, while explicitly permitted referent mutation remains valid.

```a7
// Before and after: argument binding cannot change.
bad :: fn(value: i32) i32 {
    value = 8
    ret value
}

// Before and after: ref authorizes changing caller storage.
Counter :: struct {
    value: i32
}

increment :: fn(counter: ref Counter) {
    if counter == nil { ret }
    counter.value += 1
}
```

The proposed ownership change is that assignment of a heap owner transfers responsibility.

```a7
// Before: existing reference-copy behavior creates an alias.
box := new Counter
if box == nil { ret }
box.value = 7
other := box

// Proposed after: this assignment moves the owner.
other := box
// Reading box afterward is a compile-time error.
// other remains the usable owner.
```

Code that needs independent contents must request duplication explicitly.

```a7
// Proposed API. CloneCounterResult and clone_counter are not current APIs.
copied := clone_counter(box)
if !copied.ok {
    // box is unchanged and still owned here.
    ret
}

other := copied.value
// box and other now contain independent Counter objects.
```

Automatic cleanup changes existing manual cleanup obligations.

```a7
// Before: documented manual cleanup.
box := new Counter
if box == nil { ret }
defer del box
box.value = 7
```

```a7
// Proposed after: automatic cleanup on normal scope exit.
box := new Counter
if box == nil { ret }
box.value = 7
```

Compatibility requires retaining the first form. Under the conservative deferred-cleanup proposal, adding `del box` after `defer del box` is rejected. The program must select one cleanup responsibility.

Returning an owned value replaces an invalid escaping stack view.

```a7
// Before: existing accepted syntax does not establish a safe lifetime.
make_values :: fn() []i32 {
    values: [3]i32 = [10, 20, 30]
    ret values[0..3]
}
```

```a7
// Proposed after: return the fixed array by value.
make_values :: fn() [3]i32 {
    ret [10, 20, 30]
}
```

For dynamic output, the alternative is a returned owning buffer. Returning a borrow into an input requires the more expressive lifetime contract in Alternative B. Silently allocating a copy is not an acceptable compatibility fix.

Exclusivity checks must use storage identity, not argument names.

```a7
swap_i32 :: fn(a: ref i32, b: ref i32) {
    temp := a
    a = b
    b = temp
}

// Proposed rejection if both accesses require exclusivity.
swap_i32(values[i], values[j])
```

```a7
// Proposed accepted form when bounds and separation are established.
if i < values.len and j < values.len and i != j {
    swap_i32(values[i], values[j])
}
```

For two slices, `i != j` is insufficient. Different indices can select the same underlying element through different offsets. The compiler must reason about backing storage and projections, or require an explicit checked operation.

Partial moves need a limited rule.

```a7
// Proposed owning record.
Pair :: struct {
    first: ref Counter
    second: ref Counter
}

extracted := pair.first
// Proposed: pair.second remains accessible.
// Passing pair as a complete value is rejected.
```

```a7
// Proposed restoration after successful replacement allocation.
replacement := new Counter
if replacement == nil {
    // Remaining fields and extracted owner still have defined cleanup.
    ret
}
replacement.value = 0
pair.first = replacement
// pair is complete again.
```

This requires field-sensitive analysis. If `Pair` has a custom destructor that reads both fields, the partial move should initially be rejected. Moving an arbitrary indexed element out of a container should use an operation that replaces or removes the slot.

Initialization policy also needs a visible before/after decision.

```a7
// Before: new Counter followed by field writes.
box := new Counter
if box == nil { ret }
box.value = 7
```

```a7
// Proposed constructor API with a fully initialized success result.
created := counter_create(7)
if !created.ok { ret }
box := created.value
```

The constructor spelling is not prescribed. The required behavior is that failed construction releases storage and completed fields, while successful construction exposes a fully valid owner.

For iteration, structural mutation must not invalidate an active element access.

```a7
// Proposed rejection while iteration borrows items.
for item in items {
    append_item(items, item)
}
```

```a7
// Proposed alternative: construct independent output.
for item in items {
    appended := append_item(output, item)
    if !appended.ok { ret }
}
```

A consuming iterator is another possible API, but needs separate approval. Advancing an iterator may invalidate its previous yielded view even when the collection still exists.

Task transfer needs failure-aware ownership.

```a7
// Proposed APIs, not current concurrency syntax.
sent := channel_send(sender, job)
if !sent.ok {
    job := sent.unsent
    // The failed send returns the still-owned job.
    ret
}
// Successful send leaves no usable job owner here.
```

The essential before/after change is that ordinary reference copying into a task is replaced by a defined transfer. Failed spawn and failed send must return or retain ownership in one documented place.

A complete change register should accompany each approval:

| Proposed change | Before | After | Compatibility impact |
|---|---|---|---|
| Affine assignment | `other := box` aliases | Transfers ownership | Later uses of `box` require restructuring or duplication |
| Call ownership effects | Conflicting research defaults | Resolved signature determines read, mutation, or transfer | Public API contract changes become visible |
| Automatic cleanup | `del` or `defer del` required | Live owners clean up on defined exits | Destruction timing becomes observable |
| Deferred cleanup reservation | Interaction unspecified | Conflicting transfer or deletion rejected | Some previously accepted sequences stop compiling |
| Initialization | Declaration or allocation may precede writes | Reads require initialized state | Constructors and delayed initialization need migration |
| Restricted escaping views | Slice return syntax accepted without complete lifetime proof | Unsafe escape rejected | Return ownership, copy explicitly, or approve lifetime dependencies |
| Partial moves | Unspecified ownership behavior | Plain-record field tracking | Whole-object operations blocked until restoration |
| Iteration exclusivity | No full invalidation contract | Structural mutation conflicts with borrowed iteration | Use separate output or consuming APIs |
| Task transfer | Proposed root-value move | Reachable graph and allocator lifetime checked | Some handles cannot transfer |
| Tensor mutation | No implemented autograd contract | Saved-value lifetime and mutation policy enforced | Some in-place operations fail, copy, or become unavailable |

---

Call-site exclusivity and effect inference are central design work.

A parameter's effect summary should distinguish at least:

- Binding use and referent reads.
- Writes to fields or elements.
- Replacement, resizing, invalidation, and destruction.
- Ownership transfer into returns, aggregates, globals, tasks, or closures.
- Temporary versus retained access.
- Global reads and writes.
- Callback invocation and possible re-entry.
- Allocation, failure, suspension, and cancellation points.
- Returned views and their storage dependencies.

These are not a single ordered scale. A function can read one field, mutate another, return a view into a third, and invoke a callback. “Maximum use is mutate” loses essential information.

Private inference can reduce annotations, but it must not invent permission. If a declaration permits reading only, discovering a write should produce an error. It should not silently widen the API.

For public functions, the approved permissions must remain stable when the implementation changes. Generated summaries can help users inspect behavior, but a body edit that starts consuming an argument is a compatibility change even if the call spelling remains identical.

Function pointers need ownership and effect contracts in their types or associated interface metadata. Indirect calls must satisfy both their access contract and the source-recursion ban. A conservative target set can reject uncertain cases. The compiler must not erase effects simply because the call is indirect.

Closures are owned environments. Immediate callbacks may borrow captures for the call. Escaping closures must own captures or use an approved retained-storage mechanism. A closure that consumes a capture may be callable only once. The language needs to decide how that property appears in its interface. Rust's capture and callable-trait distinctions provide useful precedent, without prescribing A7 syntax. [Rust closure types](https://doc.rust-lang.org/reference/types/closure.html).

Globals and callbacks also defeat purely syntactic exclusivity checks. Passing `state.field` exclusively is insufficient if the callee invokes a callback that accesses the same global `state`. Distinct field paths can establish separation only when the representation and all relevant access paths support that conclusion.

Backend `noalias` should be added only after proving the precise backend contract. An immutable parameter, read-only borrow, or pair of different source names is not enough. Initially omitting an optimization promise is preferable to emitting an unjustified one. [LLVM alias attributes](https://llvm.org/docs/LangRef.html).

A recoverable dynamic exclusivity check must occur before the conflicting operation's effects. Checking midway through a callback-driven operation does not undo earlier writes. General transactional rollback should not be implied.

---

Owned containers and recursive data remain compatible with nonrecursive A7 functions.

A tree can own child allocations while traversal uses an explicit stack. A graph can have one owning node container and non-owning indices between nodes. Neither representation needs recursive source functions.

The distinction is between recursive data shape and recursive execution. Compiler-generated drop functions can accidentally reintroduce unbounded native recursion when destroying a deep ownership tree. A7 must specify the supported destruction strategy independently.

For graph handles, `usize` indices can identify slots. If slots are reused, a generation or equivalent validity mechanism prevents a stale handle from naming a new object. Generation exhaustion must have defined behavior. Silently wrapping a generation counter and reviving an old handle is not acceptable.

Self-references introduce address stability, which is separate from ownership. Moving a heap-owner handle can leave the allocation stationary, but replacing or resizing its contents can still invalidate interior access. Rust's pinning contract exists precisely because heap allocation alone is insufficient. [Rust pinning](https://doc.rust-lang.org/std/pin/index.html).

For A7 v1, prefer indices and opaque stable native-buffer owners over general user-authored self-referential structures. If public pinning is later approved, define construction, projection, replacement, destruction, and FFI retention together.

Resource handles also need semantic ownership. File descriptors, mapped files, kernel plans, thread handles, and foreign contexts cannot be treated as ordinary Copy integers. A7 must distinguish borrowed handles from owned handles and select the correct release function.

---

Concurrency needs an ownership state machine that covers failure and cancellation.

| Event | Required ownership state |
|---|---|
| Before send | Sender owns the complete transferable value |
| Send fails before enqueue | Sender retains ownership, or failure returns it |
| Send commits | Queue owns the value |
| Receive succeeds | Receiver owns the value |
| Receiver disappears | Queue disposal has defined cleanup responsibility |
| Task spawn fails | Captures remain recoverable or are returned |
| Cancellation requested | Running task and native calls retain their live resources |
| Task completes | Result and remaining resources have defined owners |
| Join completes | Caller receives the result or failure and can reclaim task infrastructure |

“Task-private heap” is not sufficient. A receiver must not retain an allocation whose allocator state dies with the sender. Possible solutions are transferable allocator owners, longer-lived shared allocator infrastructure, whole-region transfer, or explicit copying. Each has different costs.

Channel endpoints are another exception to a simplistic “everything moves once” rule. Multiple senders require shareable endpoint capabilities or an explicit endpoint-duplication operation. The queue and scheduler contain synchronized shared state even if user data never does.

For full v1, structured task lifetimes are the most manageable proposal. A parent scope retains task handles and joins its children, including during recoverable failure. Cancellation should be cooperative. A running synchronous native kernel must finish or acknowledge cancellation before its buffers are reclaimed.

This does not prove termination. A kernel may block indefinitely, and a task may fail to reach a cancellation point. A7 should state that limitation rather than claim memory ownership makes cancellation prompt.

Immutable cross-task sharing is a separate approval. It can be valuable for model weights, but read-only access from one task does not prove no other task or foreign library can mutate the storage. Atomic reference counts protect ownership bookkeeping, not the contents. [Rust Arc contract](https://doc.rust-lang.org/std/sync/struct.Arc.html).

---

CPU autodiff makes saved storage a first-class lifetime obligation.

For `loss = x * x`, backward needs the forward value of `x`. Keeping a tensor descriptor alive is insufficient if another alias changes the backing bytes. PyTorch documents saved tensors and mutation-version checks as separate mechanisms. This is useful precedent, not a proposed dependency or a complete A7 design. [Autograd mechanics](https://docs.pytorch.org/docs/2.14/notes/autograd.html).

Two coherent A7 storage designs deserve approval consideration.

| Tensor design | Ownership arrangement | Advantages | Costs |
|---|---|---|---|
| T1. Training-session ownership | A session owns graph nodes, saved storage, and intermediates. Tensor IDs identify session entries. Raw views remain temporary | Fits affine ownership without general shared references. Explicit graph lifetime and bulk cleanup | Coarse retention, session-oriented APIs, checked IDs, explicit export of results |
| T2. Retained tensor storage | Tensor objects and tape records retain shared backing storage. Temporary views borrow from those owners | Convenient escaping tensors and earlier reclamation of unused intermediates | RC traffic, cycle avoidance, storage-version tracking, mutation uniqueness, possible atomic costs |

T1 is the simpler initial qualification target if A7 prioritizes a narrow ownership core. T2 is more ergonomic for tensor objects that routinely escape training scopes. Neither is “free.”

Under T1, a tensor ID is a checked key, not a borrowed pointer and not an owner. Operations require the live session. Wrong-session, expired-generation, and removed-entry cases need rejection or explicit failure before access. Exporting a tensor must move or copy its storage into an independent owner.

Under T2, tape records should retain the storage and metadata needed by backward without accidentally creating strong graph cycles. A weak-edge or acyclic ownership design must be explicit.

Mutation has four possible policies:

| Policy | Behavior | Tradeoff |
|---|---|---|
| Reject mutation while saved | Active saved storage cannot change | Strong local rule, but restricts in-place training operations |
| Return a recoverable mutation conflict | Dynamic check runs before mutation | Practical when saved dependencies are runtime data |
| Snapshot saved values | Tape retains an independent copy | Higher memory use and additional allocation failure |
| Operation-specific in-place rule | Allow only transformations with a defined backward rule and required saved data | Most expressive, but considerably more qualification work |

A sensible initial proposal is explicit mutation with rejection or recoverable preflight failure while the affected storage is saved. Snapshotting should be explicit, because it allocates. A version counter can detect invalidation, but detection after mutation is not equivalent to preventing it.

The ordinary-program consequence is concrete:

```a7
// Proposed session APIs. Names and signatures remain unapproved.
squared := tensor_square(session, x)
loss := tensor_sum(session, squared)

// Mutation may conflict because backward needs x's saved contents.
updated := tensor_fill(session, x, 0.0)
if !updated.ok {
    // Proposed guarantee: x is unchanged.
}
```

A proposed valid sequence completes backward and releases the relevant saved dependencies before mutation:

```a7
gradients := tensor_backward(session, loss)
if !gradients.ok { ret }

released := tensor_release_graph(session, loss)
if !released.ok { ret }

updated := tensor_fill(session, x, 0.0)
if !updated.ok { ret }
```

The exact graph-release API remains open. The invariant is that backward observes the required forward contents.

Tensor views also need shape, stride, offset, dtype, and backing-storage bounds. Different views may overlap despite different shapes or indices. Broadcasted writable views need special care because several logical elements can name one storage element.

Metadata calculations need checked arithmetic even though ordinary integers wrap. Shape products, byte offsets, alignment, and native dimension conversions must not wrap into smaller allocations.

Float policy remains unresolved. Ownership research does not authorize NaN rejection, finite-only storage, fast-math assumptions, or a particular mixed-precision accumulation rule. CPU qualification must name each supported storage dtype, arithmetic dtype, and conversion behavior.

Native kernels should borrow A7-owned storage for a documented interval. A kernel wrapper needs contracts for:

- Input and output mutation.
- Overlap and alias restrictions.
- Alignment, contiguity, strides, and dimension widths.
- Whether access ends on return.
- Whether worker threads remain active after return.
- Workspace allocation and failure.
- Error and cancellation behavior.
- Ownership of plans, descriptors, and other native resources.

Reference DGEMM demonstrates that a numerical call has concrete dimension, leading-dimension, and output-update requirements. Those must be validated before dispatch. The presence of a BLAS symbol does not qualify an A7 tensor operation. [DGEMM contract](https://www.netlib.org/lapack/explore-html/dd/d09/group__gemm_ga1e899f8453bcbfde78e91a86a2dab984.html).

DLPack distinguishes temporary descriptors from managed ownership with a producer-provided deleter. A7 must preserve allocation provenance and use the correct release mechanism. External metadata cannot become trusted merely because it arrived through a standard structure. [DLPack API](https://dmlc.github.io/dlpack/latest/c_api.html).

Future device buffers add completion events, device identity, and asynchronous retention. Recording those extension points does not qualify GPU execution or expand CPU-v1 scope.

---

The compiler obligations follow from the selected semantics.

| Analysis or lowering responsibility | Required result |
|---|---|
| Stable symbol and storage identity | Distinguish bindings, allocation instances, fields, and projected regions |
| Type ownership classification | Determine Copy, ownership, cleanup, transfer, and borrowing properties |
| Definite initialization | Track initialized fields, active variants, and initialized container prefixes |
| Move analysis | Track ownership through assignments, calls, branches, loops, returns, and captures |
| Borrow lifetime analysis | Establish when temporary access begins and ends, including local slices |
| Escape analysis | Reject or represent returned, stored, global, closure, and task-held access |
| Alias and projection analysis | Relate fields, slices, indices, offsets, and overlapping tensor storage |
| Interprocedural effects | Preserve permissions and invalidate facts across direct and indirect calls |
| Function-target analysis | Enforce source recursion policy through modules, function values, and callbacks |
| Cleanup planning | Produce one ordered cleanup plan for every defined exit |
| Allocation provenance | Retain the allocator or foreign releaser needed for eventual cleanup |
| Concurrency transfer checking | Validate the complete reachable graph, captures, endpoints, and allocator lifetime |
| Runtime-check planning | Emit approved recoverable checks before effects, with defined failure results |
| Backend approval | Preserve proof and ownership obligations through specialization and transformations |

Conceptually, these analyses belong over a typed control-flow representation with stable identities. Joins must account for all incoming paths; loops need a fixed point or conservative approximation. A binding can be initialized on one path and moved on another. A three-word state summary is useful for diagnostics but not a complete implementation model.

Facts about bounds and nilness must be invalidated when an alias, callback, resize, or ownership operation can change their basis. A proof about one allocation cannot survive replacement merely because the variable name remains the same.

Lowering should consume an explicit plan. It must not reconstruct ownership from AST spelling or rely on Zig to recover A7's intended semantics. Generic specialization and AST transformations must preserve or regenerate the relevant obligations.

The distinction between proof and checks should remain honest:

| Claim | Appropriate mechanism |
|---|---|
| A moved owner cannot be read | Compile-time ownership analysis |
| A known local view cannot escape its owner | Compile-time lifetime and escape analysis |
| Two static field projections are separate | Compile-time representation and alias reasoning |
| Runtime tensor dimensions are compatible | Explicit check or established symbolic proof |
| A runtime graph handle still names its entry | Checked lookup unless lifetime is statically established |
| Allocation succeeds | Environmental result; cannot generally be proved |
| A native library obeys its contract | Boundary assumption plus integration qualification |
| A task eventually finishes | Not established by ownership or source recursion rejection |
| A native stack never overflows | Separate target-specific analysis and environmental assumptions |
| No process can fail | Not a defensible language guarantee |

“No runtime traps from supported A7 operations under stated assumptions” is a more precise target than “zero runtime errors.” Allocation failure, invalid input, I/O failure, cancellation, and numerical failure can be defined results. Changing the public promise still requires approval.

---

Tests should start from independently stated obligations.

The following are proposed acceptance scenarios. None was executed in this review.

| Scenario | Independent expected result | Evidence class |
|---|---|---|
| Transfer a nested owner record | Recipient can use every transferred resource; sender cannot reuse it | Positive native integration plus negative compilation |
| Move on only one branch | Post-join whole-value use is rejected unless every path restores ownership | Negative compilation |
| Fail construction after two resource fields succeed | Exactly those initialized resources are released; no incomplete value is published | Recovery |
| Fail container growth | Original elements, length, and ownership remain usable under the approved guarantee | Recovery with allocator failure injection |
| Fail clone | Original contents remain unchanged; partial duplicate is reclaimed | Recovery |
| Schedule cleanup, then read | Read succeeds before scope exit; cleanup occurs once afterward | Positive integration |
| Schedule conflicting cleanup or transfer | A7 rejects the conflict at the relevant source location | Negative compilation |
| Exit through return, break, continue, or propagation | Observable cleanup order matches the approved contract | Integration |
| Return a local backing slice | A7 rejects the escape | Negative compilation, GLM owns safety validation |
| Pass separated elements for mutation | Operation produces the independently specified result | Positive integration |
| Pass overlapping views | Static rejection or documented preflight failure before mutation | Negative and recovery |
| Callback accesses an active exclusive global | Contract rejects or prevents the conflict | GLM validation question |
| Grow a container during borrowed iteration | Rejection or explicitly defined consuming behavior | Negative compilation |
| Reuse a graph slot | An old handle cannot resolve to the new object | Runtime invariant and recovery |
| Fail task spawn | Captured owners remain recoverable in the documented result | Recovery |
| Close a channel during send | Each value has one documented owner; no ambiguous enqueue outcome | Concurrent integration |
| Cancel a receiver with queued values | Queue and task cleanup reclaim undelivered owners according to policy | Concurrent recovery |
| Cancel during a synchronous CPU kernel | Storage remains live until the kernel finishes or acknowledges cancellation | Native integration |
| Destroy a deeply nested owner graph | Cleanup meets its separately stated stack and allocation contract | Runtime qualification |
| Import and release foreign storage | Producer's release mechanism runs exactly once after final use | FFI integration |
| Mutate storage saved for backward | Approved policy applies before incorrect gradients can be produced | Autograd integration |
| Complete repeated training steps | Graph storage returns to the stated retained baseline after each step | Memory-lifecycle integration |
| Backward on `x*x` at a fixed finite value | Gradient equals the independently derived `2*x` within approved numerical tolerance | Numerical integration |
| Training allocation fails before parameter commit | Parameters remain unchanged if atomic step commit is the approved policy | Recovery |
| Same supported program in Debug and release | Same ownership, cleanup, and specified value behavior | Cross-profile integration |

Allocator failure injection is a named boundary. It establishes behavior when allocation reports failure; it does not simulate an operating-system kill, every fragmentation pattern, or a foreign allocator's behavior.

Resource counters must observe actual acquisitions and releases at a named boundary. Assertions that a cleanup helper was called do not establish correct resource lifetime. Similarly, a bounded memory test should distinguish live A7 storage, allocator-retained capacity, native workspace, and process memory.

Security validation remains with GLM. The concrete questions to hand over are:

- Do storage identities and effect summaries remain sound through aliases, globals, callbacks, imports, and specialization?
- Do initialization and cleanup plans cover every error and cancellation edge?
- Can retained foreign access outlive the owner or allocator?
- Are overlap checks correct for slices and strided tensors?
- Can task or queue disposal reclaim data still used by native code?
- Are generation and reference-count exhaustion handled without invalid state reuse?
- Does generated destruction meet its claimed native-stack behavior?
- Do compiler transformations preserve operation-specific approvals?

---

The approval sequence should resolve behavior before spelling.

| Approval question | Recommended proposal | Concrete compatibility consequence |
|---|---|---|
| What is the default heap model? | Alternative A, affine owners with scoped access | `other := box` transfers ownership |
| Which borrowed views may be stored? | Permit checked local views; initially restrict escaping borrowed aggregates | Returning a local slice is rejected; owned containers remain valid |
| How are call permissions exposed? | Stable public contracts with private inference where permitted | A body change cannot silently turn a reading API into a consuming API |
| Does cleanup become automatic? | Yes, on explicitly defined language exits | Existing manual cleanup remains valid, but conflicts become errors |
| What does `defer del` reserve? | Reserve cleanup of the current owner; initially reject conflicting replacement or transfer | Some currently accepted sequences require restructuring |
| Are partial moves supported? | Plain records first; restrict indexed moves and destructor-bearing records | Whole-record use requires restoration |
| How is resource duplication controlled? | Semantic Copy classification; explicit independent clone and separate share | Integer-backed resource wrappers remain non-Copy |
| Are custom destructors part of v1? | Decide separately from structural cleanup; require explicit effects and failure restrictions | User-defined cleanup cannot be silently treated as infallible |
| How do tasks end? | Structured lifetimes, cooperative cancellation, explicit joins | Spawned work cannot silently outlive captured owners |
| Can tasks share immutable storage? | Separate approval after isolated transfer | Model-weight sharing requires more than root-value moves |
| Who owns autodiff storage? | Evaluate T1 session ownership against T2 retained storage using real workloads | Tensor escape, graph release, and peak memory differ |
| What happens on mutation of saved storage? | Reject or return a preflight conflict; snapshots explicit | Some in-place operations require graph release or duplication |
| Which runtime checks are allowed? | Explicit recoverable checks with defined failure state | Unknown runtime facts need not force traps or unverifiable assumptions |
| What stack promise is made? | Source recursion ban plus separately qualified native bounds | No “exact stack size” claim from source structure alone |

Before implementation, each selected row should become a decision record containing its A7 before/after example, compatibility impact, failure result, required analyses, and acceptance scenarios. The current ownership cluster is too contradictory to approve as one block.

This report supports that decision work. It does not establish current A7 ownership safety, CPU-AI readiness, or release readiness.