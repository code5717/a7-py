# Neural IR optimization methods and input encodings

Research date: 2026-10-04. This technical companion extends the [research overview](dl-ir-optimization-2026-10-04.md). It explains how heterogeneous compiler information becomes tensors, how different models process it, and how their outputs cause transformations. It then compares search, training, validation, and deployment choices.

There are several credible designs. A small policy can choose an existing compiler action. A graph network can select a region and rewrite rule. A transformer can rank schedules or generate replacement instructions. A model can also guide a symbolic synthesizer or generate a reusable optimization strategy offline. These approaches differ in their output authority, required data, and failure modes.

The worked schemas, equations marked as adaptations, and experiment designs below are proposals or explanations. They are not implemented A7 interfaces. Published mechanisms have direct primary-source links. Reported experiments remain the authors' results; this research did not train a model or reproduce their benchmarks.

## Choose the IR level before choosing the architecture

An optimizer's representation determines which decisions are visible. The following is a design comparison, not a prescribed lowering pipeline for A7:

| Level | Information available | Decisions worth studying | Information easily lost on lowering |
| --- | --- | --- | --- |
| Typed source AST | Source types, constructs, generic parameters, source locations | Specialization and source-aware simplification | Original intent, nominal types, exact compile-time expressions |
| Structured tensor or loop IR | Shapes, regions, access functions, reductions, layouts | Fusion, tiling, layout, placement | Tensor identities and multidimensional access structure |
| CFG and SSA IR | Value definitions, branches, calls, low-level operations | Inlining, local rewrites, control-flow simplification | High-level array and ownership structure |
| Machine IR | Target instructions, virtual registers, live ranges | Instruction selection, scheduling, register allocation | Portable operation structure |
| Assembly | Concrete instructions and register choices | Peephole superoptimization, throughput estimation | Many source-level contracts |

One model need not operate at every level. A proposed hierarchy might choose fusion at tensor IR, rank scalar rewrites at SSA IR, and use a separate machine-level predictor for final cost. Each transition needs a record connecting the original region to its lowered version. Otherwise, a score at one level may be attached to the wrong candidate at another.

TensorIR is an example of an IR designed to retain tensor computation information for scheduling and hardware tensorization. It is not itself a neural model. [TensorIR paper](https://arxiv.org/abs/2207.04296)

For A7, the inspected pipeline is a typed AST plus analysis tables followed by Zig emission. A new LLVM or tensor-IR experiment would require a separately defined extraction/lowering boundary. The current-state evidence and file locations are in the [overview's A7 section](dl-ir-optimization-2026-10-04.md#what-a7-currently-gives-an-optimizer).

## Turn heterogeneous records into model inputs

### Separate program types from tensor storage types

Suppose the program contains an `i64` counter, a nullable reference to a struct, a string, and an array of `f32`. The model usually reads descriptions of those values and their uses. It does not receive every byte of the runtime array or simulate every possible counter value. Runtime samples, shapes, or traces are optional extra observations whose coverage must be stated.

There are three distinct layers:

1. The compiler retains exact semantic records, including types, constants, identities, and attributes.
2. An extractor converts selected records into arrays of category IDs, indices, numerical measurements, and masks.
3. Neural encoders map those arrays to fixed-width floating-point vectors for prediction.

An `f64` program constant and an `f32` neural activation are different objects. The model can use approximate activations while the compiler retains the constant's exact representation. Never recover an arbitrary exact integer by rounding its learned embedding.

LLVM MLGO provides a concrete existing interface. Named inputs have a scalar type and shape through `TensorSpec`. Supported scalar storage types include signed/unsigned integers of several widths, float, and double. Compiler code fills buffers, invokes a model, and consumes a decision. This is a practical answer to how one model can accept several kinds of input. [MLGO model interface](https://llvm.org/docs/MLGO.html#interacting-with-ml-models)

### A proposed tensor schema

Let `N` be the number of graph nodes, `E` the number of edges, and `K` the number of optional numerical features. These dimensions vary by program. The following is a proposed schema:

```text
node_kind[N]                   categorical integer IDs
opcode[N]                      categorical IDs or absent marker
type_ref[N]                    indices into an exact type table
constant_ref[N]                indices into an exact constant table
numeric_features[N, K]         scaled numerical quantities
numeric_present[N, K]          availability masks
edge_index[2, E]               source and destination node indices
edge_kind[E]                   data, control, memory, call, type, ...
edge_operand_position[E]       ordered operand slot or absent marker
edge_result_position[E]        result slot or absent marker
node_to_block[N]
node_to_function[N]
node_to_program[N]
```

An opcode ID indexes an embedding table. It has no arithmetic meaning. Node indices preserve references; adjacent indices do not imply similar semantics. Branch frequency and memory size are numerical quantities. Their normalization should fit the training split only, with missingness preserved.

Multi-result operations need separate result identities. A useful graph construction has operation nodes and value nodes, with edges for producing and consuming values. This handles instructions with multiple inputs and outputs without pretending every operation is a simple binary edge.

For sparse batching, concatenate graphs and offset their indices. For global attention, mask cross-program pairs. Without that mask, a prediction can depend on unrelated programs placed in the same minibatch. Padding also needs masks, so an absent operand is not learned as a real zero-valued operand.

### Encode composite types without an enormous vocabulary

For the nested array type `[2 x [3 x [4 x float]]]`, a possible type table is:

```text
T0 = float(format=binary32)
T1 = array(length=4, element=T0)
T2 = array(length=3, element=T1)
T3 = array(length=2, element=T2)
```

This shares the array constructor across sizes and element types. An encoder can combine constructor, dimension, and child-type embeddings. Structs need ordered field edges. Function types need ordered parameter edges and result types. Nominal identity must remain separate from structural similarity where the source language distinguishes named types.

Unknown and symbolic dimensions need explicit markers. Zero is a valid dimension in some representations and cannot mean unknown. Target-dependent layout, packing, alignment, and address spaces need fields when they affect the chosen task.

For recursive reference structures, store a finite graph of type identities. Do not expand references indefinitely into a tree. A7's implementation rule requires explicit stacks or worklists for construction and traversal. Fixed rounds of graph message passing can encode a cyclic type graph without recursive Python calls.

PERFOGRAPH supplies a relevant published precedent for preserving aggregate structure and numerical values instead of relying only on normalized instruction text. Its graph representation and heterogeneous processing improve selected analysis and optimization-prediction tasks. They do not prove arbitrary transformations correct. [PERFOGRAPH](https://proceedings.neurips.cc/paper_files/paper/2023/file/b41907dd4df5c60f86216b73fe0c7465-Paper-Conference.pdf)

### Give constants an exact record and a learned view

The proposed exact record distinguishes fixed-width bit patterns, arbitrary-precision integers, floating-point formats, and compile-time rational values. A7's exact rational constants must retain numerator, denominator, and category until fitting. Floating-point records must preserve the distinctions required by the language, including negative zero.

A proposed learned view can combine byte/digit embeddings with indicators such as zero, one, power of two, sign, and magnitude bucket. These help a model recognize useful patterns. They are not an arithmetic engine. The compiler or a solver should compute exact folded constants and validate range conditions.

This separation also makes a decoder safer to design. It can select an existing constant record, ask a deterministic evaluator for `5 + 7`, or emit exact bytes. It should not invent the result from a scalar floating-point regression head.

### Preserve control, memory, and effects separately

A def-use edge says where a value came from. It does not describe every dependency between memory operations. For example:

```text
v0 = load(p)
store(q, 9)
v1 = load(p)
```

Whether `v1` can reuse `v0` depends on aliasing, volatility, concurrency semantics, and intervening effects. Two pointer names do not prove two disjoint locations.

LLVM MemorySSA represents memory uses, definitions, and joins. A memory definition can describe a modification or ordering constraint; alias analysis helps identify relevant clobbers. This is useful evidence for a model, but its graph edges must retain their meaning as conservative analysis results. They are not a complete trace of actual memory contents. [MemorySSA](https://llvm.org/docs/MemorySSA.html)

Operation purity and safe speculation are also different questions. An operation without a memory write can still trap, invoke undefined behavior, or fail to terminate on some inputs. MLIR exposes memory effects and conditional speculatability separately. Hoisting an operation needs the applicable conditions, not a generic learned label saying it looks pure. [MLIR effects and speculation](https://mlir.llvm.org/docs/Rationale/SideEffectsAndSpeculation/)

PHI inputs need value/predecessor pairs. LLVM treats their uses on predecessor edges, which differs from an ordinary use in the destination block. Modern opaque pointers need the accessed type on operations such as loads, rather than an invented universal pointee type. [LLVM PHI semantics](https://llvm.org/docs/LangRef.html#phi-instruction), [opaque pointers](https://llvm.org/docs/OpaquePointers.html)

## Instruction-focused input with constants kept outside the model

The user's proposed separation is a useful architecture to test. Feed the model operations, typed operand references and dependencies. Keep string bytes, large constant arrays and other exact payloads in a compiler-owned table. Expose selected properties only when they help the chosen optimization. This section is a proposed design, not a claim that a published system implements this exact interface.

### Three views of the same program

| View | Contents | Owner and purpose |
| --- | --- | --- |
| Exact program | Instructions, exact constants, globals, types, flags and relationships | Compiler and validator retain the authoritative program |
| Neural input | Instruction graph, typed references, permitted summaries, target and workload features | Model ranks actions or proposes edits |
| Action record | Region identity, rule or edit, references to retained values, required conditions | Compiler resolves references and checks the transformation |

The neural input is intentionally incomplete. The model's decision does not need every byte of the program if another component checks the decision against the complete program. This can reduce sequence length and irrelevant vocabulary. Its effect on prediction quality and inference cost still needs measurement.

For example, use this illustrative representation for a length-carrying byte string:

```text
Compiler-only payload table:
  C17 = bytes("request accepted")

Model-visible records:
  V4  = const_ref(C17)
  type(V4) = immutable_byte_string
  byte_length(V4) = 16
  I8  = call(output_function, V4)
```

The model does not receive the words "request accepted". It sees that the call consumes a constant string, with any selected size and effect information. The call's side effects remain in the graph; hiding its argument bytes does not make the call removable or reorderable.

`C17` is a reference resolved by the compiler, not a numeric quantity to embed as magnitude. Its digits have no optimization meaning. References must bind to an immutable or versioned program snapshot. Recompute dependent summaries after edits, and resolve original and replacement references against their exact records during validation. A pointer head can select its local constant node. Randomizing local record IDs should preserve predictions after correspondingly remapping the selected action.

### Omit payload bytes, retain operand relationships

An opcode-only list loses too much information for many transformations. These programs contain the same opcode but compute different functions:

```text
add(x, x)
add(x, y)
```

Retain value identity, repeated uses, operand order, types, control flow and relevant effects. A runtime SSA value already has no generally known runtime contents to feed the model. The model sees its definition and known properties. Separating payloads concerns known constants and data objects; it does not mean deleting all value nodes.

Likewise, two equal string contents need not designate the same storage object. Content equality and address identity are different relations. LLVM's global-variable rules distinguish whether an object's address is significant through attributes such as `unnamed_addr`. A compiler must apply the relevant language and IR rules before merging objects. [LLVM global variables](https://llvm.org/docs/LangRef.html#global-variables)

### Choose constant features for the decision

| Optimization | Potentially sufficient model input | Work that stays with the compiler |
| --- | --- | --- |
| Schedule independent operations | Dependencies, effects, estimated instruction costs | Prove motion preserves behavior |
| Rank inlining choices | Call graph, body size, profile, constant-argument flags | Substitute exact arguments and simplify |
| Fold known string length | Known length and representation contract | Compute the correct length from the exact object |
| Simplify string equality | Compiler-established equality or inequality fact | Compare exact contents under the correct semantics |
| Combine arithmetic constants | Width, flags, selected numeric properties | Perform exact arithmetic and check conditions |
| Select target immediates | Encodability or cost facts for this instruction and target | Check actual bit patterns and instruction constraints |
| Optimize a constant lookup table | Shape, element type, selected structural properties | Inspect exact entries when the transformation requires them |

These summaries are options, not universally sufficient feature sets. A string's byte length, character count and C-style length before the first NUL can differ. Folding must follow the operation's contract. A string comparison's runtime can depend on where contents first differ, so length alone may be a poor performance feature even when it is enough for another decision.

Other content-sensitive examples include format-string analysis, compile-time parsing, constant hashing and table specialization. Such work can run deterministically before model inference. The model can receive its result instead of the raw string. MLIR's folding interfaces provide an existing compiler mechanism for constant evaluation; that mechanism is separate from a learned policy. [MLIR folding interfaces](https://mlir.llvm.org/docs/Interfaces/#dialectfoldinterface)

### Four input policies worth comparing

1. Keep all payloads opaque. Include type and operand identity, but no content-derived features.
2. Add compiler-derived summaries such as exact length, zero/nonzero, alignment, known bits, or immediate-encoding cost.
3. Allow bounded requests for named facts, such as whether two constants are equal. Charge extraction and query time to the optimizer budget.
4. Encode selected payloads when a content-sensitive task benefits from them. Use a separate encoder rather than appending every byte to the instruction sequence.

My starting preference is the second policy for ordinary instruction optimization. Add the fourth only when experiments identify a missing useful signal. A request for more facts should invoke deterministic compiler analysis, not allow the model to assert an unverified fact.

For an action such as `fold_length(V4)`, the evaluator obtains the exact constant from the table and creates a correctly typed replacement. For `combine_constants(add, C5, C7)`, it performs exact arithmetic under the operation's semantics. The decoder need not generate either the original string or the resulting number.

### Information loss has a measurable consequence

Suppose `mul(x, C1)` and `mul(x, C2)` have identical model-visible records, but the hidden constants are 8 and 7. Their useful target transformations may differ. The model cannot distinguish those cases without another feature or query. It can still propose candidates for the compiler to check, but its ranking may suffer.

This is an information limit, not a training failure. More parameters cannot recover a deliberately hidden distinction from otherwise identical inputs. Include facts such as power-of-two status when they matter, or let a deterministic candidate generator expose different legal actions for the two cases.

A cryptographic hash does not give the model useful numerical structure. It can encourage memorization and does not establish equality without exact comparison. Use exact compiler-established equality classes where needed, and keep caches scoped to the actual payloads, semantic flags and compiler version. Do not reuse a previously validated edit merely because two neural inputs look the same.

The proposed evaluation should compare all four policies with identical actions, datasets and measurement budgets. Include pairs with the same instruction structure but different hidden constants. Measure optimization quality, feature-extraction cost, inference cost and rejected proposals. This tests whether omitted payloads remove irrelevant detail or erase information required for the decision.

## How the encoder communicates across the program

### Project unlike records into a common hidden dimension

Here is a proposed input projection, with `||` meaning concatenation:

```text
h[v,0] = W[node_kind(v)] * (
    opcode_embedding
    || type_encoder(exact_type_record)
    || constant_encoder(selected_constant_view)
    || attribute_encoder
    || numeric_encoder(values, availability_mask)
)
```

The constant view can contain summaries or an opaque marker; the exact payload need not enter the model. All nodes end up with `d` hidden coordinates. Their original records remain distinct. The projection matrix adapts to broad node roles such as instruction, type, or constant. Making every distinct nested type its own neural parameter category would defeat compositional sharing.

### Text and recurrent encoders

Serializing IR lets a transformer reuse language-model tooling. A decoder-only model can read a program followed by an action or replacement. An encoder-decoder model can read bidirectionally and generate an output conditioned on that representation. Canonical local naming and explicit boundaries can reduce incidental variation, but serialization must preserve semantics relevant to the task.

Earlier recurrent methods are useful comparison points. DeepTune encodes source tokens, combines that representation with auxiliary runtime or architecture inputs, and predicts optimization choices. Inst2vec learns LLVM instruction embeddings from data/control contexts and uses an RNN for downstream predictions. Neither requires a transformer. [DeepTune](https://www.pure.ed.ac.uk/ws/portalfiles/portal/37747688/AE_PACT_2017_paper_2.pdf), [inst2vec](https://arxiv.org/abs/1806.07336)

For a proposed IR experiment, plain text is a serious baseline. The experiment should test whether explicit dependencies improve outcomes enough to justify extracting and maintaining them.

### Relational message passing

A schematic relational graph convolution is:

```text
h[v,l+1] = activation(
    W_self * h[v,l]
    + sum over relations r and incoming neighbors u:
        W[r] * h[u,l] / normalization(v,r)
)
```

Each edge relation has a different transformation. The R-GCN paper also shares relation matrices through a learned combination of basis matrices, reducing parameter growth. [R-GCN](https://arxiv.org/abs/1703.06103)

For an IR adaptation, `operand-0`, `operand-1`, control successor, and memory dependency can carry different information. Reverse edges may be added for neural communication, with distinct labels. They do not reverse program execution.

With ordinary local propagation, `L` layers communicate at most `L` graph hops. A long dependency can therefore require more rounds or explicit summaries. More layers also cost time and repeatedly compress information into fixed-width vectors. Approximate learned data-flow predictions should not replace exact analyses needed to authorize a rewrite.

### Heterogeneous graph attention

HGT makes the interaction depend on the source-node type, relation, and target-node type. In a simplified single-head notation:

```text
key(s)   = h[s] * W_key[source_kind]
query(t) = h[t] * W_query[target_kind]
score(s,r,t) = key(s) * W_attention[r] * query(t)^T
              * relation_prior[source_kind,r,target_kind] / sqrt(head_dim)
message(s,r,t) = h[s] * W_message[source_kind] * W_relation[r]
```

Incoming scores are normalized per target. Weighted messages receive a target-type projection and residual update. This is neighbor attention, not automatic all-node attention. The original experiments concern heterogeneous academic graphs, so compiler use is an adaptation. [HGT](https://arxiv.org/html/2003.01332v1)

For IR, a constant-to-instruction edge can use different parameters from a block-to-instruction edge. Distant nodes still need a path, sufficient layers, or added global communication. Broad roles should determine the parameter families; exact `i32`, `f64`, and nested-array details can remain features inside those roles.

### Dense graph attention

Graphormer adds degree embeddings and structural attention biases. Its score has the general form:

```text
score(i,j) = dot(query(i), key(j)) / sqrt(head_width)
             + shortest_path_bias(i,j)
             + path_edge_feature_bias(i,j)
```

It uses shortest-path structure and a graph-level readout node. [Graphormer](https://arxiv.org/html/2106.05234v3)

Adapting this to IR requires choosing which relations define distance. If a shared type node connects every `i32` value, unrelated instructions become close in the union graph. That distance need not reflect a useful control or data dependency. Relation-specific distances, directional paths, or a local typed encoder are alternatives to test.

A finite bias for disconnected nodes still permits attention. An explicit mask forbids it. Cross-program masking therefore remains necessary even if disconnected pairs have their own distance category.

### Local and global branches

GraphGPS combines local message passing with global attention, then merges their outputs. Its linear-complexity configuration depends on choosing a suitable linear global-attention mechanism. Dense attention remains quadratic, and positional-encoding preprocessing can have its own cost. [GraphGPS](https://arxiv.org/html/2205.12454v4)

Exphormer instead uses sparse attention connections, including expander edges and global nodes. Artificial communication edges should remain labeled separately from compiler dependencies. [Exphormer](https://arxiv.org/abs/2303.06147)

My proposed comparison is relational local processing alone versus local processing plus sparse/global communication. The latter may help long-range context, but it should earn its extra cost on measured optimization quality.

### Attention memory and ordering pitfalls

At 10,000 records, dense attention contains 100 million pairs per head. Materializing scores for eight heads at two bytes each would require 1.6 billion bytes, before other tensors. This is an illustrative allocation calculation, not a minimum memory requirement. FlashAttention avoids materializing the full attention matrix through tiled computation, while still computing dense attention. [FlashAttention](https://arxiv.org/abs/2205.14135)

Graph positional encodings can also introduce incidental choices. Spectral eigenvectors allow sign flips and, for repeated eigenvalues, changes of basis. SignNet/BasisNet study architectures that handle those symmetries. [SignNet and BasisNet](https://arxiv.org/abs/2202.13013)

For a compiler dataset, my proposed invariance tests include renaming SSA values, permuting record storage order while preserving semantic order, and shuffling unordered metadata. Do not demand invariance under operand swaps, field reordering, or instruction motion that changes effects. Predictions should follow program meaning, while the action still identifies the correct concrete node.

## What the model should output

An encoder alone does not optimize a program. A decision head must connect its representation to an operation the compiler can execute. The following interfaces are proposed designs.

| Output | Example | Main training signal | Authority retained by compiler |
| --- | --- | --- | --- |
| Scalar cost | Predicted cycles for a candidate | Measured latency or ranking | Candidate construction and legality |
| Discrete action | Inline this call, choose vector width 4 | Expert action or downstream reward | Available actions and preconditions |
| Region and rule | Apply rule 17 at value 42 | Improvement after applying rule | Rule semantics and matching |
| Schedule trace | Split loop, reorder loops, bind threads | Hardware measurements | Dependence and resource checks |
| Structured edit | Replace two instructions with one | Accepted rewrite pairs | Types, dominance, effects and equivalence |
| Replacement IR | Generate a whole basic block | Validated target programs | Parsing, verification and acceptance |
| Search guidance | Rank synthesis templates | Successful proof and cost reduction | Symbolic solver and final proof |

A cost predictor can use a transformer while generating no code at all. Conversely, a code generator can use a recurrent network. Architecture and output authority are independent decisions.

### Pointer-based structured edits

Generating `%v137` as text treats an arbitrary name as a language token. A pointer head instead selects one of the values in the current program. Pointer Networks established variable-length output distributions over input positions. They do not supply compiler semantics. [Pointer Networks](https://arxiv.org/abs/1506.03134)

A proposed IR decoder maintains the insertion point, values already defined, their types, dominance information, memory effects, and pending control-flow obligations. It emits an opcode, a result type when needed, then operand selections. For operand position `j`, a compiler constructs eligible values `C_j`:

```text
score(v) = query(decoder_state, j) dot key(value_embedding[v])
p(v)     = softmax(score(v), over v in C_j)
```

The candidate set can exclude values of the wrong type or values that do not dominate the insertion point. A PHI operand requires predecessor-edge handling. Newly created values must become available to later decoder steps. Selecting a legal operand still does not establish that the replacement computes the original result.

Constrained token generation is another option. Type-Constrained Code Generation studies prefix constraints that preserve the possibility of a well-typed completion. Its formal treatment and TypeScript implementation are not a ready-made LLVM or A7 decoder. A complete-program type checker alone cannot answer every prefix-completion question. [Type-Constrained Code Generation](https://arxiv.org/pdf/2504.09246)

### Pass selection as sequential decision-making

A proposed reinforcement-learning state contains the current IR, target information, prior actions and remaining search budget. An action invokes a compiler pass or stops. The environment runs the pass, recomputes analyses, and returns the next state.

```text
s_t      = encode(IR_t, target, history, budget)
a_t      = policy(s_t)
IR_(t+1) = compiler_apply(IR_t, a_t)
r_t      = improvement - compilation_cost_penalty
```

This is schematic, not the exact reward of every published system. A histogram of opcodes can hide control flow, alias relationships and transformation history. Two programs with the same histogram may respond differently to a pass. Treating that summary as a complete Markov state is an approximation.

Intermediate size reduction is a cheap reward but can oppose runtime improvement. Measuring runtime after every action is expensive and noisy. Terminal rewards avoid inventing intermediate value, but make credit assignment harder. A critic, a learned cost model, or cached measurements can reduce that cost. Each introduces prediction error.

CompilerDream studies a learned world model for compiler optimization. The model predicts transitions and rewards in a learned representation, enabling policy training with imagined experience. Actual compiler executions still determine whether predicted improvements exist. [CompilerDream](https://arxiv.org/html/2404.16077v3)

A proposed deployment rule is to treat imagined trajectories as candidate generators. Replay promising trajectories in the real compiler before accepting their measured cost. Otherwise, the policy may exploit an inaccurate transition model.

## Local rewriting, equality saturation and synthesis

### Region selection followed by rule selection

NeuRewriter uses a tree representation and learns where to rewrite and which available rule to apply. Its expression experiments use a TreeLSTM and actor-critic training. The cost concerns expression simplification rather than a general measured executable-runtime objective. This is evidence for learned rewrite sequencing, not transformer-generated equivalence rules. [NeuRewriter](https://proceedings.neurips.cc/paper/2019/file/131f383b434fdf48079bff1e44e2d9a5-Paper.pdf)

A graph-transformer adaptation could factor the decision as:

```text
P(action | program) = P(region | program)
                    * P(rule | region, program)
                    * P(parameters | rule, region, program)
```

The compiler enumerates applicable rules or rejects failed preconditions. Parameter selection may identify constants, loop sizes or replacement operands. After mutation, invalidate dependent analyses and update the graph before the next action. Reusing stale dominance or alias information can invalidate an otherwise sound rule.

A local choice can increase immediate cost while enabling a larger later reduction. Greedy selection based only on immediate cost reduction rejects such enabling steps. Long-term value estimates, lookahead search and equality saturation can account for later benefits.

### Equality saturation retains alternatives

An e-graph groups expressions known to be equivalent into e-classes. Applying a valid equality adds equivalent representations instead of discarding the old expression. An extractor later chooses a representation under a cost function. [egg background tutorial](https://github.com/egraphs-good/egg/blob/main/src/tutorials/_01_background.rs)

There are three distinct learning problems:

1. Choose which rewrites to apply before time or memory runs out.
2. Predict the cost used to extract a final program.
3. Propose new equality rules and establish their conditions separately.

Learning the first does not establish the third. Exhaustive saturation is often too large; under a finite budget, rule order affects which alternatives are discovered. E-graph membership supports equivalence only as far as the supplied rules, conditions and implementation are sound.

Aurora applies reinforcement learning to SQL-plan equality saturation. It encodes e-nodes and e-classes with graph attention and uses policy history. Its actions include rewrites and a reset that extracts and rebuilds the graph to reduce growth. SQL cardinality and database cost features do not transfer directly to scalar compiler IR. [Aurora](https://arxiv.org/html/2407.12794v1)

An alternative uses Monte Carlo tree search to select tensor-graph rewrites, with extraction cost as search feedback. Shared subexpressions complicate extraction because summing tree costs can count shared work more than once. This study is a search baseline, not evidence that a neural network is necessary. [MCTS-guided equality saturation](https://arxiv.org/html/2410.05534v1)

EggMind uses an LLM offline to construct reusable equality-saturation strategies, including rule groups and execution phases. Optimization can later run the generated strategy without an LLM call. This moves inference cost into optimizer development, while rule soundness remains a separate responsibility. [EggMind](https://arxiv.org/html/2604.17364v1)

### Learned guidance around a symbolic synthesizer

A synthesizer searches candidate expressions and asks whether they meet a specification. A neural component can prioritize regions, instruction templates, constants or solver queries without becoming the acceptance authority.

Minotaur is a non-neural reference point. It extracts bounded LLVM slices, searches scalar and SIMD replacements, uses Alive2-based reasoning, and estimates profitability with target information. Its supported slices and instruction semantics define its scope. It is not an arbitrary whole-program equivalence oracle. [Minotaur](https://arxiv.org/html/2306.00229v3)

PrediPrune trains a classifier to reject likely-invalid Souper candidates before expensive solver work. The remaining candidates still reach the symbolic checker. False rejection can lose an optimization opportunity; it need not introduce a miscompile when acceptance still requires the checker. [PrediPrune](https://arxiv.org/html/2509.16497v1)

A proposed neural synthesis pipeline is:

```text
extract region -> rank templates -> instantiate candidates
               -> cheap checks -> solver -> target cost -> accept
```

Evaluate both solver time saved and valid improvements missed. Classification accuracy alone can hide rejection of rare, valuable rewrites. Retain an unpruned baseline and audit a sample of rejected candidates.

### Direct generation and self-improvement

SILO trains a transformer on assembly optimization examples, samples candidates, checks them, and uses better accepted programs as new training targets. This self-imitation loop can improve the generator without a human writing every target. The paper also documents verifier weaknesses exploited by generated candidates, making checker quality part of the experiment. [SILO](https://squareslab.github.io/materials/ShypulaSuperoptimization2022.pdf)

LLM-VeriOpt combines verification feedback, supervised training and reinforcement learning for LLVM peepholes. Its latency objective uses an LLVM target cost estimate, which must be distinguished from measured end-to-end runtime. Training against a verifier improves candidate quality but does not remove the need to check deployed candidates. [LLM-VeriOpt](https://samainsworth.github.io/LLM-VeriOpt-CGO2026.pdf)

My proposed acceptance ladder is parsing, structural verification, semantic validation, then profitability. A syntax-valid replacement can be ill-typed; a well-typed replacement can change behavior; an equivalent replacement can be slower. Report each rejection category separately.

## Cost models and schedule generation in detail

### Several architectures solve the same cost-ranking problem

| System | Input and model | Output or use | Important boundary |
| --- | --- | --- | --- |
| Halide autoscheduler | Algorithm and schedule features, small neural model | Cost coefficients used in schedule search | Feature design and search are substantial parts of the system |
| Tiramisu autoscheduler | Computation vectors plus recurrent aggregation over loop structure | Predicted speedup for candidate transformations | Affine-program representation and measured target constrain coverage |
| Ansor | Numeric features of generated low-level programs, boosted trees | Candidate scores for evolutionary search | Learned, but not deep learning |
| TLP | Schedule-primitive sequence, embeddings and self-attention | Ranking schedules | Sequence representation depends on the scheduling system |
| Ithemal | Assembly instructions and operands, hierarchical LSTM | Basic-block throughput estimate | Throughput is not whole-program latency |
| TCL | Schedule representation with a state-space cost model | Cost prediction and transfer across tasks/hardware within studied groups | Cross-CPU/GPU transfer is explicitly outside its demonstrated scope |

Sources: [Halide](https://halide-lang.org/papers/halide_autoscheduler_2019.pdf), [Tiramisu](https://commit.csail.mit.edu/papers/2021/tiramisu_autoscheduler.pdf), [Ansor](https://arxiv.org/html/2006.06762v2), [TLP](https://arxiv.org/pdf/2211.03578), [Ithemal](https://proceedings.mlr.press/v97/mendis19a.html), [TCL](https://arxiv.org/html/2604.12891v1).

Halide's model predicts coefficients for a structured cost computation. This differs from asking a large transformer to infer every relevant hardware effect from text. Tiramisu uses computation features, including access information and transformation parameters, and recurrent aggregation over loop structure. These are useful baselines when a compiler already exposes reliable structural features. [Halide](https://halide-lang.org/papers/halide_autoscheduler_2019.pdf), [Tiramisu](https://commit.csail.mit.edu/papers/2021/tiramisu_autoscheduler.pdf)

TLP provides a concrete transformer-style example. Its reported architecture projects schedule features into 256 dimensions, uses one eight-head self-attention layer, residual processing and a final score. It evaluates ranking and regression choices. Its fixed feature and sequence limits describe that dataset's encoding; silently cropping arbitrary compiler IR to those limits would discard information. [TLP](https://arxiv.org/pdf/2211.03578)

The practical question is whether attention improves candidate ordering enough to justify its inference and training costs. Compare it with boosted trees and a small multilayer perceptron on the same features, splits and measurement budget. A large pretrained code model is another experiment, not an automatic upgrade.

### Search traces separate structure from parameters

Ansor generates high-level schedule sketches, fills parameters, searches candidates and updates a learned cost model from measurements. MetaSchedule represents schedules through traces with sampled decisions, enabling mutation of choices such as tile sizes. The scheduling primitives enforce a structured search space. [Ansor](https://arxiv.org/html/2006.06762v2), [MetaSchedule](https://arxiv.org/html/2205.13603v2)

A proposed transformer over traces might receive:

```text
operation = matmul
shape     = [M, N, K]
dtypes    = [input_a, input_b, accumulator, output]
layout    = [stride_a, stride_b, stride_c]
target    = [vector_width, cache_sizes, thread_limits]
trace     = [split(i, ti), split(j, tj), reorder(...), vectorize(...)]
```

These are heterogeneous records. Embed operation names categorically; encode tile sizes and shapes numerically while retaining exact values; represent layout as structured strides; encode the target explicitly. A model that sees only the trace cannot distinguish two workloads whose dimensions or element widths produce different memory behavior.

Generation can alternate a primitive choice with parameter choices. A legal-action mask can remove impossible splits or unsupported vector widths. The scheduler must still check dependence, reduction and resource constraints. The measured kernel supplies the final performance label.

### Vectorization as a small action space

NeuroVectorizer uses code2vec-style AST path representations and reinforcement learning to choose vectorization and interleaving factors. It is not a transformer over complete SSA graphs. This illustrates a narrower learned decision attached to an existing compiler mechanism. [NeuroVectorizer](https://arxiv.org/html/1909.13639v3)

A small action space is attractive for a first experiment because exhaustive or near-exhaustive measurements may be affordable. It also gives a meaningful oracle baseline: the best available choice among exactly those actions. That oracle does not represent the best possible program outside the action set.

## Training objectives and data construction

The equations below are proposed generic objectives. They explain design choices rather than reproduce every paper's training recipe.

### Supervised cost estimation and ranking

Regression can predict log latency to reduce the scale difference between small and large kernels:

```text
loss_regression = mean((predicted_log_time - measured_log_time)^2)
```

A low average error does not guarantee that the fastest candidate ranks first. For two schedules of the same workload, where `a` is faster than `b`, a pairwise objective can train a higher-is-better score:

```text
loss_pair = log(1 + exp(-(score(a) - score(b))))
```

Compare pairs within a workload or use an explicit normalization scheme. Otherwise, a model can learn that small workloads are fast without learning which schedule is best for a given workload. Near-tied measurements need repeated observations or a noise-aware rule before assigning a hard ordering.

Measure top-k regret: how much slower the best of the model's k selected candidates is than the best measured candidate in the held-out set. Also report the number and cost of measurements used to obtain that result.

### Imitation and reinforcement learning

For accepted action trajectories, supervised learning minimizes negative log probability of the demonstrated actions. A compiler heuristic, exhaustive search, solver, or validated generator can provide demonstrations. The learner inherits the teacher's coverage and mistakes in the labels.

For sequence-level optimization, a possible terminal reward is:

```text
reward = log(baseline_time / candidate_time)
         - lambda_compile * added_compile_time
         - lambda_size * excess_code_size
```

Weights and units must be specified. A correctness failure should trigger rejection and a separate failure record. Do not let a large speed score compensate for changed semantics. Timeout, measurement failure and proven inequivalence are different labels.

Search-guided imitation repeatedly searches with the current model, accepts independently checked improvements, and retrains on them. It concentrates data on useful candidates but can narrow exploration. Preserve unsuccessful examples and their reasons for auxiliary tasks; do not train an incorrect replacement as a valid target.

### Pretraining can supply representations, not proof

Proposed pretraining tasks include masked opcode prediction, def-use edge recovery, type prediction and contrastive learning across compiler-generated equivalent variants. These tasks can reduce labeled-performance requirements.

They also have shortcuts. A type-prediction task can be trivial if an equivalent type annotation remains visible. A contrastive pair generated by an incorrect transformation teaches a false equivalence. A model can identify a project through naming conventions without understanding optimization behavior.

Mask the relevant information consistently, audit pair construction, and include downstream held-out optimization results. Pretraining loss alone is not evidence of a better optimizer.

### A useful training record

A proposed record keeps reproducibility information beside the tensors:

```text
program_family_id, source_revision, region_id
compiler_revision, IR_schema_version, target_cpu_or_gpu
semantic_flags, types, constants, graph, analyses
candidate_action_or_trace, transformed_IR_hash
validation_tool_version, validation_result, assumptions
measurement_protocol, repetitions, observed_times
baseline_hash, baseline_times, compilation_cost
split_group, provenance, license
```

Keep exact IR and metadata outside the neural feature arrays. They are needed for replay and validation. Include failures instead of retaining only successful fast candidates. A dataset of successful rewrites cannot teach rejection rates or represent the real search distribution by itself.

Raw IR corpora support representation learning. Performance datasets support cost learning. Verified rewrite pairs support transformation learning. These labels are not interchangeable. The overview discusses ComPile, CompilerGym and related sources; a proposed project needs a separate provenance and licensing review before redistribution.

### Split the dataset by origin and transformation lineage

Randomly separating two schedules of the same kernel into training and test sets measures interpolation within a known workload. It does not establish generalization to unseen programs.

Use separate evaluations for unseen schedule choices, unseen algorithm families, unseen projects and unseen hardware. Keep generated variants, duplicates and descendants of the same source region together when measuring unseen-program performance. Hold out a compiler version separately if claiming resilience to compiler changes.

For hardware transfer, report zero-shot prediction separately from adaptation using new measurements. Record how many target measurements adaptation consumes. A method that needs fresh target data can still be useful, but its cost must be counted.

## Worked example: exact arithmetic, graph inputs and checked edits

Consider this illustrative SSA-like fragment. It is explanatory notation, not A7 syntax or a claim that A7 already has an SSA IR.

```text
x  : u8 = argument(0)
c5 : u8 = constant(5)
c7 : u8 = constant(7)
y  : u8 = add_wrap(x, c5)
z  : u8 = add_wrap(y, c7)
return z
```

The graph contains value records for `x`, `c5`, `c7`, `y` and `z`, operation records for the two additions, and ordered use/definition edges. Both additions reference the `u8` type record. Constants retain exact integers 5 and 7. The operation explicitly states wrapping semantics.

A model could select the second addition and a constant-reassociation rule. A deterministic rule implementation combines constants modulo 256 and constructs:

```text
c12 : u8 = constant(12)
z   : u8 = add_wrap(x, c12)
return z
```

The arithmetic identity is:

```text
((x + 5) mod 256 + 7) mod 256 = (x + 12) mod 256
```

An exhaustive local check over all 256 `u8` inputs passed during this research. That check covers this finite expression only. It does not validate the entire compiler, LLVM poison semantics, or memory behavior. The reduction from two additions to one is a structural fact; a runtime improvement still requires inspecting and measuring generated code. A backend may already perform the same optimization.

The model's role can vary while keeping this example fixed:

| Approach | Learned decision | Deterministic work |
| --- | --- | --- |
| Rule policy | Choose the reassociation rule and location | Match, compute 12, construct replacement |
| Cost model | Rank original and replacement | Enumerate valid candidates |
| Pointer decoder | Emit an addition referring to `x` and a constant | Check structure and equivalence |
| Synthesis guidance | Prioritize one-addition templates | Solve constants and prove the replacement |
| Equality saturation | Select rewrites or extraction cost | Retain equivalent expressions and extract |

This is a useful controlled comparison because every method faces the same semantics. Comparing one model's tiny rule space with another model's unrestricted generation would mix architecture effects with search-space effects.

### Why floating-point types change the answer

For binary32 values near `a = 1e20`, `b = -1e20`, `c = 3.14`, rounding each addition gives different results:

```text
(a + b) + c = 3.140000104904175
a + (b + c) = 0.0
```

These values were checked locally with binary32 rounding after each addition. Reassociation therefore needs an appropriate semantic permission; copying an integer rule into floating-point code is invalid in general. Flags permitting algebraic transformations belong in the model input and in the deterministic rule precondition.

A type name alone is insufficient. Signedness, width, overflow behavior, floating-point permissions and evaluation order determine whether the rewrite is valid.

### Why memory effects change the answer

Consider two loads separated by a store:

```text
a = load(p)
store(q, 9)
b = load(p)
```

Replacing `b` with `a` requires establishing the relevant memory conditions. If `p` and `q` can refer to the same location, the store may change the second load. Volatile or atomic operations bring further restrictions. A learned alias score is not a proof that the pointers differ.

A model may rank this region as promising and ask the compiler's analysis or a solver to establish the condition. If the analysis returns unknown, the ordinary rewrite remains unavailable. A guarded transformation is a different design that must check the guard and fallback behavior.

### Why a tensor schedule has more than a dtype

For matrix multiplication, the input may include `M`, `N`, `K`, element types, accumulator type, strides, alignment, alias assumptions, memory placement and target constraints. A schedule also changes tile sizes, loop order, vectorization and thread mapping.

A proposal to tile the output dimensions can preserve each output element's sequential reduction order. Parallelizing or rearranging the reduction dimension can change floating-point rounding. Choosing a matrix instruction can also change accumulation behavior. The legality check must reflect the actual contract, including any permitted relaxed arithmetic.

A faster measured schedule for one shape and stride pattern is not evidence that it is faster for all shapes with the same dtype. Training records must retain those differences.

## Evaluation that separates the different claims

My proposed first study fixes a compiler-checked action set and compares a heuristic, boosted trees, a small neural network, a relational graph network, and a graph transformer. Use the same training examples, candidate budget and held-out workloads. This isolates the value of representation and architecture before expanding output authority.

A second study compares rule policies, beam search, equality saturation and neural-guided synthesis under matched wall-clock budgets. A third studies direct generation with the same validation system and explicit verifier-coverage limits. These are research designs, not approved A7 implementation work.

| Claim | Required evidence | Insufficient substitute |
| --- | --- | --- |
| Better cost prediction | Held-out error, ranking and top-k regret | Training loss |
| Better optimizer | Measured accepted-program performance against strong baselines | Predicted cost reduction |
| Lower tuning cost | Time and measurements needed to reach a fixed quality | Fewer model calls alone |
| Lower compile overhead | End-to-end compilation with extraction, inference and validation included | Neural forward-pass timing |
| Correct transformations | Stated semantic coverage and per-candidate validation | Parsing, type checking or passing a few tests |
| Generalization | Held-out families/projects/targets matching the claim | Random split of related variants |
| Practical deployment | Failure handling, versioning, resource limits and repeated measurements | A successful notebook experiment |

Report distributions and regressions, not only a geometric-mean speedup. Include inference cost, feature extraction, graph construction, search, solver time, compilation and benchmarking. Preserve the original program when a proposed optimization is rejected or cannot be validated.

A rough deployment break-even calculation is:

```text
required_executions = added_optimization_time / time_saved_per_execution
```

It applies only when the measured per-execution saving remains representative. Ahead-of-time compilation, just-in-time compilation and offline library tuning have different acceptable budgets.

### Validation boundaries

Equivalence and refinement are different relations. LLVM transformations often need refinement under the relevant undefined-behavior and poison rules. A checker must understand the instructions and semantic version being transformed. Unsupported constructs, bounded loop reasoning, external calls and timeouts constrain the conclusion. [Alive2](https://alive2.llvm.org/)

Tests add evidence for behavior and measurement infrastructure, but finite input testing cannot establish arbitrary-program equivalence. Solver acceptance is also qualified by the encoded semantics and implementation. Record proof assumptions and checker versions, and keep independently checkable counterexamples when a candidate fails.

A learned model should never make a transformation legal merely by assigning it a high confidence score. It can decide where to spend analysis effort, which checked option to try, or which candidate to submit for validation.

## A7-specific research boundary

The current A7 pipeline exposes typed AST nodes, exact constants, semantic information and safety obligations, then emits Zig. The overview records the inspected source locations. A CFG/SSA dataset would first require an explicit representation and extraction contract; this report does not assume those already exist.

A proportionate A7 research prototype would export stable region identifiers, structural node types, exact constants, ordered edges, known effects and target metadata without changing language behavior. It would then compare predictors on an existing, explicitly defined candidate space. Runtime measurements must include the effect of Zig's own optimizations, which may erase differences visible earlier in the pipeline.

Any new IR, transformation rule or language behavior needs its own design and approval process. This document supplies alternatives and evaluation criteria. It does not authorize implementation or settle the compiler architecture.

## Research and verification record

This companion and the overview are dated research snapshots. Primary links identify the published methods; proposed schemas, equations and experiments are labeled in the text. The research includes repository-source inspection and the finite arithmetic checks described above. No model was trained, no paper benchmark was reproduced, and no A7 compiler behavior was changed.

The accompanying PDF combines the overview with this technical companion. Document checks cover Markdown structure, local links, style and PDF rendering. Compiler release gates are outside this documentation-only task.
