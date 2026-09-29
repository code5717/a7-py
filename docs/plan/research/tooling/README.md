# Debugging, testing and analysis: research program

Started 2026-09-18 at the user's request: research how languages and compilers
are debugged, tested and analyzed, and what tooling that requires. The brief is
deliberately not A7-specific — each report studies the field first and closes
with a short section on what applies here.

Not covered again: runtime sanitizers. `docs/lang-safety/02-sanitizers.md`
(646 lines) already covers ASan, LSan, MSan, TSan, HWASan, UBSan, CFI,
`-fbounds-safety`, SafeStack, ShadowCallStack and PAC, and
`docs/lang-safety/03-hardware.md` covers MTE and CHERI. Reports below cite those
files instead of repeating them, and extend them only where a source postdates
them or contradicts them.

| Report | Question |
| --- | --- |
| `01-debug-info.md` | How a compiled or transpiled language lets a debugger show the user's own source: DWARF, `#line`, source maps, and what each compiler emits |
| `02-testing-compilers.md` | How compilers are tested: differential and metamorphic testing, random program generation, fuzzing, test-case reduction, conformance suites, golden and snapshot tests, mutation testing |
| `03-static-analysis.md` | Analyses a compiler runs on every build with no user input: abstract interpretation, dataflow frameworks, symbolic execution, and the IR designs that make them possible. Proofs the user states are report 10 |
| `04-dynamic-analysis.md` | What can only be found at run time: coverage, tracing, profilers, dynamic invariant detection, and the instrumentation each needs. Record-and-replay is report 08 |
| `05-developer-tooling.md` | LSP, DAP, REPLs, formatters, and how small languages ship them without a large team |
| `06-verified-compilation.md` | Compiler correctness as an engineering problem: CompCert, translation validation, Alive2, bisection, crash triage, regression corpora |
| `07-prevention-by-design.md` | The other half of the question: how a language design removes whole defect classes before any tool runs — Bend's laws, affinity, termination and purity, against SPARK, Dafny, Rust, Pony and others |
| `08-agentic-debugging.md` | An agent debugging a program the way a person cannot: full variable state at every step, stop and replay from any point, deterministic record-and-replay, and the protocols that expose it |
| `09-visualization.md` | Seeing a program run: state, control flow, data flow, memory, concurrency and performance, for humans and for agents |
| `10-proofs.md` | Proving a program right: contracts, refinement types, SMT-backed verifiers, proof assistants, model checking, runtime verification and proof-carrying code — what each costs, where each is used in industry, and how a small language adopts them incrementally |

Evidence standard, as for every research document in this repository: quote the
source verbatim with a URL and the date read, attribute nothing you have not
read, mark inference as inference, and state plainly where sources disagree.

Every claim is judged on agent value and human value, weighted toward
agentic use, and each gets a report, a section or a one-paragraph ruling
according to that judgement. See [EVALUATION.md](../EVALUATION.md); do not
research an idea past its ruling.
