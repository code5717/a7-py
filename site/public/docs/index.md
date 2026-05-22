---
title: A7 Documentation
nav: Overview
group: Getting started
summary: What A7 is, how the compiler pipeline works, and where to read next.
order: 0
---

# A7 Documentation

A7 is an ahead-of-time compiler. It lowers `.a7` source to a single Zig 0.16
file, then the host Zig toolchain builds a native binary. The compiler is
Python. There is no A7 runtime.

## Pipeline

```text
.a7 → tokenize → parse → semantic checks → emit Zig → native binary
```

## Read order

| Need | Page |
| --- | --- |
| Install and run your first program | [Start](/a7-py/start/) |
| Syntax and language rules | [Language](/a7-py/language/) |
| Built-in modules | [Stdlib](/a7-py/stdlib/) |
| Compiler pipeline and CLI | [Compiler](/a7-py/compiler/) |
| Current gaps and priorities | [Status](/a7-py/status/) |
| Release gates and deploy | [Release](/a7-py/release/) |
| curl / agent fetch paths | [Agent Usage](/a7-py/agent-usage/) |
| Contributing and doc maintenance | [Project](/a7-py/project/) |

## Repository docs

The site compresses material from the repository. For compiler work, treat these
as authoritative:

- `README.md` — everyday usage and examples
- `docs/SPEC.md` — language semantics
- `docs/STATUS.md` — gaps and priorities
- `docs/RELEASE.md` — release gates

Drift between the site and repository docs is a bug.

## Public contract

These URLs are intentionally stable:

- `/a7-py/`
- `/a7-py/llms.txt`
- `/a7-py/llms-full.txt`
- `/a7-py/docs/index.md`
- `/a7-py/docs/start.md`
- `/a7-py/docs/language.md`
- `/a7-py/docs/stdlib.md`
- `/a7-py/docs/compiler.md`
- `/a7-py/docs/status.md`
- `/a7-py/docs/release.md`
- `/a7-py/docs/agent-usage.md`
- `/a7-py/docs/project.md`
