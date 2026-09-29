# Website review — Codex

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it.

The Field Manual design can stay. The main work is to correct the documentation, make search useful and qualify keyboard and mobile behavior. This review made no implementation changes; the working tree stayed clean.

Priorities: P1 means a documented workflow is blocked. P2 means an accuracy or usability defect.

| Priority | Finding and evidence | Reproduction and acceptance |
|---|---|---|
| P1 | Release instructions change into `site` before running the root test script. [release.md:20](/home/cx89/Projects/pl-dev/a7-py/site/public/docs/release.md:20). **Source-confirmed.** | Paste the complete block. After a successful site build, `./run_all_tests.sh` resolves inside `site`, where it does not exist. Use the authoritative subshell form and verify the complete block from the repository root. |
| P2 | A7 version branding says `v0.16` and `v0.16.0`, while the package version is `0.3.0`. [build.ts:385](/home/cx89/Projects/pl-dev/a7-py/site/scripts/build.ts:385), [pyproject.toml:3](/home/cx89/Projects/pl-dev/a7-py/pyproject.toml:3). **Source-confirmed.** | Separate the A7 package version from Zig 0.16.0. Derive package branding from package metadata. |
| P2 | Mobile CSS hides the only search and shortcut buttons at widths ≤640px. [tailwind.css:1088](/home/cx89/Projects/pl-dev/a7-py/site/src/tailwind.css:1088). **Source-only behavior finding.** | At 375px, verify a touch user can open search without a hardware keyboard. Keep a visible, named search control. |
| P2 | Search omits document body text and code. [build.ts:706](/home/cx89/Projects/pl-dev/a7-py/site/scripts/build.ts:706). **Generated-index verified.** | `usize`, `println`, `--format` and `recursion` produce zero matching entries, although they appear in the docs. Index section content and verify these queries lead to relevant sections. |
| P2 | Modal accessibility is incomplete. There is no focus trap or background `inert` handling. Escape uses a close path that does not restore focus. [site.js:153](/home/cx89/Projects/pl-dev/a7-py/site/src/site.js:153), [site.js:350](/home/cx89/Projects/pl-dev/a7-py/site/src/site.js:350). Search selection also lacks an input-to-active-option association. **Source-only.** | Browser acceptance must cover Tab/Shift+Tab containment, Escape focus restoration and screen-reader announcement of arrow-key selection. |
| P2 | The Markdown renderer collapses numbered lists into paragraphs. [build.ts:173](/home/cx89/Projects/pl-dev/a7-py/site/scripts/build.ts:173). **Generated-HTML verified.** | The Compiler pipeline renders as `<p>1. Tokenize source 2. Parse…</p>`, with zero ordered lists. Render the nine steps as `<ol><li>` elements. |
| P2 | Status contradicts supported imports and the authoritative roadmap. [status.md:31](/home/cx89/Projects/pl-dev/a7-py/site/public/docs/status.md:31) treats file-backed imports broadly as future work, although simple alias imports are supported. Its priorities also diverge from [docs/STATUS.md:16](/home/cx89/Projects/pl-dev/a7-py/docs/STATUS.md:16). **Source comparison.** | Distinguish supported imports from remaining forms. Reconcile priorities against the canonical status document before adding any implementation work. |
| P2 | Public release guidance omits the separate dependency and security audits and calls the script the “single local release gate.” [release.md:24](/home/cx89/Projects/pl-dev/a7-py/site/public/docs/release.md:24), [docs/RELEASE.md:63](/home/cx89/Projects/pl-dev/a7-py/docs/RELEASE.md:63). **Source comparison.** | Include the required commands, or state that the summary is incomplete and link directly to the full checklist. |
| P2 | Compiler documentation overstates iterative internals. [compiler.md:58](/home/cx89/Projects/pl-dev/a7-py/site/public/docs/compiler.md:58) conflicts with the remaining recursive emission paths described in [README.md:140](/home/cx89/Projects/pl-dev/a7-py/README.md:140). **Source comparison.** | Keep the distinction between banned A7 source recursion and remaining Python implementation recursion. |
| P2 | The homepage terminal shows invented stage-by-stage output and a static green release gate, with no label saying it is illustrative. [build.ts:576](/home/cx89/Projects/pl-dev/a7-py/site/scripts/build.ts:576). **CLI comparison verified.** | Actual compilation prints `Compiled … -> …`. Use representative real output and label example transcripts. Do not present static success text as current verification. |

## Additional onboarding improvements

- [Start](/home/cx89/Projects/pl-dev/a7-py/site/public/docs/start.md:11) names dependencies but gives no installation links, Zig setup guidance or expected first-run output.
- The Compiler reference omits useful supported options, including `--output`, `--doc-out` and `--verbose`.
- Raw Markdown contains 20 links to HTML routes. Canonical documents such as `docs/SPEC.md` appear as unlinked filenames. Add directly fetchable sibling or source links.
- Terminal tabs declare ARIA tab roles without panel associations or arrow-key behavior. This needs browser qualification together with the modal fixes.

## What passed

- `bun run check` passed in an isolated temporary copy using existing dependencies. Nine pages built.
- All 259 generated local links and fragments resolved.
- An independent sub-agent verified exact `llms-full.txt` parity with all nine public Markdown documents.
- CLI help agrees with the documented mode names.
- Hello-world compilation, the language-tour pipeline and all three standalone Language/Stdlib snippets passed.
- Core guidance on `usize`, source recursion, heap fixed arrays and public reference syntax agrees with repository authority.

## Proposed roadmap for agreement

1. **Correct published facts and commands.** Accept when release blocks preserve cwd, version labels distinguish A7 from Zig, status matches canonical docs and transcripts represent actual output.
2. **Complete onboarding and reference links.** Accept after a clean-environment walkthrough reaches the expected hello-world output, all CLI options are covered and agents can follow raw or source links directly.
3. **Repair search and semantic interaction.** Accept when the listed queries work, numbered lists stay semantic, mobile search is reachable and keyboard and screen-reader checks pass.
4. **Qualify and prevent regressions.** Add targeted checks for links, corpus freshness, version facts, command examples and search. The coordinator verifies that desktop and mobile captures preserve Field Manual typography, palette, layout and compiler map.

## Coverage limits

Not performed: browser sessions, Playwright, visual captures, live-site checks, clean dependency installation, native Zig execution and the full release gate. The supplied uv path was missing; the nested binary worked with `--no-sync`. Zig was absent from `PATH`. These are environment limits, not compiler failures. The build emitted a Node deprecation warning but succeeded.
