# What A7 should take from Bend 2

Companion to [the Bend analysis](../../lang-safety/comparative/bend.md), which
holds the verbatim quotations and the sources. This file is a proposal list:
nothing here is approved, and every item that changes A7 syntax or behavior
needs its own packet with before-and-after examples (the approval rule in
CLAUDE.md, ledger L24).

Ordered by what it fixes, not by how interesting it is.

## B1. Function contracts: let the user state a precondition

**Bend.** The user writes the property in `LAWS.bend` and the compiler refuses
the program until a proof discharges it. Proof obligations are user-stated, not
a fixed list.

**A7 today.** The obligation set is fixed and internal: divisor non-zero, index
in bounds, slice bounds, reference non-nil (`a7/safety.py`, `ObligationKind`).
A user cannot state an invariant, so two whole classes of code are unwritable:

- `ref T` parameters are assumed non-nil and no call site proves it, so passing
  `nil` builds and writes through null (SAF-1, CRITICAL,
  `docs/audits/2026-09-16/compiler/safety.md`; probes `p08`, `p08b`: A7 exit 0,
  Zig exit 0).
- Indexing or slicing a slice or string parameter always fails the bounds proof,
  because no fact about the parameter's length can enter the function (KNOWN
  S11, `docs/plan/audit/evidence/2026-09-16-ledger-part2.md:84`).

So today a library function that takes a slice and reads it cannot be written at
all, and a function that takes a `ref` is trusted blindly. Those are opposite
failures with one cause: nothing crosses the call boundary.

**Proposal.** A `requires` clause on a function signature, over a decidable
fragment. Inside the body its conditions are facts; at every call site they are
obligations the caller must discharge from its own facts, or the call is
rejected.

```a7
// Proposed. Does not compile today.
get :: fn(xs: []i32, i: usize) i32
    requires i < xs.len
{
    ret xs[i]          // rejected today (S11): no fact about xs.len exists
}

main :: fn() {
    buf: [4]i32 = [1, 2, 3, 4]
    v := get(buf[0..4], 2)   // 2 < 4 is provable here: accepted
    w := get(buf[0..4], 9)   // rejected at the call site, not inside get
}
```

The fragment must stay decidable and side-effect free, or the checker becomes a
prover. Proposed limit: comparisons and equalities between parameters, `.len`,
integer literals and `::` constants, `!= nil`, joined by `and`, `or`, `not`.
No calls, no field mutation, no quantifiers. Bend pays for full dependent types
with near-total annotation; A7 should take the narrow fragment instead.

**What it fixes.** SAF-1 (the caller proves non-nil, or the signature says
`requires p != nil`), S11 (slice parameters become usable), and the general
complaint that A7's proofs are all-or-nothing.

**Cost and risk.** New keyword: a corpus scan must measure how many programs use
`requires` as an identifier. Every call site gains a discharge step, so the
safety pass needs call-site facts it does not have today — that work is track 5
and the typed IR (Wave 3), so B1 lands after them, not before.

**Approval:** yes, new syntax. Packet P-CON, after the correctness exit.

## B2. Make the wall between proved and assumed explicit

**Bend.** Consistency is kept by a split: "Code that runs is checked *live*;
types, erased arguments and equations are checked *dead* … nothing dead ever
counts as live evidence."

**A7 today.** The same boundary exists — the safety pass proves, the backend
emits code that assumes — but it is implicit. The audits found approvals that
survive transformations they should not (folding replaces a node and the
approval keyed by `id()` follows the wrong one, ZIG-1 = SAF-7), operations that
emit with no obligation at all (ZIG-7 runtime shift, ZIG-38 overflow, ZIG-8
inactive union field read), and a diagnostic set with no machine-readable
category (SAF-22).

**Proposal.** An obligation ledger in the typed IR: every obligation carries an
id, a kind, a span and how it was discharged; every backend site that may emit
an unchecked operation names the obligation id it relies on. Then two
enforcement points that cost nothing to keep:

- A test that fails if any approval site emits without a discharged obligation.
- A `--mode obligations` dump, so a user can see what the compiler proved and
  what it assumed. That dump is also the answer to the missing trap contract
  (checklist gap 8): what the program does when a proof is impossible is a
  visible property, not a hidden one.

**Approval:** none. No program changes; this is compiler plumbing. It belongs in
Wave 3 with the typed IR, and the ledger should be designed before the IR, not
after.

## B3. One owner means in-place mutation

**Bend.** `Array<T>` "has exactly one owner at all times. That is what lets
`a[5] <- 42` overwrite the slot and hand back the same array, with no copy." A
read returns the array alongside the element so the array is not lost.

**A7 today.** The memory plan's phases on storage reuse are still open
(`docs/plan/memory.md`), and value semantics for collections is the core
question of gate C1/C2 there.

**Proposal.** Adopt the rule, not the type system. Bend forces uniqueness with
affine types; A7 has no affine types and does not need them — the compiler can
prove uniqueness where it holds and copy where it does not. The Bend rule gives
the memory plan a concrete answer for the common case: a write through a
uniquely owned array is in place, and uniqueness is a proof obligation like any
other. Bend's "read hands the array back" is the part to skip; it exists because
Bend's values are affine, and it makes ordinary code read strangely.

**Approval:** it is a memory-plan gate decision (M-gates), not a separate packet.

## B4. Parallelism as an annotated call, if concurrency happens at all

**Bend.** `f!(x)` marks a parallel call; the scheduler is fork-join with no task
migration. No threads, no locks. The disclosed cost: "Parallelism requires
balanced calls."

**A7's gate G7** is open with no shape chosen. A7 permits `ref` parameters to mutate caller storage. Immutable argument
bindings do not establish independent calls. A7 needs checked read/write effects
and alias relationships before scheduling calls in parallel. Unknown effects
remain sequential under L40. A small explicit API remains a future decision.
Bend's runtime uses workers and synchronization internally; a simple user API
does not make that work disappear.

**Approval:** gate G7, with Bend's limitation quoted as a known cost.

## B5. Recursion: the ban versus a termination check

**Bend.** Live recursion is allowed and must be proved terminating, with
`@unsafe` to opt out. There is no C stack: "a call is a jump".

**A7.** Source recursion is banned outright (SPEC 6.2), and the compiler's own
internals are moving to the same rule (the NOREC batches).

**Observation worth recording.** The two projects buy the same property — a
bounded stack — in different ways. Bend compiles calls into a flat state machine,
so depth is a heap question. A7 emits Zig and inherits the host stack, so the ban
is what keeps depth bounded. That means the ban is a consequence of the backend
choice, not of the safety model. If A7 ever emits an explicit machine instead of
recursive Zig calls, the ban becomes a choice again rather than a necessity.

**Recommendation.** Do not reopen it now. Record it as an option under gate G4
with this reasoning, so the decision is made with the real trade-off visible.

## B6. Erased arguments

**Bend.** Quantities mark a variable erased (`-A`, gone at run time) or reusable
(`+A`).

**A7.** Generic specialization is incomplete (`docs/STATUS.md`), and nothing
states which generic arguments must not exist at run time. Marking type
arguments erased makes the monomorphization contract explicit and gives the
generics work a rule to test against. Small, and it should wait for the generics
audit in the 2026-09-18 round.

## B7. One honest limitations list, where a user reads it

Bend's README ends with 30 plain lines: no debugger, no LSP, terse errors,
strings are linked lists, the compiler is 99% AI-written and unaudited. A user
knows what they are getting before they install.

A7's equivalent is spread across `docs/STATUS.md`, SPEC Appendix E and the plan.
The language audit checklist is the first place it exists in one piece, but that
file is a planning document, not something a user reads.

**Proposal.** A "Limitations" section in `README.md`, derived from the checklist
and STATUS, listing what does not work today in one place: no slice parameter
indexing, no user-stated invariants, the stdlib surface (3 io functions, 10 math
functions), no formatter, no language server, no debugger mapping, parsed-only
syntax, one supported platform.

**Approval:** none; it is a docs change and the Docs Accuracy rule in CLAUDE.md
already requires the parsed-only half of it.

## What not to take

- **Removing inference to make the checker fast.** Bend states the trade
  plainly. A7's checker is not the bottleneck; its problem is soundness. More
  annotation would not fix a single audit finding.
- **Shipping an unaudited compiler.** Bend says "The compiler (not kernel) is
  99% AI-written and has not been fully audited yet" — honest, and the opposite
  of what this repository is currently doing.
- **`Type : Type` with a live/dead wall.** The wall is worth copying; the
  permissive theory behind it is not, because A7 has no dependent types to make
  consistent.

## Order

| Item | Needs | Approval | When |
| --- | --- | --- | --- |
| B2 obligation ledger | typed IR design | none | Wave 3, design first |
| B7 limitations section | the checklist | none | now |
| B3 one-owner in-place write | memory plan gates | M-gate | memory plan |
| B1 `requires` contracts | B2, call-site facts (track 5) | packet P-CON | after the correctness exit |
| B6 erased arguments | generics audit | packet | with generics work |
| B4 parallel call annotation | B1-style obligations | gate G7 | after v1 core |
| B5 recursion reconsidered | a non-recursive backend | gate G4 | not now; recorded |
