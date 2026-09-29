# Open items: defects, corrections and decisions with no owner

Everything found on 2026-09-17, 2026-09-18 and 2026-09-19 that no batch, gate or
packet in [the execution plan](../execution.md) owns yet. Each entry cites its
evidence. Read this before planning the next wave.

Sources: the seven audits in [docs/audits/2026-09-18](../../audits/2026-09-18/README.md),
the batch verifications in `tmp/reports/`, and the research programmes under
[research](../research/README.md).

## Core V1 implementation, 2026-09-20

The [current batch evidence](../../audits/2026-09-20-core-v1/README.md) records
iterative module loading, type display, console labels, CLI workflows and release
checks. Backend probes cover array assignment evaluation order, character escaping,
deferred return values and unused constants. These are trigger-level repairs.

Before the follow-up integration, fresh [critical safety probes](../../audits/2026-09-20-core-v1/critical-safety-revalidation.md)
accepted the original SAF-2, SAF-3, SAF-4, SAF-6 and SAF-8 cases. The SAF-4 correction now removes stale guard reinjection. Isolated tests, a
corpus comparison and independent native controls passed; the integrated gate
is running.
The simple SAF-2 candidate rejects a valid guarded program and is not ready.
The [field-path draft](../packets/P-SAF-field-paths.md) records that limitation.
Do not infer complete safety from the aggregate gate or from historical closure.

The closure review also found an unused-loop-label failure. An A7 `@outer for`
loop with an ordinary update compiles but Zig rejects its unused label. Adding
`continue outer` builds successfully. This remains open alongside scope-aware
constant usage. The [fresh failure/control record](../../audits/2026-09-20-core-v1/unused-loop-label.json)
contains exact source and compiler/native diagnostics.

## Scoped GLM audit repairs, 2026-09-19

The user authorized repairs after the full GLM-5.3 language review. The
[remediation report](../../../site/docs/audits/glm-5.3-remediation.md) records
current evidence and remaining limits. Earlier bullets below remain historical
records; their wording does not reopen these verified trigger-level repairs:

- Silent parser declaration loss, malformed-number internal errors, and unused
  nested recursion acceptance.
- The six crashing safety probes, plus nil guards after deferred, loop, and
  callee deletion. Branch joins and loop/call invalidation now reject stale facts.
- Wider arithmetic result typing, defined wrapping, compound division/remainder,
  IO braces, backend names, string-array defaults, and wrapped generic fields.
- Contextual literals, literal constant array aliases, root entrypoint signatures,
  cycle diagnostics, and match fallback JSON serialization.
- The self-derived cast-policy matrix and the missing exit-8 JSON diagnostic test.

These repairs do not close all alias/lifetime or numeric policy questions.
General module-qualified types, generic reference read/write semantics, and
planned language/library operations remain separate work. Consult the report
before carrying a historical finding into another repair batch.

## Closed on 2026-09-19 by the repository audit and cleanup

A separate session audited and repaired this working tree on 2026-09-19 between
20:02 and 20:43 (see [docs/audits/2026-09-19](../../audits/2026-09-19/README.md),
with five independent GLM reviews). Its gate passed all nine checks with 2,629
tests and no failures, so the 11 known failing tests this plan gated against are
gone. Items below that it closed, kept here so the evidence trail survives:

- The four `test_pipeline_artifacts` failures: `--output` and `--doc-out` could
  overwrite the source or a loaded module, and failed runs advertised stale
  artifacts. Destinations are now validated against every loaded source and
  every other output, including symlinks and hard links, before any write, and
  an output path is assigned only after a successful write.
- The four `test_pipeline_diagnostics` failures: operator columns were wrong,
  imported errors lost their origin, and an imported parse error surfaced as an
  internal fault (exit 8).
- The three `test_pipeline_native` failures: Zig keywords, unused loop captures
  and shadowed captures produced bindings that would not build. Fixed under
  ledger entry L34.
- Float remainder disagreeing between constant folding and run time
  (`-5.5 % 2.0` folded to 0.5 where run time gives -1.5). Fixed under ledger
  entry L33; folding now truncates and preserves signed zero.
- The secrets scan reading ignored downloads: it now enumerates tracked and
  non-ignored files, with a regression test that force-added ignored secrets
  stay in scope.
- The dependency audit running against the isolated tool environment rather
  than the project's locked requirements.
- The five research links pointing at an unwritten optimization report.

Closed later on 2026-09-19, in this session:

- SEC-3 and SEC-4 from 2026-09-14: `oven-sh/setup-bun@v2` was mutable at three
  sites and is now pinned to commit `0c5077e5` (v2.2.0); `python -m pip install
  uv` was unpinned at three sites and is now `uv==0.12.15`. All five workflow
  files still parse.
- Three documents claimed typed math spellings such as `sqrt_f64` are callable
  bare builtins (`site/public/docs/stdlib.md`, `site/public/llms-full.txt`,
  SPEC 11.2). A probe exits 6; all three now say they are a planned API shape.
- The public status page listed four active priorities against `docs/STATUS.md`'s
  six and had dropped three known gaps; both sections now match.
- `CLAUDE.md` said file-backed local imports "currently fail closed before
  codegen". A two-file probe compiles with exit 0 and the imported function is
  in the output, so the line now says they are merged into the single Zig
  output.
- pytest had no `testpaths`, so a bare `pytest` walked the whole tree and
  collected test files from scratch directories — which broke a gate run on
  2026-09-18. `pyproject.toml` now sets `testpaths = ["test"]`; a planted stray
  test in `tmp/` is no longer collected, and `uv build` still succeeds.

## Safety

- P-SAF (from r1a-c4 impl, 2026-09-17): SAF-25 second step. `x := 5; { defer { x = 0 } }; 10 / x` and the `if c { defer { x = 0 } }` form are accepted, build, and divide by zero at run time. Dropping facts for variables a deferred statement assigns, at block exit (and surviving the restores at if/while/for exits), rejects them. Rejects programs that build today.

- P-SAF (from r1a-c4 impl): deleted-variable state around `defer`. Restoring it after a deferred statement makes `del b; defer { b = new Box }; b.value` rejected (builds today, reads freed memory) and `defer { del b }; b.value` accepted (wrongly rejected today). Needs a rule for when a deferred `del`/assignment takes effect.

- P-SAF (from r1a-c4 verify, 2026-09-18): pre-existing programs that build today and divide by zero at run time: `defer { x = 0 }` inside a loop (d02), the defer-free loop form (l01), d04 and d09. Root cause is KNOWN S2 (the safety pass visits a loop once, with no fixed point).

- NEW from the methods audit (2026-09-18, docs/audits/2026-09-18/methods.md): MTH-2 is the live probe for KNOWN S3 (a call invalidates no facts): `x := 4; if x != 0 { zero_it(x); 100 / x }` compiles, builds and emits `@divTrunc(100, x)` after the call set x to 0. Belongs with the SD/SE proof-repair batches and P-SAF.

- NEW MTH-16: no struct field is ever a safety fact, so `c := Cfg{d: 4}; 100 / c.d` is rejected even when guarded.

- NEW, and the largest test finding so far (2026-09-18, docs/audits/2026-09-18/examples-tests.md): mutation testing proves the suite does not test the compiler. Replacing `classify_cast` with a constant leaves 2508 of 2587 tests passing (60 catch it); making `get_binary_precedence` a constant, so `1+2*3` parses as `(1+2)*3`, leaves 2571 of 2594 passing (4 catch it). 1223 of 2587 tests (47%) assert nothing that could fail. `test_cast_safety_matrix.py` is 48% of the suite and computes its expectations with the function under test. Three parser files are one assertion form each (`assert ast is not None`, `assert result.kind == PROGRAM`). This is a test-repair program, not a single batch; it belongs in the plan as its own lane with the mutation harness kept as the acceptance check.

- DSG-4 (FFI): the chain is M25 -> M12 -> M43 -> track 10 -> AI step 4 (BLAS, L9) -> track 11 -> phase F -> track 6b -> track 13. M25 is blocked by nothing and phase A's exit evidence already needs it open; the only draft (docs/lang-safety/edge-cases/12-ffi-boundary.md) uses vocabulary its own notes supersede. Open M25 now.

- NEW from the language-features audit (2026-09-18, 29 findings, 6 CRITICAL): LNG-02, `char` supports only `==` and `!=` — no ordering, no arithmetic, no cast to an integer — so `is_digit`, `to_lower` and `'7'` -> `7` are all impossible. LNG-04, a value taken from a parameter, a struct field or a call can never be an index whatever guard precedes it, so no bounds-checked accessor can be written. LNG-12, an `if c != 0` guard does not survive a `cast` on the divisor, so an average is uncomputable. LNG-15, a `::` constant as an array size makes the array unindexable (root cause SAF-21). LNG-16, a file with no `main` exits 0. LNG-10, exhaustiveness is checked for enums only and six other match shapes pass A7 and fail Zig. LNG-03 (KNOWN PIP-6, new scale): an imported module whose functions call each other emits "use of undeclared identifier", capping multi-file A7 at one function per imported file.

- NEW from the prevention research, about A7's own obligations (cited to code, not plan): `a7/safety.py` declares eight obligation kinds, but `UNION_FIELD` has zero producers and `_prove_integer_overflow` begins with an unconditional `return`, so its body is dead code; `REF_NON_NIL` is defeated at call sites (SAF-1). Release builds use `-OReleaseFast`, so safety checks are off and every obligation gap is a release-mode gap with no runtime backstop. `docs/lang-safety/comparative/bend.md` and `docs/plan/research/bend-for-a7.md` say A7 has four obligation kinds; both lag the code and need correcting.

- Three separate fixes, in cost order, for "a panic names the user's own file and line": (1) bake an A7 `file:line` constant into the panic messages the A7 backend emits itself — Rust's model, no DWARF, no unwinder, survives `-fstrip`; (2) a side-car span map plus a runtime DWARF lookup for Zig's own inserted safety checks, which pass only `@returnAddress()` and work only in Debug and ReleaseSafe; (3) rewrite the emitted `.debug_line`, which also buys stepping. Note that a ReleaseFast fault prints nothing at all today, because Zig's segfault handler is disabled there.

- From the runtime-model claims audit (docs/plan/research/runtime-model/00-claims-audit.md, quotes fetched by curl and grep-verified, re-runnable scripts under tmp/research/runtime-model/sources/): A7 actions in order — (1) decide float determinism at gate G1, which is free because Zig is already strict; (2) memory gate M40: compile the same input twice under different hash seeds and compare, since Python salts string hashes by default and the compiler's own reproducibility is untested; (3) settle gate G7 so determinism is a design property while A7 still has no concurrency; (4) record that memory gates M4/M5 buy cheap snapshots as well as safety; (5) emit a source-line mapping into the generated Zig.

## Type system and language surface

- P-TYP (from r1a-t0v1 verify, 2026-09-17): `char +=`/`char |=` and `bool &=`/`^=` are accepted (Zig builds them) while the binary forms `c + d` and `a & b` are rejected. Decide one rule. Also 223 compound-assignment programs A7 accepts but Zig rejects (signed `/=` `%=`, float `%=`, `char <<= 'b'`, `char += f64`); pre-existing, class B candidates.

## Modules and visibility

- NOREC-0b (no approval; from r1a-norec0 verify): before the first NOREC conversion lands, (1) assert the scan with unresolved calls as edges finds the same groups; (2) model dispatch tables (class-body dict, dict of bound methods built in `__init__`, module-level dict); (3) stop flagging continuation lambdas pushed on an explicit stack and `self.b.run()` delegation to an unannotated receiver; (4) `repr=False` on `_Func.parent` in test/norec_scan.py:151 and include dataclass methods in the self-scan; (5) execution.md conversion table: add the `a7/types.py` `__str__`/`__hash__` cycles, the nested `base_identifier` self-loop in zig.py, and a batch for the 44 recursive dataclass methods.

- P-MOD (from r1a-pl02 verify, 2026-09-18): a global declared before the import that aliases the same name (`h := ...` then `h :: import "flat"`) compiles, builds and prints the global's value where SPEC A.3 makes the module call right (PIP-18). A live class-C miscompile PL-02 does not close; L28's alias-clash error is the MOD answer.

- Follow-up (from r1a-pl02 verify): enum variant names are the one binding form `_annotate_file_module_calls` does not count. Unreachable today because local enum declarations are rejected; revisit if that changes.

- NEW MTH-12: `sh.Counter{value: 1}` (module-qualified struct literal) silently deletes `main` — exit 0, no main in the emitted Zig. New manifestation of PAR-02 plus the F2 declaration drop.

- NEW from production readiness: an undocumented 1000-declaration cap corrupts `--format json` on a SUCCESSFUL compile (PAR-17's cap, new consequence); SPEC Appendix C's import depth limit of 32 fails at depth 2; every diagnostic in both formats goes to stdout and stderr is never used; no error code is ever emitted and `ErrorSeverity` is dead code; `@type_set(...)` — the one intrinsic CLAUDE.md exempts as working — exits 7 at codegen; `sqrt_f64` is advertised in three docs and exits 6.

- NEW from the visibility/modules audit (2026-09-18, 17 findings, 12 NEW): VIS-1 is the root cause of MTH-6 — `Ctr :: Counter` is never parsed as a type alias (`a7/parser.py:1515-1523` lists only primitive keywords, `ref` and `$T`), so any identifier right-hand side becomes a CONST. Aliases of structs, enums, unions, other aliases and generic instantiations all fail, while `Handle :: u64`, `[]u8`, `[3]f32` and `fn(i32,i32) i32` work. `Ctr{value: 1}` as a struct-literal head still builds, so one declaration is a type in one position and not in another. The circular-alias diagnostic is unreachable for identifier forms. No batch; MOD does not cover type aliases.

- NEW VIS-3: import-cycle detection is dead code — `load_module` returns from cache before the `loading_stack` check and caches before recursing, and `topological_sort` is called from nowhere. An A<->B cycle exits 6 with an unrelated transitive-import message.

- NEW VIS-4 (answers the unchecked "generics x modules" pair): `g.identity(5)` emits a call missing the comptime type argument (Zig: expected 2 arguments, found 1); the unqualified spelling infers the type argument but drops the module prefix. Neither spelling works. Generic types across files do work, because only FUNCTION declarations get `module_emit_prefix`.

- NEW VIS-5 (extends MTH-12): `x: h.Hnd` and `g.Box(i32){...}` each silently delete the enclosing declaration and emit Zig with no `main` that `build-obj` accepts.

- Seven of the visibility findings change a program A7 accepts and Zig builds today, so their fixes need approval; the report's MOD table says MOD answers VIS-2, 3, 5, 8, 10, 11 and partly 4, 6, 7, 12, 14, and says nothing about type aliases (VIS-1, 13, 16).

- NEW (from the C2 verification, 2026-09-18): batch C2 also fixes an unrecorded miscompile — a user module aliased `io` (`import "mine"` or `import "./mine"`) was rewritten into stdout printing. Needs a regression test and a ledger line.

- All 12 known failing tests are right and the compiler is wrong; none fails because the test is wrong. An imported parse error exits 8 (internal crash) and exit 8 is asserted nowhere.

- Docs discrepancy found by the prevention research (2026-09-18, not fixed, needs the owner's call): CLAUDE.md says local imports "currently fail closed before codegen", but `a7/compile.py` combines successful local imports into one AST that does reach codegen — which matches docs/STATUS.md. One of the two is wrong; CLAUDE.md is the likelier.

## Recursion rule

- NEW defect (from r1a-t0v1-fix verify, inferred from one example, unverified in audit): a parameter aliased locally (`h := g; h(n)`) where a top-level function is also named `g` links the call graph to top-level `g`, giving a false recursion error. Pre-existing in main. Candidate for T-lane (call-graph construction) after scope-aware lookup.

## Standard library

- UPDATE, 2026-09-19: the float-remainder part of the C1 verification below is
  fixed under approval L33. Constant and runtime `-5.5 % 2.0` now both produce
  `-1.5`; Debug and ReleaseFast regression checks cover the change. Other findings
  in that historical entry are not closed by this fix.

- NEW defects found while verifying C1 (2026-09-18, `tmp/reports/r1a-c1-verify.md`, pre-existing, not caused by any batch): (a) float `%` folds with Python's floor rule, so `-7.5 % 2.0` folds to 0.5 where run time gives -1.5; (b) stdout redirected to a regular file is overwritten at offset 0 on each `io.println`; (c) the parser rejects a `main` body of about 1196 lines (related to PAR-17's 1000-iteration cap); (d) the fits-the-type gate in const_eval is effectively "fits i32", because the type checker types every literal expression i32, so the u8/u64 paths are unreachable today.

- CORRECTION (2026-09-18, docs/audits/2026-09-18/stdlib.md): the "stdout redirected to a regular file is overwritten at offset 0" item recorded from the C1 verification is REFUTED for the current tree. Batch C3's `writerStreaming` change fixes it; four prints redirected into a file all persist in order. Keep the item only as a regression test to add: no test redirects a compiled binary's stdout into a file, which is the property C3 exists to guarantee.

- NEW from the stdlib audit: the named `@type_set` alias form SPEC 7.3 documents (`Ints :: @type_set(i32, i64)`) is an exit-7 codegen error, while inline constraints work; the tokenizer accepts any `@`-name, including `@1` and a bare `@`, and promises each one "parsed for future support"; `io.println` takes only a string literal and no document says so; a literal `{`...`}` pair in a format string is falsely rejected; `f := math.sqrt` as a value emits an undeclared identifier.

- Docs (no approval): `site/public/docs/stdlib.md:36-37` and `site/public/llms-full.txt:281-282` say the typed math variants "are available as bare builtins"; they exit 6. Extends PIP-23 to new locations.

- No owner at all (stdlib audit's missing table): number parsing, number formatting, ASCII classification, sorting, assertions. Assertions and ASCII need no design work.

- Correction to the checklist: "no sorting anywhere" is about the stdlib only. Sorting by hand works today (`examples/029`, and the audit's own tool sorts an array of structs by a field). Generics are not blocking either.

## Tests and examples

- Test config (no approval): pytest has no `testpaths`, so bare `pytest` collects `test_*.py` under `tmp/` and worktree scratch dirs. Add `testpaths = ["test"]`.

- Docs (no approval; MTH-4, MTH-5): SPEC 6.5 "Methods" is wrong three ways — neither example compiles (undefined bare `sqrt`; `self.x /= len` is rejected as a possible zero divisor), `:815` calls the receiver immutable while `:820` mutates it, and `:473-474` calls dot-call syntax planned while `:806-831` presents receiver functions as a feature with no status note. README, STATUS, the site docs and llms*.txt never mention methods or receivers at all.

- Track 8a blocker (MTH, question 6): no packet, gate or ledger entry owns dot-call syntax, and `docs/plan/memory.md:182-186` writes `a.append(1)` as "Proposed syntax" that A7 rejects. Either rewrite those examples as `append(a, 1)` (no approval) or open a packet for the syntax before Wave 5 phase C1.

- NEW: release binaries embed the absolute build path (27 `strings` hits for `/home/cx89/Projects/pl-dev/a7-py/...`); all 8 CI `runs-on` are `ubuntu-latest` (no platform matrix); `git tag -l` is empty, so the release workflow has never run.

- NEW: the real baseline on this tree is 19 failing tests, not 12. Seven `test_tokenizer_errors.py` failures come from `FORCE_COLOR=3` in the environment; they pass under `NO_COLOR=1`. Gate runs use `env -u FORCE_COLOR`, which is why the gate reports 12. Record the environment dependency in docs/audits/2026-09-16/baseline.md.

- Examples: `013`, `017` and `037` are shaped around a ref-mutability defect that does not reproduce on this tree or at HEAD, and `037:111-112` states it as a rule in the canonical language tour. `035_matrix.a7` is the only user of element-wise array `+` and has no test. SPEC has no output-formatting section, so the 43 goldens are the sole definition of `{}` formatting.

- Not scheduled anywhere: a rejected-on-purpose example, file I/O examples, `std/mem` and `std/string` coverage, a SPEC formatting section, exit-8 coverage, stderr as a separate golden stream, and allocation accounting for the two `new`/`del` examples whose goldens cannot observe `del`.

- DSG-2/DSG-3 (concurrency): three incompatible shapes are promised (`@parallel` in SPEC:1322, `task_group`/`spawn`/`Channel` in G7, the annotated parallel call in bend-for-a7 B4), the site says concurrency is deferred while ledger L1 puts it in v1, and gate G7's own example violates memory gates M10 and M36 — the owner would be reading a proposal that its own memory rules reject.

- Measured edit-to-binary loop today: 0.262 s front end plus 0.298 s `zig build-exe`, about 0.56 s for a 143-line example. No hot-reload argument can be made on latency grounds.

- Evidence that bears directly on the `requires` contracts proposal (docs/plan/research/bend-for-a7.md B1), from the finished prevention research (`claims checked: 162`): the annotation cost is the counterargument to write into the packet. Frama-C/WP on real avionics code (Dordowsky, arXiv:1508.03894, an independent SME, not the vendor): "the amount of instrumentation in form of assertions and loop invariants is in the same order of magnitude as the size of the source code, or even exceeds it", and 15 of 237 proof obligations for one function were never discharged. Tokeneer's own EAL5 summary (Praxis for the NSA, 2008): 9,939 lines, 260 person-days, 38 LOC/day overall against 203 during coding — four fifths of the effort went somewhere other than writing code — and its zero post-delivery defect figure carries the caveat "independent testing is ongoing", so it is a floor, not a result. No independent SPARK defect-density study exists; every published figure is authored by the builder.

- Also from that research, sharpening why a fixed obligation set is not obviously worse than a stated one: the Alloy robustness work on Tokeneer found nine anomalous scenarios the formal development and system testing both missed, all of them outside the specified envelope. A zero-defect result is zero against the specification you wrote, which is the same boundary failure Fonseca et al. measured.

## Debug information

- NEW, cheap and concrete (from docs/plan/research/tooling/08-agentic-debugging.md, measured on this machine with gdb 17.2 and Zig 0.16.0): A7 locals are invisible to a debugger because the backend emits them as `const`. Emitting `var` plus a `_ = &name;` discard makes the local reappear in `info scope` under its A7 name. Neither half works alone: bare `var` fails to compile ("local variable is never mutated"), and the discard after a `const` changes nothing. A confined codegen change, no language change, worth a batch.

- NEW, closes a design route: Zig 0.16 has no line directive and no source-path remap, and rejects a non-`.zig` extension. Zig issue #1833 ("source maps") is closed as not planned. The Nim `#line` approach is therefore unavailable to A7; the remaining options are a sidecar map (Cython's model), post-processing the DWARF line table, emitting DWARF directly, or debugger-side translation.

- PLAN CONFLICT to resolve (two repository documents disagree, one must change): the production-readiness audit's PRD-7 names batch SRC-MAP as the owner of the debug-info fix, while `docs/plan/audit/language-evidence-map.md:131` says "Wave 3 SRC-MAP `EXEC:155` is for compiler diagnostics, not debug info", and `docs/plan/fix-program/frontend-fix-plan.md:310` agrees with the evidence map. On the evidence map's reading, nothing in the plan owns debug info at all.

- NEW, actionable, from docs/plan/research/tooling/01-debug-info.md (measured on this machine): Zig's panic printer opens whatever file the DWARF line table names, at run time, so a corrected line table would make a panic print A7 source with no change to Zig. The A7 compilation unit's DWARF file table currently has exactly one entry (the generated `.zig`), and the binary contains zero `.a7` strings. Variables already carry their A7 names — only the coordinates are wrong.

- NEW: `-OReleaseFast` binaries carry 3,254,024 bytes of debug information, as much as `-ODebug`, and `DW_AT_comp_dir` leaks the absolute build path (the same leak the production audit found in release archives). In release every user function is inlined into `main`.

- Zig issue 1833 ("source maps") was closed as rejected on 2026-04-21: "Zig is primarily a human-to-programming-language interface rather than a programming-language-to-programming-language interface ... this would incur a non-trivial language complexity cost due to Zig lacking any kind of preprocessor." The `#line` route is definitively closed.

## Release, CI and security

- Security (no approval, no owner): all twelve 2026-09-14 SEC findings are still live. SEC-3 (`setup-bun@v2`) appears at three sites, two with write permissions; SEC-4 (unpinned `pip install uv`) at three sites, one more than the original finding records.

- Smallest set for a useful 500-line text tool, from the audit's evidence chain (a 193-line tool needed three rewrites): argument access (packet P9), `char` ordering and `char`<->int, string `==`, an index guard that discharges the bounds obligation, named capacities plus arrays of structs, float precision plus the cast-divisor fix.

## Promised but absent

- NEW from the design-gaps audit (2026-09-18, 21 findings, all NEW, none changing a program that builds): all 16 A7 code blocks in SPEC 9 fail to compile, and 10 never reach the type checker because SPEC 9 is not written in A7 syntax. Word-boundary grep over `a7/` for 21 terms (tensor, spawn, Channel, extern, @vectorize and the rest) returns zero hits for every one.

- DSG-1: SPEC 9.5/9.10 use destructuring as working code at five sites while SPEC 4.1:422 calls it planned; the compiler neither supports nor rejects it (`a, b := f()` exits 0 and deletes `main`, the PRD-33 family).

- DSG-21 and friends: SPEC 9 constrains tensors to `Numeric`, which by SPEC:951 cannot contain `f16`/`bf16` — the two dtypes ledger L11 locks. SPEC documents `^` as "Power" while it is defined and compiled as XOR (a snippet that compiles today with the wrong meaning). SPEC 9 also uses two generic spellings no other section defines, about 20 named-argument calls with no grammar production, and `axis: -1` against the `usize` rule.

- NEW outside SPEC 9: element-wise array `+` is 1-D and addition-only, and the rank-2 diagnostic prints "add between [2][2]f64 and [2][2]f64" — two identical types reported as incompatible (`type_checker.py:1223-1233`).

- Docs recommendation (docs-only, no approval, required by the Docs Accuracy rule): move SPEC 9's body to a design file, leave a short stub that keeps the word "Planned", and re-fence every block as `text`. Withdrawing the promise instead would contradict locked L1 and L7-L11 and needs approval. Concurrency needs `site/public/docs/status.md:44` corrected.

## Documentation

- NEW CRITICAL from the production-readiness audit (2026-09-18, docs/audits/2026-09-18/production-readiness.md): PRD-33, `x, y := 10, 20` exits 0 and emits a .zig whose whole content is `var y = 10;` — `main` and everything after the comma vanish. The sibling `a, b, c: i32 = 1, 2, 3` is correctly rejected (exit 5). Class A/B parser fix, no approval; belongs in the PR lane with PAR-02/PAR-03.

## Tooling notes

- Tooling note: the GLM fallback hit `MCP error -429: Weekly/Monthly Limit Exhausted` on the zai-coding-plan provider today, so delegated lookups are returning nothing. `tmp/glm/run_glm.sh` now treats that message as a provider limit and stops retrying instead of burning three attempts.

- Provider note: the GLM/zai search quota is exhausted until 2026-09-22. Use tmp/ai/run_grok.sh (grok CLI, headless, web search) until then; tmp/glm/run_glm.sh will return nothing.

## Other

- NEW (from r1a-c4 verify): a nested function declared inside an `if` (probe n06) is newly accepted by C4 and emits invalid Zig (ZIG-40, a pre-existing backend limit that exit 7 used to mask). Needs a backend row.

- NEW MTH-6: a type alias of a struct (`Ctr :: Counter`) is unresolvable ("Undefined type"), while `Handle :: u64` works. Type aliases had no audit coverage before; this is a frontend defect with no batch.

- NEW MTH-7: a generic receiver `ref $T` cannot read a field ("Cannot access field on non-struct type"), so generic code over structs is unwritable. The "methods x generics" interaction the checklist flags.

- CORRECTION: TYP-19's "changes accepted programs Zig builds: no" is wrong. `math.abs` on a runtime signed integer whose result is only used in arithmetic (`z := math.abs(x) - 10`) compiles in A7 and builds in Zig, with unsigned subtraction where A7's rules say the result is negative. The fix therefore needs owner approval.

- Residual after C2 (confirmed, not blocking): a local `io` inside an `else if` block, and inside a match-statement case following a match expression, still hijacks; the batch fixes resolution in the type checker rather than name resolution, so it inherits the PIP-4/PIP-5 scope desync. Every shape the verifier built is rejected by Zig or at exit 6; no building wrong-output binary was found. Closes with NR-02/X-SYM.

- Disclosure recorded in that report: one probe using `ref` parameters was built and run before the exclusion was rechecked; no further `ref` probe was run.

- NEW: Zig's two backends fail in opposite directions on the same emitted file. The default backend resolves no line numbers inside `__a7_user_main` although objdump decodes them (a gdb-Zig interop failure); with `-fllvm` lines work but the A7 local has no `DW_TAG_variable` at all. A7 identifiers survive the transpile unchanged; file, line and function name are lost. `break __a7_user_main` fails because the symbol is namespaced.

- Incompatible with compiling through Zig, per the same audit: in-place schema migration (M25 will hand raw addresses to C) and live code replacement (needs a patch point in every function; Zig's incremental compilation is still experimental).


## NOREC-0b disposition, 2026-09-20

The dictionary dispatch, continuation/delegation, scanner representation and
conservative-scan cases listed above now have regression tests. Three compiler
helper cycles were removed after those checks passed. This supersedes the open
NOREC-0b entry for those specific mechanisms, not the remaining compiler
conversions or unmodelled Python dispatch. See [batch evidence](../../audits/2026-09-20-v1-foundations/README.md).
The [49-ID inventory](../../audits/2026-09-20-v1-foundations/critical-high-inventory.md)
separates original critical/high evidence from broader repair claims.
