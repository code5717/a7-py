# Repository documentation

The [project README](../README.md) and [release checklist](RELEASE.md) are the
authoritative user-facing docs. The public site summarizes repository material.
Use this index to find current guidance, design work, and historical evidence.

## Use and change the compiler

| Need | Document |
| --- | --- |
| Set up the compiler and use the CLI | [Project README](../README.md) |
| Look up language syntax and semantics | [Language specification](SPEC.md) |
| Check implementation gaps and priorities | [Status](STATUS.md) |
| Understand enforced safety checks and unfinished proof work | [Compiler safety contract](SAFETY_CONTRACT.md) |
| Build, verify, and prepare release artifacts | [Release checklist](RELEASE.md) |
| Understand the trust boundary and report vulnerabilities | [Security policy](SECURITY.md) |
| Read release-facing changes | [Changelog](CHANGELOG.md) |
| Read runnable language examples | [Examples](../examples/) |

The specification includes planned language features. Read its implementation
qualifications together with Status. A design requirement or a passing example
does not establish complete safety or backend coverage.

## Read the public docs

- [Public docs index](../site/public/docs/index.md) organizes the site by task.
- [Compact agent index](../site/public/llms.txt) lists public Markdown pages.
- [Full public corpus](../site/public/llms-full.txt) combines those pages.
- [Agent usage](../site/public/docs/agent-usage.md) documents fetch paths.
- [Documentation maintenance](../site/public/docs/project.md#documentation-maintenance)
  describes how public summaries follow repository docs.

The full public corpus contains the site pages, not all repository research or
PDFs. Its source pages live in `site/public/docs/`. The site build regenerates
`llms.txt` and `llms-full.txt` from those pages.

## Continue safety-design work

The [safety research index](lang-safety/README.md) maps the research, rationale,
source attributions, edge-case studies, and language comparisons. Start with
the [handoff](lang-safety/HANDOFF.md) for the design-work snapshot, then consult
the [decision record](lang-safety/08-decisions.md) for acceptance and open questions.
The [comparative index](lang-safety/comparative/README.md) maps per-language studies.

These records contain proposals and historical implementation assessments.
Accepted design decisions are not proof that a feature has shipped. Compare them
with [Status](STATUS.md) and the [compiler safety contract](SAFETY_CONTRACT.md)
before implementation work.

## Plan v1

- [Decision ledger](plan/decisions.md): user decisions for v1, including
  superseded research decisions.
- [V1 plan](plan/README.md): order of work, evidence requirements and open
  approval gates.
- [Memory plan](plan/memory.md): proposed automatic, compile-time memory
  management with value semantics.
- [Plan research](plan/research/README.md): advisory framework, hardware,
  language, memory and security reports, plus the memory audits and reviews.

A plan entry is not an implemented feature. Check [Status](STATUS.md) for current
behavior.

## Historical reports and artifacts

The [audit index](audits/README.md) maps the dated reviews.
Each records its own scope and verification limits. Historical passing gates do
not override later counterexamples or establish that a finding remains unfixed.

[Error analysis](ERROR_ANALYSIS.md) records an older 36-example compiler state.
Its measurements are historical, not current verification results.
[Archive notes](archive/README.md) record earlier cleanup and the locations of
archived tools.

The [pointer syntax analysis](POINTER_SYNTAX_ANALYSIS.pdf) remains as historical
design material. Its proposed reference operators are not current A7 syntax.
The six alternate renderings were removed on 2026-09-19 with user approval;
git history retains them. Current reference syntax is documented in the
[specification](SPEC.md#35-reference-semantics) and
[safety contract](SAFETY_CONTRACT.md#reference-surface).

For changes over time, use `git log -- README.md docs site/public/docs
site/public/llms.txt site/public/llms-full.txt`. Preserve each record's dates,
qualifications, and sources when citing it.
