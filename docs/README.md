# Repository documentation

The [project README](../README.md) and [release checklist](RELEASE.md) are the
authoritative user-facing guides. Choose an entry point below; use
[Status](STATUS.md) to distinguish implemented behavior from planned work.

## Use the language

| Need | Document |
| --- | --- |
| Install A7 and use the CLI | [Project README](../README.md) |
| Look up syntax and semantics | [Language specification](SPEC.md) |
| See complete programs | [Examples](../examples/) |
| Understand an error | [Diagnostic catalog](ERROR_CATALOG.md) |
| Check safety guarantees and gaps | [Safety contract](SAFETY_CONTRACT.md) |
| Read release changes | [Changelog](CHANGELOG.md) |

The specification includes planned features. Read its implementation limits
alongside Status; an accepted example does not establish general safety.

<a id="use-and-change-the-compiler"></a>

## Change the compiler or docs

| Need | Document |
| --- | --- |
| Find compiler stages and modules | [Architecture](ARCHITECTURE.md) |
| Follow repository working rules | [Agent/contributor instructions](../AGENTS.md) |
| Run verification and package checks | [Release checklist](RELEASE.md) |
| Understand the trust boundary | [Security policy](SECURITY.md) |
| Maintain public documentation | [Documentation maintenance](../site/public/docs/project.md#documentation-maintenance) |
| Style the site | [Design system](design-system.md) |

<a id="read-the-public-docs"></a>

The [public docs index](../site/public/docs/index.md) organizes user guides.
Its Markdown sources live in `site/public/docs/`. The
[compact agent index](../site/public/llms.txt) and
[full public corpus](../site/public/llms-full.txt) are generated from those pages;
they do not include all repository research or PDFs. See
[agent usage](../site/public/docs/agent-usage.md) for fetch paths.

<a id="continue-safety-design-work"></a>

<a id="plan-v1"></a>

## Follow decisions and design work

The [plan index](plan/README.md) maps current work, approvals, research and dated
handoffs. [Status](STATUS.md) and the [delivery roadmap](plan/delivery-roadmap.md)
own current todos. The [decision ledger](plan/decisions.md) records user choices;
a research recommendation is not approval or evidence that a feature shipped.
Use the [continuation prompt](plan/goal-prompt.md) to resume approved work.

- [Safety research index](lang-safety/README.md): rationale, edge cases and
  comparisons. Its [handoff](lang-safety/HANDOFF.md) and
  [decision record](lang-safety/08-decisions.md) retain their historical context.
- [Memory plan](plan/memory.md): proposed automatic-memory design.
- [Plan research](plan/research/README.md): advisory studies and reviews.
- [Language inspirations](inspirations.md): ideas from other languages, their
  research records and A7 dispositions.
- [Array programming proposal](design/array-programming.md): tensor and
  accelerator sketches, not implemented syntax.
- [Zig GPU research](research/2026-10-07-zig-gpu-support.md): versioned evidence,
  including local compile-only observations.

<a id="historical-reports-and-artifacts"></a>

## Find historical evidence

The [audit index](audits/README.md),
[archived V1 plan](plan/archive/v1-plan-before-2026-10-16.md) and
[archive notes](archive/README.md) preserve dated work. Each record keeps its
scope and verification limits. Historical passing checks do not override later
counterexamples. [Error analysis](ERROR_ANALYSIS.md) describes an older
36-example compiler state, not current verification.

The [pointer syntax analysis](POINTER_SYNTAX_ANALYSIS.pdf) is historical design
material. Its proposed reference operators are not current syntax; use the
[specification](SPEC.md#35-reference-semantics) and
[safety contract](SAFETY_CONTRACT.md#reference-surface). Six alternate renderings
were removed with user approval on 2026-09-19 and remain in git history.

Use `git log -- README.md docs site/public/docs site/public/llms.txt
site/public/llms-full.txt` for changes over time. Preserve original dates,
qualifications and sources when citing historical records.
