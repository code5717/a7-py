<!-- Preserved 2026-09-19 from tmp/research/runtime-model/sources/claim1/SOURCES.md. Repository home-path prefixes normalized; claims and verification statements below are historical. Saved files remain beside the original temporary manifest. -->

# Claim 1 — deterministic fiber concurrency and logical scheduling: primary sources

All items read 2026-09-18. Every file listed under `Saved:` is in this directory.

**Quote verification method.** PDFs were converted with `pdftotext` to a `.txt`
sidecar. HTML pages were saved as `.html` (the original bytes) and converted to a
tag-stripped, entity-decoded, whitespace-collapsed `.txt` sidecar. Every quote
below was verified present in the sidecar by exact substring match
(`tr -s '[:space:]' ' ' < file.txt | grep -o -F '<sentence>'`, run as
`/tmp/verify.py`). Quotes that did not match were reworded until they matched or
dropped. Where `pdftotext` mangles spacing (e.g. `D MP -O` for the small-caps
`DMP-O`), the quote is trimmed to the part that reproduces exactly.

---

### Goldberg — What Every Computer Scientist Should Know About Floating-Point Arithmetic
URL: https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html
Saved: goldberg.html (sidecar goldberg.txt)
Read: 2026-09-18
Kind: spec / reference article
Quote (grep-verified): "Due to roundoff errors, the associative laws of algebra do not necessarily hold for floating-point numbers."
Note: Establishes the mechanism behind reduction-order nondeterminism: if the
order in which partial sums are combined changes between runs, the floating-point
result can change. It does not say anything about schedulers; it establishes that
"bit-exact across runs" requires a fixed reduction order, not merely a correct one.

---

### Rayon — `ParallelIterator::sum` / `product` docs
URL: https://docs.rs/rayon/latest/rayon/iter/trait.ParallelIterator.html
Saved: rayon-sum.html (sidecar rayon-sum.txt)
Read: 2026-09-18
Kind: project doc (vendor/library doc)
Quote (grep-verified): "Note that the order in items will be reduced is not specified, so if the + operator is not truly associative (as is the case for floating point numbers), then the results are not fully deterministic."
Note: A mainstream production work-stealing runtime states in its own API docs
that floating-point reductions are *not* run-to-run deterministic. Directly
contradicts "100% bit-exact" for any float reduction over a work-stealing
scheduler that does not also fix the split/join tree.

---

### oneTBB specification — `parallel_deterministic_reduce`
URL: https://oneapi-spec.uxlfoundation.org/specifications/oneapi/latest/elements/onetbb/source/algorithms/functions/parallel_deterministic_reduce_func
Saved: tbb-spec-detreduce.html (sidecar tbb-spec-detreduce.txt)
Read: 2026-09-18
Kind: spec
Quote (grep-verified): "parallel_deterministic_reduce uses a simple_partitioner or a static_partitioner only because other partitioners react to random work stealing behavior."
Note: The authoritative statement of *why* ordinary work stealing is
nondeterministic ("random work stealing behavior") and of the price of removing
it: you lose the adaptive partitioners. Establishes determinism is bought by
fixing the partitioning, not by making stealing deterministic.

---

### oneTBB user guide — Partitioner Summary
URL: https://uxlfoundation.github.io/oneTBB/main/tbb_userguide/Partitioner_Summary.html
Saved: tbb-partitioners.html (sidecar tbb-partitioners.txt)
Read: 2026-09-18
Kind: project doc
Quote (grep-verified): "static_partitioner Deterministic chunk size, cache affinity and uniform distribution of iterations without load balancing."
Note: States the trade-off explicitly — the deterministic partitioner gives up
load balancing. This is the cost that claim 1 does not state.

---

### Kendo (Olszewski, Ansel, Amarasinghe), ASPLOS 2009
URL: https://people.csail.mit.edu/mareko/asplos073-olszewski.pdf
Saved: kendo.pdf (text kendo.txt)
Read: 2026-09-18
Kind: research paper — measured result
Quote (grep-verified): "Experimental results on the SPLASH-2 applications yield a geometric mean overhead of only 16% when running on 4 processors."
Quote (grep-verified): "Weak determinism offers the same guarantee for exactly those inputs that lead to race-free executions under the deterministic scheduler"
Quote (grep-verified): "we conjecture that it cannot be provided efficiently without hardware support"
Quote (grep-verified): "Unfortunately, many of the performance counter events we tested did not offer deterministic results. For example, both the retired instructions and retired loads events are non-deterministic"
Note: The fourth quote is mechanism (a) at the hardware layer: the very
counters a "logical cycle clock" would be built from are themselves not
reproducible on real x86 CPUs. Kendo had to search for a counter (retired
stores) that was. The closest published analogue to the claim's "logical cycle clocks"
(Kendo calls them *deterministic logical clocks*, built from x86 store-retired
performance counters). Its measured cost is 16% geomean on 4 cores — but the
guarantee it buys is *weak* determinism: only for race-free executions. The third
quote is the authors' conjecture about the strong guarantee — the one claim 1
asserts — being unattainable efficiently in software. Limits: 4 cores, SPLASH-2,
2009 hardware; says nothing about fibers or reverse stepping.

---

### CoreDet (Bergan, Anderson, Devietti, Ceze, Grossman), ASPLOS 2010
URL: https://sampa.cs.washington.edu/new/papers/asplos10-coredet.pdf
Saved: coredet.pdf (text coredet.txt)
Read: 2026-09-18
Kind: research paper — measured result
Quote (grep-verified): "Scheduling, memory reordering, timing, and low-level hardware effects all introduce nondeterminism in the execution of multithreaded programs."
Quote (grep-verified): "the overheads for 8 threads range from 1.1x–6x"
Note: The first quote is a compact authoritative enumeration of mechanism (a).
The second is the measured cost of *strong* determinism (arbitrary racy
pthreads code) on 8 threads: 1.1x–6x for the ownership scheme; the same sentence
continues with 1.2x–11x for the buffering scheme (that half is not quoted because
`pdftotext` mangles the small-caps scheme names). PARSEC + SPLASH2.

---

### dOS / Deterministic Process Groups (Bergan, Hunt, Ceze, Gribble), OSDI 2010
URL: https://homes.cs.washington.edu/~luisceze/publications/osdi10-dos.pdf
Saved: dos.pdf (text dos.txt)
Read: 2026-09-18
Kind: research paper — measured result
Quote (grep-verified): "latency increases by 1.7× for DPGs alone and by 1.8× for DPGs with"
Quote (grep-verified): "Broadly, overhead tends to increase with sharing, especially as the number of threads grows."
Note: OS-level deterministic execution of unmodified multithreaded programs. The
evaluation table (Table 3, not quotable as text — `pdftotext` flattens it)
reports parallel-workload overheads from 1.2× to 10.1×. The second quote is the
structural finding that matters for claim 1: the cost of a deterministic schedule
*rises* with sharing and thread count — the opposite of "even under heavy
parallel loads".

---

### DThreads (Liu, Curtsinger, Berger), SOSP 2011
URL: https://people.cs.umass.edu/~emery/pubs/dthreads-sosp11.pdf
Saved: dthreads.pdf (text dthreads.txt)
Read: 2026-09-18
Kind: research paper — measured result
Quote (grep-verified): "Kendo ensures determinism of synchronization operations with low overhead, but does not guarantee determinism in the presence of data races"
Quote (grep-verified): "do not ensure determinism in the presence of data races"
Quote (grep-verified): "run up to 8.4× slower than"
Quote (grep-verified): "Grace prevents all concurrency errors but is limited to fork-join programs. Although"
Note: The Grace sentence (it continues "...it can be efficient, it often requires
code modifications to avoid large runtime overheads") describes the closest
published analogue to "fibers plus structured dependency graphs" — a
deterministic fork-join runtime — and names its cost: restricted to fork-join,
and needing code changes to stay fast. Independent confirmation that Kendo's cheap 16% buys only the weak
guarantee, and an independently measured figure for CoreDet's strong guarantee
(up to 8.4× slower than pthreads). DThreads itself claims near-pthreads
performance for 9 of 14 benchmarks, but it achieves this by running threads in
separate address spaces with copy-on-write and committing at synchronization
points — a programming model, not a drop-in fiber scheduler.

---

### Determinator (Aviram, Weng, Hu, Ford), OSDI 2010
URL: http://dedis.cs.yale.edu/2010/det/papers/osdi10.pdf
Saved: determinator.pdf (text determinator.txt)
Read: 2026-09-18
Kind: research paper — measured result
Quote (grep-verified): "incurs a fixed performance cost of about 35% for the chosen quantum of 10 million instructions"
Note: A deterministic-by-construction OS. 35% is the *quantization* cost alone at
a very coarse 10M-instruction quantum; the paper goes on to note the fine-grained
`lu` benchmarks cost much more, i.e. the cost is a function of synchronization
granularity. Note also that the primary USENIX-hosted PDF
(`www.usenix.org/legacy/event/osdi10/tech/full_papers/Aviram.pdf`) returned HTTP
200 to HEAD but reset the connection on GET from this host; the Yale DeDiS copy
was used instead.

---

### rr — project homepage
URL: https://rr-project.org/
Saved: rr-project.html (sidecar rr-project.txt)
Read: 2026-09-18
Kind: project doc
Quote (grep-verified): "emulates a single-core machine. So, parallel programs incur the slowdown of running on a single core. This is an inherent feature of the design."
Note: Answers (c) directly and affirmatively. The one production tool that
delivers reverse-execution debugging of arbitrary shared mutable state does so by
giving up multi-core execution, and its own docs call that inherent to the design
— not an implementation gap.

---

### rr — "Engineering Record And Replay For Deployability" (O'Callahan et al., USENIX ATC 2017, extended TR)
URL: https://arxiv.org/pdf/1705.05937
Saved: rr-paper.pdf (text rr-paper.txt)
Read: 2026-09-18
Kind: research paper — measured result
Quote (grep-verified): "There is a large slowdown for workloads with a consistently high degree of parallelism"
Quote (grep-verified): "The one-thread-at-a-time restriction is implemented by supervising all tracee processes/threads via the ptrace system call."
Quote (grep-verified, Table 1 row): "Record 1.49× 7.85× 1.79× 1.49× 1.57×"
Quote (grep-verified, Table 1 row): "Single core 0.98× 3.36× 1.36× 1.07× 0.95×"
Note: Table 1 columns are, in order, cp / make / octane / htmltest / sambatest.
So recording costs 1.49×–7.85×, and the "Single core" row — just
`taskset`-pinning threads to one core, no recording at all — costs up to 3.36×
by itself on the parallel `make -j8` workload. The serialization is the
dominant cost on parallel work, before any recording. Directly contradicts "preserving reverse
stepping ... even under heavy parallel loads".

---

### Hermit (facebookexperimental/hermit) — README
URL: https://raw.githubusercontent.com/facebookexperimental/hermit/main/README.md
Saved: hermit-readme.html (sidecar hermit-readme.txt) — the fetched file is raw Markdown despite the `.html` name
Read: 2026-09-18
Kind: vendor claim + stated overhead
Quote (grep-verified): "controls sources of nondeterminism including thread scheduling, time, random data, CPUID results, and selected file metadata"
Quote (grep-verified): "Hermit's deterministic ptrace backend should generally be budgeted at roughly 3-6x native wall-clock time."
Note: Answers (e). Hermit determinizes an unmodified x86-64 Linux guest under
ptrace — the broadest scope in this set — at a self-stated 3-6x. The README also
states Hermit "is in maintenance mode", that Linux compatibility is "substantial
but incomplete", and that record/replay is "Experimental". The 3-6x is a planning
range the README explicitly declines to call a benchmark ("This is a planning
range, not a benchmark promise"). Provenance: the upstream README's install
section points at the `rrnewton/hermit` "maintained fork", so this figure is the
fork maintainer's, not a published measurement.

---

### GGPO — how rollback networking works
URL: https://www.ggpo.net/
Saved: ggpo.html (sidecar ggpo.txt)
Read: 2026-09-18
Kind: vendor claim / project doc
Quote (grep-verified): "Rollback networking is designed to be integrated into a fully deterministic peer-to-peer engine."
Note: Establishes that rollback netcode *requires* determinism as a precondition
supplied by the game engine; it does not provide it. Relevant to (f) only as the
consumer side. The pond3r/ggpo GitHub README (saved as ggpo-github.html) contains
no occurrence of "determin" — not usable.

---

### Photon Quantum 3 — Fixed Point (FP)
URL: https://doc.photonengine.com/quantum/current/manual/quantum-ecs/fixed-point
Saved: photon-fixedpoint.html (sidecar photon-fixedpoint.txt)
Read: 2026-09-18
Kind: vendor claim
Quote (grep-verified): "completely replaces all usages of floats and doubles to ensure cross-platform determinism"
Note: The commercially shipping deterministic multiplayer engine achieves
cross-machine bit-exactness by *abandoning floating point entirely* (Q48.16 fixed
point for all math, physics and navigation). This is the price claim 1 does not
mention. Quantum's simulation systems are also written against
`SystemMainThread`; the doc page carries a banner that it "has not been upgraded
to Quantum 3.0 yet".

---

### Factorio — Friday Facts #188, "Bug, Bug, Desync"
URL: https://www.factorio.com/blog/post/fff-188
Saved: factorio-fff188.html (sidecar factorio-fff188.txt)
Read: 2026-09-18
Kind: vendor/developer report — field experience
Quote (grep-verified): "Unfortunately making a fully deterministic game is not easy, so you will notice desyncs, especially at the beginning of a new experimental release such as this one."
Note: A shipping deterministic-lockstep game, with determinism as a hard product
requirement and years of engineering behind it, still ships desyncs. Field
evidence against "guarantees ... 100% bit-exact" as a property that falls out of
a scheduler design.

---

### Unity — `Unity.Burst.FloatMode` scripting reference (Unity 6.6)
URL: https://docs.unity3d.com/6000.6/Documentation/ScriptReference/Unity.Burst.FloatMode.html
Saved: unity-floatmode.html (sidecar unity-floatmode.txt)
Read: 2026-09-18
Kind: vendor doc
Quote (grep-verified): "Deterministic Ensure that floating point calculations are deterministic (64-bit only)."
Note: Unity's deterministic float mode is architecture-limited. The default mode
is `Strict`, not `Deterministic`.

---

### Unity — Burst manual, `BurstCompile` attribute (Burst 1.8)
URL: https://docs.unity3d.com/Packages/com.unity.burst@1.8/manual/compilation-burstcompile.html
Saved: unity-burst-opt.html (sidecar unity-burst-opt.txt)
Read: 2026-09-18
Kind: vendor doc
Quote (grep-verified): "Ensure that floating point calculation in Burst are deterministic, i.e., consistent across all supported platforms. Only supported on 64-bit architectures."
Note: The nearest thing in this set to a vendor cross-platform bit-exactness
claim — and it is scoped to floating-point *codegen* within Burst-compiled jobs
on 64-bit architectures. It says nothing about job scheduling order.

---

### Rust — `std::collections::HashMap`
URL: https://doc.rust-lang.org/std/collections/struct.HashMap.html
Saved: rust-hashmap.html (sidecar rust-hashmap.txt)
Read: 2026-09-18
Kind: spec / stdlib doc
Quote (grep-verified): "The algorithm is randomly seeded, and a reasonable best-effort is made to generate this seed from a high quality, secure source of randomness provided by the host without blocking the program."
Note: Mechanism (a), hash iteration order: a per-process random seed makes hash
iteration order differ between runs of the *same* binary on the *same* machine,
independent of any scheduler. Any runtime claiming bit-exact repeatability must
also pin this.

---

### Python — command line and environment (`-R` / `PYTHONHASHSEED`)
URL: https://docs.python.org/3/using/cmdline.html
Saved: python-hashseed.html (sidecar python-hashseed.txt)
Read: 2026-09-18
Kind: spec / language doc
Quote (grep-verified): "so that the __hash__() values of str and bytes objects are “salted” with an unpredictable random value"
Note: Second instance of the same mechanism, in a different language, showing it
is a deliberate default rather than an accident.

---

### Nathaniel J. Smith — "Notes on structured concurrency, or: Go statement considered harmful"
URL: https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/
Saved: njs-structured.html (sidecar njs-structured.txt)
Read: 2026-09-18
Kind: project doc / essay (the canonical statement of structured concurrency)
Quote: **none — absence is the finding.** The word "determin" (any case) occurs
**0 times** in the saved article (`grep -o -i -c determin njs-structured.txt` → 0).
Note: Answers (g) negatively. The founding document of structured concurrency
argues for guaranteed *lifetime and cancellation* propagation — that a task
cannot outlive its nursery and that errors cannot be silently lost. It never
claims, or even raises, determinism. Structured concurrency constrains *when
tasks may still be running*, not *in what order they interleave*.

---

### Christian Gyrling — "Parallelizing the Naughty Dog engine using fibers", GDC 2015
URL: https://media.gdcvault.com/gdc2015/presentations/Gyrling_Christian_Parallelizing_The_Naughty.pdf
Saved: nd-fibers.pdf (text nd-fibers.txt)
Read: 2026-09-18
Kind: vendor/practitioner talk (slides)
Quote: **none — absence is the finding.** "determin", "race" and "order" each occur
**0 times** in the 1499-line extracted text of the slide deck.
Note: Answers (h) negatively. The best-known production fiber-based job system in
games claims 60 fps, CPU utilization, jobification of all code and frame-centric
memory lifetimes. It does not claim deterministic execution, and does not discuss
determinism at all. The fiber abstraction is sold as a scheduling/latency tool,
not a reproducibility tool.

---

### rr — Usage wiki
URL: https://github.com/rr-debugger/rr/wiki/Usage
Saved: rr-usage.html (sidecar rr-usage.txt)
Read: 2026-09-18
Kind: project doc
Quote: not used — the page is the GitHub wiki UI and the determinism statements
on it are weaker than, and subsumed by, the homepage quote above.
Note: Retained for completeness.

---

### OpenCilk glossary — Determinism / Nondeterminism / Determinacy race
URL: https://opencilk.org/doc/reference/glossary/determinism/ ; https://opencilk.org/doc/reference/glossary/nondeterminism/ ; https://opencilk.org/doc/reference/glossary/determinacy-race/
Saved: opencilk-determinism.html, opencilk-nondet.html, opencilk-detrace.html (sidecars .txt)
Read: 2026-09-18
Kind: project doc (definitional)
Quote (grep-verified, determinism): "The property of a program when it behaves identically from run to run when executed on the same inputs."
Quote (grep-verified, nondeterminism): "The property of a program when it behaves differently from run to run when executed on exactly the same inputs."
Quote (grep-verified, determinacy race): "A race condition that occurs when two logically parallel strands access the same memory location and at least one strand performs a write."
Note: Cilk's own vocabulary frames determinism as a property of *observable
behavior* given the same inputs — not as a property of the schedule. The
determinacy-race definition is the boundary condition: Cilk's guarantee holds
precisely where no two logically parallel strands race. This is the (b)
distinction stated in the vendor's own words, though the site does not spell out
the "any schedule yields the same result" consequence on these pages. The
narrative "find and fix nondeterminism" user-guide page that does spell it out is
JavaScript-rendered and was not readable (see failed fetches).

---

### Unity Physics package — overview page
URL: https://docs.unity3d.com/Packages/com.unity.physics@1.3/manual/index.html
Saved: uphys-toc.html (sidecar uphys-toc.txt)
Read: 2026-09-18
Kind: vendor claim
Quote (grep-verified): "The Unity Physics package, part of Unity's Data-Oriented Technology Stack (DOTS), provides a deterministic rigid body dynamics system and spatial query system."
Note: **This is an unqualified vendor determinism claim.** Task item (f) asked me
to verify whether Unity limits its determinism claim to the same
platform/architecture/build. On the pages I could reach, **I did not find that
limitation stated** — the overview asserts determinism flatly, and every
candidate URL for a dedicated determinism page returned a "page not found" stub
(see failed fetches). The only architecture qualification I could verify anywhere
in Unity's docs is the Burst `FloatMode.Deterministic` "64-bit only" note above.
**Treat "Unity limits its determinism claim to the same platform" as UNVERIFIED
and unfound, not as disproven** — see the Design philosophy entry below for the
eight-page sweep of the package manual that also failed to turn it up.

---

### Hermit — docs/ARCHITECTURE.md (scheduler turn)
URL: https://raw.githubusercontent.com/facebookexperimental/hermit/main/docs/ARCHITECTURE.md
Saved: hermit-arch.md
Read: 2026-09-18
Kind: project doc
Quote (grep-verified): "Tentatively choose the next runnable TID"
Quote (grep-verified): "This is conservative and limits parallelism, but makes the global snapshot and commit order well defined."
Note: Answers the "how" half of (e), and it is decisive. Hermit's scheduler is a
**turn-based loop that picks one runnable thread at a time**, waits for "broad
quiescence" before advancing a turn, and its own architecture doc states this
"limits parallelism" as the price of a well-defined commit order. Hermit also
derives its logical time from retired-conditional-branch performance counters —
the same mechanism class Kendo used, with the same hardware caveats. So the
broadest-scope deterministic runtime in this set buys its determinism by
constraining parallelism, exactly as rr does, only less bluntly.

---

### Unity Physics — Design philosophy page
URL: https://docs.unity3d.com/Packages/com.unity.physics@1.3/manual/design.html
Saved: uphys-design.html (sidecar uphys-design.txt)
Read: 2026-09-18
Kind: vendor claim
Quote (grep-verified): "Unity Physics is a completely deterministic rigid body dynamics and spatial query system, written entirely in high performance C# using ECS best practices."
Note: A second unqualified Unity determinism claim, stronger than the first
("completely deterministic"), again with no platform/architecture caveat on the
page. I fetched the Unity Physics 1.3 manual's full `toc.html` and checked the
eight pages whose titles could plausibly carry the caveat — `design`,
`concepts-intro`, `concepts-simulation`, `physics-pipeline`,
`simulation-modification`, `simulation-results`, `troubleshooting`, `glossary` —
and the word "deterministic" appears on exactly two of them (`index` and
`design`), both times as an unqualified claim. **Finding: in the pages I could
read, Unity does not state the same-platform/architecture/build limitation.**
That is an absence in my search, not proof the caveat exists nowhere in Unity's
docs; the WebSearch budget was exhausted before I could search for it directly.

---

## Not readable / failed fetches

- `https://www.usenix.org/legacy/event/osdi10/tech/full_papers/Aviram.pdf` and
  `.../Bergan.pdf` — HEAD returns HTTP 200 `application/pdf`, GET resets the
  connection (`curl: (35) Recv failure`) across HTTP/1.1 and HTTP/2 and three
  retries. **Not readable — no quote.** Both papers were obtained from
  author/institution mirrors instead (Yale DeDiS, UW `luisceze`), and the
  mirrored PDFs were confirmed to be the full conference papers by reading their
  title blocks and abstracts.
- `https://www.opencilk.org/doc/users-guide/find-and-fix-nondeterminism/` —
  JavaScript-rendered; the saved HTML contains only the Algolia/GTM shell and
  ~1.2 KB of chrome, no article body. **Not readable — no quote.** The raw
  GitHub Markdown path guessed for it returned 14 bytes.
- `https://gdcvault.com/play/1022186/...` (saved as naughtydog-fibers.html) —
  video player page, no slide text. Superseded by the slide PDF above.
- Unity Physics determinism page — four candidate URLs under
  `docs.unity3d.com/Packages/com.unity.physics@1.3/manual/` (`determinism.html`,
  `concepts-determinism.html`, `simulation-determinism.html`,
  `simulation-results.html`) all returned the identical 8026-byte "page not
  found" stub. **Not found — no quote.** Delegated to GLM (below).
- `https://docs.unity3d.com/Manual/job-system.html` — returned a 2.2 KB stub with
  zero occurrences of "determin". **Not readable — no quote.**
- `https://doc.photonengine.com/quantum/current/manual/determinism-guide` —
  returns the site's "Page not found" SPA shell. **Not readable — no quote.**
  The Fixed Point page above was used instead.
- `https://raw.githubusercontent.com/pond3r/ggpo/master/doc/GettingStarted.md` —
  14 bytes (404). **Not readable — no quote.**
- WebSearch budget for this session was exhausted (200/200) partway through, so
  the remaining URL discovery was delegated to GLM.

---

### GLM lookup — Unity determinism docs, Unity Job System claims, Cilk determinacy races, deterministic work-stealing measurements
Kind: **secondary — GLM-5.3-flash lookup, not a primary source**
Saved: tmp/glm/claim1-unity-cilk.md
Prompt: tmp/glm/claim1-unity-cilk-prompt.md
Read: 2026-09-18
Note: **The GLM run FAILED and produced no answer.** The output file contains
only its search tool's error trace: `MCP error -429 ... "Weekly/Monthly Limit
Exhausted. Your limit will reset at 2026-09-22"`, repeated for all five queries.
The zai-coding-plan provider's web-search quota is exhausted, so the GLM fallback
path is unavailable this week (the coordinator has since confirmed this and
withdrawn the fallback instruction). **No content from GLM is used anywhere in
this file or in the ruling.** The gaps it was meant to close were closed instead
by direct curl against the Unity Physics `toc.html` and the OpenCilk sitemap
(see those entries), except where noted as still unfound.

---

## Where sources disagree

**Two conflicts worth naming.** (a) Kendo conjectures strong determinism "cannot be
   provided efficiently without hardware support"; DThreads reports matching or
   beating pthreads on 9 of 14 benchmarks *with* a strong guarantee. The
   reconciliation is that DThreads changes the execution model — separate address
   spaces, copy-on-write, commit at synchronization points — rather than
   scheduling threads deterministically in shared memory. (b) CoreDet's abstract
   says its approach "scales comparably to nondeterministic execution"; dOS, from
   the same group a year later, says "overhead tends to increase with sharing,
   especially as the number of threads grows." These describe different axes —
   baseline slowdown vs. the scaling curve — but a reader taking CoreDet's
   sentence alone would overestimate what is available.

## Gaps — things I looked for and did not find a source for

1. **No published measurement of a deterministic work-stealing scheduler.** Not
   one source in this set measures the overhead of making *work stealing itself*
   reproducible on a multicore machine. Every deterministic system measured here
   removes stealing (TBB's `static_partitioner`/`simple_partitioner`), replaces
   scheduling with a logical-clock turn order (Kendo), quantizes and commits
   (CoreDet/dOS/Determinator/DThreads), or serializes onto one core (rr). The
   phrase "deterministic work-stealing scheduler" in the claim has no measured
   precedent I could locate.
2. **No source states the same-platform limitation on Unity's determinism claim.**
   Found the claim (Unity Physics overview), not the limitation. See that entry.
3. **No source ties fibers to determinism.** The canonical production fiber
   scheduler talk (Naughty Dog) never uses the word.
4. **No source claims structured concurrency yields determinism.** The canonical
   essay never uses the word.
5. **No source in this set reports bit-exact multi-core reverse stepping.** rr is
   the only production reverse-stepping debugger here and it is explicitly
   single-core by design.
