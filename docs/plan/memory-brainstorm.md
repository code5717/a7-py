# Memory brainstorm record

Status: closed record of how the memory design was explored, 2026-09-15 to
2026-09-16. The result is the [memory plan](memory.md). Decisions are in the
[ledger](decisions.md).

## Why

The user asked for memory management that feels like a garbage-collected
language, has no runtime collector and is resolved at compile time (L15, L17, L18,
L19). It must have C-like performance (L20) and avoid Zig's manual memory work
(L21).

No known system frees arbitrary pointer graphs exactly when they die, at compile
time, for every program. Every existing design restricts programs, keeps some
runtime work, or holds memory longer than necessary. The brainstorm had to choose
which of these A7 accepts, and where.

L19 is stricter than the advisors' proposals. Their designs still ask users to
model graphs as tables and ids and to rewrite programs the compiler rejects. Under
L19, memory-related rejections and memory vocabulary must be rare enough that
ordinary users never meet them.

## Steps

| Step | Output |
| --- | --- |
| 1. Read all saved research | Reading notes A–H in [research/memory](research/memory/) |
| 2. Ask GLM, Fable and Grok the same question | [Advisor prompt](research/memory/advice-prompt.md) and three advice files |
| 3. Check user-supplied material | [Gemini comparison](research/memory/gemini-comparison.md) and [functional memory fact check](research/memory/functional-memory-fact-check.md) |
| 4. Compare the advice | [Synthesis](research/memory/synthesis.md) |
| 5. Write the plan | Memory plan revision 1 |
| 6. Audit edge cases | Five audits, summarized in the [edge-case audit](research/memory/edge-case-audit.md); revision 2 |
| 7. External review | Qwen, Kimi and nine GLM reviews, all complete on 2026-09-16. See the [review index](research/memory/review/README.md); revision 3 pending |

Reading groups:

| Notes | Sources |
| --- | --- |
| A | `lang-safety` 01–04: capabilities, sanitizers, hardware, comparison |
| B | `lang-safety` 05–07, Codex review, compile-time knowledge |
| C | Decision register, HANDOFF, parameter modes, research index |
| D | Conversions, narrowing, the 12 edge-case studies |
| E | The 13 comparative language studies |
| F | Plan research: memory design, memory security, ownership, numerical policy |
| G | Plan research: language features, AI frameworks, hardware |
| H | 2026-09-14 memory, compiler, security and contract audits; pointer-syntax PDFs; current SPEC memory surface; memory repro fixtures |

## Findings

- **A large subset is achievable, not every program.** Training steps, game-style
  worlds, request loops, owned tensors and structured tasks fit a static model.
  Arbitrary object graphs do not (all three advisors, synthesis). GLM reframed the
  promise: no collector, no counts, no pauses, static free points, and small
  deterministic runtime costs such as bump allocation, free-list reuse and one
  generation compare (`advice-glm.md`).
- **Static placement breaks** where runtime data chooses lifetimes: cache
  eviction, runtime-selected subsets, removal of single nodes from shared graphs,
  escaping closures, unbounded accumulation and dynamic sizes (`advice-glm.md`).
- **Saved research did not design L15.** It assumed manual `del`, proposed
  Rust-style drop, or optional collectors. None of it covers data-oriented layout
  (notes B, C, D, F, G).
- **No Odin or Jai study exists.** L15 names both, but `lang-safety/comparative/`
  has no Odin or Jai file, and Zig's allocator idioms get one paragraph. The
  comparative files still assume explicit `del`, finite floats and proof-only
  arithmetic (notes E). An Odin, Jai and Zig allocator study is a missing input.
- **The recursion ban does not prevent cyclic data.** Loops can build cycles
  (notes B). Releasing storage by extent instead of by reachability makes cycles
  harmless (`advice-glm.md`).
- **Current compiler gaps are prerequisites:** fact tracking drops branch updates,
  ignores calls and keys on names; there is no escape analysis; union and
  initialization rules are incomplete; a self-referential `ref` struct field
  compiles but cannot be assigned (notes H; see the memory plan).
- **Defects found while reading, compile-only.** Copying a `ref` into a struct
  field and then deleting the original writes freed memory. Returning a struct
  that holds a `ref` to a local leaves a dangling reference (notes H).
- **Storage reuse prior art splits in two** (corrected 2026-09-16). Koka and
  Lean 4 place reuse at compile time and test uniqueness with a runtime count.
  Roc does the same, with narrower reuse in its current compiler. Carp frees
  storage statically; no compiler-inserted reuse was found in the files checked.
  MLKit was not checked. L15 and L18 need reuse without the runtime test. GLM
  proposes deriving uniqueness from affine ownership (`advice-glm.md`). FP²
  checks function definitions statically; at call sites the static option is
  uniqueness typing, which duplicates functions
  ([storage reuse study](research/memory/reuse-languages.md)).
- **Tensors.** A buffer may be reused only when no alias, saved autodiff value or
  caller can observe its old contents. Tape storage fits a per-step extent. Async
  kernels complicate releases at scope end (notes G, `advice-glm.md`).

## Changes from the first brainstorm plan

The first draft planned seven sessions that scored mechanisms as rival
candidates. The advice changed that (synthesis):

- The mechanisms form one stack, not alternatives. The typed IR (v1 track 4) is
  its base.
- Single ownership closes today's double-free and alias bugs and sits under
  extents, pools and reuse.
- Reference counts, including compile-time count elision, are not candidates.
  The contract rules out reference counts (memory plan contract item 1).
- A `--memory-report` shows compiler decisions instead of source annotations
  (gate M8).

The draft and advisor concept names map to the plan's terms:

| Draft or advisor term | Plan term |
| --- | --- |
| lifetime group, home (GLM, draft), frame (Grok), region (Fable) | extent |
| family, pool, store, `Store<T>` | `Table(T)` where users see it; pool in lowering |
| link, handle, `Handle<T>` | `Id(T)`, or a `usize` position in a `List` |
| boundary, escape edge | escape |

## Opening questions and where they went

| Question | Answer in the memory plan |
| --- | --- |
| Which programs should be easy first? | The falsifying corpus covers servers, trees, entity systems, training steps, tasks and native kernels |
| May the compiler reject a program it cannot place? | Placement never fails visibly; the compiler copies a value out on the escaping path. Other rejections form a closed list (contract item 8) |
| May small runtime checks remain? | Yes, only those listed as residual runtime work (section 6) |
| Do users see arenas and pools? | No (contract item 9); an optional report shows decisions (gate M8) |
| How is cyclic data handled? | Lists with `usize` positions, or `Table(T)` with `Id(T)` links where removal is needed (gates M1, M5) |
