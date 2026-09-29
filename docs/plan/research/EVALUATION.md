# How ideas in these research programmes are judged

Set 2026-09-18 by the user: keep both agentic and human coding in mind, weighted
toward agentic. And do not research everything — some supplied ideas belong to a
different kind of project and need a ruling, not a report.

## Every claim gets two verdicts

| Axis | Question |
| --- | --- |
| **Agent value** (weighted higher) | Does this make a coding agent more effective? An agent has no eyes, infinite patience, and a small context window. It benefits from queryable state, machine-readable output, deterministic re-execution, fast feedback loops it can run thousands of times, and errors that localize a fault precisely. It gains nothing from a rendering, a gesture, or a smooth drag. |
| **Human value** | Does this make a person more effective? A person benefits from seeing shape at a glance, from direct manipulation, and from not holding state in working memory. |

A visual idea often has an agent-facing twin: a timeline a person scrubs is a
history an agent queries; an inspector a person reads is a structured dump an
agent parses; a value scrubber is a parameter sweep an agent runs in a loop. When
an idea has such a twin, name it — that is usually the version worth building
here.

## Depth is decided by value, not by interest

- **Report**: high agent value, or high human value and cheap to build. Full
  research with sources.
- **Section**: useful but narrow. A few paragraphs inside a related report.
- **Ruling**: belongs to a different kind of project (a game engine, a graphics
  tool, a music environment), or depends on hardware A7 does not target. One
  paragraph: what it is, why it is out of scope here, and the one transferable
  idea if there is one. Do not research it further.

Rulings are not dismissals. An idea can be excellent and still be out of scope
for an ahead-of-time compiled systems language with no runtime and no editor.

## What A7 is, for scoping

An ahead-of-time compiler from `.a7` to Zig, producing a native binary. No
runtime of its own, no concurrency, no accelerator support, no incremental
compilation, no editor integration, no reload story, and today no mapping from
the generated Zig back to `.a7` lines. Source recursion is banned. Compile-time
proof with rejection on failure is the intended safety contract; the current
implementation has known proof and lifetime gaps described in
[Status](../../STATUS.md). Package-registry work is out of scope.
Anything that assumes an interpreter, a live image, or a graphical editor has to
say plainly what it would cost to get there.
