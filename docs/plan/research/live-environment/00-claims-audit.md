# Live programming environments: concepts audit

Audited 2026-09-18. The user supplied eight feature claims from another project
(verbatim in `tmp/research/live-environment/claims.md`). Per
[CONCEPTS.md](../CONCEPTS.md) the features are not the subject: this report is
organized by the concepts under them, with the supplied claims as an index into
the evidence. Judged under [EVALUATION.md](../EVALUATION.md), agent value weighted
above human value. Rulings are consistent with the register in
[CLAIMS.md](../CLAIMS.md).

Evidence standard: every quotation was fetched, with its URL and the date read.
Where a fetch failed it is recorded as a failure, not smoothed over. Inference is
marked INFERENCE. Raw excerpts and per-source fetch logs, including every failed
fetch, are in `tmp/research/live-environment/notes/`.

Provenance of the quotations: those attributed in the text to a URL were fetched
by this audit's research passes on 2026-09-18. The following were re-fetched
independently by the auditor as spot checks and matched exactly — Granger's
Light Table retrospective, the Eve wind-down post, Guo's two Python Tutor
statements, Pharo's feature page (via an Internet Archive snapshot; the live page
now returns a stub), and the ODB and TOD cost figures. Where a figure comes from
a research pass and was not re-fetched here, it is marked UNVERIFIED at the point
of use.

Secondary-source fallback: the GLM-5.3-flash route was attempted for the
historical gaps. This auditor's own run returned nothing —
`tmp/glm/live-env-history.status` reads `attempt=1 rc=1 FAILED provider-limit`,
its search backend reporting "Weekly/Monthly Limit Exhausted" until 2026-09-22 —
as did the claim-3, claim-6 and claim-8 runs. One research pass's third attempt
did eventually complete (`tmp/glm/live-eval-gaps`), and its only unique
contribution was a set of Observable quotes that the pass recorded as UNVERIFIED
and did not promote, having equivalent statements from docs it had fetched
itself. **No claim in this report derives from GLM.** A Grok lookup was then run for the
remaining scale questions (`tmp/ai/live-env-scale2.md`, returned 2026-09-19,
"claims checked: 42"). It is used in one place only — the largest-program table —
where each item it supplied is labelled a Grok lookup and marked UNVERIFIED. The
two Erlang sources it pointed to were fetched and text-extracted by the auditor
directly and are cited as primary. This session's web-search budget was exhausted
(200/200), so late lookups were done by direct `curl`.

One point remains open and is marked where it appears: no source read here
establishes the largest Smalltalk or Pharo program on which live class
redefinition was actually performed.

## The short answer

Almost none of this is new, most of it has been built, and the parts that
survived share one property: they gave up on completeness. Every shipped system
in this audit bounds what it materializes — Python Tutor stops at 1,000
execution steps, Pernosco dims every loop iteration but the current one, React
Fast Refresh documents six cases where it silently drops your state, rr replays
one thread at a time. The supplied claims are written in the unbounded form
("permanent", "all intermediate values", "every iteration simultaneously"), and
the unbounded form is exactly what no one shipped.

The strongest single piece of evidence is that the author of the flagship
instant-feedback editor said in print that instant feedback was not the
bottleneck. Chris Granger, "Toward a better programming", 2014-03-27
(https://chris-granger.com/2014/03/27/toward-a-better-programming/, read
2026-09-18):

> "With Light Table for example, I thought shortening the feedback loop would
> make a tremendous difference, and while it does make a big impact, it's
> overshadowed by the fact that it's the same old broken version of
> programming."

> "People still struggled. I still struggled. It didn't deliver us from the
> incredible frustration that is writing and debugging software."

## Where each supplied claim is answered

| # | Supplied claim, short | Concept | Where | Register depth |
| --- | --- | --- | --- | --- |
| 1 | Zero-turnaround continuous evaluation | C6 + loop cost | [C6](#c6-mutable-program-during-execution) | Section (CLAIMS.md: "Live code swap by trampoline or module reload") |
| 2 | Parameter scrubbing | C1 precondition; agent twin is a sweep | [Rulings](#rulings-what-belongs-to-a-different-kind-of-project) | Ruled out |
| 3 | Bidirectional source-to-visual mapping | C3 | [C3](#c3-provenance) | Section; pixel-to-code ruled out |
| 4 | Time mapped to space | C2 | [C2](#c2-execution-history-as-data) | Section; trajectory drawing ruled out |
| 5 | Unfolded iteration tables | C2 + C10 | [C2](#c2-execution-history-as-data), [C10](#c10-self-describing-data) | Section |
| 6 | Data-reified schematics, ghost waveforms | C10 | [C10](#c10-self-describing-data) | Ruled out as a domain |
| 7 | Gesture and performance capture | — | [Rulings](#rulings-what-belongs-to-a-different-kind-of-project) | Ruled out |
| 8 | Ambient state introspection | C2 + C10 | [C2](#c2-execution-history-as-data), [C10](#c10-self-describing-data) | Section |

Claim 5 also touches [C9](#c9-programs-as-structure-not-text), which CONCEPTS.md
assigns to `06-structural-editing.md`. That report is not listed in this
programme's README; the gap is noted, not fixed here.

## C2. Execution history as data

*The record of a run is a value the system can keep, search and re-enter.*
Supplied claims 4, 5 and 8 are three renderings of this one concept: a
trajectory drawn across the screen, a table of every loop iteration, and every
intermediate value left permanently visible. All three assume the history
exists. The research question is what it costs to have it.

### What has been built

| System | Author, date | What the language or runtime had to provide | Status |
| --- | --- | --- | --- |
| Omniscient Debugger (ODB) | Bil Lewis, AADEBUG 2003 | A JVM: bytecode instrumentation of every assignment, plus heap room for the event log | Built and abandoned (proof-of-concept freeware) |
| TOD | Pothier, Tanter, Piquer, OOPSLA 2007 | The same instrumentation, plus a dedicated 10-node distributed database off the machine under test | Research prototype; never productized |
| rr | Mozilla; O'Callahan, Jones, Noll, Froyd, Huey, USENIX ATC 2017 | Nothing from the language. x86-64 (or Apple M1+) Linux, a known syscall set, and one thread at a time | Shipped and in use (free software) |
| Pernosco | O'Callahan and Huey | An rr-compatible binary with DWARF; statically compiled languages | Shipped and in use (commercial, subscription) |
| Python Tutor | Philip Guo, since 2010 | A debugger hook in the language runtime (`bdb`) and a heap walkable from globals | Shipped and in use, 25M+ users |
| Projection Boxes / VERSABOX | Sorin Lerner, CHI 2020 | Re-execution of the whole program on every keystroke, over small inputs; Python in the browser | Demonstrated only on small examples |
| FLiPS | Sorin Lerner, UIST 2020 | The same, plus programmer-supplied hypothetical loop-entry values stored in comments | Demonstrated only on small examples |
| "Learnable Programming" timelines | Bret Victor, September 2012 | A pure, deterministic, cheaply restartable drawing program | Not built as a system |

### The cost, in numbers

This is the part of the agenda with real measurements, and they are the reason
the unbounded form was never shipped.

Bil Lewis, "Debugging Backwards in Time", AADEBUG 2003
(https://arxiv.org/pdf/cs/0310016, read 2026-09-18):

> "In a 31-bit address space, there is room to store about 10 million events. A
> huge percentage of real bugs fit nicely into this space. A good percentage
> don't."

> "Performance is not an issue for bugs which generate less than 10 million
> events. At a rate of 2µs/event, it takes only 20 seconds to fill the entire
> 2GB address space."

His measured slowdowns, verbatim: "Debugging ODB back-end — 300x", "Debugging
ODB display — 10x", "Debugging Ant — 7x", with tight numeric loops at 300x.
Twenty seconds of recording is the ceiling for a naive full trace. Lewis is
explicit that the ODB "represents a worst-case implementation".

Pothier, Tanter and Piquer, "Scalable Omniscient Debugging", OOPSLA 2007
(https://pleiad.cl/papers/2007/pothierAl-oopsla2007.pdf, read 2026-09-18) state
why the idea did not reach production:

> "Omniscient debuggers make it possible to navigate backwards in time within a
> program execution trace, drastically improving the task of debugging complex
> applications. Still, they are mostly ignored in practice due to the challenges
> raised by the potentially huge size of the execution traces."

> "The potentially huge size of these traces poses several scalability
> challenges, which are the main reason for the lack of production-quality ODs."

Their numbers, after building a dedicated 10-node distributed database to solve
it:

> "On a dedicated 10-node cluster TOD handles a sustained input rate of approx.
> 470kEv/s (thousands events per second), and hundreds of queries per second."

> "Experiments show that the average size of an event is kek = 38 bytes."
> "in average an event plus the associated index data occupies 190 bytes of
> storage, although the event itself occupies only 38 bytes."

> "The recorded execution trace comprises around 720 million events and weighs
> in at 33GB."

> "the overhead imposed on the application execution time is similar in TOD and
> ODB: around 115 times the cost of standalone execution."

That is the honest price of claim 8 read literally: a 10-node cluster, 115x
slowdown, 33 GB for one Eclipse session, and an admission that the object-id
index alone "would require P · 10^7 = 40GB of buffer space, which is not a
reasonable figure".

The general instrumentation cost is documented by the Valgrind manual
(https://valgrind.org/docs/manual/manual-core.html, read 2026-09-18):

> "Memcheck adds code to check every memory access and every value computed,
> making it run 10-50 times slower than natively."

> "the minimal tool, called Nulgrind, adds no instrumentation at all and causes
> in total 'only' about a 4 times slowdown."

Supervised execution that captures *nothing* already costs 4x. Microsoft states
the same order for OS-level time-travel recording
(https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/time-travel-debugging-overview,
read 2026-09-18): "You can expect about a 10x-20x performance hit in typical
recording scenarios."

### The engineering answer: recompute, do not store

rr's contribution is to stop storing values and store only the nondeterminism,
then recompute everything by replaying. rr-project.org (read 2026-09-18):

> "rr records a group of Linux user-space processes and captures all inputs to
> those processes from the kernel, plus any nondeterministic CPU effects
> performed by those processes (of which there are very few). rr replay
> guarantees that execution preserves instruction-level control flow and memory
> and register contents. The memory layout is always the same, the addresses of
> objects don't change, register values are identical, syscalls return the same
> data, etc."

> "The overhead of rr depends on your application's workload. On Firefox test
> suites, rr's recording performance is quite usable. We see slowdowns down to
> ≤ 1.2x."

Measured overheads from the ATC 2017 paper (arXiv:1705.05937, read 2026-09-18),
recording slowdown: `cp` 1.49x, `make` 7.85x, `octane` 1.79x, `htmltest` 1.49x,
`sambatest` 1.57x. The paper's summary: "Excluding make, RR's recording slowdown
is less than a factor of two."

The price is paid in parallelism instead of storage:

> "emulates a single-core machine. So, parallel programs incur the slowdown of
> running on a single core. This is an inherent feature of the design."

This is the single most important structural finding in the audit: **two to
three orders of magnitude separate storing the history (ODB, TOD: 115x, tens of
GB) from reconstructing it (rr: 1.2–1.8x, a log of syscalls).** Every shipped
system in this concept is on the reconstruct side.

Pernosco then builds the queryable database from the replay, not from the
recording (https://pernos.co/about/vision/, read 2026-09-18):

> "We record application execution with rr and then build an omniscient database
> of CPU-level state by replaying execution with binary instrumentation.
> Deferring database construction to the replay phase keeps the initial overhead
> low while the application is interacting with its environment (e.g., avoiding
> spurious timeouts). We don't waste much effort if tests don't fail."

And states its own ceiling:

> "The obvious barrier to omniscient debugging is scalability: building and
> storing that database is very expensive. We have made tremendous technical
> improvements over previous implementations of omniscient debugging, and can
> demonstrate cost-effective debugging of complex applications with recorded
> execution times of many minutes (though not yet hours)."

### The hard question: how many iterations can be shown

Claim 5 asserts every iteration side by side. No one does this, and the people
who tried published why.

Victor's own demo, "Learnable Programming", September 2012
(https://worrydream.com/LearnableProgramming/, read 2026-09-18), loops twenty
times, and his answer for more is to stop showing iterations:

> "The example above only loops twenty times. Is it possible to understand a
> loop with, say, thousands of iterations, without drowning in thousands of
> numbers? Yes -- there is an entire field of study devoted to depicting large
> amounts of numbers. To visualize this data, we can use all of the standard
> techniques of data visualization. In the following example, as the programmer
> zooms the timeline out, the visualization automatically switches from a table
> to a plot."

TOD arrived independently at the same answer and implemented it — event density
murals, "a 'reduced representation of an entire information space that fits
entirely within a display window'" — plus selective tracing: "Support for
partial traces by offering static and dynamic mechanisms for selective trace
generation".

Sorin Lerner built the iteration table for real. "Projection Boxes:
On-the-fly Reconfigurable Visualization for Live Programming", CHI 2020
(https://cseweb.ucsd.edu/~lerner/papers/projection-boxes-chi2020.pdf, read
2026-09-18):

> "There is one projection box for each line in the program. Each box is a table
> of values, with each column being a variable name, and each row being a runtime
> state. The "#" column shows iteration counts for loops."

His first stated problem is the claim's assumption:

> "One challenge in live programming environments for general purpose languages
> is information overload. Indeed, displaying updated runtime values at virtually
> each and every change can be intrusive, overwhelming and/or distracting, which
> could ultimately offset some of the benefits of the visualization."

> "The biggest drawback of projection boxes as described so far is that they
> display a lot of data, which can lead to information overload."

Of ten study subjects asked which view they preferred, three chose the one that
shows everything: "Q5 is a multiple choice question, whose answer distribution
was (out of 10 subjects): Full (3), Summary (1), Row (6), Stealth (0)." And the
paper declines the systems problem outright:

> "There are many systems challenges in making this kind of "run-always" approach
> practical, including efficiently running code, supporting I/O, and supporting
> infinite-running programs. While these systems challenges are not fully solved
> yet, in this paper we explicitly do not address these."

Lerner's follow-up, "Focused Live Programming with Loop Seeds", UIST 2020
(https://cseweb.ucsd.edu/~lerner/papers/FLiPS-uist2020.pdf, read 2026-09-18),
is a direct refutation of claim 5's central sentence — that errors become
"visually apparent the moment the code is typed":

> "In this paper we show that such input values are insufficient for imperative
> programs, in a fundamental way. Indeed there are cases where input values will
> never drive an incomplete imperative program to show useful live data in a
> loop. This is because the data that is useful for writing the code inside a
> loop is generated by the loop itself, which does not happen until the loop has
> been fully written. In essence, until the loop is written in full, the live data
> in the loop is either unavailable, incomplete or incorrect, which not only
> defeats the purpose of live programming, but worse yet actually leads to
> programmers being confused. This situation can arise in a such fundamental
> settings as: insertion sort, Dijkstra's algorithm for shortest path, building
> histograms, reversing a list, and building an interpreter."

> "First, there is no input that the user can provide which would rectify the
> situation."

His fix is to show *fewer* iterations, not more: "the live data visualization is
modified to only display the one iteration with the loop seeds". He also records
that concrete data from a half-written loop actively misleads: "a buggy loop can
generate intermediate iterations where the list is not even sorted."

Even Pernosco, the strongest shipped system here, cannot lay iterations out
spatially (https://pernos.co/about/control-flow/, read 2026-09-18):

> "Loops have to be flattened onto the linear source view. We highlight the lines
> executed in the current iteration of any (possibly nested) loop(s) the
> application is currently in [...] Also, lines executed in this function
> activation but not in the current loop iteration are highlighted with a lighter
> color."

And the exact feature of claim 8 — values shown inline in the source as they
change — is listed by Pernosco under **Future work**, not shipped
(https://pernos.co/about/vision/, read 2026-09-18):

> "Variable value annotations in source code. Pernosco should display the values
> of variables as they changed across source lines, so data changes over time can
> be directly visualized instead of having to set the current moment in time to
> successive states."

### The demo that named the concept ran on a recorded tape

Claim 4 is close to a transcript of one 2012 demo, and the demo's own mechanism
is the audit's answer to it. Bret Victor, "Inventing on Principle", CUSEC 2012,
transcript at
https://raw.githubusercontent.com/ezyang/cusec2012-victor/master/transcript.md
(read 2026-09-18), at 13:20:

> "if you have a process in time, and you want to see changes immediately, you
> have to map time to space. ... hit this button here, which shows my guy's
> trail. So now I can see where he's been. And when I rewind, this trail in front
> of him is where he is going to be. This is his future. And when I change the
> code, I change his future."

And at 12:43, the mechanism:

> "now when I move it forward, it's going to simulate it, using the same input
> controls, the same keyboard commands recorded as before, but with the new
> code."

The "future" is a re-simulation of a **recorded input tape** under edited code.
It is not a prediction of a live future, and it could not be: a live future
depends on input not yet given. That single sentence answers the branching-
futures question for the whole claim — the demo does not solve branching, it
eliminates it by fixing the inputs. Which is, exactly, replay.

This also explains why the shipped systems in this concept all look backwards.
rr, Pernosco, WinDbg TTD and IntelliTrace reconstruct a finished recording;
Blender motion paths and Maya motion trails draw authored keyframe data; Unreal's
`PredictProjectilePath` predicts an input-free ballistic dummy over a default
two-second horizon, not the entity's behavioural logic. Pernosco lists comparing
two executions as unsolved future work:

> "One of the most difficult debugging scenarios is explaining why something
> didn't happen. One way to attack this problem would be to compare an execution
> where something didn't happen with a "closely related" execution where it did."

### The one that shipped, and what it gave up

Python Tutor is the only system in this concept with a documented mass user
base. pythontutor.com (read 2026-09-18): "Since 2010 over 25 million people in
more than 180 countries have used it to visualize over 500 million pieces of
code". Philip Guo states its limit himself, IEEE Software Blog, 2019-02-26
(http://blog.ieeesoftware.org/2019/02/python-tutor.html, read 2026-09-18 and
re-verified by direct fetch for this report):

> "It records a full trace of the stack and heap state at all execution steps and
> then sends the trace to the web frontend to render as interactive diagrams. The
> main limitation of this "trace-everything" approach is scalability: it's clearly
> not suitable for code which runs for millions of steps or creates millions of
> objects. But code written by instructors and students in educational settings is
> usually small -- running for dozens of steps and creating around a dozen data
> structures -- so this simple approach works well in practice."

> "stopping after 1,000 execution steps and suggesting for the user to shorten
> their code"

Note what the successful system does *not* do: it shows one step at a time with
a forward/back stepper, not an unfolded table. The system that reached 25 million
users shipped the pinhole Victor criticized.

### The designer of the concrete-first idea on his own results

Jonathan Edwards introduced example-centric programming (Subtext, OOPSLA 2004)
and spent two decades building versions of it. His own retrospective, September
2025, is the plainest abandonment statement in this audit:

> "It is fair to say that Subtext was a series of overambitious failed
> experiments."

And on why the demos did not transfer (2020):

> "Small contrived examples don't cut it. TodoMVC doesn't cut it."

He also gave the best description of how the working systems actually behave, in
2004: they project "the illusion that the complete details of execution and state
are present when in fact only the minimum necessary is being recorded."

(These three quotations come from the claim-5 research pass, which fetched
alarmingdevelopment.org directly; they were not re-fetched by this auditor, so
treat the dates as UNVERIFIED at this level.)

### Agent-facing form

A person scrubs a timeline; an agent queries a history. The agent version of
claims 4, 5 and 8 is one thing: **a recorded run that answers questions**
— "when did this become zero", "who wrote this address", "what were the values
of `i` and `lo` on every iteration of this loop" — returned as structured data,
not rendered. Pernosco's dataflow view is the shipped proof that the query is
the valuable half:

> "Pernosco can trace dataflow backwards in time, from where a variable has an
> incorrect value back to where that variable was set — instantly."

This inverts the human ranking. The trajectory drawing, the side-by-side
columns and the inline value overlay are all renderings of a query result, and
an agent needs the result, not the rendering. Weighted per EVALUATION.md: agent
value **high**, human value high but achievable only in bounded form.

### Reachable for A7?

Yes, and more cheaply than for most languages, because rr requires exactly what
A7 already produces: an unmodified native x86-64 Linux binary with DWARF.
Pernosco's own scope statement (https://pernos.co/faq/, read 2026-09-18):

> "Currently we support x86-64 Linux, and statically compiled languages producing
> DWARF debugging information including C, C++, Ada and Rust."

A7 needs no runtime of its own for this. It needs debug information that names
A7 constructs rather than generated Zig ones, which is C3 below. Without C3, an
rr session on an A7 program shows the user generated Zig — true, useless.

## C3. Provenance

*Every value, allocation and effect can name where it came from.* This is
supplied claim 3, and it is the concept the rest of this report's
recommendations depend on.

### What has been built

| System | Author, date | What the language or runtime had to provide | Status |
| --- | --- | --- | --- |
| Alice Whyline | Ko and Myers, CMU, CHI 2004 | A scene-graph language whose output objects have identity — Ko's own phrase, "a rigid definition of output" | Built and abandoned |
| Java Whyline | Ko and Myers, CMU, ICSE 2008 (Distinguished Paper) | Bytecode instrumentation recording every value; all output through standard Java I/O; a reimplemented `Graphics2D` with occlusion tracking | Built and abandoned; source dumped to GitHub 2016-05, no commits since |
| Program slicing | Weiser, ICSE 1981 / IEEE TSE 1984 | A system dependence graph over the whole program; in practice a commercial analyzer | Shipped as a technique (GrammaTech CodeSurfer) |
| Dynamic slicing | Korel and Laski 1988; Agrawal and Horgan, PLDI 1990 | A dynamic dependence graph, which "may be unbounded in length" | Research; used inside tools |
| Sketch-n-Sketch | Chugh et al., U. Chicago, PLDI 2016 / UIST 2019 | A custom DSL with value traces on numbers, and SVG output whose shapes keep identity | Demonstrated only on small examples |
| JS source maps | TC39-TG4, ECMA-426 | Only that the compiler emit a position-pair side table | Shipped and in use at web scale |
| Chrome DevTools element inspection | Google | A DOM that survives to the output and is hit-testable | Shipped and in use |
| RenderDoc pixel history | Baldur Karlsson | A capturable, replayable graphics API; per-API support added over a decade | Shipped and in use |
| Flutter DevTools widget inspector | Google | Source instrumentation (`--track-widget-creation`) that disables `const` canonicalization in debug builds | Shipped and in use |
| The claim as written | — | — | Not built |

### The hard question: what is "the line responsible"

The foundational definition already answers this, and the answer is not "a
line". Mark Weiser, "Program Slicing", IEEE TSE SE-10(4), July 1984
(https://se421-fall2018.github.io/resources/readings/WeiserStaticSlicing.pdf,
read 2026-09-18; the PDF is a scan, quotes OCR-normalized for letter spacing
only):

> "There can be many different slices for a given program and slicing criterion.
> There is always at least one slice for a given slicing criterion-the program
> itself."

> "Theorem: There does not exist an algorithm to find statement-minimal slices
> for arbitrary programs."

The ICSE 1981 version states it in one sentence: "Finding a slice is in general
unsolvable."

So the answer is a set, it is not unique, and the smallest one cannot be
computed. The measured size of the set is the decisive number. Binkley, Gold and
Harman, "An Empirical Study of Static Program Slice Size", TOSEM 16(2), 2007
(https://www.cs.loyola.edu/~binkley/papers/tosem-slice-size.ps, read 2026-09-18;
PostScript converted locally, word spacing restored):

> "The results show that, for the most precise slicer, the average slice contains
> just under one third of the program."

> "for Slicer s1 over all 43 programs, the average backward slice contained 28.1%
> of the program and the average forward slice contained 26.1% of the program."

> "Consider a program whose average size is near the average size for the entire
> collection. For example, ijpeg contains about 20 KLoC and has an average slice
> size of 31%, or 5,761 LoC."

On a 20,000-line program, "which code produced this?" answers with about 5,761
lines. The claim's "the specific line of code and variable responsible" is off by
three orders of magnitude, and the range across programs is 7.4% to 61.7%.

Note also that the claim's *forward* direction — hover a statement, highlight its
pixels — is the harder one: the forward slice averages 26.1% of the program, so
one statement in a loop or a helper contributes to a large fraction of the
output.

### It is two hops, and the first one usually does not exist

A pixel is four bytes and records nothing about its origin. The Whyline's answer
to "which code drew this?" was to rebuild the renderer. Ko and Myers, ICSE 2008
(https://faculty.washington.edu/ajko/papers/Ko2008JavaWhyline.pdf, read
2026-09-18 — Ko's hosted revision, footer "Most up-to-date version: 06/22/2021",
not the ACM camera-ready):

> "The creation of an I/O history is fundamental to the Whyline's question
> support: it is how the Whyline establishes a connection between the pixels on
> screen and the data and logic used to paint the pixels."

> "To recreate this history, we created an emulator for the Graphics2D class,
> including special support for the use of double buffering, in order to track
> precisely when and where each render event occurred on screen. As these events
> are read from the trace, we also track when they occlude other render events"

So: hop 1 is pixel to output primitive, which requires a scene graph that
survived to the output or a reconstruction of one; hop 2 is primitive to code,
which requires value provenance. The claim assumes hop 1 is free. It is free only
where object identity reaches the output — a DOM node, an SVG shape, a widget
tree — and that is precisely where the technique ships.

The natural experiment is the Whyline itself, the same authors and the same
interaction on two languages. On Alice, a pedagogical 3D scene-graph language
(CHI 2004 abstract, https://faculty.washington.edu/ajko/papers/Ko2004Whyline.pdf,
read 2026-09-18):

> "Comparisons of identical debugging scenarios from user tests with and without
> the Whyline showed that the Whyline reduced debugging time by nearly a factor of
> 8, and helped programmers complete 40% more tasks."

Ko names the reason himself in the ICSE 2008 paper:

> "The Alice Whyline [8] supported a similar interaction technique, but for an
> extremely simple language with little need for procedures and a rigid
> definition of output (in a lab study, the Whyline for Alice decreased debugging
> time by a factor of 8)."

On Java, where identity had to be rebuilt, the result drops and the cost appears
(ICSE 2008 abstract): "novice programmers with the Whyline were twice as fast as
expert programmers without it" — on one task, against a control group reused from
a prior study. Measured cost, ICSE 2008 Table 1:

| Program | LOC | Test case | Tracing slowdown | Events | Trace (MB) | Load (s) |
| --- | --- | --- | --- | --- | --- | --- |
| Binclock | 177 | run for five seconds | 1.7x | 140,268 | 4.7 | 2.5 |
| jTidy | 12,258 | clean one HTML page | 15.3x | 16,504,866 | 118.1 | 13 |
| JEdit | 66,403 | open, type, quit | 7.2x | 8,983,890 | 84.5 | 17.5 |
| javac | 54,054 | compile 2,810 lines | 8.5x | 35,193,667 | 283.6 | 46.5 |
| ArgoUML | 113,117 | load to splash, quit | 5.1x | 18,303,691 | 137.6 | 14.2 |

And the authors' own limit, verbatim:

> "The Whyline approach has several limitations. First and foremost, because it
> is a trace based approach, it is not practical for executions that span more
> than a few minutes, or those that process or produce substantial amounts of
> data."

That is the largest this was ever shown working on: ArgoUML at 113 KLoC, for one
minute of interaction, at 137 MB and a 14-second load.

The Whyline's designers could not decide between the last writer and the whole
dependence closure, so they shipped both on a modifier key: "By default, this
command finds the 'source' of a value, which is where the value was computed or
instantiated (the direct data dependency is reached using a modifier key)." What
it returns is "a sequence of executions" and, for why-not questions, "a set of
potential explanations" — never a line. That is the honest admission that "the
line responsible" is not a function of a pixel.

The GPU tools agree by construction. RenderDoc's pixel history shows "every
modification to the selected texture from the start of the frame", "each
modifying event as its own row", and lets you "expand each event to see if there
were multiple fragments" — it is a list because there is no singular answer, and
it colors rows red for fragments that failed a test, so the causes of a pixel
include draws that did not write it. Neither RenderDoc nor Nsight maps back to
application source at all.

### What actually shipped: positions, not values

The mass-market instance of this concept is the JavaScript source map, and what
it maps is worth stating exactly: **positions to positions**. It carries
generated-position to original-position pairs plus identifier names, and nothing
about values, and the ECMA-426 draft (dated 2026-09-11) concedes that stack
mapping "without knowledge of the source language is not covered". That is the
entire commercial answer to "an optimizing compiler destroyed my mapping", and it
is enough to power every browser's debugger.

The recurring pattern across every shipped system is that provenance is a side
channel bought with an optimization. Flutter's widget inspector needs
`--track-widget-creation`, which "prevents otherwise-identical const Widgets from
being considered equal in debug builds" — the identity the mapping needs is
exactly the identity `const` canonicalization destroys, so Flutter turns the
optimization off in debug builds. The Whyline skips "methods that, once
instrumented, exceed the 65,536 byte length limit imposed by the JVM", so some
methods have no mapping at all. Sketch-n-Sketch's traces "record data flow but
not control flow", and only on numbers.

INFERENCE: the general rule is that provenance is not preserved for free by a
compiler; it is an artifact the compiler must be asked to emit, it costs either
an optimization or a recording, and it degrades to positions when it has to cross
an optimizing back end.

### Agent-facing form

A person hovers and sees a highlight; an agent asks a question and gets a set of
source locations. The agent version of claim 3 is **a provenance lookup**: given
an observed value, an address, a diagnostic or a crash, return the source
constructs implicated, as data. CONCEPTS.md states the payoff: provenance
"converts 'read the code and reason about it' into a lookup".

Two things follow from the evidence above. First, an agent is the *right*
consumer for a 5,761-line slice — it can filter, rank and test candidates, where
a person cannot read them. The measured slice size that kills the human version
does not kill the agent version. Second, the positions-only form that shipped
(source maps) is sufficient for the agent's most common needs: putting a
diagnostic, a profiler sample, a stack frame or a debugger stop on the right
line of the language the user actually wrote.

Agent value **high**. Human value high, but only where output identity survives.

### Reachable for A7?

The positions-only form is reachable now and is the cheapest high-value item in
this report; the value-level form is not, and does not need to be.

A7 already computes spans and drops them. `SourceSpan` rides on every AST node
(`a7/ast_nodes.py:162`) and is serialized by
`a7/formatters/json_formatter.py:82-89`; `a7 --mode ast --format json` on
`examples/004_func.a7` emits 146 spans (6 null). `a7/backends/zig.py` emits none
of this: it writes Zig text with no record of which A7 span produced which line.
There is nothing downstream to catch a mapping either — a full-text scan of the
Zig 0.16.0 language reference (https://ziglang.org/documentation/0.16.0/, read
2026-09-18, 411,765 characters extracted) found zero occurrences of `#line`,
"line directive" or "source map".

Function-level correspondence survives by accident: compiling
`examples/004_func.a7` emits `fn add`, `fn greet` and `fn divide` with A7's own
names, so a debugger already lands somewhere recognizable. Statement-level does
not, and the generated prelude corresponds to no A7 source at all.

## C6. Mutable program during execution

*Code and data layouts change while the program runs, without discarding the
state built so far.* This is supplied claim 1. It is the oldest item on the list
— continuously shipped since 1980 — and the one whose agent value is lowest.

### The hard question is the only question: what happens to the state

Every system that has built this had to answer one question, and they gave six
different answers. The claim assumes the answer is free.

| System | Answer to "state when the code changes" | Status |
| --- | --- | --- |
| Common Lisp `defvar`/`defparameter` | The programmer chooses per variable, at the definition site | Shipped (ANSI Common Lisp) |
| CLOS class redefinition | Automatic reshaping, lazy, identity preserved, with an overridable migration generic function | Shipped |
| Smalltalk / Pharo | Automatic reshaping of live instances | Shipped (Smalltalk-80 lineage) |
| Erlang/OTP | Mandatory hand-written, versioned migration (`code_change/3`) | Shipped and in production |
| webpack / Vite HMR | Nothing preserved unless the module author wrote a `dispose` handler | Shipped at web scale |
| React Fast Refresh | Best-effort preservation with six documented ways to lose it silently | Shipped at web scale |
| Unreal Live Coding / Live++ | Hand-written pre/post-patch hooks; stack objects cannot migrate at all | Shipped on AAA C++ |
| Godot | Undocumented | Shipped |
| Jupyter | Preserved — and that is the defect | Shipped at enormous scale |
| Observable | Discard and recompute every downstream cell | Shipped |
| Hazel | Re-run from scratch, except for hole filling | Research proof-of-concept |

Self makes the same point more sharply: the answer depends on which editor pane
you typed in. Self Handbook 2024.1
(https://handbook.selflanguage.org/2024.1/howtoprg.html, read 2026-09-19, via the
claim-1 research pass):

> "changing a method in an ordinary outliner would just affect that one object,
> even if other objects had been cloned from it"

> "when a method is changed from the debugger, every slot pointing to that same
> method is made to feel the change—the method is changed in place"

The Lisp case is the cleanest statement that the concept is underdetermined. CLHS
`defparameter, defvar`
(https://www.lispworks.com/documentation/HyperSpec/Body/m_defpar.htm, read
2026-09-18):

> "defparameter unconditionally assigns the initial-value to the dynamic variable
> named name. defvar, by contrast, assigns initial-value (if supplied) to the
> dynamic variable named name only if name is not already bound."

Reloading the same source text has two incompatible correct answers, and the
language makes you pick one by choosing a different macro. Decades of live systems have not found a third option.

Pharo is the most complete implementation of the claim. pharo.org/features (live
page now returns a stub; quoted from the Internet Archive snapshot
https://web.archive.org/web/2024/https://pharo.org/features, read 2026-09-18,
and spot-verified by direct fetch of that snapshot for this report):

> "Pharo can evolve while it's running. It is like an organism. You can do things
> like add or remove instance variables of classes that have already existing
> instances. All these living instances will be properly modified."

> "These capabilities are essential for the ability of the system to evolve
> without the need for restarts."

The cost Pharo's own page does not mention is documented on the Squeak side: an
old class definition does not disappear when you change it, it survives in the
image as `ObsoleteMyClass`, kept "to support existing instances"
(https://wiki.squeak.org/squeak/2176, read 2026-09-18). That is live code in the
running system corresponding to no source definition anywhere — the exact
opposite of the claim's "permanent, continuous synchronization", produced by the
most complete implementation of it. INFERENCE: this is why rebuilding an image
from source alone is a known hard problem in every Smalltalk community; that
generalization is the auditor's reading, not a sourced claim.

Hand-written migration is not unique to Erlang — CLOS, Live++ and webpack/Vite
all expose a hook — but Erlang is the one system where it is *mandatory and
versioned*, tied to a release upgrade with an explicit old-version argument. The documented failure mode is a hard limit the claim's word
"permanent" cannot survive — Erlang "Code Replacement"
(https://www.erlang.org/doc/system/code_loading.html, read 2026-09-18):

> "If a third instance of the module is loaded, the code server removes (purges)
> the old code and any processes lingering in it are terminated."

React Fast Refresh is the mass-market instance, and its own documentation is the
best evidence against the strong claim. Next.js, "Fast Refresh"
(https://nextjs.org/docs/architecture/fast-refresh, read 2026-09-18):

> "Fast Refresh tries to preserve local React state in the component you're
> editing, but only if it's safe to do so. Here's a few reasons why you might see
> local state being reset on every edit to a file:
>  * Local state is not preserved for class components (only function components
>    and Hooks preserve state).
>  * The file you're editing might have *other* exports in addition to a React
>    component.
>  * Sometimes, a file would export the result of calling a higher-order component
>    like `HOC(WrappedComponent)`. If the returned component is a class, its state
>    will be reset.
>  * Anonymous arrow functions like `export default () => <div />;` cause Fast
>    Refresh to not preserve local component state."

> "In particular, `useState` and `useRef` preserve their previous values as long
> as you don't change their arguments or the order of the Hook calls."

> "Finally, if you **edit a file** that's **imported by files outside of the React
> tree**, Fast Refresh **will fall back to doing a full reload**."

The largest programs this was ever shown working on are C++ game codebases —
during development, not in players' hands. Epic states the scope: "Editing your
application in Unreal Editor. Running your application with Play In Editor (PIE).
Running a packaged Desktop build of your application attached to the editor for
debugging." And there the vendor documents crashes. Unreal Engine, "Using Live Coding"
(https://dev.epicgames.com/documentation/en-us/unreal-engine/using-live-coding-to-recompile-unreal-engine-applications-at-runtime,
read 2026-09-18):

> "Live Coding can still easily handle small changes to code such as changes in
> variable values or minor changes to existing functions."

> "large-scale changes to code, such as new functions, new sets of variables, or
> dramatic re-factors, will behave unpredictably when you attempt to compile them
> without Object Reinstancing. This will usually result in crashes."

Live++ states the underlying constraint (https://liveplusplus.tech/docs/documentation.html,
read 2026-09-18):

> "When making structural changes to existing code and data, Live++ has to make
> sure that new code can correctly work with existing data allocated and stored in
> an old memory layout. In order to do so, existing objects must have their data
> migrated from the old into the new memory layout, which can be achieved by using
> pre-patch and post-patch hot-reload hooks."

> "Keep in mind that **objects created on the stack cannot be migrated to a new
> class layout.**"

That last sentence is the ceiling for any statically compiled language with
stack-allocated values, A7 included. And the same vendor states the limit on the
word "instantaneous" outright, under "Functions on the stack"
(https://liveplusplus.tech/docs/documentation.html, read 2026-09-19, fetched and
text-extracted directly for this report):

> "Because of how code patching in Live++ works, functions currently on the stack
> need to be re-entered before any of their code changes can be observed."

> "This is a limitation inherent to the patching mechanism used by Live++ and
> cannot be changed."

The vendor's hedge in between — "In practice this is almost never a problem" — is
a claim about frequency, not about permanence. The code you are currently
executing inside is the code that cannot update, and the vendor says that cannot
be fixed. That is the most precise refutation of claim 1 in this audit, from the
system with the largest native deployment.

Jupyter is the counterexample that matters most, because it is the most widely
deployed live-state environment in existence and its best-known critique is
precisely that source and state diverge. Joel Grus, "I don't like notebooks.",
JupyterCon NY, 11:55am Friday 24 August 2018. Slide text from the deck's own
export endpoint
(https://docs.google.com/presentation/d/1n2RlMdmv1p25Xy5thJUhkKGvjtV-dkAIsUXP-AL4ffI/export/txt,
read 2026-09-19, fetched directly for this report):

> "notebooks have tons and tons of hidden state that's easy to screw up and
> difficult to reason about"

> "because there's some computation that ran between the first two cells that I
> can't see"

Grus then anticipates the obvious objection, and his answer is the sharpest
conceptual point in this audit:

> "some of you are thinking that my REPL has plenty of hidden state too"

> "which it does, but that state was built up in a linear fashion, which I can
> see just by scrolling back in my terminal"

**What continuous evaluation destroys is not the state, it is the account of how
the state got there.** A REPL keeps just as much hidden state as a notebook; what
it also keeps is a linear, readable history of the commands that produced it. An
environment that re-evaluates as you type, in whatever order you edit, keeps the
state and discards the derivation. That is a cost the supplied claims never
mention, and it bears directly on agent value: a history an agent can read is
worth more than a current state it cannot explain.

It is not only an opinion. Pimentel, Murta, Braganholo and Freire, "A Large-scale
Study about Quality and Reproducibility of Jupyter Notebooks", MSR 2019
(https://www.ic.uff.br/~leomurta/papers/pimentel2019a.pdf, read 2026-09-18),
measured it over 1,159,166 notebooks from 264,023 GitHub repositories:

> "out of 863,878 attempted executions of valid notebooks (i.e., notebooks with
> defined Python version and execution order), only 24.11% executed without
> errors and only 4.03% produced the same results."

> "Among the notebooks with unambiguous execution order, 36.36% have cells
> out-of-order."

That is the audited claim's own premise, measured at scale and failing: the most
widely deployed environment that keeps state and materializes output produces
documents where 95.97% of stored outputs do not reproduce. Materialized values
that are stale look authoritative, which is worse than no values.

Observable's answer is to remove the degree of freedom rather than display more
state — "Cells run in topological order ... Observable runs like a spreadsheet"
(observablehq.com documentation, recovered from the Internet Archive snapshot
20250124135058 after the live site returned HTTP 429 on every attempt).

Hazel is the closest the literature comes to the claim, and it gets there by
removing the hard case — a pure functional language with no mutable external
state. Omar, Voysey, Chugh and Hammer, "Live Functional Programming with Typed
Holes", POPL 2019 (https://arxiv.org/abs/1805.00155, read 2026-09-18):

> "Rather than aborting when evaluation encounters any of these holes as in some
> existing systems, evaluation proceeds around holes, tracking the closure around
> each hole instance as it flows through the remainder of the program."

> "Hole closures also enable a fill-and-resume operation that avoids the need to
> restart evaluation after edits that amount to hole filling."

The self-limitation is in the sentence: resume applies to edits "that amount to
hole filling", and nothing else. The authors call the result "a proof-of-concept
live programming environment".

### What Light Table and Eve actually say

Light Table was built (Kickstarter 2012), shipped, and archived — GitHub
LightTable/LightTable (read 2026-09-18): "This repository was archived by the
owner on Oct 21, 2022. It is now read-only." Granger's 2014 verdict is quoted at
the head of this report: the feedback loop "does make a big impact" but was
"overshadowed".

Eve's end was commercial, and the report should not overstate it. Chris Granger,
"Eve is winding down", eve-talk, 2018-01-24
(https://groups.google.com/g/eve-talk/c/YFguOGkNrBo/m/EozaCfheAQAJ, read
2026-09-18, verified by direct fetch for this report):

> "Despite some promising leads and lots of meetings over the past several months,
> we weren't able to find a good home for Eve. Unfortunately that means we have to
> start the process of winding the company down and looking for other
> opportunities for ourselves."

That is a funding statement, not a technical verdict. The technical verdict is the
2014 Light Table quote, and it is about feedback loops specifically.

### Agent-facing form

Low. An agent does not have a session to preserve; it rebuilds and re-runs. What
matters to an agent is the concept CONCEPTS.md names alongside C6: **the cost of
the loop** — wall-clock time from edit to observed behavior. That is a number,
and for A7 it is measured below.

Agent value **low to medium**; human value high. Under this programme's weighting
this is the lowest-priority item on the list, which inverts its position in the
supplied claims, where it is first.

### Reachable for A7?

Not in the claim's form, and it should not be attempted. A7 compiles ahead of
time to a native binary with stack-allocated values and no runtime; Live++'s
"objects created on the stack cannot be migrated to a new class layout" applies
directly. Getting hot code swap would mean a development-time interpreter or a
trampoline-based dynamic-linking scheme, i.e. a second execution model to build
and keep consistent with the first.

The reachable version is loop latency, and A7 is already close. Measured on this
machine 2026-09-18, zig 0.16.0, CPython 3.13.15
(`tmp/research/live-environment/probe/loop-latency.txt`):

| Step | Time |
| --- | --- |
| A7 full pipeline, `--mode pipeline`, `001_hello.a7` (4 lines) | 108 ms |
| A7 full pipeline, `037_language_tour.a7` (143 lines) | 217 ms |
| A7 compile to `.zig`, `037_language_tour.a7` | 142 ms |
| `zig build-exe`, cold cache | 5626 ms |
| `zig build-exe`, after a one-literal edit | 346 ms |

The steady-state edit-to-binary loop is about **0.5 s** for the largest example
in the repository, and A7's own share of it is 142 ms with no incremental
compilation anywhere in `a7/compile.py`. INFERENCE: sub-second is already inside
the range where liveness buys little for an agent, so the return on building
incremental compilation in A7 now is low. Zig 0.16.0 release notes
(https://ziglang.org/download/0.16.0/release-notes.html, read 2026-09-18) note
that the downstream half can improve further but is not yet safe to rely on:

> "Incremental compilation still has known bugs, including some miscompilations,
> and therefore remains disabled by default in 0.16.0."

## C10. Self-describing data

*A type carries how it should be presented, and tools render it accordingly.*
This is the concept under supplied claim 6 (values drawn on the topology,
previous behavior left as a ghost) and the display half of claims 5 and 8.

### The finding: it shipped, industrially, and only where the program is already a diagram

Every shipped instance of "values drawn on the structure" is a domain where the
program *is* the structure before any tool touches it: a circuit, a block
diagram, a statechart, a dataflow graph. The topology exists first; the tool
annotates it. There is no shipped equivalent for imperative text, because there
is no canonical spatial layout of a C function.

It is worth separating three things the claim runs together:

- **(a)** an instantaneous scalar annotated onto the topology;
- **(b)** a time-series waveform drawn *along* the wire;
- **(c)** dragging a parameter leaves a persistent ghost of the previous
  behavior, in place.

| System | (a) scalar on topology | (b) waveform on wire | (c) ghost in place | What it required | Status |
| --- | --- | --- | --- | --- | --- |
| LabVIEW (NI, since 1986) | Yes | No — probes open a side window | No | A user-placed dataflow graph; an execution mode that trades speed for the display | Shipped and in use |
| Simulink port value labels | Yes | No — "similar to a tooltip" | No | A block diagram, and signals the accelerator did not optimize away | Shipped and in use |
| Simulink Data Inspector | — | — | Run-vs-run, in a separate window | Two runs whose signals align; unchanged topology | Shipped and in use |
| Stateflow animation | Yes, categorical | Nothing continuous to draw | No | A statechart; simulation mode, not accelerator, SIL or PIL | Shipped and in use |
| Falstad / CircuitJS | Yes (wire color, current dots) | No — scopes at the window bottom | No | A user-drawn schematic and an idealized component model | Shipped and in use |
| LTspice | DC operating point on hover only | No — separate plot pane | `.step` family, in the plot pane | A closed set of sweepable parameters; N complete batch re-runs, nested at most three deep | Shipped and in use |
| Victor's circuit environment | Yes | Yes | Claimed, unverified | A hand-built environment over one hand-built circuit | Demonstrated once, in a talk |

Only one artifact in this audit is said to do all three, and it is a talk — and
the third category could not be verified even there. Bret Victor,
"Media for Thinking the Unthinkable", MIT Media Lab, 4 April 2013
(https://worrydream.com/MediaForThinkingTheUnthinkable/, read 2026-09-18):

> "To show current, the symbolic representation of each component is replaced
> with a visual representation of the component's data."

> "This representation conveys the same structural information as a conventional
> schematic, but it conveys behavior as well. It's built out of live data, not
> dead symbols."

That is almost word for word the supplied claim's first two sentences. The same
page ends:

> "All of the examples I've shown here are hints. They are nibbling at the
> corners of a big problem — what is this new medium for understanding systems?"

> "We have an opportunity to reinvent how we think about systems, to create a new
> medium. I don't know what that medium is, but if you'd like to help find it, let
> me know."

Nothing on the page offers the environment for download. Two attribution
corrections matter. The word "ghost" does not appear on that page; a full-text
scan found no occurrence, and the page's own wording is "visually overlay any
voltage on all other voltages to compare" — which is comparing different signals
within one run, not a previous run against the current one. And the page
attributes the drag-leaves-a-trace mechanism to a different talk, "Inventing on
Principle, 23:22", whose video could not be fetched (FETCH FAILED
https://vimeo.com/36579366, Cloudflare gate). So category (c) is UNVERIFIED even
as a demonstration.

The one shipped tool that draws a real waveform on a node body is TouchDesigner,
and it proves the dimensionality rule rather than breaking it: "CHOP Viewer - A
2D viewer to inspecting and editing CHOP channel values. Time is on the x-axis,
value (or amplitude) is on the y-axis" — a CHOP channel *is* a scalar over time.
The hardware world's equivalent is explicit that it is not live at all: "GTKWave
is designed for post-mortem analysis by analyzing dumpfiles rather than real-time
interaction during simulations", and its back-annotation writes values into RTL
source text, not onto a schematic.

### The hard question: what does it take to generalize

Three preconditions, each established from a primary source.

**The topology must pre-exist.** LabVIEW, Simulink, Stateflow, SPICE and Falstad
all get their layout from the program itself. For text the layout would have to
be derived, and a derived layout moves when the text changes. INFERENCE: this is
why no one ships it for C or Python; it is not stated in any source fetched here.

**The ghost requires a cheap, pure re-run over one swept scalar.** LTspice's
`.step` is the shipped form, and the help text says exactly what it does
(https://ltwiki.org/LTspiceHelpXVII/LTspiceHelp/html/DotStep.htm, read
2026-09-18, an ltwiki HTML mirror of the LTspice help file, not an ADI-hosted
page):

> "This command causes an analysis to be repeatedly performed while stepping the
> temperature, a model parameter, a global parameter, or an independent source."

> "Perform the simulation three times with global parameter Rload being 5, 10 and
> 15."

The overlaid family is N independent batch simulations, not a memory of an
interaction. Victor states the same precondition in functional terms in "Up and
Down the Ladder of Abstraction", October 2011
(https://worrydream.com/LadderOfAbstraction/, read 2026-09-18): "A concrete
representation corresponds to a function that takes no arguments", and abstracting
over a variable "turns the time variable into an argument". The ghost picture is
the graph of a pure function `f(t, p)`. Vary anything but `p` and Victor's own
verdict on the technique is:

> "We're attempting to overlay trajectories from different environments in the
> same space. This representation, though visually attractive, is difficult to
> make sense of."

MathWorks ships the same constraint as a documented restriction
(https://www.mathworks.com/help/simulink/ug/compare-simulation-data.html, read
2026-09-18): "The Simulation Data Inspector only compares signals from the
Baseline run that align with a signal from the Compare To run." Change the
topology and the comparison breaks.

**The value must be a scalar over time.** A voltage graphs; a hash table does
not. Stateflow is instructive here: a statechart's live datum is *which state is
active*, a categorical value, so what Stateflow draws is a highlight, not a
graph. There is nothing continuous to plot on a transition arrow.

**And the live view costs execution speed.** This is documented by two vendors
independently. NI on Execution Highlighting
(https://www.ni.com/en/support/documentation/supplemental/12/debugging-techniques-in-labview.html,
read 2026-09-18):

> "Note: Execution highlighting greatly reduces the speed at which the VI runs."

MathWorks on Stateflow animation
(https://www.mathworks.com/help/stateflow/ug/animate-stateflow-charts.html, read
2026-09-18): "Animation does not run in accelerator mode", "Animation does not run
for SIL or PIL modes." And on port value labels
(https://www.mathworks.com/help/simulink/ug/displaying-block-outputs.html, read
2026-09-18): "Port value labels do not show values for output signals of blocks
that are optimized out of the simulation target for accelerator mode."

You get the live view or you get speed. Every shipped system makes you choose,
which is the direct industrial refutation of claim 8's word "permanently".

### The one system built on this concept as a concept

Glamorous Toolkit (Tudor Gîrba, feenk) is the only shipped environment whose
organizing idea is per-type projections. gtoolkit.com and the GT book
(https://book.gtoolkit.com/inspector-6k9vwubemen05fcxg4kv6wi6b, read 2026-09-18):

> "Each class can define object extensions that are meaningful for inspecting
> instances of that class."

> "Every object is different and should be allowed to look different, too."

And it states the cost plainly (gtoolkit.com FAQ, read 2026-09-18):

> "You can use existing tools, but if you want to leverage Glamorous Toolkit to
> its full potential, you have to program it."

> "Thus, if a tool does not yet exist, it is imperative that developers build
> one."

That is the honest price and it is not small: the view is hand-written, one per
class. GT is *not* ambient — nothing materializes itself. Its enabling condition
is also stated: "We implemented it primarily in Smalltalk because it offers a
reflective system in which the environment can be changed live while using it."
Status: shipped and in use, on a small base.

### Agent-facing form

This is where the concept earns its place, and it is the cheapest item in the
whole audit. A person reads a rendered inspector; an agent reads a **structured
projection** — the same per-type declaration, a different renderer. The mechanism
is one projection function per type; only the back end differs (a canvas for a
person, JSON for an agent). CONCEPTS.md already rules this in on those grounds,
and CLAIMS.md gives it Report depth: "For a person, a canvas; for an agent, a
structured projection instead of a memory dump. Same mechanism, two renderers."

Agent value **high**. Human value high in the domains that already have a
diagram, low elsewhere.

### Reachable for A7?

The agent form is reachable and cheap; the visual form is not A7's business. A7
would need a way for a type to declare a projection, and it has no general
mechanism for attaching anything to a type today. What exists is narrower: an
`is_tagged` flag on union declarations (`a7/ast_nodes.py:183`), the `@type_set`
generic constraint (`a7/parser.py:682`, and the only intrinsic CLAUDE.md lists as
supported), and internal preprocessor annotations such as `resolved_type`
(`a7/ast_nodes.py:253-257`) that are compiler state, not user-facing. None is a
user-declarable attribute. A7 would need that, plus a consumer that prints the
projection as structured text. It needs no runtime and
no editor. The decision A7 must make first is where projection metadata lives:
in the type declaration (a language change, requiring the approval process in
CLAUDE.md), or in the debug information as a side table (no language change).

## C9. Programs as structure, not text

*The canonical form of a program is a tree or graph with identity; text is one
projection.* The historical claim is about editors. The version that matters here
is narrower: if constructs have stable identity, then provenance, diffs and
incremental compilation become precise rather than line-based.

### Evidence

Hazel is the strongest research instance, and it earns the liveness of claim 1 by
being a structure editor first. Omar et al., POPL 2019
(https://arxiv.org/abs/1805.00155, read 2026-09-18):

> "The implementation inserts holes automatically, following the Hazelnut edit
> action calculus, to guarantee that every editor state has some (possibly
> incomplete) type."

hazel.org (read 2026-09-18) states the consequence: "Every incomplete program
that you can construct using Hazel's language of edit actions is both statically
and dynamically well-defined" — "there are no meaningless editor states". That
property is what makes evaluation-while-typing possible at all, and it is
unavailable to a text editor over a text language.

Sketch-n-Sketch is the other instance, and its published limit is exactly the one
C9 predicts: its value traces "record data flow but not control flow", and only
on numbers — so which branch produced a shape is not recoverable. Structure
without control-flow identity buys only part of the mapping.

JetBrains MPS is the one projectional editor that shipped with a named
industrial user — the Dutch Tax and Customs Administration, per JetBrains' own
case study. Be precise about what it provides: MPS replaces text with a
projection of the tree, giving notation freedom and precise structural edits. It
does **not** display live runtime values; it is not an instance of claims 1, 5 or
8. Intentional Software, the other commercial attempt, ended in acquisition by
Microsoft (announced 2017-04-18). Both of these come from the claim-5 research
pass rather than a first-hand fetch by this auditor; treat the case-study
attribution as UNVERIFIED at this level of detail.

CONCEPTS.md assigns C9 to `06-structural-editing.md`, which this programme's
README does not list; that report is where the projectional-editor evidence
belongs and where MPS should be examined properly.

### A7's own evidence is stronger than any of it

A7 is the negative case, documented in its own audits. Every pass keys node
identity by the Python `id()` of the AST object
(`docs/audits/2026-09-16/compiler/parser.md:372`), and the backend audit names
the consequences directly
(`docs/audits/2026-09-16/compiler/backend.md:508-511`):

> "Node identity: `type_map` in the backend and `BackendPlan` in safety are keyed
> by `id(node)`, with no stable node identity. This is the cause of ZIG-1."

> "Declaration identity: `_mutated_vars` and `_used_identifiers` are keyed by
> name, with no declaration identity. This causes ZIG-13, ZIG-14 and ZIG-25."

The hazard is visible in the source. `a7/ast_preprocessor.py:130-137` keeps
every replaced node alive for the lifetime of the tree solely so that its `id()`
cannot be recycled:

> "type_map is keyed by id(node): if a replaced node (or one of its children)
> were freed, a later new node could reuse its id and inherit its type."

That is four miscompile classes and a memory-retention workaround, all bought by
not having stable identity. The concept is not an editor feature for A7; it is a
correctness fix that happens to also enable provenance and incremental
compilation later.

### Agent-facing form

An agent editing structure produces fewer invalid programs than one editing text,
and a diff over structure is a better input than a patch. But the near-term agent
value is indirect: stable identity is what lets a provenance table (C3) survive
an edit, and what lets a cache key on something other than a file hash.

Agent value **medium to high**, mostly through C3. Human value medium.

### Reachable for A7?

Yes, and it is already on A7's own roadmap as the typed IR (Wave 3). The work is
to give AST nodes a stable identity field and move analysis annotations into side
tables keyed by it, which the parser audit already prescribes: "Move analysis
annotations (types, implicit refs, casts) out of the syntax tree into side tables
keyed by node ID." No language change, no runtime, no editor. It is the one item
in this report that A7 would benefit from even if none of the live-programming
agenda were ever pursued.

## Rulings: what belongs to a different kind of project

Per [EVALUATION.md](../EVALUATION.md), an idea that belongs to a graphics tool,
a music environment or an authoring tool gets a paragraph saying why it stops
here and what the transferable idea is — not a report. The register in
[CLAIMS.md](../CLAIMS.md) already rules these out; this section records the
evidence behind the rulings and nothing more.

### Claim 2, parameter scrubbing

Bret Victor demonstrated it in "Inventing on Principle" (CUSEC, January 2012).
The page `https://worrydream.com/InventingOnPrinciple/` now returns
`301 Moved Permanently` to `https://vimeo.com/906418692` (read 2026-09-18): the
canonical artifact is a video, and no tool was ever released. That is the whole
history in one redirect.

What makes it hard beyond the demo is not the interaction, it is the
precondition: the program must be re-runnable from scratch, cheaply, and
identically, for every value the drag passes through. Victor states the
precondition himself in "Up and Down the Ladder of Abstraction" (October 2011):
"A concrete representation corresponds to a function that takes no arguments."
A program with side effects re-runs its I/O on every mouse-move; a program with
accumulated state gives a different answer on the second pass; and a value that
is not a literal — computed, folded, read from configuration — has no source
position to grab. The shipped instances are all in domains that satisfy the
precondition by construction: CSS value dragging in browser dev tools, and
parameter sliders in circuit and shader tools. The shipped industrial form of
the same idea is a batch parameter sweep, not a drag (LTspice `.step`, quoted
under C10).

**Ruling: out of scope, agent twin retained.** The agent version of a scrub is a
parameter sweep — run the program N times over a range and compare the outputs
— which is property testing, already covered by C1 and by the runtime-model
programme. It needs determinism (C1) and nothing else.

**Research gap, stated:** the agent assigned to this claim terminated on an API
error, and the GLM fallback could not run (provider quota exhausted:
`tmp/glm/live-env-history.status`, "attempt=1 rc=1 FAILED provider-limit"). So
the intended lookups on Khan Academy's scrubbable-number editor (John Resig,
c. 2012) and Adobe's Project Para were **not completed**, and no claim is made
about them here.

### Claim 7, gesture and performance capture

This is the one claim that is largely *solved*, in a different industry, and it
is solved in a way that contradicts the claim's own framing. Recording a
performed curve and then editing it is routine in audio and animation tools.
Ableton Live manual, "Automation and Editing Envelopes"
(https://www.ableton.com/en/live-manual/12/automation-and-editing-envelopes/,
read 2026-09-18):

> "When Automation Arm is on, all changes of a control that occur while the
> Control Bar's Arrangement Record button is on become Arrangement automation."

> "Click at a position on a line segment to create a new breakpoint there."

Unreal Engine's Take Recorder
(https://dev.epicgames.com/documentation/en-us/unreal-engine/take-recorder-in-unreal-engine,
read 2026-09-18): "Take Recorder records gameplay animation, live performances,
and other sources into Unreal Engine directly." TouchDesigner's Record CHOP
(https://docs.derivative.ca/Record_CHOP, read 2026-09-18) "takes the channels
coming in the first (Position) input, converts and records them internally, and
outputs the stored channels as the CHOP output."

Note where the recording lands in every one of these: an automation lane, a Level
Sequence, a CHOP channel — a **side artifact referenced by the program**, never
the program text. That is the distinction the claim elides. A 60–240 Hz sample
stream is a buffer, not a program; making it editable requires curve fitting or
keyframe reduction, which is lossy; and turning one recorded performance into a
reusable function of a parameter is generalization from a single example, which
is a programming-by-example problem, not a recording problem.

**Ruling: out of scope. No agent value.** An agent does not perform gestures. The
one transferable idea is that a recorded input stream is replayable data, which
is the input journal of C1 and C2 — already covered, and covered better there.

**Research gap, stated:** the agent for this claim could not be launched
(concurrency limit) and the evidence above was gathered directly; the intended
coverage of TidalCycles, Sonic Pi, Extempore and Max/MSP was **not completed**.
Given the ruling, it was not pursued further, per EVALUATION.md.

### Claim 6's domain, and claim 4's trajectory drawing

Both are ruled out in CLAIMS.md as belonging to a circuits tool and a graphics
environment respectively. The concept underneath each is kept: the value-on-
structure display is C10, and the recorded-history-across-time capability is C2.
Both are treated above.

## Verdict table

One row per supplied claim, using the four rulings: **shipped and in use**,
**built and abandoned**, **demonstrated only on small examples**, **not built**.
Several claims need two, because the claim as written and the part that shipped
are different things; the bold label leads, the qualifier follows. "Closest
system" is the one that came nearest to the claim as written, not the most
famous.

| # | Claim | Ruling | Closest system | Why it is not universal |
| --- | --- | --- | --- | --- |
| 1 | Source and running program in permanent sync | **Built and abandoned** as a general product; **shipped and in use** in bounded form | Smalltalk/Pharo (since 1980); React Fast Refresh at web scale | State migration after a shape change has no general answer. Pharo mutates instances and accumulates `ObsoleteMyClass` definitions with no source; React publishes six ways it silently drops state; Live++ says stack objects "cannot be migrated"; Unreal says large changes "will usually result in crashes". Light Table shipped it and its author said the loop was not the bottleneck |
| 2 | Scrubbing a literal re-runs the program live | **Demonstrated only on small examples**; **shipped and in use** only where re-running is cheap | Browser dev tools CSS value dragging; LTspice `.step` as the batch form | Requires a pure, cheap, identical re-run per value. Side effects re-fire, accumulated state diverges, and a value that is not a literal has no source position to grab. The canonical artifact is a 2012 talk whose page now redirects to a video |
| 3 | Pixel ↔ the specific line and variable, both ways | **Not built** as stated; **shipped and in use** where output identity survives | Java Whyline (abandoned 2016); Flutter widget inspector and Chrome DevTools, shipped | Slicing answers with a set: 28.1% of the program on average, 5,761 lines on a 20 KLoC program, and minimal slices are uncomputable. A framebuffer pixel has no provenance, so hop one must be rebuilt — the Whyline wrote a `Graphics2D` emulator to do it, at 1.7–15.3x and up to 283 MB |
| 4 | Time unfolded across space, futures reshaped live | **Not built** forwards; **shipped and in use** backwards, over finished recordings | Pernosco (commercial) and rr (free), over finished recordings | Victor's own demo re-simulated a *recorded input tape*; a live future depends on input not yet given. Pernosco flattens loops onto the source view, caps at "many minutes (though not yet hours)", and lists comparing executions as future work |
| 5 | Every loop iteration shown side by side | **Demonstrated only on small examples** | Projection Boxes / VERSABOX (Lerner, CHI 2020) | Its author's next paper documents the loop-datavoid problem — live data inside a half-written loop "is either unavailable, incomplete or incorrect" — and his fix shows *one* iteration. Victor's demo loops twenty times and switches to a plot beyond that. Python Tutor shipped to 25M users with a 1,000-step cap and a one-step-at-a-time stepper |
| 6 | Values on the wires, ghost of the previous run | **Shipped and in use** for scalars on the topology; **not built** for waveforms on wires or in-place ghosts | LabVIEW (1986), Simulink port value labels, Stateflow animation | Every shipped instance annotates a topology the program already was; there is no canonical layout of a text function. The waveform always goes in a separate pane — ten teams, four decades, same choice. The ghost needs a pure re-run over one swept scalar, and even the demo's version of it could not be verified |
| 7 | Performed gesture becomes editable program data | **Shipped and in use** — as a referenced asset, not as program text | Ableton automation recording; Unreal Take Recorder | The recording lands in an automation lane, a Level Sequence or a CHOP channel — a side artifact the program references. A 60–240 Hz sample stream is a buffer; making it editable needs lossy curve reduction, and making it reusable needs generalization from one example |
| 8 | All intermediate values permanently materialized | **Not built**, and unbounded by construction | rr plus Pernosco, by recomputing rather than storing | Capturing values costs 10–50x (Valgrind Memcheck) and 115x with a 10-node cluster (TOD); recording nondeterminism and replaying costs ~1.5x. Every shipped inline-value feature is gated on paused + current frame + viewport. "Permanently" has no fixed point for a program of unbounded run length |

## The largest program each was shown working on

The original brief asks this of every claim. It is the question the literature
answers least often, and where a figure exists it is usually smaller than the
system's reputation implies.

| System | Largest documented case | Source |
| --- | --- | --- |
| Java Whyline | ArgoUML, 113,117 LOC, one minute of interaction: 5.1x slowdown, 18.3M events, 137.6 MB, 14.2 s to load. javac over a 2,810-line file produced 283.6 MB and a 46.5 s load. Authors' own bound: "not practical for executions that span more than a few minutes" | Ko and Myers, ICSE 2008, Table 1 and §7 |
| TOD | One Eclipse session: 720 million events, 33 GB, at 313 kEv/s, needing a dedicated 10-node cluster | Pothier et al., OOPSLA 2007 |
| Omniscient Debugger | 10 million events, about 20 seconds of recording before a 2 GB address space fills | Lewis, AADEBUG 2003 |
| Pernosco | "recorded execution times of many minutes (though not yet hours)" | pernos.co/about/vision/ |
| rr | Firefox test suites, Samba, Chromium, QEMU, LibreOffice, Wine — real applications, at ≤1.2x on Firefox suites | rr-project.org; ATC 2017 |
| Python Tutor | 1,000 executed steps; source under roughly 2,000 characters; no libraries, no I/O, no multi-file | Guo, IEEE Software Blog 2019-02-26; pythontutor.com |
| Projection Boxes | Ten subjects, six list-manipulation tasks; "used on unit test inputs, which are relatively small" | Lerner, CHI 2020 |
| Sketch-n-Sketch | "68 little programs of varying complexity, spanning more than 2,000 lines of code in total" | Chugh et al., PLDI 2016 |
| Hazel | Authors' own word: "proof-of-concept"; no size figure published for live evaluation of holes. A later Hazel paper on code completion had to build its corpus by concatenation — "we have emulated a larger more realistic codebase by combining those five programs ... to create a 1000-line simulated codebase" — which is the closest number anyone puts on a Hazel program, and it is simulated. UNVERIFIED (Grok lookup; not re-fetched here) | Omar et al., POPL 2019; Blinn et al., OOPSLA 2024 |
| Unreal Live Coding | AAA C++ codebases during development, and at that scale the vendor documents that large changes "will usually result in crashes" without Object Reinstancing. Note the documented scope: "Editing your application in Unreal Editor. Running your application with Play In Editor (PIE). Running a packaged Desktop build of your application attached to the editor for debugging." No source establishes it patching a retail build with players connected | Epic, Live Coding docs |
| Pharo / Smalltalk | No figure for live class redefinition. The largest production Smalltalk codebase found is MediaGeniX Whats'On at "1.9 Million lines of code / 15.000 own classes / 200.000 methods", but that source is about continuous integration, not about redefining a class in a running production image. UNVERIFIED (Grok lookup; not re-fetched here) | STIC 2012 slides |
| Erlang hot code loading | **The largest in this audit by a wide margin.** Armstrong's thesis: "At the time of writing (2003) the AXD301 has over 1.7 million lines of Erlang code which probably makes it the largest system ever to be written in a functional style of programming"; his own case study used a version with "over 1.1 million lines of Erlang". Cronqvist's 2004 Erlang Workshop slides put it at "~2.1 million lines of Erlang / ~300 coders (cumulative)" and list, under "No Down Time (99.999% availability)", the line "Updating code in running systems is routine" | Armstrong, PhD thesis 2003 (erlang.org/download/armstrong_thesis_2003.pdf); Cronqvist, ACM SIGPLAN Erlang Workshop 2004 (erlang.org/workshop/2004/matsbilder.pdf). Both fetched and text-extracted directly, read 2026-09-19 |
| LabVIEW, Simulink, LTspice, GTKWave | Industrial scale, but for values-on-topology only, and LabVIEW's live view "greatly reduces the speed at which the VI runs" | NI, MathWorks docs |

The pattern is that the systems with large numbers attached (Erlang, rr, Unreal,
the EDA and simulation tools) are the ones that gave up the strongest form of the
claim, and the systems that implement the strongest form (Whyline, TOD, ODB,
Projection Boxes, Hazel) are the ones whose largest case is a minute, a lab task,
or a proof of concept.

Erlang is the instructive exception and deserves stating plainly: it is the one
system here that runs the concept at multi-million-line industrial scale, in
production, for decades. It gets there by conceding everything the supplied
claims assert. There is no continuous synchronization — code is loaded in
discrete, versioned release upgrades. Nothing is automatic — the programmer
writes `code_change/3` by hand for every stateful process. And only two versions
of a module may coexist; load a third and "any processes lingering in it are
terminated". The concept scales exactly as far as the guarantees are weakened.

## What the survivors have in common

Six properties, each with evidence in this report.

**1. They bounded what they materialize, and said so.** Python Tutor stops at
1,000 steps and Guo publishes the reason. VS Code's `InlineValuesProvider` is
called only "whenever the generic debugger has stopped", for one `frameId`, over
one `viewPort`. Pernosco dims every loop iteration but the current one. The
unbounded versions — ODB's full trace, TOD's 720-million-event database — are the
ones that did not ship.

**2. They reconstruct rather than store.** The single largest cost difference in
this audit is between capturing values and capturing only nondeterminism and
replaying — two to three orders of magnitude, measured, in the C2 cost tables
above. Every shipped omniscient system is on the reconstruct side.

**3. They kept the derivation, not just the state.** Grus's observation about the
REPL is the general rule: what makes state comprehensible is a readable record of
how it was produced. rr keeps an input journal, Erlang keeps versioned release
upgrades, LTspice re-runs from a stated parameter list, Observable recomputes
from a dependency graph. Jupyter is the case that keeps state and loses the
derivation, and it is the one with a measured 4.03% reproduction rate. For an
agent this property dominates the others: a history it can read beats a live
state it cannot explain.

**4. The evaluation model was pure, cheap to restart, or externally journalled.**
Hazel gets resume-after-edit by being a pure functional language with no mutable
external state, and even then only for hole filling. LTspice gets its overlaid
curve families by re-running the whole analysis N times. rr gets replay by
capturing the process's inputs at the kernel boundary. Nothing here preserves a
mutable heap across an arbitrary code change and calls it solved; Live++ says
outright that "objects created on the stack cannot be migrated to a new class
layout".

**5. The domain already had a spatial form.** Every shipped instance of values
drawn on structure — LabVIEW, Simulink, Stateflow, SPICE, Falstad — annotates a
topology the program already was. No one ships it for imperative text.

**6. The live view was optional, because it costs speed.** NI: "Execution
highlighting greatly reduces the speed at which the VI runs." MathWorks:
"Animation does not run in accelerator mode." Every vendor makes the user choose
between the live view and the fast path, which is the direct industrial
refutation of "permanent".

The counter-pattern is equally clear. The projects that tried to deliver the
unbounded version as a product — Light Table, Eve, the Omniscient Debugger, TOD,
Intentional Software — are the ones that are archived, wound down, or never
productized. And the strongest testimony is from the person best placed to give
it: the author of Light Table concluded that the shortened feedback loop was
"overshadowed by the fact that it's the same old broken version of programming."

## For A7

A7 compiles ahead of time to Zig and runs as a native binary. It has no runtime
of its own, no incremental compilation (no cache of any kind in
`a7/compile.py`), no editor integration — `docs/audits/2026-09-18/production-readiness.md:1104`
records "Language server | None" and `:1105` "Syntax grammar for editors | None"
— and no mapping from the generated Zig back to `.a7` lines.

### What A7 already has, exactly

This matters, because two of the five concepts are much closer than they look.

**Source spans exist and survive to the JSON dump.** `SourceSpan` is carried on
every AST node (`a7/ast_nodes.py:162`) and serialized by
`a7/formatters/json_formatter.py:82-89`. Measured on `examples/004_func.a7`:
`a7 --mode ast --format json` emits 146 spans, 6 of them null.

**The spans are dropped at codegen.** A grep of `a7/backends/zig.py` for line,
position or source-map emission finds nothing; the backend writes Zig text and
keeps no correspondence. Zig cannot recover it either: a full-text scan of the
Zig 0.16.0 language reference (https://ziglang.org/documentation/0.16.0/, read
2026-09-18, 411,765 characters of extracted text) found **zero** occurrences of
`#line`, "line directive" or "source map". There is no downstream mechanism to
push a mapping into; A7 would have to emit a side table itself.

**Function-level correspondence survives by accident.** Compiling
`examples/004_func.a7` emits `fn add`, `fn greet`, `fn divide` with the A7 names
intact, so a debugger stopping in `add` already lands in something recognizable.
Statement-level correspondence does not survive, and the twelve-line generated
prelude (`__a7_stdout_print`, `pub fn main`) corresponds to no A7 source at all.

**The loop is already fast.** Measured 2026-09-18
(`tmp/research/live-environment/probe/loop-latency.txt`): A7's own pipeline runs
in 108–306 ms across the repository's examples, and the full edit-to-binary loop
is about 0.5 s in steady state, of which A7 is 142 ms.

### Reachability, concept by concept

| Concept | Reachable for an AOT native language? | What it would demand of A7 | Cost |
| --- | --- | --- | --- |
| **C2** execution history as data | Yes, without a runtime | Debug info that names A7 constructs, so rr/Pernosco-class tooling attaches to the binary; determinism (C1) for replay | Medium. The record-replay machinery already exists and is free; A7 supplies only the debug info |
| **C3** provenance | Yes, partially | A side table from A7 span to emitted Zig line, written at codegen; then DWARF that names `.a7` files | Low for the side table. High for full statement-level provenance through Zig and LLVM |
| **C10** self-describing data | Yes, in its agent form | A per-type projection declaration and a printer that emits structured text | Low, once A7 decides where the metadata lives |
| **C9** programs as structure | Partially, and independently valuable | Stable identity on AST nodes instead of name- and Python-object-identity keying | Medium; it is a compiler-internals change with correctness benefits of its own |
| **C6** mutable program during execution | No, not in the claim's form | A development-time interpreter or a trampolining dynamic linker — a second execution model | High, and it buys an agent almost nothing |

### The two that repay the effort first

**First: C3, a span side table at codegen.** Everything else in this report that
is reachable depends on it. Without a mapping, an rr session on an A7 program
shows generated Zig; a diagnostic points at a `.zig` line the user never wrote; a
profiler attributes time to `__a7_stdout_print`. The work is to have
`a7/backends/zig.py` record, for each emitted line, the `SourceSpan` it came
from, and write that table beside the `.zig` output. The spans are already there
and already serialized elsewhere in the compiler, so this is plumbing, not
research.

The production audit shows what a broken span already costs before codegen: across
a module import, A7's diagnostic records a span from one file with the filename of
another, so "An editor that jumps to `file` + `span` lands on unrelated code"
(`docs/audits/2026-09-18/production-readiness.md:150`). Spans that are wrong
across modules and absent across codegen are the same defect at two stages.

**Second: C2, record-replay over the native binary.** A7 produces exactly the
artifact rr consumes — an unmodified x86-64 Linux binary with DWARF — and
Pernosco's own scope statement names "statically compiled languages producing
DWARF debugging information including C, C++, Ada and Rust". A7 needs no runtime
to join that list. The agent-facing payoff is the queryable history: "when did
this become zero", "who wrote this address", answered as data. Note the two
constraints that come with it and that A7 must accept rather than solve: replay
is single-core ("emulates a single-core machine ... This is an inherent feature
of the design"), and it requires the program's nondeterminism to be capturable,
which is C1.

**Third, if there is room: C10 in its agent form.** One projection function per
type, rendered as structured text. It is cheap, it has no dependency on the
other two, and its value to an agent is immediate — a structured dump instead of
a memory dump. Its shipped precedent, Glamorous Toolkit, is honest about the
price: you write the view yourself, one per class.

### What A7 must decide first

Three decisions, in this order. None is a research question; each is a choice
that forecloses options if made late.

**1. Is there a development-time execution model other than "emit Zig, build,
run"?** Everything in claims 1, 2 and 5 assumes a program can be evaluated
cheaply, repeatedly, and partially. The options are a tree-walking interpreter
over the checked AST (two implementations to keep in agreement — and A7's audits
already record miscompiles caused by analyses keyed on names and Python object
identity, so divergence is not hypothetical), an instrumented development build,
or nothing. **Recommendation: nothing, for now.** The measured 0.5 s loop means
the interpreter would buy latency A7 does not lack.

**2. Where does the source-to-emitted mapping live, and is it a supported
artifact?** A side table next to the `.zig` file, or DWARF emitted through Zig,
or both. This decides whether the mapping is an internal debugging aid or
something a language server, a profiler and a record-replay session can all
consume. It should be decided before the language server work in the production
audit's P2 list begins, not after.

**3. Where does per-type projection metadata live?** In the type declaration —
which is a language change and needs the approval packet CLAUDE.md requires,
with current and proposed examples — or in the debug side table, which is not.
The second is reversible and should be tried first.

One thing A7 should decide *not* to do: pursue liveness in the claim-1 sense.
The evidence is that the state-migration problem is unsolved in every system in
this report, that the vendor with the largest C++ deployment documents crashes at
scale, that stack-allocated values cannot migrate at all, and that the author of
the flagship live editor said the feedback loop was not the bottleneck. For a
language whose values live on the stack and whose loop is already half a second,
this is the worst ratio of cost to benefit on the list.
