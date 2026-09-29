# Prevention by design: how a language stops defects from existing

Report 07 of the [debugging, testing and analysis research program](README.md).
Written 2026-09-18.

The question: how does a language design stop a defect from existing, rather
than finding it after the fact? Bend is the spine, because the user asked how
Bend "makes less problems programs"; the rest of the field is comparison.

**Not covered here.** Runtime sanitizers are in
[`docs/lang-safety/02-sanitizers.md`](../../../lang-safety/02-sanitizers.md)
(ASan, MSan, TSan, UBSan, CFI, `-fbounds-safety`) and hardware detection in
[`03-hardware.md`](../../../lang-safety/03-hardware.md) (MTE, CHERI). Those are
detection, and this report cites them rather than restating them. The
compile-time mechanism catalog — definite assignment, non-null types, affine
types, borrowing, regions, refinement and dependent types — is in
[`06-compile-time-safety.md`](../../../lang-safety/06-compile-time-safety.md),
whose section 15 already tables mechanism against *memory-safety* bug class.
This report's table is a different cut: a wider defect set (protocol errors,
logic errors against a specification, deadlock, performance cliffs) against
mechanisms that are not all type systems, each row carrying its cost and the
evidence that it works.

**Sources already in this repository, read first and not repeated.** Bend's
model with verbatim quotes is in
[`docs/lang-safety/comparative/bend.md`](../../../lang-safety/comparative/bend.md);
what A7 might take from it is in
[`docs/plan/research/bend-for-a7.md`](../bend-for-a7.md); the per-language
studies of Rust, Pony, Vale, Austral, Ada/SPARK, Cyclone, Hylo, Swift, Zig,
Mojo, Inko/Koka/Verona are in
[`docs/lang-safety/comparative/`](../../../lang-safety/comparative/), organized
by the twelve edge-case gaps rather than by defect class.

**One mark lifted.** `bend.md` marked `paper/BendTT.pdf` and `paper/BendRT.pdf`
UNVERIFIED because they had not been read. They were read for this report
(fetched at commit `08768a3` and converted with `pdftotext -layout`), and Part 1
quotes them. `bend.md` is not edited; this report supersedes that mark.

### The concepts, not the products

Per [`CONCEPTS.md`](../CONCEPTS.md), the subject is the mechanism, not anyone's
feature list. Bend, SPARK and the rest are evidence; the concepts they are
evidence for are these.

| Concept | How this report reaches it |
| --- | --- |
| **C12. Search with a verifier** | The organizing concept of the whole report. A proof obligation is a checker; who or what proposes the code is left open. Bend's `LAWS.bend`/`PROOF.bend` is propose-and-check with an agent as the proposer, and CONCEPTS states the rule this report confirms in detail: "The value lives in the checker, not the proposer." §1.1, §1.6, §3.2 and §3.3 are an extended study of what happens when the checker is strong and the specification is weak. |
| **C7. Staged evaluation** | Prevention that is computation, not argument. Bend's flagship proof does not reason about its map: `chk_all` enumerates every cell and the checker evaluates it to `True` (§1.2). Zig's `comptime` and Bend's `~` templates are the same move. The finding for A7 is in §3.4: a finite property is cheaper to *compute* at check time than to prove. |
| **C1. Reproducible execution** (prevention side) | Determinism as a precondition for any of this. Bend's benchmark discipline requires "every executor must print the pinned checksum" (§1.6), and the JS lane's divergence on `F32` NaN payloads is the counterexample the project files under OPEN. A checker that is a semi-decision procedure (BendTT §3.4) is reproducible only in its accepts, never in its hangs. |
| **C4. Resumable failure** | The negative space. Every design in Part 2 either prevents a fault or crashes on it; only Erlang/OTP treats the fault as a thing to survive, and it does so by *discarding* the frame rather than resuming it (§2, Armstrong). Bend is at the opposite pole: allocation failure, an unbalanced array tree, a `Nat` past 2^48 all "fail-stop" (§1.4), with no resumption and no condition to handle. Nothing in this report offers C4. |

**Agent value.** CONCEPTS weights agent value above human value, and that changes
what matters about a proof obligation. To a person, a discharged obligation is
an assurance: the program will not divide by zero. To an agent, the *undischarged*
obligation is the more useful artifact, because it is a machine-readable
statement of what the code must establish — a specification to work against, in
the same position as a failing test. Each mechanism below therefore carries an
"agent value" line saying what it hands an agent, which is not the same as what
it promises a reader.

---

## Part 1 — Bend

Source: the repository `HigherOrderCo/Bend` at commit
`08768a399807af1ce8877ce53ea06b633cb7bb22` (Apache-2.0, 21,369 stars, pushed
2026-09-18), read 2026-09-18 through `gh api`. File links below are blob URLs at
that commit. The site <https://bend-lang.com> was read the same day.

### 1.1 What `LAWS.bend` and `PROOF.bend` actually are

They are two ordinary Bend source files with a naming convention, plus one rule
in the CLI. There is no separate specification language, no solver and no proof
search.

The mechanism, from
[`guide/GUIDE.md`](https://github.com/HigherOrderCo/Bend/blob/08768a399807af1ce8877ce53ea06b633cb7bb22/guide/GUIDE.md)
(read 2026-09-18):

> By convention, a project keeps its laws in two files at its root. `LAWS.bend`
> imports the code and states the laws, each an open claim: the human writes it,
> the AI does not touch it. `PROOF.bend` imports `LAWS.bend` and proves each law
> with a def of the same name (`law sorted` is proven by `def Laws.sorted`): the
> AI writes it, along with the code. `bend PROOF.bend` is the gate: it fails
> while any law is open or false, and prints "All terms check." once every law
> holds. bend refuses a `PROOF.bend` that sits beside a `LAWS.bend` without
> importing it.

A `law` is a declaration with no body. `paper/BendTT.pdf` §2.1 gives its status
in the theory:

> A `law` declares a name at a closed type and a later `def` fills it. Until its
> fill a name is an axiom: it may appear in types and other dead positions, and
> live code may not consume it.

So the enforcement is entirely the type checker's. A law's statement is a type;
its proof is a definition of that type; an unfilled law is an axiom that live
code may not use. There is no tactic language:

> Bend has no tactics: a proposition is a type, and a proof is a def of that
> type. (`guide/GUIDE.md`)

**When the check runs.** At `bend PROOF.bend`, which is one pass of the same
bidirectional checker that checks every other file. There is no separate
verification phase and no SMT call. BendTT §1 describes the whole checker as
"one bidirectional pass [12] with a usage counter per binder, no unification,
one syntactic test per self-call, and a dead fragment that costs nothing and is
erased before the runtime."

**What happens on a violation.** Three distinct outcomes, and they are not
equivalent:

| State | What `bend PROOF.bend` does |
| --- | --- |
| A law has no `def` filling it | Fails: the law is an open claim |
| A law's `def` does not check | Fails, printing "the expected and observed terms" (GUIDE) |
| Any `def` is marked `@unsafe` | **Prints "All terms check, with N unsafe annotations." and exits 0** |

The third row is from
[`WONTFIX.txt`](https://github.com/HigherOrderCo/Bend/blob/08768a399807af1ce8877ce53ea06b633cb7bb22/WONTFIX.txt),
filed under DESIGN, and the project states it plainly:

> `@unsafe` programs check and exit 0 (#776, #805). The checker prints "All
> terms check, with N unsafe annotations." and exits 0. `@unsafe` is a choice
> the author made in the source; read the note, not the exit code.

That matters for the advertised workflow. The README's instruction to an agent
is "run `bend PROOF.bend` before committing", and a CI job that checks the exit
code alone cannot distinguish a proved program from an `@unsafe` one. The
information is on stdout, not in the status. `?TODO` — the other escape —
does fail, so the two hatches behave differently.

BendTT §3.4 claims the disclosure is complete:

> One escape hatch exists and is always disclosed. A definition marked
> `@unsafe` skips descent and forms its `+` binders at any kind; the checker
> reports every book that uses one, so a clean report means none of the claims
> above is waived.

**Agent value (C12).** This is the cleanest propose-and-check loop in the
report, and the reason is the checker's shape rather than the theory's power.
`LAWS.bend` is a specification an agent cannot edit; `PROOF.bend` is an artifact
it can regenerate without limit; the verdict is one command, and a failure
"prints the expected and observed terms" so the next attempt is informed rather
than blind. `?name` prints the open goal, which is a machine-readable statement
of what remains to be shown. Nothing here needs the program to run, so the loop
has no reproducibility problem (C1) and no test flake. The two defects in the
loop are that a green verdict does not distinguish a real law from a vacuous one
(§1.2), and that `@unsafe` makes the exit code lie — an agent driving this loop
on exit status alone can be satisfied by a program that proves nothing.

### 1.2 The demos: what a law looks like in practice

Four demos, read at the same commit, show the range.

**`demos/io_hello_world`** — the whole law and the whole proof:

```python
# LAWS.bend
law prints_hello:
  {Hello.main() == IO.print("Hello, world!") : IO(Unit)}

# PROOF.bend
def Laws.prints_hello():
  {==}
```

The proof is reflexivity. The law says the implementation equals itself written
out again. It is machine-checked, true, and carries no information: it restates
`main`. This is the clearest small example of the failure mode Part 3 calls the
proved-but-vacuous specification, and it ships as the project's first demo.

**`demos/app_win_is_bug_2d`** — the README's flagship, the game whose law is
"winning is impossible":

```python
law you_cant_win:
  for moves: List<Game.Move>
  board = Game.replay(Game.start(), moves)
  {Game.is_won(board) == False{} : Bool}
```

This one is real: it quantifies over every sequence of moves of every length.
The demo's own README states the stake — "If you ever see the win screen, the
type checker is broken. File a bug" — and the division of labor: "The human
maintains the wall; the machine does anything it wants on the other side of it,
except lie."

Two things about it are worth more than the headline. First, `LAWS.bend`
carries a *second* law, `never_on_flag`, with 50 lines of supporting definitions
that walk the drawn board looking for the character `'F'`. Its stated reason, in
the file's own comment, is that the first law does not bind what the screen
shows: "The board the page draws … and the page's reading of it: the character
at column x of row y, `'F'` where it draws the flag. Both laws bind exactly what
the page shows." **INFERENCE:** `you_cant_win` constrains `is_won`, a field of
the game state, so a program could leave that field `False` while putting the
player on the flag; the second law closes that gap. Either way, one law was not
enough for the property meant, and that is the specification-authoring problem
in miniature, inside the project's own showcase.

Second, the sizes:
[`main.bend`](https://github.com/HigherOrderCo/Bend/blob/08768a399807af1ce8877ce53ea06b633cb7bb22/demos/app_win_is_bug_2d/main.bend)
is 194 lines, `LAWS.bend` 68, and `PROOF.bend` 484 — 2.5 lines of proof per line
of program, for a game that fits on one screen. For
`demos/proof_insertion_sort` the ratio is 92 lines of code to 83 of proof, for
sorting a list.

**`demos/pure_par_sum`** — the law is that the parallel fork/join tree computes
the same number as a sequential loop `seq`, and `main.bend` labels `seq` with
`# spec for LAWS.bend only`. The specification is a second implementation. That
is a legitimate and common technique, and it is worth naming: the law does not
say what the sum is, it says two programs agree.

**`demos/proof_numerics`** — laws for commutativity, associativity, distribution
and Euclidean division on `Nat`, with `exs q: Nat` witnesses. These are
mathematical facts, not program properties, and they are what the machinery is
best at.

### 1.3 Defect classes the design removes, and by which mechanism

Each row states what a program would have to do to hit the defect anyway.

**Use-after-free and double-free — removed by affinity.**
"Bend, by default, is *affine*, meaning variables must be used, at most, once"
(GUIDE). There is no free operation to call twice: "Since values are affine, a
`match` frees the node it opens on the spot, and only `+` values carry a
reference count" (GUIDE, Under the Hood). *To hit it anyway:* you cannot from
the source language. The deallocation is compiled, not written. BendRT §5 states
the consequence — "a value has one owner, so a match frees its scrutinee as it
opens it, arrays update in place, and a forked task carries no lock" — and the
remaining exposure is the C runtime that implements it, which BendRT §12 says is
"unverified".

**Data races — removed by purity plus affinity.**
"A parallel call promises the compiler two things: 1. The calls are
independent. 2. They run in roughly the same time. Since Bend is pure and affine,
the first point always holds" (GUIDE). There is no shared mutable state to race
on, so the parallel annotation needs no analysis. *To hit it anyway:* use the
disclosed hatch — the README lists "Sharing arrays with atomics across threads
is experimental and needs `@unsafe`."

**Non-termination in live code — removed by the descent check.**
"Bend verifies termination by requiring recursive calls to use smaller parts of
their inputs, obtained through pattern matching. The check reads the arguments
of a recursive call from left to right: each must be passed unchanged until one
is a smaller part of its parameter, and the ones after it are free" (GUIDE).
The motive is soundness, not liveness: "Termination is mandatory and mutual
recursion is not allowed. Both restrictions keep Bend's proofs sound, as a
function that never returns could otherwise prove anything." *To hit it anyway:*
`@unsafe`, which "recurses freely, but falls outside Bend's proof guarantees" —
and which exits 0.

**Logical inconsistency from `Type : Type` — removed by the live/dead split.**
This is the design's cleverest move and the one most worth understanding.
Bend keeps `Type : Type` and drops the positivity check, both of which are
normally fatal, and recovers consistency from affinity alone:

> Bend's theory has one universe and no positivity check: `Type : Type` holds,
> and a datatype may recurse on the left of an arrow. What keeps this consistent
> is a wall between two checking modes. Code that runs is checked *live*; types,
> erased arguments and equations are checked *dead*. Dead code may loop forever
> or inhabit `Empty`, but nothing dead ever counts as live evidence, and live
> recursion must terminate. (GUIDE, Under the Hood)

BendTT §3.1 gives the mechanism concretely, and it is a single counter:

> Hurkens' paradox [17] is twenty definitions long in Bend and typechecks up to
> `tauinner`, the first place a function-typed variable is used twice; it dies
> there with `f (consumed more than once)`. Impredicativity and `Type : Type` do
> no harm on their own.

The classical paradoxes all copy a function; no function type is `Data`; only a
`Data` type may be copied. *To hit it anyway:* you would have to obtain `Data`
for something affine, and §3.3 is a list of the attempts and why each fails.

**Out-of-bounds array indexing — not removed. Defined away.**
"Indexes wrap around" (GUIDE). `a[5]` on a four-slot array reads slot 1. There
is no fault to prevent because there is no fault: the operation is total. This
is a legitimate design choice and it is *not* the same guarantee as a proof that
the index is in range — a program that computes the wrong index reads the wrong
element silently. The README's example law list includes "`array_set()` may
never be called out-of-bounds", which is a law a user would have to state and
prove themselves; nothing in the language requires it.

**Resource-handle misuse (double close, use after close, forged handle) —
removed by affinity on opaque types.**
"A handle (`File`, `Socket`, `Window`) is an affine, opaque value, so every
effect on one hands it back beside its result, and no program can forge or
reuse one" (GUIDE). The handle types are declared in
[`bend2/base.bend`](https://github.com/HigherOrderCo/Bend/blob/08768a399807af1ce8877ce53ea06b633cb7bb22/bend2/base.bend)
as unfilled laws (`law File:`, `law Socket:`, `law Listener:`, `law Window:`,
`law Audio:`, `law Chan:`), so there is no constructor. *To hit it anyway:* you
cannot from the source language.

**Anything else a user can state and prove.** The open-ended half. "Anything you
can spell can become a law" (README). Bounded by what the theory can express and
what someone is willing to prove.

### 1.4 What it does not remove

The README carries a 30-line limitations block and the project keeps a separate
`WONTFIX.txt`; both are unusually honest and are the starting point. What
follows adds the categories they do not name.

**Whatever the laws do not say.** This is the whole of it, and the hello-world
demo proves the point better than an argument would. A law is a claim someone
chose to write. The site says "Merging a bug is mathematically impossible: it is
a _theorem_" and "no AI can ship one line that breaks them, ever"
(<https://bend-lang.com>, read 2026-09-18) — both true *of the stated laws*, and
neither a statement about bugs. The demo that needed a second law
(`never_on_flag`) to close a gap in its first one is the project's own evidence.

**Anything about floating point.** "F32 is axiomatic: nothing about floating
point can be proven" (README). This is not a slogan; it is mechanical.
`base.bend` declares 43 laws that are never filled, of which 36 are `F32`
operations (`F32.add`, `F32.mul`, `F32.div`, `F32.sqrt`, `F32.sin`, the
comparisons, and so on) plus `U32.to_f32` and the six opaque handle types.
(Method: every `^law N:` in `base.bend` with no matching `^def N[(:]` in the
same file; counted 2026-09-18.) Live float code calls them: `F32.lerp` at line
1623 is an ordinary `def` whose body is `F32.add(a, F32.mul(F32.sub(b, a), t))`.
So every Bend program that touches a float — the ray tracer, the 3D demos,
nbody, mandelbrot — rests on 37 axioms with no proof content.

How live code may call an axiom at all is not stated in the guide, the
`WONTFIX` file or either paper; BendTT §2.1 says the opposite ("live code may
not consume it"). The mechanism is in the compiler:
[`bend2/comp.ts`](https://github.com/HigherOrderCo/Bend/blob/08768a399807af1ce8877ce53ea06b633cb7bb22/bend2/comp.ts)
carries a primitive table that emits C and JavaScript for each one —
`f32_add` becomes `f32_rewrap(f32_unbox($0) + f32_unbox($1))` in C and
`Math.fround($0 + $1)` in JS. **INFERENCE:** the unfilled `F32` laws are
compiler intrinsics, filled at code generation rather than by a Bend `def`, so
the type checker sees an axiom where the backend sees an instruction. That is
the cleanest statement of the float story: the checker knows nothing about
floats *because there is nothing there to know*.

A related qualification belongs here rather than in §1.3. BendTT §3.4 says the
affinity of handles and arrays — the thing that makes double-close
unrepresentable — "is a property of the base library, not a rule": "A type with
runtime ownership (a file, a socket, an array) is declared `Type`, never `Data`;
this is a property of the base library, not a rule." Nothing in the theory stops
a user declaring an owning type `Data`.

**What the theory admits but the runtime refuses.** `WONTFIX.txt` has a RUNTIME
section for exactly this — programs that check and then fail-stop:

> An unbalanced `Array` tree fail-stops at runtime (#808). `ALeaf`/`ANode` are
> public, so the checker admits a tree whose halves differ; every backend stores
> an array as one flat block and traps on such a node. A depth index would fix
> it in the type, but Bend does no inference, so `xs[i]` would have to become
> `xs[i^d]`; we chose not to.

> A Nat past 2^48-1, or an array past block class 31, fail-stops (#779).
> Immediates hold 48 bits; blocks have 32 classes. The theory has no such bound.

Allocation failure joins them: "Out of memory is fatal everywhere, not a `Fail`"
(#792). So a proved program can still die at run time, and the gap between the
theory and the machine is the project's own list.

**Deadlock is detected, not prevented.** "The program ends when every
computation is done, or reports a deadlock when the remaining ones all wait"
(GUIDE, IO and Concurrency). That is a runtime report.

**Performance.** Affinity buys data-race freedom without buying speed. The
balance obligation is stated in the language and checked by nobody — BendRT §12:
"The equal-parts contract is unverified: a skewed program silently loses its
parallelism." The README says the same in one line: "Parallelism requires
balanced calls."

**What an affine type system still permits.** Affinity is *use at most once*,
not *use exactly once*. Dropping a value is always free — GUIDE: "Affine
variables are the default, and dropping one is always free." So a program may
silently discard a result it should have used. A linear system (Austral, see
[`comparative/austral.md`](../../../lang-safety/comparative/austral.md)) would
reject that; Bend does not. Affinity also says nothing about *order*: it stops a
handle being used twice, not being used in the wrong sequence. A protocol
("open, then write, then close") is not enforced by affinity alone; it would
need a law, or typestate the language does not have.

**What `@unsafe` opens.** Termination and the kind restriction on `+` at once:
BendTT §3.4, "A definition marked `@unsafe` skips descent and forms its `+`
binders at any kind." Forming a `+` binder at any kind is the license the whole
consistency argument rests on (§3.3: "Every attack we know of tries to obtain
`Data` for something affine"). So `@unsafe` does not weaken one guarantee — it
suspends the argument for all of them, in that definition, and exits 0.

**The compiler itself.** The README, verbatim: "The compiler (not kernel) is 99%
AI-written and has not been fully audited yet" and "The Lean formalization and
bend.ts mismatch. Early consistency bugs may occur."

### 1.5 The cost side

**Verbosity, by design and for a stated reason.** "Bend does almost no
inference, meaning it requires more annotations than similar languages. This is
what allows Bend's checker to be significantly faster than other provers, and
its error messages more precise, at the expense of programs and proofs being
more verbose" (GUIDE). The README: "Everything is annotated and nothing is
inferred, so code is verbose."

**Proof effort, measured on the project's own demos.** 484 lines of proof for a
194-line game; 83 for a 92-line insertion sort. No tactics and no search: "Bend
has no tactics or proof search; proving theorems takes extra effort" (README).
Every rewrite is written out by hand with its motive — see the `%e : P` lines in
`demos/pure_par_sum/PROOF.bend`, where proving that a fork/join sum equals a
loop takes three lemmas and explicit associativity.

**What affinity costs the programmer.** BendTT §7 states it without hedging:

> What affinity takes away. Contraction on closures. The standard `map` is
> ill-typed: `f` is applied once per element, so it would need `+`, and no
> function type is `Data`. … the closure-heavy style of Haskell does not
> transfer.

`List.map` exists in Base as a *template* — a compile-time inlined `~f` argument
— not as a higher-order function. That is the workaround, and it means the
functional idiom most programmers reach for first is not available in the shape
they expect.

**The balanced-split requirement.** The runtime will not repair an unequal fork.
BendRT §6:

> The price is written into the language. Work stealing [2, 4] repairs an
> unequal split at run time; the cube does not. If a program forks unequal
> parts, lanes idle at the end of a work turn, and the runtime declines to
> correct that: balance is the program's job.

This is a performance cliff created by a safety mechanism: the same
single-owner-per-task discipline that removes locks removes work stealing.

**Strings.** "Strings are linked lists of characters, so text processing is
slow" (README), and on the JS lane deep folds overflow the host stack —
`WONTFIX.txt` SOON: "String.length over 100k chars, List.length over 200k
elements".

**No tooling.** "Error messages are terse; no debugger, profiler, formatter,
REPL or LSP" and "No editor support, no test framework and no documentation
beyond the guide" (README).

### 1.6 Evidence quality: what is measured and what is claimed

The distinction matters, because the marketing and the papers say different
things.

**Runtime performance — measured, narrowly.**
[`bench/runtime/_pin_/apple_m4.txt`](https://github.com/HigherOrderCo/Bend/blob/08768a399807af1ce8877ce53ea06b633cb7bb22/bench/runtime/_pin_/apple_m4.txt)
pins 16 benchmarks with columns for compile time, one CPU thread, parallel CPU,
and GPU (pin dated 2026-09-11). BendRT Table 1 adds the C comparison. Caveats,
all from the project's own text:

- One machine. "seconds on one Apple M4 Max (pin of 2026-08-31, commit
  `64fc4b7`)".
- The C baseline is a transliteration, not tuned C: "the hand-written C twin,
  one C function per Bend definition."
- One of two GPU lanes: "The Metal lane is measured; the CUDA lane is in the
  source and not measured here" (§12).
- Self-measured by the vendor, two runs per cell: "Each cell is a warm run then
  a timed run on an idle machine."

The paper's own summary is more modest than the README's. BendRT abstract: "the
sequential build runs within **0.8 to 1.5 times** the time of hand-written C."
The README says "as fast as hand-written C (single-core)". Those are not the
same claim, and the 1.5 end is a 50% loss. Similarly the paper reports the GPU
as bimodal — "Uniform work reaches 52 to 67 times the sequential build …
while divergent and skewed work loses to sixteen threads (n-queens, symbolic
regression)" — and credits itself for saying so: "the design stance is to report
the loss rather than tune the scheduler toward it."

**Checker performance — the comparison is not in the repository.** The README
shows a chart captioned "Checker benchmarks: Bend vs Isabelle, Agda, Lean, Rocq"
and claims Bend "checks, in under a second, files that other projects would take
minutes". `bench/checker/` does contain rival files (`main.agda`, `main.lean`,
`main.v`, `main.thy`) for each of five benchmarks. But
[`bench/checker/_pin_/apple_m4.txt`](https://github.com/HigherOrderCo/Bend/blob/08768a399807af1ce8877ce53ea06b633cb7bb22/bench/checker/_pin_/apple_m4.txt)
has a single `CHECKER` column, for Bend, and `gates/perf.ts` runs only
`bun bend2/main.ts main.bend` on those directories. **INFERENCE:** the rival
timings that produce the chart are generated elsewhere (`bend2/docs/gen_charts.ts`
per `AGENTS.md`) and are not reproducible from the pinned gate; the repository's
own gate measures Bend against its past self, at a 1.15x regression threshold
(`gates/perf.ts`: `const SLACK = 1.15`). The README concedes the thinness: "We
don't have as many benchmarks as we'd like yet, especially for the checker."

**`evals/` measures nothing yet.** Twenty `.bend` files graded `easy`, `firm`,
`hard`, `hell` and `cake`, each stating a problem, a `law`, and then a
`# solution` section that solves it — e.g. `hard.resource_certificate.bend`
asks for a proof that equal tree certificates identify equal trees. There is no
scoring harness in the tree. `gates/test.ts` runs `tests/`, and
`gates/repo.ts` says so explicitly: "evals/ is not counted: it is the models'
arena, not the repo's shape." So `evals/` is a prompt set, not a result. No
claim about how often a model succeeds can be sourced from this repository.

**The defect-prevention claim itself has no measurement at all.** There is no
study, no bug count, no before-and-after. The evidence offered is one demo where
a law blocks one class of change, and three animated GIFs. That is a
demonstration, not a measurement, and the report says so here because the site's
wording — "Merging a bug is mathematically impossible" — invites the other
reading.

**The papers are AI-written, and say so.** Both carry the same disclosure, which
this report quotes rather than paraphrases:

> AI Disclosure. Bend and BendTT were designed by the human author. This paper
> was written by Claude Fable 5.1 from the author's code and design choices, and
> reviewed by the author. The Lean mechanization was human-specified, AI-proven,
> and verified by a computer. Human paper soon™.

**The formal results, stated exactly.** BendTT §6 reports "about twenty thousand
lines, no `sorry`, no axiom declarations" in Lean 4, proving confluence, subject
reduction for weak reduction, and at the live demand progress, weak
normalization and consistency. The limitations are the part to carry forward,
verbatim from §7:

> The consistency result is syntactic, relative to Lean's own foundation, with
> no semantic model. The mechanization lags the shipped checker (Section 6).
> Equality is intensional, with no extensionality principle. And the theorems
> are about the calculus, not the code.

And BendRT §12: "The C runtime is unverified: the correctness argument is the
checksum discipline plus the type system's guarantees, and the companion paper's
theorems stop at the calculus."

Read together with the README's "The Lean formalization and bend.ts mismatch",
the honest summary is: a calculus is mechanized and the mechanization lags the
checker; the checker is 99% AI-written and unaudited; the runtime is unverified.
The guarantee a user gets is the checker's, and the checker's correctness is
the unproved link.

---

## Part 2 — the comparison

Each entry states what the design removes, what it costs, and the source. Where
this repository already holds a study, the entry cites it rather than repeating
it and adds only what the defect-class framing needs.

### Graded assurance: buy only the proof you need

*Evidence: SPARK Ada.*

Existing study:
[`comparative/ada.md`](../../../lang-safety/comparative/ada.md) and the
whole-language
[`ada-deep-dive.md`](../../../lang-safety/comparative/ada-deep-dive.md).

There are **five** assurance levels, not three. From the SPARK User's Guide §8.1
(<https://docs.adacore.com/spark2014-docs/html/ug/en/usage_scenarios.html>, read
2026-09-18):

> These can be divided into five easily remembered levels:
> Stone level - valid SPARK · Bronze level - initialization and correct data
> flow · Silver level - absence of run-time errors (AoRTE) · Gold level - proof
> of key integrity properties · Platinum level - full functional proof of
> requirements

The guidance is a cost ladder, and AdaCore's own advice is not to climb it all
the way:

> Platinum level is defined here for completeness, but it is seldom applicable
> due to the high cost of achieving it.

with Silver "as the default target for critical software (subject to costs and
limitations)", Gold "only for a subset of the code subject to specific key
integrity (safety/security) properties", and Platinum "only for those parts of
the code with the highest integrity constraints."

**What Silver removes.** "The goal of this level is to ensure that the program
does not raise an unexpected exception at run time. Among other things, this
guarantees that the control flow of the program cannot be circumvented by
exploiting a buffer overflow, or integer overflow." Plus the Bronze
guarantees: "no reads of uninitialized variables, no possible interference
between parameters and global variables, no unintended access to global
variables, and no infinite loop or recursion in functions."

**What it costs, in AdaCore's own words.** Three distinct costs, all stated in
the same guide:

1. *Annotation.* "Proof is, by construction, limited to local understanding of
   the code, which requires using sufficiently precise types of variables, and
   some preconditions and postconditions on subprograms to communicate relevant
   properties to their callers." Loops need explicit invariants.
2. *False alarms.* "The initial pass may require a substantial effort to resolve
   all false alarms, depending on the coding style adopted previously."
3. *Prover incompleteness.* "Even if a property is provable, automatic provers
   may nevertheless not be able to prove it, due to limitations of the heuristic
   techniques used in automatic provers. In practice, these limitations mostly
   show up on non-linear integer arithmetic (such as division and modulo) and
   floating-point arithmetic."

That third cost is the one worth carrying forward: the same two areas — integer
division and floats — where Bend gives up entirely (F32 axiomatic) and where A7
leaves gate G3 and G1 open.

**The residual is admitted, not hidden.** SPARK ships `pragma Annotate` to
justify an unproved check by hand. On Tokeneer, the NSA-commissioned
access-control system re-proved with SPARK 2014
(<https://www.adacore.com/blog/tokeneer-fully-verified-with-spark-2014>, read
2026-09-18): "we went from 234 unproved checks on Tokeneer code … down to 39
unproved but justified checks. The justification is important here: there are
limitations to GNATprove analysis, so it is expected that users must sometimes
step in and take responsibility for unproved checks."

The same post reports a seeded-defect experiment, which is the closest thing in
this report to a controlled test of prevention: "we have seeded four
vulnerabilities in the code, and reanalyzed it. The analysis of GNATprove
(either through flow analysis or proof) detected all four: an information leak,
a back door, a buffer overflow and an implementation flaw." Four seeded defects,
vendor-run, is weak evidence — but it is evidence, and more than Bend offers.

### Obligations discharged by a solver

*Evidence: Dafny.*

Dafny checks two kinds of obligation, and its manual names them (Dafny Reference
Manual §13.7.3, <https://dafny.org/latest/DafnyRef/DafnyRef>, read 2026-09-18):

> Well-formedness assertions: All the implicit requirements of native operation
> calls (such as indexing and asserting that divisiors are nonzero), `requires`
> clauses of function calls, explicit assertion expressions and `decreases`
> clauses at function call sites generate well-formedness assertions.
>
> Correctness assertions: All remaining assertions and clauses

So the obligation set A7 discharges internally — index in bounds, divisor
non-zero — is exactly Dafny's *well-formedness* half, and Dafny's second half is
what a user adds on top with `requires`, `ensures`, `invariant` and `decreases`.

**The cost is not annotation. It is brittleness.** Dafny's own manual has a
section titled "Debugging brittle verification":

> When evolving a Dafny codebase, it can sometimes occur that a proof obligation
> succeeds at first only for the prover to time out or report a potential error
> after minor, valid changes. We refer to such a proof obligation as brittle.
> This is ultimately due to decidability limitations in the form of automated
> reasoning that Dafny uses. The Z3 SMT solver that Dafny depends on attempts to
> efficiently search for proofs, but does so using both incomplete heuristics
> and a degree of randomness, with the result that it can sometimes fail to find
> a proof even when one exists (or continue searching forever).

The mitigation is a tool that re-runs each proof with different random seeds and
reports the variance: `dafny measure-complexity --iterations N`. This is the
characteristic failure of SMT-backed verification and it has no analogue in
Bend, whose checker has "no unification" and one syntactic descent test —
Bend trades expressiveness for a decision procedure that does not flake.

**Measured effort: IronFleet.** Hawblitzel et al., *IronFleet: Proving Practical
Distributed Systems Correct*, SOSP 2015
(<https://sigops.org/s/conferences/sosp/2015/current/2015-Monterey/250-hawblitzel-online.pdf>,
read 2026-09-18). Figure 12: 1,400 lines of specification, 5,114 of
implementation, **39,253 of proof**. The paper's own framing is favourable:

> At the implementation layer, our ratio of proof annotation to executable code
> is 3.6 to 1. We attribute this relatively low ratio to our proof-writing
> techniques … In total, developing the IronFleet methodology and applying it to
> build and verify two real systems required approximately 3.7 person-years.

And the payoff it claims: "except for unverified components like our C# client,
both IronRSL … as well as IronKV … worked the first time we ran them." Note the
assumptions, §2.5: "the spec for each system is trusted, as is the brief
main-event loop", "We assume the correctness of Dafny, the .NET compiler and
runtime, and the underlying Windows OS", "We also rely on the correctness of the
underlying hardware." Part 3 returns to what happened when someone tested those
assumptions.

### Proof that survives extraction to the shipping language

*Evidence: F\* and HACL\*.*

F* is a dependently typed language whose verified output is extracted to C.
The evidence that it reaches production is HACL*: Zinzindohoué, Bhargavan,
Protzenko and Beurdouche, *HACL\*: A Verified Modern Cryptographic Library*,
CCS 2017 (<https://eprint.iacr.org/2017/536.pdf>, read 2026-09-18):

> The F∗ source code for each cryptographic primitive is verified for memory
> safety, mitigations against timing side-channels, and functional correctness
> with respect to a succinct high-level specification of the primitive derived
> from its published standard. The translation from F∗ to C preserves these
> properties…

Three defect classes at once, and one of them — secret independence, i.e. no
branch or memory access depending on a secret — is a class no other design in
this report addresses at all. The measured cost is *performance*, and it is
small: "When compiled with GCC on 64-bit platforms, our primitives are as fast
as the fastest pure C implementations in OpenSSL and Libsodium … and between
1.1x-5.7x slower than the fastest hand-optimized vectorized assembly code in
SUPERCOP."

The proof effort is measured and it varies by an order of magnitude with the
mathematics involved (HACL* §8): "The proof-to-code ratio hovers around 2, and
each primitive took around one person-week" for Chacha20 and SHA2, while "Code
that involves bignums requires more advanced reasoning … The proof-to-code ratio
is up to 6, and verifying Poly1305, X25519 and Ed25519 took several
person-months." Its successor EverCrypt scales that up: "EverCrypt consists of
over 124K verified lines of specs, code, and proofs, and it produces over 29K
lines of C and 14K lines of assembly code", and "designing, specifying,
implementing, and verifying EverCrypt took three person-years, plus approximately
one person year spent on infrastructure" (*EverCrypt*, IEEE S&P 2020, read
2026-09-18). So about 2.9 verified lines per line of output, at four person-years
— the cheapest full-functional-proof ratio in this report, on the most favourable
problem shape.

**INFERENCE:** the reason HACL* is the field's best example of verification
paying for itself is the shape of the problem, not the tool. A cryptographic
primitive has a short, published, unambiguous specification that someone else
already wrote; the hard part of verification — knowing what to prove — is done
before the project starts. That condition does not hold for most software, and
it is exactly the condition Bend's `LAWS.bend` asks a user to satisfy for an
arbitrary application.

### Additive verification: nothing is removed from the language

*Evidence: Frama-C and ACSL.*

ACSL is a specification language written in C comments so that annotated source
still compiles: "we consider that specifications are given as annotations in
comments written directly in C source files, so that source files remain
compilable" (ACSL 1.24 manual §1.2, read 2026-09-18 via frama-c.com). Its
ancestry is stated plainly — Caduceus, then JML, then "the general
design-by-contract principle proposed by Bertrand Meyer, originally implemented
in the Eiffel language". The WP plugin discharges them: "This plug-in allows
proving that ACSL contracts are fulfilled for all possible executions of the
code. It is based on weakest-precondition calculus and relies on external
automated provers and proof assistants" — Alt-Ergo, Z3, CVC4, Coq, and anything
Why3 supports (<https://frama-c.com/fc-plugins/wp.html>, read 2026-09-18).

**The industrial figures, from an independent SME.** Frank Dordowsky (ESG
Elektroniksystem- und Logistik GmbH), "An experimental Study using ACSL and
Frama-C to formulate and verify Low-Level Requirements from a DO-178C compliant
Avionics Project", arXiv:1508.03894, 2015 (read 2026-09-18). ESG is a Frama-C
*user*, not its developer, which makes this the one genuinely independent
industrial datapoint in Part 2. The subject is real certified code: "The examples
in this study have been taken from the control software of a sensor that ESG has
developed as a central component of a pilot assistance system for a military
helicopter. The sensor control software has been developed in accordance with
DO-178B, level D and was accepted by the German military certification authority
WTD 61/ML in 2014."

The annotation cost, in the author's own words, is the headline:

> It should be noted that the amount of instrumentation in form of assertions and
> loop invariants is in the same order of magnitude as the size of the source
> code, or even exceeds it.

And the outcome on four functions (Table 1, "Verification Status of Temperature
Monitoring Functions"): `cbit_set_work_cond` 6 obligations, 5 valid;
`cbit_check_temperature` 22 scheduled, 17 valid, 5 unknown;
`acq_measure_temp` 237 scheduled, 221 valid, 1 unknown, **15 timed out**; and
`adc_read` not attempted at all —

> The WP plugin could not be executed on adc read because of the non-standard C
> statements in the source … We were able to explain all proof obligations for
> which a proof attempt failed except for the 15 proof obligations of
> acq measure temp that timed out. We were not able to conclude the analysis of
> the problem due to lack of time.

Four functions of a shipping avionics sensor: one unprovable because of
non-standard C, one with 15 obligations left timed out, and roughly a line of
annotation per line of code. That is what "contracts bolted onto C" costs when a
medium-sized company tries it on code that already exists — and it is a far more
honest picture than any vendor page in this report.

**What WP itself declines to support** is also documented, in the plugin manual's
§1.6 "Limitations & Roadmap" (read 2026-09-18), which grades each gap *easy*,
*medium* or *hard*: global invariants not implemented (easy); type invariants
requiring "new memory models and some memory region analysis" (hard). The
repository's notes record that the manual also lists statement contracts as
unsupported since Frama-C 23 "because of unsoundness bugs", `assigns` clauses as
"sound but incomplete", floats as incomplete and function pointers as restricted —
the same two weak spots (floats, and the places where a memory model has to be
chosen) that SPARK names.

The design point worth extracting: this is the only entry in Part 2 where the
verification is *additive*. Nothing is removed from the language, nothing is
rejected that C would accept, and an unannotated function is simply unproved.
That makes adoption incremental and makes the guarantee partial by default —
the opposite of Bend, where the language is restricted first and the laws are
the only optional part.

### Aliasing discipline, and the classes it cannot reach

*Evidence: Rust.*

Existing study: [`comparative/rust.md`](../../../lang-safety/comparative/rust.md)
walks the 12 gaps. What that file does not state is the negative space, which is
the part the question asks for, so it is sourced here directly.

**What is removed.** The Rust Reference's list of behaviors considered undefined
(<https://doc.rust-lang.org/reference/behavior-considered-undefined.html>, read
2026-09-18) names eleven items, the first four being data races; dangling or
misaligned access; out-of-bounds pointer arithmetic; and breaking the pointer
aliasing rules. The introduction is the load-bearing sentence:

> Rust code is incorrect if it exhibits any of the behaviors in the following
> list. This includes code within `unsafe` blocks and `unsafe` functions.
> `unsafe` only means that avoiding undefined behavior is on the programmer; it
> does not change anything about the fact that Rust programs must never cause
> undefined behavior.

**What is not removed — leaks.** Leaks are not on that list, and the Rustonomicon
says why, without hedging
(<https://doc.rust-lang.org/nomicon/leaking.html>, read 2026-09-18):

> Many people like to believe that Rust eliminates resource leaks. In practice,
> this is basically true. You would be surprised to see a Safe Rust program leak
> resources in an uncontrolled way. However from a theoretical perspective this
> is absolutely not the case, no matter how you look at it.

`mem::forget` is safe: "This function consumes the value it is passed _and then
doesn't run its destructor_", and "In the past `mem::forget` was marked as
unsafe as a sort of lint against using it … However this was generally
determined to be an untenable stance to take."

**What is not removed — deadlock and logic errors.** Neither appears on the
undefined-behavior list. A Rust program may deadlock on two mutexes, and a Rust
program may compute the wrong answer; the type system has nothing to say about
either. This is the general shape of ownership-based prevention: it removes the
classes that arise from *aliasing under mutation*, and it is silent on
everything that is a property of what the program computes.

### Typing the sharing versus removing the sharing

*Evidence: Pony, against Bend.*

Existing study: [`comparative/pony.md`](../../../lang-safety/comparative/pony.md),
which tables all six reference capabilities and their sendability.

The framing this report adds: Pony and Bend buy the same property — no data
races — by opposite routes. Pony *types the sharing*: six capabilities describe
what each reference may do and which may cross an actor boundary, so shared
mutable state exists and the type system says who may touch it. Bend *removes
the sharing*: values are affine and the language is pure, so "Since Bend is pure
and affine, the first point always holds" and no capability annotation is
needed. Pony pays in annotation and in a concept a programmer must learn; Bend
pays in expressiveness — no shared mutable structure at all, and the parallel
balance obligation moved onto the programmer instead.

### Tolerating the defect instead of preventing it

*Evidence: Erlang/OTP. This is the C4 pole of the report.*

This is the one entry in Part 2 that is not prevention, and it belongs here as
the alternative hypothesis: if defects cannot be removed, contain their blast
radius.

Joe Armstrong, *Making reliable distributed systems in the presence of software
errors*, PhD thesis, KTH, December 2003
(<https://erlang.org/download/armstrong_thesis_2003.pdf>, read 2026-09-18), §4.4:

> The philosophy is let some other process fix the error, but what does this
> mean for their code? The answer is let it crash. By this I mean that in the
> event of an error, then the program should just crash.

And the distinction the slogan usually loses, from the same section:

> exceptions occur when the run-time system does not know what to do. errors
> occur when the programmer doesn't know what to do.

So "let it crash" is not "do not handle errors"; it is "do not write code for
the case where you do not know what the code should do." Recovery is structural,
in the supervision tree (OTP design principles,
<https://www.erlang.org/doc/system/sup_princ.html>, read 2026-09-18), not in the
failing process.

**The evidence, and the problem with it.** The Erlang reliability claim most
often repeated is nine nines for the Ericsson AXD301, and it does not survive
contact with its own source. The origin is a slide in Armstrong's 2002
Lightweight Languages talk at MIT: "99.9999999% reliability (9 nines) (31 ms.
year!)" (<http://ll2.ai.mit.edu/talks/armstrong.pdf>).

Mats Cronqvist, who states on his slides that he was the AXD 301's system
architect and troubleshooter, devoted a 2010 Erlang Factory talk to it
(<https://www.erlang-factory.com/upload/presentations/243/ErlangFactorySFBay2010-MatsCronqvist.pdf>,
read 2026-09-18). His account, verbatim:

> The customer (British Telecom) claimed nine nines service availability
> integrated over about 5 node-years. As far as I know, no one in the AXD 301
> project claimed that this was normal, or even possible. For the record, Joe
> Armstrong was not part of the AXD 301 team.

> the claim is pretty bogus… there was much more C than Erlang in the system ·
> there were no restarts and no upgrades · the functionality was very well
> defined

> nevertheless… the system was very reliable · compared to similar systems, it
> was amazingly reliable · I have been unable to find any publicly available
> reference to this. An anecdote will have to do!

Report it that way: a customer availability figure over five node-years,
attributed to a mostly-C system, disowned by its own architect, and repeated for
two decades as a language benchmark. The underlying claim — that supervision
produced an unusually reliable system — is supported only by that architect's
anecdote, and he says so.

### Checks that exist in some builds and not others

*Evidence: Zig — and A7's own backend.*

Existing study: [`comparative/zig.md`](../../../lang-safety/comparative/zig.md),
which is load-bearing for A7 because Zig is A7's backend.

Zig removes very little at compile time and is explicit about where the checks
live. The language reference at 0.16.0 — the release A7 targets — states the four
modes (<https://ziglang.org/documentation/0.16.0/>, read 2026-09-18):

| `-Doptimize=` | Reference wording |
| --- | --- |
| `Debug` | "Optimizations off and safety on (default)" |
| `ReleaseSafe` | "Optimizations on and safety on" |
| `ReleaseFast` | "Optimizations on and safety off" |
| `ReleaseSmall` | "Size optimizations on and safety off" |

The master (post-0.16.0) reference has dropped the "Build Mode" section and
renamed the modes; its Illegal Behavior section carries the rule instead:

> Most Illegal Behavior is safety-checked. However, to facilitate optimizations,
> safety checks are disabled by default in the fast and small optimization
> modes. … When safety checks are disabled, Safety-Checked Illegal Behavior
> behaves like Unchecked Illegal Behavior; that is, any behavior may result from
> invoking it.

So Zig's answer to the defect classes A7 proves away is *detection, in two of
four build modes*. The relevance is direct and is spelled out in §3.4 below:
A7's release profile compiles with `-OReleaseFast`, which is the row where the
checks are gone.

Zig's genuine prevention is elsewhere and is not a type system: no default
allocator (every allocation names where it comes from), no hidden control flow,
mandatory error handling, and `comptime` in place of macros. Those remove a
class of *reasoning* failure rather than a class of runtime fault.

### Termination as the price of soundness

*Evidence: Idris 2.*

Idris 2's own documentation states both the guarantee and its limit
(<https://idris2.readthedocs.io/en/latest/tutorial/theorems.html>, read
2026-09-18). The guarantee:

> If we really want to trust our proofs, it is important that they are defined
> by total functions — that is, a function which is defined for all possible
> inputs and is guaranteed to terminate. Otherwise we could construct an element
> of the empty type, from which we could prove anything.

That is the same argument Bend's guide makes for its descent rule, word for
word in substance. The limit:

> Note the use of the word "possibly" — a totality check can never be certain due
> to the undecidability of the halting problem. The check is, therefore,
> conservative.

And a totality check is **off by default**: a function must be marked `total`
for its failure to be a compile error. Bend inverts this — termination is
mandatory and `@unsafe` opts out — which is the stricter default and, as §1.1
showed, still exits 0.

Idris 2's other relevance is that it implements Quantitative Type Theory, the
framework BendTT positions itself against: BendTT §1 says QTT makes ω the
ordinary binder and keeps the universe hierarchy, "Here 1 is the ordinary binder
and ω is a permission a type earns."

### Predicates attached to an existing type system

*Evidence: Liquid Haskell.*

LiquidHaskell is the "additive" position applied to a functional language:
"LiquidHaskell _(LH)_ refines Haskell's types with logical predicates that let
you enforce important properties at compile time"
(<https://ucsd-progsys.github.io/liquidhaskell/>, read 2026-09-18). The landing
page's own worked categories are partial functions (a `head` with no `Nil`
case), off-by-one and buffer overflow in array access, non-termination of
recursive functions, and user-stated invariants such as list ordering.

The design lesson for A7 is the *shape*, not the checks: a refinement is a
predicate attached to an existing type, discharged by a solver, and a function
with no refinement is simply checked as before. That is precisely the `requires`
fragment proposed as B1 in
[`bend-for-a7.md`](../bend-for-a7.md), and the reason that proposal insists on a
decidable fragment is Dafny's brittleness section above: the moment the
predicate language outruns the decision procedure, the compiler's answer becomes
a function of a random seed.

UNVERIFIED: no measured result for LiquidHaskell was obtained for this report —
the landing page carries no bug counts or annotation ratios, and the papers were
not read.

### A small trusted kernel everything else reduces to

*Evidence: Lean 4.*

"Lean is an open-source programming language and proof assistant that enables
correct, maintainable, and formally verified code" and "Lean's minimal trusted
kernel guarantees absolute correctness in mathematical proof, software and
hardware verification" (<https://lean-lang.org/about/>, read 2026-09-18). Mathlib
is "over a million lines of formalized mathematics".

Two things matter here for the Bend comparison. First, the *small trusted
kernel* is the standard architecture for a prover: everything elaborates down to
a core a human can audit. Bend has no such kernel — `bend2/bend.ts` is the
checker, the Lean file is a separate model of the calculus, and the README says
the two "mismatch". Second, the second "guarantees absolute correctness" clause
is a vendor sentence on a project home page, of the same kind as Bend's
"mathematically impossible"; the kernel guarantees that a proof term checks, not
that the theorem is the one you wanted.

Lean is also where Bend's own formalization lives, so the comparison is not
adversarial: BendTT §6 reports ~20,000 lines of Lean 4 with "no `sorry`, no
axiom declarations", and §7 admits the result is "relative to Lean's own
foundation."

### Verifying the design and never the code

*Evidence: TLA+ at AWS.*

TLA+ is the entry that changes the axis: it verifies a *design* before there is
code, and never looks at the code. The industrial evidence is unusually good.
Newcombe, Rath, Zhang, Munteanu, Brooker and Deardeuff, "Use of Formal Methods
at Amazon Web Services" (manuscript dated 2014-09-29 on Lamport's site;
published as "How Amazon Web Services Uses Formal Methods", CACM 58(4), April
2015, 66–73, DOI 10.1145/2699417). Both versions were read on 2026-09-18 — the
manuscript at <https://lamport.azurewebsites.net/tla/formal-methods-amazon.pdf>
and the published CACM article at
<https://cdn.amazon.science/67/f9/92733d574c11ba1a11bd08bfb8ae/how-amazon-web-services-uses-formal-methods.pdf>
(cacm.acm.org itself returns HTTP 403). **They differ editorially**, so the
quotations below are from the published CACM version unless marked. Its results
table, verbatim:

| System | Component | Line count (excl. comments) | Benefit |
| --- | --- | --- | --- |
| S3 | Fault-tolerant, low-level network algorithm | 804 PlusCal | "Found two bugs, then others in proposed optimizations" |
| S3 | Background redistribution of data | 645 PlusCal | "Found one bug, then another in the first proposed fix" |
| DynamoDB | Replication and group-membership system | 939 TLA+ | "Found three bugs requiring traces of up to 35 steps" |
| EBS | Volume management | 102 PlusCal | "Found three bugs" |
| Internal distributed lock manager | Lock-free data structure | 223 PlusCal | "Improved confidence though failed to find a liveness bug, as liveness not checked" |
| Internal distributed lock manager | Fault-tolerant replication-and-reconfiguration algorithm | 318 TLA+ | "Found one bug and verified an aggressive optimization" |

The summary claim:

> So far we have used TLA+ on 10 large complex real-world systems. In every case
> TLA+ has added significant value, either finding subtle bugs that we are sure
> we would not have found by other means, or giving us enough understanding and
> confidence to make aggressive performance optimizations without sacrificing
> correctness.

And the cost, which is the striking number: "Engineers from entry level to
Principal have been able to learn TLA+ from scratch and get useful results in 2
to 3 weeks." Specifications of a few hundred lines, against 3.7 person-years for
IronFleet and 20 person-years for seL4. **INFERENCE:** the ratio is explained by
what is being verified — a design abstraction that a person wrote to be checkable
— not by TLA+ being a better tool than Dafny or Isabelle.

Two honest limits from the same paper. One row of the table is a negative
result, reported as such: "Improved confidence though failed to find a liveness
bug, as liveness not checked."

And the authors answer the design/code question directly, which is the single
most useful sentence in this report for locating where TLA+ stops:

> On learning about TLA+, engineers usually ask, "How do we know that the
> executable code correctly implements the verified design?" The answer is we do
> not know.

(CACM 58(4); the 2014 manuscript reads "The answer is that we don't.") They do
not treat that as a defeat — the same paragraph argues formal methods still pay —
but it means TLA+ is, by construction, on the far side of the boundary that §3.3
says is where defects end up.

The paper also has a section titled "What Formal Specification Is Not Good For":

> We are concerned with two major classes of problems with large distributed
> systems: 1) bugs and operator errors that cause a departure from the logical
> intent of the system, and 2) surprising 'sustained emergent performance
> degradation' of complex systems that inevitably contain feedback loops. We
> know how to use formal specification to find the first class of problems.
> However, problems in the second category can cripple a system even though no
> logic bug is involved.

That is the sourced statement of the performance-cliff row in Part 3's table,
and it is a class that *no* design in this report prevents.

### Bounded search: counterexamples, not proofs

*Evidence: Alloy.*

"Alloy is a language for describing evolving structures and a tool for exploring
them", and "Alloy's tool, the Alloy Analyzer, is a solver that takes the
constraints of a model and finds structures that satisfy them"
(<https://alloytools.org/about.html>, read 2026-09-18). The analysis is finite:
"All alloy models are **bounded**: they must have a maximum possible size. If not
specified, the analyzer will assume that there may be up to three of each
top-level signature and any number of relations. This is called the **scope**"
(<https://alloy.readthedocs.io/en/latest/language/commands.html>, read
2026-09-18).

The consequence is stated by the project itself, in the FAQ entry comparing
Alloy to theorem provers (<https://alloytools.org/faq/how_does_the_alloy_analyzer_differ_from_theorem_provers.html>,
read 2026-09-18):

> The Alloy Analyzer's analysis is fully automatic, and when an assertion is
> found to be false, the Alloy Analyzer generates a counterexample. It's a
> "refuter" rather than a "prover". … If the Alloy Analyzer finds no
> counterexample, the assertion may still be invalid. But by picking a large
> enough scope, you can usually make this very unlikely.

The argument for why bounded search is useful anyway is Jackson's, and he is
careful about its status. Daniel Jackson, *Software Abstractions: Logic,
Language, and Analysis*, The MIT Press, first edition 2006, ISBN 0-262-10114-9,
§5.1.3 "The Small Scope Hypothesis" (pp. 141–144):

> Most flaws in models can be illustrated by small instances, since they arise
> from some shape being handled incorrectly, and whether the shape belongs to a
> large or small instance makes no difference. So if the analysis considers all
> small instances, most flaws will be revealed. This observation, which I call
> the small scope hypothesis, is the fundamental premise that underlies Alloy's
> analysis.

> Most bugs have small counterexamples.

And, in the Q&A that follows:

> Can you prove the small scope hypothesis? No—that's why I call it a
> hypothesis. It makes a claim about the assertions that arise in practice, not
> the space of all possible assertions. One can construct an invalid assertion
> whose smallest counterexample is just beyond any given scope. Fortunately,
> inadvertent errors are rarely so devious in practice. It's important to bear in
> mind, nevertheless, that instance finding is an incomplete analysis, and
> sometimes the scope needed to find a bug is larger than intuition would
> suggest.

That is the most honest sentence about coverage in this whole report, and it is
the author of the tool writing it. Note that the phrase does **not** appear on
alloytools.org or in the 2002 TOSEM paper, which states the same idea in other
words — "By its very nature, the analysis is not complete: a failure to find a
counterexample does not prove a theorem correct" (Jackson, "Alloy: A Lightweight
Object Modelling Notation", TOSEM 11(2), April 2002, 256–290, read 2026-09-18 via
the MIT Software Design Group PDF). The book is the reference of record for the
hypothesis; the copy where the wording was verified was a course-hosted PDF, not
an authorized distribution, so the book is cited and the URL is not.

One sourced practitioner judgement, from the AWS paper's evaluation of Alloy
before they chose TLA+: "we found that Alloy is not expressive enough for many
of our use cases. For instance, we could not find a practical way in Alloy to
represent rich data structures such as dynamic sequences containing nested
records with multiple fields." They attribute this to the analysis method, not
the model: "Alloy's limited expressivity appears to be a consequence of the
particular approach to analysis taken by the Alloy Analyzer tool."

---

## Part 3 — synthesis

### 3.1 Defect classes against mechanisms

The axis is deliberately not the one in
[`06-compile-time-safety.md`](../../../lang-safety/06-compile-time-safety.md)
§15, which maps memory-safety bug classes to type-system machinery. Here each
cell says *how a design answers the defect*, and the categories are:

- **Prevented** — the defect is unrepresentable, or rejected at compile time.
- **Defined away** — the operation is total; there is no fault, but a wrong
  value may propagate silently.
- **Detected** — a check at run time turns the defect into a controlled failure.
- **Tolerated** — the defect happens and the system is structured to survive it.
- **Unaddressed** — the design has nothing to say.

| Defect class | Bend | Rust | SPARK Silver/Gold | Dafny / F* | Erlang/OTP | Zig | A7 today |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Use-after-free, double-free | Prevented (affinity, no `free` in the source) | Prevented (ownership) | Prevented (SPARK 2018 ownership) | Prevented (no manual memory) | N/A (GC) | Unaddressed | Design in progress (memory plan) |
| Data races | Prevented (purity + affinity) | Prevented (`Send`/`Sync`) | Prevented (Ravenscar) | Prevented / verified | Prevented (no shared state) | Unaddressed | N/A (no concurrency; gate G7) |
| Integer overflow | Defined away for `U32`; `Nat` fail-stops past 2^48 | Detected in debug, wraps in release | Prevented (Silver AoRTE) | Prevented (proof obligation) | N/A (bignums) | Detected in `Debug`/`ReleaseSafe` | Defined away for `+ - *` (ledger L5); prover disabled |
| Division by zero | **Defined away** (`x/0 = 0`) | Detected (panic) | Prevented (Silver) | Prevented (well-formedness) | Tolerated (crash + supervisor) | Detected in safe modes | Prevented (`DIVISOR_NONZERO`) |
| Out-of-bounds indexing | **Defined away** (indexes wrap) | Detected (panic) or prevented via iterators | Prevented (Silver) | Prevented (well-formedness) | Tolerated | Detected in safe modes | Prevented (`INDEX_IN_BOUNDS`, `SLICE_IN_BOUNDS`) |
| Nil dereference | Prevented (no null) | Prevented (`Option`) | Prevented (Silver + ownership) | Prevented | Prevented (no null) | Prevented (optionals) + detected | Intended; **defective today** (SAF-1, SAF-2) |
| Resource leak / handle misuse | Double-use prevented (affine handles); *dropping* still allowed | **Not prevented** (`mem::forget` is safe) | Bronze flow analysis | Provable, if specified | Tolerated (process death frees) | Unaddressed (`defer` by convention) | Unaddressed |
| Protocol / state-machine error | Only if a law says so | Unaddressed (typestate is not in the language) | Gold ("transitions between states follow a specified safety automaton") | Provable, if specified | Tolerated (supervisor restarts to a known state) | Unaddressed | Unaddressed |
| Logic error against a specification | Prevented **for the properties stated in `LAWS.bend`** | Unaddressed | Platinum ("full functional proof of requirements"), "seldom applicable" | Prevented, for what is specified | Unaddressed | Unaddressed | Unaddressed |
| Concurrency deadlock | **Detected** at run time ("reports a deadlock") | Unaddressed (not undefined behavior) | Prevented under Ravenscar restrictions | Provable as a liveness property | Tolerated (timeouts, supervisors) | Unaddressed | N/A |
| Performance cliff | Unaddressed and *created* (unbalanced fork loses parallelism silently) | Unaddressed | Unaddressed | Unaddressed | Unaddressed | Unaddressed | Unaddressed |
| Allocation failure | Fail-stops ("fatal everywhere, not a `Fail`") | Aborts by default | Provable with bounded storage | Assumed away | Tolerated | Returned as an error value | Unaddressed |

The costs, per mechanism, in one line each:

| Mechanism | Cost, as its own documentation states it | Agent value: what it hands an agent |
| --- | --- | --- |
| Affinity / linearity (Bend, Austral, Rust's moves) | "the closure-heavy style of Haskell does not transfer" (BendTT §7); `map` needs a compile-time template | A rejection names the variable used twice — a local, mechanical fix with no search |
| Ownership + borrowing (Rust) | Lifetime discipline; a class of correct programs rejected (see [`rust.md`](../../../lang-safety/comparative/rust.md), "Where Rust accepts more programs") | Same: a borrow error is a located, repairable fact, not a behaviour to reproduce |
| Termination checking | Conservative by necessity — Idris: "a totality check can never be certain due to the undecidability of the halting problem" | Turns "does this loop?" from a test that may hang into a compile-time yes/no |
| Dependent types, no inference (Bend) | "Everything is annotated and nothing is inferred, so code is verbose"; 484 proof lines for a 194-line game | The goal is printable (`?name`) and the failure prints expected against observed — a propose-and-check loop with no runtime |
| Contracts + SMT (SPARK, Dafny, Frama-C) | False alarms, prover incompleteness on non-linear arithmetic and floats, and proof brittleness under a random seed | Strongest specification-as-input, weakest loop: a brittle proof fails on a reseed, so the agent cannot tell its edit from noise (violates C1) |
| Full functional proof (seL4, IronFleet, CompCert, F*) | 3.6:1 to 23:1 proof-to-code; CompCert is 76% proof by line; 3 to 20 person-years | Best-defined target, worst iteration cost; the ratios are the reason no agent loop runs here |
| Design-level model checking (TLA+) | Cheap (2–3 weeks to learn, hundreds of lines) but says nothing about the code | A counterexample trace is executable evidence, and the model is small enough to regenerate wholesale |
| Bounded model finding (Alloy) | Finds counterexamples within a scope; expressivity limits (AWS: "not expressive enough for many of our use cases") | Counterexample-shaped output is ideal input; the silent scope bound is the trap — no counterexample reads as success |
| Build-mode checks (Zig) | Zero compile-time cost, but "safety checks are disabled by default in the fast and small optimization modes" | Nothing at edit time; the signal only exists if the agent remembers to run the safe build |
| Supervision (Erlang) | Nothing is prevented; the cost is that partial failure is now a design problem you must solve everywhere | Near zero. A restart erases the state the agent needed (the C4 gap, stated) |

Two rows deserve emphasis because they are the report's most useful finding.

**"Defined away" is not prevention, and Bend uses it twice.** Bend's array
indexes "wrap around" (GUIDE), and `Nat.divmod(a, 0n)` returns `(0n, a)` in
`base.bend` with the U32 emitter in `comp.ts` matching
(`"((u32)($1) == 0 ? 0 : U32_BIN($0, /, $1))"`). So a Bend program that computes
a wrong index or divides by zero does not fault — it silently produces a wrong
number, and no law requires anyone to notice. A7 makes the opposite choice on
both (`INDEX_IN_BOUNDS`, `DIVISOR_NONZERO` at `a7/safety.py:177-185`) and the
*same* choice on `+ - *` overflow (ledger L5: "Ordinary `+`, `-` and `*` wrap,
as in Odin"). Totalizing an operation removes a crash and keeps the bug. It is a
legitimate trade, and it should be argued as one rather than counted as safety.

**The mechanisms are mostly orthogonal.** Nothing in the table prevents
everything, and the columns do not dominate each other: Rust prevents the row
Bend leaves to a law (nothing) and leaves the row SPARK Gold prevents (protocol
automata). The only column that addresses the logic-error row without a
person writing a specification is empty.

### 3.2 What is actually known about effectiveness

Sorted by evidence quality, strongest first. The pattern is worth stating up
front: **every measured result below is about memory safety or about
full functional verification of a small kernel. There is no measurement anywhere
in this report of the laws-and-proof approach Bend proposes.**

**Memory-safe languages reduce memory-safety vulnerabilities — strong,
longitudinal, first-party.** Google's Android team, in two posts three years
apart. 2022 (<https://security.googleblog.com/2022/12/memory-safe-languages-in-android-13.html>,
read 2026-09-18):

> From 2019 to 2022 the annual number of memory safety vulnerabilities dropped
> from 223 down to 85. … From 2019 to 2022 it has dropped from 76% down to 35%
> of Android's total vulnerabilities. 2022 is the first year where memory safety
> vulnerabilities do not represent a majority of Android's vulnerabilities.

> In Android 13, about 21% of all new native code (C/C++/Rust) is in Rust. …
> To date, there have been zero memory safety vulnerabilities discovered in
> Android's Rust code.

2024 (<https://security.googleblog.com/2024/09/eliminating-memory-safety-vulnerabilities-Android.html>,
read 2026-09-18): "Memory safety issues, which accounted for 76% of Android
vulnerabilities in 2019, and are currently 24% in 2024, well below the 70%
industry norm, and continuing to drop."

Google states the causal caveat itself — "While correlation doesn't necessarily
mean causation … Of course there may be other contributing factors or
alternative explanations" — and separately rules out the detection-based
explanation: they deployed Scudo, HWASAN, GWP-ASAN, KFENCE and more fuzzing over
the same period, and "these alone do not account for the large shift in
vulnerabilities that we're seeing, and other projects that have deployed these
technologies have not seen a major shift in their vulnerability composition."

The 70% baseline is Microsoft's. The primary source is Matt Miller's BlueHat IL
slide deck of February 2019, "Trends, challenges, and shifts in software
vulnerability mitigation", in Microsoft's own `MSRC-Security-Research` repository
(`presentations/2019_02_BlueHatIL/`, read 2026-09-18). The load-bearing caption,
on a chart of "% of memory safety vs. non-memory safety CVEs by patch year"
running from 2006:

> ~70% of the vulnerabilities addressed through a security update each year
> continue to be memory safety issues

The MSRC blog posts of July 2019 restate it — "the root cause of approximately
70% of security vulnerabilities that Microsoft fixes and assigns a CVE … are due
to memory safety issues. This is despite mitigations including intense code
review, training, static analysis, and more"
(msrc-blog.microsoft.com/2019/07/18/we-need-a-safer-systems-programming-language/,
read 2026-09-18 via the Internet Archive; the live MSRC URL now redirects to the
blog landing page). Two things are worth noting about the figure everyone cites:
it is a share of *Microsoft's* CVEs, not an industry census, and it is a
proportion, so on its own it says nothing about whether the absolute count was
rising or falling.

This is the single best evidence in the field that prevention beats detection,
and it is worth being precise about what it shows: a whole *class* removed by
language choice, measured over six years, on a codebase of hundreds of millions
of lines, by the party with the full vulnerability data. It says nothing about
logic errors — the same 2022 post notes the residual is "largely logic bugs".

**Verified compilation works, and the bugs are in the unverified part.** Yang,
Chen, Eide and Regehr, "Finding and Understanding Bugs in C Compilers", PLDI
2011 (<https://users.cs.utah.edu/~regehr/papers/pldi11-preprint.pdf>, read
2026-09-18). On CompCert:

> This bug and five others like it were in CompCert's unverified front-end code.

> The striking thing about our CompCert results is that the middle-end bugs we
> found in all other compilers are absent. As of early 2011, the
> under-development version of CompCert is the only compiler we have tested for
> which Csmith cannot find wrong-code errors. This is not for lack of trying: we
> have devoted about six CPU-years to the task. The apparent unbreakability of
> CompCert supports a strong argument that developing compiler optimizations
> within a proof framework, where safety checks are explicit and machine-checked,
> has tangible benefits for compiler users.

And the framing from their own introduction, which is the argument of this whole
section: "formal verification seldom provides end-to-end guarantees: 'details'
such as parsers, libraries, and file I/O usually remain in the trusted computing
base."

CompCert's own cost, from Xavier Leroy, "Formal verification of a realistic
compiler", CACM 52(7), July 2009, 107–115, DOI 10.1145/1538788.1538814 (author's
PDF at <https://xavierleroy.org/publi/compcert-CACM.pdf>, read 2026-09-18), §3.3:

> The whole Coq formalization and proof represents 42000 lines of Coq (excluding
> comments and blank lines) and approximately 3 person-years of work. Of these
> 42000 lines, 14% define the compilation algorithms implemented in CompCert, and
> 10% specify the semantics of the languages involved. The remaining 76%
> correspond to the correctness proof itself.

So three quarters of the artifact is proof, and the compiler and its semantics
together are a quarter — the cleanest single statement of the price in this
report. Leroy also names the architecture Bend lacks: "Internally, Coq builds
proof terms that are later re-checked by a small kernel verifier, thus generating
very high confidence in the validity of proofs."

**Verified distributed systems still had 16 bugs, none of them in the verified
part.** Fonseca, Zhang, Wang and Krishnamurthy, "An Empirical Study on the
Correctness of Formally Verified Distributed Systems", EuroSys 2017. Abstract,
verbatim:

> This paper thoroughly analyzes three state-of-the-art, formally verified
> implementations of distributed systems: IronFleet, Verdi, and Chapar. Through
> code review and testing, we found a total of 16 bugs, many of which produce
> serious consequences, including crashing servers, returning incorrect results
> to clients, and invalidating verification guarantees. These bugs were caused by
> violations of a wide-range of assumptions on which the verified components
> relied. Our results revealed that these assumptions referred to a small
> fraction of the trusted computing base, mostly at the interface of verified and
> unverified components.

The distribution matters more than the count. Finding 5:

> No protocol bugs were found in the verified systems. None of the bugs we found
> were due to mistakes in the implementation of distributed protocols (e.g.,
> Paxos, Raft), which are well known to be complex and difficult to implement
> correctly. Our results suggest that verification does improve the reliability
> of the verified components: all the bugs described in this section were located
> in the unverified shim layer code, in the unverified shim layer library (Bug
> C3), or in the shim layer runtime (Bug V8). In fact, we found no shim layer
> bugs in IronFleet, which is the system studied with fewest unverified
> components.

Two of the sixteen were specification bugs, and some were in the verification
tools themselves. The authors' own conclusion is not a rejection:

> Verified components can only fail, regarding verified properties, if developers
> introduce both an implementation bug and a verification bug (i.e., specification
> or verifier bug). Furthermore, those two bugs have to match … This extra level
> of redundancy helps explain why we did not find any protocol-level bugs in any
> of the verified prototypes analyzed, despite that such bugs are common even in
> mature unverified distributed systems.

**seL4: the cost, and the assumptions.** Klein et al., SOSP 2009
(<https://sigops.org/s/conferences/sosp/2009/papers/klein-sosp09.pdf>, read
2026-09-18). 8,700 lines of C and 600 of assembler; "The overall size of the
proof, including framework, libraries, and generated proofs … is 200,000 lines
of Isabelle script." Cost: "The cost of the proof is higher, in total about 20
py. This includes significant research and about 9 py invested in formal language
frameworks … The total effort for the seL4-specific proof was 11 py", against
2.2 person-years for the kernel itself. And the assumptions, in the abstract:
"We assume correctness of compiler, assembly code, and hardware."

**SPARK: three weak data points, none independent.** Tokeneer's residual after
re-proof — "39 unproved but justified checks" — and a vendor-run seeded-defect
experiment where GNATprove caught four of four (AdaCore, §2). The third is the
original NSA outcome, as recounted by Jones and Thomas, *The development and
deployment of formal methods in the UK* (arXiv:2006.06327v3, read 2026-09-18):

> The Tokeneer project was a success [BJW06] in that the NSA were unable to find
> any faults in the software, Praxis were able to train two NSA interns to extend
> the system, and the NSA said that the productivity of the Praxis team was the
> highest they had ever experienced but somehow this did not lead to sales of the
> SPARK toolset or to further NSA projects.

That is a stronger result than AdaCore's own — the customer could not find a
fault — but it is **not independent**: Martyn Thomas founded Praxis, the company
that built Tokeneer. Treat it as a well-documented practitioner account, not a
measurement.

**The proof-automation numbers, across twenty years and three real systems.**
Roderick Chapman and Florian Schanda, "Are We There Yet? 20 Years of Industrial
Theorem Proving with SPARK", ITP 2014
(<https://proteancode.com/keynote.pdf>, read 2026-09-18). Both authors were at
Altran UK — the former Praxis, which built these systems and sold SPARK — so this
is a peer-reviewed paper by the vendor, not an independent evaluation. The
figures are concrete and checkable, which is more than the marketing offers:

| Project | Size | Verification conditions | Discharged automatically |
| --- | --- | --- | --- |
| SHOLIS (1995, Def Stan 00-55 SIL4) | "about 27 kloc (logical) of SPARK code, 54 kloc of information-flow contracts, and 29 kloc of proof contracts" | "nearly 9000 VCs, of which 3100 were for functional and safety properties, and 5900 for type safety" | "6800 (75.5 %) … with the remaining 2200 being 'finished off' using the interactive Checker" |
| Tokeneer (NSA) | "only about 10 kloc logical" | 2623 | "2513 of those were proven automatically (95.8 %), with only 43 left to the Checker and 67 discharged by review" |
| iFACTS (NATS en-route air traffic) | "about 250 kloc logical lines of code"; 74k lines of SPARK contracts | 152,927 | "151026 (98.76 %) are proven entirely automatically … User-defined rules are used for another 1701 VCs, with only 200 proved 'by review'" |

Three things this settles that AdaCore's marketing does not.

*The annotation cost is a function of what you prove, and it is enormous at the
top.* SHOLIS carried 83 kloc of contracts against 27 kloc of code — three lines
of specification per line of program, all figures logical (derived from the
quoted counts). The paper's verdict on that experience is one sentence: "The
experience was painful."

*The largest deployment deliberately stops at Silver.* On iFACTS: "Proof
concentrates on type-safety, but not functional correctness, since the system has
stringent requirements for reliability and availability - in short, the software
must be proven 'crash proof'." Its contract burden is correspondingly far
lighter: 74k physical lines of SPARK contracts against 529k physical lines of
executable code, roughly one line of contract per seven of code (derived from
Figure 1's `wc -l` counts; the paper's 250 kloc for iFACTS is a *logical* count
and is not comparable to the 74k, so the two are not mixed here). The most
ambitious industrial SPARK project chose absence-of-run-time-errors over
functional proof, and its automation rate is the best of the three. That is the
§2 cost ladder, confirmed by the people who climbed it.

*Automation rose from 75.5% to 98.76% over two decades* — and the paper credits
the code as much as the prover: "the 'proof friendliness' of the code under
analysis … we were learning how to write provable programs, so we started to set
a goal for projects to 'hit' a particular level of automatic proof (e.g. 95 % of
VCs discharge automatically), making the proof a design-level challenge rather
than a retrospective slog."

**The defect-density figure, from the original project artefact.** The Tokeneer
report itself was located and read: *Tokeneer ID Station, EAL5 Demonstrator:
Summary Report*, S.P1229.81.1, Issue 1.1 Definitive, 19 August 2008, by David
Cooper and Janet Barnes of Praxis High Integrity Systems for the NSA (AdaCore's
copy is dead; read 2026-09-18 from the released project archive mirrored at
`github.com/martin-cs/Tokeneer`, `tokeneer/docs/81_1_Summary_Report/81_1.pdf`).
Its Executive Summary lists the project's key statistics verbatim:

> The TIS system's key statistics are:
> • lines of code: 9939
> • total effort (days): 260
> • productivity (lines of code per day, overall): 38
> • productivity (lines of code per day, coding phase): 203
> • defects (defects found post delivery per 1000 lines of code): currently zero,
>   however independent testing is ongoing.

That is the number the SPARK literature is usually pointing at, and three things
about it deserve saying. It is **zero defects per KLOC**, which is a remarkable
result for ~10,000 lines of security software. It is **Praxis's own report** —
Cooper and Barnes built the system — so it is vendor-side, though it is the
project deliverable rather than marketing. And the authors attach their own
caveat in the same breath: *"currently zero, however independent testing is
ongoing."* A defect count taken before independent testing finishes is a floor,
not a result, and the report says so.

The effort side is the more useful half: 9,939 lines in 260 person-days, 38 lines
per day overall against 203 during coding — so roughly four fifths of the effort
went somewhere other than writing code. That is the real price of Correctness by
Construction, stated by the people who charged it.

**The rest, from a Grok lookup — not read by this author, and labelled
accordingly.** A delegated deep-research run (grok-4.6, `tmp/ai/run_grok.sh`,
2026-09-19; the run hit its turn limit but produced a sourced report, preserved at
`tmp/ai/prevention-gaps3.md`) reached several sources this report could not. All
of the following is **UNVERIFIED**: the quotations are Grok's reading, not mine,
and no primary source below was opened by this author. Treat them as leads with
attached citations, not as evidence of the same standing as §3.2's other entries.

*Published SPARK defect densities exist, and every one of them is vendor-authored.*
Per the Grok lookup: MULTOS CA at 0.04 defects/KLOC, quoted from Hall and Chapman,
"Correctness by Construction: Developing a Commercial Secure System", *IEEE
Software* 19(1), 2002 — "In the year since acceptance, during which the system was
in productive use, we found four faults. … This rate, 0.04 defects per KLOC, is
far better than the industry average for new developments"; and SHOLIS at 0.22
defects per ksloc after ten years of service, from Croxford and Chapman,
*CrossTalk*, December 2005, and White, Matthews and Chapman, "Formal verification:
will the seedling ever flower?", 2017. Grok's own conclusion is the one that
matters here, and it matches this report's independent finding about Tokeneer:
"None of the published defects/KLOC figures … is attributed to an independent
evaluator; they are reported by Praxis/Altran authors who built the systems." It
also flags that SHOLIS is 27,000 SLOC in one paper and 42 ksloc in another, so the
two 0.22 figures may not measure the same thing. No defects/KLOC figure for iFACTS
was found in any source it reached.

*One comparison against C and Ada appears to be genuinely independent.* Per the
Grok lookup, A. German of QinetiQ, "Software static code analysis lessons
learned", *CrossTalk*, November 2003, reports a UK MoD retrospective IV&V of
military avionics: "the poorest language for safety-critical applications is C
with consistently high anomaly rates. The best language found is SPARK (Ada),
which consistently achieves one anomaly per 250 software lines of code" — Grok
reads its Table 1 as roughly 4 anomalies per KLOC for SPARK, 25 for average Ada,
and 26–167 for average C. Two cautions travel with it even second-hand: it counts
*static-analysis anomalies*, not operational defects after delivery, and
*CrossTalk* is an editorially reviewed defence-community magazine rather than a
peer-reviewed venue. UNVERIFIED.

**Resolved: the Woodcock Tokeneer claim.** Earlier revisions of this report
carried it as an unsourced rumour. Per the Grok lookup, which quotes the Springer
chapter page for Woodcock, Aydal and Chapman, "The Tokeneer Experiments" (2010),
the claim is **true but means something different from what it sounds like**:

> Our experiment uses a model-based testing technique that exploits formal methods
> and tools to discover nine anomalous scenarios.

and, from §17.5, the scenarios surface only outside the specified envelope — "it
is only when the test cases exercise system behaviour beyond the anticipated
operational envelope that the stories such as the ones given in the previous
sections are uncovered" — with §17.6 answering the obvious question directly:

> Is Tokeneer really secure? Of course it is! … But these are interesting
> scenarios nonetheless, and they have been overlooked both by the formal
> development and by system testing.

These are requirements-level and socio-technical scenarios — a door left unlocked
for its latch-unlock duration, a configuration file that silently reverts settings
to defaults — not failures of the SPARK proofs. That is the specification-scope
failure of §3.3 in its most literal form: the proofs held, the *model of what the
system must do* did not reach far enough, and a different technique aimed outside
the envelope found nine things nobody had looked for. It also undercuts the
zero-defects headline in the right way: the residual was zero *against the
specified envelope*. All UNVERIFIED — the chapter is paywalled and was not read
here.

**Still not read:** King, Hammond, Chapman and Pryor, *IEEE TSE* 26(8), 2000; the
German *CrossTalk* paper itself; the Springer chapter; Aydal's PhD thesis.

**The automation figure AdaCore publishes** belongs beside Chapman and Schanda's
measured ones, since it is a forecast rather than a measurement: "Typically, 95%
to 98% of run-time checks can be proved automatically, and the remaining checks
can be either verified with manual provers or justified by manual analysis"
(SPARK User's Guide §8, read 2026-09-18). The measured range across twenty years
was 75.5% to 98.76%, and the low end was the project that proved functional
correctness.

**Correction to an earlier note.** This report previously recorded as UNVERIFIED
a claim that Woodcock, Aydal and Chapman found defects in Tokeneer using
Alloy-generated robustness tests. It remains unread and unasserted — but note that
*The Tokeneer Experiments* (in *Reflections on the Work of C.A.R. Hoare*,
Springer 2010, 405–430) has **Rod Chapman as a co-author**, per Chapman and
Schanda's own reference [28]. So even if it does report defects, it is not the
independent evaluation this section is looking for.

**Frama-C: closed, in §2.** An independent industrial study was found and read —
Dordowsky's DO-178C avionics experiment at ESG — and it is reported there with its
annotation ratio and its timed-out obligations.

The "up to 98%" figure that circulates for WP is **not** what it appears to be.
Per the Grok lookup: "The homepage 98% figure is about VCs; CACM's 98.5% figure is
about 3315 functions in a cited avionics case, not VCs. The WP plug-in page …
does not state the 98% claim." This report does not cite the figure. UNVERIFIED,
and recorded only so the next reader does not chase it.

A first delegated lookup (GLM-5.3-flash, `tmp/glm/prevention-industrial-prompt.md`)
failed outright: its web-search backend returned `MCP error -429: Weekly/Monthly
Limit Exhausted`, so it produced no answer and nothing in this report comes from
it.

**TLA+ at AWS: bug counts, self-reported, no control.** Ten systems, the table in
§2 above, "either finding subtle bugs that we are sure we would not have found by
other means" — which is an engineering judgement, not a measurement, and the
authors present it as one.

**Erlang: anecdote, and a debunked headline number.** See §2. The insider's own
summary is "I have been unable to find any publicly available reference to this.
An anecdote will have to do!"

**Bend: nothing.** No study, no defect count, no before-and-after, no scored eval
run. `evals/` is a set of problems with solutions and no harness; `bench/` is a
performance regression gate against the project's own past times. The claim
"Merging a bug is mathematically impossible: it is a _theorem_" is a statement
about the laws a user wrote, presented as a statement about bugs. This is not a
criticism of the design — it is a young project and it says so — but the
evidence column is empty, and anyone weighing the approach should know that the
whole case rests on one game demo and an argument.

### 3.3 Where prevention beats detection, and where it does not

**Prevention wins when the defect class is definable without reference to what
the program is supposed to do.** Memory corruption, data races, use-after-free,
nil dereference: these are properties of *how* a program computes, and a type
system can be built to make them unrepresentable. The Android data is what this
looks like at scale. The economics are also one-sided — Google's 2024 post makes
the argument explicitly: detection "address[es] the symptoms of memory unsafety,
not the root cause. They typically require constant pressure to get teams to
fuzz, triage, and fix their findings, resulting in low coverage. Even when
applied thoroughly, fuzzing does not provide high assurance, as evidenced by
vulnerabilities found in extensively fuzzed code." Prevention is paid once, at
language-design time, and is then free forever. Detection is paid per run, per
team, per release, and never finishes.

**Prevention loses, or becomes something else, when the defect is a mismatch
with intent.** Here the mechanism cannot be built into the language, because the
language does not know the intent. Every design in Part 2 that addresses the
logic-error row does it the same way: a person writes the intent down, and the
machine checks the code against what was written. That relocates the problem
rather than solving it, and it creates three failure modes that the sources
document:

*The proved-but-vacuous specification.* Bend's own hello-world demo is the
cleanest example in this report: `{Hello.main() == IO.print("Hello, world!")}`,
proved by `{==}`. The law restates the implementation, so the proof is
reflexivity and the theorem's content is zero. Nothing in the toolchain
distinguishes this from `you_cant_win`. A mechanically checked law that says
nothing checks green.

*The proved-but-wrong specification.* Fonseca et al. found this empirically: "Two
of the sixteen found bugs were in the specification of the systems analyzed."
Bend's flagship demo shows the softer version — `you_cant_win` was not enough,
and a second law had to be added to bind what the screen shows. If the first law
had shipped alone, the program would have been proved correct against a property
that was not the one the user cared about. IronFleet's answer is to keep the
specification tiny and auditable — "the high-level trusted specification for
IronRSL is only 85 SLOC … making them easy to inspect for correctness" — which is
an admission that specification review is a human process that does not scale.

The general form of this failure is old enough to be folklore among practitioners.
Jones and Thomas, writing a history of UK formal methods deployment
(arXiv:2006.06327v3, read 2026-09-18), put it in one sentence:

> There are numerous stories of formal machine-checked proofs that do not actually
> capture what the user intended to establish.

They draw a conclusion from it that bears directly on Bend: "the real payoff of
formal methods comes from their use early in the design phase", and about theorem
provers specifically, "their modes of interaction distract from thinking about the
application in hand." Bend's answer to that second objection is genuinely novel —
if an agent writes the proof, the interaction cost falls on the machine, and the
human writes only the law. Whether that shifts the first objection is untested:
nobody has measured whether a person writing `LAWS.bend` states the property they
meant more often than a person writing a Dafny `ensures`.

*The boundary.* This is the best-evidenced failure in the whole report, and three
independent studies say the same thing. Csmith found bugs only in CompCert's
unverified front end. Fonseca found every one of the 11 shim-layer bugs at "the
interface of verified and unverified components", and *zero* in the verified
protocol logic. seL4 assumes the compiler, the assembler, the hardware and (per
the project FAQ) that DMA is off. The rule this yields: **verification does not
reduce the defect count so much as relocate it to the boundary**, and the
boundary is where nobody is looking, because the proof's green light covers the
part that was already the most carefully written.

Bend has exactly this boundary and it is visible in its own flagship demo: the
game is proved unwinnable over `List<Game.Move>`, and the mapping from a keypress
to a `Move` lives in `web/main.js`, outside the theory. The demo's README says
"The browser never decides anything", which is the right design response; it is
also an unverified assumption of precisely the kind Fonseca et al. catalogued.
Bend's other boundaries: the 37 axiomatic `F32` intrinsics, the `@unsafe` hatch
that exits 0, the C runtime that BendRT §12 calls "unverified", and the 99%
AI-written checker.

**The cost of proof is real and is the reason the field has not converged.** The
numbers in one place: seL4, 23 lines of proof per line of C and 20 person-years;
CompCert, 42,000 lines of Coq of which 76% is the correctness proof, and about 3
person-years; IronFleet, 3.6:1 and 3.7 person-years; Bend's own demos, 2.5:1 for a
194-line game with no tactics and no search. Against that, TLA+ at AWS — a few hundred
lines, two to three weeks to learn, six real bugs in production systems. The
cheapest verification in this report is the one that does not look at the code.
**INFERENCE:** that ordering is not a fact about tool quality; it is that
verifying an abstraction a person wrote to be verifiable is a fundamentally
smaller problem than verifying an implementation someone wrote to be fast.

**What nobody prevents.** The performance-cliff row is empty across the table,
and AWS names it as the class their methods do not reach: "problems in the second
category can cripple a system even though no logic bug is involved … from the
customer's perspective it is effectively unavailable due to sustained
unacceptable response times." Bend is worse than neutral here: its safety
mechanism *creates* such a cliff, since the contention-free scheduler will not
repair an unbalanced fork and "a skewed program silently loses its parallelism."

**The honest position.** Prevention and detection are not competitors for the
same budget. Prevention removes classes; detection covers the boundary that
prevention creates. Fonseca et al.'s own recommendation is to test the shim
layer specifically, and the 2011 Csmith paper's is that "a verified compiler is
only as good as its specification … testing is still needed." A project that
adopts a prevention mechanism and then retires its testing has moved its defects,
not removed them.

### 3.4 For A7

What A7 already has, cited to the repository rather than to the plan.

**A fixed, internal obligation set — eight kinds, three of them inert.**
`a7/safety.py:177-185` declares `CAST`, `DIVISOR_NONZERO`, `INDEX_IN_BOUNDS`,
`SLICE_IN_BOUNDS`, `REF_NON_NIL`, `INTEGER_OVERFLOW`, `UNION_FIELD` and
`MOVE_VALID`. That is twice the four that
[`bend.md`](../../../lang-safety/comparative/bend.md) and
[`bend-for-a7.md`](../bend-for-a7.md) list; those documents lag the code. But the
count overstates the coverage:

- `UNION_FIELD` has **no producer**: `grep -c "ObligationKind.UNION_FIELD"
  a7/safety.py` returns 0 outside the enum. It is an obligation in name only.
- `INTEGER_OVERFLOW` has a producer that cannot run. `_prove_integer_overflow`
  (`a7/safety.py:630`) begins with a comment and an unconditional `return`;
  everything below it, including the `_obligation(...)` call, is dead code. The
  comment says so: "Overflow policy is represented in the obligation model, but
  full range-safe arithmetic is intentionally left for a dedicated follow-up."
- `REF_NON_NIL` exists and is defeated at the call boundary: SAF-1 (CRITICAL) in
  `docs/audits/2026-09-16/compiler/safety.md:68` — "On function entry every
  parameter whose type node is `TYPE_POINTER` (`ref T`) gets `non_nil=True`;
  callers are never asked to pass a non-nil value. Passing `nil` or a nil `ref`
  local builds, and the callee writes through null."

So A7's position in the §3.1 table is aspirational in three of eight rows, and
this report's contribution is the count: **the obligation ledger proposed as B2
in [`bend-for-a7.md`](../bend-for-a7.md) would have caught all three**, because
an obligation with no producer and an obligation whose prover returns early are
both visible in a dump and invisible in the current design.

**No escape hatch.** There is no `@unsafe`, no `unsafe` block, no suppression
pragma in A7. A grep of `a7/` for `unsafe`, `@allow` and `suppress` finds only
`UNSAFE_CAST` (a diagnostic code) and a parser flag. That is a genuine strength
and it is the direct opposite of Bend's most awkward property — a Bend program
with `@unsafe` prints "All terms check" and exits 0. A7 has no way for a program
to claim a proof it does not have.

**Source recursion is banned, and the ban is a backend consequence.**
`docs/SPEC.md` §6.2: "Recursion is not part of A7. A function may not call
itself directly, and groups of functions may not call each other in a cycle."
Bend allows live recursion and proves termination, but compiles it away — "each
def compiles to a segment of a flat state machine, a call is a jump". A7 emits
Zig and inherits the host stack. [`bend-for-a7.md`](../bend-for-a7.md) B5 already
records this; nothing here changes it.

**Release builds have no runtime backstop, by design.**
`scripts/build_examples.py:18-25` sets `debug` to `-ODebug` and `release` to
`-OReleaseFast`. Per §2's Zig table, `ReleaseFast` is "Optimizations on and
safety off", and Zig's master reference adds that with checks off,
"Safety-Checked Illegal Behavior behaves like Unchecked Illegal Behavior; that
is, any behavior may result from invoking it." The codegen contract intends
exactly this —
[`comparative/zig.md`](../../../lang-safety/comparative/zig.md): "A7 must emit
Zig that is safe without Zig's runtime safety checks." The consequence for the
§3.1 table: A7's debug profile is *prevention plus inherited detection*, and its
release profile is *prevention alone*. Every gap in the obligation set above is
therefore a release-mode gap, and SAF-1's probe already shows both A7 and Zig
exiting 0 on a program that writes through null.

**Fail-closed, precisely.** `a7/compile.py:246-260`: a module resolution failure
raises `SemanticError`, is collected into `import_errors`, and suppresses the
combined-AST step for codegen modes. But a *successful* local import is combined
into one AST and does reach codegen
(`_combined_program_for_file_modules`), which matches `docs/STATUS.md` ("File-backed
imports target one combined Zig output file") and not `CLAUDE.md`'s wording that
local imports "currently fail closed before codegen". **That line in `CLAUDE.md`
is stale**; the fail-closed behavior is on resolution failure, not on local
imports as such. Flagged, not fixed — this report changes only its own file.

**What A7 could adopt, at what cost.**

| Mechanism | Cost for A7 | Verdict |
| --- | --- | --- |
| An obligation ledger and a `--mode obligations` dump | Compiler plumbing, no language change | **Take it.** Already B2; this report adds three concrete defects it would have surfaced |
| User-stated preconditions over a decidable fragment | New syntax, call-site facts, an approval packet | Already B1. The Dafny brittleness section is the reason to keep the fragment decidable rather than call a solver |
| Gold-level state-machine properties ("transitions follow a specified safety automaton") | Needs B1 first, then a typestate or invariant surface | Worth recording as the natural extension once B1 exists; nothing in A7 addresses the protocol row today |
| Design-level model checking (TLA+ on A7's own compiler passes) | No language change at all; cheapest item in this report | **Under-considered.** A7 has a pipeline with ordering invariants and a safety pass whose obligations must reach the backend; that is the shape TLA+ is good at, and AWS's cost was 2–3 weeks |
| Full functional verification of the compiler (CompCert-style) | 3.6:1 to 23:1 proof-to-code, years | Out of scope. The NOREC and audit program is the affordable version |
| A `@unsafe`-style escape | None; A7 does not have one | **Do not add it.** Bend's exits 0 |

**What is incompatible with A7's design.**

- *Affinity as the consistency argument.* BendTT buys `Type : Type` with
  affinity. A7 has no dependent types to make consistent, and
  [`bend-for-a7.md`](../bend-for-a7.md) already rejects this.
- *Removing inference for checker speed.* Stated there too, and unchanged.
- *"Defined away" as a safety answer where a proof already exists.* A7 has taken
  this route once, deliberately (L5, wrapping `+ - *`). It should not be extended
  to division, shifts or narrowing casts — gate G3 — without the argument being
  made explicitly, because Bend shows where it ends: an index that wraps and a
  division that returns zero look like safety and are not.
- *Floats.* Bend's answer is to prove nothing about them (37 axioms). A7's ledger
  L16 takes the opposite line — IEEE 754 values, strict arithmetic by default —
  with the sub-decisions in gate G1. A7 cannot copy Bend here: a language whose
  stated target includes tensor operations and training (L7, L11) cannot declare
  its float semantics unprovable.

**The finding that matters most for A7.** The three studies in §3.2 that examined
real verified systems — Csmith on CompCert, Fonseca on IronFleet/Verdi/Chapar,
and seL4's own assumption list — all reach the same conclusion: the verified core
holds, and the defects move to the boundary with unverified code. A7's boundary
is the emitted Zig, compiled at `-OReleaseFast` with every check removed, and its
own audits already show that boundary failing in the way the literature predicts
(SAF-1 and SAF-2: a proof the pass believes, an emission the backend trusts, and
a program that writes through null with both exit codes at 0). The lesson is not
to prove more. It is to make the boundary explicit and to test it specifically —
which is what Fonseca et al. recommended after finding eleven bugs there, and
what B2's obligation ledger would make possible.

---

## Sources and method

All fetched material is preserved under `tmp/research/prevention/`, one
directory per system, each source block carrying its URL and the date read. Bend
was read through `gh api` at commit `08768a399807af1ce8877ce53ea06b633cb7bb22`;
`paper/BendTT.pdf` and `paper/BendRT.pdf` were converted with `pdftotext
-layout` and are quoted from that text, so column-interleaving artifacts were
checked by eye against the surrounding paragraph before any quotation was used.
A7 facts are read from the working tree, not from the plan documents, and the
two places where a plan document lags the code are flagged in §3.4.

Two provenance warnings about the preserved material itself:

- `tlaplus/notes.txt` and `alloy/notes.txt` were opened in `w` mode by a fetching
  agent while a sibling agent was working in the same directories. Earlier
  content in those two files may have been overwritten and is unrecoverable. The
  quotations this report draws from them were re-read in the surviving text
  before use, but the files are not a complete record of what was fetched.
- Jackson's 2019 *Communications of the ACM* Alloy overview was unreachable
  (HTTP 403, ACM bot challenge), as was the CACM page for the AWS paper; the
  published AWS article was obtained from Amazon Science instead, and the small
  scope hypothesis was verified in a course-hosted copy of Jackson's book rather
  than an authorized one (the MIT Press edition is what this report cites).

**Delegated lookups.** Three were run and they are not equal in standing. A
GLM-5.3-flash run failed on a provider quota error and contributed nothing. A
grok-4.6 run (`tmp/ai/run_grok.sh`, 2026-09-19, output preserved at
`tmp/ai/prevention-gaps3.md`) hit its turn limit but returned a sourced report;
everything taken from it is labelled a Grok lookup and marked UNVERIFIED at the
point of use, and nothing from it appears in §3.1's table. A fetching subagent
retrieved primary sources which **this author then read directly** — the Tokeneer
EAL5 Summary Report, the Dordowsky avionics study, the WP manual, the EverCrypt
and HACL* effort figures; those are cited normally, not as a delegated lookup.

Gaps, stated rather than papered over:

- No **independent** defect-density figure for SPARK was read by this author. Every
  published figure located is authored by the system's builder (Praxis/Altran);
  the one apparently independent comparison, German's *CrossTalk* 2003 avionics
  study, is known only through the Grok lookup and is marked UNVERIFIED (§3.2).
- Liquid Haskell has no measured result here; only its landing page was read.
- Bend's `bend2/bend.ts` (the checker) was not read; claims about how checking
  works come from the guide and the papers, except the `F32` intrinsic table,
  which was read in `bend2/comp.ts`.
- No program in any language discussed here was compiled or run for this report.

claims checked: 162 (49 block quotations and 82 inline quotations, each matched
against a file fetched to `tmp/research/prevention/` on 2026-09-18 or 2026-09-19;
12 A7 source and audit citations read in the working tree; 19 derived counts and
ratios — proof-to-code line counts, the SHOLIS and iFACTS contract ratios, the 43
unfilled `base.bend` laws, the zero-producer grep for `UNION_FIELD`, the
build-profile flags — recomputed from those files. The file also carries about
ten further quotations attributed to the Grok lookup; those are **excluded** from
this count, are marked UNVERIFIED in place, and were not checked against a primary
source by this author.)
