# Proposed v1 completion roadmap

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it; the current plan is the [v1 plan](../../plan/README.md).

This roadmap was proposed for agreement on 2026-09-14. It is an implementation
plan based on the audit, not release approval. A7 is not ready for v1
qualification.

## Scope to agree

Complete a defined, self-consistent language and developer product. Start with
the currently documented language and release gate. Resolve conflicting or
explicitly unfinished promises before implementing them. Do not treat every
research proposal as a v1 requirement.

Recommended boundary (cited as `completion-roadmap.md:15-18` in
docs/plan/decisions.md): one qualified Zig backend, the existing CLI and package,
the documented supported language subset, trustworthy diagnostics, accurate
documentation, and a usable website. Keep experimental numeric types, GPU/AI
work, package-registry infrastructure and concurrency outside v1 unless separately
accepted. Existing reference, memory and aggregate operations need a supported
policy; leaving them accepted without adequate checks is not a completion option.

Note (2026-09-16): v1 scope replaced by ledger L1, L7. Numeric redesign follows
L3–L5 and L16; AI and concurrency are now in v1. Package-registry work stays out
of scope. The plan keeps this roadmap's correctness phases and exit evidence as
tracks 1, 2, 3, 12 and 13.

For each feature, record syntax, semantics, support status, failure behavior,
native evidence, documentation and remaining limits. An unsupported feature must
receive an A7 diagnostic before emission. A documented gap must not be relabelled
as a completed feature.

## Ordered work and exit criteria

| Phase | Work | Evidence required to close |
| --- | --- | --- |
| 0. Freeze the contract | Map SPEC and research claims to the current implementation. Decide overflow, references and ownership, union access, uninitialized values, escaping slices, module cycles, visibility, numeric conversion and supported complexity limits. | An agreed feature matrix and decision record. Every unresolved rule is explicitly deferred or assigned a v1 requirement. |
| 1. Protect compilation and enforce current promises | Prevent source/output collisions and misleading artifacts. Make parser recovery fail compilation after source errors. Correct stale proof facts across assignments, branches, loops, calls and scopes. Close documented recursion-ban bypasses. | Real CLI filesystem checks preserve input bytes and report only actual artifacts. Malformed programs never silently lose declarations. GLM reviews cybersecurity and memory changes with positive controls and rejection cases. |
| 2. Complete front-end validation and diagnostics | Correct token boundaries and malformed numeric handling, parser progress, spans and import origins, literal-fit contexts, aggregate validation, symbol identity, call signatures, module identity and privacy. Replace internal exceptions for source errors with useful diagnostics. | Valid and invalid source run through the public CLI in human and JSON modes. Exit categories and original locations agree across imports and modes. Supported programs reach native compilation; unsupported forms fail in A7. |
| 3. Qualify transformations and backend behavior | Fix exact constant division/remainder, naming and loop bindings. Review pass ordering, type/span preservation, hoisting, generic specialization, import lowering, short-circuiting, side effects, mutation and copying. | Independently specified results match folded and non-folded native programs in Debug and the selected release profile. Reachable native entry points exercise each supported lowering. No helper may silently bypass semantic errors. |
| 4. Complete the memory model | Implement the accepted lifetime, alias, deletion, deferred cleanup, allocation provenance, union and initialization policy. Reject constructs that cannot yet meet the chosen guarantees. | Dedicated GLM review of the whole affected pipeline, then GLM follow-up on fixes. Compile-only findings remain distinct from runtime evidence. Meaningful integration and adversarial checks demonstrate each claimed guarantee within explicit limits. |
| 5. Finish documentation and the website | Correct version stamps, transcripts and release claims. Fix search corpus/fragments, mobile access, modal focus behavior, instruction structure and content organization. Review typography, responsive layout and visual consistency against actual captures. | Repo docs and generated agent docs agree. A fresh install-to-first-program journey succeeds. Keyboard, screen-reader, zoom, mobile and error-state checks are recorded. Performance findings have measurements, not source guesses. |
| 6. Qualify the release | Audit the actual locked dependencies. Reconcile workflow claims and artifact provenance. Verify package contents, clean installation and release assets. Reconcile every reviewer finding and rerun the full gate at the candidate revision. | Full gate passes with no hidden known failures. GLM cybersecurity disposition is recorded. Native artifacts and wheel installation succeed in named target environments. Site acceptance and docs parity are complete. Release approval names the exact revision and remaining nonblocking limitations. |

Note (2026-09-16): phase 0's overflow and numeric-conversion items are partly
decided by ledger L3–L5 and L16 (the rest is open under gate G3). Phase 4's
deletion, deferred-cleanup and ownership direction is superseded by L15, L17–L19
and L21; see the [memory plan](../../plan/memory.md).

Phases 2 and 3 and the website work can proceed in separate files after scope
agreement. Memory-policy decisions must precede dependent changes in phases 1
and 4. Release qualification follows integration; individual reviewer approval
does not replace the combined gate.

## Decisions that need agreement

The recommended defaults are conservative. They are proposals, not new language
rules.

1. Keep the present small language scope. Reject unfinished constructs unless
   their complete semantics and verification are included in v1.
   Note (2026-09-16): superseded by ledger L1, L7.
2. Preserve the fail-closed safety promise. Unknown proof facts must not approve a
   risky operation. GLM should assess the tradeoff between conservative rejection
   and more precise analysis.
3. Define fixed-width overflow and evaluation order before widening arithmetic
   support. Exact representable integer folding is already a correctness fix,
   independent of the overflow decision.
   Note (2026-09-16): overflow for integer `+`, `-` and `*` is decided by ledger L5
   (wrapping). Division, shifts and casts remain open under gate G3.
4. Adopt one explicit ownership and deferred-cleanup policy. Defer must preserve
   legal reads before scope exit while preventing conflicting cleanup. A variable
   that once held a heap allocation is not permanently safe to delete.
   Note (2026-09-16): direction superseded by ledger L15, L17–L19, L21; see the
   [memory plan](../../plan/memory.md).
5. Enforce documented file privacy through symbol resolution. Retain private
   declarations that public functions need internally. Decide import cycles
   separately instead of deriving a language rule from dead loader code.
6. Keep parser recovery for diagnostic collection only if any recovered source
   error still makes compilation fail. Silently dropping a declaration is never
   successful compilation.
7. Choose and document the release optimization profile. Changing the profile
   alone cannot repair A7 proof errors or qualify memory safety.

## Test strategy

The exact test-quality rule is now in `AGENTS.md`. Current additions use real
files, the public CLI and real native builds. They contain no mocks, skips or
expected-failure masking. They expose failures rather than making the gate look
healthier.

- Keep a requirement-to-evidence table for each fix.
- Prefer a valid control and a distinct failing boundary over equivalent
  permutations.
- Add native behavior checks where semantics survive several compiler passes.
- Use generated or property-based cases only when their invariant is stated
  independently of the implementation.
- Do not execute memory-corruption fixtures as ordinary host tests; GLM owns their
  verification design.
- Replace the bool-only defer/delete assertions identified in the test review with
  assertions about the accepted or rejected requirement and its diagnostic.
- Review helper paths that bypass semantic validation.
- Test count and coverage percentage are not acceptance goals.

## Present evidence and remaining work

- Baseline full gate: 12/12, with 2,511 pytest passes.
- Current full gate after 16 new cases: 11/12, with 12 pytest failures and 2,515
  passes. The new cases contain 12 failures and four passes.
- A separate low-recursion test fails with `python -m pytest` but passes in the
  configured `uv run pytest` gate. Qualify that invocation-sensitive limit.
- Site build/lint and 259 internal generated links pass after docs cleanup.
- Browser interaction, visual acceptance and measured site performance remain
  unverified. Playwright fallback permission is pending.
- Passing the existing dependency command did not audit the project dependency
  environment. GLM must qualify a corrected command and its target inventory.

The [audit matrix](audit-matrix.md) contains the detailed questions and probes.
The [coordinator review](root-review.md) separates reproduced findings from
advisory claims. Scope agreement starts implementation; it does not approve a
release.
