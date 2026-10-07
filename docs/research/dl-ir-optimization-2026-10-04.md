# Deep learning for typed compiler IR optimization

Research date: 2026-10-04. IR means compiler intermediate representation. The scope is learning to transform programs, including programs with many value types. Neural-network compilation is a related application, discussed separately below. The [technical companion](dl-ir-methods-and-encodings-2026-10-04.md) adds concrete encodings, architecture equations, search mechanisms, training objectives and worked examples.

Deep learning can predict optimization benefit, choose compiler passes, rank legal rewrites, or generate replacement IR. Transformers already have published results in these roles. My recommendation for A7 is to investigate a typed graph representation and a learned optimization policy while keeping program semantics and acceptance checks in compiler code. A graph transformer is a candidate to compare against simpler models, not an established winner for A7.

An instruction-focused model can keep literal strings and large constant payloads outside its input. The compiler retains exact data and supplies typed references or selected facts. The companion compares opaque constants, derived summaries, on-demand facts and selective payload encoders.

The representation question comes first. A model needs to distinguish program value types, relationships between instructions, exact constants, memory effects, hardware, and workload observations. Converting these into neural tensors is possible. Preserving enough information to justify a transformation is the harder problem.

This report combines a current source inspection with primary papers, author repositories, and official compiler documentation. Published results below are author-reported and were not reproduced. Proposed schemas and experiments are research recommendations, not approved A7 language changes or implementation commitments.

## What A7 currently gives an optimizer

The inspected working tree has HEAD `c8face6dc0fae59e00b59f22971c655e379d5862` plus extensive existing changes. The findings refer to that working tree, not the clean commit alone. Its pipeline is:

```text
A7 source
  -> tokenizer and parser
  -> name resolution and type checking
  -> semantic validation and safety proof planning
  -> AST preprocessing
  -> Zig source
  -> native compilation
```

The current implementation passes an AST, a node-to-type map, a symbol table, and an operation-specific `BackendPlan` into code generation. Inspection found no dedicated CFG or SSA optimization IR in `a7/`. A CFG records possible control-flow transfers. SSA gives each value definition a distinct identity. Both would be new infrastructure for A7. See [architecture](../ARCHITECTURE.md), `a7/compile.py:499`, `a7/compile.py:574`, and `a7/backends/zig.py:87`.

Existing input information includes the following:

| Family | A7 information available | Local evidence |
| --- | --- | --- |
| Scalars | Signed and unsigned integer widths, pointer-sized integers, `f32`, `f64`, `bool`, `char`, `string` | `a7/types.py:970` |
| Containers | Fixed arrays, parameterized array sizes, slices, nested element types | `a7/types.py:152` |
| References | Referent type and nullable references; an internal pointer type also exists | `a7/types.py:204` |
| Aggregates | Struct fields, enum variants, unions, type names and ordered fields | `a7/types.py:302` |
| Calls and generics | Parameter and return types, variadic metadata, type arguments, compile-time value arguments, type sets | `a7/types.py:252`, `a7/types.py:433` |
| Constants | Exact rational values, integer/float category, negative zero, destination fitting | `a7/exact_constants.py:1` |
| Analysis facts | Intervals, nonzero values, known lengths, nil state, initialization, moved state, discriminants | `a7/passes/safety.py:167` |
| Obligations | Bounds, division, casts, reference access, and other operation-specific approvals | `a7/passes/safety.py:213` |

An internal type class does not establish public syntax support. In particular, the reference syntax and its current limitations are described in the [safety contract](../SAFETY_CONTRACT.md). Tensor and device proposals in existing research notes must not be treated as implemented model inputs.

There is an immediate bookkeeping constraint. Types use `id(node)` keys, and backend approvals use pairs of node identity and operation. The preprocessor retains replaced nodes to prevent Python ID reuse. A serialized dataset therefore needs stable IDs. A proposed rewrite must trigger reanalysis or a justified transfer of facts; it cannot copy old approvals onto replacement nodes. See `a7/passes/type_checker.py:72`, `a7/passes/safety.py:243`, and `a7/ast_preprocessor.py:129`.

## What many data types means for model input

There are two separate questions. What types can the program manipulate? What kinds of evidence does the optimizer consume? A function that operates only on `i32` can still require control flow, alias information, branch frequencies, and a CPU description to optimize well.

LLVM IR has integer, floating-point, pointer, vector, array, and structure types, among others. Operation semantics also live in flags, attributes, predicates, and memory rules. An LLVM `i32` is not intrinsically signed or unsigned; `sdiv` and `udiv`, for example, interpret its bits differently. [LLVM language reference](https://llvm.org/docs/LangRef.html)

MLIR can retain higher-level operations and domain-specific types. Its operations connect typed values and can contain nested regions. The region's defining operation determines its semantics. This makes MLIR useful when shape, layout, tensor operations, or loop structure should remain explicit before lower-level compilation. [MLIR language reference](https://mlir.llvm.org/docs/LangRef/)

The following is a proposed input schema, not a claim that any cited model already implements every field:

| Input category | Exact compiler record | Possible learned encoding |
| --- | --- | --- |
| Operation | Opcode, dialect, result count, attributes | Categorical embeddings |
| Scalar type | Kind, width, source signedness where meaningful | Structured fields with shared embeddings |
| Composite type | Element types, ordered fields, dimensions with symbolic/unknown markers, layout | Type graph or type-description encoder |
| Constant | Integer bits, float bits, or exact rational components | Digit/byte embeddings plus numeric features |
| Value identity | Stable definition ID and operand references | Def-use edges and pointers to existing value records |
| Operand role | Position, result index, PHI predecessor pairing | Edge attributes |
| Control flow | Blocks, successor edges, branch conditions | Directed graph relationships |
| Memory and effects | Access type, reads/writes, address space, alignment, alias facts | Effect nodes and dependence edges |
| Hierarchy | Function, block, loop, region membership | Membership embeddings and hierarchical pooling |
| Analysis | Ranges, proven nonzero, dominance, loop information | Typed facts with provenance and validity scope |
| Target | CPU/GPU, instruction set, ABI, data layout, compiler version | Context embeddings and numerical fields |
| Workload | Input sizes, trip-count distributions, hotness | Numerical features and missing-data masks |
| Search history | Applied actions, measured outcomes, rejected proposals | Sequence encoder or state summary |

The source program's `f64` value does not need to become an `f64` neural activation. Its exact bits remain in the compiler record. A learned embedding can use lower-precision floating point for prediction. Similarly, a 64-bit integer constant should not be stored only as one approximate float feature, which can merge distinct integers. These are proposed representation rules for avoiding accidental information loss.

Nested types need compositional encoding. Giving every possible `array<length, element_type>` combination a separate vocabulary entry produces unseen combinations. Encoding the constructor, length, and child type separately allows reuse across combinations. A type graph also avoids expanding shared or cyclic reference structures without limit. A7's no-recursion implementation rule calls for worklists when traversing such structures.

For optional profiles, record whether a measurement exists. A missing branch count and a measured count of zero are different observations. Keep target-dependent sizes explicit, especially for A7 `usize` and `isize`. Test whether renaming local values changes predictions. Arbitrary names or numeric IDs should not become shortcuts for learning a transformation.

### A concrete instruction example

```llvm
%n = load i32, ptr %p, align 4
%twice = mul i32 %n, 2
```

A text model sees tokens. A structured model can separately receive `load`, the result type `i32`, pointer operand `%p`, alignment `4`, the constant `2`, and the edge connecting `%n` to the multiply.

Modern LLVM's opaque `ptr` does not specify a pointee type. Here the access type belongs to the load. A graph builder that looks only at `%p` cannot recover it. Accessed types and GEP source element types need their own fields. [LLVM opaque pointers](https://llvm.org/docs/OpaquePointers.html)

For these unflagged integer operations, replacing the multiply with a left shift by one is a possible candidate. Whether it improves machine code requires measurement. The compiler may already make the same change. The example illustrates representation and candidate selection, not a demonstrated optimization gain.

## How a transformer can consume the representation

A transformer operates on vectors. Text tokenization is one way to create them; it is not a requirement that all inputs start as prose. Attention lets each representation combine information from other positions. [Attention Is All You Need](https://arxiv.org/abs/1706.03762)

For an IR experiment, I would compare the following architectures on the same task and data:

| Architecture | Input and output | Useful role | Main concern to test |
| --- | --- | --- | --- |
| Feature model, such as a small MLP | Counts and target fields to scores/actions | Cheap pass or inlining decisions | Cannot distinguish programs with identical summaries |
| IR2Vec plus prediction head | Compact program embeddings to scores | Low-cost representation baseline | Compression does not preserve a reconstructable program |
| Relational GNN | Typed nodes and edges to node/graph scores | Local rewrite selection, dependence-sensitive ranking | Long-range information requires sufficient propagation |
| Text transformer | Serialized IR to actions or IR text | Pretrained model reuse and candidate generation | Long context, arbitrary naming, exact references |
| Graph transformer | Typed nodes plus relation-aware attention | Combining distant dependencies with explicit structure | Dense attention cost and training-data needs |
| Graph encoder plus text decoder | Structural representations condition generation | Constrained edits or replacement regions | Extra complexity must beat simpler baselines |
| Hierarchical model | Instructions to blocks to functions | Large functions and modules | Summaries may hide decisive effects |

IR2Vec learns representations of LLVM entities and combines them into symbolic or flow-aware program embeddings. Its original evaluations include device mapping and thread coarsening. LLVM now documents an IR2Vec integration, including the need to refresh embeddings after program changes. That documentation does not prove availability in A7's installed toolchain. [IR2Vec paper](https://arxiv.org/abs/1909.06228), [LLVM integration](https://llvm.org/docs/MLGO.html#ir2vec)

ProGraML makes control, data, and call dependencies explicit. Its learned data-flow tasks provide a way to test whether an encoder captures useful program relations before asking it to optimize anything. Its published extractor support is version-specific; the repository lists LLVM 3.8, 6.0, and 10.0. Modern opaque-pointer IR needs a compatibility check. [ProGraML paper](https://proceedings.mlr.press/v139/cummins21a.html), [repository](https://github.com/ChrisCummins/ProGraML)

PERFOGRAPH directly addresses the user's type-rich input concern. It extends a ProGraML-derived representation with aggregate structure and numerical information, including digit/position embeddings, and uses heterogeneous graph processing. Its results concern selected prediction and analysis tasks. They do not establish verified arbitrary IR rewriting. [PERFOGRAPH paper](https://proceedings.neurips.cc/paper_files/paper/2023/file/b41907dd4df5c60f86216b73fe0c7465-Paper-Conference.pdf)

GraphCodeBERT combines code tokens with data-flow information through graph-guided attention. Its evaluations cover code understanding and transformation tasks, rather than proving a compiler optimization correct. Heterogeneous Graph Transformer supplies type-dependent attention mechanisms, while Graphormer shows how structural encodings help transformer graph models. Their broader graph results motivate experiments; they do not select an A7 architecture for us. [GraphCodeBERT](https://arxiv.org/abs/2009.08366), [HGT](https://arxiv.org/abs/2003.01332), [Graphormer](https://arxiv.org/abs/2106.05234)

### A proposed combined encoder

The proposal below combines those ideas. It has not been trained or benchmarked.

```text
Exact typed IR, owned by the compiler
    |
    +-- instruction/type/constant encoders --+
    +-- control/data/memory/call edges -------+--> structural encoder
    +-- optional IR text encoder ------------+          |
                                                       v
Target + workload + optimization objective ------> fused representation
                                                       |
                                    +------------------+----------------+
                                    |                                   |
                              candidate scores                    edit/action decoder
                                    |                                   |
                                    +----------> independent checks <---+
                                                       |
                                              measure or reject
```

One possible node representation concatenates opcode, type, constant, attribute, and context embeddings, then projects them to a shared dimension. Attention can add learned biases for edge kind, direction, operand position, and block membership. This gives related instructions a structural connection without expecting token adjacency to encode every dependency.

For large inputs, compare sparse edge attention and block/function summaries against full attention. Standard dense attention has quadratic pair interactions in sequence length. A flat stream with 10,000 instruction records already has 100 million position pairs per attention head before token expansion. That arithmetic explains why function boundaries and region selection matter.

A pointer-style output mechanism could choose existing SSA values by ID, while a constrained decoder chooses only operators and operands permitted by the current type environment. These constraints can prevent undefined references and type mismatches. They still do not prove that a rewrite preserves values, effects, or termination.

PRISM, published for MLCAD 2026 and posted to arXiv on September 29, provides a recent related example. Separate AST, CFG, and DFG encoders feed a code LLM through gated cross-attention. It targets HLS pragma generation, not general LLVM rewriting. Its reported 26.9% synthesis success rate versus 7.7% for Llama3-8B also shows how much failure remains despite structural input. [PRISM](https://arxiv.org/html/2609.38601v1)

## What the model should produce

Different output contracts require different evidence. Reinforcement learning is a training strategy that can train several architectures; it is not a separate IR representation.

| Output | Transformation mechanism | Acceptance requirement |
| --- | --- | --- |
| Profitability score | Existing compiler performs a chosen legal transformation | Compiler legality checks plus measured objective |
| Pass sequence | Compiler applies named passes in order | Supported pipeline, validation, regression comparison |
| Rule and location | Compiler applies a predefined rewrite | Rule preconditions and correct matching |
| Schedule | Compiler changes tiling, fusion, layout, vectorization, or placement | Dependency, shape, resource, and effect checks |
| Replacement IR | Model constructs new instructions and control flow | Structural verification and semantic validation |
| Optimizer implementation patch | An agent edits compiler source | Human/code review and compiler change verification |

MLGO is the clearest existing integration precedent for learned profitability decisions. Its original inlining work reports up to 7% size reduction over `-Oz`. LLVM's current documentation includes inlining and register-eviction interfaces that retain compiler constraints around the learned decision. The percentage is an upper result in that study, not an expected A7 gain. [MLGO paper](https://arxiv.org/abs/2101.04808), [LLVM MLGO](https://llvm.org/docs/MLGO.html)

An alternative is equality saturation. A compiler records multiple equivalent expressions using supplied rewrite rules, then extracts a preferred expression using a cost model. Learning can guide rule scheduling or extraction. Correctness still depends on each rule's semantics and preconditions. Integer algebra cannot silently justify floating-point reassociation. [egg documentation](https://egraphs-good.github.io/egg/egg/)

For A7, my preferred first learned output is a score or ranking over compiler-checked candidates. Direct generation is a useful later research comparison once a bounded transformation domain and its checker exist.

## Evidence from transformer and learning systems

These studies answer different questions. Percentages across rows are not comparable without their metric, baseline, corpus, and search cost.

| Work | Model input and task | Author-reported result | What the result establishes |
| --- | --- | --- | --- |
| [LLMs for compiler optimization, 2023](https://arxiv.org/html/2309.07062v1) | 7B transformer; normalized LLVM 10 IR to pass lists | 3.01% aggregate IR instruction reduction over `-Oz`, 3.52% with baseline backup | Evidence for pass selection. Generated IR is an auxiliary training task; deployment executes compiler passes. |
| [Meta LLM Compiler, 2024](https://arxiv.org/html/2407.02524v1) | IR/assembly pretraining; 7B/13B models; IR to pass lists | 13B reduces MiBench binary size by 4.88% over `-Oz`, or 5.26% with backup, across 2,398 objects | Binary-size evidence. Does not establish faster execution or universally correct generated IR. |
| [Compiler-generated feedback, 2024](https://arxiv.org/html/2403.14714v1) | Pass prediction with compiler feedback | Improvement over `-Oz` rises from 2.87% to 3.40%; ordinary sampling wins at at least 10 samples | More elaborate feedback is not automatically the best use of a search budget. |
| [CompilerDream, KDD 2025 version](https://arxiv.org/html/2404.16077v3) | Model-based RL using 56 AutoPhase features and action history | cBench baseline/result instruction-count ratio 1.068x with 2.9 seconds inference | A non-LLM baseline. This autotuning result includes training on evaluated programs; separate generalization experiments must be considered separately. |
| [Compiler-R1, 2025](https://arxiv.org/html/2506.15701v1) | Qwen plus supervised training and RL; default input is 56 features and initial count | Mean 8.46% instruction reduction over LLVM 10 `-Oz` across seven datasets; 26 seconds per program | Compact observations can guide pass search. Its 96.71% success metric measures interaction protocol, not semantic correctness. |
| [LLM-VeriOpt, CGO 2026](https://samainsworth.github.io/LLM-VeriOpt-CGO2026.pdf) | Qwen-3B; LLVM text to peephole rewrites; Alive2-guided RL | About 90% different verified outputs; 2.30x estimated latency improvement over `-O0`, versus 2.39x for InstCombine; lower estimated latency than InstCombine in 20.1% of cases | Direct rewriting is feasible in a filtered, checked setting. Latency is the sum of LLVM AArch64 cost estimates, not measured application runtime. |
| [IntOpt, February 2026](https://arxiv.org/html/2602.18511v1) | LLM proposes intent, compiler analyses inform refinement, then LLM emits IR | Of 200 programs, 71% pass Alive2 and another 19.5% pass differential tests. Against LLVM 19.1 `-O3`: 37 wins, 105 within 2%, 58 losses including 19 incorrect outputs | Planning and analysis context are useful research ideas. The 90.5% combined figure is not a formal-proof rate. |
| [Verified learning for compiler optimization, September 2026](https://arxiv.org/html/2609.27214v1) | Wyvern lazification pairs train an LLM; Alive2 checks proposals | 9.8% of benchmarks match or improve on Wyvern runtime; Wyvern is faster on most | Recent preliminary evidence for a validation workflow, with weak evidence of performance superiority. |

The 2023 pass-selection paper normalizes away comments, debug metadata, and attributes. That preprocessing choice is inappropriate as a blanket recipe for a lossless rewriting representation. A profitability policy can use an incomplete observation because the compiler retains the full program. A replacement generator still needs its output checked against the original semantics. [2023 paper, normalization section](https://arxiv.org/html/2309.07062v1)

Meta's 2024 work used 546 billion foundation-training tokens plus downstream training. It also reports rejecting 9.85% of unique candidate pipelines during training filtering for compilation or execution failures. Its scale is evidence against assuming a small new language needs to reproduce foundation training, and its failures show why pass execution still needs validation. [Meta LLM Compiler](https://arxiv.org/html/2407.02524v1)

Compiler-R1's raw-IR experiment is an ablation. The main model's summarized inputs are especially relevant here: a model does not always need every type and instruction to select a useful action. This depends on the output contract. It does not mean 56 statistics are sufficient to reconstruct or prove a program. [Compiler-R1](https://arxiv.org/html/2506.15701v1)

IntOpt evaluates a filtered corpus suitable for baseline Alive2 checking and differential testing, with IR sample pairs capped at 5,000 tokens. Its own appendix qualifies a bit-reversal rewrite whose behavior differs on negative inputs unless an extra caller precondition holds. The transformation must respect the input domain and termination behavior. [IntOpt evaluation and appendix H](https://arxiv.org/html/2602.18511v1)

## Training data and learning objectives

Large amounts of IR exist. Profitable, semantically validated transformation examples with trustworthy measurements are a more specific dataset requirement.

| Resource | Available evidence | Suitable research use |
| --- | --- | --- |
| [ComPile](https://llvm-ml.github.io/ComPile/) | LLVM IR from Rust, Swift, Julia, C/C++; public corpus is 1.9 TB text and 144 billion tokens with a 10,000-token vocabulary | IR pretraining and representation study. It does not automatically provide speedup or equivalence labels. |
| [CompilerGym LLVM datasets](https://compilergym.com/llvm/index.html#datasets) | AnghaBench v1 has 1,041,333 compile-only functions; CBench v1 has 23 runnable benchmarks and partial validation support; POJ104 v1 has 49,816 solutions and is listed as non-validatable | Pass-search environments and baselines. Compilation alone does not establish output correctness. |
| [ProGraML analysis tasks](https://proceedings.mlr.press/v139/cummins21a.html) | Compiler-derived labels for data-flow analysis | Auxiliary training and tests of structural reasoning. |
| A7 working tree | Existing examples, tests, semantic rules, and compiler transformations | Domain adaptation and edge cases after auditing provenance and behavior. No training-size sufficiency is claimed. |

ComPile's often repeated 182-billion-token figure refers to the larger closed corpus. Its public count falls to 94 billion with a 50,000-token vocabulary. The project describes filtering for MIT, Apache-2.0, BSD-3-Clause, and BSD-2-Clause and distributing provenance/license text. Preserve those records when constructing derived datasets. [ComPile dataset description](https://llvm-ml.github.io/ComPile/)

My proposed transformation record would contain:

```text
program origin, source license, source/compiler revisions
IR schema version, dialect, target, build profile
exact before IR and candidate action
exact after IR
structural verification result
semantic checker result, supported scope, settings, diagnostics
baseline and candidate measurements, workload, repetitions
compile time, model time, checking time, measurement time
accepted/rejected reason and no-change baseline
```

Keep several kinds of outcomes. Valid improvements teach profitability. Valid regressions teach when to abstain. Invalid proposals teach failure boundaries. Unsupported verification and checker timeouts need separate labels, because neither establishes equivalence or inequivalence.

Possible objectives, all proposed for experimentation:

- Pretrain on IR tokens, type relationships, def-use links, and compiler-derived analysis labels.
- Train a cost model to rank valid alternatives under the same target and workload.
- Imitate useful pass or rewrite sequences obtained through search.
- Train an edit decoder on verified before/after pairs, retaining no-change examples.
- Use RL to explore sequences whose benefit appears only after later actions.

A simple profitability reward could use `log(baseline_runtime / candidate_runtime)` minus optimization overhead and size penalties. Correctness should be a hard acceptance condition outside this scalar reward. A high speed reward must never compensate for an invalid transformation. Treat this formula as a proposed objective, not a reproduced result from the cited studies.

Split datasets by original repository or program family before generating optimization variants. Otherwise, alternate versions of one function can appear in training and test sets. Hold out compiler versions, targets, large functions, and rare type combinations to test transfer. Include exact-constant boundary cases, unusual widths, nested aggregates, aliasing, and missing profiles.

For A7, begin with pretrained representations or small models. Foundation-scale training is hard to justify before proving that the selected optimization opportunity survives the existing Zig backend and improves real workloads. No GPU memory, training duration, or cost estimate is offered without a chosen model, context length, dataset, and measurement.

## Correctness requirements for generated IR

Type checking only establishes some structural obligations. It cannot establish arbitrary semantic equivalence.

Consider these illustrative counterexamples:

| Candidate simplification | Why it can be wrong |
| --- | --- |
| Replace `x + 1 > x` with true | An 8-bit wrapping unsigned value at 255 becomes 0 |
| Replace floating-point `x / x` with 1 | Zero, infinity, and NaN violate the identity |
| Reuse a load across a store | An alias may point to the same location |
| Move a division outside its guarded branch | The divisor may be zero on previously unevaluated paths |
| Treat a compile-time A7 expression like runtime arithmetic | A7 exact constants defer fitting; runtime integer arithmetic wraps |
| Copy safety approval to a replacement node | A7 approvals identify a particular node and operation |

LLVM flags such as `nsw`, `nuw`, and fast-math flags alter the legal transformation space. Poison, undefined behavior, and `freeze` also matter. A model must not invent stronger assumptions merely because they enable faster code. [LLVM language reference](https://llvm.org/docs/LangRef.html)

A7's exact constants use rational arithmetic until destination materialization. Runtime integer wrapping and checked shift counts follow a different contract. The compiler also names current alias, lifetime, discriminant, and ownership gaps. Existing safety analysis is therefore not a general equivalence checker for neural rewrites. [Exact constants implementation](../../a7/exact_constants.py), [A7 safety contract](../SAFETY_CONTRACT.md)

Alive2 checks LLVM refinement using symbolic execution and an SMT solver. Refinement requires the transformed program to stay within the behavior allowed by the original. Its PLDI paper describes bounded loop reasoning and explicitly notes that bounds can miss bugs. Its repository excludes interprocedural transformations. A successful result must retain the checker's supported domain and settings. [Alive2 paper](https://users.cs.utah.edu/~regehr/alive2-pldi21.pdf), [Alive2 repository](https://github.com/AliveToolkit/alive2)

For a proposed A7 experiment, I recommend this acceptance sequence:

1. Decode the candidate without changing the authoritative program.
2. Verify structure, types, references, dominance where applicable, and operation constraints.
3. Recompute affected analyses and reject unsupported semantic assumptions.
4. Check the transformation with an appropriate validator for the restricted domain.
5. Retain proof, bounded validation, differential testing, and unsupported results as distinct evidence classes.
6. Measure accepted candidates against the unchanged baseline and retain the preferred artifact.

If the experiment promises formally checked rewrites, timeout or unsupported results must preserve the original program. A learned prediction that the checker would probably succeed cannot replace the check.

LLVM-level validation also does not prove that A7-to-Zig or Zig-to-LLVM lowering preserves A7 semantics. Those translation boundaries remain separate obligations. A7 currently exposes Zig generation, not a ready LLVM optimization plugin interface.

## Measuring whether optimization actually helps

Instruction count, binary size, estimated latency, and measured runtime answer different questions. Fewer IR instructions can still produce slower machine code. Vectorization and unrolling can increase IR size while reducing execution time.

A June 2026 study examines 113 cumulative LLVM `-O3` prefixes over 30 PolyBench/C kernels on one Intel Alder Lake host. It reports negative within-kernel correlation between instruction count and runtime for 27 kernels. Its scope is regular, single-threaded affine kernels, so the result motivates direct measurement rather than a universal numerical prediction. [Per-pass LLVM study](https://arxiv.org/html/2606.31238v1)

My proposed evaluation records the following separately:

| Question | Measurement |
| --- | --- |
| Does it preserve behavior? | Checker outcomes, counterexamples, output tests, excluded cases |
| Does execution improve? | Repeated runtime measurements on declared hardware and inputs |
| Does size improve? | Object and final executable sections under a declared linking configuration |
| Is compilation affordable? | Feature extraction, inference, compiler, checker, and search costs |
| Does it generalize? | Held-out projects, types, sizes, compiler versions, and targets |
| Does it regress? | Per-program regressions and unchanged-baseline selections |
| Is it reproducible? | Versions, artifacts, model/decoder settings, seeds, and raw measurements |

Compare against the actual A7 Zig baseline, an ordinary compiler optimization baseline, random search, and a simpler learned model under matched budgets. Compare text-only, feature-only, graph-only, and combined models. Ablate types, constants, memory edges, and target context to find which information earns its extraction and inference cost.

Report geometric mean runtime ratios alongside the distribution and worst regressions. Specify how invalid and unchanged outputs enter the denominator. Repeated measurements, randomized execution order, and uncertainty estimates are necessary when improvements are close to machine noise. Search should use training/tuning inputs; final runtime evaluation needs held-out inputs.

Optimization overhead also has a break-even point. If a proposed run adds 10 seconds of compile/inference/checking cost and saves 1 millisecond per execution, it needs more than 10,000 executions to repay that time. These numbers are an illustration, not a measurement. Offline optimization may suit frequently executed kernels even when interactive compilation does not.

## Related work on tensor and neural-network programs

A compiler can optimize a neural network using ordinary algorithms. Separately, a learned model can optimize any suitable program. Some systems combine both.

Halide's learned autoscheduler uses a neural cost model and tree search to choose schedules for image-processing and deep-learning programs. This is a useful precedent for keeping a program's meaning separate from choices about how to execute it. [Halide autoscheduler](https://halide-lang.org/papers/halide_autoscheduler_2019.pdf)

Learning to Optimize Tensor Programs and Ansor study learned cost guidance and search over tensor implementations. Their relevance here is the design of legal candidate spaces and hardware-specific measurement. Neither establishes that a general transformer is required for optimization. [Learning to Optimize Tensor Programs](https://arxiv.org/abs/1805.08166), [Ansor](https://arxiv.org/abs/2006.06762)

MLIR's Transform dialect provides a language for expressing transformations separately from the program being transformed. A model could propose such a schedule while compiler machinery applies it. This is an architectural option, not evidence that A7 should adopt MLIR or that generated schedules are automatically correct. [Transform dialect](https://mlir.llvm.org/docs/Dialects/Transform/)

If A7 later has tensor operations, useful inputs would include dtype, symbolic dimensions, strides, layout, device, aliasing, and precision policy. Lowering everything to scalar loads and arithmetic too early can hide those optimization opportunities. This is a design inference for future work; it does not change the current tensor implementation status.

## Research choices for A7

The following are experiment designs, not additions to the delivery roadmap.

| Experiment | What it would answer | Evidence needed before expanding scope |
| --- | --- | --- |
| Read-only typed AST export | Can existing semantic data be serialized without losing identity, constants, or type structure? | Stable IDs, documented schema, faithful inspection of sampled records |
| Representation comparison | Do explicit types and graph relations help a selected prediction task? | Held-out results against compact feature and text baselines |
| Ranking checked candidates | Does a learned policy find useful choices cheaply? | Correct candidates, real objective measurements, matched search budgets |
| Restricted typed IR rewriting | Can a model propose useful new local transformations? | A defined semantic subset and independently checked accepted rewrites |
| Larger regions and memory | Does added scope justify verification and inference cost? | Alias/effect handling, loop qualifications, cross-workload performance |

An existing language implementation can support some prediction experiments without a new SSA IR. Free-form transformations need a stronger representation and validation boundary. For A7, any new compiler traversals must use explicit stacks or worklists under the repository's no-recursion rule.

The central open empirical question is whether the learned system finds improvements that the current Zig toolchain leaves available. Until that is measured, a type-rich graph transformer is a research hypothesis. The first useful outcome would be a reproducible dataset and an honest comparison showing when richer inputs improve decisions enough to repay their cost.

## Evidence and verification limits

The research covered representation, architectures, learned compiler decisions, direct rewriting, datasets, formal validation, tensor scheduling, and A7 integration constraints. It includes primary material posted through September 2026. It is a targeted literature review, not a claim to enumerate every paper.

Three independent subagents investigated A7's current inputs, optimization papers, and graph/type/dataset representations. The parent checked local implementation passages and primary sources for the central claims. No model was trained, no benchmark result was reproduced, and no A7 compiler behavior was changed. Toolchain extraction compatibility and model licensing for a chosen deployment remain to be checked when selecting an actual experiment.

The report passed the repository style checker applied directly to this file, local Markdown-link existence checks, and a whitespace check. Compiler tests and release gates were not run for this research-only document. The combined PDF was rendered and visually inspected.
