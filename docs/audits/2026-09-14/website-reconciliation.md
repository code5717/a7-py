# Website report reconciliation

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it.

This is an independent, static, coordinator-side review of the completed Flash reports on accessibility, organization, interactions, typography, responsive design, design system, SEO and content. It read current source and inspected existing generated files. It made no browser checks, builds, implementation edits or external CLI calls. Cybersecurity findings are outside this pass and stay assigned to GLM. The Unslop skill guided the prose.

The performance Flash report arrived after the initial pass; it is adjudicated in its own section below. Source line references describe the reviewed working tree and can shift as other work lands.

## Accepted findings

| Finding | Reconciled evidence and scope |
| --- | --- |
| Escape does not restore modal focus | `site/src/site.js:145-150` restores focus only through `closeModal`. Escape instead calls `closeAllModals` at line 350. That function removes attributes and resets scrolling at lines 153-159 without focusing the trigger. Reject accessibility F2's blanket assertion that closing already restores focus. Close button and backdrop paths do restore it. Escape with a nonempty search input first clears the query at lines 345-348. |
| Modal reopening can overwrite the return target | `site.js:127` unconditionally stores the active element. Cmd/Ctrl+K at lines 338-340 calls `openModal` even while the search input already has focus. A subsequent close button then attempts to restore focus into the hidden modal. Initial opening is implemented, but all close/reopen paths need browser verification. |
| Modal containment and search semantics are incomplete | No containment exists in `site.js:123-176`. Search creates focusable anchors with option roles at lines 228-245, while `site/scripts/build.ts:300-303` omits the corresponding combobox state and announcements. A source check establishes the incomplete implementation. Screen-reader behavior and conformance remain untested. |
| Numbered instructions lose list semantics | `build.ts:173` recognizes only bullet items. Lines 191 and 100 merge numbered steps into a paragraph. `site/public/docs/compiler.md:16-24` is an existing nine-step numbered pipeline. Current `site/dist/compiler/index.html` contains one paragraph beginning `1. Tokenize source 2. Parse into AST`, and no ordered list for those steps. Accessibility's general statement that list semantics are good excludes a real failure. |
| Four homepage search fragments have no targets | `build.ts:706-725` indexes the overview Markdown headings, but `homeHtml` at line 451 uses a separate template. Independently enumerating current `dist/assets/search.json` against IDs in `dist/index.html` found `/a7-py/#pipeline`, `#read-order`, `#repository-docs` and `#public-contract` without targets. This is generated-artifact evidence, not a clicked browser reproduction. |
| Search has no body-text index and hides loading failures | `site.js:204` searches only title, section and summary. `build.ts:706-725` stores no body text. `site.js:187-195` caches a failed load as an empty array; lines 223-225 display the empty-results state. Terms occurring only in document bodies cannot match. Whether full-text search is a v1 requirement needs an explicit decision. Failure must not imply that documentation contains no results. |
| Same-page search navigation has no modal cleanup | Result anchors have only a mousemove listener at `site.js:241-244`; Enter calls `location.assign` at line 289. Neither path closes the dialog. The source lacks cleanup for fragment navigation that retains the document. Reproduce the visible behavior in a browser before acceptance. |
| Mobile CSS removes the only visible search entry point | `build.ts:391-392` assigns both header buttons `shortcut-trigger`; `tailwind.css:1083-1088` hides that class at widths up to 640px. Keyboard shortcuts remain, but no replacement touch control exists. This is a current functional omission shared across the interaction and responsive reports. |
| Tabs and copy status need accessibility work | `build.ts:569-594` supplies tab roles without associated tabpanel roles; `site.js:413-427` handles clicks only. The release and agents panels have static `hidden` attributes, so those panel contents are unavailable without JS. `site.js:42-58` changes copy text while keeping the static accessible name. Treat no-JS support as a product requirement to agree, not an automatic WCAG failure. |
| Search focus styling and paragraph spacing are missing | `tailwind.css:943-944` applies `outline-none` to a more specific selector than the global ring at lines 84-86. Paragraph styling at lines 774-775 adds no margins after Tailwind's reset. These source defects support focused visual remediation, but the amount of spacing and final focus appearance need rendered review. |
| Navigation order and overview presentation diverge | `build.ts:24-41` orders Agent Usage before Project but groups Project before Agents. Pager order at lines 403-408 is flat; route-board order at lines 269-283 is grouped. `pageHtml:365` sends index to `homeHtml`, which omits the Markdown body. Organization F2 should say the authority statement is absent from the homepage, not from all human-readable pages; the report itself identifies it on Status and Agent Usage. |
| Website stamps use the wrong unqualified version | `build.ts:385`, `:460` and `:641` display v0.16 or v0.16.0. `pyproject.toml:3` is 0.3.0. Zig's toolchain version does not establish the A7 version. Content and design reports correctly detect this; SEO F10's claim that versions are in sync only compares the site's package.json and misses compiler authority. |
| Homepage transcripts and support claims overstate reality | `build.ts:577-582` shows invented compile-stage output, while `a7/compile.py:545-553` prints a single `Compiled ...` line. `build.ts:500` says `MULTI-FILE INPUT`; `README.md:164` limits implemented imports and `docs/STATUS.md:19` still lists practical multi-file support as work. Label illustrative output and qualify import support. |
| Public compiler prose contradicts README's recursion bounds | `site/public/docs/compiler.md:58` says compiler internals avoid recursive AST traversal. `README.md:140` explicitly names recursive parser and emission paths. Accept this as a documentation contradiction; any safety implication belongs to the dedicated GLM review. |
| Preview does not report missing routes as 404 | `site/scripts/serve.ts:28-29` substitutes the 404 file but creates a default-status response. This is a local QA defect. Do not generalize it into a production soft-404 finding; the SEO reviewer reported live production 404s. |
| Site lint omits a required document | `site/scripts/lint.ts:6` omits `project.md` from REQUIRED, despite its navigation entry at `build.ts:33`. The guard does not enforce the full current corpus. |

## Rejected or downgraded claims

- SEO F1 correctly counts two H1 elements in raw HTML, but its claimed doubled visible/accessibility outline ignores `tailwind.css:745`, which hides the prose H1. Removing duplicate markup is reasonable cleanup. There is no evidence here for a P1 SEO defect or ranking penalty.
- Content F9 claims that omitting `--max-warnings=0` makes local lint more lenient. The complete `site/scripts/lint.ts` never reads command-line arguments and has no warning threshold. The workflow passes an ineffective flag at `.github/workflows/deploy-docs.yml:46`. Correct the documentation or tool contract, but do not claim different enforcement today.
- Content F2 confirms stale local build output, but overstates it as an established corpus-equality failure inside the build.
  - Independent byte checks confirm that `dist/docs/index.md` and `dist/llms-full.txt` differ from current public sources. That does not prove the two old dist files disagree with each other. Organization O1 treated it as pending rebuild work, which was more accurate.
  - The coordinator has since rebuilt the site and reports `bun run check` passing and 259 generated internal links passing. Stale dist is resolved locally. These follow-up results come from the coordinator, not an independent rerun in this pass.
  - The deployment workflow builds before uploading (lines 48-55), so this was never an established production defect.
- Accessibility F10 infers that every scroll region is keyboard-unreachable solely from absent tabindex. Native scroll focusability varies by browser, and some containers contain focusable descendants. Keep wide code/table access on the browser checklist; reject the universal failure statement without keyboard reproduction.
- SEO F4 proposes `.nojekyll` for a hypothetical switch to branch publishing. Current workflow publishes a built artifact at `.github/workflows/deploy-docs.yml:52-66`. This is optional future-proofing, not a present release blocker.
- SEO F3's suggested title calls the source Python-like. That description needs language-owner agreement and should not replace accurate A7/Zig wording merely for search keywords.
- Design-system wording that the version is overstated by five minor versions is numerically wrong. The supported finding is a mismatch between A7 0.3.0 and Zig 0.16.0, with no inferred release history.
- The route-board text says nine pages and the board links eight because the homepage is excluded by `build.ts:272`. This is a small copy ambiguity, not a missing ninth document.

## Provisional visual and product decisions

Responsive F1's precise overflow interval, touch target sizes, mobile anchor occlusion, reading measure, clipping, font shift, and typography sizing preferences require rendered measurements. CSS analysis identifies plausible failures but cannot certify their exact viewport ranges or impact. The reports correctly disclose blocked browser access, which their priority labels must not obscure.

Contrast token findings are useful inputs. This pass verified the token declarations and selectors, not every computed ratio or composited background. Recompute against actual rendered adjacent colors. The accessibility report's F8 correction direction is backwards in prose: improving dark-background text usually requires lighter text, and improving paper-background text usually requires darker text. Its examples and numeric acceptance criteria should be checked independently before use.

Preserve the Field Manual design while checking the actual tasks: install and run the first example, find a language rule, recover from failed search loading, follow a search fragment, return focus after every modal close path, read the compiler pipeline as ordered steps, navigate at phone width, copy code with keyboard and touch, and identify current limitations and the actual A7 version. Each acceptance check must describe observed behavior. Static source inspection cannot close accessibility, performance or product acceptance.

## Performance follow-up adjudication

The completed `website-flash-performance.md` adds local file-size measurements and static performance hypotheses. It discloses unavailable browser execution and unmeasured production caching. Those limitations control the conclusions.

- Accept F1's source finding that `build.ts:377-379` loads an external font stylesheet in the document head. This establishes a render-blocking CSS dependency and subsequent font discovery. Reject the ranking of this as the single largest user-visible risk or largest improvement. No waterfall, font payload, paint timing or competing-cost measurement supports that ranking. Visible layout shift is also unmeasured.
- Accept F2's presence of a sticky topbar with blur and saturation at `tailwind.css:121-126`. Scroll jank, reduced smoothness, measurable battery cost and its designation as the main mobile cost are hypotheses. The report has no device traces or battery measurements. Whether removing the effect improves the actual experience needs comparison on agreed devices.
- Accept F3's persistent `will-change` declaration at `tailwind.css:1012-1018`. Reject the claim that each element necessarily retains a compositor layer. Browser allocation is not guaranteed by this hint; layer count and memory/raster cost were not inspected. No-JS visibility for reveal targets follows the current attribute-installation path, but does not excuse the separately hidden terminal panels.
- Accept F4's verbatim JS-copy observation. Its predicted 2-3 KB gzip saving and negligible parse time were not measured. Minification and filename hashing are possible implementation choices, not current performance blockers established by this review.
- F5 establishes a small index and linear ranking, not an instant first keystroke or verified response-time acceptance. No debounce is justified solely by anticipated growth. Keep the existing search correctness findings separate from performance.
- F6's stale local dist observation is now resolved by the coordinator's rebuild. It was a snapshot issue, not evidence that the build stopped being deterministic or that production served the wrong corpus. The deployment workflow builds before upload. Historical byte measurements should retain their snapshot label.
- F7's description of hidden phone search controls as reasonable conflicts with the accepted mobile-search omission. A performance review cannot approve that loss of access. The same report's cheap-scroll-listener and compositor-friendly statements remain source-based expectations, not measured runtime outcomes.

The proposed grep checks for absent font-host links, blur declarations or `will-change` enforce implementation choices. They cannot establish acceptable loading or scrolling. Even the blur check must account for inherited desktop declarations and the CSS cascade, not only search a mobile block.

Under the AGENTS.md test-quality rule, acceptance needs user-observable requirements and measured results:

- compare cold and warm page loading under documented network and device conditions;
- record text visibility and layout shift during font loading;
- inspect long-page scrolling with the header visible;
- measure search response after opening and typing.

Agree thresholds and representative environments in the roadmap before calling performance complete. Browser traces and actual response headers must distinguish local preview from deployed hosting.

## Verification record

This pass read AGENTS.md, the eight initial Flash reports and the later performance report, the relevant build/client/CSS/preview/lint source and deployment workflow. It used Python standard-library file reads to compare the current search index with homepage IDs, inspect the rendered compiler pipeline paragraph, and compare two source/build corpus files. No implementation or public documentation changed. The only new file is this report. No review was promoted into v1 acceptance.
