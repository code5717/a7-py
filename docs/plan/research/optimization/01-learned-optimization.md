# What already works: measured optimization, and what each technique costs

Report 01 of the [context-aware and AI-assisted optimization research
programme](README.md). Written 2026-09-19.

The question: which automated optimization techniques have shipped, what did
their implementers *measure*, and what does each one cost to adopt? This is the
evidence base for concept
[C12, "search with a verifier"](../CONCEPTS.md), and the ground under the user's
request for a compiler that understands the hardware and emits the best code for
it (`tmp/research/optimization/claims.md`).

**The answer, up front.** Every technique below is a search, and they differ in
one property: what decides whether a candidate is admissible. That property, not
the search, is what determines the gain, the cost and whether the output can be
trusted. Three families exist, and they are not interchangeable.

- **Search over a space where every point is correct by construction.** PGO,
  MLGO, Halide, TVM, Ansor. The proposer picks a pass list, an inline decision,
  a loop schedule — never an instruction. Correctness comes free because the
  compiler applies the choice. Measured gains: 2–14% (Go's own figure for PGO),
  3.7–5.9% size (MLGO inlining), 1.37×–2.29× (Halide's autoscheduler), up to
  3.8× (Ansor on a tensor program). The cost is a profile, a training corpus or
  hours of search per program per machine.
- **Search over a space where a checker decides.** Souper (an SMT solver),
  equality saturation (rewrite rules assumed sound), translation validation
  (per-compilation proof). These can propose an arbitrary instruction sequence
  because something rejects the wrong ones. Measured: Souper shrank a Clang
  binary by 4.4%, and made it 2% *slower*; the first build took 86 minutes
  against 8.
- **Search where a test suite decides.** STOKE, AlphaDev, and every LLM result
  in the planned report 03. AlphaDev's sorting networks reached
  libc++ and are checked by "exhaustive tests", not a proof.

The largest single-technique number in the whole literature is BOLT's: up to
20.4% on GCC and Clang binaries *on top of* FDO and LTO. It is also the
technique that needs the least from the language — it works on a linked binary.

**For A7 specifically, three things were measured on this machine** (full log in
`tmp/research/optimization/measurements.md`):

1. `zig build-exe --help` on Zig 0.16.0 contains the string "profile" **zero
   times**. There is no PGO for Zig-language code at the driver A7 uses.
2. `--emit-relocs` does work on an A7-produced binary (9 RELA sections), which
   is BOLT's documented precondition. `llvm-bolt` is not installed here, so BOLT
   was not run.
3. A complete instrumented-PGO loop *can* be run on A7 output, through
   `-femit-llvm-bc` and a matching-version clang, after working around three
   separate toolchain collisions. On the benchmark tried it produced no
   measurable gain, because that benchmark has nothing PGO can improve.

**Not covered here.** Whether a language should accept "game", "kernel" or
"safety-critical" as a compiler input is report 02. Language models proposing
transformations, and the verification behind them, is
the planned report 03; this report stops at the classical
techniques it cites. Numeric determinism as a language decision is
[`runtime-model/00-claims-audit.md`](../runtime-model/00-claims-audit.md) §C1.

**Sources.** Every quotation below was fetched with `curl` to
`tmp/research/optimization/sources/` on 2026-09-19 and quoted from the local
copy; `tmp/research/optimization/manifest.txt` lists each URL, the date and the
local file with its HTTP status. PDFs were converted with `pdftotext`, HTML with
`pandoc`. Nothing here is quoted from a search snippet or a summarizing fetch.
Local measurements, with the exact commands, are in
`tmp/research/optimization/measurements.md`; the programs and binaries are under
`tmp/research/optimization/measure/`.

Two words are used strictly. **Measured** means the source reports a number it
obtained by running something. **Claimed** means the source asserts a number
without showing the measurement, or the measurement is of the vendor's own
product on the vendor's own workload. A vendor benchmark is not a measurement.

---

## 1. Profile-guided optimization

### 1.1 What it is, and the gain its implementers report

PGO feeds a record of one execution back into the next compilation. Go's own
documentation states both the mechanism and the number (<https://go.dev/doc/pgo>,
read 2026-09-19):

> Profile-guided optimization (PGO), also known as feedback-directed
> optimization (FDO), is a compiler optimization technique that feeds
> information (a profile) from representative runs of the application back into
> to the compiler for the next build of the application, which uses that
> information to make more informed optimization decisions. For example, the
> compiler may decide to more aggressively inline functions which the profile
> indicates are called frequently.

> As of Go 1.22, benchmarks for a representative set of Go programs show that
> building with PGO improves performance by around 2-14%. We expect performance
> gains to generally increase over time as additional optimizations take
> advantage of PGO in future versions of Go.

That is the Go team measuring Go programs, so it is a vendor number by the rule
above — but it is stated as a range with a floor, on a named version, which is
unusually honest for a vendor figure. Take 2–14% as the order of magnitude a
mature PGO implementation delivers on ordinary application code.

### 1.2 The operational cost is representativeness, and it is not small

The Go documentation is explicit that the profile, not the compiler, is the hard
part:

> For best results, it is important that profiles are representative of actual
> behavior in the application's production environment. Using an unrepresentative
> profile is likely to result in a binary with little to no improvement in
> production. Thus, collecting profiles directly from the production environment
> is recommended, and is the primary method that Go's PGO is designed for.

And that the obvious substitute does not work:

> If it is difficult or impossible to collect from the production environment
> (e.g., a command-line tool distributed to end users), it is also possible to
> collect from a representative benchmark. Note that constructing representative
> benchmarks is often quite difficult (as is keeping them representative as the
> application evolves). In particular, microbenchmarks are usually bad candidates
> for PGO profiling, as they only exercise a small part of the application, which
> yields small gains when applied to the whole program.

This is the sentence that decides whether PGO is available to a language at all.
A language whose users ship command-line tools and libraries, rather than
long-running services the author operates, has no natural source of a
representative profile. A7 is in that category today.

Two further costs the same document names, both of which are consequences of
running PGO more than once:

> Go PGO is generally robust to skew between the profiled version of an
> application and the version building with the profile, as well as to building
> with profiles collected from already-optimized binaries. This is what makes
> this iterative lifecycle possible.

> Iterative stability is the prevention of cycles of variable performance in
> successive PGO builds (e.g., build #1 is fast, build #2 is slow, build #3 is
> fast, etc). We use CPU profiles to identify hot functions to target with
> optimizations. In theory, a hot function could be sped up so much by PGO that
> it no longer appears hot in the next profile and does not get optimized, making
> it slow again. The Go compiler takes a conservative approach to PGO
> optimizations, which we believe prevents significant variance.

Read that carefully: iterative stability is not a property PGO has, it is a
property the Go team *bought* by making its PGO optimizations conservative. The
cost of a stable feedback loop is paid in the gain.

And the failure mode when a profile stops matching:

> When adding new code or enabling new code paths with a flag flip, that code
> will not be present in the profile on the first build, and thus won't receive
> PGO optimizations until a new profile reflecting the new code is collected.

### 1.3 PGO is not reachable through the compiler A7 uses

**Measured, 2026-09-19, Zig 0.16.0** (measurements.md M1). `zig build-exe --help`
contains the string "profile" zero times. The flags it does offer that are
adjacent to this territory are `-flto`, `-fstrip`, `--emit-relocs`,
`-femit-llvm-ir`, `-femit-llvm-bc` and `-fopt-bisect-limit`. The bundled
`zig cc` — clang 21.1.0 — has the whole clang PGO surface
(`-fprofile-generate`, `-fprofile-use`, `-fprofile-instr-generate`), but that is
the C front end, and A7 emits Zig.

So PGO for an A7 program requires leaving the Zig driver. **That is possible,
and it was done here** (measurements.md M8). The sequence that worked:

    zig build-exe bench2.zig -OReleaseFast -lc \
        -femit-llvm-bc=bench2c.bc -femit-bin=bench2c.tmp
    clang -O3 -fprofile-generate bench2c.bc -o bench2.instr3
    LLVM_PROFILE_FILE=b2b.profraw ./bench2.instr3
    llvm-profdata merge -output=b2b.profdata b2b.profraw
    clang -O3 -fprofile-use=b2b.profdata bench2c.bc -o bench2.pgo

Both binaries print the same answer as the ordinary `zig build-exe -OReleaseFast`
build. Three collisions had to be worked around first, and each is an adoption
cost rather than a curiosity:

1. `zig cc -fprofile-generate bench2.bc` fails with `duplicate symbol: _start`
   — glibc's `crt1.o` against Zig's `std/start.zig:190` — unless the module is
   built with `-lc` so Zig takes the libc entry path.
2. Linking the clang profile runtime produces the `__llvm_prf_cnts` and
   `__llvm_prf_names` sections but writes **no** `.profraw`: the runtime's
   registration symbols are never pulled out of the archive. `-u__llvm_profile_runtime`
   fixes it. Without that flag the counters increment into a void, and nothing
   tells you.
3. `zig cc -fprofile-use` on a profile indexed by the host `llvm-profdata` fails
   with `unsupported instrumentation profile format version`. Zig 0.16.0 bundles
   clang 21.1.0; the host tools here are LLVM 22.1.8; `llvm-profdata merge` has
   no version-downgrade flag. The loop completes only by using the host clang
   for *both* halves, which means the shipped binary is no longer built by Zig.

The gain measured on that benchmark was nil — `bench2.noPGO` min 0.0254 s
against `bench2.pgo` min 0.0249 s, n=7. That is a statement about the
benchmark, which is a single hot loop with no branch-layout or inlining
opportunity, and not about PGO. The reachability result is the useful one.

---

## 2. Post-link optimization: AutoFDO and BOLT

### 2.1 AutoFDO: sampling instead of instrumenting, and staleness by design

Instrumented PGO requires a special build and a special run. AutoFDO replaces
both with hardware performance counters on the production binary. From the
authors' own abstract (Chen, Li, Moseley, CGO 2016,
<https://research.google/pubs/autofdo-automatic-feedback-directed-optimization-for-warehouse-scale-applications/>,
read 2026-09-19):

> AutoFDO is a system to simplify real-world deployment of feedback-directed
> optimization (FDO). The system works by sampling hardware performance monitors
> on production machines and using those profiles to guide optimization. Profile
> data is stale by design, and we have implemented compiler features to deliver
> stable speedup across releases. The resulting performance is a geomean of 10.5%
> improvement on our benchmarks. AutoFDO achieves 85% of the gains of traditional
> FDO, despite imprecision due to sampling and information lost in the
> compilation pipeline. The system is deployed to hundreds of binaries at Google,
> and it is extremely easy to enable; users need only to add some flags to their
> release build. To date, AutoFDO has increased the number of FDO users at Google
> by 8X and has doubled the number of cycles spent in FDO-optimized binaries.
> Over half of CPU cycles used are now spent in some flavor of FDO-optimized
> binaries.

Two numbers matter and one phrase matters more. The numbers: **10.5% geomean**,
and **85% of instrumented FDO's gains**. The phrase is "**Profile data is stale
by design**" — AutoFDO's whole premise is that you accept a profile from a
*different, older* binary, and that this costs you 15% of the available gain in
exchange for the profile being free to collect. That trade is what made FDO
deployable at all: adoption went up 8×.

This is a measurement of Google's system on Google's benchmarks, reported by its
authors. It is the strongest evidence available and it is still a first-party
number.

### 2.2 BOLT: the largest published gain, on top of everything else

BOLT rewrites a *linked binary*. Panchenko, Auler, Nell and Ottoni state
(arXiv:1807.06735v2, <https://arxiv.org/abs/1807.06735>, read 2026-09-19):

> In this paper, we present BOLT, a post-link optimizer built on top of the LLVM
> framework. Utilizing sample-based profiling, BOLT boosts the performance of
> real-world applications even for highly optimized binaries built with both
> feedback-driven optimizations (FDO) and link-time optimizations (LTO). We
> demonstrate that post-link performance improvements are complementary to
> conventional compiler optimizations, even when the latter are done at a
> whole-program level and in the presence of profile information. We evaluated
> BOLT on both Facebook data-center workloads and open-source compilers. For
> data-center applications, BOLT achieves up to 8.0% performance speedups on top
> of profile-guided function reordering and LTO. For the GCC and Clang compilers,
> our evaluation shows that BOLT speeds up their binaries by up to 20.4% on top
> of FDO and LTO, and up to 52.1% if the binaries are built without FDO and LTO.

The "on top of" is the load-bearing phrase and it is the one readers drop. 20.4%
is not BOLT against `-O2`; it is BOLT against a binary that already had FDO and
LTO applied. The 52.1% figure is BOLT against an unoptimized-pipeline binary and
is not comparable to the first.

BOLT's precondition is a linker flag (paper §3.2, saved PDF):

> A second and more ambitious mode was later added to operate by changing the
> position of all functions in the binary. While multiple approaches were
> considered, the most obvious and straightforward one was to rely on relocations
> recorded and saved by the linker in an executable. Both BFD and Gold linkers
> provide such an option (`--emit-relocs`). However, even with this option, there
> are still some missing pieces of information. An example is the relative
> offsets for PIC jump tables which are removed by the linker.

**Measured here (M2): `zig build-exe --emit-relocs` works on an A7-produced
binary and yields 9 RELA sections.** BOLT's stated precondition is therefore
satisfiable for A7 output today. Whether `llvm-bolt` actually succeeds on a Zig
binary was not tested — `llvm-bolt` is not installed on this machine and `perf`
is not either, so a profile could not be collected. That gap is named, not
filled.

BOLT's own cost is not stated as a number in the paper; what the paper does say
is that the pipeline disassembles the whole binary, rebuilds a CFG per function,
and re-emits — so the cost scales with binary size, not source size, and it
requires the binary's debug and exception information to be rewritten
consistently (§3.4).

### 2.3 Where the three disagree

They do not, much, and that is itself informative. Go reports 2–14% for
compile-time PGO on Go programs; AutoFDO reports 10.5% geomean for sampled FDO
on C++ data-center binaries; BOLT reports up to 8% *further* on data-center
binaries that already had FDO. The consistent picture across three independent
groups is that profile feedback is worth roughly ten percent, that most of it is
code layout, and that the layout part survives being applied last, at the binary
level, after everything else.

---

## 3. Machine learning in a shipping compiler: MLGO

### 3.1 What it replaced

MLGO is in upstream LLVM. Trofin, Qian, Brevdo, Lin, Choromanski, Li and the
rest state the scope precisely (arXiv:2101.04808,
<https://arxiv.org/abs/2101.04808>, read 2026-09-19):

> We propose MLGO, a framework for integrating ML techniques systematically in an
> industrial compiler -- LLVM. As a case study, we present the details and
> results of replacing the heuristics-based inlining-for-size optimization in
> LLVM with machine learned models. To the best of our knowledge, this work is
> the first full integration of ML in a complex compiler pass in a real-world
> setting. It is available in the main LLVM repository. We use two different ML
> algorithms: Policy Gradient and Evolution Strategies, to train the
> inlining-for-size model, and achieve up to 7\% size reduction, when compared to
> state of the art LLVM -Oz.

What was replaced is a threshold comparison, and the paper describes the
displaced heuristic in enough detail to see how little of the compiler the model
touches (§2, saved PDF):

> The compiler first computes the static "cost" of the callee post inlining by
> traversing the callee body simulating post-inline cleanup passes. If some call
> site arguments are known to be constant at compile time, that information is
> used to evaluate what instructions / basic blocks would be simplified, should
> the inlining be carried out. The computed cost is then compared with a
> threshold.

### 3.2 The guideline that makes it safe, stated by its authors

This is the single most important sentence in the MLGO paper for anyone
considering a model inside a compiler (§3.1, guideline 1):

> To maintain correctness guarantees, we replace heuristics, not
> semantics-preserving code. For example, we change the decision making process
> for carrying out function inlining, not how the inlining action is implemented.

That is concept C12 with the search removed from the trusted path entirely. The
model does not emit code. It emits a decision that the compiler's existing,
tested inlining machinery then carries out. A wrong decision produces slow or
large code, never wrong code.

### 3.3 How a model stays reproducible inside a build

The same section answers the reproducibility question directly, and the answer
is architectural, not procedural (§3.1, guideline 2):

> 'Online' training - meaning, training while the compiler is executing in
> production - is an anti-goal for us: it would hurt determinism and compilation
> performance. Instead, policy training happens offline. Trained policies are
> embedded in the compiler as statically linked native code, and the resulting
> compiler is subjected to the same release process it currently is. Build and
> release infrastructures and pipelines of targets using the compiler do not need
> to be changed. Build determinism using the ML-enabled compiler is ensured
> because the policies are fixed - no training happens when the compiler runs,
> only inference.

The mechanism has a name and a CMake file. From the LLVM documentation
(<https://llvm.org/docs/MLGO.html>, read 2026-09-19):

> **ReleaseModeModelRunner.** This is intended for inference scenarios. This uses
> the rules defined in `llvm/cmake/modules/TensorFlowCompile.cmake` to convert, at
> the time the compiler is built, TensorFlow Saved Models into a header (.h) and
> native object (.o). The latter is a CPU-based implementation of the neural
> network, together with its weights (essentially, loops performing matrix
> multiplications)

So the shipped compiler contains no model file, no inference runtime and no
network call. It contains a `.o` full of matrix multiplications with constant
weights. Running it twice on the same input gives the same answer for the same
reason any other compiler pass does. The same page names the other three
runners, and marks one of them as explicitly not for production:

> **InteractiveModelRunner.** This is intended for training scenarios where the
> training algorithm drives compilation. This model runner has no special
> dependencies, and relies on I/O pipes to communicate with a separate process,
> presumably a python training algorithm. We do not envision using this in a
> production environment.

The versioning story is also spelled out, and it is the part a build system
would otherwise get wrong:

> We support a model "knowing" less inputs than the compiler. [...] Since the
> rest of the inputs are still provided, this allows an evolution model where we
> first add features to the compiler and continue using older models without
> regressing. Then, the new compiler can be used to train new models. Deprecating
> features in the compiler involves, then, training first a model without those
> features.

### 3.4 What it measured, and what it cost

Size reduction against `-Oz`, by training algorithm (paper Table 2):

| Policy | Size reduction | Data-collection parallelism | Training time |
| --- | --- | --- | --- |
| Policy Gradient | 4.95% | 100 | ~12 h |
| Evolution Strategies | 3.74% | 488 | ~60 h |
| ES (large) | 5.94% | 488 | ~150 h |

The abstract's "up to 7%" is the best case over targets; the table is the
per-policy figure on the training application. Compilation overhead (§6.1):

> For the current model, we observed 0.65% increase in memory utilization at
> run-time. When inlining a large IR module ( 33MB), we measured a 10% increase
> in inlining time, mostly attributable to feature extraction; since inlining
> tends to represent 10-15% of total compile time, the net contribution of the
> release mode is only 1%. Finally, clang binary size increase due to the
> inclusion of the compiled model was 115KB, representing 0.08% size increase.

That is the whole price: about 1% of compile time and 115 KB of compiler.

### 3.5 Who claims what, on whose workload

Google's own blog post gives the deployment numbers
(<https://research.google/blog/mlgo-a-machine-learning-framework-for-compiler-optimization/>,
read 2026-09-19):

> We trained the inlining-for-size policy on a large internal software package
> containing 30k modules. The trained policy is generalizable when applied to
> compile other software and achieves a 3% ~ 7% size reduction.

> The MLGO inlining-for-size training has been deployed on Fuchsia — a general
> purpose open source operating system designed to power a diverse ecosystem of
> hardware and software, where binary size is critical. Here, MLGO showed a 6.3%
> size reduction for C++ translation units.

> Similar to the inlining-for-size policy, the register allocation
> (regalloc-for-performance) policy is trained on a large Google internal software
> package, and is generalizable across different software, with 0.3% ~1.5%
> improvements in queries per second (QPS) on a set of internal large-scale
> datacenter applications. The QPS improvement has persisted for months after its
> deployment, showing the model's generalizability across the time horizon.

Attribution, plainly: **every MLGO number in circulation is Google measuring
Google's models on Google's or Fuchsia's code.** No independent replication was
located during this research. The numbers are specific, the mechanism is in
upstream LLVM and can be inspected, and the framework is honest about its own
overhead — but the gains have one source.

Note the asymmetry between the two deployed models. Inlining-for-size: 3–7%,
6.3% on Fuchsia. Register-allocation-for-performance: **0.3–1.5% QPS**. The
performance model, on the harder problem, buys roughly a fifth of what the size
model buys. That ratio is worth remembering whenever someone proposes learned
optimization for speed.

---

## 4. Autotuning and schedule search

### 4.1 The ancestors: ATLAS and FFTW

Neither is machine learning and both are the same idea. ATLAS (Whaley and
Dongarra, LAWN 131,
<https://www.netlib.org/lapack/lawnspdf/lawn131.pdf>, read 2026-09-19) generates
matrix-multiply kernels and times them:

> This section of code is automatically created by a code generator which uses
> timings to determine the correct blocking and loop unrolling factors to perform
> an optimized on-chip multiply. The user may directly supply the code generator
> with as much detail as desired (i.e., the user may explicitly indicate the L1
> cache size, the blocking factor(s) to try, etc); if such details are not
> provided, the generator will determine appropriate settings via timings.

The search is a nested sweep, results are cached to disk, and the cost is stated:

> All results are stored in files, so that subsequent searches will not repeat
> the same experiments, allowing searches to build on previously obtained data.
> This also means that if a search is interrupted (for instance due to a machine
> failure), previously run cases will not need to be re-timed. A typical install
> takes from 1 to 2 hours for each precision.

**One to two hours per precision, per machine, at install time.** That is the
price of a hardware-specific kernel obtained by search, set in 1997, and it has
not changed much.

FFTW (Frigo and Johnson, *Proc. IEEE* 93(2), 2005,
<https://www.fftw.org/fftw-paper-ieee.pdf>, read 2026-09-19) moves the search to
run time:

> The FFTW planner works by measuring the actual run time of many different plans
> and by selecting the fastest one.

> FFTW provides a mode of operation where the planner quickly returns a
> "reasonable" plan that is not necessarily the fastest.

That second sentence is FFTW's "estimate mode", and it exists because the
planner's own cost is sometimes larger than the transform's. The paper reports
that estimate mode "imposes median and maximum speed penalties" relative to the
measuring planner — the trade is explicit and user-selectable. The general
lesson for any search-based optimizer: it needs a cheap mode, because the search
cost lands on someone.

### 4.2 Halide: beam search over schedules with a learned cost model

Adams et al. (SIGGRAPH 2019,
<https://halide-lang.org/papers/halide_autoscheduler_2019.pdf>, read 2026-09-19)
state the result:

> We show that this approach operates effectively with or without autotuning. It
> produces schedules which are on average almost twice as fast as the existing
> Halide autoscheduler without autotuning, or more than twice as fast with, and
> is the first automatic scheduling algorithm to significantly outperform human
> experts on average.

The measured figures on a hundred unseen random pipelines (Fig. 6 caption):

> Our algorithm operating in fast greedy mode is on average 1.37 times faster
> than the master autoscheduler. With beam search, our system is 2.29 times
> faster. The dynamic range is high — we are sometimes more than ten times faster,
> and sometimes less than half the speed.

"Sometimes less than half the speed" is the honest half of that sentence, and it
is the general property of learned cost models: they are good on average and
have a tail.

### 4.3 Does a learned schedule transfer to another machine?

Here the sources disagree, and the disagreement is the finding.

**Halide says it transfers for ordering, and not for a new architecture.** The
cost model is trained on Xeons and evaluated on a desktop, and that is fine
(Fig. 7 caption):

> The model was trained on a cluster of Intel Xeon servers in a managed Linux
> environment, yet these runtimes were measured on a desktop x86 CPU running
> vanilla Ubuntu, so the line of best-fit is slightly off the diagonal. For our
> scheduling algorithm to work we do not need to predict runtimes accurately, we
> just need to put them in the correct order, so minor changes in the target
> architecture are unimportant.

Across an ISA the same model still helps, at a much reduced rate (§6.2):

> We evaluated our x86 model on quad-core Cortex A72 instances available on AWS.
> In greedy mode it is 9% faster than Halide master, and running beam search it
> is 23% faster, despite the fact that these weights were fit to results from
> processors on the opposite end of the performance spectrum. We lack enough ARM
> training samples to date to train network weights specifically for that
> architecture.

9% and 23% on ARM against 37% and 129% on x86 — the model transfers, at roughly
a quarter of its value. And a *new* architecture is not a retrain, it is a
project (§6.2):

> In decoupling the featurization, the search space, and the search algorithm, we
> have designed our system to be adaptable to new architectures by extending any
> of these as necessary. However, this does not mean adding a new architecture is
> a trivial undertaking. Each new architecture requires going through a similar
> bring-up process as we did for x86 CPUs. We must train a cost model on hundreds
> of thousands of fresh random programs, and triage the results to ensure that the
> featurization correctly captures the factors that matter for performance on that
> architecture.

**AutoTVM says transfer is worth 2×–10× of search time.** Chen et al. (NeurIPS
2018, <https://arxiv.org/abs/1805.08166>, read 2026-09-19) built the transfer in
deliberately:

> We learn domain-specific statistical cost models to guide the search of tensor
> operator implementations over billions of possible program variants. We further
> accelerate the search by effective model transfer across workloads.

and measured it (§6.2):

> Overall, using transfer learning yielded a 2× to 10× speedup.

Note what is being transferred and what is not. AutoTVM transfers *across
workloads*, reusing a model trained on one operator to speed up the search for
another on the same hardware. Halide transfers *across machines*. These are
different claims and neither supports the other. Nobody in this literature
claims a schedule found on one machine is optimal on a different one; they claim
the *model* that ranks schedules survives a change of machine, partially.

### 4.4 Ansor: what a search actually costs in wall-clock time

Zheng et al. (OSDI 2020, <https://arxiv.org/abs/2006.06762>, read 2026-09-19)
report the gains:

> We show that Ansor improves the execution performance of deep neural networks
> relative to the state-of-the-art on the Intel CPU, ARM CPU, and NVIDIA GPU by
> up to $3.8\times$, $2.6\times$, and $1.7\times$, respectively.

and, more usefully for a cost discussion, what AutoTVM had to spend to reach the
same point on an Intel CPU (Table 3b, wall-clock seconds):

| Network | AutoTVM | Ansor | Time saving |
| --- | --- | --- | --- |
| ResNet-50 | 39,250 s | 4,540 s | 8.6× |
| Mobilenet-V2 | 58,468 s | 660 s | 88.6× |
| 3D-ResNet | 7,594 s | 2,296 s | 3.3× |
| DCGAN | 4,914 s | 420 s | 11.7× |
| BERT | 12,007 s | 266 s | 45.1× |

AutoTVM spent **16 hours** on Mobilenet-V2. Ansor's own summary of the regime
(§7.4):

> Typically, it takes several hours for Ansor to generate fully-optimized
> programs for a DNN on a single machine. This is acceptable for inference
> applications because it is a one-shot effort before deployment.

"Acceptable ... because it is a one-shot effort before deployment" is the
condition under which schedule search is viable at all, and it does not describe
a compiler. It describes a deployment step for a program that will run
unchanged, on known hardware, for a long time. A general-purpose compiler cannot
spend hours per program.

Ansor's cost model quality, for the record (§7.5): "0.079 RMSE, 0.958 R2
correlation, 0.851 pairwise comparison accuracy, and 0.624 recall@30 of top-30
programs" on 25,000 measured programs.

---

## 5. Equality saturation and rewriting against a fixed pass pipeline

### 5.1 egg, and what it actually sped up

Willsey, Nandi, Wang, Flatt, Tatlock and Panchekha (POPL 2021,
<https://arxiv.org/abs/2004.03082>, read 2026-09-19) describe the mechanism:

> Given an input program 𝑝, equality saturation constructs an e-graph 𝐸 that
> represents a large set of programs equivalent to 𝑝, and then extracts the "best"
> program from 𝐸.

The headline measured result is a case study on Herbie (§6.1.2):

> Our egg simplification backend is a drop-in replacement to the existing Herbie
> simplifier, making it easy to compare speed and results. [...] the egg
> simplification backend is over 3000× faster than Herbie's initial simplifier.
> This speedup eliminated Herbie's largest bottleneck: the initial implementation
> dominated Herbie's total run time at 98.1%, backporting egg improvements into
> Herbie cuts that to about half the total run time, and egg simplification takes
> under 5% of the total run time.

**This number is frequently misread and the misreading matters.** 3000× is the
speedup of *the optimizer*, not of the optimized program. egg's contribution is
that equality saturation became affordable; it says nothing about how much faster
the resulting code runs. Equality saturation's *output* quality claim is a
different one: because the e-graph holds every rewriting of the program
simultaneously, extraction is not subject to phase ordering — you never lose a
good program because a rewrite fired in the wrong order.

Correctness in equality saturation rests entirely on the rewrite rules being
sound. The e-graph faithfully represents the congruence closure of whatever
equalities you assert. Assert a wrong one and it propagates everywhere. There is
no checker in egg; the checker, if any, is upstream in how the rules were
written.

### 5.2 Cranelift replaced its mid-end with one, and measured it

Cranelift's accepted RFC (bytecodealliance/rfcs, `accepted/cranelift-egraph.md`,
<https://raw.githubusercontent.com/bytecodealliance/rfcs/main/accepted/cranelift-egraph.md>,
read 2026-09-19) is the only source found that measures an e-graph mid-end
against the conventional pass pipeline it replaces, in a production compiler:

> Its performance profile is actually fairly nice. On two test cases driven by a
> Wasmtime frontend, SpiderMonkey.wasm and bz2.wasm, we see:
>
> * Compile time:
>   * SpiderMonkey: +1% (slower)
>   * bz2: -15% (faster)
> * Run time:
>   * SpiderMonkey: -13% (faster)
>   * bz2: -3% (faster)

And the explanation, which is the reason this result is not too good to be true:

> This comparison is using an aegraphs configuration that fully replaces most
> optimization phases in the existing mid-end of Cranelift (GVN, LICM,
> simple\_preopt, alias analysis). This is where the compilation-time *speedup*
> comes from: we are doing the same work in a different way, rather than adding
> on work, so it is possible to come out ahead (while still producing better
> code!).

The RFC's stated *motivation* is verification, not speed, and it quantifies the
problem it is trying to avoid:

> It is generally well-studied how handwritten compiler code can introduce subtle
> bugs: for example, the [Alive] verification engine for LLVM was explicitly built
> to find bugs in the InstCombine subsystem of LLVM, which does rewrites of the IR
> with [a significant body of hand-written C++]. This work found 8 bugs in 334
> hand-coded transforms (2.4%), a serious issue when any given codegen bug could be
> catastrophic (e.g. cause a CVE).

> Ideally, we would have a way to express most or all code transforms in a
> declarative way, where it is (i) easier to ensure when writing, and see by
> inspection later, that the equivalence holds; and more importantly (ii)
> eventually use an automated or semi-automated workflow to prove the rewrite(s)
> correct against a semantics for our IR, CLIF.

That is the C12 argument arriving from the opposite direction: not "let a
machine search", but "make the transformations small and declarative enough that
a machine could check them". A 2.4% defect rate in hand-written peephole
transforms is the number that justifies both.

---

## 6. Superoptimization

### 6.1 Souper: an SMT solver as the checker

Sasnauskas, Chen, Collingbourne, Ketema, Lup, Taneja and Regehr
(arXiv:1711.04422, <https://arxiv.org/abs/1711.04422>, read 2026-09-19):

> We developed Souper, a synthesizing superoptimizer, to see how far these ideas
> might be pushed in the context of LLVM. [...] Shipping, or about-to-ship,
> versions of both compilers contain optimizations suggested by Souper but
> implemented by hand. Alternately, when Souper is used as a fully automated
> optimization pass it compiles a Clang compiler binary that is about 3 MB (4.4%)
> smaller than the one compiled by LLVM.

Note that the *deployed* result was human: optimizations Souper *suggested*, then
implemented by hand in LLVM and MSVC. The fully automated mode produced a 4.4%
smaller Clang, and the paper does not hide what else it produced (§2.1, saved
PDF):

> smaller than one built without Souper, though it is also about 2% slower. (We
> do not yet know why; in this configuration, the only optimizations performed by
> Souper were replacing variables by constants. This should not hurt performance.)

**Smaller and slower, cause unknown.** That is what an unguided search over a
cost function that measures size gets you.

The checker is a solver, and the method is the standard one:

> Verification follows the standard technique: Souper asks the solver whether
> there exists any valuation of the inputs that causes the left-hand and
> right-hand sides of the optimization to be unequal. If this query is
> unsatisfiable, equivalence has been proved and the optimization is sound. If the
> query is satisfiable, a counterexample has been discovered and it is presented
> to the user.

Souper can also be used *only* as a checker, which is the clearest published
statement of the propose-and-check split:

> Souper can be used to verify an optimization that was derived by hand or
> synthesized previously—perhaps by an untrusted solver or untrusted organization.

**Cost.** The paper reports it as a build-time experiment (§2.13):

> Although the initial compilation of a program using Souper is often 5× to 25×
> slower than optimized compilation with LLVM, Souper's discoveries are cached and
> subsequent compilations have much lower overhead. For example, the time for
> Souper with a warm cache to compile LLVM on our test machine is about nine
> minutes, as opposed to about eight minutes without Souper.

> For the developer using Souper, compilation on October 1 took about 86 minutes
> because the cache was cold and the solver had to be called many times. However,
> for the rest of the month, this developer could take advantage of the fact that
> most of a large code base does not change frequently [...] The Souper user's
> LLVM build was a little over a minute slower, on average, than the non-Souper
> build, during October 2–31.

86 minutes cold, 8 minutes without, ~1 minute of overhead warm. The caching is
what makes it viable, and it is a Redis instance — a stateful, shared,
network-reachable component in a build. For anyone who cares about reproducible
builds, that is a component that has to be pinned or excluded.

**What the checker cannot certify.** Souper's §2.11 is the most honest passage in
this literature about the limits of solver-checked optimization:

> We have observed miscompilations due to three causes other than the obvious one
> (defects in Souper's implementation). First, an incorrect LLVM optimization can
> turn a defined program into an undefined one, but in a subtle way that is not
> exploited by an LLVM backend. There are known, long-standing bugs of this type in
> LLVM [...] Souper, on the other hand, readily notices and exploits undefined
> behaviors in order to perform computations more cheaply.

> A second, closely related problem is that some applications execute undefined
> behavior that happens to be benignly compiled by LLVM. In this case, the
> application, not LLVM, is wrong, but the end result can be the same: Souper
> notices and exploits the undefined behavior to break the application.

A proof is a proof *against a semantics*. If the semantics says a program has
undefined behaviour and the program relies on the compiler's incidental kindness,
a correct optimizer breaks it. The stronger the checker, the more aggressively
the search exploits exactly the corners where the semantics and the practice
diverge. This is not an argument against verification; it is an argument that
verification raises the value of the language having a semantics its users can
live with.

### 6.2 STOKE: test cases in the loop, a validator at the end

Schkufza, Sharma and Aiken (ASPLOS 2013,
<https://theory.stanford.edu/~aiken/publications/papers/asplos13.pdf>, read
2026-09-19):

> We formulate the loop-free binary superoptimization task as a stochastic search
> problem. [...] Beginning from binaries compiled by `llvm -O0` for 64-bit x86, our
> prototype implementation, STOKE, is able to produce programs which either match
> or outperform the code produced by `gcc -O3`, `icc -O3`, and in some cases,
> expert handwritten assembly.

The design decision that matters for C12 is *why* a symbolic validator is not in
the search loop (§4.1):

> Unfortunately, the total number of validations that can currently be performed
> per second, even for modestly sized codes, is low. Figure 2 (left) suggests that
> for the benchmarks discussed in Section 6 the number is well below 100. Because
> MCMC sampling is effective only insofar as it is able to explore sufficiently
> large numbers of proposals, the repeated computation of Equation 7 in its
> inner-most loop would almost certainly drive that number well below a useful
> threshold.

So STOKE replaces the proof with a Hamming distance over test outputs, and gets
something a proof could not give it:

> Besides being much faster than using a theorem prover, this approximation of
> program equivalence has the added advantage of producing a smoother landscape
> than the 0/1 output of a symbolic equality test; it provides a useful notion of
> "almost correct" that can help to guide the search.

That is a genuine insight and it generalizes: **a proof is a bad search signal
because it is binary.** A checker that says "wrong in 3 bits" steers; a checker
that says "not proved" does not. The architecture that follows is two-tier —
a cheap approximate checker inside the loop, an exact one at the boundary. The
counterexamples from failed exact validations feed back into the test set.

Cost (§6): "Synthesis and optimization are executed in parallel on a small
cluster consisting of 40 dual-core 1.8 GHz AMD Opterons. Both are allocated
computational budgets of 30 minutes." Per kernel.

### 6.3 AlphaDev: exactly what was optimized, and exactly how it was checked

Mankowitz et al. (*Nature* 618, 2023,
<https://www.nature.com/articles/s41586-023-06004-9>, read 2026-09-19). The
scope is small and specific, and the paper is precise about it:

> In this work, we focus on two types of small sort algorithm: (1) the fixed sort
> and (2) the variable sort. Fixed sort algorithms sort sequences of a fixed
> length (for example, sort 3 can only sort sequences of length 3), whereas
> variable sort algorithms can sort a sequence of varying size (for example,
> variable sort 5 can sort sequences ranging from one to five elements).

What was improved:

> As seen in Table 1a, AlphaDev is able to find algorithms with fewer instructions
> than the human benchmarks for sort 3 and sort 5 and matches the state-of-the-art
> performance on sort 4. [...] We managed to save three instructions on sort 6, two
> instructions on sort 7 and one instruction on sort 8

The shipped gain, at the input sizes where it applies:

> We reverse engineered the low-level assembly sorting algorithms discovered by
> AlphaDev for sort 3, sort 4 and sort 5 to C++ and discovered that our sort
> implementations led to improvements of up to 70% for sequences of a length of
> five and roughly 1.7% for sequences exceeding 250,000 elements.

**Read the input sizes.** 70% applies to sorting five elements. At 250,000
elements the gain is 1.7%, because the small sort is a leaf of a divide-and-
conquer and most of the work is elsewhere. Both numbers are in the same
sentence in the paper and only the first travels.

How correctness was established — this is the part the task asked to be precise
about, and the answer is: **by testing, not by proof.** During search, correctness
is a reward term computed from test sequences:

> Algorithm correctness (Fig. 2b) involves inputting a set of N test sequences
> into the current algorithm P_(t) to generate N outputs. These outputs are then
> compared to the expected outputs and a correctness reward r_(t) is computed.

For fixed sort 3 the test set is exhaustive over orderings — "in the case of
sorting three elements, test inputs comprise all sequences of unsorted elements
of length 3" — which for a comparison-only branchless routine is a genuine
argument. For the released artefacts, the data-availability statement says:

> We have released the discovered AlphaDev assembly implementations for sort 3–8
> as well as VarSort3, 4 and 5 on Github [...] We have included exhaustive tests
> to ensure that each implementation is correct.

And the paper acknowledges that this is the binding constraint on the method's
scope:

> It is important to note that AlphaDev can, in theory, generalize to functions
> that do not require exhaustive verification of test cases.

Optimality was established for exactly one case, by brute force, and the Methods
section states both the result and its qualification:

> We also used a brute-force approach to prove that no program shorter than 17
> instructions exists for sort 3. We had to enumerate roughly 10³² programs and,
> even with pruning heuristics, it took more than 3 days to prove this hypothesis.
> For sort 4 and above this approach is infeasible.

> Thus, when we mention that we apply the brute force approach on sort3 to prove
> that no shorter program exists, we mean that, for the supported set of
> instructions we consider for fixed sort3 (i.e., MOV, CMOV and CMP), we found the
> shortest program to be 17 instructions.

Latency, for the variable sorts, was measured rather than modelled — "taking the
fifth percentile of latency measurements across 100 different machines, with
computed confidence intervals". The search itself never measured latency: "only
needs to compute actual measured latency on less than 0.002% of generated
programs".

**The honest summary of AlphaDev.** A reinforcement-learning search over x86
instruction sequences, on branchless routines short enough to test exhaustively,
found one or two instructions of slack in each of three heavily studied kernels,
and those kernels shipped in libc++. It is a real result. It is also the
smallest possible unit of code, verified by enumeration of its entire input
space, and the paper says so.

---

## 7. Learned cost models and hardware modelling

This is the half of the user's request about "fully understanding the underlying
hardware". The literature has a clean answer: static throughput prediction for a
basic block, on one Intel microarchitecture, can be made accurate to about 1%.
Everything beyond that — memory hierarchy, branch prediction, whole programs —
is not modelled by any of these tools.

### 7.1 llvm-mca states its own boundaries

From the LLVM documentation (<https://llvm.org/docs/CommandGuide/llvm-mca.html>,
read 2026-09-19):

> llvm-mca is a performance analysis tool that uses information available in LLVM
> (e.g. scheduling models) to statically measure the performance of machine code
> in a specific CPU.

> By design, the quality of the analysis conducted by llvm-mca is inevitably
> affected by the quality of the scheduling models in LLVM.

And, crucially:

> llvm-mca assumes that instructions have all been decoded and placed into a queue
> before the simulation start. Therefore, the instruction fetch and decode stages
> are not modeled. Performance bottlenecks in the frontend are not diagnosed. Also,
> llvm-mca does not model branch prediction.

The load/store unit's limits are listed explicitly:

> - The LSUnit does not know when store-to-load forwarding may occur.
> - The LSUnit does not know anything about cache hierarchy and memory types.
> - The LSUnit does not know how to identify serializing operations and memory
>   fences.

> The LSUnit does not attempt to predict if a load or store hits or misses the L1
> cache.

**No cache model, no branch predictor, no front end.** A tool with those
exclusions cannot answer "will this program be fast"; it answers "how many
cycles would this straight-line block take if every operand were already in a
register". That is a useful question and a narrow one.

### 7.2 Ithemal: learn the model instead of writing it

Mendis, Renda, Amarasinghe and Carbin (ICML 2019,
<https://arxiv.org/abs/1808.07412>, read 2026-09-19):

> In this paper we present Ithemal, the first tool which learns to predict the
> throughput of a set of instructions. Ithemal uses a hierarchical LSTM--based
> approach to predict throughput based on the opcodes and operands of instructions
> in a basic block. We show that Ithemal is more accurate than state-of-the-art
> hand-written tools currently used in compiler backends and static machine code
> analyzers. In particular, our model has less than half the error of
> state-of-the-art analytical models (LLVM's llvm-mca and Intel's IACA). Ithemal
> is also able to predict these throughput values just as fast as the aforementioned
> tools, and is easily ported across a variety of processor microarchitectures with
> minimal developer effort.

The last clause is the real argument for a learned cost model: porting is
retraining, not re-reading an optimization manual.

### 7.3 uiCA disputes the comparison and beats everyone anyway

Abel and Reineke (ICS 2022, <https://arxiv.org/abs/2107.14210>, read
2026-09-19) start by asking whether the existing error rates are any good:

> The average error of existing models compared to measurements on the actual
> hardware has been shown to lie between 9% and 36%. But how good is this? To
> answer this question, we propose an extremely simple analytical throughput model
> that may serve as a baseline. Surprisingly, this model is already competitive
> with the state of the art, indicating that there is significant potential for
> improvement.

Their baseline is three lines of arithmetic: `max(n/4, m_r/2, m_w)` from
instruction count, memory reads and memory writes on Skylake. Table 1, MAPE
against the BHive reference measurements on Skylake:

| Predictor | MAPE | Kendall's Tau |
| --- | --- | --- |
| Ithemal | 9.51% | 0.8523 |
| IACA 3.0 | 14.50% | 0.8131 |
| DiffTune | 24.62% | 0.7444 |
| llvm-mca-10 | 27.91% | 0.7832 |
| OSACA | 29.74% | 0.7770 |
| **Baseline (3 lines of arithmetic)** | **17.21%** | 0.7719 |

**Three lines of arithmetic beat llvm-mca, DiffTune and OSACA.** That is the
single most useful fact in this section, and it should temper any enthusiasm for
sophisticated cost modelling: a simple resource-bound formula captures most of
what a basic-block throughput model can capture.

**Where the sources disagree.** Ithemal claims "less than half the error" of
llvm-mca and IACA. uiCA says that comparison is not valid (§5.2):

> In [13, 36], these measurements are used to compare the predictions of Ithemal
> (which was trained on benchmarks that were evaluated with the same profiler) to
> the predictions of IACA, OSACA, and llvm-mca (which are based on the 𝑇𝑃_L
> definition). As the predictions of Ithemal are closer to the measurements than
> the predictions of the other tools, they conclude that Ithemal "outperforms" the
> other tools. We don't think this conclusion is valid because the measurements
> are based on a different definition of throughput than the predictions of the
> other tools.

They rebuild the benchmark suite so the definitions agree, and the ordering
changes (§6.1):

> On BHiveU, Ithemal provides the best predictions among the previous tools;
> however, the predictions of uiCA are significantly better. On BHiveL, several
> other previous tools provide better predictions than Ithemal; in two cases the
> MAPE is even below the baseline. It is likely that retraining Ithemal on
> measurements obtained with the methodology described in Section 5 would improve
> its accuracy on BHiveL. However, we were unable to do so, as the training set is
> not publicly available.

Two lessons, both of which apply to any learned compiler component. First, a
learned model inherits the definition and the biases of its training
measurements, and comparing it to an analytical model that uses a different
definition measures the definitions, not the models. Second, "we were unable to
do so, as the training set is not publicly available" — the model could not be
re-evaluated fairly because its data was not published. That is a reproducibility
failure of exactly the kind the planned report 03 §4 is about.

### 7.4 What is achievable, and what is not

**Achievable.** uiCA's own accuracy: "its predictions are usually within 1% of
measurement results, improving upon prior models by roughly an order of
magnitude." That is a hand-built, parametric pipeline simulator for every Intel
Core generation from 2011 to 2021, and it demonstrates that a basic block's
steady-state throughput on a *known* microarchitecture is a solved problem — if
someone does the work of modelling that microarchitecture in detail. The paper's
own conclusion is that the details matter: "several microarchitectural details
considered to be rather insignificant in previous work, are in fact essential for
accurate prediction."

**Not achievable from any of these tools.** Cache behaviour, branch prediction,
memory-level parallelism across blocks, anything involving the front end, and
anything about a whole program. The measurement methodology itself is a source
of error the same size as some of the models: uiCA reports that BHive's original
measurements differ from their improved ones by "up to 4.4%".

**The cost of running them**, per basic block on Skylake (§6.1): "uiCA (which is
implemented in Python) requires on average per benchmark around 105 ms, OSACA
1300 ms, IACA 10 ms, llvm-mca 36 ms. For Ithemal it depends: end-to-end it takes
around 580 ms; in interactive mode, each additional benchmark requires around
8 ms." A compiler that consulted uiCA for every basic block would be roughly a
hundred times slower than one that did not.

So "a compiler that fully understands the underlying hardware" is, on the
evidence, achievable for one narrow question (steady-state throughput of
straight-line code on a named Intel part), at a cost of one detailed model per
microarchitecture and ~100 ms per query, with no coverage of the memory
hierarchy at all.

---

## 8. What A7's own measurements say about where its leverage is

Two local results bound the discussion in the planned report 03.

**The safety checks A7's proof pass exists to remove cost 2.2× on the one
workload where they cost anything, and it is not the bounds check.**
(measurements.md M4.) On `bench2.a7` — a 4096-element array summed 200,000 times
— ReleaseSafe runs in 0.165 s and ReleaseFast in 0.081 s. Editing the emitted
Zig's `acc += buf[k]` to the wrapping `acc +%= buf[k]` and rebuilding at
**ReleaseSafe** gives 0.080 s. The entire gap is the **integer overflow check on
the accumulator**; the bounds check on `buf[k]` costs nothing measurable,
because LLVM hoists it out of a loop whose trip count it knows. On `bench.a7`
(trial division, no arrays) ReleaseSafe and ReleaseFast are indistinguishable:
0.727 s against 0.721 s.

**Binary size is not a usable signal at A7's current program sizes**
(measurements.md M3). Across four examples, ReleaseFast binaries are *larger*
than ReleaseSafe ones (e.g. 3,829,984 against 3,798,104 bytes for
`032_prime_numbers`), because size is dominated by the Zig standard library's
panic, DWARF and Io machinery rather than by A7's emitted code. `.text` at
ReleaseSmall is 91,864 bytes against 404,809 at ReleaseSafe for the same
program.

---

## 9. The table

Gains are as each source reports them; the baseline differs per row and is named.
"Verifiable output" distinguishes three things that are routinely conflated: a
machine-checked proof of equivalence, correctness that holds because the search
space contains only correct programs, and a test suite that passed.

| Technique | Measured gain (and against what) | Adoption cost | Needs a runtime profile? | Is the output verifiable? |
| --- | --- | --- | --- | --- |
| **Compile-time PGO** (Go 1.22) | 2–14% on "a representative set of Go programs", vendor-measured | Profile collection from production; a build step; iterative stability designed into the optimizer | **Yes**, and a representative one | Not applicable — the compiler applies the profile; no new transformations exist |
| **AutoFDO** (CGO 2016) | 10.5% geomean; 85% of instrumented FDO's gains | Hardware perf counters on production machines; profile-to-IR mapping in the compiler | **Yes**, sampled; stale by design | Same — profile guides existing passes |
| **BOLT** (arXiv 1807.06735) | Up to 8.0% on data-center apps *on top of* FDO+LTO; up to 20.4% on GCC/Clang on top of FDO+LTO | Linker `--emit-relocs`; a whole-binary disassemble-and-rewrite pass; debug/EH info rewriting | **Yes**, sampled | No proof. Correctness rests on the rewriter's own disassembly and relocation handling |
| **MLGO inlining** (LLVM, Google) | 4.95%/3.74%/5.94% size against `-Oz` by policy; 6.3% on Fuchsia C++ TUs | 12–150 h training on 100–488 workers; +115 KB compiler; ~1% compile time | No | Correct by construction — "we replace heuristics, not semantics-preserving code" |
| **MLGO regalloc** (LLVM, Google) | 0.3–1.5% QPS on Google datacenter apps | As above | No | Same |
| **ATLAS** (1997) | Competitive with hand-tuned BLAS | **1–2 h per precision, per machine**, at install | No (timing, not profiling) | Correct by construction — it searches blocking factors, not code |
| **FFTW** (Proc. IEEE 2005) | Planner selects fastest plan by measurement; estimate mode trades a named penalty for speed | Planner runs at program start-up; "wisdom" must be persisted | No | Correct by construction — plans compose verified codelets |
| **Halide autoscheduler** (SIGGRAPH 2019) | 1.37× greedy / 2.29× beam over the previous autoscheduler; "sometimes less than half the speed" | Cost model trained on hundreds of thousands of random programs; **a full bring-up per new architecture** | No | Correct by construction — schedules, not code |
| **AutoTVM** (NeurIPS 2018) | Competitive with hand-tuned libraries; transfer learning gives 2–10× less search | Hours per operator per machine | No | Correct by construction |
| **Ansor** (OSDI 2020) | Up to 3.8×/2.6×/1.7× (Intel CPU/ARM CPU/NVIDIA GPU) over state of the art | "several hours ... for a DNN on a single machine"; acceptable only as a one-shot pre-deployment step | No | Correct by construction |
| **egg / equality saturation** (POPL 2021) | 3000× faster *simplification* in Herbie (optimizer speed, not program speed) | A rewrite-rule set; extraction cost function | No | **Only as sound as the asserted rewrite rules.** No checker in the loop |
| **Cranelift aegraph mid-end** | Run time −13% (SpiderMonkey) / −3% (bz2); compile time +1% / −15% | Rewriting the mid-end; rules in a DSL (ISLE) | No | Not yet proved; the stated goal is that declarative rules *become* provable against a CLIF semantics |
| **Souper** (arXiv 1711.04422) | 4.4% smaller Clang binary — **and 2% slower** | 5–25× slower cold builds; 86 min vs 8 min first build; a Redis cache in the build | No | **Yes** — SMT equivalence proof per optimization. Sound only against LLVM's UB semantics |
| **STOKE** (ASPLOS 2013) | Matches or beats `gcc -O3`/`icc -O3` on loop-free kernels; sometimes beats expert assembly | 30 min per kernel on 40 dual-core machines | No | Two-tier: Hamming-distance over test cases in the loop, symbolic validator at the boundary |
| **AlphaDev** (Nature 2023) | One instruction fewer on sort 3 and sort 5; up to 70% at n=5 and **1.7% at n>250,000** in libc++ | A full RL training run per kernel; 100-machine benchmarking service | No (latency measured directly) | **Tests, not proof** — "exhaustive tests"; brute-force optimality for sort 3 only, at 10³² programs and 3 days |
| **llvm-mca** | 27.91% MAPE on BHive/Skylake — worse than a 3-line baseline | Free; already in LLVM | No | N/A — a predictor, not a transformer |
| **Ithemal** (ICML 2019) | 9.51% MAPE on BHive/Skylake, best of the pre-uiCA tools | Training data per microarchitecture; **training set not published** | No | N/A |
| **uiCA** (ICS 2022) | "usually within 1% of measurement results" | One hand-built pipeline model per Intel generation; 105 ms per basic block | No | N/A |

### What the table says, read as one thing

The rows with the best gain-to-cost ratio are all in the "correct by
construction" column, and they all share a shape: **the search proposes a
coordinate in a space the compiler already knows how to realize.** A pass list. A
profile. An inline decision. A loop schedule. Nothing the search emits reaches
the binary directly, so nothing the search gets wrong can make the binary wrong.

The rows that propose actual code — Souper, STOKE, AlphaDev — need a checker, and
each paid for it differently: an SMT solver that makes builds 5–25× slower, a
test-based approximation with a validator at the boundary, or exhaustive
enumeration over an input space small enough to enumerate. Their gains are not
larger than the first group's. Souper's is negative on speed.

That is the finding this report exists to establish, and the argument
the planned report 03 builds on: **the value is in what the
checker admits, not in how clever the proposer is, and the cheapest checker is a
search space that cannot express a wrong answer.**
