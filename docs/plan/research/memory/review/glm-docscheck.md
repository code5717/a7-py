> **Source:** OpenCode `zai-coding-plan/glm-5.3` audit of the 2026-09-16 documentation cleanup. Prompt in [review-prompt.md](../review-prompt.md).  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

The 2026-09-16 cleanup modified tracked files (`docs/lang-safety/*`, `docs/SPEC.md`, `README.md`) and created untracked `docs/plan/` and `docs/audits/`. I can diff the tracked ones against `701c679` to detect lost/altered decision records.
All D-entries D.001–D.053 (incl. D.041b) survived the reformat. Now checking the disposition table at the top of the new 08-decisions.md against the ledger.
The disposition table matches the ledger exactly. Now I'll check whether the reformat altered decision content, and verify the plan README's line citations into the new file.
The plan README's `08-decisions.md:700-705` citation refers to the documented old (701c679) numbering — consistent with the ledger's convention. Now checking what content actually changed in the diff beyond annotations.
Diff shows annotations plus clarity rewording; decision substance appears preserved. Now scanning all rewritten docs for `Current A7` labeled code blocks and rule violations (`.adr`, `.val`, `&`, recursion).
Research notes quoting old `.adr`/`.val` material are historical and acceptable. Now checking for recursion examples and non-`usize` indices in the rewritten docs.
The stack-budget examples are honestly labeled ("compile results were not checked"). Now I'll verify the behavioral claims compile-only. First, checking whether the CLI writes artifacts next to source files (I must stay read-only on the repo).
CLI only writes with `--output`/`--doc-out`, so plain compile runs are read-only. Running compile-only probes in the sanctioned scratch dir to verify the docs' behavioral claims.
File writes are blocked (plan mode). I'll verify claims through an in-memory compile API instead, if one exists — no files created.
COMPILE mode writes `<input>.zig` next to the source, so I'll drive the compiler API from Python with the input in an ephemeral `/tmp` file and output redirected to `/dev/null` — no repository files touched. This is compile-only (no Zig build, nothing executed).
Probes work but the compiler prints full JSON. Re-running with output captured, covering the remaining claims (G1, G9, G4, G5, G6, G2, memory.md before-blocks).
All README claims verified so far (one nuance: the `café` diagnostic actually reports `'Ã'`, not `'é'`). Now the memory.md before/after and contract-example claims.
Retesting the `ref`-return claim without a caller (my earlier probe failed at the construction site, not the declaration), plus self-referential `ref` fields.
All `Before`-block claims verified. Now auditing the rewritten `docs/audits/2026-09-14` files and cross-references.
Roadmap has the promised inline "cited as" marker and dated notes. Checking HANDOFF.md decision records (Q1–Q3) survived, and the lang-safety README.
HANDOFF structure intact. Now verifying cross-references, the later-modified files (12:45–12:47 wave), and example claims.
`memory-brainstorm.md:72-73` says self-referential struct fields are rejected, but `memory.md:268` says they compile (my probe: they do compile). Checking notes-h, the cited source.
Confirmed: declaration compiles, assignment fails — memory.md is precise; brainstorm's phrasing is looser but consistent with its source. Now the second cleanup wave (12:45–12:47): `06-compile-time-safety.md`, `parameter-modes.md`, `comparative/README.md`, `edge-cases/`.
All verified. Now `parameter-modes.md` and `comparative/README.md` (second wave).
SPEC change is only a ToC anchor fix. Verifying the SPEC defects listed in plan README:364-379 still exist as stated.
This report covers the earlier 2026-09-14 additive cleanup; my target is the 2026-09-16 rewrite (the 9k+ deleted lines in the tracked diff). Checking for content loss file by file, starting with the one that shrank.
Headers preserved; rewrites added new "What the compiler does today" / "Re-check" sections — these are new behavioral claims to verify. Reading them.
All cast-class claims verified. Now a cross-reference link check across the rewritten trees plus a filler scan.
Those "broken" hits are absolute-path citations with `:line` suffixes (files exist) and code-fragment URLs in review snapshots — not real broken links; all 691 relative links resolve. Checking the new `docs/README.md` and audit review headers.
One last sweep: `Current A7` blocks in comparative files, and any `&`/`*` operator usage in a7 code blocks in the rewritten trees.
# Audit report: 2026-09-16 documentation cleanup

## Method

Read the ledger, plan, memory plan, edge-case audit, plan README, the rewritten `docs/lang-safety/` (diffed against `701c679`), `docs/plan/`, `docs/audits/2026-09-14/`, `docs/README.md`, and SPEC/STATUS/SAFETY_CONTRACT. Verified behavioral claims with **compile-only probes** (in-memory `A7Compiler` API, sources in ephemeral `/tmp` files, output to `/dev/null`; no Zig build, nothing executed, no repo files touched). ~40 probe programs run.

## Verified facts (compile-only, this session)

All of these doc claims reproduce exactly:

- **plan README gates**: G1 float-division divisor proof (exit 6, exact message, docs/plan/README.md:69-77); G2 `set_to_100` → `value.?.* = 100` + `&n` (:119-128), double-`del` accepted (:132-141), `swap` reassign rejected "Cannot assign to immutable binding: 'a' is immutable" (:370-373); all 8 G3 rows incl. exact messages for `cast(u8, n)` and `250 + 10` (:147-156); G4 stored function value compiles (:177-198); G5 match compiles with `const ok = __a7_match_1` (:220-238); G6 café/string/unclosed-comment (:249-263); G9 `x += 1` (:314-324).
- **memory.md Before/contract blocks** (docs/plan/memory.md:139-214, 284-417): every "Current A7 … accepted/rejected" claim verified, including `ref` returns and self-referential `ref` fields compiling while assignment fails "expected 'ref unknown type', got 'Node'" (:268 — exactly as written), `fn_ptr: ref fn() = nil` accepted, SPEC's `ref fn() void = nil` rejected "Undefined type (Type 'void')" (plan README:356-358), and the exact `new [4]u8` message.
- **lang-safety**: edge-cases/01-cast all 7 class blocks with exact messages (:81-200); edge-cases/02 N-03/N-08/09/11/14/N-15 exact (:89-160); 06-compile-time-safety 4 blocks (:78-477); 07-language-review re-check citations (`_prove_ref_non_nil` at a7/safety.py:610, `classify_cast` forbidden branch at a7/cast_classifier.py:40-41, nil-deref message) (:60-77, 96-110); comparative/mojo:104 and swift:136-149 blocks; narrowing.md current-A7 division guard.
- **Decision records**: D.001–D.053 + D.041b all preserved with original statuses; the new disposition table (08-decisions.md:15-25) matches the ledger's sets (decisions.md:104-113) exactly. HANDOFF sections 1–16 and Q1–Q4 intact with dated notes. Ledger citations into old files (D.001 line 76, D.024 line 760, D.038 line 1290, SAFETY_CONTRACT.md:54, STATUS.md:20-21/41-44) all check out against `701c679`; STATUS.md and SAFETY_CONTRACT.md are indeed unchanged.
- **Cross-references**: 691 relative links in the three trees all resolve. The 26 flagged targets are absolute-path citations with `:line` suffixes and code fragments inside review snapshots — documented as historical in docs-cleanup-report.md:117-122.
- **No filler**: no marketing/slop phrases found; evidence-status labeling is consistent ("compile-only", "not checked in this session", "compiler was not run").

## Findings

**Blockers: none. Majors: none.**

Minor:

1. **docs/plan/README.md:252** — quotes the `café := 1` diagnostic as `Unexpected character: 'é'`. Actual message (verified): `Unexpected character: 'Ã'` — the tokenizer reports the first UTF-8 byte (0xC3), not the full character. Exit code 4 and substance correct.
2. **docs/plan/memory-brainstorm.md:72-73** — "self-referential struct fields are rejected" is imprecise: the field declaration compiles (verified, exit 0); only assignment/use is rejected. memory.md:268 states it correctly; the brainstorm's compression reads as declaration-level rejection.
3. **docs/lang-safety/comparative/README.md:29** — in a "Current state" column: "Emitted code still never relies on a Zig safety check that ReleaseFast removes." As a present-tense claim it conflicts with plan README G3 (verified: `x += 1` overflow relies on Zig's check) and lang-safety README.md:166-169 ("The test above would not pass today"). It is true only as a memory-plan design rule; reword to future/design intent.
4. **docs/plan/README.md:375** — cites `08-decisions.md:700-765`-era line numbers (the CA summary is now at 766-772 after the reformat). The old-numbering convention is documented in decisions.md:90-93, but this citation doesn't carry the caveat locally; citing by D-entry ID would be sturdier.
5. **docs/lang-safety/08-decisions.md:59-60** — says cleanup-added examples "use explicit-width types"; true of the ones I checked, but the file still contains historical `int`/`number` examples in D-entry bodies. The header note at :36-37 covers this; no action strictly needed.

No A7-rule violations found in any rewritten doc: every `Current A7` block I probed compiles in today's syntax; proposed blocks are labeled; no recursion, no non-`usize` indices, no `&`/`*`/`.adr`/`.val` as reference operations (`.adr`/`.val` appear only in historical research notes quoting superseded PDFs, explicitly marked obsolete, e.g. notes-h:176-191).

## Decisions for the user

1. **Fix the two misstatements** (findings 1–3: G6 quoted character, brainstorm phrasing, comparative README tense). Recommendation: yes — pure documentation-accuracy fixes within track 0, no syntax/behavior change, so no approval-rule trigger.
2. **Citation style for reformatted files** (finding 4): keep `701c679` line numbers with the ledger's caveat, or switch to D-entry IDs. Recommendation: switch to IDs; line numbers into a reformatted file will drift again.
3. **Rerun the interrupted GLM memory-safety review** (edge-case-audit.md:21-23, L12 obligation). Recommendation: schedule it before memory-plan revision 3; already tracked, this is a reminder, not a new decision.
