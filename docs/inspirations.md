# Language inspirations

This is A7's index of ideas studied in other languages and programming systems.
It links each idea to its research record and distinguishes adopted decisions
from comparisons and proposals. Updated 2026-10-17.

The [decision ledger](plan/decisions.md) owns approvals. The
[specification](SPEC.md) and [status](STATUS.md) describe implementation and gaps.
Research recommendations, example syntax and upstream benchmark results do not
establish A7 behavior. Detailed reports keep their original dates and evidence
limits; this index does not freshly verify every upstream claim.

## Direct influences and current decisions

| Language | Idea relevant to A7 | A7 disposition and evidence |
| --- | --- | --- |
| Zig | Native backend, explicit representation, compile-time evaluation, native integration and strict floating-point behavior | Backend retained under L21, L22 and L41. Zig's manual memory model is not A7's intended user model. See [backend opportunities](plan/research/zig-free-features.md), [safety comparison](lang-safety/comparative/zig.md) and [GPU research](research/2026-10-07-zig-gpu-support.md). GPU execution remains deferred under L75. |
| Odin | Wrapping arithmetic, exact-fit untyped constants, module organization and data-oriented programming | L5 adopts wrapping arithmetic; L47 adopts contextual exact fitting. A7's file-module choice is its own contract. See [constants](plan/research/global-constants-2026-09-20.md), [modules](plan/research/modules-odin-zig-go.md) and [ownership comparison](plan/research/ownership-zig-odin-glm.md). |
| Jai | Predictable data layout, performance goals, compile-time execution and live development | L15 cites the performance direction; no wholesale Jai memory or metaprogramming contract is adopted. The [ownership comparison](plan/research/ownership-zig-odin-glm.md) contains corrections. The [language-facilities programme](plan/research/language-facilities/README.md) includes planned comparisons. |
| C | Performance and memory baseline, explicit layouts, native ABI and IEEE floating point | L16 and L38 retain numerical and per-workload measurement requirements. [Goose preparation](plan/packets/P-GOOSE-direction.md) defers C export, while preserving C benchmark controls. Native integration remains through Zig. |
| Python | Low user effort, ordinary programming without manual memory bookkeeping, bootstrap implementation | L17 and L19 establish the usability goal. Python is the current compiler implementation; L73 requires A7 self-hosting before V1 publication. See [architecture](ARCHITECTURE.md) and [bootstrap proposal](plan/packets/P-BOOTSTRAP-parity.md). Python runtime semantics are not adopted by analogy. |
| Goose | Inferred lifetime roots, data stacks, stable growth, compact nested values and ADTs, relative references, destination construction, nonlocal returns, isolated workers and static callbacks | L77 authorizes research and preparation. The [pinned study](plan/research/goose-2026-10-17.md) and [preparation packet](plan/packets/P-GOOSE-direction.md) state restrictions and experiments. No production memory mechanism or new syntax is selected. C output and TinyCC are deferred. |

## Safety, ownership and storage reuse

[Lobster lessons for A7](plan/research/lobster-2026-10-17.md) examines automatic
borrowing with runtime reference counting, ownership specialization, inline
values, non-escaping callbacks, string construction and isolated workers. Its documented alias limits
and cycle handling inform adversarial tests. No memory mechanism or syntax is
adopted; upstream performance claims remain unverified for A7.

The older [comparative studies](lang-safety/comparative/README.md) contain
recommendations superseded by later decisions. In particular, they do not
authorize parameter-mode syntax, replacing current stored references, removing
`del`, or changing wrapping arithmetic. Follow the current ledger and spec.

| Language or family | Ideas examined | Research and limits |
| --- | --- | --- |
| Rust | Ownership, lifetime and alias checks, sum types, safe interfaces and explicit failure handling | [Safety study](lang-safety/comparative/rust.md). A7 does not thereby adopt Rust lifetime syntax or exclusivity rules. Error composition is indexed below. |
| Ada and SPARK | Distinct and ranged types, contracts, proof obligations, packages, generics and tasking | [Safety study](lang-safety/comparative/ada.md), [whole-language study](lang-safety/comparative/ada-deep-dive.md). Refinement and proof proposals remain separate from A7's approved arithmetic. |
| Hylo | Mutable value semantics, ownership and parameter access modes | [Study](lang-safety/comparative/hylo.md). Comparative evidence, not adoption of its value or parameter model. |
| Swift | Borrowing, consuming values, exclusivity and reference-counting tradeoffs | [Study](lang-safety/comparative/swift.md). No new parameter modes or ARC policy selected for A7. |
| Cyclone | Safe-C design, regions and region inference | [Study](lang-safety/comparative/cyclone.md). Historical input to memory design, not measured A7 migration or performance evidence. |
| Austral | Linear ownership and a deliberately constrained borrow system | [Study](lang-safety/comparative/austral.md). User-visible linear syntax is not adopted. |
| Vale | Generational references and checked lifetime access | [Study](lang-safety/comparative/vale.md). A candidate tradeoff between static restrictions and runtime checks. |
| Pony | Reference capabilities, actors and transfer between isolated workers | [Study](lang-safety/comparative/pony.md). A7's [concurrency proposal](plan/packets/P-CON-structured-tasks.md) still needs its own lifecycle and channel contract. |
| Inko and Verona | Isolated storage and region-based concurrency | [Combined study](lang-safety/comparative/inko-koka-verona.md). Historical comparisons; neither runtime is selected. |
| Carp | Inferred ownership, allocation control and storage reuse | [Report](plan/research/memory/languages/carp.md), [correction](plan/research/memory/languages/carp-verify.md). Read both; the correction qualifies earlier findings. |
| Koka | Effects, Perceus reference counting and reuse analysis | [Report](plan/research/memory/languages/koka.md), [reuse synthesis](plan/research/memory/reuse-languages.md). Compile-time placement of count operations does not eliminate runtime uniqueness checks. |
| Lean 4 | Reference counting, uniqueness and functional value reuse | [Report](plan/research/memory/languages/lean4.md). Its evidence includes an HTML paper rendering; no A7 performance result follows. |
| Roc | Uniqueness, reuse, abilities and separation of applications from effect-providing platforms | [Memory report](plan/research/memory/languages/roc.md), [language sweep](research/language-needs/11-language-sweep-nim.md). Historical implementation claims need version checks before adoption. |
| Clean | Uniqueness typing and specialization tradeoffs | [Reuse synthesis](plan/research/memory/reuse-languages.md). A comparison within that study, not a separately qualified A7 mechanism. |
| MLKit and the ML family | Region inference and the boundary between static placement and dynamic storage | [Functional-memory fact check](plan/research/memory/functional-memory-fact-check.md), [supplied comparison](plan/research/memory/gemini-comparison.md). The comparison explicitly leaves MLKit unverified. |
| Kotlin, TypeScript, C# and Crystal | Flow-sensitive narrowing, null-state tracking and definite assignment | [Narrowing comparison](lang-safety/narrowing.md), [compile-time knowledge](lang-safety/compile-time-knowledge.md), [definite assignment](lang-safety/06-compile-time-safety.md#1-definite-assignment--flow-analysis). These historical comparisons motivate proof rules; they do not establish current A7 coverage. |
| OCaml, Haskell and Scala | Sum types, exhaustive matching and functional representations | [Compile-time safety techniques](lang-safety/06-compile-time-safety.md). Concept comparisons, not adoption of their evaluation or runtime models. |
| Liquid Haskell, F* and Dafny | Refinement predicates and solver-backed verification | [Narrowing research](lang-safety/narrowing.md), [compile-time safety techniques](lang-safety/06-compile-time-safety.md). No solver dependency or public refinement syntax is selected by these reports. |
| Idris | Dependent types and indexing guarantees | [Compile-time safety techniques](lang-safety/06-compile-time-safety.md). Foreign recursive examples are research material; A7's source and compiler recursion bans remain in force. |

## Errors, generics and compile-time programming

| Language or family | Ideas examined | Research and disposition |
| --- | --- | --- |
| Rust and Eros | Typed errors, combining error sets, widening during propagation, narrowing after handling and retaining diagnostic context | [Error-set composition](plan/research/consuming-results.md#error-set-composition-research-october-9) discusses Dillon McMahon's [article](https://mcmah309.github.io/posts/the-missing-piece-in-rust-error-handling/). A7 retains L68's Result/Option direction. Composition, consuming payloads and representation costs remain proposals. Eros is a library, not a language. |
| Go | Constant typing, declaration order and package/module alternatives | [Constants comparison](plan/research/global-constants-2026-09-20.md), [module comparison](plan/research/modules-odin-zig-go.md). A7 chose file modules and local imports; comparison does not import Go's runtime model. |
| D | Template constraints, specialization, compile-time function execution, ranges and explicit allocation auditing | [D study](research/language-needs/12-language-d.md). Its recommendations are advisory; phrases such as "adopt" in that report are not decisions. |
| Nim | Structural generic constraints, macros/templates and memory-management alternatives | [Language sweep](research/language-needs/11-language-sweep-nim.md). Historical source claims and syntax sketches need primary-source validation before implementation. |
| Gleam | Typed results, callback-based error flow and a small language core | [Language sweep](research/language-needs/11-language-sweep-nim.md). Proposed error-flow spellings are not A7 syntax. |
| Hare | Tagged error values and a restrained compiler/backend design | [Language sweep](research/language-needs/11-language-sweep-nim.md). Neither manual allocation nor proposed profile-dependent safety is adopted from the report. |
| V | Error propagation, fallback blocks, reflection and lessons from automatic-freeing claims | [Language sweep](research/language-needs/11-language-sweep-nim.md). These are research topics, not verified guarantees of V or A7. |
| C++ and Terra | Compile-time execution, specialization and control of generated layouts | [Language-facilities programme](plan/research/language-facilities/README.md). The listed topic reports are planned; the index alone is not completed research. |

The [conversion study](lang-safety/conversions.md) also compares method,
constructor and operator spellings across Kotlin, Rust, Python, JavaScript,
Swift and other languages. Its historical `number`/`int` examples predate A7's
explicit-width decisions. They are not current syntax or conversion rules.

## Lisp family and live programming

The [Lisp-family study](plan/research/lisp-family-2026-10-17.md) reviews primary
sources for macros, compilation phases, conditions and restarts, live images,
typing and runtime costs. It recommends binding-aware internal transformations,
explicit phase dependencies and reproducible tooling experiments. No Lisp syntax
or runtime is selected for A7; no Lisp implementation was executed.

| Language or system | Ideas already recorded | Evidence boundary |
| --- | --- | --- |
| Common Lisp and SBCL | Conditions/restarts, form-transforming macros, native compilation and saved images | [Lisp-family study](plan/research/lisp-family-2026-10-17.md). SBCL is an implementation. Native compilation can coexist with condition machinery; A7 would need an explicit runtime and cleanup contract. |
| Scheme and Guile | Hygienic macros, tail calls, compiler passes and foreign rooting | [Lisp-family study](plan/research/lisp-family-2026-10-17.md). Guile's runtime is implementation-specific. Proper tail calls do not relax A7's recursion ban. |
| Racket and Typed Racket | Binding-aware syntax objects, phase-separated imports, occurrence typing and typed/untyped boundaries | [Lisp-family study](plan/research/lisp-family-2026-10-17.md). Hygiene, type-aware rewriting and typed macro interfaces are separate concepts. |
| Clojure | Persistent values, transient builders, explicit state and transactional updates | [Lisp-family study](plan/research/lisp-family-2026-10-17.md). JVM services, GC and retry effects remain part of its cost and behavior model. |
| Emacs Lisp | Live evaluation, editor integration and native compilation within an existing runtime | [Lisp-family study](plan/research/lisp-family-2026-10-17.md). Native code still depends on Emacs objects and services. |
| GOOL and GOAL | Domain-specific game tooling and live native-target development | [Lisp-family study](plan/research/lisp-family-2026-10-17.md). Historical systems with different execution models; no A7 loader or reload implementation established. |
| Shen, Janet, Fennel and Hy | Portable cores, embedding, macros and reuse of host compilers | [Lisp-family study](plan/research/lisp-family-2026-10-17.md). Each has distinct typing, memory and host-runtime obligations. Documentation review is not implementation qualification. |
| Smalltalk and Self | Images, live objects and inspection | [Live-environment programme](plan/research/live-environment/README.md) and its [claims audit](plan/research/live-environment/00-claims-audit.md). Preserve the distinction between existing systems and proposed A7 tooling. |
| Erlang | Live code change, process isolation and a remote shell | [Runtime programme](plan/research/runtime-model/README.md), [language-facilities programme](plan/research/language-facilities/README.md). A7 has no adopted hot-reload contract. |
| Julia and ISPC | Structure-of-arrays layout and data-parallel programming | [Language-facilities programme](plan/research/language-facilities/README.md). Listed comparisons, not completed A7 layout experiments. |
| Unison and Hazel | Structural editing, incomplete programs and persistent code identity | [Language-facilities programme](plan/research/language-facilities/README.md), [live-environment programme](plan/research/live-environment/README.md). Research agenda only where the detailed report is absent. |

Light Table, Eve, Sketch-n-Sketch, Glamorous Toolkit, MPS, Observable and Jupyter
also appear in the [live-environment records](plan/research/live-environment/README.md).
These include tools and programming environments as well as languages. Their
presence does not establish an A7 editor, notebook or image runtime.

## Parallelism, tensors and hardware languages

| Language or system | Ideas examined | Research and disposition |
| --- | --- | --- |
| Bend | Parallel evaluation and the costs of a specialized execution model | [Bend 2 study](lang-safety/comparative/bend.md), [A7 assessment](plan/research/bend-for-a7.md). Keep these separate from older Bend/HVM2 descriptions in the [GPU sweep](research/language-needs/21-small-lang-gpu.md). |
| Mojo | Ownership, specialization and the host/kernel boundary for numerical work | [Safety study](lang-safety/comparative/mojo.md), [GPU sweep](research/language-needs/21-small-lang-gpu.md). No Mojo compiler/runtime component is selected. |
| Futhark | Restricted array programs, parallel transformations and CPU/GPU targets | [GPU sweep](research/language-needs/21-small-lang-gpu.md). Optimizer ideas are advisory; A7 GPU execution remains deferred. |
| WGSL, CUDA and other kernel interfaces | Explicit host/device boundaries and restricted device code | [Zig GPU study](research/2026-10-07-zig-gpu-support.md), [GPU interface research](research/language-needs/19-gpu-interface.md). A library or shader API is not an adopted A7 backend. |
| Haskell/Clash and Scala/Chisel | Hardware construction, elaboration and synthesizable subsets | [Software-to-hardware study](plan/research/hardware-export/01-software-to-hardware.md). RTL generation differs from native compilation and from a working FPGA deployment. |
| Bluespec | Rule-based hardware descriptions | [Software-to-hardware study](plan/research/hardware-export/01-software-to-hardware.md). Primary-source checks remain incomplete in that report. |
| Calyx, Dahlia and Spatial | Hardware scheduling, sized values and memory-port constraints | [Software-to-hardware study](plan/research/hardware-export/01-software-to-hardware.md). These are specialized languages or intermediate representations, not selected A7 dependencies. |
| Halide | Separating an image-processing algorithm from its execution schedule and partitioning work between CPU and FPGA | [Software-to-hardware study](plan/research/hardware-export/01-software-to-hardware.md). Historical measurements belong to their named workloads and hardware, not A7. |
| OpenCL | Explicit kernels and host/accelerator partitioning | [Software-to-hardware study](plan/research/hardware-export/01-software-to-hardware.md), [GPU sweep](research/language-needs/21-small-lang-gpu.md). Research does not establish A7 device execution. |
| SpinalHDL and Python/Amaranth | Host-language programs that construct hardware descriptions | [Software-to-hardware study](plan/research/hardware-export/01-software-to-hardware.md). That report explicitly marks these two characterizations as unverified analogies. |
| Verilog, SystemVerilog and VHDL | Circuit descriptions and hardware output formats | [Hardware-export programme](plan/research/hardware-export/README.md). No A7 hardware export is implemented or selected by this index. |

JAX, PyTorch and TensorFlow are framework inputs, not language decisions. The
[AI framework study](plan/research/ai-frameworks-codex.md) and
[autodiff transitions](plan/research/autodiff-transitions.md) track those ideas.
LLVM, MLIR, Cranelift and QBE are compiler infrastructure comparisons; see the
[IR programme](plan/research/ir/README.md) and
[runtime programme](plan/research/runtime-model/README.md).
The [SIMD/vector study](research/language-needs/17-simd-vectors.md) compares
Zig, Odin, Rust and Mojo vector interfaces. Vector widths, target portability
and reduction semantics still need A7-specific contracts and measurements.

## Maintaining this index

When another language or programming system informs A7 work, add its concrete
idea, a research/source link and its A7 disposition here. Link to detailed
reports instead of copying them. Mark a planned study as planned and preserve
corrections and version differences. Update the disposition when the decision
ledger changes; keep implementation progress in Status and the delivery roadmap.
