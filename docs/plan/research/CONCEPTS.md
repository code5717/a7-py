# The concepts under the ideas

The material the user supplied on 2026-09-18 describes another project's
features. The features are not the subject. This file names the concepts behind
them, and the research programmes are organized by these, not by anyone's
product. A feature like a session file or a hotkey is at most an illustration of
a concept; it is never the thing being researched.

Judged under [EVALUATION.md](EVALUATION.md): agent value weighted above human
value. The raw claims, deduplicated and ruled, stay in [CLAIMS.md](CLAIMS.md) as
the index back to the sources.

## C1. Reproducible execution

A program's execution is a function of its inputs, and running it again with the
same inputs gives the same result, bit for bit.

Everything else here rests on this. Without it there is no replay, no reliable
bisection of a run, no comparison of two runs, and no way for an agent to tell a
real change from noise. The research question is what breaks it in practice
(scheduling order, address layout, floating-point reduction order, clocks,
hashing, concurrency) and what each remedy costs.

Agent value: high. An agent's core loop is change something, run it, compare.
Non-reproducibility poisons the comparison.

## C2. Execution history as data

The record of a run is a value the system can keep, search and re-enter, rather
than an event that happened and is gone.

Two families: keep the whole history (expensive, exact) or keep enough to
reconstruct any point (an initial state, a log of non-deterministic inputs, and
periodic checkpoints). The second is what makes "go back to any moment" cheap,
and it depends entirely on C1.

The important property is not stepping backward — it is that history becomes
queryable. "When did this become zero" is a search over data, not a debugging
session.

Agent value: high, and higher than for a person. A person scrubs a timeline; an
agent runs ten thousand queries against it.

## C3. Provenance

Every value, allocation and effect can name where it came from: which source
construct produced it, when, and from what inputs.

This is the concept behind birth-stamping objects, behind mapping a rendered
pixel back to a line, and behind a debugger that can answer "who wrote here".
For a compiled language it starts one level down: the emitted code must be
traceable to the source that produced it, which A7 cannot do today at all.

Agent value: high. Provenance converts "read the code and reason about it" into
a lookup.

## C4. Resumable failure

A fault suspends the computation with its state intact instead of unwinding and
discarding it. The state can be examined, the cause corrected, and the
computation continued from where it stopped.

Common Lisp's conditions and restarts are the mature form. The concept is
separable from liveness: even without editing code mid-run, a fault that
preserves its frame is far more informative than a stack trace, and far more
useful to an agent, which can inspect the live state rather than reconstruct it.

The open question for A7 is whether a statically compiled language, with no
runtime of its own, can offer any of this — and if not, what the nearest
reachable thing is (a dumped frame? a re-entrant checkpoint?).

Agent value: high, if reachable. Feasibility is the research.

## C5. State as plain, relocatable data

Program state lives in flat, contiguous, position-independent structures rather
than a graph of pointers into an opaque heap.

This is the enabler concept. Snapshotting, serializing, migrating, diffing,
sending over a network and rolling back are all trivial for flat data and hard
for a pointer graph. Arenas, handle-based references and "no globals" are the
techniques; the concept is that the shape of state decides which capabilities
are cheap.

It is a language and memory-model decision, not a tooling one, which places it
against A7's memory plan rather than its debugging story.

Agent value: medium directly, high indirectly — it is what makes C2 affordable.

## C6. Mutable program during execution

Code and data layouts can change while the program runs, without discarding the
state built so far.

Two halves that are usually confused: replacing behavior (swapping a function's
implementation) and migrating representation (a struct gains a field while
instances exist). The first is mostly a linking problem; the second is a data
migration problem with the same shape as a database schema change.

Agent value: low to medium. An agent rebuilds and re-runs cheaply; it does not
need to preserve a session. The related concept that does matter to an agent is
the *cost of the loop* — how long from edit to observed behavior.

## C7. Staged evaluation

There is no hard boundary between what runs while compiling and what runs after.
The compiler can evaluate arbitrary program code to produce tables, validate
invariants or shape the program before emitting it.

The research is not whether it is possible — Zig, D and Jai all do it — but what
it costs in reproducibility, build hermeticity and security, and where the
boundary must stay hard (a compiler that can read the network at build time is a
supply-chain surface).

Agent value: high. Precomputation and build-time checks are work an agent can
generate and verify mechanically.

## C8. Representation control

The programmer states how data is laid out, independently of how the algorithm
reads it — array of structs against struct of arrays, alignment, padding,
packing.

A performance concept, largely independent of the rest of this document, and one
that interacts with C5: flat data with declared layout is what makes both
snapshots and cache behavior predictable.

Agent value: medium. An agent can measure layouts against each other, which is
exactly the kind of search a person avoids.

## C9. Programs as structure, not text

The canonical form of a program is a tree or a graph with identity, and text is
one projection of it.

The historical claim is about editors. The version that matters here is narrower
and testable: if constructs have stable identity, then edits, diffs, provenance
and incremental compilation all become precise rather than line-based. A7
already suffers the opposite: analyses keyed by name and by Python object
identity are the direct cause of several miscompiles found in its audits.

Agent value: medium to high. An agent editing structure rather than text makes
fewer invalid programs, and a diff over structure is a better input than a patch.

## C10. Self-describing data

A type carries how it should be presented, and tools render it accordingly
rather than dumping bytes.

For a person that is a canvas or a graph. For an agent it is a structured
projection — the same declaration, a different renderer. This is the concept
worth keeping from every "moldable inspector" demonstration, and it costs
little: a projection function per type, used by whatever is looking.

Agent value: high, in its structured form.

## C11. Context-directed compilation

The kind of program being built is an input to the compiler: what it may
allocate, what it may block on, what timing it must meet, what it must prove.

Existing profiles (Ravenscar, MISRA, DO-178C, freestanding and `no_std` builds)
encode this socially, in documents and review. The concept is to make the
context machine-checkable, so that violating it is a compile error rather than a
finding in an audit.

Agent value: high. A stated, enforced context is a specification an agent can
work inside without being told the rules each time.

## C12. Search with a verifier

The compiler proposes transformations by search — learned, random or exhaustive
— and a checker decides which are correct. Only checked transformations survive.

This is the only safe framing for machine learning inside a compiler, and it is
older than machine learning: superoptimizers, equality saturation and
translation validation all have this shape. The value lives in the checker, not
the proposer.

Agent value: high. Propose-and-check is precisely the loop an agent can run
without supervision, and the checker is what makes it safe to leave running.

## C13. Deterministic concurrency

Parallel execution has a defined order, so results do not depend on scheduling.

A special case of C1, separated because the cost is specific: determinism
constrains a scheduler, and constraining a scheduler costs throughput. The
research must say how much, from measurements rather than assertion.

Agent value: high, through C1.

## How these map to the programmes

| Concept | Where it is researched |
| --- | --- |
| C1, C13 | `runtime-model/01-deterministic-concurrency.md` |
| C2 | `runtime-model/03-state-snapshots-arenas.md`, `tooling/08-agentic-debugging.md` |
| C3 | `tooling/01-debug-info.md`, `live-environment/02-bidirectional-mapping.md` |
| C4 | `language-facilities/01-condition-systems.md` |
| C5 | `runtime-model/03`, and the memory plan |
| C6 | `runtime-model/06-loop-editing.md`, `language-facilities` |
| C7 | `language-facilities/02-compile-time-execution.md` |
| C8 | `language-facilities/03-data-layout-control.md` |
| C9 | `live-environment/06-structural-editing.md` |
| C10 | `language-facilities/05-moldable-inspection.md`, `tooling/09-visualization.md` |
| C11 | `optimization/02-context-profiles.md` |
| C12 | `optimization/01-learned-optimization.md`, optimization report 03, not yet written |

Each report answers, for its concept: what the concept is, what it requires of a
language, what it costs, who has built it and what happened, what the agent-
facing form is, and whether it is reachable for a language that compiles ahead
of time to a native binary.
