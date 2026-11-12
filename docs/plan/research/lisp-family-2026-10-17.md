# Lisp families: transferable mechanisms for A7

Research dated 2026-10-17. A7 should study binding-aware transformations,
explicit compilation phases, recoverable-operation interfaces and inspectable
compiler state. These concepts do not require Lisp surface syntax. Full images,
resumable conditions, continuations and managed heaps require separate runtime
contracts. This report recommends experiments; it adopts no language feature.

Zig remains A7's backend. C export and GPU execution remain deferred. Neither
A7 source recursion nor recursion in compiler internals becomes permitted.
The approved Result/Option direction and allocation-deletion rules remain in
force. See [decisions](../decisions.md), especially L68 and L74, and the
[current specification](../../SPEC.md).

## Evidence and prior work

This is a documentation and primary-source review. No Lisp implementation was
installed, compiled or benchmarked. No A7 compiler change or native job ran.
Documentation version labels below identify the material read, not a claim that
it is the latest available release. Mutable project pages were read on the date
above; their implementation revisions were not pinned.

The [language-facilities agenda](language-facilities/README.md) lists planned
condition-system, compile-time and live-target reports. Those numbered reports
are absent in that directory. They are not completed evidence. The
[claims register](CLAIMS.md), [live-environment audit](live-environment/00-claims-audit.md)
and [runtime-model audit](runtime-model/00-claims-audit.md) preserve earlier
research and its source-access limits. Their proposed memory, concurrency and
reload designs are not substituted for current decisions here.

One earlier uncertainty can be narrowed: ahead-of-time native compilation does
not itself prevent a condition system. The relevant questions are runtime
support, control transfer, cleanup and foreign-call boundaries. This does not
establish that A7 already supports such a system.

## Families, implementations and tools

| Name | What is being compared | Relevant mechanism and dependency |
| --- | --- | --- |
| Historical Lisp | McCarthy's 1960 language foundations | Symbolic expressions and programs represented as manipulable data. This is not a modern macro, module or ownership specification. |
| Common Lisp | Standardized language; CLHS reference | Form-transforming macros, dynamic conditions/restarts and rich runtime objects. SBCL is one implementation, not the language definition. |
| Scheme | Family; R7RS-small report used here | Lexical binding, hygienic pattern macros, proper tail calls and continuations. Guile is one implementation with additional facilities. |
| Racket | Language ecosystem and implementation | Binding-aware syntax objects and explicit phase levels. Its module, contract and runtime machinery are part of the comparison. |
| Typed Racket | Typed Racket language variant | Predicate-based type refinement and several typed/untyped boundary modes. It is not synonymous with typed macro expansion. |
| Clojure | JVM-hosted language in the cited references | Persistent values and explicit state-management mechanisms, with JVM services. ClojureScript and CLR ports are different targets, not evidence for this runtime. |
| Emacs Lisp | Emacs extension language | Live function evaluation and editor integration, byte/native compilation, managed Lisp objects and editor-specific ambient state. |

[McCarthy's original paper](https://www-formal.stanford.edu/jmc/recursive.html)
was published in April 1960. Its historical title and recursive formulations do
not change A7's recursion ban. An S-expression is a representation, not proof
that name resolution, effects, typing or allocation are simple. Scheme's
[external-representation discussion](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-5.html)
explicitly distinguishes a list representing an expression from its evaluated
value. A7 can retain its parser while making internal forms inspectable.

## Macros: representation, binding and typing are separate

Common Lisp's [reader algorithm](https://www.lispworks.com/documentation/HyperSpec/Body/02_b.htm)
turns character input into objects and dispatches macro characters.
[DEFMACRO](https://www.lispworks.com/documentation/HyperSpec/Body/m_defmac.htm)
operates later: an expansion function receives a form and environment and
returns a replacement form. Reader customization and expression transformation
therefore affect different contracts. Adding reader macros to A7 would change
parsing, formatting and tooling; it is not needed for an internal lowering pass.

Scheme's [R7RS expression specification](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-6.html)
defines hygienic derived forms and `syntax-rules`. Hygiene protects bindings
against accidental capture during expansion. It does not prove single
evaluation, termination, absence of I/O, or type correctness. The same report
leaves procedure operator/operand evaluation order unspecified. A7 must keep
its own order rules rather than import Scheme's rule with a transformation.

Racket [syntax objects](https://docs.racket-lang.org/guide/stx-obj.html) preserve
source locations and lexical-binding context alongside the represented datum.
Two identifiers can refer to the same binding despite different printed names.
This is the strongest immediate lesson for A7: generated temporaries need
resolved identities, and generated diagnostics need provenance. A textual
rename or a fresh-looking spelling alone is insufficient.

Three designs must not be conflated:

- A hygienic syntactic macro preserves lexical binding during rewriting.
- A type-aware transformation consumes checked type information at an explicit
  compiler stage. It must preserve or regenerate proofs for its output.
- A typed macro interface can constrain what a transformer accepts and emits.
  That interface alone does not make arbitrary transformer code pure or safe.

This report does not establish a ready-made typed-macro design for A7. Typed
Racket's existence is not such evidence. A7 should first test an internal,
non-user-extensible normalized form with explicit binding IDs and source spans.
It must not share mutable checked AST annotations between generic instances.

[Turnstile's Type Systems as Macros artifact](https://stchang.github.io/popl2017/index.html)
provides a more direct comparison: type-system rules expressed through macros
that check and elaborate programs. For A7, the research question is whether
each internal rewrite can state its input judgment, emitted operation and
preserved obligations. Checking an output type alone does not establish effect
order, source provenance or lifetime safety. This is an implementation research
direction; no artifact was run and no public macro facility is selected.

Clojure's [macro reference](https://clojure.org/reference/macros) describes
compile-time form transformation; its [reader](https://clojure.org/reference/reader)
has separate data and reader forms. These are useful comparisons for separating
input formats from evaluation. They do not justify treating arbitrary read
forms as inert configuration or adopting Clojure's runtime representation.

## Compilation phases and hermetic evaluation

Racket [separates phase binding spaces](https://docs.racket-lang.org/guide/stx-phases.html).
A runtime helper is not automatically available to a macro transformer;
`begin-for-syntax` and phase-shifted imports make that dependency explicit.
Common Lisp's [EVAL-WHEN](https://www.lispworks.com/documentation/HyperSpec/Body/s_eval_w.htm)
also distinguishes compilation, loading and execution situations. Neither
mechanism by itself restricts filesystem, clock or process effects.

Proposed A7 experiment: describe compile-time inputs as a dependency graph,
including compiler version, target layout, imported source and declared data.
Run the same transformation in fresh processes with different working
locations and hash seeds. Require identical checked forms and emitted Zig.
An undeclared clock, environment or file dependency should fail the experiment
rather than silently become part of a cache key. This is a proposed contract,
not a claim that arbitrary A7 CTFE is implemented or sandboxed.

Separate host evaluation from target evaluation. Host-sized integers, byte
order, float behavior and pointer layout cannot silently determine target
constants. Transformer failure must carry an originating span and phase. An
expansion worklist must preserve the compiler's no-recursion rule; adding
language-level expansion also needs a separately approved termination and
resource policy. No arbitrary expansion threshold is selected here.

## Conditions, restarts, Result and cleanup

The Common Lisp condition system separates reporting a situation, choosing a
handler and offering recovery actions. CLHS [handler search](https://www.lispworks.com/documentation/HyperSpec/Body/09_ad.htm)
uses active dynamic handlers. Invoking a handler need not first discard the
signaling stack. This can let a higher-level policy choose an operation offered
by lower-level code before that operation's state disappears.

A restart is not automatically a retry, rollback or debugger repair.
[RESTART-CASE](https://www.lispworks.com/documentation/HyperSpec/Body/m_rst_ca.htm)
unwinds the dynamic state to its selected clause before running that clause.
[RESTART-BIND](https://www.lispworks.com/documentation/HyperSpec/Body/m_rst_bi.htm)
can associate a restart with a function that returns without a nonlocal
transfer. [UNWIND-PROTECT](https://www.lispworks.com/documentation/HyperSpec/Body/s_unwind.htm)
specifies cleanup on exit; it does not undo arbitrary mutations or external I/O.
A nonlocal exit during a cleanup form can prevent later cleanup forms from
running. The same `unwind-protect` does not protect its cleanup sequence.

For A7, distinguish these hypothetical interfaces using a file read:

| Interface | State and policy consequence |
| --- | --- |
| Existing Result-oriented direction | Caller receives a value describing failure and chooses another operation after ordinary return/cleanup. |
| Explicit retry policy | The operation receives a bounded policy interface or returns enough data to attempt a new operation. Repeated I/O remains visible. |
| Resumable condition | A handler may act while lower-level state remains active. Dynamic extent, alias validity and cleanup timing need a new contract. |
| Image/debugger intervention | Code or data may change during suspension. Versioned frames, foreign resources and proof invalidation become separate obligations. |

The first row preserves [L68](../decisions.md); the other rows are comparisons,
not adopted API designs. A narrow recovery-policy library can be studied
before dynamic stack resumption. Required cases include refusal to retry,
partial output already written, handler failure, nested recovery and exactly
once cleanup initiation. The experiment must separately specify cleanup failure
and replacement of a pending control transfer. Initiating cleanup once does not
prove that every cleanup action completes. No recovery action may revive an
allocation deleted under L74.

## REPL, saved image and reload are different products

The [SBCL 2.6.9 manual](https://www.sbcl.org/manual/) describes native compilation,
standalone executables containing an SBCL runtime, and saved images. Image
saving preserves global state but unwinds the stack; thread and foreign-library
handling have restrictions. This is concrete evidence against an AOT-versus-
conditions prohibition. It is not evidence that arbitrary native program
frames can be saved or that an image is portable across runtime versions.

Emacs 30.2 documents [native compilation through libgccjit](https://raw.githubusercontent.com/emacs-mirror/emacs/emacs-30.2/doc/lispref/compile.texi).
The resulting `.eln` code still participates in Emacs. Native compilation does
not remove editor state or turn Emacs Lisp into a standalone ownership model.
Its [memory documentation](https://raw.githubusercontent.com/emacs-mirror/emacs/emacs-30.2/doc/lispref/internals.texi)
describes automatic collection and the latency/memory tradeoff of collection
thresholds. Do not transfer an interactive workflow while hiding that runtime.

For A7, the first useful interactive tool could compile and run an isolated
fragment with an explicit input fixture and show diagnostics, generated Zig and
output. It need not patch a running process. A later reload experiment would
need an explicit ABI, a quiescent boundary, old-code lifetime, schema migration
and invalidation of cached safety facts. A raw pointer held by foreign code
cannot be made relocatable by changing the language's surface syntax. These
are proposed engineering prerequisites, not proof of a particular reload
implementation's feasibility or cost.

## Types, data, memory and concurrency

Typed Racket's [occurrence typing](https://docs.racket-lang.org/ts-guide/occurrence-typing.html)
refines types using predicate results and distinguishes one-sided propositions.
Its documentation discusses mutation and field-access limits. A7 can compare
those rules with nil and bounds proofs: a false predicate need not establish
the complement of every positive fact, and mutation can invalidate a prior
fact. This does not equate type refinement with proof of allocation liveness.

[Typed/untyped interaction](https://docs.racket-lang.org/ts-guide/typed-untyped-interaction.html)
has Deep, Shallow and Optional modes. Contracts can wrap values and impose
costs; shape checks provide different protection. These are useful examples of
making a boundary policy explicit. They do not establish zero-cost contracts
or justify weakening A7 checks at unknown-call or foreign boundaries.

[Clojure's JVM account](https://clojure.org/about/jvm_hosted) places the runtime
on Java's VM and GC. Its [Refs and transactions](https://clojure.org/reference/refs)
coordinate updates through STM. Conflicts can retry a transaction, so external
side effects need care; mutable values inside a Ref do not gain immutable
semantics automatically. Transfer the distinction between a stable identity and
successive values when designing analysis snapshots. Do not infer deterministic
thread scheduling, zero copying or allocation-free persistent structures.

[Clojure transients](https://clojure.org/reference/transients) add a construction
discipline. Updates preserve the persistent source, and callers must retain each
update's returned transient. Publishing with `persistent!` invalidates the
transient and its aliases. Access requires isolation; the creator-thread check
was removed in 1.7. A possible A7 compiler experiment would compare copied
analysis maps with shared snapshots and private edits. Old snapshots must remain
unchanged, and measurements must include retained memory and merge work. This
does not select a public builder API or reclamation mechanism.

Emacs 30.2 [threads](https://raw.githubusercontent.com/emacs-mirror/emacs/emacs-30.2/doc/lispref/threads.texi)
share memory and use mostly cooperative switching, but the manual warns against
relying on that scheduling property. Dynamic local bindings and captured lexical
bindings also have different sharing behavior. This illustrates why a single
word such as "thread" cannot define A7's future concurrency contract.

R7RS's [storage and tail-call model](https://standards.scheme.org/corrected-r7rs/r7rs-Z-H-5.html)
uses conceptual locations and requires proper tail calls. Conceptual identity
need not be a physical address. Proper tail calls are not an exemption from
A7's source-recursion prohibition. Any comparison algorithm for A7 must use
loops or explicit worklists. GC-backed persistence, multi-shot continuations
and mutable global namespaces cannot be adopted as incidental consequences of
borrowing syntax or an inspector.

## Additional dialects and implementations

| System and primary source | Relevant evidence | A7 use and limit |
| --- | --- | --- |
| [GOOL, author retrospective](https://all-things-andy-gavin.com/2011/03/12/making-crash-bandicoot-gool-part-9/) | Gavin distinguishes Crash's mostly interpreted GOOL from GOAL; later GOOL compiled some expressions. | Study domain-specific state-machine tooling. Do not call GOOL and GOAL the same native compiler. |
| [GOAL, documentation v1.15](https://all-things-andy-gavin.com/goal-test/) | Published historical documentation describes a compiled Scheme-derived language, a Common Lisp compiler and dynamic linking into a running target. | Concrete counterexample to "Lisp means interpreted." The target runtime, loader and object model were designed together. No portability or A7 reload proof follows. |
| [Shen S-series](https://shenlanguage.org/s-series.html) and [education guide](https://shenlanguage.org/learn.html) | The project describes sequent-calculus/type tooling, KLambda ports and changes in kernel responsibilities. | Compare a small portable core and explicit proof rules. Current port correctness, optional-typing details and performance were not audited; host costs vary by implementation. |
| [Janet](https://janet-lang.org/) | Project documents GC, fibers, mutable/immutable collection pairs, C embedding and macros. | Useful comparison for an embeddable diagnostic tool. Runtime allocation, scheduling and C-boundary obligations remain; no latency claim was verified. |
| [Guile compiler tower](https://www.gnu.org/software/guile/manual/html_node/Compiler-Tower.html) and [GC](https://www.gnu.org/software/guile/manual/html_node/Garbage-Collection.html) | The manual describes successive intermediate languages and managed SCM objects, with precise Scheme tracing and conservative C roots. | Compare pass contracts and explicit foreign rooting. Guile is a Scheme implementation/runtime, not a universal Scheme storage rule. |
| [Fennel tutorial](https://github.com/bakpakin/Fennel/blob/main/tutorial.md) | Fennel compiles to Lua and uses Lua's tables, modules and coroutine facilities. The tutorial documents host-semantic constraints. | Study a small frontend that respects its backend. Lua services still exist; the project's overhead goal is not measured A7 evidence. |
| [Hy 1.1.0](https://hylang.org/hy/doc/v1.1.0) and [macros](https://hylang.org/hy/doc/v1.1.0/macros) | Hy transforms forms into Python AST objects and exposes Python interoperability. | Useful analogy for using a host compiler. It retains Python execution and object semantics; it is not an AOT systems-memory model. |
| [Carp](https://github.com/carp-lang/Carp) | Project describes static inference, ownership tracking and deterministic memory management without a GC or VM. | Relevant ownership/representation comparison. This review read project documentation, not a soundness proof or allocator audit; do not repeat its performance claims as facts about A7. |

GOAL's custom assembly and object runtime are historical evidence, not a reason
to replace Zig or start a C backend. OpenGOAL's attempted documentation endpoint
was unavailable in this review; no claim about its current implementation is
made. Shen's current S-series page describes a September 2026 port revival;
that project report was not independently built or validated.

## Proposed experiments and decision boundaries

| Stage | Bounded experiment | Observable requirement | Status |
| --- | --- | --- | --- |
| 1 | Read-only normalized-form dump with binding IDs, spans and phase labels | Shadowed names and generated names remain distinguishable; diagnostics trace to original source; output is deterministic across hash seeds. | Tooling proposal. Reuse existing internal data before creating an abstraction. |
| 2 | Internal rewrite of one already-supported construct | Exact evaluation count/order, nil/deletion rejection sites, cleanup order and emitted behavior match existing contract. Iterative deep-input traversal remains valid. | Requires an isolated implementation plan and normal qualification. No user macro syntax. |
| 3 | Hermetic compile-time evaluation design | Explicit host/target types, dependency manifest, effect policy and reproducible artifacts; failure has phase and source provenance. | Language/runtime proposal requiring approval. |
| 4 | Recovery-policy comparison around an existing Result-returning operation | Failure, retry refusal, partial I/O and cleanup are independently specified; no stale alias becomes valid. | Preserve Result/Option; any new behavior needs approval. |
| 5 | Process-isolated interactive evaluator, then separate reload feasibility | A clean session reproduces the same artifact/output; later reload rejects incompatible layouts and active-frame changes. | Tooling and runtime proposals, not a V1 completion claim. |

The compiler-simplification hypothesis is specific: a small set of checked
operations may reduce repeated handling across type, safety and emission
passes. More intermediate forms can also add copying and invalidation work.
Measure pass work, source provenance and retained invariants before claiming
simplicity. Guile's compiler tower motivates the question; it does not prove
that another A7 pass is needed.

Before any memory or concurrency experiment, keep the current allocation
identity and invalidation contracts explicit. Count allocations, retained
objects, peak live memory, GC pauses where applicable and total runtime
separately. Cross-language syntax similarity is not a benchmark control.
Existing A7 performance requirements remain unchanged.

## Source versions, bibliography and verification limits

All external citations above are primary language references, project manuals,
project repositories or the original designer's historical account. CLHS is a
reference to standardized Common Lisp; R7RS-small is the 2013 report using its
corrected HTML edition. The Typed Racket page displayed version 9.3; the SBCL
manual displayed 2.6.9. Emacs sources are explicitly tagged `emacs-30.2`; Hy
links select 1.1.0. Other unversioned pages are dated reads, not pinned builds.

The bibliography is the linked source set in each section and matrix. No source
was used for a language-wide performance or safety theorem. Native runtime
behavior, current implementations' bugs, GC pause distributions, live reload
compatibility and macro expansion resource limits remain unverified.

Some direct GNU HTML requests, Fennel's home page, two Shen guessed page paths
and the OpenGOAL endpoint returned tool access errors. Emacs claims use the
version-tagged source manual instead. Guile claims use the primary manual text
returned by web search; direct page opening failed. Fennel uses the project's
linked repository tutorial. Shen uses links discovered from its actual home
page. Failed access is not evidence that a feature or project is absent.

The parent independently checked the CLHS handler/restart distinction and SBCL
runtime/image boundary. It confirmed that L68's Result/Option disposition stays
unchanged. This research changes no approved behavior and does not resolve the
pending scalar-reference or call-order design questions.
