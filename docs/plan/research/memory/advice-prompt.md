# Advisor prompt

The same prompt was sent to GLM, Fable and Grok on 2026-09-15.

```text
You are an external advisor invoked by a controlling Claude Code session. You are not the coordinator. Your output is advisory. Do not launch any other model or agent CLI. Read-only: do not edit, create or delete files in the repository.

Repository: /home/cx89/Projects/pl-dev/a7-py (A7, an ahead-of-time compiler from .a7 source to Zig, written in Python).

Read first:
- docs/plan/memory-brainstorm.md (draft brainstorm plan for the memory model)
- docs/plan/decisions.md (user decision ledger; especially L15, L16, L17, L18)
- docs/plan/README.md (v1 plan and gates)
- docs/SAFETY_CONTRACT.md and docs/SPEC.md sections 3.3-3.5, 6.3 and 8 (current memory surface: new, del, defer, ref, nil)
Consult as needed: docs/plan/research/memory-design-codex.md, docs/plan/research/memory-security-glm.md, docs/plan/research/ownership-zig-odin-glm.md, docs/lang-safety/comparative/, docs/lang-safety/08-decisions.md.

User's memory direction, in their words:
- "something like garbage collection, but with data oriented design in mind and everything is resolved compile-time so it becomes as jai, odin and zig"
- "i want to make this super simple like python and how gc languages work"
- "the compiler should group some stuff together as arenas and pools, we need new concepts"
- "also reusing allocated space and optimization, i want this to be the next generation of compiler technology"

Fixed constraints: no runtime garbage collector and no reference counting as the core; explicit-width integers with wrapping + - *; IEEE floats like Zig/C; function argument bindings immutable, mutation of referenced data by explicit permission; A7 source recursion is banned (compile-time error); no public address-of or dereference operators; fail-closed safety (unproven risky operations are rejected before codegen); CPU-first A7-owned tensors and reverse-mode autodiff are in v1; concurrency is in v1.

Give candid, expert advice on:
1. Is the combined goal (Python-simple surface + no GC + compile-time resolved + compiler-inferred arenas/pools + storage reuse) achievable? Where exactly does it break, and what is the least-bad set of restrictions or residual runtime work?
2. The strongest candidate architecture. Be concrete about the analyses (escape analysis, region/lifetime inference, uniqueness/affinity, liveness-based static memory planning, in-place reuse, SoA layout), the IR they need, and how the recursion ban, immutable arguments and whole-program compilation help.
3. The "new concepts" A7 should introduce (compiler-internal and, if any, user-visible). Critique or replace the draft names: lifetime group, family, home, link, boundary.
4. How to handle the hard cases: returning allocations, growing lists with references into them, cyclic graphs and parent pointers, caches and globals, closures, long-running loops/servers, entity removal, tensors with views and autodiff tape, optimizer state and checkpoints, tasks/channels, native kernel buffers.
5. What happens when inference fails: diagnostics, optional hints, or fallback. Which fallback keeps the Python-simple feel without breaking fail-closed safety?
6. Prior art to study, with precise names: languages, papers, compilers (for example MLKit region inference, Tofte-Talpin, ASAP static deallocation, Lobster, Koka/Perceus reuse, Hylo mutable value semantics, Vale generational references, Cyclone, Val, Swift OSSA, Go/Java escape analysis, ML compiler memory planners, Jai/Odin/Zig allocator idioms). Say which parts are directly usable and which are traps.
7. Critique of the brainstorm plan in docs/plan/memory-brainstorm.md: what is missing, mis-ordered or unnecessary; suggest the corpus programs that would most quickly falsify a design.
8. Concrete A7 examples for your recommended direction, clearly labeled as proposed syntax (no recursion, usize indices, no & or * operators).

Separate facts you verified from inferences. Do not claim you ran code. Keep the answer structured, direct and as long as it needs to be.
```
