# 08 — Agentic debugging: full state, stop, and replay

Report 08 of the [debugging, testing and analysis programme](./README.md).
Question: what would it take for an agent to see every variable at every step
of a program, stop it anywhere, and replay it from that point with full state —
what exists, what it costs, and what a language must emit to support it.

Evidence standard: every quotation carries its URL and the date it was read.
Vendor claims are marked separately from measured results. Inference is marked
INFERENCE. Where sources disagree, both are given.

Scope split with the rest of the programme: report 01 (`01-debug-info.md`,
not yet written as of 2026-09-18) covers DWARF, source maps and `#line` as
*formats*. This report covers only what record-replay and full-state
inspection add on top. Sanitizers are in `docs/lang-safety/02-sanitizers.md`
and are not repeated.

## Findings in one place

1. **The full-state tape is not how anyone does it.** Recording every value at
   every step costs 12-17x slowdown and ~0.5 bits per retired instruction
   (Nirvana, measured). The deployed alternative — record only the
   nondeterministic inputs crossing a boundary and recompute the rest — costs
   under 2x on most workloads (rr, measured) and single-digit MB/s of trace.
2. **Steppable and queryable are different products.** rr gives a tape you
   step. Pernosco and WinDbg TTD build an index you ask questions of. For an
   agent that can afford thousands of questions, the index is the whole point,
   and it is the part that is either commercial (Pernosco, Undo) or
   Windows-only (TTD).
3. **"Resume with one variable changed" is not replay.** It is re-execution
   from a checkpoint. rr's own docs say state changes during replay are
   discarded. The mechanism that gives cheap repeated resume is the fuzzer
   fork server, not the record-replay debugger.
4. **The protocols are ready; the backends are not.** DAP has `stepBack` and
   `reverseContinue` in the spec, gated on a capability almost nothing sets.
   GDB/MI says of itself that it is a "machine oriented text interface" for
   "systems which use the debugger as just one small component."
5. **One benchmark measures an agent with and without a debugger.** debug-gym
   on SWE-bench Lite: a `pdb` tool takes o1-preview from 10.7% to 30.2% and
   Claude 3.7 Sonnet from 37.2% to 52.1%, and costs GPT-4o two points.
   No published work evaluates an agent against a record-replay or time-travel
   debugger at all.
6. **For A7 today, the cheapest useful step is not a source map.** Measured on
   this machine (§8): with Zig's default backend, gdb reads A7 variables by
   their A7 names but gets no line numbers at all inside the generated
   function; with `-fllvm`, lines work but one of the two A7 locals in a
   twelve-line program has no `DW_TAG_variable` at all — and emitting that
   local as Zig `var` instead of `const` makes it reappear. Pinning a backend,
   emitting provenance comments and that one-word codegen change cost about a
   day and fix more than a line map would.

---

## 1. Deterministic record and replay

### 1.1 rr (Mozilla)

The primary source is O'Callahan, Jones, Froyd, Huey, Noll, Partush,
"Engineering Record And Replay For Deployability" (USENIX ATC 2017 /
arXiv:1705.05937), read 2026-09-18 from
<https://arxiv.org/pdf/1705.05937>.

**What it records.** Not values — inputs.

> "To enable record and replay of arbitrary Linux applications, without
> requiring kernel modifications or a virtual machine, RR records and replays
> the user-space execution of a group of processes... The inputs and sources
> of nondeterminism are mainly the results of system calls, and the timing of
> asynchronous events."
> — arXiv:1705.05937 §2.1, read 2026-09-18

> "While replay preserves user-space state and execution, only a minimal
> amount of kernel state is reproduced during replay. For example, file
> descriptors are not opened, signal handlers are not installed, and
> filesystem operations are not performed."
> — arXiv:1705.05937 §2.1, read 2026-09-18

**Overhead — MEASURED by the authors**, on "a Dell XPS15 laptop with a
quad-core Intel Skylake CPU (8 SMT threads), 16GB RAM and a 512GB SSD",
geometric mean of 5 of 6 runs (Table 1):

| Workload | Baseline | Record | Replay | Single core |
| --- | --- | --- | --- | --- |
| cp | 1.04 s | 1.49x | 0.72x | 0.98x |
| make | 20.99 s | 7.85x | 11.93x | 3.36x |
| octane | 32.73 s | 1.79x | 1.56x | 1.36x |
| htmltest | 23.74 s | 1.49x | 1.01x | 1.07x |
| sambatest | 31.75 s | 1.57x | 1.23x | 0.95x |

> "Excluding make, RR's recording slowdown is less than a factor of two.
> Excluding make, RR's replay overhead is lower than its recording overhead.
> Replay can even be faster than normal execution, in cp because system calls
> do less work."
> — arXiv:1705.05937 §4.3, read 2026-09-18

`make` is the outlier and the paper says why:

> "Overhead on make is significantly higher than for the other workloads.
> Forcing make onto a single core imposes major slowdown. Also, make forks and
> execs 2430 processes, mostly short-lived."
> — arXiv:1705.05937 §4.3, read 2026-09-18

**What it cannot record.** The paper is unusually candid.

*Parallelism* is not solved, it is removed:

> "With threads running on multiple cores, racing read-write or write-write
> accesses to the same memory location by different threads would be a source
> of non-determinism. Therefore we take the common approach ... running only
> one thread at a time. RR preemptively schedules these threads, so context
> switch timing is nondeterminism that must be recorded."
> — arXiv:1705.05937 §2.2, read 2026-09-18

> "This approach is much simpler and more deployable than alternatives ... and
> is efficient for low-parallelism workloads. There is a large slowdown for
> workloads with a consistently high degree of parallelism."
> — arXiv:1705.05937 §2.2, read 2026-09-18

*Shared memory* with non-recorded processes is a hole with four named patches:

> "It is possible for recorded processes to share memory with other processes,
> and even kernel device drivers, where that non-recorded code can perform
> writes that race with accesses by tracee threads. Fortunately, this is rare
> for applications running in common Linux desktop environments, occurring in
> only four common cases: applications sharing memory with the PulseAudio
> daemon, applications sharing memory with the X server, applications sharing
> memory with kernel graphics drivers and GPUs, and vdso syscalls."
> — arXiv:1705.05937 §2.5, read 2026-09-18

*Nondeterministic instructions* are trapped one at a time:

> "One common nondeterministic x86 instruction is RDTSC, which reads a
> time-stamp counter. This particular instruction is easy to handle, since the
> CPU can be configured to trap on an RDTSC and Linux exposes this via a prctl
> API, so we can trap, emulate and record each RDTSC."
> — arXiv:1705.05937 §2.6, read 2026-09-18

> "RDRAND generates random numbers and hopefully is not deterministic. We have
> only encountered it being used in one place in GNU libstdc++, so RR patches
> that explicitly."
> — arXiv:1705.05937 §2.6, read 2026-09-18

> "RTM is nondeterministic from the point of view of user-space, since a
> hardware transaction can succeed or fail depending on CPU cache state (and
> probably the occurrence of hardware interrupts). Fortunately so far we have
> only found these being used by the system pthreads library, and we
> dynamically apply custom patches to that library to disable use of hardware
> transactions."
> — arXiv:1705.05937 §2.6.1, read 2026-09-18

*ASLR and memory layout* are reproduced rather than disabled — this is a
fidelity claim, not a limitation:

> "In particular, user-space memory and register values are preserved exactly,
> with a few exceptions noted later in the paper. This implies CPU-level
> control flow is identical between recording and replay, as is memory
> layout."
> — arXiv:1705.05937 §2.1, read 2026-09-18

*Hardware* is a real deployment constraint. rr needs a virtualized performance
counter:

> "At time of writing, most cloud providers do not virtualize any performance
> counters and thus RR does not work on them, except for Digital Ocean, where
> RR does work."
> — arXiv:1705.05937 §2.4.2, read 2026-09-18

And ARM was, at the time of the paper, a failed port:

> "Porting RR to ARM failed because all ARM atomic memory operations use the
> 'load-linked/store-conditional' approach, which is inherently
> nondeterministic."
> — arXiv:1705.05937 §5.1, read 2026-09-18

rr's own wiki now lists certain AArch64 microarchitectures, naming ARM Neoverse
N1 and Apple Silicon M-series, as supported (paraphrase: this came through the
fetch tool's summary, not raw HTML)
(<https://github.com/rr-debugger/rr/wiki/Building-And-Installing>, read
2026-09-18), so the paper's ARM statement is superseded. `io_uring` remains
unsupported: <https://github.com/mozilla/rr/issues/2613> ("Support io_uring")
was still open when read on 2026-09-18.

**Storage — MEASURED**, Table 2, geometric mean MB of trace per second of
baseline run time: octane 0.08, htmltest 0.79, sambatest 6.85, make 15.82,
cp 19.03; deflate ratios 4.87x-21.87x.

> "Different workloads have highly varying space consumption rates, but several
> MB/s is easy for modern systems to handle. In real-world usage, trace storage
> has not been a concern."
> — arXiv:1705.05937 §4.4, read 2026-09-18

**Checkpointing**, which is what makes reverse execution tolerable:

> "fork is (mostly) copy-on-write and is very well optimized on Linux, so
> creating a checkpoint typically takes less than ten milliseconds."
> — arXiv:1705.05937 §6.1, read 2026-09-18

**Queryable?** No. rr is steppable forward and backward through gdb. The query
layer is Pernosco, built on top (§2.1).

**Chaos mode** deserves a note, because it is the one feature aimed squarely
at a machine that can run a test a thousand times. It randomizes thread
priorities and inserts starvation intervals to shake out races:

> "Make most threads high-priority; I give each thread a 0.1 probability of
> being low priority. Periodically re-randomize thread priorities."
> — <https://robert.ocallahan.org/2016/02/introducing-rr-chaos-mode.html>,
> read 2026-09-18

### 1.2 Undo LiveRecorder / UndoDB — vendor claims only

Every number in this subsection is Undo's own. No independent measurement of
Undo was found.

> "1.5-5x slowdown whilst capturing on real-world programs"
> — <https://undo.io/solutions/products/live-recorder/>, read 2026-09-18
> (VENDOR CLAIM)

Their own benchmark page gives per-workload figures: sqlite (100,000
insertions) 2.6x overall, gzip (128 MB) 1.33x, ffmpeg VP9→H264 4.8x overall
and about 1.6x per thread.

> "per-thread slowdown is kept low (at 1.33 – 2.6x) by Undo's dynamic
> just-in-time instrumentation"
> — <https://undo.io/resources/undo-performance-benchmarks/>, read 2026-09-18
> (VENDOR CLAIM)

The asymmetry with rr matters: the rr paper states hardware, run count and
which run was discarded; Undo's page states none of that. Treat the two
numbers as differently supported even though they are numerically close.

Undo makes the same threading bet as rr:

> "the Undo Engine serializes the execution of threads, as if they were running
> on a uniprocessor CPU ... a global mutex such that only a single thread at a
> time can execute"
> — <https://docs.undo.io/TechnicalDetails.html>, read 2026-09-18

Shared memory across processes is supported with a stated constraint:

> "Multi-Process Correlation for Shared Memory only supports accesses to shared
> memory that is mapped at the same address in all recorded processes."
> — <https://docs.undo.io/MPCSharedMemory.html>, read 2026-09-18

Undo has one genuine query primitive rather than a query language:

> LiveRecorder can "log accesses to shared memory from multiple processes. This
> log can be queried in UDB using the ublame command to determine which of the
> recorded processes modified a region of shared memory."
> — <https://docs.undo.io/MPCSharedMemory.html>, read 2026-09-18

Storage cost per second: **not published**.

### 1.3 WinDbg Time Travel Debugging, and Nirvana/iDNA underneath it

> "Time Travel Debugging (TTD) is a tool that captures a trace of your process
> as it executes and replays it later both forwards and backwards."
> — <https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/time-travel-debugging-overview>,
> read 2026-09-18

> "You can expect about a 10x-20x performance hit in typical recording
> scenarios."
> — same URL, read 2026-09-18 (VENDOR CLAIM)

The engine descends from Nirvana/iDNA (Bhansali et al., VEE 2006), whose paper
is the best measured account of full instruction-level tracing anywhere in this
report. Table 3, read 2026-09-18 from
<https://www.usenix.org/legacy/events/vee06/full_papers/p154-bhansali.pdf>:

| Application | Instructions (M) | bits/instruction | Trace (MB) | Native (s) | Tracing overhead |
| --- | --- | --- | --- | --- | --- |
| Gzip | 24,097 | 0.08 | 245 | 11.7 | 15.98x |
| Spreadsheet | 1,781 | 0.44 | 99 | 18.2 | 5.76x |
| Presentation | 7,392 | 0.57 | 528 | 43.6 | 5.66x |
| Internet browser | 116 | 0.36 | 5.15 | 0.499 | 13.90x |
| DumpAsm | 2,408 | 0.50 | 152 | 2.74 | 17.01x |
| SatSolver | 9,431 | 1.10 | 1,300 | 9.78 | 12.98x |
| Average | | 0.51 | | | 11.89x |

> "Our current performance overhead is approximately a 12−17× slowdown of a
> cpu-intensive user-mode application."
> — VEE 2006 paper §1, read 2026-09-18 (MEASURED, by the authors)

> "The key insight for reducing the data size is to recognize that not all
> memory values that are read need to be recorded; we only need to record those
> memory reads that cannot be predicted."
> — same paper, read 2026-09-18

Divide trace size by native time and the figures are 12-133 MB per second of
*original* execution (Gzip ≈ 21 MB/s, Presentation ≈ 12 MB/s, SatSolver ≈ 133
MB/s). That division is mine, not the paper's — INFERENCE from Table 3.

Nirvana takes the opposite threading bet from rr and Undo:

> "Nirvana supports multi-threaded applications running on multiple threads and
> processors. A technique to gather traces of multi-threaded applications on
> multiple processors with very little additional overhead."
> — same paper, contributions list, read 2026-09-18

This is the sharpest design disagreement in the record-replay literature.
rr and Undo serialize to one thread and accept a large slowdown on parallel
workloads. Nirvana traces every thread and orders cross-thread events by
logging synchronization operations. No source found in this research
independently stress-tests one approach against the other.

TTD's stated limits:

> "TTD currently supports only user mode operation, so you can't trace a kernel
> mode process."

> "Read-only playback: You can travel back in time, but you can't change
> history. You can use read memory commands, but you can't use commands that
> modify or write to memory."

> "Index files can be large, typically twice as large as the trace file."
> — all three: TTD overview page, read 2026-09-18

Queryable: yes, and that is the reason TTD matters here. See §2.3.

### 1.4 Replay.io

> "A deterministic capture of every DOM change, network request, and state
> update."
> — <https://www.replay.io/about>, read 2026-09-18

> "Our median recording overhead is now 27%, but we won't stop until we are
> consistently below 20%."
> — <https://www.replay.io/blog/changelog-41-chromium-network-monitor>,
> read 2026-09-18 (VENDOR CLAIM)

Its architecture is widely assumed to be rr-derived. No fetched Replay.io page
says so. The About page says only:

> "Our founders spent a decade at Mozilla working on the Firefox browser engine
> — one of the most complex software systems ever built."
> — <https://www.replay.io/about>, read 2026-09-18

Marked UNCONFIRMED. Product status changed in 2024:

> Replay.io "discontinued Replay Test Suites" effective August 31, 2024, to
> focus on "the intersection of replayability and AI"; "Replay DevTools remains
> active".
> — <https://www.replay.io/blog/a-new-direction>, read 2026-09-18

No nondeterminism-limitation list, replay-fidelity statement or storage figure
was found. **Not published.**

### 1.5 Pernosco (recording side)

Pernosco does not record. rr records; Pernosco indexes the replay.

> "We record application execution with rr and then build an omniscient
> database of CPU-level state by replaying execution with binary
> instrumentation."
> — <https://pernos.co/about/vision/>, read 2026-09-18

> "Deferring database construction to the replay phase keeps the initial
> overhead low while the application is interacting with its environment (e.g.,
> avoiding spurious timeouts)." ... "it lets us speed up database building by
> processing different sections of a single execution in parallel."
> — same URL, read 2026-09-18

Everything rr cannot record, Pernosco cannot see. Its query model is §2.1.

### 1.6 gdb's built-in reverse debugging

Two mechanisms with opposite trade-offs, both from
<https://sourceware.org/gdb/current/onlinedocs/gdb.html/Process-Record-and-Replay.html>,
read 2026-09-18.

`record full`:

> "full — Full record/replay recording using GDB's software record and replay
> implementation. This method allows replaying and reverse execution."

The manual states no slowdown multiplier for `record full` anywhere on that
page. That was checked against the stripped HTML, not a summary. Say so
plainly, because "gdb reverse debugging is impossibly slow" is usually asserted
without a citation. The nearest primary characterisation is from an rr author
writing about gdb on rr's own wiki:

> "very very high overhead (singlesteps the program using ptrace)"
> — <https://github.com/rr-debugger/rr/wiki/Related-work>, read 2026-09-18
> (a competitor's characterisation, not gdb's own)

The same page also names what gdb's recorder does not handle:

> "unclear how modification of user memory during syscalls is recorded
> (apparently not at all)" ... "unclear how process-shared memory is dealt with
> (apparently not at all)"
> — same URL, read 2026-09-18

gdb's own documented limits:

> "Currently, process record and replay is supported on ARM, Aarch64,
> LoongArch, Moxie, PowerPC, PowerPC64, S/390, RISC-V and x86 (i386/amd64)
> running GNU/Linux."

> "The full recording method does not support these two modes." [non-stop mode
> and asynchronous execution mode]

> "Note that some side effects are easier to undo than others. For instance,
> memory and registers are relatively easy, but device I/O is hard. Some
> targets may be able undo things like device I/O, and some may not."
> — the last one:
> <https://sourceware.org/gdb/current/onlinedocs/gdb.html/Reverse-Execution.html>
> footnote 7, read 2026-09-18

`record btrace` is the hardware-assisted alternative, and the quotation below
is the single most important sentence in this section for anyone hoping
hardware tracing solves the problem:

> "btrace format — Hardware-supported instruction recording, supported on Intel
> processors. This method does not record data. Further, the data is collected
> in a ring buffer so old data will be overwritten when the buffer is full. It
> allows limited reverse execution. Variables and registers are not available
> during reverse execution."
> — Process-Record-and-Replay.html, read 2026-09-18

An agent stepping backwards through a `btrace` recording sees control flow and
nothing else.

### 1.7 Java

Chronon is the canonical Java omniscient debugger. No Chronon vendor page was
fetched; the only sourced figures are the rr wiki relaying a Chronon slide deck
— a third-hand vendor claim:

> "Chronon instruments bytecode to record variable changes and memory writes.
> Raw trace data goes to helper threads which use carefully optimized
> compression."

> "Overheads quoted in this slide deck range from >200x ... for well-optimized
> Java code that's CPU bound, down to 2x when you spend plenty of time in I/O
> or code that's excluded from Chronon instrumentation."

> "No divergence support: of course Java VMs don't support cloning, so they
> could only implement divergence using emulation"
> — <https://github.com/rr-debugger/rr/wiki/Related-work>, read 2026-09-18
> (VENDOR CLAIM relayed secondhand)

The Oracle JVMTI specification was **not fetched directly** in this research.
No JVMTI claim is made here. Undo announced LiveRecorder support for Java in
2020; the announcement page was not fetched for body text.

### 1.8 Python

`sys.monitoring` (PEP 669) is the modern low-overhead hook, and its motivation
reads like a specification for agentic debugging:

> "Developers should not have to pay an unreasonable cost to use debuggers,
> profilers and other similar tools."

> "By using quickening, we expect that code run under a debugger on 3.12 should
> outperform code run without a debugger on 3.11."
> — <https://peps.python.org/pep-0669/>, read 2026-09-18

The PEP quantifies only the cost of keeping `sys.settrace` compatibility
machinery ("between 1 and 2% speedup from not supporting sys.settrace()
directly"); it describes the settrace-versus-monitoring gap qualitatively, not
with a benchmark figure.

PyPy's RevDB is the one Python reverse debugger with published numbers:

> "Replaying a program uses a lot more memory; maybe 15x as much than during
> the recording [because] it creates many forks."

> "You can expect pypy-revdb to be maybe 3 times slower than CPython."

> "Only works on Linux and OS/X"; "Does not contain a JIT"; missing modules
> "thread, cpyext, micronumpy, _continuation"; multithreading "is possible, but
> not done yet."
> — <https://pypy.org/posts/2016/07/reverse-debugging-for-python-8854823774141612670.html>,
> read 2026-09-18

No `thread` module means RevDB cannot record thread nondeterminism at all — a
much narrower envelope than rr, Undo or Nirvana.

### 1.9 Side by side

| System | Records | Overhead | Source of number | Storage/s | Queryable |
| --- | --- | --- | --- | --- | --- |
| rr | syscall results, async-event timing, nondeterministic instructions | 1.49-7.85x (<2x excl. make) | MEASURED, ATC'17 | 0.08-19 MB/s | No — steppable only |
| Undo | same class, via JIT binary translation | 1.5-5x | VENDOR | not published | One primitive (`ublame`) |
| TTD / Nirvana | every instruction's unpredictable memory reads | 10-20x (TTD, vendor); 11.89x avg (Nirvana, measured) | both | 12-133 MB/s derived from Nirvana Table 3 | Yes — LINQ over calls and memory |
| Replay.io | DOM, network, state, in forked browsers | 27% median | VENDOR | not published | Not documented |
| Pernosco | nothing; indexes an rr replay | rr's, plus offline index build | — | not published | Yes — full index |
| gdb `record full` | memory and register deltas, in software | no figure in the manual | — | not published | No |
| gdb `record btrace` | branches only (BTS or Intel PT) | "very low overhead" (manual) | manual | ring buffer | No, and no data values |
| PyPy RevDB | operation results, not arguments | ~3x vs CPython | project blog | not published | No |

### 1.10 Where the sources disagree

- **Threads.** rr and Undo serialize; Nirvana/TTD trace all threads and order
  them by logged synchronization. Both sides publish numbers; nobody has
  compared them directly.
- **Whether full-state tracing is affordable.** Nirvana measures 11.89x average
  and ships it inside Microsoft's tooling. TOD measures 113x for the same
  ambition on a JVM, and calls the benefit worth it; Lienhard et al. (ECOOP
  2008) call that same class of approach impractical — see §2.2. The two
  measurements are not comparable as stated: different hardware (P4 2.2 GHz
  versus Pentium M 2 GHz), different workloads, different instrumentation
  levels. INFERENCE: the order-of-magnitude gap plausibly reflects machine-code
  versus bytecode instrumentation, but no source found here tests that.
- **gdb's reverse-debugging cost.** Universally described as prohibitive; the
  gdb manual publishes no number, and the loudest citation is a competitor.

---

## 2. Omniscient and query-based debugging

This is the section that matters most for an agent. An agent does not get tired
of asking. A stepping interface forces it to spend a round trip per step; an
index answers a question about the whole execution in one.

### 2.1 Pernosco: the execution as a database

> "collect all program states into a database indexed for efficient queries
> (e.g. containing every memory and register write)"
> — <https://pernos.co/about/vision/>, read 2026-09-18

> "Precomputes all program states so shifting time is instantaneous"

> "Query for executions of specific functions and lines (via unified
> search-oriented interface) and get bulk results instantly"
> — <https://pernos.co/about/overview/>, read 2026-09-18

The dataflow view is the "where did this value come from" primitive, stated as
a product feature:

> "Pernosco can trace dataflow backwards in time, from where a variable has an
> incorrect value back to where that variable was set — instantly."

> "When the value set was simply copied from some other memory or register
> location, Pernosco displays the copy step and then automatically continues
> the explanation by following the source of the copy further backward in
> time."

> "Because Pernosco is aware of all program state across all recorded
> processes, it can even track data backwards through system constructs like
> pipes and sockets."
> — <https://pernos.co/about/dataflow/>, read 2026-09-18

Symbol search is cheap for the same structural reason:

> "Because we have indexed debuginfo offline, we can find all symbols
> containing a given substring, and show results for each symbol, with very low
> latency."
> — <https://pernos.co/about/searchbox/>, read 2026-09-18

**Cost.** Pernosco states the barrier and gives one bound, and no numbers:

> "The obvious barrier to omniscient debugging is scalability: building and
> storing that database is very expensive." ... "We have made tremendous
> technical improvements over previous implementations of omniscient debugging,
> and can demonstrate cost-effective debugging of complex applications with
> recorded execution times of many minutes (though not yet hours)."
> — <https://pernos.co/about/vision/>, read 2026-09-18

No indexing wall-clock time, core count, storage figure or price appears on
the overview, workflow-ci or FAQ pages; each was fetched and each lacks them.
That gap is itself a finding: the one commercial system that does exactly what
this report is about publishes no cost model.

Scope is stated:

> "x86-64 Linux, and statically compiled languages producing DWARF debugging
> information including C, C++, Ada and Rust. Additionally, some support is
> available for JavaScript running on certain version of the V8 engine."

> "Your program must be capable of running under rr to use Pernosco"
> — <https://pernos.co/faq/>, read 2026-09-18

That second sentence is the constraint that decides whether any of this is
available to a new language: produce DWARF, run under rr.

### 2.2 The older omniscient debuggers, and the cost they hit

**ODB** (Bil Lewis, "Debugging Backwards in Time", AADEBUG 2003,
arXiv:cs/0310016, read 2026-09-18 from <https://arxiv.org/pdf/cs/0310016>)
recorded every assignment:

> "The ODB keeps a single array of time stamps. Each time stamp is a 32-bit int
> containing a thread index (8 bits), a source line index (20 bits), and a type
> index (4 bits)."

> "Every variable has a HistoryList object associated with it which is just a
> list of time stamp/value pairs. When the ODB wants to know what the value of
> a variable was at time 102, it just grabs the value at the closest previous
> time."

Measured overhead, spanning two orders of magnitude depending on what the loop
does:

> "for (int i=0; i<MAX; i++) sum+=smallArray[i];    300x
> for (int i=0; i<MAX; i++) x=x*x+x;                100x
> for (int i=0; i<MAX; i++) sum+=bigArray[i];        30x
> for (int i=0; i<MAX; i++) s=\"Item\"+i;              2x"

And the capacity arithmetic, which is the whole design problem in two
sentences:

> "It requires roughly 10µs to record the method call and another 1µs per each
> assignment and marker event, for a total of 10 events in 19µs, and average of
> 2µs/event."

> "Performance is not an issue for bugs which generate less than 10 million
> events. At a rate of 2µs/event, it takes only 20 seconds to fill the entire
> 2GB address space."

**TOD** (Pothier, Tanter, Piquer, "Scalable Omniscient Debugging", OOPSLA 2007)
answered with a distributed trace database. The paper was unreachable during
the main research pass; it was retrieved on 2026-09-19 from
<https://pleiad.cl/papers/2007/pothierAl-oopsla2007.pdf> and extracted with
`pdftotext -layout`. All quotations below are from that text.

> "Specialized distributed database engine for scalable and fast storing and
> querying of events, which leverages the highly-constrained nature of
> execution traces. On a dedicated 10-node cluster TOD handles a sustained
> input rate of approx. 470kEv/s (thousands events per second), and hundreds
> of queries per second."

The worst-case emission benchmark (Table 4), a CPU-bound program in which every
step emits an event, on a "2GHz notebook":

| Setup | JVM heap (MB) | Time (s) | Events emitted | Events recorded | Rate (kEv/s) | Overhead |
| --- | --- | --- | --- | --- | --- | --- |
| None | 16 | 1.53 | — | — | — | 1 |
| ODB1 | 500 | 179 | 110m | 5m | 614 | 116 |
| ODB2 | 64 | 188 | 110m | 530k | 585 | 122 |
| TOD | 16 | 173 | 90m | 90m | 520 | 113 |

Two things in that table matter more than the headline. TOD is 113x slower than
the baseline — the "factor of 100 or more" figure Lienhard et al. cite is the
paper's own number, not a critic's. And TOD records every event it emits (90m
of 90m) while ODB, at eight times the heap, retains 5 million of 110 million.
The 113x buys completeness; ODB's 116x buys a 4.5% sample.

The realistic case is the Eclipse session:

> "the recorded execution trace comprises around 720 million events and weighs
> in at 33GB. The average event emission rate is 313kEv/s, 40% less than the
> worst-case scenario presented above."

33 GB for one interactive Eclipse session, with the JDK classes excluded from
instrumentation. The qualitative cost is stated plainly:

> "The start-up time of Eclipse is greatly augmented when trace capture is
> enabled, due to the loading of instrumented classes (which are roughly 3
> times bigger than non-instrumented classes)."

> "Although using TOD implies a perceptible slowdown [of] the debugged program,
> we believe that the benefits of [omnis]cient debugging in quickly pinpointing
> hard-to-find [bugs] far outweigh this inconvenience."

That is the most complete published cost model for omniscient debugging found
in this research: 113x, 33 GB per session, and a ten-machine cluster to keep up
with one debugged program.

**Lienhard, Gîrba and Nierstrasz** (ECOOP 2008,
<https://scg.unibe.ch/archive/papers/Lien08bBackInTimeDebugging.pdf>, read
2026-09-18) wrote the rebuttal, and give an independent number for the earlier
systems:

> "Back-in-time debuggers are extremely useful tools for identifying the causes
> of bugs. Unfortunately the 'omniscient' approaches that try to remember all
> previous states are impractical because they consume too much space or they
> are far too slow."

> "Current implementations such as ODB [3], TOD [4] or Unstuck [5] can incur a
> slowdown of factor 100 or more for non-trivial programs."

That is not a hostile estimate: TOD's own Table 4 above reports 113x and ODB's
reports 116x, so the two sides agree on the measurement and disagree only about
whether it is acceptable.

Their own approach — keep history in the same heap so the garbage collector
prunes it — measures far cheaper:

> "the execution overhead of the modified VM averaged 15% when recording is
> disabled and the average slowdown when recording is turned on is 3.84"

That is the real trade: 3.84x for history that the collector is allowed to
forget, versus 100x for history that is not.

**Whyline** (Ko & Myers, ICSE 2008,
<https://faculty.washington.edu/ajko/papers/Ko2008JavaWhyline.pdf>, read
2026-09-18) started from the questions rather than the recording. Its taxonomy
is the closest thing in the literature to a debugging API for an agent:

> "GRAPHICAL OUTPUT MENU / PROPERTIES / why did property = value ? / FIELDS
> AFFECTING OUTPUT / [FIELD MENUS] / OBJECTS INVOKING OUTPUT / [OBJECT MENUS]
> FIELD MENU / why did field = value ? / why didn't field's value change after
> time T ? / [if value is object, include OBJECT MENU]
> OBJECT MENU / why did object get created ? / FIELDS AFFECTING OUTPUT / OUTPUT
> INVOKING METHODS / why didn't method execute after time T ?
> OUTPUT-INVOKING CLASSES MENU / why didn't an instance of class C appear?"

> "Why did questions refer to a specific event from a trace" ... "Why didn't
> questions refer to one or more instructions in the code."

MEASURED user study:

> "Overall, the participants with the Whyline completed the task in a median of
> 4 minutes, ranging from 1 to 12, significantly faster than the control group,
> which had a median of 10 minutes, ranging from 3 to 38 (p < .05, Wilcoxon
> rank sums test)."

And the finding that motivates giving a machine this interface:

> "developers' initial guesses were wrong almost 90% of the time"

Scale at which it stayed interactive:

> "The largest trace we have tested is on ArgoUML ... and includes 35,597 I/O
> events over a minute of user interaction. The history is navigable at
> interactive speeds"

**Chronon** appears discontinued: chrononsystems.com fetched on 2026-09-18
contains no mention of the debugger product, only Java training courses. No
dated statement of discontinuation was found. INFERENCE, not a verified fact.

### 2.3 What a query interface actually looks like

Three shipped examples, in decreasing generality.

**WinDbg TTD** exposes the trace as a LINQ-queryable object model. This is the
most concrete "ask the execution a question" surface that exists in a shipping
tool:

> "Calls [Returns call information from the trace for the specified set of
> methods: TTD.Calls("module!method1", "module!method2", ...)]
> Memory [Returns memory access information for specified address range:
> TTD.Memory(startAddress, endAddress [, "rwec"])]"
> — <https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/time-travel-debugging-object-model>,
> read 2026-09-18

"Who wrote this memory, and take me there" is one line:

> "dx @$cursession.TTD.Memory(&@$teb->LastErrorValue, &@$teb->LastErrorValue +
> 0x4, \"r\").Where(m => m.TimeStart < @$dialog).OrderBy(m =>
> m.TimeStart).Last().TimeEnd.SeekTo()"
> — same URL, read 2026-09-18

"Group every call to this function by its return value and count them" is
another:

> "dx -g @$cursession.TTD.Calls(\"kernelbase!GetLastError\").Where( x=>
> x.ReturnValue != 0).GroupBy(x => x.ReturnValue).Select(x => new { ErrorNumber
> = x.First().ReturnValue, ErrorCount = x.Count()}).OrderByDescending(p =>
> p.ErrorCount)"
> — same URL, read 2026-09-18

Microsoft is honest that the index does not make it free:

> "Calls() [... Note that this is a function that does computation, so it takes
> a while to run.]"
> — same URL, read 2026-09-18

**Replay.io's protocol** has the batched-evaluation primitive an agent wants —
run this expression at every hit of this breakpoint across the whole recording:

> "Evaluating a user-provided expression everywhere the breakpoint is hit is
> done with a few Analysis requests: Analysis.createAnalysis specifies an
> analysis that can run when the program is paused somewhere,
> Analysis.addLocation indicates that the analysis should run everywhere a
> specific breakpoint is hit, and Analysis.runAnalysis starts the analysis and
> returns the results of performing it at all the hits for that breakpoint."

> "the results of those evaluations within a second or two"
> — <https://www.replay.io/blog/inspecting-runtimes>, read 2026-09-18

**Perfetto's trace processor** is the counter-example: real SQL, real
production scale, over traces that are not complete.

> "Trace Processor is a C++ library that ingests traces in a variety of formats
> and exposes an SQL interface for querying them through a consistent set of
> tables."
> — <https://perfetto.dev/docs/analysis/trace-processor>, read 2026-09-18

> "Traces cannot feasibly capture execution of extreme high frequency events
> e.g. every function call."
> — <https://perfetto.dev/docs/tracing-101>, read 2026-09-18

Perfetto answers questions about what was instrumented. It has no memory-write
log and no dataflow primitive, so none of the three canonical questions below
is answerable in general.

**PQL** (Martin, Livshits, Lam, OOPSLA 2005) is the academic precedent for a
query language over program events:

> "a language for expressing patterns of events on objects. It provides a
> frontend to static and dynamic program analyses to go find those sequences on
> the program as it runs."
> — <https://pql.sourceforge.net/>, read 2026-09-18

Its own project page says "full documentation is not yet available". The OOPSLA
paper is paywalled; no query syntax is quoted here.

### 2.4 The three questions, answered by system

| Question | Pernosco | TTD | Whyline | ODB | Perfetto | rr alone |
| --- | --- | --- | --- | --- | --- | --- |
| Where did this value come from? | First-class (`dataflow`), stated instant | `TTD.Memory(...)`, "takes a while to run" | First-class ("why did X = v?") | Per-variable `HistoryList` | No | Manual reverse-stepping |
| Who wrote this memory? | Same dataflow view | One-line query, quoted above | Not framed that way | In principle, not first-class | No | Reverse watchpoint |
| Why did this branch go that way / why did this not run? | Control-flow visualization; no "why not" primitive documented | No "why not" primitive | First-class, a whole menu half | No | No | No |

Whyline is the only system in the table with a first-class "why didn't"
answer, and it is a 2008 research prototype for Java. That is the largest
unfilled gap between what an agent would want and what exists.

---

## 3. Checkpoint and restore of full state

### 3.1 CRIU

CRIU's own limitations page is the useful document, because it enumerates
precisely the state that cannot be captured:

> "CRIU allows to dump the set of processes and their resources if this set has
> no connections outside"

> "If a task has opened or mapped any character or block device, this typically
> means, it wants some connection to the hardware. In this case dump (and
> restore) is impossible."

> "CRIU doesn't dump tasks with held locks."

> "CRIU uses the same API as debuggers do...Thus tasks under gdb or strace
> cannot be dumped."

> "Dumping + restoring an application connected to a 'real' Xserver...is
> impossible now."
> — all: <https://criu.org/What_cannot_be_checkpointed>, read 2026-09-18

That fourth quotation is a direct obstacle to the thing this report is about:
you cannot checkpoint a process that a debugger is already attached to.

Measured cost, for one 11-task container:

> "Total time ~3.5 seconds" ... "Frozen time ~3.0 seconds" ... "Restore time
> ~1.9 seconds"
> — <https://criu.org/Performance_research>, read 2026-09-18

Restore is dominated by remapping, not by I/O:

> "Reading images 1%" / "Mapping huge premap area << 1%" / "(Re-)mapping
> sub-areas 73%" / "Filling area with data 26%"
> — same URL, read 2026-09-18

No image-size figure was found on any fetched CRIU page. Nothing on any fetched
page addresses restoring the same image many times.

### 3.2 Hypervisor snapshots

QEMU saves "the complete virtual machine including CPU state, RAM, device state
and the content of all the writable disks"
(<https://www.qemu.org/docs/master/system/images.html>, read 2026-09-18), and
warns that some drivers, "in particular USB", do not restore correctly.

Firecracker is the system that states the branching hazard outright, and it is
the single most useful sentence in this section:

> "State other than the guest kernel entropy pool, such as unique identifiers,
> cached random numbers, cryptographic tokens, etc **will** still be replicated
> across multiple microVMs resumed from the same snapshot."
> — <https://github.com/firecracker-microvm/firecracker/blob/main/docs/snapshotting/snapshot-support.md>,
> read 2026-09-18

Resuming many times from one snapshot works. It also duplicates every secret
and every random number the snapshot contained. For a debugger that is an
advantage — determinism is what you wanted. For anything else it is a
vulnerability, and it is the reason "just snapshot the world" is not a general
answer.

No restore-latency or snapshot-size numbers are published on that page; it
states only that "performance depends on the memory size, vCPU count and
emulated devices count".

### 3.3 Language-level images and continuations

**Smalltalk** persists the heap, execution state included:

> "The image, when stored to a file, is saved with a header section followed by
> a binary snapshot of the contents of the object memory."

> "the header section provides enough information for the VM to reload the
> snapshot, fixing up object pointer addresses and other details within the
> object memory as it is loaded, and preparing the VM to begin running the
> image at the point it was last saved"
> — <https://wiki.squeak.org/squeak/2213>, read 2026-09-18

**SBCL** shows what a language runtime loses at the OS boundary:

> "Everything related to open streams is necessarily changed, since the OS
> won't let us preserve a stream across save and load."

> On multi-threaded platforms, "only a single thread may remain running after
> `sb-ext:*save-hooks*` have run."

> "There is absolutely no binary compatibility of core images between different
> runtime support programs."
> — <https://www.sbcl.org/manual/#Saving-a-Core-Image>, read 2026-09-18

**Erlang is not a checkpoint system** and should not be cited as one. Its
supervisors restart children to their configured initial spec:

> "A supervisor is responsible for starting, stopping, and monitoring its child
> processes. The basic idea of a supervisor is that it is to keep its child
> processes alive by restarting them when necessary."
> — <https://www.erlang.org/doc/system/sup_princ.html>, read 2026-09-18

What Erlang actually contributes to this report is live introspection of any
process without stopping it — `sys:get_state/1,2` returns "the state of the
callback module" for a `gen_server`, "the tuple `{CurrentState,CurrentData}`"
for a `gen_statem` (<https://www.erlang.org/doc/man/sys.html>, read
2026-09-18), and `erlang:trace/3` turns "trace flags on processes or ports"
with flags including `call`, `return_to`, `send`, `receive`, `procs`,
`garbage_collection`
(<https://www.erlang.org/doc/apps/erts/erlang.html#trace/3>, read 2026-09-18).
That is a different and cheaper capability than replay: total observability of
a running system, with no recording at all.

**Continuations** as a checkpoint mechanism have exactly one worked precedent,
and it is a 1993 research debugger:

> "We have built a portable, instrumentation-based, replay debugger for the
> Standard ML of New Jersey compiler. ... The debugger also provides reverse
> execution, both as a user feature and an internal mechanism. Reverse
> execution is implemented using a checkpoint and replay system; checkpoints
> are represented primarily by first-class continuations."

> "SML/NJ supports efficient first-class continuations, which provide a cheap
> and elegant mechanism for checkpointing immutable variables and control
> state. Since most ML programs have few side-effects, and mutable variables
> are distinguished statically, a checkpoint in a typical computation can be
> described by a continuation plus a small amount of additional information
> describing the values of mutable variables."
> — Tolmach & Appel, "A Debugger for Standard ML", JFP 1(1), 1993,
> <https://www.cs.princeton.edu/~appel/papers/debugger.pdf>, read 2026-09-18

Read that second quotation as a language-design claim, not a debugger claim:
checkpointing is cheap in proportion to how little mutable state the language
lets you have. No production system using `call/cc` this way was found.

### 3.4 Fork-based checkpointing in fuzzers

This is the cheap, deployed answer to "resume from this point, many times".

> "thanks to the powers of copy-on-write, the clone is created very quickly yet
> enjoys a robust level of isolation from its older twin"

> "the stop-at-main() logic, already shipping with afl 0.36b, can speed up the
> fuzzing of many common image libraries by a factor of two or more"
> — <https://lcamtuf.blogspot.com/2014/10/fuzzing-binaries-without-execve.html>,
> read 2026-09-18

AFL++'s persistent mode goes further:

> "In persistent mode, AFL++ fuzzes a target multiple times in a single forked
> process, instead of forking a new process for each fuzz execution."

> "the speed can easily be x10 or x20 times faster without any disadvantages"

> "All professional fuzzing uses this mode"
> — <https://github.com/AFLplusplus/AFLplusplus/blob/stable/instrumentation/README.persistent_mode.md>,
> read 2026-09-18

And the snapshot LKM measures the remaining gain over `fork()` itself:

| project | program | exec/s with snapshot | exec/s normal | factor |
| --- | --- | --- | --- | --- |
| afl++ | test-instr | 25k | 8234 | x3 |
| unrar | unrar | 7044 | 1938 | x3.6 |
| jpeg | djpeg | 1911 | 1502 | x1.3 |
| tiff | thumbnail | 5058 | 3114 | x1.6 |
| libxml | xmllint | 7835 | 3450 | x2.3 |

> "fork() is slow and we want to fuzz faster. The speed gain currently varies
> between 20-360% depending on the target."
> — <https://github.com/AFLplusplus/AFL-Snapshot-LKM>, read 2026-09-18

The maintainers also say it is unmaintained: "Due to syscall hooking and the
never ending changes in the kernel we are unable to maintain it".

### 3.5 What "resume from any point with one variable changed" actually requires

Three layers, from the sources above: address space and registers (CRIU's
memory dump, QEMU's "CPU state, RAM, device state", the LKM's
`AFL_SNAPSHOT_REGS`); file descriptors and kernel objects (CRIU's open-file
dump, `AFL_SNAPSHOT_FDS` — and CRIU's outright refusal for character devices);
and the external world, which nobody solves, which is why Firecracker's docs
warn about duplicated crypto tokens.

The fourth requirement is the one that is usually missed, and it is decisive:
if you change a variable, you are no longer replaying. rr states this
directly:

> "When you call a program function from the debugger, rr temporarily clones
> the current program state, runs your function in the clone (echoing console
> output), and then throws away the clone so replay can continue from the state
> before running the function."

> "Therefore attempting to alter program state persistently by calling
> functions will not work."
> — <https://github.com/rr-debugger/rr/wiki/Usage>, read 2026-09-18

INFERENCE, from combining that with the rr design in §1.1: a recording is a
fixed sequence of syscall results and scheduling decisions. A modified program
may make different syscalls in a different order, so the recorded tape no
longer describes its future. "Replay with a change" is a contradiction; what is
actually wanted is *re-execution from a checkpoint*, which is the fork server,
gdb's `checkpoint`/`restart`, or a fresh recording.

gdb's `checkpoint` is the standard-issue version:

> "checkpoint: Save a snapshot of the debugged program's current execution
> state." ... "restart checkpoint-id: Restore the program state that was saved
> as checkpoint number checkpoint-id."

> "Characters that have been sent to a printer (or other external device)
> cannot be 'snatched back'"

> "each checkpoint will have a unique process id (or pid)" ... "If your program
> has saved a local copy of its process id, this could potentially pose a
> problem"

> "Currently, only GNU/Linux."
> — <https://sourceware.org/gdb/current/onlinedocs/gdb.html/Checkpoint_002fRestart.html>,
> read 2026-09-18

An agent that wants "stop here, change x, see what happens, then undo that and
try y" is asking for gdb `checkpoint` plus a deterministic program, not for a
record-replay debugger.

---

## 4. The protocols an agent would drive

The short answer: several of these were designed for programs, and the two
designed most explicitly for programs (GDB/MI, JDWP) are also the two with the
least fashionable tooling.

### 4.1 Debug Adapter Protocol

DAP's own reason for existing is tool decoupling:

> "It takes a significant effort to implement the UI for a new debugger" and
> "this work must be repeated for each development tool."
> — <https://microsoft.github.io/debug-adapter-protocol/overview>, read
> 2026-09-18

The spec has everything an agent needs, on paper. All quotations from
<https://microsoft.github.io/debug-adapter-protocol/specification>, read
2026-09-18:

- `evaluate`: "Evaluates the given expression in the context of a stack frame.
  The expression has access to any variables and arguments that are in scope."
- `setVariable`: "Set the variable with the given name in the variable
  container to a new value."
- `setExpression`: "Evaluates the given `value` expression and assigns it to
  the `expression` which must be a modifiable l-value."
- `dataBreakpointInfo` / `setDataBreakpoints`: "Obtains information on a
  possible data breakpoint that could be set on an expression or variable."
- `granularity`: "Stepping granularity. If no granularity is specified, a
  granularity of `statement` is assumed." — `statement`, `line`, `instruction`.
- `readMemory` / `writeMemory` / `disassemble`.
- `stepBack`: "The request executes one backward step (in the given
  granularity) for the specified thread and allows all other threads to run
  backward freely by resuming them."
- `reverseContinue`: "The request resumes backward execution of all threads."

Both reverse operations are gated: clients should only call them "if the
corresponding capability `supportsStepBack` is true". How many adapters set it
could not be established from a primary registry; search indicates it is
implemented essentially only where the underlying debugger already has reverse
execution (LLDB under rr). **Reported as sparse, not quantified.**

### 4.2 GDB/MI

The manual's self-description settles the "usable by a program" question:

> "GDB/MI is a line based machine oriented text interface to GDB and is
> activated by specifying using the --interpreter command line option."

> "It is specifically intended to support the development of systems which use
> the debugger as just one small component of a larger system."

> "GDB/MI is still under construction, so some of the features described below
> are incomplete and subject to change."
> — <https://sourceware.org/gdb/current/onlinedocs/gdb.html/GDB_002fMI.html>,
> read 2026-09-18

Variables:

> "Display the names of local variables and function arguments for the selected
> frame. If print-values is 0 or `--no-values`, print only the names of the
> variables; if it is 1 or `--all-values`, print also their values; and if it
> is 2 or `--simple-values`, print the name, type and value for simple data
> types, and the name and type for arrays, structures and unions."
> — `-stack-list-variables`, GDB/MI Stack Manipulation, read 2026-09-18

Variable objects are the incremental-update mechanism, which matters for an
agent polling state:

> "MI provides an update command that lists all variable objects whose values
> has changed since the last update operation. This considerably reduces the
> amount of data that must be transferred to the frontend."
> — GDB/MI Variable Objects, read 2026-09-18

Reverse execution is present in MI as a flag on the ordinary commands:
`-exec-continue --reverse`, `-exec-next --reverse`, `-exec-step --reverse`,
`-exec-next-instruction --reverse`, `-exec-step-instruction --reverse`,
`-exec-finish --reverse` (GDB/MI Program Execution, read 2026-09-18).

GDB/MI is the most complete machine interface in this report: scope
variables, expression evaluation, incremental change notification, instruction
and line granularity, and reverse execution, all in one wire format that the
manual says is for programs.

### 4.3 LLDB

The Python SB API is the intended programmatic surface
(<https://lldb.llvm.org/python_api.html>, read 2026-09-18). The MI clone is
gone:

> "lldb-mi has been moved out of the LLDB source tree into its own GitHub
> repository here: https://github.com/lldb-tools/lldb-mi"

> "LLDB no longer provides the lldb-mi executable."
> — <https://lists.llvm.org/pipermail/lldb-dev/2019-August/015357.html>,
> read 2026-09-18

Its replacement is DAP:

> "lldb-dap brings the power of lldb to any editor or IDE that supports the
> Debug Adapter Protocol (DAP)."
> — <https://lldb.llvm.org/use/lldbdap.html>, read 2026-09-18

### 4.4 gdbserver and the remote serial protocol

The floor of the stack. Packet format:

> "A packet is introduced with the character '$', the actual packet-data, and
> the terminating character '#' followed by a two-digit checksum."

> "At a minimum, a stub is required to support the '?' command to tell GDB the
> reason for halting, 'g' and 'G' commands for register access, and the 'm' and
> 'M' commands for memory access."
> — <https://sourceware.org/gdb/current/onlinedocs/gdb.html/Overview.html>,
> read 2026-09-18

Four commands and you have a debuggable target. No variables, no types, no
expressions — GDB supplies all of that from DWARF on its side. INFERENCE: this
is why RSP is the lowest common denominator; the protocol carries bytes, the
debug information carries meaning.

### 4.5 ptrace

> ptrace provides "a means by which one process (the 'tracer') may observe and
> control the execution of another process (the 'tracee'), and examine and
> change the tracee's memory and registers."
> — <https://man7.org/linux/man-pages/man2/ptrace.2.html>, read 2026-09-18

`PTRACE_PEEKTEXT`/`PEEKDATA` read a word; `POKETEXT`/`POKEDATA` write one;
`PEEKUSER`/`POKEUSER` reach the register area, and hardware watchpoints are set
by poking the debug registers. There is no request in the list for a symbol or
a type. INFERENCE from that absence: ptrace gives an agent bytes at addresses,
and everything else is DWARF's job.

### 4.6 JDWP and JVMTI

JDWP is the best-specified wire protocol of the set:

> "The Java Debug Wire Protocol (JDWP) is the protocol used for communication
> between a debugger and the Java virtual machine (VM) which it debugs."

> "The JDWP differs from many protocol specifications in that it only details
> format and layout, not transport."

> "The JDWP is designed to facilitate efficient use by the JDI; many of its
> abilities are tailored to that end."
> — <https://docs.oracle.com/javase/8/docs/technotes/guides/jpda/jdwp-spec.html>,
> read 2026-09-18

JVMTI sits underneath, in-process:

> "It provides both a way to inspect the state and to control the execution of
> applications running in the Java TM virtual machine (VM)."

> Agents run "in the same process with and communicate directly with the
> virtual machine ... This native in-process interface allows maximal control
> with minimal intrusion on the part of a tool."
> — <https://docs.oracle.com/javase/8/docs/platform/jvmti/jvmti.html>, read
> 2026-09-18

### 4.7 Chrome DevTools Protocol

Fetched from the protocol JSON, because the documentation site is a
client-rendered shell that returns no body text
(<https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/json/js_protocol.json>,
read 2026-09-18):

- `Debugger.setBreakpoint`: "Sets JavaScript breakpoint at a given location."
- `setBreakpointByUrl`'s `condition`: "Expression to use as a breakpoint
  condition. When specified, debugger will only stop on the breakpoint if this
  expression evaluates to true."
- `Debugger.evaluateOnCallFrame`: "Evaluates expression on a given call frame."
- `Debugger.setVariableValue`: "Changes value of variable in a callframe.
  Object-based scopes are not supported and must be mutated manually."
- `stepOver` / `stepInto` / `stepOut` / `pause`.
- `Runtime.getProperties`: "Returns properties of a given object."
  (<https://pkg.go.dev/github.com/chromedp/cdproto/runtime>, read 2026-09-18)

No reverse-execution method was found in the Debugger domain.

### 4.8 eBPF, uprobes and USDT — observation without a debugger

> uprobes "are the user-space equivalent of kprobes"

> "arguments are available via the argN builtins and can only be accessed with
> a uprobe"

> "If the traced binary has DWARF included, function arguments are available in
> the args struct."
> — <https://raw.githubusercontent.com/bpftrace/bpftrace/master/docs/language.md>,
> read 2026-09-18

The limitation is the same one as ptrace, stated by the kernel:

> "uprobe event interface expects the user to calculate the offset of the
> probepoint in the object"
> — <https://docs.kernel.org/trace/uprobetracer.html>, read 2026-09-18

Without DWARF or BTF you name registers and byte offsets. With them you name
variables. That is the whole reason report 01's subject is a prerequisite for
this one. No overhead figures appear on the kernel or bpftrace pages fetched.

### 4.9 Comparison

| Protocol | Scope variables | Expression eval | Conditional bp | Data bp | Step granularity | Reverse | Machine-drivable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DAP | `variables` / `variablesReference` | `evaluate` | yes | `setDataBreakpoints`, gated | statement / line / instruction | `stepBack`, gated, rarely implemented | Yes, by design |
| GDB/MI | `-stack-list-variables`, variable objects | `-data-evaluate-expression` | yes | not confirmed in fetched pages | line and instruction | `--reverse` on every exec command | Yes, stated in the manual |
| LLDB SB API | `SBFrame` / `SBValue` | yes | yes | not confirmed | yes | via rr | Yes, a scripting API |
| gdbserver / RSP | none at the wire level | none | none | none | none | depends on the stub | Yes, by construction |
| ptrace | none | none | none | debug registers | instruction | none | Yes — it is a syscall |
| JDWP | via JDI's object model | yes | yes | not confirmed | not itemized | none found | Yes, explicitly |
| CDP | `Runtime.getProperties` | `evaluateOnCallFrame` | yes, `condition` | not found | over / into / out | none found | Yes, JSON over WebSocket |
| uprobes / bpftrace | only with DWARF or BTF | script expressions | predicates | n/a — arbitrary probes | probe points | none | Yes |

Cells marked "not confirmed" reflect what was fetched, not a claim that the
capability is absent.

---

## 5. Agents doing this today

The honest summary: one benchmark measures an LLM agent with a debugger against
the same agent without one, and it finds the debugger helps strong models and
hurts weak ones. Everything else in this section is either older automated
debugging (fault localization, repair, test generation) with decades of
measured results, or a demo.

### 5.1 debug-gym — the one controlled comparison

Microsoft Research's debug-gym (arXiv:2503.21557) gives an agent a Python
program in a container and five tools — `eval`, `view`, `pdb`, `rewrite`,
`listdir`.

> "This tool is a wrapper that acts as a direct interface between the agent and
> the full suite of pdb commands available to the original Python debugger,
> such as b(reak), cl(ear), s(tep), n(ext), c(ontinue), and p(rint)."
> — <https://arxiv.org/pdf/2503.21557> p.8, read 2026-09-18

Three agents are compared: `rewrite` (no debugger), `debug` (pdb from the
start), `debug(5)` (pdb unlocked after the fifth failed rewrite). Three runs
each. SWE-bench Lite, 300 tasks, % success (Table 3):

| Backbone | rewrite | debug | debug(5) |
| --- | --- | --- | --- |
| GPT-4o | 19.1±2.4 | 17.2±0.8 | 23.6±1.0 |
| GPT-4o-mini | 4.0±0.7 | 3.5±0.7 | 6.2±0.1 |
| o1-preview | 10.7±0.7 | 30.2±1.0 | 30.8±0.9 |
| o3-mini | 8.5±1.0 | 22.1±0.9 | 19.8±1.1 |
| Claude 3.7 Sonnet | 37.2±2.1 | 48.4±1.6 | 52.1±1.6 |
| Llama-3.3-70B-Instruct | 2.4±0.5 | 4.0±1.0 | 4.8±0.4 |

> "The results suggest that for (relatively weaker) LLMs (GPT-4o, GPT-4o-mini,
> and lama-3.3-70B-Instruct), accessing the pdb tool at the beginning (i.e.,
> the debug agent) could to some extent harm the overall performance. In
> comparison, the debug agent with stronger LLMs (o1-preview, o3-mini, and
> Claude 3.7 Sonnet) can somehow benefit from the pdb tool and achieve a
> significantly higher success rate."
> — same source p.19, read 2026-09-18

On the easy benchmark the effect vanishes:

> "Comparing among the agents, Table 1 suggests that in the relatively simple
> (short) code generation task, the access to additional interactive debugging
> tool does not have clear effect to an agent's performance."
> — same source p.14, read 2026-09-18

The authors' own conclusion is not a success story:

> "Our experimental results show that our agents, despite being equipped with
> powerful tools that facilitate the codebase investigation used by human
> developers, are still far from being capable of using those tools in a
> meaningful way... the most performant agent-backbone model combination can
> barely solve about a half of the SWE-bench-Lite tasks."
> — same source p.22, read 2026-09-18

BENCHMARK, N=300 for the headline table. Two readings are defensible and the
paper supports both: a debugger triples o1-preview's score (10.7 → 30.2) and
adds 15 points to Claude 3.7 Sonnet; it also costs GPT-4o two points. The
capability being measured may not be "can it read state" so much as "does it
know when to stop guessing and look" — consistent with `debug(5)`, where the
tool is withheld until five rewrites have failed, being the best configuration
in five of the six rows. That reading is INFERENCE; the paper's own statement
(p.19, quoted above) attributes the split to model strength, not to timing.

### 5.2 SWE-agent — the interface, without a debugger

SWE-agent (arXiv:2405.15793) is the reference for agent-computer interface
design, and what it does not include matters here: a debugger. Its tools are a file viewer, an editor with lint feedback, and
search.

> "We perform an ablation study on a subset of 300 SWE-bench test instances
> (SWE-bench Lite) to analyze our ACI design choices. The results show that
> SWE-agent solves 10.7 percentage points more instances than the baseline
> agent, which uses only the default Linux shell."
> — <https://arxiv.org/pdf/2405.15793> p.2, read 2026-09-18

The paper reports 12.5% pass@1 on SWE-bench. Leaderboard numbers have moved
far past that since 2024; those later figures were not fetched and are not
quoted here.

### 5.3 Runtime state without a debugger: LDB

LDB (arXiv:2402.16906) splits a program into basic blocks and shows the LLM
intermediate variable values after each block — full state at coarse
granularity, no stepping.

> "LDB segments programs into basic blocks and tracks the values of
> intermediate variables after each block throughout the runtime execution...
> Experiments demonstrate that LDB consistently enhances the baseline
> performance by up to 9.8% across the HumanEval, MBPP, and TransCoder
> benchmarks"
> — <https://arxiv.org/pdf/2402.16906> p.1, read 2026-09-18

TransCoder with a GPT-3.5 backbone, by difficulty: easy 95.1% → 96.3%, medium
82.8% → 87.6%, hard 73.3% → 82.4%.

> "LDB shows the most improvement (9.1%) on the hard-level problems, which
> indicates that LDB is able to detect the non-trivial bugs and understand the
> complex execution flows in the harder problems."
> — same source p.7, read 2026-09-18

BENCHMARK, on single-function problems — materially easier than SWE-bench. The
pattern matches debug-gym's: state helps most where the problem is hard enough
that guessing fails.

For contrast, Chen et al.'s "Self-Debugging" (arXiv:2304.05128) never touches a
debugger. It re-reads execution output and error messages, reporting 2-3% on
Spider (9% on the hardest problems) and up to 12% on TransCoder and MBPP with
unit-test feedback.

### 5.4 What the benchmark itself is worth

> "The benchmark consists of 2,294 software engineering problems drawn from
> real GitHub issues and corresponding pull requests across 12 popular Python
> repositories."
> — <https://arxiv.org/abs/2310.06770>, read 2026-09-18

The sharpest published critique is a contamination argument:

> State-of-the-art models achieve "up to 76% accuracy in identifying buggy file
> paths using only issue descriptions" on SWE-Bench tasks, but only "up to 53%
> on tasks from repositories not included in SWE-Bench."

> "These disparities suggest that performance gains may stem from memorization
> of benchmark data rather than genuine problem-solving capabilities."
> — "The SWE-Bench Illusion", <https://arxiv.org/abs/2506.12286>, read
> 2026-09-18

Read every number in §5.1 and §5.2 with that in front of it.

### 5.5 Fault localization, and the result that should temper all of it

Spectrum-based fault localization (Tarantula, Ochiai) ranks statements by how
often they appear in failing versus passing runs. Parnin & Orso's ISSTA 2011
study, "Are Automated Debugging Techniques Actually Helping Programmers?", is
the standard counterweight. Five routes to the paper failed during the main
research pass; it was eventually retrieved from
<https://huang.isis.vanderbilt.edu/cs8395/paper/faultloc-not-help.pdf> and
extracted locally with `pdftotext -layout` (read 2026-09-19). All quotations
below are from that text.

The design: 34 developers across two experiments. The first, "run with 24
students split between groups" A and B, compared completion time on two tasks —
a rotation bug in Tetris and a parse exception in NanoXML (4,408 LOC) — with
and without a ranking-based Eclipse plugin. The second used "10 new
participants split into groups C and D" and manipulated the rank directly.

> "we found that the use of an automated tool helped more experienced
> developers find faults faster in the case of an easy debugging task, but the
> same developers received no benefit from the use of the tool on a harder
> task. We also found that most developers, when provided with a list of ranked
> statements, do not examine the statements in the order provided, but rather
> search through the list based on some intuition on the nature of the fault
> (which limits the usefulness of pure statement ranking)."

Measured navigation behaviour:

> "All participants exhibited some form of jumping between positions.
> Specifically, 37% of the visits jumped more than one position and, on
> average, each jump skipped 10 positions."

A second experiment with 10 more participants manipulated the rank directly —
the cleanest test of whether ranking is what matters:

> "for the NanoXML task group D was not any faster than group C despite the
> much lower rank of the faulty statement (16 versus 83). In fact, group D
> actually performed the NanoXML task slower than group C—15:12 for group C
> versus 18:30 for group D."

> "even when we changed the rank of the faulty statement in NanoXML from 83 to
> 16, there was no observed benefit. This is consistent with other research in
> search tasks, where it is clearly shown that most users do not inspect
> results beyond the first page"

The conclusion:

> "developers could use a ranking based tool to complete a task significantly
> faster than without the tool, but this effect was limited to more experienced
> developers and simpler code."

> "Even when using an artificially-high rank, we found that the ranking tool
> considered was no more effective than traditional debugging for our more
> challenging task."

This matters for an agent in a specific way. Every failure mode the paper found
is human: developers stop inspecting after a few entries, jump around the list
on intuition, and gain nothing from a better rank because they never got far
enough down to notice. An agent has none of those limits — it will inspect rank
200 without complaint. The paper's negative result is therefore not evidence
that ranked fault localization is useless to a machine. It is evidence that the
field measured the wrong thing for a decade, and that the metric it optimized
(absolute rank) may suit an automated consumer better than it ever suited a
human one. That is INFERENCE; no source found here tests it.

### 5.6 Delta debugging — the technique that transfers best to an agent

Zeller & Hildebrandt's ddmin (IEEE TSE 2002) has a stated guarantee and
measured costs, and it is a search an agent can run unattended.

> "Proposition 11 (ddmin minimizes): For any c ⊆ c✗, ddmin(c) is 1-minimal in
> the sense of definition 10."

> "Proposition 13 (ddmin complexity, best case): If there is only one
> failure-inducing change Δᵢ ∈ c✗, and all test cases that include Δᵢ cause a
> failure as well, then the number of tests t is limited by t ≤ 2 log₂(|c✗|)...
> Proposition 12 (ddmin complexity, worst case): ... ddmin(c✗) takes |c✗|² +
> 3|c✗| tests."
> — <https://www.st.cs.uni-saarland.de/papers/tse2002/tse2002.pdf> p.6, read
> 2026-09-18

Measured reductions:

> Mozilla: "After 57 tests, the ddmin algorithm minimizes the original 896
> lines to a 1-line input"

> "After 82 test runs (or 21 minutes), only 3 out of 95 user actions are left."

> "It takes 24 tests to minimize the fuzz input of 10⁶ characters to the single
> failure-inducing character"
> — same paper, pp.7-10, read 2026-09-18

Zeller's companion FSE 2002 work applies the same search to *program state*
rather than input — comparing memory graphs between a passing and a failing run
to isolate a cause-effect chain. That is precisely the technique a full-state
debugger would enable, and it is the one this research could not quote: the PDF
was fetched twice and its abstract could not be extracted either time. Gap.

Hierarchical delta debugging and C-Reduce are the practised descendants:

> "Our Hierarchical Delta Debugging algorithm produces simpler outputs and
> takes orders of magnitude fewer test cases than the original Delta Debugging
> algorithm."
> — <https://www.cs.purdue.edu/homes/xyzhang/fall07/Papers/hdd.pdf> p.1, read
> 2026-09-18

> "This reducer produces outputs that are, on average, more than 25 times
> smaller than those produced by our other reducers or by the existing reducer
> that is most commonly used by compiler developers."
> — <https://users.cs.utah.edu/~regehr/papers/pldi12-preprint.pdf> p.1, read
> 2026-09-18

### 5.7 Automated program repair, and the disagreement that defines it

GenProg's headline (ICSE 2012):

> "GenProg automatically repairs 55 of those 105 defects." "A successful repair
> completes in 96 minutes and costs $7.32, on average."
> — via <https://gpbib.pmacs.upenn.edu/gp-html/LeGoues_2012_ICSE.html>, read
> 2026-09-18 (citation-abstract page; the primary PDF did not render as text)

Qi, Long, Achour and Rinard re-ran the same patches three years later:

> "The overwhelming majority of the reported patches are not correct and are
> equivalent to a single modification that simply deletes functionality."

> "Our analysis indicates that only 5 of the 414 GenProg patches ... are
> correct. This leaves GenProg with correct patches for 2 of 105 defects..."

> "104 of the 110 plausible GenProg patches, 37 of the 44 plausible RSRepair
> patches, and 22 of the plausible 27 AE patches are equivalent to a single
> modification that deletes functionality."
> — <https://groups.csail.mit.edu/pac/patchgen/papers/kali-issta2015.pdf>
> pp.24-28, read 2026-09-18

55 versus 2, on the same 105-defect corpus. The two papers do not disagree
about the data; they disagree about the bar. "Plausible" means the test suite
passes. "Correct" means the bug is fixed. A generate-and-validate loop optimizes
whatever oracle it is given, and a test suite is a weak oracle.

That is the most important result in this section for anyone building agent
tooling, and it generalizes past repair: an agent that can run a test suite
thousands of times will find whatever the suite fails to forbid.

Modern LLM repair reports much better economics — ChatRepair
(arXiv:2304.00385) "fix[es] 162 out of 337 bugs for $0.42 each" — but the
benchmark composition behind the 337 was not confirmed, and the
plausible-versus-correct caveat above applies unless a paper re-validates
beyond its test suite.

### 5.8 Automatic test generation

EvoSuite on a real production codebase, from a study the tool's own authors
co-wrote:

> "we extracted 25 real faults from the version history of this software
> project, and applied two up-to-date unit test generation tools for Java,
> EvoSuite and Randoop... Automatically generated test suites detected up to
> 56.40% (EvoSuite) and 38.00% (Randoop) of these faults... classification of
> the undetected faults shows that 97.62% of them depend on either 'specific
> primitive values' (50.00%) or the construction of 'complex state
> configuration of objects' (47.62%)."
> — <https://www.evosuite.org/wp-content/papercite-data/pdf/icse17_experience.pdf>
> p.1, read 2026-09-18

The SF110 branch-coverage figure often quoted for EvoSuite (71%) came only from
search snippets here; the TOSEM 2014 paper was blocked. UNVERIFIED.

Pynguin, for a dynamically typed language, is blunter:

> "It is, however, substantially more difficult to automatically generate
> supportive tests for dynamically typed programming languages such as Python,
> due to the lack of type information and the dynamic nature of the language...
> our results demonstrate that dynamic typing nevertheless poses a fundamental
> issue for test generation"

> "For example, for the apimd project without type information the coverage is
> slightly above 20%, which is the coverage achieved just by importing the
> module"
> — <https://arxiv.org/pdf/2007.14049> pp.1,10, read 2026-09-18

BENCHMARK, 104 modules across 10 projects, 30 runs each. For a statically typed
language with explicit types — which A7 is — this is the favourable case, and
it is the reason type information is a test-generation asset and not only a
correctness one.

Fuzzing is the outlier in scale:

> "As of August 2023, OSS-Fuzz has helped identify and fix over 10,000
> vulnerabilities and 36,000 bugs across 1,000 projects."
> — <https://google.github.io/oss-fuzz/>, read 2026-09-18

### 5.9 Dynamic invariant detection — Daikon

Daikon infers likely invariants from observed executions. It is the closest
existing tool to "recover the properties this program maintains", which is what
an agent with full state would want to compute.

> "An alternative to expecting programmers to fully annotate code with
> invariants is to automatically infer likely invariants from the program
> itself."

> "These experiments demonstrate that, at least for small programs, invariant
> inference is both accurate and useful."
> — <https://www.cs.cmu.edu/~mernst/pubs/invariants-tse2001.pdf> p.1, read
> 2026-09-18

Note the hedge in the authors' own sentence. The cost model is stated:

> "The analysis demonstrates that inference running time is linearly correlated
> to the number of program points being traced, the square of the number of
> variables in scope at a program point, and the size of the test suite."
> — same paper p.2, read 2026-09-18

Quadratic in the number of variables in scope. That is the price of asking
"what is true of all of these at once", and it is the reason full-state
inference does not scale by simply having more state.

No numeric false-positive rate was found in the pages fetched. The structural
problem is the same as GenProg's: invariants are inferred from the test suite,
so a weak suite yields confident, wrong invariants.

### 5.10 What this section supports, and what it does not

Supported by measured results: delta debugging works and has a proof; test
generation finds roughly half of real faults and misses the rest for structural
reasons; repair systems optimize their oracle rather than correctness; a
debugger raises a strong model's SWE-bench Lite score substantially and lowers
a weak one's.

Not supported by anything found here: that record-and-replay, omniscient
debugging or query-over-execution has been shown to help an LLM agent. No paper
was found evaluating an agent against rr, Pernosco, TTD or any time-travel
debugger. debug-gym's `pdb` is the state of the published art, and `pdb` is a
forward-only stepper.

---

## 6. What the compiler must provide

Report 01 covers the debug-information formats. This section covers only the
four things record-replay and full-state inspection add on top: keeping values
observable, determinism, a mapping that survives two compilers, and the cost of
each.

### 6.1 Why `-O2` loses variables

Not because the format cannot express the value — because the value no longer
exists anywhere the format can point at. GCC's dedicated debugging level does
not claim otherwise:

> "-Og should be the optimization level of choice for the standard
> edit-compile-debug cycle, offering a reasonable blend of optimization, fast
> compilation and debugging experience especially for code with a high
> abstraction penalty."

> "-Og enables all -O1 optimization flags except for those known to greatly
> interfere with debugging"
> — <https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html>, read 2026-09-18

LLVM's policy is to be honestly incomplete rather than plausibly wrong:

> "LLVM debug information always provides information to accurately read the
> source-level state of the program, regardless of which LLVM optimizations
> have been run."

> a `#dbg_value` with operand `poison` "should be used, to terminate earlier
> variable locations and let the debugger present `optimized out`." ...
> "Withholding these potentially stale variable values from the developer
> diminishes the amount of available debug information, but increases the
> reliability of the remaining information."
> — <https://llvm.org/docs/SourceLevelDebugging.html>, read 2026-09-18

> "when there is no way to reconstitute the value of the lost instruction, this
> is the best possible outcome." [after `salvageDebugInfo` fails]
> — <https://llvm.org/docs/HowToUpdateDebugInfo.html>, read 2026-09-18

DWARF's partial rescue is `DW_OP_entry_value`, motivated exactly by this:

> "Many architectures pass arguments in registers and quite often the register
> in which an argument has been passed is quickly reused for something else. In
> that case all the debugger can say is that a value has been optimized out."
> — <https://dwarfstd.org/issues/100909.1.html>, read 2026-09-18

And the debug info that does survive is measurably buggy. Two papers looked:

> "Optimizing compilers emit debug information (e.g., DWARF information) to
> support source code debuggers. Wrong debug information causes debuggers to
> either crash or to display wrong variable values."

> "Our framework has led to 47 confirmed bug reports, 11 of which have already
> been fixed. Moreover, in three days, our technique has found 2 confirmed bugs
> in the Rust compiler."

> "many of our reported bugs are latent which affect at least three recent
> releases of both compilers."
> — Li, Zhang et al., "Debug Information Validation for Optimized Code",
> PLDI 2020, Georgia Institute of Technology,
> <https://faculty.cc.gatech.edu/~qrzhang/papers/pldi20_yuanbo1.pdf>, read
> 2026-09-19

That last sentence is the one to carry forward: these are not transient
regressions. Wrong debug information survived three releases of both GCC and
LLVM without anyone noticing, because nothing was checking.

> "Little attention has been devoted to checking that such information is
> correctly preserved by modern toolchains' optimization stages. This is
> particularly important as managing debug information in optimized production
> binaries is non-trivial, often leading to toolchain bugs that may hinder
> post-deployment debugging efforts."

> "We have used Debug² to find 23 bugs in the LLVM toolchain (clang/lldb), 8
> bugs in the GNU toolchain (GCC/gdb), and 3 in the Rust toolchain
> (rustc/lldb) -- with 14 bugs already fixed by the developers."
> — Di Luna, Italiano, Massarelli, Österlund, Giuffrida, Querzoni, "Who is
> Debugging the Debuggers? Exposing Debug Information Bugs in Optimized
> Binaries", ASPLOS 2021, <https://arxiv.org/abs/2011.13994>, read 2026-09-19

There is no trustworthy published figure for what fraction of locals go
missing at `-O2`. The closest primary source implies the number did not
cleanly exist:

> "current compilers often generate only partial debugging information in
> optimised programs... Current approaches for measuring the extent of coverage
> of local variables are based on crude assumptions... and are not comparable
> from one compilation to another."

> "it is currently not clear what it means for debug info to be fully complete
> and correct. Historically, a 'best effort' approach has prevailed... but
> placing no strong correctness criterion on compilers."
> — Stinnett & Kell, "Accurate Coverage Metrics for Compiler-Generated
> Debugging Information", CC 2024, arXiv:2402.04811, read 2026-09-18

Do not quote a percentage for this. There isn't one.

### 6.2 Keeping values alive, and what that costs

The strongest guarantee any production language documents is one line of
Swift's:

> "-Onone: This is meant for normal development. It performs minimal
> optimizations and preserves all debug info."
> — <https://github.com/apple/swift/blob/master/docs/OptimizationTips.rst>,
> read 2026-09-18

Compare `-Osize` on the same page: "Debug information will be emitted but will
be lossy."

LLVM has a per-function attribute aimed exactly at the middle ground:

> `optdebug` — "This attribute suggests that optimization passes and code
> generator passes should make choices that try to preserve debug info without
> significantly degrading runtime performance."
> — <https://llvm.org/docs/LangRef.html>, read 2026-09-18

Rust's profiles put the choice in the build system rather than the language:
`[profile.dev]` is `opt-level = 0, debug = true`, `[profile.release]` is
`opt-level = 3, debug = false`
(<https://doc.rust-lang.org/cargo/reference/profiles.html>, read 2026-09-18).

No language was found that offers a verified "nothing is ever elided" mode.
`-O0`, `-Og`, `optnone` and `optdebug` are minimal-optimization modes, not
guarantees. And the cost of choosing `-O0` could not be quantified from a
citable source: no peer-reviewed or vendor-published `-O0` versus `-O2` ratio
was obtained. **Gap, stated plainly.**

### 6.3 Determinism is a language decision

Record-replay works by pinning down nondeterminism. Some of it is the
operating system's (ASLR, disabled by `personality(ADDR_NO_RANDOMIZE)` or
`setarch -R`, both man7.org, read 2026-09-18). The rest the language chose.

Python randomizes hash seeds, and says why:

> "Hash randomization is intended to provide protection against a
> denial-of-service caused by carefully chosen inputs that exploit the worst
> case performance of a dict construction, O(n^2) complexity."
> — <https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED>, read
> 2026-09-18

`PYTHONHASHSEED=0` turns it off. Rust makes the same call:

> "By default, HashMap uses a hashing algorithm selected to provide resistance
> against HashDoS attacks. The algorithm is randomly seeded"
> — <https://doc.rust-lang.org/std/collections/struct.HashMap.html>, read
> 2026-09-18

Go injects nondeterminism as policy, with no opt-out in the spec:

> "The iteration order over maps is not specified and is not guaranteed to be
> the same from one iteration to the next."
> — <https://go.dev/ref/spec>, read 2026-09-18

Each of these was chosen for a good reason and each costs reproducibility. A
language that wants an agent to replay its programs has to decide, per
construct, whether the attacker-resistance or the reproducibility wins, and
give the other one a flag. No mainstream language guarantees a deterministic
heap layout at the specification level.

### 6.4 Surviving two compilers

Four precedents, and they point in different directions.

**Nim → C** gets it free, because the intermediate language already has the
construct and the debugger already understands it:

> "The --lineDir option can be turned on or off. If turned on the generated C
> code contains #line directives. This may be helpful for debugging with GDB."

> "--debugger:native use native debugger (gdb)"
> — <https://nim-lang.org/docs/nimc.html>, read 2026-09-18

**Cython → C** takes the other road: a sidecar artifact plus a debugger
extension.

> "Cython comes with an extension for the GNU Debugger that helps users debug
> Cython code."

> "The debugger will need debug information that the Cython compiler can
> export."
> — <https://cython.readthedocs.io>, read 2026-09-18

Cython emits the mapping out of band (`cython --gdb`) and ships `cygdb`, a gdb
Python extension that reconstructs Cython-level breakpoints, stepping and
variable printing (`cy break`, `cy step`, `cy print`). The format was confirmed
by reading `Cython/Debugger/DebugWriter.py`
(<https://raw.githubusercontent.com/cython/cython/master/Cython/Debugger/DebugWriter.py>,
read 2026-09-18): it is XML, written to a `cython_debug` directory
(`os.path.join(output_dir or os.curdir, 'cython_debug')`) as
`"cython_debug_info_" + self.module_name`, with a root element opened as
`self.start('cython_debug', attrs=dict(version='1.0'))`. A sibling file named
`interpreter` records the Python executable path.

This is the closest structural precedent for A7: a compiler that emits a
second language, writes a versioned sidecar next to the generated code, and
ships a debugger extension that reads it. Nothing about it requires the target
language to cooperate.

**Kotlin/Native** is the contrast: it never produces an intermediate
human-readable language at all.

> "The debug information is compatible with the DWARF 2 specification, so
> modern debugger tools, like LLDB and GDB can: Set breakpoints, Use stepping,
> Inspect variable and type information"
> — <https://kotlinlang.org/docs/native-debugging.html>, read 2026-09-18

**TypeScript → JS** shows what happens when mappings chain. Node warns about
the cost of consuming them:

> "When using a transpiler, such as TypeScript, stack traces thrown by an
> application reference the transpiled code, not the original source position.
> `--enable-source-maps` ... makes a best effort to report stack traces
> relative to the original source file."

> "enabling source maps can introduce latency to your application when
> `Error.stack` is accessed."
> — <https://nodejs.org/api/cli.html#--enable-source-maps>, read 2026-09-18

Note "best effort". Industry material describes the multi-stage failure — a
transpiler followed by a separate minifier, without explicit stitching, yields
a map pointing at the intermediate form rather than the original source — but
this came from a vendor engineering blog via search, not a spec, and is marked
as such.

Zig has no equivalent of any of this. The direct proposal —
<https://github.com/ziglang/zig/issues/1833>, "source maps", asking whether Zig
supported functionality "similar to the line control macros that you see in
GCC", for a literate-programming environment that relies on "these macros to
make debugging possible" — is **Closed as not planned**, with no substantive
discussion on the issue page (read 2026-09-18).
`std.builtin.SourceLocation`, what `@src()` returns, is call-site reflection,
not remapping:

```zig
pub const SourceLocation = struct {
    /// The name chosen when compiling. Not a file path.
    module: [:0]const u8,
    /// Relative to the root directory of its module.
    file: [:0]const u8,
    fn_name: [:0]const u8,
    line: u32,
    column: u32,
};
```
— <https://github.com/ziglang/zig/blob/master/lib/std/builtin.zig>, read
2026-09-18

Confirmed locally on Zig 0.16.0: `zig build-exe --help` lists `-fstrip` /
`-fno-strip`, `--compress-debug-sections`, `-fno-valgrind` and
`-fno-error-tracing` as its only debug-information options. There is no
`--debug-prefix-map`, no source-path remap, and no way to attribute generated
code to another file. `zig build-exe test.a7` fails with "error: unrecognized
file extension of parameter 'test.a7'", so the generated file's name in DWARF
will always end in `.zig`.

So a language that emits Zig has two of the four options above: Cython's
sidecar, or Kotlin/Native's bypass. Nim's route is closed.

---

## 7. The scale problem, stated honestly

A full value trace is enormous, and every practical system gives something up
to avoid storing one. Here is what each gives up, with numbers.

**Store everything.** Nirvana measures 0.51 bits per dynamic instruction
averaged over six applications, 11.89x average tracing overhead, and traces of
245 MB to 1.3 GB for runs of 10 to 44 seconds (Table 3, §1.3). TOD, doing the
same thing one level up at the bytecode, measures 113x and 33 GB for a single
interactive Eclipse session, and needs a ten-machine cluster to absorb the
event stream (Table 4, §2.2). The two are not directly comparable — different
hardware, workloads and instrumentation levels — but both work, and both are
why nobody records by default.

**Store only the nondeterminism, recompute the rest.** This is rr's answer and
it is the best deal in the report: under 2x on most workloads, 0.08-19 MB/s of
trace. What it gives up is random access — to answer any question you must
replay, and replay costs roughly what recording cost.

> "We identify a boundary around state and computation, record all sources of
> nondeterminism within the boundary and all inputs crossing into the boundary,
> and reexecute the computation within the boundary by replaying the
> nondeterminism and inputs."
> — arXiv:1705.05937 §2.1, read 2026-09-18

**Record control flow in hardware.** Cheap to collect, and it drops every
value:

> "A limitation of Intel PT is that it produces huge amounts of trace data
> (hundreds of megabytes per second per core) which takes a long time to
> decode, for example two or three orders of magnitude longer than it took to
> collect."
> — <https://raw.githubusercontent.com/torvalds/linux/master/tools/perf/Documentation/perf-intel-pt.txt>,
> read 2026-09-18

Note the number: *control flow alone* is hundreds of MB/s. And gdb's own
manual on the same mechanism: "This method does not record data ... Variables
and registers are not available during reverse execution" (§1.6).

**Sample.** Statistically valid for aggregates, useless for a point query.
Google-Wide Profiling reports "With negligible overhead, GWP provides stable,
accurate profiles and a datacenter-scale tool for traditional performance
analyses", with a cited sampling overhead "approximately 0.3 percent"
(<https://research.google.com/pubs/archive/36575.pdf>, read 2026-09-18,
MEASURED). What it gives up is exactly the question this report asks: a
sampling profiler cannot say what `x` was at step 4,712.

**Bound the history.** Ring buffers keep the last N events at near-zero cost.
Nirvana's default ring buffer is 16 MB. Java Flight Recorder's published figure:

> "The overhead for recording a standard time fixed recording (profiling
> recording) using the default settings is less than two percent for most
> applications."
> — <https://docs.oracle.com/en/java/javase/21/troubleshoot/troubleshoot-performance-issues-using-jfr.html>,
> read 2026-09-18 (VENDOR CLAIM)

What it gives up is everything before the window, which is usually where the
cause is.

**Index after the fact.** Pernosco's model: build the database during replay,
in parallel, in the cloud. What it gives up is stated by Pernosco itself —
"recorded execution times of many minutes (though not yet hours)" — plus the
requirement to run the replay at all. TTD's index is "typically twice as large
as the trace file".

**Record only what was asked, and re-run for more.** The cheapest approach and
the one with the least published evidence. DynamoRIO exposes API for
re-instrumenting cached code on demand (`dr_flush_region_ex`,
`dr_replace_fragment`, <https://dynamorio.org/API_BT.html>, read 2026-09-18),
but no verbatim statement of an adaptive-instrumentation workflow was obtained,
and no benchmark of the approach was found. For an agent this is nonetheless
the most natural shape: the agent already knows what it wants to ask, and can
afford to run the program again.

| Approach | Cost | Gives up |
| --- | --- | --- |
| Full value trace, native (Nirvana) | 0.51 bits/instr, 11.89x (MEASURED) | Nothing — which is why it is the expensive one |
| Full event trace, bytecode (TOD) | 113x, 33 GB per Eclipse session, 10-node cluster (MEASURED) | Nothing; the cost is an order of magnitude above Nirvana's, on different hardware and workloads |
| Deterministic replay (rr) | <2x excl. make, 0.08-19 MB/s (MEASURED) | Random access; every query needs a replay |
| Hardware branch trace (Intel PT) | 100s of MB/s/core; decode 100-1000x collect time | All data values |
| Sampling (GWP) | ~0.3% (MEASURED) | Any specific instant |
| Ring buffer (JFR) | <2% (VENDOR) | Everything outside the window and the event set |
| Offline index (Pernosco, TTD) | Replay plus parallel build; index ~2x trace (TTD) | Bounded to minutes of execution; not local |
| Re-run with more instrumentation | Only what is asked | Retroactive answers; the bug must reproduce |

---

## 8. For A7

A7 compiles to Zig, and today nothing maps the binary back to `.a7`
(`docs/audits/2026-09-18/production-readiness.md`, PRD-7). This section states
what was measured on this machine on 2026-09-18, then orders the options by
cost. Probe notes: `tmp/research/agentic-debugging/06-a7-probe.md`.

### 8.1 What actually happens today, measured

`examples/012_arrays.a7` compiled to Zig and built two ways. Environment:
`gdb` 17.2, `zig` 0.16.0, binutils 2.47, x86_64 Linux. `rr`, `lldb` and `perf`
are not installed on this machine.

**The generated Zig keeps A7's names.** The A7 locals `numbers`, `sum`, `i`,
`value` appear verbatim in the emitted Zig. Only the function name is mangled
(`main` → `__a7_user_main`) and the loop binding order is swapped. The
name-level mapping is already close to identity; what is lost is file, line and
function name.

**Default backend: variables, no lines.** With `zig build-exe arr.zig -ODebug`:

```
Breakpoint 1, 0x00000000011d8058 in arr.__a7_user_main ()
numbers = {10, 20, 30, 40, 50}
sum = -15576
```

gdb prints both A7 locals, by their A7 names, with correct values. But
`break arr.zig:20` fails with "No compiled code for line 20 in file
\"arr.zig\"" even though `objdump --dwarf=decodedline` shows line 20 at
`0x11d80b5`, `info line *0x11d8058` reports "No line number information
available", and `next` reports the function "has no line number information".
Line info works for the thin wrapper `arr.main` and not for the generated body.

**LLVM backend: lines, one variable missing.** With `-fllvm`:

```
Breakpoint 1, arr.__a7_user_main () at arr.zig:20
20	        sum += value;
value = 10
i = 0
sum = 0
No symbol "numbers" in current context.
```

`info scope arr.__a7_user_main` lists exactly one variable, `sum`. The A7 local
`numbers` — a five-element array the user declared — has no `DW_TAG_variable`
at all, at A7's own debug profile. A controlled probe identifies the cause:
emitting `var numbers` with an address-taking discard makes it appear
(`Symbol numbers is a variable at frame base reg $rbp offset 0+-88, length 20`,
and `print numbers` gives `{10, 20, 30, 40, 50}`). Neither half alone works:
`_ = &numbers;` after a `const` leaves the scope unchanged, and a bare `var`
does not compile. See §8.3 item 2a.

The two backends fail in opposite directions on the same source, and A7 pins
neither today. Choosing one is the first thing to fix, and it is a build-flag
decision, not a compiler change.

Two more measurements. `break __a7_user_main` fails; the symbol is namespaced
`arr.__a7_user_main`, so an agent must know the module prefix. And the debug
sections of that twelve-line program total 3.23 MB (default backend) or 2.41 MB
(`-fllvm`), almost all of it Zig's standard library.

### 8.2 A correction to the plan

The audit's PRD-7 names **SRC-MAP** (Wave 3) as the owner of the fix. The
evidence map disagrees, in the repository's own words:

> "no source-map work (Wave 3 SRC-MAP `EXEC:155` is for compiler diagnostics,
> not debug info)"
> — `docs/plan/audit/language-evidence-map.md:131`

`docs/plan/fix-program/frontend-fix-plan.md:310` defines SRC-MAP as "One source
map per file (file ID, offsets, line table); tokens carry offsets, end
positions and decoded values" — that is byte offsets for diagnostics, not a
generated-code-to-source mapping. Nothing in the plan owns debug info. Two
repository documents disagree about this and one of them should change.

### 8.3 What is cheap, in order

**0. Free, today: an agent can already debug an A7 program in Zig terms.** rr
is language-agnostic — it records syscalls, not source — and `-ODebug` emits
DWARF. An agent with rr plus gdb gets deterministic record, reverse execution,
and whatever variable state Zig's DWARF exposes, which §8.1 shows is
incomplete. The names it does see are A7's. Nothing needs to be built for this;
rr needs installing. Do this first, because it measures how much the rest is
worth.

**1. Pin a Zig backend and test the result (hours).** On the one example
probed, gdb 17.2 could not resolve any line for the generated function body
under the default backend and could under `-fllvm`; `objdump` decodes the lines
in both cases, so what was observed is a gdb-Zig interop failure, not a missing
line table. Either way, until a backend is pinned every statement about A7
debuggability is conditional. A test that compiles one example, builds it, and
asserts `gdb -batch` can set a line breakpoint inside the generated function
would have caught this.

**2. Emit provenance comments (hours to days).** `grep -n '"//' a7/backends/zig.py`
returns nothing: the backend emits no provenance at all. A `// a7:<file>:<line>`
comment before each emitted statement costs one string per statement, changes
no semantics, and gives an agent — or a person reading a panic trace — the A7
line by reading the generated file at the line the trace names. It does not
reach DWARF. It is still the highest ratio of usefulness to cost on this list.

**2a. Emit `var` plus a discard, not `const`, in the debug profile (hours).**
Measured on this machine: emitting `var numbers: [5]i32 = ...` followed by
`_ = &numbers;` makes the missing variable appear.

```
Scope for arr_var.__a7_user_main:
Symbol numbers is a variable at frame base reg $rbp offset 0+-88, length 20.
Symbol sum is a variable at frame base reg $rbp offset 0+-68, length 4.
$1 = {10, 20, 30, 40, 50}
```

Both halves are required, and each was probed separately:

- `_ = &numbers;` after a `const` does not work — the scope still lists only
  `sum`.
- `var` alone does not compile. Zig rejects it:
  `error: local variable is never mutated` / `note: consider using 'const'`.

So this is two tokens, not one, and it is a codegen choice rather than a trick:
in the debug profile, emit A7's immutable locals as Zig `var` with an
address-taking discard, and accept whatever the optimizer would have done with
the `const`. That turns §6.2's "keep values alive" from a research topic into a
small, local change while the backend is still small. It should be confined to
the debug profile; nothing here argues for doing it in a release build.

**3. Name the generated file after the source (minutes).** Zig refuses a
non-`.zig` extension, but accepts `hello.a7.zig`. DWARF then contains a
filename with `.a7` in it, and `strings | grep .a7` stops returning 0. Cosmetic,
and it makes the panic traces in PRD-7 legible.

**4. A sidecar line map plus a shim (weeks).** The Cython precedent (§6.4),
which is a working system and not a hypothesis: Cython writes
`cython_debug/cython_debug_info_<module>`, a versioned XML file, and ships
`cygdb`, a gdb Python extension that reads it. For A7 that means an out-of-band
map from generated Zig line to `.a7` line, plus a DAP or gdb-Python layer that
translates locations and demangles `arr.__a7_user_main` back to `main`. This is
the only route to real A7-level breakpoints, because Zig has no line directive
and the proposal to add one is closed as not planned (§6.4). It needs the origin
data SRC-MAP would produce, but it is a separate deliverable from SRC-MAP and
needs its own owner.

**5. Line-preserving code generation (weeks, with a permanent tax).** Verified
possible: the entire A7 preamble compiles as a single Zig line, so Zig line N
can be made to equal A7 line N. Tested on this machine — a one-line preamble
built and debugged correctly. The cost is that every A7 statement must emit on
one Zig line forever, and the generated Zig becomes unreadable. It buys correct
line numbers without a shim, and it is fragile in exactly the way generated
code should not be. Listed for completeness; not recommended.

**6. Emit DWARF directly, bypassing Zig's debug info (months).** The
Kotlin/Native route. Correct, and out of scope for a language that does not yet
have error codes.

**Verdict.** Items 0 through 3, including 2a, are worth doing before the
language is finished: together they are a day's work and they change what a
panic trace and a debugger session show. Item 4 is worth doing once the origin
data exists, and it needs its own owner — not SRC-MAP, per §8.2. Item 5 is not
worth its permanent tax. Item 6 is not a v1 question.

### 8.4 What A7 should decide now, before the language is finished

Three of these are language decisions, not tooling decisions, and they get
harder later:

- **Determinism, per construct.** §6.3: every language that randomizes
  something did so for a good reason and made replay harder. A7 has no hash
  map iteration order to fix yet. Decide now whether map order, allocator
  addresses and RNG seeding are specified, reproducible-on-request, or free.
- **A debug profile with a stated guarantee.** Swift's `-Onone` "preserves all
  debug info" is the strongest claim anyone documents (§6.2). A7 controls its
  own emitted Zig; it could refuse to fold a user's `const` in the debug
  profile, which is exactly what made `numbers` invisible in §8.1. That is a
  codegen decision and it is cheap while the backend is small.
- **No recursion is an asset here.** A7 bans source recursion. Bounded call
  depth makes stack reconstruction, checkpointing and the "why did this not
  run" question all cheaper, and it is the kind of property Tolmach & Appel
  were relying on when they said checkpoint cost tracks the amount of mutable
  state (§3.3). Worth stating in the eventual debugging design rather than
  rediscovering.

And one that is not a language decision: an agent gains more from the query
interface than from the stepping interface (§2). If A7 ever builds
agent-facing debugging, the thing to copy is TTD's `Calls()` and `Memory()`, or
Whyline's question taxonomy — not `stepBack`.

---

## Sources

Primary sources fetched and quoted in this report, all read 2026-09-18. Full
extraction notes, including fetch failures, are in
`tmp/research/agentic-debugging/`.

Record and replay: arXiv:1705.05937 (rr, ATC 2017); rr-project.org and the rr
wiki; undo.io and docs.undo.io; Microsoft Learn TTD overview and object model;
usenix.org VEE 2006 p154-bhansali.pdf (Nirvana/iDNA); replay.io about, blog and
static.replay.io/protocol; sourceware.org gdb manual (Process Record and
Replay, Reverse Execution, Checkpoint/Restart, GDB/MI, Remote Overview);
pypy.org RevDB post; peps.python.org/pep-0669.

Omniscient and query: pernos.co (vision, overview, dataflow, searchbox, faq);
robert.ocallahan.org (Pernosco update, chaos mode); arXiv:cs/0310016 (ODB);
pleiad.cl/tod; scg.unibe.ch Lien08b (ECOOP 2008); pleiad.cl
pothierAl-oopsla2007.pdf (TOD); Ko & Myers ICSE 2008 and CHASE 2008; pql.sourceforge.net; perfetto.dev.

Checkpoint: criu.org (What_cannot_be_checkpointed, Performance_research,
Statistics); qemu.org; Firecracker snapshot-support.md; wiki.squeak.org;
sbcl.org manual; erlang.org (sup_princ, sys, erlang:trace, dbg);
scheme.com/tspl4; Tolmach & Appel JFP 1993; lcamtuf.blogspot.com;
AFLplusplus persistent_mode.md and AFL-Snapshot-LKM.

Protocols: microsoft.github.io/debug-adapter-protocol; sourceware.org GDB/MI;
lldb.llvm.org; lists.llvm.org lldb-dev 2019-08; man7.org ptrace(2),
personality(2), setarch(8); Oracle JDWP and JVMTI specs;
ChromeDevTools/devtools-protocol JSON; docs.kernel.org uprobetracer;
bpftrace docs/language.md.

Agents, localization, repair, test generation, invariants: arXiv 2503.21557
(debug-gym), 2405.15793 (SWE-agent), 2402.16906 (LDB), 2304.05128
(Self-Debugging), 2310.06770 (SWE-bench), 2506.12286 (SWE-Bench Illusion),
2304.00385 (ChatRepair), 2007.14049 (Pynguin); st.cs.uni-saarland.de tse2002
(ddmin); cs.purdue.edu hdd.pdf; users.cs.utah.edu pldi12-preprint (C-Reduce);
gpbib.pmacs.upenn.edu LeGoues_2012_ICSE; huang.isis.vanderbilt.edu
faultloc-not-help.pdf (Parnin & Orso ISSTA 2011); groups.csail.mit.edu
kali-issta2015.pdf (Qi et al.); evosuite.org icse17_experience.pdf;
google.github.io/oss-fuzz; cs.cmu.edu invariants-tse2001.pdf and
plse.cs.washington.edu daikon manual.

Compiler and scale: gcc.gnu.org Optimize-Options; llvm.org
SourceLevelDebugging, HowToUpdateDebugInfo, LangRef; dwarfstd.org issue
100909.1; arXiv:2402.04811 (CC 2024); faculty.cc.gatech.edu
pldi20_yuanbo1.pdf (PLDI 2020); arXiv:2011.13994 (ASPLOS 2021);
apple/swift OptimizationTips.rst;
doc.rust-lang.org (cargo profiles, HashMap); docs.python.org PYTHONHASHSEED;
go.dev/ref/spec; nim-lang.org/docs/nimc.html; cython.readthedocs.io;
kotlinlang.org native-debugging; nodejs.org --enable-source-maps;
github.com/ziglang/zig issue 1833 and lib/std/builtin.zig;
torvalds/linux perf-intel-pt.txt; research.google.com GWP; Oracle JFR
troubleshooting; dynamorio.org API_BT.

## Not verified

Research method note: five parallel agents fetched primary sources on
2026-09-18, with raw extractions kept in `tmp/research/agentic-debugging/`.
The session's web-search budget (200 calls) was exhausted before every gap was
closed. Two delegated fallback lookups were attempted: a GLM-5.3-flash run,
which failed on the provider's weekly limit (`tmp/glm/agentdbg-gaps.status`),
and a Grok run (`tmp/ai/agentdbg-gaps3.md`), which exceeded its turn limit
without producing a clean answer.

**No claim in this report is sourced to either delegated lookup.** What the
Grok run did supply was four working URLs. Those were fetched directly on
2026-09-19 and extracted locally with `pdftotext -layout`, which closed four
gaps with primary text: Parnin & Orso's ISSTA 2011 paper (§5.5), TOD's OOPSLA
2007 measurements (§2.2), the PLDI 2020 paper (§6.1), and the ASPLOS 2021 paper
(§6.1, whose title is "Who **is** Debugging the Debuggers?", not "Who's").
Extractions are in `tmp/research/agentic-debugging/parnin_orso.txt`,
`tod_oopsla2007.txt` and `pldi2020.txt`.

What remains open:

- **TOD's query latencies.** The paper was retrieved on 2026-09-19 and its
  overhead, event-rate and trace-size figures are now quoted in §2.2. Its
  query-response measurements (§6.2 of that paper) were not extracted.
- **Zeller's FSE 2002 cause-effect chains.** The PDF was fetched twice and its
  abstract could not be extracted either time. No cost figures are given in
  §5.6 for the state-differencing technique, which is the technique most
  directly relevant to this report's question.
- **EvoSuite's SF110 branch-coverage figure** (commonly cited as 71%). The
  TOSEM 2014 paper was blocked; the figure appears here only as UNVERIFIED in
  §5.8. A likely author preprint at
  `evosuite.org/wp-content/papercite-data/pdf/tosem_evaluation.pdf` was
  surfaced by the Grok lookup but not fetched.
- **ChatRepair's benchmark composition.** The 162/337 headline was confirmed
  from the arXiv abstract; which corpus the 337 comes from was not.
- **Whether any published work evaluates an LLM agent against a record-replay
  or time-travel debugger.** None was found (§5.10). Absence of evidence here
  reflects a search that ran out of budget, not a proof that none exists.
- **`-O0` versus `-O2` performance ratio.** Still no source read directly. The
  Grok lookup surfaced three candidates it claims to have read — a Purdue
  technical report (TR-ECE 04-01, GCC 3.3 on SPEC CPU2000), Branco 2016, and a
  thesis using Clang 6.0.0 on PolyBench — reporting ratios between 2.44x and
  3.91x. None was verified here, so no ratio is quoted in §6.2.
- **Replay.io's architecture.** No fetched Replay.io page states that it is
  built on rr. Treated as unconfirmed.
- **Chronon's overhead and its discontinuation date.** The 200x/2x figures are
  a vendor slide deck relayed by the rr wiki — third-hand. No dated
  discontinuation statement was found.
- **JVMTI.** The specification was not fetched directly. No JVMTI claim is made
  beyond the Oracle overview page quoted in §4.6.
- **Fraction of local variables unavailable at `-O2`.** No trustworthy
  published figure exists; see §6.1.
- **Cython's sidecar contents.** The file's name, directory, XML format and
  root element were read from `Cython/Debugger/DebugWriter.py` (§6.4). What
  elements it emits below the root was not enumerated.
- **How many DAP adapters implement `stepBack`.** Reported as sparse, not
  counted.
- **A7 probes** cover one example (`012_arrays.a7`) on one machine, one Zig
  version and one gdb version. They are not a survey of A7's debuggability.
- **rr on an A7 binary** was not run: `rr` is not installed on this machine.
  The claim in §8.3 item 0 that rr would work is INFERENCE from rr's
  syscall-level design and the presence of DWARF in the `-ODebug` build.
