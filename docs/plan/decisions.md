# V1 decision ledger

Status: the authoritative record of user decisions for the A7 v1 plan. Other plan
documents cite entries by ID.

Entries L1–L14 and O1–O4 come from the Codex planning session of 2026-09-14,
rollout `2026-09-14T08-23-34-01a09e5e-e46a-7c93-8af5-686fbcc52b59`. Plan Mode
stopped that session from writing its decisions or research to the repository,
so they were recovered from its log on 2026-09-15. Entries L15–L22 come from the
Claude Code session of 2026-09-15, which recorded no times.

User words are quoted exactly, including original spelling. Times are UTC.

## States

- **Locked:** the user chose this direction. Details still follow the approval
  rule.
- **Open:** the user deferred, asked for more research or asked for a
  recommendation. Nobody may choose on the user's behalf.
- **Superseded:** a locked decision replaces this earlier material.

## Approval rule

User direction, 2026-09-14 18:32: "everything that changes, ask me with examples,
so i can approve, (document this)".

Before changing existing syntax or behavior, present the current behavior, the
proposed behavior, concrete A7 examples and the compatibility impact. Then obtain
the user's approval. Research recommendations and earlier accepted design
decisions are not approval. `AGENTS.md` and `CLAUDE.md` state the same rule.

## Locked decisions

| ID | When | Topic | Decision | User words |
| --- | --- | --- | --- | --- |
| L1 | 2026-09-14 18:20 | V1 boundary | Finish the broader vision: the accepted redesign plus ownership, a fuller standard library and concurrency | Selected "Finish the broader vision" |
| L2 | 2026-09-14 18:32 | Compatibility | Documented breaking changes are allowed, under the approval rule | Selected "Allow documented breaking changes" |
| L3 | 2026-09-14 19:11 | `number` type | Remove `number`; `f32` and `f64` are ordinary types | Earlier: "maybe remove number?, and become like odin and zig"; selected "Remove number" |
| L4 | 2026-09-14 19:20 | Integers | Explicit widths only: `i8`–`i64`, `u8`–`u64`, `isize`, `usize`. No arbitrary-precision `int` or `uint` | Selected "Explicit widths" |
| L5 | 2026-09-14 19:45 | Integer arithmetic | Ordinary `+`, `-` and `*` wrap, as in Odin | Earlier: "look at zig, odin etc."; selected "Odin-style defined wrapping" |
| L6 | 2026-09-14 20:00 | Argument mutation | Argument bindings are immutable. Changing referenced data needs a separately approved interface | Earlier: "all function arguments are immutable"; selected "Explicit mutation" |
| L7 | 2026-09-14 19:51 | AI in v1 | Tensor operations, inference, training and an AI-ready language foundation | "All, Tensor ops & Infrerence, and training, and AI-ready language foundation" |
| L8 | 2026-09-14 20:00 | AI target | CPU first, with an accelerator interface for a later GPU backend | Selected "CPU first" |
| L9 | 2026-09-14 20:00 | AI implementation | A7 owns tensor semantics and automatic differentiation over established native kernel libraries | Selected "A7 runtime" |
| L10 | 2026-09-14 20:02 | AI acceptance | Train and run a small image classifier and a small decoder transformer, including checkpoint recovery | Selected "Classifier and transformer" |
| L11 | 2026-09-14 20:02 | AI precision | Tensor formats `f16` and `bf16` in addition to `f32` and `f64` | Selected "Also f16 and bf16" |
| L12 | 2026-09-14 05:35 and 16:15 | Review routing | Cybersecurity reviews use GLM | "any cyber seucirity stuff use glm" |
| L13 | 2026-09-14 05:33 | Test quality | The test-quality rule, recorded exactly in `AGENTS.md` | None |
| L14 | 2026-09-14 20:11 | Research records | Research is kept in repository docs | "all research should add to docs" |
| L15 | 2026-09-15 | Memory direction | Automatic memory management with no runtime collector, designed for data-oriented programs, resolved at compile time, in the style of Jai, Odin and Zig | "we need to make something like garbage collection, but with data oriented design in mind and everything is resolved compile-time so it becomes as jai, odin and zig" |
| L16 | 2026-09-15 | Floats | Follow Zig and C: IEEE 754 values, so NaN and infinity are ordinary values. Strict arithmetic by default; result-changing optimizations only by explicit opt-in | "for the float use zig, C" |
| L17 | 2026-09-15 | Memory surface (refines L15) | As simple to use as Python and garbage-collected languages. The compiler groups allocations into arenas and pools itself. This needs new language concepts | "i want to make this super simple like python and how gc languages work"; "the compiler should group some stuff together as arenas and pools, we need new concepts" |
| L18 | 2026-09-15 | Memory optimization | Reuse allocated space and optimize memory, aiming at next-generation compiler technology | "also reusing allocated space and optimization, i want this to be the next generation of compiler technology" |
| L19 | 2026-09-15 | Memory visibility (refines L15, L17) | Programmers should not have to think about memory at all | "basically anyone using this programming language shouldnt care about memory in general" |
| L20 | 2026-09-15 | Language goals | Powerful and simple, with C-like performance and memory use. Syntax may change or be simplified, under the approval rule | "we might need to change some of the syntax as needed or simplify more"; "I want a powerful, super simple, super fast (C like) performance"; "its like C in performance and memory usage"; "not even like C++" |
| L21 | 2026-09-15 | Relationship to Zig | A7 must not carry Zig's mental load of manual memory management and safety. Zig is the backend target, not the user model | "Zig is like C but complicated and requires alot of mental load of memory management and safety" |
| L22 | 2026-09-15 | Starting point | Keep the current A7 syntax for now and build on it from the Zig backend. Syntax changes come later, under L20 and the approval rule | "we can work from Zig (keep my a7 syntax for now and start from it)" |
| L23 | 2026-09-16 | Work order | Correctness first: new examples, the typed IR and docs rewrites wait until every CRITICAL and HIGH compiler-audit finding is fixed or is in an approval packet the user has seen | Selected "Correctness first" |
| L24 | 2026-09-16 | Approval batching | Crashes, hangs, miscompiles, wrong diagnostics and code Zig already rejects are fixed without a packet. Every fix that changes a program that compiles and works today goes into one packet per area (lexer, parser, modules, types, safety, backend) with before and after examples | Selected "Batch per area" |
| L25 | 2026-09-16 | Module unit | One file is one module. Its top-level names live in its own namespace and are written `alias.name` after `alias :: import "path"` | "can u see what odin does? or make a better solution"; "what if i made the file as the module"; selected "File is the module" |
| L26 | 2026-09-16 | Duplicate imports | Importing the same file twice in one file is a compile error, whether by the same path, another spelling of it, or a second alias. Different files may each import it | "and naming the same file twice isnt allowed" |
| L27 | 2026-09-16 | Module visibility | A top-level name starting with `_` is private to its file; every other top-level name is public; names starting with `__` are reserved for the compiler | "can we think about something"; selected "Underscore means private" from four options shown with examples |
| L28 | 2026-09-17 | Alias clashes | A local with the same name as an import alias is a compile error | Selected "Compile error" |
| L29 | 2026-09-17 | Struct fields across files | All struct fields are visible to importers | Selected "All fields visible" |
| L30 | 2026-09-17 | Import paths | Import paths resolve from the importing file; `..` is allowed while the result stays inside the main file's folder | Selected "From the importing file" |
| L31 | 2026-09-17 | Stdlib import names | Bare names stay: `import "io"` and `import "math"` mean the standard library, so local files named `io.a7` or `math.a7` cannot be imported | Selected "Keep bare names for stdlib" |
| L32 | 2026-09-19 | Safety of uncalled functions | Batch C4's deferred-assignment fix may reject a program that A7 accepts and Zig builds today, where the program only builds because Zig analyses function bodies lazily. Example: an uncalled `helper :: fn()` containing `while i < 3 { defer x -= 5; y := 10 / x; i = i + 1 }` — a certain division by zero on iteration 2 that Zig never inspects because nothing calls `helper`. A7 analyses uncalled functions by design, so it rejects it. Waived: the rejection stands | Selected "Waive and apply"; corpus blast radius measured at 0 of 2,030 programs; not applying would leave the loop-defer hole to become an accepted, building division by zero once batch Z4 fixes `defer void;` |


## Cleanup approval, 2026-09-19

L33. The user approved matching constant float remainder to the existing Zig
runtime remainder. User words: "Approve matching runtime remainder".
The presented example used `x: f64 = -5.5`, `y: f64 = 2.0`, and
`io.println("{} {}", -5.5 % 2.0, x % y)`. It printed `0.5 -1.5` before the fix;
the approved result is `-1.5 -1.5`. This changes some constant-expression results.
Remainder uses a quotient truncated toward zero, with the dividend's sign.
No syntax change or change to divisor proof requirements was approved.

L34. The user approved correcting three backend binding failures. User words:
"ok fix", followed by "Yes, fix them". The approved cases are a local named
`error`, an unused `for` item, and a loop item that shadows an outer variable.
A7 accepted these forms but emitted Zig that failed to build. The fix escapes
backend keywords, discards unused captures, and preserves binding scope through
unique emitted names. This approval does not change A7 syntax or the meaning of
lexical shadowing.


L35. After the GLM-5.3 audit and its corrected reproductions, the user said
"go fix it" on 2026-09-19. This authorizes repairs to the reviewed compiler
failures. The implementation rejects the six accepted-crashing safety probes
and malformed declarations instead of emitting unsafe or partial programs.
Mixed-width arithmetic uses the wider compatible native type, so an explicit
narrow destination is rejected rather than mis-typed. L5's concrete
`x: u8 = 255; x += 1` case now produces 0. Existing successful non-overflowing
example outputs must remain unchanged. Compiler recovery, diagnostics, backend
identifier quoting, compound division/remainder, literal context, and the
reported IO/type mismatches are repaired within the reviewed scope.

This instruction does not choose new syntax, a new ownership model, `ref`
read/write semantics, signed `abs(MIN)`, signed division overflow, or planned
library operations. Those alternatives remain explicit open items. Historical
audit reports are retained; the remediation report records actual checks.


## Core V1 and self-hosting decisions, 2026-09-20

These entries come from the current Codex planning conversation and the user's
instruction, "Implement the plan." They change the delivery direction, not the
implemented language. Exact syntax, failure behavior and compatibility changes
still follow the approval rule above.

| ID | Topic | Decision and evidence |
| --- | --- | --- |
| L36 | Core V1 | Qualify the core language, automatic memory, useful libraries and tools first. User selected "Core language first (Recommended)". This supersedes L1 and L7 as V1 release requirements. AI and concurrency remain design constraints and later delivery work. |
| L37 | Runtime memory help | Compiler-managed runtime tracking is allowed when static analysis is insufficient. User selected "Allow automatic runtime help". This supersedes L15's absolute no-collector restriction. It does not select reference counting, tracing or another mechanism. |
| L38 | Performance | Each required equivalent workload must have median runtime and peak live memory at most 1.10 times a reviewed C baseline. User selected "Within 10%". Include runtime bookkeeping; also report reserved memory, RSS, allocations, copies, cleanup and compiler cost. No candidate is qualified yet. |
| L39 | Safety | Prefer compile-time proof; allow checked execution where proof is unavailable. User selected "Allow checked execution (Recommended)" and added "try as much as possible compile-time proof". Required runtime checks must remain in release builds. The current fail-closed contract needs an explicit migration packet before behavior changes. |
| L40 | Future parallel execution | Infer independence where safe, with a small explicit API where needed. User selected "Infer when safe (Recommended)" and said "keep AI and concurrency in mind when making the language, and see how bend programming lang does things, with multi-core and gpu targets too". Unknown effects stay sequential. |
| L41 | Native integration | Include a minimal checked native interface, implemented through Zig. User selected the minimal C interface, then clarified "the C interface use Zig for it" and "just Zig for all". Zig handles native imports, runtime support, builds and linking. Application code does not manage raw native pointers. |
| L42 | List identity | Growable-list assignment shares identity. An explicit copy creates independent data. User selected "Share the same list (Recommended)" for `b := a`. This does not change the current value behavior of structs or fixed arrays. Copy spelling and detailed failure behavior remain subject to the packet rule. |
| L43 | V1 compiler | Keep the Python compiler for V1. User selected "Keep Python compiler for V1 (Recommended)" when asked whether "just Zig" required rewriting the compiler in Zig. Zig remains the backend and runtime implementation language. |
| L44 | V2 compiler | Prepare to implement the compiler in A7 itself. User said "we might need to stablize the python compiler to write V2 of the compiler in itself (A7)". Qualify compiler-building workloads in V1. V2 needs bootstrap parity before replacing Python. |
| L45 | Implementation | The user said "Implement the plan." Preserve the existing working tree, repair correctness and release gates, prototype and measure memory candidates, and implement approved language packets. Do not report V1 complete from passing aggregate tests alone. |
| L46 | Later cleanup | The user requested extensive compiler comments, small execution diagrams, organization and performance work, then said "first finish the plan". Complete the agreed V1 work first. Keep documentation necessary for its changes in scope; broad cleanup follows. |

## Constant design direction, 2026-09-20

L47. The user selected "Develop exact-fit untyped constants, like Odin" in
response to the choice between flexible constant fitting and strict concrete
constant types. Develop [P-TYP](packets/P-TYP-forward-globals.md) so an untyped
`RATE :: 2.0` can initialize `i32` in either declaration order, while `2.5` and
out-of-range values reject. Ordinary runtime float values still require explicit
conversion. This approves development of the revised packet, not implementation
or every arithmetic, rounding and materialization detail. The earlier strict
rejection proposal is preserved as history. Obtain approval of the completed
behavior and compatibility examples before changing the compiler.

Follow-up on L47: the user said "proceed" after the draft identified nonfinite
constant routes and resource limits as remaining issues. Continue the design,
isolated candidate and compatibility measurements. Preserve the existing typed
math-call routes confirmed by native evidence. Record concrete resource limits
and further changed-program examples before requesting implementation approval.
No production behavior change was recorded by that follow-up.

Implementation authorization, 2026-09-20: after reviewing the completed packet,
the user challenged the repeated approval request with "again?" and then said
"continue". Treat the earlier "proceed" as approval to implement P-TYP's
selected rules, compatibility changes and documented resource limits. The
controller's earlier design-only interpretation is superseded. Do not request
this approval again. Keep implementation and release verification status separate
from authorization.

## Buffered stdout and release arithmetic, 2026-09-30
L48. The user selected "C-like buffered (Recommended)" for the generated print
helpers. Stdout calls buffer through one persistent writer and flush at
program exit and before every stderr write. Stderr calls keep flushing after
each call. Compatibility: pipe and file consumers see the same bytes, and the
interleaving of stdout and stderr becomes deterministic for completed
programs. Stdout content always precedes the stderr content written after it.

L49. The user selected "Debug keeps +%, release uses +" for integer arithmetic
lowering. When the safety pass proves that an integral `+`, `-`, `*` or
compound assignment result fits the type range, release builds emit the plain
Zig operator. Debug builds keep the wrapping form, so a wrong proof surfaces
as a Debug/Release output difference that the both-profile tests catch.
Unproven cases keep wrapping in both profiles, and `--no-nonwrap` forces
wrapping everywhere. This refines L5: wrapping remains the language semantic,
and non-wrap is an approved codegen optimization for proven cases. Proven
cases cannot wrap, so observable values do not change.

## Wave execution order and memory scope, 2026-10-01

L50. The user selected "Interleave: C code, B research" for wave order, then
"C then E then B" for the repair sequence: Wave C (declaration-identity
shadowing) first, Wave E (the 15 exact-arithmetic failures) second, Wave B
(memory prototypes) last. All work stays uncommitted until the final green
gate; a consolidated checkpoint commit of both sessions' work starts
implementation.

L51. The user selected "Arena + RC, no tracing" for Wave B scope. Build the
C1' arena interim-lowering prototype and an RC prototype behind a flag, and
compare them against the delivery roadmap's seven workload shapes before
selecting a mechanism under gates M45/M14/M2. Tracing is documented but not
built. This records the mechanism comparison without selecting a mechanism,
so L37 still stands.

L52. The user adopted the 15 exact-arithmetic failures as repair Wave E after
diagnosis showed they reproduce at clean HEAD and share one subsystem
(`a7/exact_constants.py` plus its type-checker consumers). The repairs restore
pinned contracts: IEEE f64 rounding for fold operands (L16), i32 wrap for
i32-fitting operands, safety precedence for zero divisors. The LNG-16 no-main
exit-code decision enters as an approval-first packet draft, and the
-OReleaseFast safety-backstop question enters the Wave B comparison memo.

L53. The bench gate adopts two fixes from diagnosis: add the report-only
`bench_perf.py` run to `run_all_tests.sh` (the docs already claim it runs
there), and harden the harness (more runs, trimmed median, run-to-run CV
filter, CPU pinning) before re-pinning. The 8-27% loose pins are re-taken on
an idle box under the fixed harness. Buffered stdout (L48) and non-wrapping
release arithmetic (L49) are not reverted: the former is a 5x win on
print-hot shapes, the latter costs nothing measurable on the corpus.

L54. The user selected Option B ("--lib flag") for LNG-16 on 2026-10-01:
a file with no `main :: fn()` is rejected at the Entry Point stage with
exit 6 instead of passing check and failing late at the Zig build. Current
behavior shown before approval: `a7 check` and `compile` both exited 0 on a
main-less file. Only the entry file is gated (the check runs before imported
modules merge, so libraries need no `main`); `a7 check --lib` and
`main.py --lib` accept a main-less library file, while `build` and `run`
still require `main` and exit 6 without it. Codegen is byte-identical:
`--lib` only suppresses the gate. Corpus impact is zero: all 50 examples,
all 10 benches, and all 10 safety fixtures define `main`.

L55. Gate diagnosis 2026-10-01: uncommitted parser work classified
`Name :: <bare identifier>` as TYPE_ALIAS (`_is_bare_identifier_alias`),
which broke the HEAD-pinned v1 behavior `Alias :: N` as a CONST value alias
(`unused-constant-keeps-effects`, both profiles, plus the same shape in
`test_audit_type_boundaries.py`). The parser cannot tell a value from a
named type, no corpus file uses a bare-identifier type target, and the new
pin test was added alongside the breaking change without approval. Both
call sites reverted to HEAD semantics (bare identifier stays CONST) and the
pin now asserts that; named-type aliases remain follow-up work. Not LNG-16:
the LNG-16 gate is inert when `main` exists, proven by stash isolation
(passing at HEAD, failing in worktree, fixed by this revert).

## Scope limits

- **L5** covers integer `+`, `-`, `*` and their compound assignments: after
  `x: u8 = 255` and `x += 1`, `x` must be 0. It does not decide division,
  remainder, signed `MIN / -1`, negation, shifts, narrowing casts or
  allocation-size arithmetic. For example, `q := x / -1` on `x: i8 = -128` stays
  open under gate G3.
- **L6** approves the principle only. No parameter-mode syntax is approved. The
  current `ref` parameter remains the working form: `value = 100` inside
  `fn(value: ref i32)` writes to the caller's value, and the binding `value` itself
  cannot be pointed elsewhere.
- **L8** permits accelerator interface design. It does not qualify any GPU, NPU,
  TPU or FPGA.
- **L11** names tensor formats. Scalar floats remain `f32` and `f64`.
- **L16** settles float values and strictness. Its sub-decisions remain in gate G1.
- **L20** is read as C's performance and simplicity without C++'s complexity or
  hidden costs. The user has not yet confirmed this reading.
- **L25-L31** set the module design direction. Their compatibility impact (which
  programs that compile today change) is shown in packet P-MOD before any of it is
  implemented. Cycles, the fate of `pub`, `x/mod.a7` directories and named or bare
  imports are not decided by these rows.
- **L24** does not approve any specific fix: the no-approval classes are listed in
  packet P0.1, and every fix still runs a compatibility scan.
- **L33** covers constant-folded float remainder matching the runtime remainder
  (quotient truncated toward zero, dividend's sign). It changes some
  constant-expression results; it does not change syntax or divisor proof
  requirements.
- **L35** authorizes repairs to the reviewed compiler failures within the
  reviewed scope (rejected crashing probes and malformed declarations,
  wider-type mixed-width arithmetic, recovery, diagnostics, identifier
  quoting, compound division/remainder, literal context, reported IO/type
  mismatches), keeping existing successful non-overflowing example outputs
  unchanged. It does not choose new syntax, a new ownership model, `ref`
  read/write semantics, signed `abs(MIN)`, signed division overflow, or
  planned library operations.
- **L47** covers the P-TYP selected rules, compatibility changes and
  documented resource limits for exact-fit untyped constants. Ordinary
  runtime float values still require explicit conversion. The completed
  behavior and compatibility examples need approval before further compiler
  changes.
- **L48** covers the generated print helpers only: stdout buffers through one
  persistent writer, flushed at program exit and before every stderr write;
  stderr keeps flushing after each call. Pipe and file consumers see the same
  bytes; stdout/stderr interleaving is deterministic for completed programs.
- **L49** covers release lowering of proven-range integral `+`, `-`, `*` and
  compound assignments to the plain Zig operator; debug builds keep the
  wrapping form and unproven cases keep wrapping in both profiles, with
  `--no-nonwrap` forcing wrapping everywhere. Wrapping remains the language
  semantic; this refines L5 as a codegen optimization for proven cases.
- **L50–L55** record the 2026-10-01 session's wave order (C, then E, then B),
  Wave B mechanism comparison (arena interim lowering plus flagged RC
  prototype against seven workload shapes, tracing documented but not built),
  Wave E exact-arithmetic repairs under pinned contracts, and bench-harness
  fixes with re-pinning on an idle box. L51 compares mechanisms without
  selecting one, so L37 still stands; L48 and L49 are not reverted.

## Implementation dispositions, 2026-09-20

SAF-4 continues the approved branch-fact repairs described in L35 and the
execution plan's S1 lane. The fix removes stale guard reinjection after an early
return. Its original unsafe case now rejects; valid continuing branches and
fresh guards remain accepted in the isolated tests. A 255-file corpus comparison
found no acceptance or diagnostic changes. This records implementation under
existing repair authority, not a new syntax or memory-model choice. See
[the repair evidence](../audits/2026-09-20-core-v1/saf4.md).

The external review's D2 constant-binding defect stays open in the lexical
binding/usage work. Fixing flat name tracking requires scope identities; no
blanket discard or speculative renaming is approved by this disposition. V1
cannot be qualified while required language cases still emit invalid Zig.

## Open decisions

| ID | When | Question | User response | State |
| --- | --- | --- | --- | --- |
| O1 | 2026-09-14 19:35–20:05 | Float values: IEEE or finite-only | "look at zig and odin"; "what should we do in terms of odin, and jai"; "Keep researching … i need this for AI too"; "review what should i choose"; "what should i do?" | Resolved by L16 |
| O2 | 2026-09-14 19:35–19:45 | Ownership interface and mode syntax | "we need to check this more"; "check odin and jai, and zig" | Research complete; gate G2, now replaced by the [memory plan](memory.md) |
| O3 | 2026-09-14 18:32 | Representation of `number` | "lets brainstorm this" | Superseded by L3 |
| O4 | 2026-09-14 18:32 | Arbitrary-precision allocation failure | "explain (in a more simpler way)" | Superseded by L3 and L4 |

## Superseded material

These records are kept, but they no longer define the v1 plan.

- Line numbers into tracked files (`docs/lang-safety/`, `docs/STATUS.md`,
  `docs/SAFETY_CONTRACT.md`) refer to git commit `701c679`.
- `08-decisions.md` and `HANDOFF.md` were reformatted on 2026-09-16 and carry
  dated notes pointing here. Find their entries by ID.
- The audit files are untracked. The roadmap carries an inline "cited as" marker
  at the cited passage.
- `STATUS.md` and `SAFETY_CONTRACT.md` are unchanged. Track 0 updates them. `D.nnn`
entries are in `docs/lang-safety/08-decisions.md`.

| Material | Replaced by |
| --- | --- |
| `docs/audits/2026-09-14/completion-roadmap.md:15-18`: experimental numeric types, GPU/AI and concurrency outside v1 | L1, L7 |
| `docs/STATUS.md:41-44`: tensor, AI, GPU and concurrency as deferred tracks | L1, L7 |
| `docs/STATUS.md:20-21`: numeric design brief before adding `int`, `uint`, `number` | L3, L4; gate G3 replaces the brief |
| D.001 (line 76): `int`, `uint`, `number` as primary types, with "No NaN, no inf" for `number` | L3, L4; float values go to L16 and gate G1 |
| D.002 (line 115): bit-width types for FFI only, with warnings elsewhere | L4 |
| D.003 (line 141): non-overflowing arithmetic through bignum promotion | L4, L5 |
| D.004 (line 179): mixed-sign widening that relies on arbitrary precision | L4 |
| Accepted conversion and parsing decisions written for `int`, `uint` and `number`: D.005, D.022, D.025–D.027, D.029, D.033–D.037, D.039 | L4; restate for explicit widths under G3 |
| D.007 `uint` string lengths; D.010 and D.020 `int`/`number` optionals and range tracking | L4; restate with `usize` and explicit widths |
| D.024 (line 760) and D.038 (line 1290): contradictory keep and remove decisions for `cast(T, x)` | Neither; gate G3 |
| `docs/SAFETY_CONTRACT.md:54`: range proofs for fixed-width `+`, `-`, `*` | L5. Proofs remain for division, casts, shifts and sizes |
| Proposed D.040, D.041, D.049: parameter-mode keywords, inferred modes, no storable references | Not accepted; L6 scope limit and gate G2 (now the memory plan) |
| `docs/lang-safety/HANDOFF.md` Q1 (bignum) and Q3 (`number`) | L3, L4. Q2 (`cast`) stays open under G3 |
| L1, L7 as V1 release requirements (broader vision, AI, ownership, stdlib, concurrency) | L36, L37: core language, automatic memory, libraries and tools first; AI and concurrency are later delivery work |
| L15 absolute no-collector restriction | L37 allows compiler-managed runtime tracking when static analysis is insufficient |
| L5 plain wrapping lowering for proven-range integral `+`, `-`, `*` | L49: wrapping stays the semantic; proven cases lower to the plain operator in release |
| Per-call stdout flushing in the generated print helpers | L48 C-like buffered stdout |

## Pending records

L50–L53 are session-selected, 2026-10-01.

### Gate-to-decision stub

| Gate | Locking coverage | State |
| --- | --- | --- |
| G1 | Partial: L16 (IEEE 754 values, strict arithmetic), L33 (runtime-matching float remainder) | Open |
| G2 | Replaced by the [memory plan](memory.md) | Open |
| G3 | Partial: L5 (wrapping `+`, `-`, `*`), L35 (reviewed failure repairs), L47–L49 (exact-fit constants, buffered stdout, release arithmetic) | Open |
| G4–G9 | None | Open |
| M1–M51 | None; L51 feeds the comparison into M45/M14/M2 without selecting a mechanism | Open |

Gates G1–G9 in the [v1 plan](README.md) and gates M1–M51 in the
[memory plan](memory.md) are not decisions until the user chooses. Record each
choice here with its time, the example the user approved and the compatibility
impact.
