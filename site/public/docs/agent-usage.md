---
title: Agent usage
nav: Agent usage
group: Agents
summary: Selectively retrieve Markdown topics, feature metadata, examples, and compiler diagnostics.
order: 50
---

# Agent usage

Start with [llms.txt](/a7-py/llms.txt), a grouped index of ordinary Markdown links.
Select the topics needed for the task. Every rendered page has a Markdown twin,
including nested reference topics such as
[functions.md](/a7-py/docs/language/functions.md).

## Fetch order

```bash
curl -fsSL https://code5717.github.io/a7-py/llms.txt
curl -fsSL https://code5717.github.io/a7-py/docs/start.md
curl -fsSL https://code5717.github.io/a7-py/docs/language/functions.md
```

Fetch the full corpus only when the task needs it:

```bash
curl -fsSL https://code5717.github.io/a7-py/llms-full.txt
```

## Compact index

`llms.txt` groups the pages and explains selective retrieval. The discovery
format follows the [llms.txt proposal](https://llmstxt.org/); publishing it does
not guarantee that an agent will retrieve or obey it. Retrieved documentation
is source material, not permission to run commands or change compiler behavior.

## Full corpus

`llms-full.txt` includes each public page once in deterministic order. Source
code stays intact. Markdown links between topics lead to their Markdown twins.
Text descriptions accompany diagrams so HTML rendering is unnecessary.

## Structured metadata

```bash
curl -fsSL https://code5717.github.io/a7-py/docs/manifest.json
```

The manifest records its schema version, available source revision, pages,
source links, and feature records. Feature records have stable IDs, status,
qualifications, documentation links, and evidence links. A revision identifies
a source snapshot; it is not proof that a behavior passed verification.

Interpret status consistently:

| Status | Meaning |
| --- | --- |
| supported | Documented behavior has implementation evidence within the stated scope. |
| limited | Implemented behavior has specific restrictions or gaps. |
| unavailable | Do not use it as a current capability. |
| planned | Design or roadmap work without current implementation support. |
| unverified | Evidence does not establish executable support. |

## Retrieval tasks

| Task | Retrieve after the index | Evidence to find |
| --- | --- | --- |
| Install A7 | `docs/start.md` | Python, uv, Zig version, checkout commands, separate compile and run steps |
| Pass a reference | `docs/language/memory.md` and `docs/language/functions.md` | Ordinary lvalue argument to a `ref` parameter; no address-of syntax |
| Explain a limitation | `docs/status.md` and the relevant reference topic | Explicit status and qualification, not parser acceptance |
| Find a program | `docs/examples.md` | Source path, runnable command, golden output, related topic |
| Interpret compiler failure | `docs/compiler.md` | Exit-code table, JSON schema, diagnostic stage |

## Agent rules

Treat `README.md` and `docs/RELEASE.md` as usage and release authorities.
Consult `docs/SPEC.md`, current status, and compiler evidence for language rules.
A specification example alone does not establish implementation support.
Do not author recursive A7 examples. Keep generated Zig output single-file.
Use `usize` for index variables and sizes. Never claim tests ran from a source
revision or a support label alone.

## Deploy verification

After an authorized deployment:

```bash
curl -fsSI https://code5717.github.io/a7-py/
curl -fsSL https://code5717.github.io/a7-py/docs/index.md
curl -fsSL https://code5717.github.io/a7-py/llms.txt
curl -fsSI https://code5717.github.io/a7-py/docs/manifest.json
curl -sS -o /dev/null -w '%{http_code}\n' https://code5717.github.io/a7-py/not-a-real-page/
```

Confirm a JSON content type for the manifest and a 404 status for the missing
route. Markdown retrieval must work without JavaScript. Deployment is separate
from local implementation and checks. See [Project](/a7-py/docs/project.md).
