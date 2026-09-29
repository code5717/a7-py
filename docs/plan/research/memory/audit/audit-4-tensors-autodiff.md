> **Source:** Claude Code audit subagent 4, tensors, autodiff and AI workloads. Its gate numbers M14–M22 predate the plan's numbering; see the crosswalk in edge-case-audit.md.  
> **Date:** 2026-09-15. Audit of docs/plan/memory.md revision 1.  
> **Status:** Advisory. Expected results are hand traces; probe results are compile-only unless stated. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

# Audit 4: tensors, autodiff and AI workloads against the memory plan

Date: 2026-09-15. Status: advisory audit. It approves nothing.

Scope: `docs/plan/memory.md` (contract section 1, layers 0-8 in section 4, gates M2,
M8, M11, M12, M13, corpus programs 8, 9 and 12, phase F), checked against
`docs/plan/decisions.md` (L7-L11, L15-L19), `docs/plan/README.md` (G8 and the AI
sequence), `research/ai-frameworks-codex.md` (AI), `research/numerical-policy-glm.md`
(GLM R-1 to R-12), `research/memory/notes-g-language-ai-hardware.md` (notes G),
`research/memory/synthesis.md`, and the advisor proposals in
`research/memory/advice-fable.md` and `advice-grok.md`.

Evidence level: **every expected behavior below is a hand trace against plan text.**
Nothing was compiled or run. All A7 code is **proposed syntax**, not current A7, and
must not be copied into examples or public docs. Snippets follow the A7 rules: `usize`
indices, no `&`, `*`, `.adr` or `.val`, `ref` parameter bindings never rebound, no
source recursion, no `new [N]T`.

Assumed proposed surface for the snippets (for illustration only): `Tensor(T)` value
type with dtypes `f16`, `bf16`, `f32`, `f64`; functions `matmul`, `transpose`,
`reshape`, `broadcast`, `relu`, `dropout`, `cross_entropy`, `backward(loss)` returning
gradients, `adam_update`; `List(T)`; `ref` parameters as today.

Layer numbers: 0 typed IR, 1 sound facts, 2 internal ownership, 3 escape analysis,
4 extent inference, 5 storage formation, 6 copy elimination and reuse, 7 static
buffer planning, 8 layout.

Coverage values: **Covered** (memory.md gives a determinate answer), **Ambiguous**
(two readings), **Contradicts** (memory.md gives conflicting answers), **Silent**
(no answer).

## 1. Headline programs

These eight programs carry most of the contradictions. The table in section 2
references them.

### P1. Saved value changed before backward (corpus 8)

```a7
// Proposed syntax
x := tensor_from([1.0, -2.0, 3.0], f32)
y := x * x          // backward of mul saves x
x = x + 1.0         // x changes while the tape depends on its old value
g := backward(sum(y), x)
```

memory.md section 2 says `b := a` shares storage "until either side changes". Under
that model the write to `x` builds a new value; the saved old `x` is untouched, and the
gradient `[2, -4, 6]` is correct. Corpus 8 says "Reject or report before execution".
Contract item 7 says a value changed while something depends on it is an exclusivity
conflict. The plan therefore says both "accept with copy" and "reject". There is also a
second question: with respect to which `x` is the gradient requested? The new `x` has no
path to `y`.

### P2. Weight update while the tape still holds the weight (corpus 9)

```a7
// Proposed syntax
train_step :: fn(model: ref Model, batch: Batch) f32 {
    h := relu(matmul(batch.x, model.w1))   // matmul saves model.w1 for grad of input
    loss := cross_entropy(matmul(h, model.w2), batch.y)
    grads := backward(loss)
    adam_update(model, grads)              // writes w1 and w2
    ret loss.item()
}
```

Corpus 9 expects "Accept; step memory reused" "after tape release". Nothing in source
releases the tape, and contract item 6 forbids memory vocabulary. If the tape is
still live when `adam_update` runs (for example because it is only released at step end),
then under share-until-changed every weight is copied once per step (peak doubles, no
diagnostic unless M8 fires), and under the reject reading this ordinary program is
rejected.

### P3. Tied embeddings

```a7
// Proposed syntax
Decoder :: struct {
    wte: Tensor(f32)      // token embedding, [vocab, d]
    blocks: List(Block)
}

forward :: fn(m: Decoder, tokens: Tensor(usize)) Tensor(f32) {
    h := gather(m.wte, tokens)
    // ... blocks ...
    ret matmul(h, transpose(m.wte))       // same parameter used as output head
}
```

Using one field twice works and gradients accumulate (AI:463, 501). But a model written
as `lm_head: Tensor(f32)` initialized with `lm_head = wte` under value semantics is two
independent values: they diverge after the first update. There is no way under
section 2 to state "these two fields are one parameter" except by giving up one field.
memory.md is silent. This blocks a common variant of the L10 transformer recipe.

### P4. Loss kept across steps (classic PyTorch leak)

```a7
// Proposed syntax
total := zeros([], f32)
for s: usize = 0; s < steps; s += 1 {
    loss := train_step(model, loader.next())   // suppose train_step returns Tensor(f32)
    total = total + loss                        // loss carries tape history
}
```

If `loss` keeps its autodiff history, `total` keeps every step's tape alive, memory
grows linearly, and contract item 5 ("every extent ends") holds only at process end.
M11 says the step extent owns the tape, so the tape must end at iteration end, which
means `loss` must either be detached automatically when it escapes, or the escape is
rejected. memory.md does not say which.

### P5. Gradient accumulation across microbatches

```a7
// Proposed syntax
acc := zero_grads(model)
for k: usize = 0; k < micro; k += 1 {
    b := loader.next()
    grads := backward(cross_entropy(forward(model, b.x), b.y))
    acc = acc + grads          // loop-carried; activations and tape must die per k
}
adam_update(model, acc)
```

Contract item 5 lists "loop iteration" and "training step" as extents. Here the
optimizer step spans `micro` iterations while activations and tape must be per
iteration. If extent inference equates the step with the innermost loop iteration that
contains `backward`, `acc` is fine (loop-carried, layer 4) but "step extent" as named in
M11 is not a syntactic construct at all.

### P6. KV cache growth during generation

```a7
// Proposed syntax
cache := List(KV){}
last_token := prompt_last_token(prompt)
for t: usize = 0; t < max_new; t += 1 {
    q := project_query(model, last_token)
    kv := project_kv(model, last_token)
    cache.append(kv)
    past := stacked_keys(cache)                // view or copy over all positions?
    logits := attend(q, past)
    last_token = argmax(logits)
}
```

If `past` is a view into `cache`, appending on the next iteration while `past` is live
is the M13 conflict (corpus 2 analog). If `past` is a copy, generation is O(T^2) bytes
copied. If the cache is a preallocated `[max_ctx, ...]` tensor updated in place, the
write into a live tensor happens while no tape exists (inference) and is legal, but
memory.md has no tensor capacity or in-place slice write rule.

### P7. Layer-6 reuse creating an aliased GEMM

```a7
// Proposed syntax
a = matmul(a, w)   // last use of old a; layer 6 may reuse a's buffer as output
g := matmul(x, transpose(x))   // read-read overlap: both inputs share storage
```

Corpus 12 says "Native kernel given overlapping buffers: Reject". The second line is a
legal, common Gram or attention computation with read-only overlap. The first line is
safe in the source, but the compiler's own reuse (layer 6) would pass the same buffer as
input and output to `cblas_sgemm`, which forbids it. The hazard is created by the
compiler, not the user.

### P8. Out-of-memory back-off

```a7
// Proposed syntax
bs: usize = 64
for {
    r := try_train_step(model, loader.next_batch(bs))
    match r {
        case .out_of_memory: { bs = bs / 2 }   // requires releasing the failed step's storage
        case .ok(loss): { break }
    }
}
```

M2 makes tensor calls recoverable. The failed step has a partly built tape and partly
filled activation arena. Contract item 5 releases storage at extent end, but an error
value returned from the middle of a step is only an extent end if the step is a call.
Retrying with `bs / 2` also means a new shape signature for layer 7. If the planner
keeps the 64-batch arena (ORT BFCArena never shrinks, GLM section 2.4), back-off frees
nothing and the retry fails again.

## 2. Edge-case table

L19 column: **Y** means an ordinary user would notice (diagnostic, rewrite, visible cost
or wrong result), **N** means invisible when the plan is implemented as proposed.

| ID | Category | Program (proposed syntax or pseudocode) | Expected under memory.md | Layer / gate | L19 | Coverage | Proposed precise rule |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EC4-01 | Values vs views | `t := transpose(x); t[0, 1] = 5.0` | Section 2: `t` is a value, `x` unchanged, write copies `t` storage | 2, 6, M13 | Y (hidden copy of full tensor) | Ambiguous (M11 says views are temporary; is `t` a view?) | A view-producing call bound to a name is a value. The first write through it materializes a private copy. M8 reports copies above a size threshold. |
| EC4-02 | Values vs views | `r := reshape(transpose(x), [n * m])` | Reshape of non-contiguous input cannot be a view; aliasing is stride-dependent at run time (AI:51, notes G 11) | 2, 6 | N | Silent | Treat a reshape result as "may alias its input" in layer 2. If strides are statically unknown and a write follows, always copy; never make uniqueness depend on run-time strides. |
| EC4-03 | Values vs views | `v := x[.., 5..0]` (reversed slice) | `usize` strides cannot express negative strides (AI:52) | 0, G8 | Y | Silent | Reversal and flip always produce new storage in v1. Stride type stays `usize`; no negative stride descriptors. |
| EC4-04 | Broadcast | `bb := broadcast(b, [n, d]); bb[0, 0] = 1.0` | Writing an expanded view would write all rows | 2, 6, M13 | Y | Silent | Broadcast results are read-only descriptors; a write materializes a full `[n, d]` copy first and M8 reports it. No writable overlapping view exists. |
| EC4-05 | Broadcast backward | `y := x + bias` then `backward` | Bias gradient must sum over the broadcast axes (AI:501) | AD registry, 7 | N | Silent (numerics, but the reduction buffer is step storage) | Broadcast VJP allocates the reduced gradient in the step extent; planner sizes it from the unbroadcast shape. |
| EC4-06 | In-place ops | `x += y` where `x` is uniquely owned and unsaved | Layer 6 turns it into in-place update | 6 | N | Covered | `x op= y` is sugar for `x = x op y`; in-place only when layer 2 proves uniqueness and no saved-value dependency. |
| EC4-07 | In-place ops | `x += y` where `x` is saved on a live tape (P1) | Section 2: copy. Corpus 8 and contract 7: reject | 2, 6, M11 | Y | **Contradicts** | Gate M15 (section 4). Recommended: reject as exclusivity conflict when statically known; the diagnostic names the saving operation and suggests computing a new name. |
| EC4-08 | Value cost | `snapshot := model` (EMA or best-so-far) then `adam_update(model, g)` | Share until changed; first update copies every parameter, peak doubles | 6, M8 | Y (peak memory) | Covered, cost unmeasured | Keep; phase E measurement must include this program. M8 report lists whole-model copies. |
| EC4-09 | Value cost | Element write `big[0, 0] = 1.0` on a 1 GB tensor shared with another name | Whole tensor copied for one element | 6, M8 | Y | Covered in principle | Warn (M8) when a copy of more than a threshold is triggered by a single-element write. No chunked copy-on-write in v1. |
| EC4-10 | Value cost | Tensor passed by value to a function that only reads it | Borrow for the call; no copy | 2, 3 | N | Covered (by immutable argument bindings) | Non-`ref` tensor arguments are read-only borrows; never copied. |
| EC4-11 | Saved values | P1 with gradient requested w.r.t. the rebound `x` | New `x` has no path to `y` | AD registry | Y | Silent | Gradient requests name the value that was recorded, not the variable. Rebinding a differentiated input before `backward` is rejected with "input changed after use", independent of M15. |
| EC4-12 | Saved values | Saved value is a view: `k := transpose(reshape(h, ...))`, attention saves `k` | Tape holds a view beyond the statement; contradicts "views are temporary" (M11, M13) | 2, 4, M11, M13 | N | **Contradicts** | The tape retains the base storage and a descriptor, not a user-visible view. Base storage extent is extended to the tape's extent. M13 applies only to user-visible bindings. |
| EC4-13 | Saved values | Saved value mutated through a different alias: `a := x; a[0] = 0.0` after `y := x * x` | Value semantics: `a` copies; saved `x` intact | 2, 6 | N | Covered if M15 = copy; reject if M15 = reject | Aliasing is by storage identity (layer 0), never by name. Tests must include the alias path, not only the direct name. |
| EC4-14 | Saved values in dynamic control flow | `if data_dependent { y = x * x } ; x = x + 1.0; backward(y)` | Whether `x` is saved depends on a run-time branch; "report before execution" impossible | 1, M11 | Y | **Ambiguous** | Static analysis uses may-save facts joined over branches (layer 1). M15 rejection applies to may-save. No run-time version counter in v1 (contract item 4 does not list one). |
| EC4-15 | Tape release | P2: `backward(loss)` then `adam_update` | Corpus 9 presumes a release point the user never writes | 4, M11 | Y if rejected | **Contradicts** contract item 6 wording ("tape release" is not user-visible) | Gate M14: `backward(loss)` consumes the tape of `loss` (affine move in layer 2). Saved values die at that point, not at step end. Parameter writes after it are unconstrained. |
| EC4-16 | Repeated backward | `g1 := backward(loss); g2 := backward(loss)` | With consume-on-backward: use after move | 2, M14 | Y | Silent | Second `backward` on a consumed loss is a compile-time use-after-move diagnostic ("gradients of `loss` were already computed"). |
| EC4-17 | Repeated backward, two losses | `ga := backward(l1, params); gb := backward(l2, params)` sharing a trunk | Consuming on first backward breaks the second | 2, M14 | Y | Silent | Offer one call `backward([l1, l2])` that sums cotangents, or a persistent-tape form behind M14. No implicit retention. |
| EC4-18 | Tape lifetime | Tape nodes in a loop with data-dependent trip count | Tape length dynamic (AI:310) | 4, 5, M2 | N | Covered (release points static, sizes dynamic, contract 3) | Tape is a growable step-extent store; growth failure is an M2 recoverable error. |
| EC4-19 | Tape release shape | Release of a very deep tape (transformer x N layers x T steps) | Must not use native recursion | Contract 8 | N | Covered | Tape release is a bulk extent reset; no per-node destruction walk unless a node owns native handles, then walked iteratively. |
| EC4-20 | Gradient escapes step | P4: `total = total + loss` with history | Tape of every step retained or step extent cannot end | 3, 4, M11 | Y (linear memory growth, the most common PyTorch leak) | **Silent** | A tensor with autodiff history that escapes the extent owning its tape is rejected with a rewrite to `loss.item()` or `detach(loss)`. No silent detach, no silent extent extension (synthesis item 7). |
| EC4-21 | Gradient accumulation | P5 | `acc` loop-carried; activations per iteration | 4, M11 | N | Ambiguous ("training step" extent undefined) | Define the extent hierarchy (section 3, gap G-4). Accumulators are loop-carried values; layer 6 reuses `acc` in place because the old value is dead. |
| EC4-22 | Gradient accumulation with skipped step | P5 with f16 and one microbatch overflowing | Whole optimizer step skipped (GLM N-3) | M2, G8 | N | Silent | Non-finite check runs on the accumulator after the last microbatch; `acc` is dropped with the step; model extent untouched. |
| EC4-23 | Disconnected parameter | `backward(loss)` where `model.unused` has no path | Absent vs zero gradient (AI:316) | AD registry, 5 | N | Silent | Absent gradients allocate no storage; the gradient container holds an optional per parameter. Optimizers skip absent entries. |
| EC4-24 | Recomputation | `h := checkpointed(block, x)` | Saved activations replaced by replay | 0 (effects), 4, 7 | N | **Silent** (AI:573 says decide explicitly) | Gate M18. If in v1: region must have an effect summary of "pure except RNG"; file I/O, parameter writes, channel sends inside it are rejected. |
| EC4-25 | Dropout with recomputation | `dropout(h, p, rng)` inside a recomputed block, `rng: ref Rng` | Replay must reuse the mask without advancing the RNG twice (AI:330) | 0, 2, M18 | Y if wrong (silently different gradient) | Silent | The tape saves the RNG state value at region entry (a small value copy); replay uses the copy; the caller's `rng` advances exactly once. |
| EC4-26 | Eval mode | `logits := forward(model, x)` in an evaluation loop, no `backward` reachable | No tape needed | 3, 4 | N | Silent | Tape recording is a static property: if no `backward` is reachable from a value's uses (layer 3 summary), no saved values are recorded. When reachability is dynamic, record. |
| EC4-27 | Eval mode dropout | Same `forward` used for train and eval | Mode is a value, not memory | G8 | Y | Silent (not memory) | Mode passed as an ordinary value; the static no-tape rule of EC4-26 does not depend on it. |
| EC4-28 | Optimizer state lifetime | Adam `m`, `v` created lazily in the first step inside `train_step` | Created in step extent, would be released at step end unless it escapes into `ref Model` | 3, 4 | N | Covered by escape (store into `ref` parameter) | Values written into a `ref` argument take the extent of the caller's value. Test: lazy creation keeps `m`, `v` across 1000 steps with flat memory. |
| EC4-29 | Optimizer state in a local | `for ... { opt := Adam{}; adam_update(model, opt, g) }` | Moments reset every iteration | 4 | Y (wrong training) | Covered (value semantics make it visible in code) | No memory rule; lint candidate only. |
| EC4-30 | Master weights | f32 master plus f16 working copy each step | Working copy saved by forward (matmul saves weight) | 4, 6, 7, M11 | N | Silent | Working copies are step-extent values derived from masters; master writes after `backward` consumed the tape (M14) are free. Caching working copies across steps is a layer-6 optimization only when no write to the master occurred. |
| EC4-31 | Mixed-precision staging | Non-finite check then update of 100 parameters | Skipped step must leave masters, moments, counters unchanged (AI:240) | M2, 5 | Y if partial | Silent | Check all gradients (one fused scan) before the first parameter write. Optimizer workspace is reserved before the first write, so an out-of-memory cannot occur between writes. |
| EC4-32 | Loss scaling | f16 loss scaled by 65536, backward produces Inf | Gradients freed with step; scaler value updated | 4, G8 | N | Silent | Scaler state is a model-extent value and part of the checkpoint (GLM N-3). |
| EC4-33 | Conversion temporaries | bf16 tensor on a CPU without native bf16, widened to f32 per op | Hidden f32 temporaries (AI:246) | 7, M8 | Y (peak) | Silent | Conversion temporaries enter the step plan like any buffer; M8 report lists emulation buffers separately. |
| EC4-34 | Parameter sharing | P3 tied weights via two fields | Two independent values diverge | 2, M1 | Y (wrong model) | **Silent** | Gate M16. Recommended: parameters live in one parameter table; tying uses one index used twice. Fields holding the same parameter are indices, not tensors. |
| EC4-35 | Parameter sharing, gradient | Same parameter used in gather and matmul | Gradients accumulate into one buffer (AI:463) | AD registry, 7 | N | Silent | Accumulation buffer per parameter identity (storage identity from layer 0), never per use site. |
| EC4-36 | Repeated gather indices | `gather(wte, [3, 3, 3])` backward | Scatter-add accumulates (README test plan) | AD registry | N | Covered by README test plan, not memory.md | Index tensors are `usize`; backward buffer is `[vocab, d]` in step extent, or sparse row set (decide in G8). |
| EC4-37 | KV cache as list | P6 with `past` as a view over `cache` and `append` next iteration | M13: growth with live view rejected | 2, M13 | Y | Covered (reject), but ordinary code becomes a rewrite | Gate M19: tensors with reserved capacity (`reserve_rows`), writes into rows beyond length allowed while views cover only rows below length. |
| EC4-38 | KV cache as preallocated tensor | `cache[t, ..] = kv` into `[max_ctx, d]` | In-place write of a unique value with no tape | 6 | N | Ambiguous (tensor element slice assignment not described) | Row assignment into a uniquely owned tensor is in place; if shared, copies (EC4-09). |
| EC4-39 | KV cache per-token temporaries | Logits, attention scores per token | Iteration extent reset | 4, 5 | N | Covered | Keep; corpus test must show flat memory over 10 000 generated tokens. |
| EC4-40 | Variable batch shape | Last partial batch `[37, ...]` instead of `[64, ...]` | Layer 7 assumes static sizes | 7 | N | **Ambiguous** (contract 3 allows dynamic sizes, layer 7 text implies static) | Gate M17: a deterministic runtime planner runs per shape signature; plans for a smaller signature may reuse the larger arena. |
| EC4-41 | Variable sequence length | Decoder training with lengths 1..2048, and generation where length grows by one each token | One plan per length: 2048 plans | 7, M17 | Y (compile or run cost, memory held by plan cache) | Silent | Plan cache is bounded (count and bytes) in the process extent; shapes above the bound use bucketed plans (round up to a power of two) or unplanned allocation. |
| EC4-42 | Native workspace (call) | oneDNN scratchpad for one convolution call | M12 borrow for the call | M12, 7 | N | Covered | Size only from descriptor query (GLM R-3); allocate in step plan; never computed with A7 arithmetic. |
| EC4-43 | Native workspace (fwd to bwd) | oneDNN max-pool workspace kept from forward to backward | Retained across two native calls | M12, M11 | N | **Ambiguous** ("borrow for the call" vs "declared owned handle") | A kernel descriptor may declare a workspace output; it becomes a saved value on the tape, owned by the tape extent, consumed by `backward` (M14). |
| EC4-44 | Overlap into GEMM | P7 line 1: `a = matmul(a, w)` with layer-6 reuse | Compiler creates input-output aliasing | 6, M12 | N if rule holds; memory corruption if not | **Contradicts** corpus 12 intent (hazard is compiler-made) | Layer 6 must not choose any input storage as a native kernel output unless the descriptor declares in-place safety. Checked in the backend plan, not by spelling. |
| EC4-45 | Read-read overlap | P7 line 2: `matmul(x, transpose(x))` | Corpus 12 "reject overlapping buffers" would reject a legal program | M12 | Y if rejected | **Contradicts** | Only output-overlaps-input is illegal. Input-input overlap is allowed. Corpus 12 wording changes (section 3). |
| EC4-46 | BLAS integer width | `matmul` with a dimension above `2^31 - 1` on LP64 OpenBLAS | Dimension conversion overflow (AI:344) | M12, R-1 | Y (error) | Silent in memory.md | Size and dimension conversions at native boundaries are checked; failure is the M2 recoverable error kind with a distinct tag, never a wrapped value. |
| EC4-47 | Size arithmetic | `zeros([a, b, c], f32)` where `a * b * c * 4` wraps `usize` | Ordinary `*` wraps (L5) | M2, R-1 | Y (error) | **Silent** | Contract gains: tensor byte counts come from checked multiplication only; overflow is a recoverable error before any allocation. |
| EC4-48 | Zero-size tensors | `zeros([0, 128], f32)`; empty final batch | Zero-byte allocation | 5, 7 | N | Silent | Zero-element tensors own no storage; planner assigns no slot; kernels are not called with zero dims (some BLAS reject them). |
| EC4-49 | Checkpoint save | `save_checkpoint(path, model, opt, rng, loader_pos)` | Copies out (synthesis item 10) | M11, M7 | N | Covered (copies out) | Save reads values; no view of live storage escapes into the writer. |
| EC4-50 | Checkpoint partial write | Crash or disk full mid-save | Corrupt file replaces good one | M7, G8 | Y | Silent | Write to a temporary file, flush, then rename; failure leaves the prior checkpoint intact. |
| EC4-51 | Checkpoint load peak | `model = load_checkpoint(path)` on a model already in memory | Build new then drop old: 2x parameter peak (fable) | 4, 6 | Y (peak) | Silent | Two-phase load: validate header, shapes and byte ranges against existing storage first (no allocation), then read directly into uniquely owned existing storage. Only if validation fails nothing is changed. A read error during the data phase leaves the model marked invalid and returns an error. |
| EC4-52 | Checkpoint load, stale ids | Grok: "all tensor ids invalid after load" | Under value semantics there are no ids | M11 | N | **Contradicts** advisor model (session ids) | Record that memory.md uses values, so ids-into-session from advice-grok do not apply. Loaded values replace old values; old saved values cannot exist because load requires no live tape (M14). |
| EC4-53 | Load in a fresh process | All parameter sizes known only after reading the header | Layer 7 cannot precompute the model plan | 7, M17 | N | Silent | Model extent storage planned at run time after header validation, same planner as M17. |
| EC4-54 | Memory-mapped weights | Inference loads safetensors-style file by mmap (GLM R-6) | Storage owned by the mapping, read-only | M12 | N | Silent | Mapped tensors are values whose storage is a read-only owned handle; the first write materializes a heap copy. Mapping lives in the process or session extent. |
| EC4-55 | Data loader buffer | Loader reuses one decode buffer per batch; first layer saves the input batch | Next batch overwrites saved input if tape still live | 2, 6 | N | Covered if loader returns values | Loader returns a value; layer 6 may reuse the buffer only if the previous batch is dead, which M14 (tape consumed) makes provable. |
| EC4-56 | Prefetch across iterations | Batch for iteration i+1 prepared during iteration i | Value surviving an iteration | 4 | N | Covered (loop-carried value) | Loop-carried values are placed in the enclosing extent; test with flat memory. |
| EC4-57 | Loader in a task | Worker task decodes batches and sends them on a channel | M10 move; queued values outlive the sender's extent | M10, 3 | N | Ambiguous (queued value after worker join) | Sent values are placed in the channel's extent (receiver side), not the worker's task extent (LF send-commit table). |
| EC4-58 | Parameters shared with a task | Eval task reads `model` while training loop writes it | M10: no sharing without move | M10 | Y | Covered (reject) | Offer explicit `snapshot := model` then move `snapshot`; M8 reports the copy size. |
| EC4-59 | Tape across tasks | Forward in task A, `backward` in task B | Tape extent crosses tasks | M10, M11 | Y | Silent | Reject: tensors with autodiff history cannot be sent (same rule as EC4-20). |
| EC4-60 | Concurrent kernels | Two tasks call GEMM at once | Memory fine; threading hazard (GLM R-4) | M12, G7 | N | Out of memory scope | Cross-reference R-4; memory plan only guarantees distinct output storage per task. |
| EC4-61 | OOM mid-step | P8 | Recoverable error, partial tape and activations | M2, 4 | Y | **Ambiguous** | Tensor library calls that can fail return an error; the enclosing step extent must be a call or block whose exit on the error path runs the extent reset before the error reaches the caller. |
| EC4-62 | OOM back-off retains arena | P8 with arena sized for the failed shape | Retry fails again | 5, 7, M2, M17 | Y | **Silent** | On the out-of-memory error path, step arenas return storage to the system allocator before the error is delivered. |
| EC4-63 | OOM in ordinary values inside tensor code | `names.append(label)` or tape-node growth during a step | M2: ordinary values stop the program; tensor calls recover | M2 | Y | **Ambiguous** (tape growth is not a user call; `List` in a step is ordinary) | Classify by storage owner, not by call site: any allocation in a step extent (tape, activations, planner arena, lists created inside the step) is recoverable when the step body can return the error; allocations outside step extents stop the program. |
| EC4-64 | OOM inside native library | OpenBLAS internal buffer pool exhausted terminates process (GLM 2.4) | M2 recoverable promise broken by the library | M12, M2 | Y | Silent | M2 recoverability applies only to storage A7 allocates. Native libraries are configured so they do not allocate (user-provided scratchpads) or the limitation is documented. |
| EC4-65 | Tensors in structs | `Block :: struct { attn: Attention, mlp: Mlp }` updated by `ref` | Field update in place | 2, 6 | N | Covered | No rule change. |
| EC4-66 | Tensors in collections | `layers: List(Linear)`; `for i: usize ... { layers[i].w = layers[i].w - lr * g[i] }` | Element update while iterating by index | 2, 6, M13 | N | Covered (index, no live slice) | Iteration by index is allowed; iteration by element view with write to the same list is an exclusivity conflict. |
| EC4-67 | Layout of records with tensors | `List(Linear)` where `Linear` holds two tensors | Layer 8 may apply structure-of-arrays | 8 | N | Silent | Tensor payload storage is never split or moved by layer 8; only the fixed-size descriptor fields may be. Native boundary exemption covers tensor storage. |
| EC4-68 | Truncated backprop through time | Hidden state `h` carried across steps | `h` carries history (EC4-20) | 3, 4 | Y | Silent | Same as EC4-20: carrying requires `detach(h)`; diagnostic suggests it. |
| EC4-69 | Scalar extraction | `loss.item()` on a 0-dim f32 tensor | Scalar copy; no history | 6 | N | Covered | 0-dim tensors may be stored inline (no heap storage). |
| EC4-70 | Global constant tensor | Positional encoding table computed once, used every step and saved on tapes | Process extent, read-only | 4 | N | Covered | Values in process extent that are saved on a tape are never copied; tape stores the identity. |
| EC4-71 | Function returning activations | `h := block_forward(m, x)` returns tensors and their tape nodes | Escape into the caller's step extent | 3, 4 | N | Covered by escape analysis, tape not mentioned | Escape summaries include "carries tape nodes"; tape nodes follow the returned value's extent. |
| EC4-72 | Integer tensors | Token ids and labels need `Tensor(usize)` or `Tensor(i64)` | L11 lists only float dtypes | G8 | Y | Silent (ledger scope) | G8 must name an index dtype; memory planning treats it like any dtype. Recommend `usize` per A7 index rule. |

Count: 72 edge cases.

## 3. Plan gaps and contradictions, with fixes

G-1. **Share-until-changed vs saved-value rejection.** memory.md section 2 ("shares storage
until either side changes") makes P1 correct with a copy, while corpus 8 ("Reject or
report before execution") and contract item 7 make it a conflict. Fix: add gate M15
(section 4) and change corpus 8's expected result to "Per M15". Also note that the
advisors' version-counter fallback (advice-fable, advice-grok, AI:294) is run-time
bookkeeping not listed in contract item 4. Either add "saved-value version tests where
they cannot be proven away" to item 4, or state that v1 rejects may-save conflicts
statically.

G-2. **"Tape release" is memory vocabulary with no source construct.** Corpus 9 says
"weight update after tape release". Fix: add gate M14 with "`backward(loss)` consumes the
recorded computation of `loss`", and rewrite corpus 9 as "Training step with weight
update after `backward`: accept; step memory reused".

G-3. **"Views are temporary" (M11, M13) vs saved views on the tape.** Attention saves
reshaped and transposed tensors. Fix M11 text: "Views bound in source are temporary. The
tape may retain the base storage of a view with its descriptor; that retention ends
when the tape is consumed."

G-4. **Extent names are inconsistent.** Contract item 5 lists "function call, loop
iteration, task, training step or the process"; M11 adds "session"; P5 (accumulation)
and P6 (generation) need an extent between iteration and session. Fix: state the tensor
extent hierarchy as inferred (never written): process, then session (parameters, masters,
moments, RNG, scaler, plan cache), then optimizer step (accumulators), then iteration or
microbatch (activations, tape), then call. State how each is identified: session is the
extent of the value holding parameters; optimizer step is the extent of the loop
containing the parameter write; microbatch is the extent containing `backward`.

G-5. **Autodiff history escaping its extent is unaddressed** (P4, EC4-20, EC4-59,
EC4-68). This is the most common real-world training memory leak. Fix: add to M11
"A value with recorded history cannot leave the extent that owns its tape; the diagnostic
offers `item()` or `detach`." Add this program to the phase A corpus.

G-6. **Parameter identity (tied weights) is inexpressible in value semantics** (P3,
EC4-34). Fix: gate M16. Without it the L10 decoder recipe must avoid tied weights, which
must be recorded in G8.

G-7. **Corpus 12 wording is too coarse and misses the compiler-made hazard.** Fix:
replace "Native kernel given overlapping buffers: Reject" with "Native kernel output
overlapping an input: reject in source; never produced by layer 6 reuse unless the
kernel descriptor permits in-place. Read-only input overlap: accept."

G-8. **Layer 7 assumes static shapes.** Contract item 3 allows dynamic sizes but layer 7
("pack buffer lifetimes within an extent") has no dynamic story; fable's run-time
per-shape planner is not in memory.md. Fix: gate M17 and a layer 7 note: "Static plans
where shapes are static; a deterministic run-time planner keyed by shape signature
otherwise, with a bounded plan cache."

G-9. **M2 recoverable out-of-memory lacks extent semantics** (P8, EC4-61 to EC4-64). Fix
M2 text: "Recoverability is decided by the owning extent: allocations in a step extent
report a recoverable error that ends the step extent (storage returned to the system
allocator) before the caller observes the error. Native library internal allocation is
outside this promise." Reconcile with GLM R-8 ("`defer` cleanups run"), which assumes
`del`-era cleanup, and with M7.

G-10. **Checked size arithmetic is missing from the memory contract.** GLM R-1 and AI:378
require checked byte counts and checked BLAS dimension conversion. memory.md mentions
neither, and contract item 4 lists no size checks. Fix: add to contract item 4
"checked size and dimension conversions" and link R-1 as a phase F exit condition.

G-11. **M12 "borrow for the call" vs forward-to-backward workspaces** (EC4-43). Fix M12:
"A kernel descriptor may declare an output workspace; it is a saved value owned by the
tape."

G-12. **Mixed-precision transactional update is not stated** (EC4-31). Fix: add to phase
F exit "a skipped or failed optimizer step leaves all model-extent values bit-identical",
and the rule "no parameter write before the non-finite check and optimizer workspace
reservation both succeed."

G-13. **Phase F exit is too narrow.** It lists corpus 8, 9, 11, 12 and the README AI
scenarios. Missing: P3, P4, P5, P6, P8, checkpoint load peak (EC4-51), variable shapes
(EC4-40, EC4-41), recomputation if in v1. Fix: add these as corpus programs 16 to 23.
Phase F also depends on G8, which memory.md does not name.

G-14. **Advisor tensor models contradict memory.md.** advice-grok proposes `TensorId` into
a session and explicit `tensor_release_graph`; advice-fable says tape nodes reference
tensors by handle. Both carry memory vocabulary into source (L19) and, for grok, stale ids
after reload. memory.md section 2 chose values. Fix: record in memory.md that T1 "session
ownership" is an inferred extent, not a user-visible session object or id type.

G-15. **SPEC section 9 defects that block the plan** (track 0 additions): `Tensor.data: ref T`
is a stored reference (contradicts M4); `tensor_view` and `tensor_flatten` "share memory"
as storable values (contradicts M13); `tensor_save` returns `bool` (cannot express R-6
rejection or EC4-50); `axis: -1` uses a negative index (contradicts the `usize` rule;
needs a separate axis convention); `tensor_no_grad { ... }` introduces tape vocabulary
without a lifetime rule; `@prefetch(a.data, ...)` exposes storage.

G-16. **Recomputation has no effect-system hook.** Layer 0 lists "effect summaries" but
not the "pure except RNG" property recomputation needs (notes G 2.3). Fix: name the
property in layer 0 if M18 selects recomputation for v1.

G-17. **Generation-time plans and KV cache capacity** (P6, EC4-37, EC4-41): tensors have no
reserved-capacity concept, so either M13 rejects the natural cache or copies grow
quadratically. Fix: gate M19.

## 4. New gate questions

| Gate | Question | Recommendation |
| --- | --- | --- |
| M14 | Tape lifetime: does `backward(loss)` consume the recorded computation, or does the tape live to the end of the step extent, or is a persistent tape available? | Consume on `backward`. Two losses use one multi-loss `backward`. Persistent tape deferred. |
| M15 | Changing a value that a live tape saved: accept with copy (section 2 semantics) or reject as exclusivity conflict (contract 7, corpus 8)? | Reject when may-saved (static, joined over branches). No run-time version counter in v1. Revisit if the corpus shows many rejections. |
| M16 | Parameter identity: how are tied or shared parameters expressed without stored references? | One parameter table per model; fields hold `usize` parameter indices where tying is needed; ordinary untied models keep tensor fields. |
| M17 | Dynamic-shape planning: run-time planner per shape signature, bucketing, plan-cache bounds, arena shrink on out-of-memory? | Run-time deterministic planner; cache bounded by count and bytes; power-of-two sequence buckets; arenas shrink on the out-of-memory error path. |
| M18 | Activation recomputation in v1? If yes, which effects are allowed in a recomputed region and how RNG is captured? | Defer unless the L10 decoder does not fit the qualification host; if included, "pure except captured RNG value". |
| M19 | Tensor capacity: may a tensor reserve rows beyond its length so appends do not invalidate views over existing rows? | Yes for the leading axis only; views cover only rows below the length at view creation; growth beyond capacity with a live view is a conflict. |
| M20 | Autodiff history escaping its extent (loss accumulation, TBPTT, sending across tasks). | Reject with rewrite to `item()` or `detach`. |
| M21 | Out-of-memory classification: by call site (M2 today) or by owning extent? | By owning extent (G-9). |
| M22 | Checkpoint load strategy: build-then-swap (2x peak) or validate-then-write-in-place? | Validate-then-write-in-place for same-shape loads; build-then-swap only when shapes change. Temp-file-then-rename for save. |

## 5. Questions for GLM (memory safety and security, L12)

1. If M15 selects static rejection, is a may-save analysis joined over branches sound
   given the current fact-engine defects (MS-1, MS-2)? Which counterexample would let a
   saved value be overwritten without a diagnostic?
2. Layer 6 reuse feeding native kernels (EC4-44): what descriptor fields and backend-plan
   checks are needed so an input buffer is never chosen as a BLAS or oneDNN output,
   including after fusion (R-9)?
3. Run-time shape planner (M17): dataset-controlled sequence lengths and batch sizes
   select plans. What bounds on plan count, arena bytes and planning time prevent a
   resource-exhaustion input? Should the plan cache key include dtype and device?
4. Validate-then-write-in-place checkpoint load (M22): does any failure after the data
   phase starts leave a model that later code can use without noticing? Is marking the
   model invalid enough, or must load always be all-or-nothing with a 2x peak?
5. Memory-mapped weights (EC4-54): risks when the file changes or truncates under a live
   mapping (SIGBUS), and whether mapped storage is acceptable under contract item 2.
6. Out-of-memory back-off (EC4-62): is returning arena storage on the error path safe when
   a native library still holds a scratchpad pointer from the failed call (oneDNN
   library scratchpad mode, R-4)?
7. Does restricting M2 recoverability to A7-allocated storage (EC4-64) conflict with R-8,
   and which native library settings make kernel-internal allocation impossible?
8. Tape extents with retained workspaces (EC4-43): can a workspace outlive the primitive
   or engine that produced it, and what must the descriptor record to make that a
   compile-time or backward-time error?
9. Autodiff history across tasks (EC4-59): is rejecting send of values with history
   sufficient, or can a detached value still alias tape-owned storage through layer 6
   sharing?
10. Checked size arithmetic (EC4-46, EC4-47): should the compiler reject any tensor
    allocation whose byte count is not produced by the checked path, even in Debug where
    Zig would trap, so ReleaseFast and Debug behave identically?

## 6. Limits of this audit

- Hand traces only; no program was compiled or executed.
- The proposed tensor surface in the snippets is invented for illustration and is not a
  syntax proposal.
- External framework behavior is taken from the repository research reports, not
  re-verified.
- No snippet uses parsed-only forms (destructuring, variadics, intrinsics other than
  `@type_set`).
