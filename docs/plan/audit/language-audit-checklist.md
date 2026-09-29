# Language audit checklist

Status: working document, started 2026-09-18 at the user's request ("audit
everything in every aspect of the language, and a checklist"). It records what
has been audited, what each audit found, where the fix or the approval lives,
and what nobody has looked at yet. The checklist itself changes no behavior and
needs no approval; rows that propose a language change name the packet that will
carry it.

Companion files, both written 2026-09-18 by a read-only survey; every cell in
them cites a file and line, and every "none found" names the grep that found
nothing:

- [`language-evidence-map.md`](language-evidence-map.md) — 75 aspects (52
  language, 15 compiler and tooling, 8 project), each with its SPEC section,
  implementation files, audit coverage, findings with severities, fix batch,
  approval gate or packet, tests, docs and status.
- [`language-interactions.md`](language-interactions.md) — 31 cross-feature
  interactions a finding already records, then 14 pairs no audit and no test
  covers.

Everything these audits found that no batch, gate or packet owns is collected in
[open-items.md](open-items.md), grouped by area.

## 1. Audit coverage

Of 75 aspects: **64 audited, 6 covered only incidentally, 5 never audited.**

The gaps below were closed by the 2026-09-18 audit round
([index](../../audits/2026-09-18/README.md)): seven reports, about 145 findings.

| Report | Findings | The result in one line |
| --- | --- | --- |
| [methods](../../audits/2026-09-18/methods.md) | 16 (7 NEW, 2 CRITICAL) | A7 has no methods, only free functions with a `ref` first parameter, and neither SPEC 6.5 example compiles |
| [stdlib](../../audits/2026-09-18/stdlib.md) | 18 (8 NEW) | The callable stdlib is 14 functions; five missing pieces have no owner |
| [visibility and modules](../../audits/2026-09-18/visibility-modules.md) | 17 (12 NEW) | Imports leak in both directions, cycle detection is dead code, and `Name :: OtherType` is never parsed as a type alias |
| [production readiness](../../audits/2026-09-18/production-readiness.md) | 38 (25 NEW, 2 CRITICAL) | None of the five promised workflow commands exists, and all twelve 2026-09-14 security findings are still live |
| [examples and tests](../../audits/2026-09-18/examples-tests.md) | 36 | Mutation testing shows 47% of the suite asserts nothing that could fail; breaking operator precedence leaves 2,571 of 2,594 tests passing |
| [design gaps](../../audits/2026-09-18/design-gaps.md) | 21 (all NEW) | All 16 SPEC 9 code blocks fail to compile, and gate G7's own example violates two memory gates |
| [language features](../../audits/2026-09-18/language-features.md) | 29 (6 CRITICAL) | A 193-line text tool needed three rewrites to compile; splitting it across files broke it |

What they add to the picture, beyond their own components:

- Two more silent-deletion defects, the same class as the parser's declaration
  drop: `x, y := 10, 20` emits a file containing only `var y = 10;` (PRD-33), and
  a module-qualified name in a type or generic position deletes the enclosing
  declaration (VIS-5, MTH-12).
- The call boundary carries nothing in either direction: a call invalidates no
  facts (MTH-2, the probe for KNOWN S3), and a `ref` parameter is assumed
  non-nil with no call-site proof (MTH-1 = SAF-1). Both are miscompiles that
  build.
- Type aliases of an identifier were never implemented (VIS-1), which is the
  root cause of the broken struct alias in the methods audit and makes the
  circular-alias diagnostic unreachable. The module redesign does not cover it.

These five aspects had never been audited before that round; each now has a
report, and what follows is why each mattered.

| Was not audited | Why it mattered |
| --- | --- |
| Methods | `examples/017_methods.a7` passes, but SPEC contradicts itself: `docs/SPEC.md:806-831` documents receiver functions as working while `:473-475` calls method-call sugar planned. TYP-14 (`types.md:337`) approves implicit `ref` arguments for exactly that call shape |
| Tensors and array programming (SPEC 9) | 360 SPEC lines with no implementation (`grep -rni tensor a7/` finds nothing), and the SPEC text is self-inconsistent: the broadcast example contradicts the rule it states (`docs/plan/README.md:393-394`) |
| Concurrency | Gate G7 only; SPEC has no section |
| FFI and the native boundary | Track 10 and memory gate M25, which records that the native declaration surface "has no syntax today" (`docs/plan/memory.md:623`) |
| Editor and developer tooling | Nothing exists: no formatter, language server, syntax grammar, or mapping from generated Zig back to `.a7` lines |

Incidental only: type aliases, visibility (`pub`), stdlib `mem`, stdlib
`string`, `Option`/`Result`, and the examples corpus.

Three things the survey found that no plan row owns:

- **SAF-32, SAF-33, SAF-34 have no fix batch.** The fix-plan tables stop at
  SAF-25 (`docs/plan/fix-program/backend-fix-plan.md:521-565`) and
  `execution.md:139` resumes at SAF-26.
- **CI has no owner.** SEC-3 (mutable `oven-sh/setup-bun@v2`) and SEC-4
  (unpinned `pip install uv`), found 2026-09-14, are still live at
  `.github/workflows/deploy-docs.yml:28` and `ci.yml:35`.
- **Appendix B.1 defines error codes E0xxx-E4xxx that no diagnostic emits**
  (`grep -rn 'E[0-9][0-9][0-9][0-9]' a7/` finds nothing).

Two coverage holes in the tests and examples:

- No test mentions integer overflow or wrapping, though ledger L5 locks
  wrapping semantics.
- No example uses slices, `.len`, `pub` or `@type_set`, and only
  `examples/014_generics.a7` uses `$T`.

## 2. Completeness gaps

Source: an independent GLM-5.3 review on the zai-coding-plan provider
(`tmp/glm/checklist-completeness.md`, `claims checked: 84`), plus the spot checks
below. A row is marked **checked** only where this session confirmed it against
the repository; the rest are the reviewer's claims and stay **unchecked** until
an auditor confirms them.

| # | Gap | Evidence | Plan location | Status |
| --- | --- | --- | --- | --- |
| 1 | Numbers cannot be parsed from or formatted into text | `a7/stdlib/io.py` registers only `println`, `print`, `eprintln`; `a7/stdlib/math.py` 10 functions; `mem.py` and `string.py` are empty stubs, and `std/mem` and `std/string` are not even in `STDLIB_MODULE_ALIASES` (`a7/stdlib/__init__.py:11-16`). SPEC 10.3 lists them as planned | Track 8b (stdlib), no batch | checked |
| 2 | No sorting anywhere | grep of `docs/plan/README.md`, `execution.md`, `STATUS.md`, `SPEC.md` finds "sort" only as Kahn topological sort in the compiler | Not in plan | checked |
| 3 | Method-call syntax (`a.append(1)`) is used by the memory plan's own examples but exists nowhere in the language | SPEC 6.5 "Methods" (lines 806-831) defines methods as free functions with an explicit receiver, called as `length(v)`; there is no `x.m()` call form. `docs/plan/memory.md:182-186` marks `a.append(1)` "Proposed syntax" | Needs a packet before track 8a (collections) | checked |
| 4 | `assert`, `assert_msg` and `panic` are specified but not implemented | SPEC 11.2 lines 1616-1619 list them; SPEC 1578-1580 says the list is "planned API shape, not current implementation"; no registry entry | Track 8b; the planned `a7 test` command (STATUS priority 6) has nothing to assert with | checked |
| 5 | No editor support (LSP, highlighting) | grep finds no "LSP" or "language server" in SPEC, STATUS, README or execution.md | Not in plan | checked (absence) |
| 6 | No debugging story: generated Zig has no mapping back to `.a7` lines | `docs/plan/memory.md:743` lists "Debugger and profiler views" among the plan's own open items; no track owns it | Not in plan | checked |
| 7 | No abstraction seam for user code: type sets list concrete types, so a library cannot accept "anything that can write" or "anything comparable" | SPEC 7.3 (lines 941-971): `@type_set(...)` enumerates primitive types and constrains generic parameters; grep for "interface", "trait", "vtable", "dyn" in SPEC, README and execution.md finds only accelerator-backend interfaces (`docs/plan/README.md:41,512`), not a language feature | Not in plan | checked |
| 8 | No contract for what a program does when it stops at run time, or how the message names A7 source | `docs/SAFETY_CONTRACT.md:3-6` covers only proofs before emission ("fail closed"); `docs/plan/memory.md:628` (M39) offers a "runtime check with a defined stop" as an alternative but defines no stop. grep for "stack trace", "panic message" and report-line wording in SAFETY_CONTRACT.md and SPEC.md finds nothing; the only run-time stops today are the backend's own `@panic` calls on write failure (`a7/backends/zig.py:173-174`) | Gate M39; no packet | checked |
| 9 | No environment-variable access | grep finds no "getenv", "environ" or "environment variable" in SPEC, STATUS, README or execution.md | Not in plan (args are packet P9) | checked (absence) |
| 10 | No language-version or migration policy beyond ledger L2 | L2 (`docs/plan/decisions.md:37`) allows documented breaking changes under the approval rule, but names no version scheme, deprecation window or migration tool | Not in plan | checked |

Smaller items the same review lists as absent: linter, syntax-highlighting
grammars, REPL or playground, a compiler fuzzing campaign beyond the random
parser tests, bit intrinsics (popcount, rotate, byte swap, endianness),
user-facing checked or saturating arithmetic, compile-time function evaluation,
cross-compilation as a documented capability, and a conformance suite indexed by
SPEC clause.

## 3. Interactions nobody has checked

Every defect found on 2026-09-17 and 2026-09-18 was an interaction between two
features, not a feature failing alone: `defer` with the facts a loop carries,
`for`-in with shadowing, `::` constants with shadowing, a local name with a
module alias, compound assignment with `char` and `bool`.
[`language-interactions.md`](language-interactions.md) lists 31 such
interactions already on record, and 14 pairs with no finding and no test. The
ones most likely to hide a defect of the same kind:

| Pair | Why it is a candidate |
| --- | --- |
| Generics x modules | The module redesign introduces `alias.Box(i32)` (`docs/plan/execution.md:67`) and no test covers a generic reached through an alias |
| `match` x unions | `case ok` captures the whole union instead of testing the tag (KNOWN B2), and union field reads carry no safety obligation (ZIG-8) |
| `defer` x loops and `break` | The C4 verification found exactly this class; 12 test files contain both keywords and no test joins them |
| Casts x constant folding | No test file contains both; SAF-14, SAF-28 and SAF-33 all live here |
| Methods x generics | Methods are unaudited and no test joins them |
| Imports x visibility | Visibility is not enforced at all (PIP-7) and no example uses `pub` |

## 4. Order of the remaining work

Correctness first (ledger L23), so the order is:

1. **Finish Wave 1R-a** — C1 and C4 fix rounds, C2 verification. In progress.
2. **Audits of aspects that touch batches already in flight**, in this order:
   methods (TYP-14 approves the receiver call shape today); the stdlib registry
   against SPEC 10.3 and 11.2 (C2 changes how those names resolve); the
   diagnostics system as a whole (SPEC Appendix B against real messages,
   line and column, JSON shape, the unused error codes); the CLI's path and
   output handling (4 of the 12 known failing tests are here); generics and
   specialization; the formatters and `--doc-out`.
3. **Project-level audits:** the test suite as a whole against the test-quality
   rule, the examples corpus, docs drift, `scripts/` and the release gate, CI
   (unowned today), and a re-check of the 2026-09-14 security findings.
4. **Design aspects** (tensors, concurrency, FFI, `Option`/`Result`, methods as
   a language feature): these need decisions, not audits. Each goes to its gate
   (G5, G7, G8) or to a packet, with examples for approval.
5. **Completeness work** from section 2, after the correctness exit.

An audit adds rows to the packets and to this checklist; it changes no
behavior, so it needs no approval to start. Every fix it proposes follows the
usual rule: no approval when the program is already rejected, hangs, crashes or
miscompiles; a packet with before-and-after examples otherwise.
