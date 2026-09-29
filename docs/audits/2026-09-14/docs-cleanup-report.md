# Documentation cleanup report

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it.

| Field | Value |
| --- | --- |
| Reviewer | Codex documentation cleanup worker |
| Acceptance owner | Controlling Codex session |
| Baseline commit | `701c67936c70ad2b0608326e23e56cc5d38c9fdb` |

## Scope and authority

This was a documentation-only navigation cleanup. No files were moved, merged
or deleted. No compiler, test, script, package configuration, CI, CSS or
JavaScript code changed. No commit, deployment, full gate or site build ran.
Other reports under `docs/audits/2026-09-14/` were excluded from edits and
baseline comparisons.

The worker read `AGENTS.md`, the technical-writing skill and the unslop skill. The
project README and `docs/RELEASE.md` remain the authoritative user-facing docs.
`docs/STATUS.md` identifies current gaps. `docs/SPEC.md` includes both implemented
and planned language design. Public Markdown pages summarize repository docs.
Safety research and saved reviews retain their own historical qualifications.

## Inventory and history

Before edits, the inventory contained 69 files in the requested scope, excluding
concurrent audit reports. The inventory comprised the root README, 57 files under
`docs/`, nine public Markdown pages, and two agent corpus files. The 57 docs files
included seven top-level Markdown documents, seven pointer-syntax PDFs, 40 safety
research Markdown files, and three archive files including two historical tools.
The final table records every baseline path, byte size, and SHA-256 hash.

Reviewed history with `git log` for README, docs, public pages, and agent corpus
files, and inspected `git show --stat 5f0df01`:

- `5f0df01` reorganized site navigation by task and kept stable agent URLs.
- `f793ff4` moved the project to Zig 0.16 and simplified docs.
- `5a89dcb` clarified historical documentation status.
- `b08edd8` is the latest path-specific commit for the base pointer-syntax PDF.

The existing task-based site organization already covers start, language, stdlib,
compiler, status, release, agent usage, and project maintenance. The missing
repository-wide index was a better cleanup target than moving those pages.
The site generator in `site/scripts/build.ts` defines both agent corpus formats
and writes them back to `site/public/` during a build.

## Changes

| File | Change and preservation rationale |
| --- | --- |
| `docs/README.md` | New index groups current guidance, public docs, safety design, and historical artifacts. Links all seven existing PDF paths without treating their contents as equivalent. |
| `README.md` | Adds a link to the repository index under the existing Learn More heading. Existing usage, examples, and qualifications remain. |
| `docs/SPEC.md` | Repairs 13 contents fragments to include heading numbers. Link labels and target headings remain unchanged. |
| `docs/lang-safety/README.md` | Adds a research-status notice and links to current guidance. Preserves the original contract, decision summaries, examples, citations, and reading tables. |
| `site/public/docs/index.md` | Adds a canonical repository-index link and clarifies that design acceptance does not establish implementation coverage. Frontmatter and public routes remain unchanged. |
| `site/public/llms-full.txt` | Mirrors the public index addition using the existing generated corpus format. |
| `docs/audits/2026-09-14/docs-cleanup-report.md` | Adds this report. |

Exact moved files: none. Exact merged files: none. Deleted files: none.
`site/public/llms.txt` is unchanged because page titles, summaries, and routes did
not change. No changelog or release update was needed for this navigation-only
change. The Field Manual layout, styles, navigation metadata, and implementation
were left unchanged.

## Preservation comparison

Before edits, a temporary snapshot recorded bytes, SHA-256 hashes, and Markdown
or text contents for all 69 files. Comparison after edits found:

- 64 baseline files are byte-identical, including all seven PDFs, all archived
  tools, all research files except the research index, and `docs/RELEASE.md`.
- Five baseline files changed. Four retain every original line in order, with
  additions only. A line comparison with `difflib.ndiff` found no removed lines.
- The specification changes only 13 contents URL fragments. Removing the added
  numeric prefixes from those fragments reproduces the entire original file
  exactly. No specification prose, headings, examples, or qualifications changed.
- No baseline file is missing. New files are the repository index and this report.

These comparisons support preservation of the existing bytes and text within
this cleanup. They do not validate the truth of every technical claim, establish
that PDF variants are equivalent, or reconcile old research with current code.

## Checks

- `python scripts/check_docs_style.py`: passed, `docs-style: ok`.
- `git diff --check`: passed before report creation, repeated for final review.
- Temporary read-only validation script at `/tmp/a7-docs-cleanup-check.py` checked
  inline Markdown file targets, mapped public routes to their local source pages,
  and mapped repository GitHub links to this checkout. Of 332 checked link
  occurrences, 294 resolved and 38 historical absolute-path citations did not.
  The broad scan exited 1 because of those retained citations. A separate
  baseline comparison confirmed all 38 predate this cleanup and none occur in
  changed or new documentation. The scan skipped 240 external link occurrences.
- All 13 corrected specification contents fragments match numbered headings.
- Reproduced the read-only string construction in `llmsTxt` and `llmsFull` from
  the nine public pages. Both checked-in corpus files match exactly. No generator
  edit or build was needed.
- Inspected the tracked diff and checked the baseline preservation results.
- A built-in sub-agent performed a read-only navigation and authority review.
  It independently recommended an additive repository index and research-status
  qualification. It ran no build and launched no external agent CLI.

Temporary evidence files are `/tmp/a7-docs-cleanup-baseline.json`,
`/tmp/a7-docs-cleanup-check.py`, and
`/tmp/a7-docs-cleanup-check-results.json`. The baseline manifest below remains
in the repository if temporary files are removed.

## Unresolved issues and coverage limits

The research index says clusters CB through CG are pending, while the handoff
snapshot dated 2026-05-11 says CB is accepted with an unresolved D.024/D.038
conflict. Both original statements remain. The added notice directs readers to
current Status and the safety contract. Reconciling accepted design history
requires the coordinator's source review, not a navigation edit.

The saved `docs/lang-safety/codex-review.md` has 38 absolute-path citation
occurrences covering 19 unique targets under `/home/air/Projects/pl/a7-py/`.
They refer to the earlier machine and include historical line numbers. They were
preserved as review evidence. A future portable citation layer should retain
those original references and verify their historical targets before adding
replacement links.

No external URLs were fetched, and no PDF content or rendering was reviewed.
The PDFs were inventoried and hash-compared. Research was reviewed for structure,
authority, and history, not reread as a full technical audit. Link scanning covers
inline Markdown file targets and public route source mapping, not all Markdown
syntax, HTML links, or every research heading fragment. The 13 corrected contents
fragments were checked separately. A local target does not prove an external URL
is deployed or available.

The standard docs-style script excludes nested research and audit directories.
Its rules were also applied directly to the new report and changed research
index for this cleanup. Style checks are narrow phrase checks, not proof of prose
quality. Final site rendering, full gate results, concurrent audit findings, and
acceptance remain with the controlling session. No implemented-feature claims
were strengthened by this cleanup.

## Baseline file manifest

Hashes and sizes describe the pre-edit snapshot. The five files marked changed
have the preservation comparisons described above. Audit reports are excluded.

| Path | Bytes | Baseline SHA-256 | Comparison |
| --- | ---: | --- | --- |
| `README.md` | 10216 | `3187450707fb37bc465b0b170b78276de3fa93f0416a073a4321690fcf6705cd` | Changed as described |
| `docs/CHANGELOG.md` | 1024 | `893a7b6e5ede419e4502acda24cd9d54c16e102a4ae9466ce0d70db5c743b1d9` | Byte-identical |
| `docs/ERROR_ANALYSIS.md` | 11069 | `9681981d4b9a7ce979a44e023e659385efc6d36efd40d89c1e1a6e1c68d765b5` | Byte-identical |
| `docs/POINTER_SYNTAX_ANALYSIS.pdf` | 80524 | `a7cbf311b900aa8f4ab4e6fbd7d31402e69a6ec583ff428d544a7d0031065a50` | Byte-identical |
| `docs/POINTER_SYNTAX_ANALYSIS_beamer.pdf` | 280829 | `429f6bccade66542ab51738e4d89a736baa6294aad7917556812e175b93e7679` | Byte-identical |
| `docs/POINTER_SYNTAX_ANALYSIS_compact.pdf` | 202275 | `9864eae5796ed7d0d94377a62e17c5a90a1a4e965f423b8a2a942ce88d45e018` | Byte-identical |
| `docs/POINTER_SYNTAX_ANALYSIS_dark.pdf` | 202539 | `f3a64e60bafa412a0032c5de467741dc3a90b99b665c63542d0ee7c8a65efe9e` | Byte-identical |
| `docs/POINTER_SYNTAX_ANALYSIS_html_styled.pdf` | 73383 | `f3830699ffce769e7f806c5ff523a58fff2ac65d82fc064c6be618b8808cc725` | Byte-identical |
| `docs/POINTER_SYNTAX_ANALYSIS_latex.pdf` | 251444 | `1574acc6ec80679b881a1fb2251055bc7473c3de926eea02a9f833e0742f9865` | Byte-identical |
| `docs/POINTER_SYNTAX_ANALYSIS_wkhtmltopdf_direct.pdf` | 78361 | `2e0169382e0fa608f35278ef9bc854887f4045c553ca8a06a6b6d50cd395cb05` | Byte-identical |
| `docs/RELEASE.md` | 5180 | `0ff333e915807ad9ccb520871faeb5459a8ef9299ea6eef2e84f8ad4db50d853` | Byte-identical |
| `docs/SAFETY_CONTRACT.md` | 4241 | `ab23486edc6c311d9b4747715f613aa865f5c09d1397144593e72ca72ffdb68e` | Byte-identical |
| `docs/SECURITY.md` | 2467 | `e89cf79c7b24f147c9a32cb049121aa3d8977bcae2ecb16a90f03fb2c041b9dc` | Byte-identical |
| `docs/SPEC.md` | 59494 | `280ae211ed9d3ed5fee3014e32d8e758538f967e6fc7af9988b3e8a67fb0b3e7` | Changed as described |
| `docs/STATUS.md` | 1979 | `8c486ec96646e664a6a901a30925c388a7d65d1bce4dff58ede1292dafaa7e95` | Byte-identical |
| `docs/archive/README.md` | 554 | `196e12df0c2f9acc236cc0403ae34530493e467026d36d76c22b3756709cadb5` | Byte-identical |
| `docs/archive/tools/fix_types.py` | 1457 | `b7b87c5920965d6d4a0777dfa40a6f9664ba36e64c98f00fed020ce5cf39fa6c` | Byte-identical |
| `docs/archive/tools/run.sh` | 171 | `8cb9d9f953af1f08a92ef8fb8c74916bc41f97ab717d6bf0320cb99799b90c95` | Byte-identical |
| `docs/lang-safety/01-invisicaps.md` | 47784 | `be4531e59c64aa2dee2803fee7f4f867686f6fcdf2721386a200f10b6ebc855e` | Byte-identical |
| `docs/lang-safety/02-sanitizers.md` | 24363 | `8244b09845f0cd3cdaff4fe03a5f398be8fb93fea9966163069d93a59c00b325` | Byte-identical |
| `docs/lang-safety/03-hardware.md` | 12463 | `1ba438bc56d9295bfbb5f8889d803902bfedd3de728d9671013b65aebdd1c1a5` | Byte-identical |
| `docs/lang-safety/04-comparison.md` | 7212 | `2451f9a6af1dae3eb347d5f0836b6cf6bcac5d9495dac68b09b59bcd78e50300` | Byte-identical |
| `docs/lang-safety/05-for-a7.md` | 35225 | `32287460af18379b1d79f8841ea7a6bb7ec8b46c7bfebeb2fad81ba7c85e3c8e` | Byte-identical |
| `docs/lang-safety/06-compile-time-safety.md` | 21014 | `a92a76be5f6fcf1f4356e961fdafbfa37a95f6061a2225593b1a8a0847328e79` | Byte-identical |
| `docs/lang-safety/07-language-review.md` | 26799 | `6f993332c4cbd9a1d6725e7f8fc8963c20d62f59d01d2b8f5b105d6ba2bb8d05` | Byte-identical |
| `docs/lang-safety/08-decisions.md` | 77388 | `d0da3ecbb51ea324c60976a72c7feff40a58ffac70312b2a6416b62f273b6602` | Byte-identical |
| `docs/lang-safety/HANDOFF.md` | 28530 | `c0d9bdad644dbd913c995d1e8f51a9af0376a87c3291bbfc02b1ba0d08790d63` | Byte-identical |
| `docs/lang-safety/README.md` | 11968 | `d5680ae0f779fac3752f73d4dc092fbc52d099b347c667edcfda08df6eab3e31` | Changed as described |
| `docs/lang-safety/codex-review.md` | 24786 | `e9c08a972d013ec4b486ab56ca7d223c218b1b5c8c2145dd87559d7b092fb215` | Byte-identical |
| `docs/lang-safety/comparative/README.md` | 6145 | `c1ec6d65c6f1905474792f1993bf74c6f8cf66943cfac557f858762671367828` | Byte-identical |
| `docs/lang-safety/comparative/ada-deep-dive.md` | 30770 | `be3f7790aba987a463bda08b32810837299833a57bfd12ac455a67076c5c4dfa` | Byte-identical |
| `docs/lang-safety/comparative/ada.md` | 18539 | `e078c2f6b87f00147e5b4198014b5abaccecf753d8336704099b4b83c921c303` | Byte-identical |
| `docs/lang-safety/comparative/austral.md` | 7221 | `815c8ffe294c75985c35f89a38762ca34a3eb650d8e4e0c46ca4e47c077bdcbf` | Byte-identical |
| `docs/lang-safety/comparative/cyclone.md` | 8162 | `b8846bc621148e18c02e4005caa1dca21ab8b1b8ae7f715f59dcd72bf3e4790a` | Byte-identical |
| `docs/lang-safety/comparative/hylo.md` | 8069 | `44f9bb207eed489213f24eedfd13f25afd64d230acb460360997036bfa9bcd5a` | Byte-identical |
| `docs/lang-safety/comparative/inko-koka-verona.md` | 6412 | `093612351f9321ae7d3d35e39ec1da338d29c601b1e3a54ee5caf0bd8c0eb26e` | Byte-identical |
| `docs/lang-safety/comparative/mojo.md` | 5906 | `d7de5d0987a3bfba8c1b0177b436d1e2650ddc49fd4f6c379e11feb5b230618b` | Byte-identical |
| `docs/lang-safety/comparative/pony.md` | 7779 | `21f84a1df7e4e7123db082f44977616dbbf499e35bda7bdf79400a601460051f` | Byte-identical |
| `docs/lang-safety/comparative/rust.md` | 14663 | `4cea8b6025a0e505706b15deba0c42940b1eccd4b91f30701aabb6a6643691c2` | Byte-identical |
| `docs/lang-safety/comparative/swift.md` | 9597 | `736469f37ecde1a1341d1ff0217c5b9efd4d4666abe3f28aee9141e97555bae6` | Byte-identical |
| `docs/lang-safety/comparative/vale.md` | 6980 | `860f3fbf1ab5ad86771203ad1c5a19d2193e479ab1b44dff9fc81401d887746b` | Byte-identical |
| `docs/lang-safety/comparative/zig.md` | 10860 | `9b989b5ba1759b9001f44df5ff85935d26b4ec8aee9fcdedd6cb40684302f4e3` | Byte-identical |
| `docs/lang-safety/compile-time-knowledge.md` | 22326 | `c2e4dfa99d6a238757c1a65f1e461fe8220a4fb4ca74ec2ffc05f3a5e5c9019e` | Byte-identical |
| `docs/lang-safety/conversions.md` | 21643 | `a06467b9f33ec862f5867ff72bcc29aee98885de7422cf82f2adec047b1a0864` | Byte-identical |
| `docs/lang-safety/edge-cases/01-cast.md` | 12478 | `45b56ab9397142044db0089d6c3c2c83f5d5e83ec11a6052bb839d4233af5e66` | Byte-identical |
| `docs/lang-safety/edge-cases/02-nullable-pointers.md` | 10285 | `10744174c830fbc4ca436a01b6872c9a729cb201b70c701dacbe494507dd66d0` | Byte-identical |
| `docs/lang-safety/edge-cases/03-definite-assignment.md` | 9455 | `f7d5075819f074231ca809fdb753a1e8956c927b7e2c1cabc97bbf6b5929d021` | Byte-identical |
| `docs/lang-safety/edge-cases/04-nonzero-division.md` | 8264 | `03f7f8aafb377846baf3d55bb1176b13cbb6e6a11064b4a2665ff6171d8d5324` | Byte-identical |
| `docs/lang-safety/edge-cases/05-stack-budget.md` | 7880 | `4778fa145a2f3641b499e4dd2aecd67b8d38fc6ad75f698c16aa6ae2b0b87cb2` | Byte-identical |
| `docs/lang-safety/edge-cases/06-typed-arithmetic.md` | 8910 | `8990c9d350c9bd1be2a025b2c7aeb2f87d626b2ddc6334ac7a91cbcfce472b04` | Byte-identical |
| `docs/lang-safety/edge-cases/07-bounded-indexing.md` | 8496 | `9538fd9d2e8f4e3fa5630ed167e82d8e6733a21f31e9d7390486c9cf58f71caf` | Byte-identical |
| `docs/lang-safety/edge-cases/08-option-result.md` | 8345 | `07b82c7c14bb6754d8376857ce9eca28057c8d9322205ec38cf80c29296b7b7a` | Byte-identical |
| `docs/lang-safety/edge-cases/09-refinement-lite.md` | 9256 | `2890148b775a167ce0ec28b163d5d8465566ebf8efb56d12f16b5dd80d595af2` | Byte-identical |
| `docs/lang-safety/edge-cases/10-affine-ownership.md` | 11511 | `8267de6515d5c130e9ee8ff09b10e3a667b86a053fc4141d1bfb96868bc77aef` | Byte-identical |
| `docs/lang-safety/edge-cases/11-finite-floats.md` | 8163 | `de9c1bb320be69720785763382876b443cbc791509db31f09318b4408c9bfd91` | Byte-identical |
| `docs/lang-safety/edge-cases/12-ffi-boundary.md` | 8625 | `232287e5ce73867b4cb3d7002b10f46dc09329d260720fd8e4206eeacdc22e2e` | Byte-identical |
| `docs/lang-safety/narrowing.md` | 20978 | `d0ee6318af8fcac88d5dd2489a5f210a2d8cba2faa025dfc7ec16ca678db263d` | Byte-identical |
| `docs/lang-safety/parameter-modes.md` | 17537 | `139fcc10fdd0cc9522c64c769061af8c76cead858252d2bd7dcada20aabe57be` | Byte-identical |
| `site/public/docs/agent-usage.md` | 1352 | `0575c3b679d0a9bdbf3501d8efbf10a1c66f9ad985d887cbeaa6c83889a90343` | Byte-identical |
| `site/public/docs/compiler.md` | 1934 | `96fcdb6f74d6587081c31f2e30ef4131e169590185f0e3af5a2f34afc8f4690f` | Byte-identical |
| `site/public/docs/index.md` | 1694 | `373b8be1ce001d198f82519df59ddf58367a14640a9709f36dd1feb571153386` | Changed as described |
| `site/public/docs/language.md` | 2151 | `9e9e1d93b97dc7dd382a489385cfbeb9bece063ab2a5837797aa1a184f8e76eb` | Byte-identical |
| `site/public/docs/project.md` | 1325 | `abb8fbf82de2e5ef65abcd5da635e262c2636a8843cb8ac2a02d2878cd726468` | Byte-identical |
| `site/public/docs/release.md` | 1488 | `08f026c4d66f5342e17206ce055219c538ffc70dc62ac55169108786ee19b858` | Byte-identical |
| `site/public/docs/start.md` | 1825 | `be08a8391b7d6b6ac17bca179219617f5960cbc4cd2831d95a6f433ecb47d8db` | Byte-identical |
| `site/public/docs/status.md` | 1606 | `31ebb29d8704387a6827c707865a67d55f2985127e9882bf4197cde51e932590` | Byte-identical |
| `site/public/docs/stdlib.md` | 1402 | `5d239a4811aa2f1799886f4116025481a868386e1b206cf4d815a61d09bf7602` | Byte-identical |
| `site/public/llms-full.txt` | 14235 | `2bf453b41ccb21e6965a4edf579aca882ef255587bd3d088055430e71c78d169` | Changed as described |
| `site/public/llms.txt` | 1358 | `3ea0e0173656bc49db571282f629471f97ae48093436b9367d5ad5ff00467527` | Byte-identical |
