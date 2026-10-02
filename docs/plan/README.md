# A7 v1 plan

Started 2026-09-15. This document describes the v1 direction and proposed gates.
The decision ledger records locked directions; the execution plan records work
order and batch dispositions. Neither implies approval for an unapproved behavior
change or evidence that a planned feature has shipped. Current behavior is in
[Status](../STATUS.md) and the [safety contract](../SAFETY_CONTRACT.md). User
decisions are in the [ledger](decisions.md); evidence is in
[research](research/README.md). Memory management has its own
[memory plan](memory.md). What has been audited, what has not, and what the
language still lacks are in the
[language audit checklist](audit/language-audit-checklist.md); findings with no
owner are in [open items](audit/open-items.md).

## Where things go

- Todos: `delivery-roadmap.md` and `../STATUS.md` only. No TODO lists in
  chat logs, handoffs, or scratch files.
- Decisions: `decisions.md`, one row per choice with user words quoted.
  Research never counts as approval.
- Session handoffs: `HANDOFF-<date>.md` in this directory, dated and frozen
  once written. Never back-edit a handoff; new facts go in the ledger.
- Notes and scratch: `tmp/<topic>-YYYY-MM-DD/` directories. Never add loose
  top-level `tmp/` files. Never move or delete a `tmp/` path cited by docs.
- Advisory research: `research/`. It informs gates; it approves nothing.

## Summary

V1 is the core language under L36-L45: a qualified Python compiler, consistent
numeric semantics, automatic memory management, errors and collections, useful
libraries and installed tooling. Zig handles generated programs, native
integration, runtime support, builds and linking. Linux x86-64 is the first
qualification target. V2 aims to implement the compiler in A7.

AI, concurrency, multicore and GPU execution remain design constraints and later
qualification tracks. They no longer block core V1. Runtime memory help and
runtime safety checks are allowed, with compile-time analysis preferred. The
[delivery roadmap](delivery-roadmap.md) controls current ordering; older track
names and observations below are historical planning material until revalidated.

## Direction

The ledger holds the exact wording and scope limits. In short:

- Integers have explicit widths only: `i8`–`i64`, `u8`–`u64`, `isize`, `usize`.
  `usize` stays the index and size type. There is no `number`, `int` or `uint`
  (L3, L4).
- Integer `+`, `-` and `*` wrap, including compound assignment (L5).
- Floats follow Zig and C IEEE behavior (L16). Scalars are `f32` and `f64`; tensor
  formats add `f16` and `bf16` (L11).
- Argument bindings are immutable. Changing referenced data needs explicit
  permission, and no new permission syntax is approved (L6).
- Memory is automatic and invisible to users. Static analysis is preferred;
  runtime help is allowed. Each required workload must meet L38's 1.10-times
  runtime and peak-live-memory limits (L37-L39).
- Future AI covers tensor operations, inference, training and language foundations, on
  the CPU first with an interface for later accelerators (L7, L8).
- A7 owns tensor semantics, autodiff, optimizer state, RNG and checkpoints.
  Established libraries provide numerical kernels (L9).
- Later AI acceptance workloads are a small image classifier and a small decoder
  transformer, including checkpoint recovery (L10).
- Existing rules continue: no A7 source recursion, no public address-of or
  dereference operators, no `new [N]T`, no package registry.
- Documented breaking changes are allowed only through the approval rule (L2).
  GLM performs cybersecurity reviews (L12).

## Approval gates

Each gate needs a user decision in the ledger before dependent work starts.
Blocks marked **Current A7** use today's syntax; each states what was observed and
how. Blocks marked **Proposed syntax** are not supported and must not appear as
working code in examples, the README or public docs. All observations are
compile-only unless stated; no program was run.

### G1. Floating-point details

L16 sets the direction: IEEE values, strict by default, result-changing
optimizations only by opt-in. Zig's default float mode is strict. Its optimized
mode permits reassociation, contraction and disregard for signed zero and
non-finite values.

Current behavior contradicts L16. SPEC labels floats as IEEE, but floating
division uses the integer divisor proof:

```a7
// Current A7.
zero: f64 = 0.0
ratio := zero / zero
```

Observed 2026-09-15 in this tree: compilation fails with exit 6,
"division/modulo divisor must be non-zero". Under L16, `ratio` is NaN and
`math.is_nan(ratio)` is true.

Options considered before L16:

| Option | Result of `ratio` | Consequence |
| --- | --- | --- |
| Strict IEEE with checks (recommended, chosen by L16) | NaN; `math.is_nan(ratio)` is true | Supports f16 loss-scaling recovery. Float guards cannot prove finiteness |
| Finite-only, as earlier research promised | Compile error unless proved, or a fallible operation | Every kernel, cast, parse and intermediate result needs checks. Attention masking needs a separate definition |

Both framework reviews recommended IEEE values, strict behavior in every build
profile, no fast math by default, and `is_finite`, `is_nan` and `is_inf`
predicates.

Still to decide:

- whether v1 offers an opt-in fast mode at all;
- multiply-add contraction (Zig strict forbids it; C compilers may fuse by
  default);
- removal of the divisor proof for float division;
- literal defaults, subnormals and NaN ordering in min and max;
- float-to-integer conversion failure;
- tensor reduction order.

Compatibility: current programs keep compiling. The finite-only research promise is
withdrawn, and documentation and proof rules for float guards change.

Re-probed 2026-10-02 at HEAD (231d74e): `zero / zero` still exits 6, "Divisor not proven non-zero" at line 3 col 21, where L16 requires NaN (still open; L33 left divisor-proof requirements unchanged).

### G2. Ownership and reference surface

Replaced on 2026-09-15 by the [memory plan](memory.md) (L15–L19), which makes
ownership an internal compiler layer (see gates M3 and M4 there). The earlier
options were (a) syntax-free affine references that reject `q := p` for owned
references, recommended first; (b) parameter modes declaring borrow, inout or
consume in signatures, which add keywords and conflict with storable `ref` fields;
and (c) regions or arenas added later for scratch and tensor storage. Its
sub-decisions were storable reference fields, untagged-union access, uninitialized
values, escaping slices, allocation failure and tensor saved-value lifetime. The
observations below remain evidence.

A `ref` parameter changes caller storage while its binding stays immutable. That
already matches L6:

```a7
// Current A7 (SPEC section 3.3).
set_to_100 :: fn(value: ref i32) {
    value = 100
}
```

Observed 2026-09-16 with a `main` that calls `set_to_100(n)`: compiles to
`value.?.* = 100` and passes `&n`. `bump` in `examples/037_language_tour.a7`
writes through a `ref i32` the same way. Assigning one `ref` parameter to another
is rejected (see the `swap` defect below).

A heap reference can be copied and deleted twice:

```a7
// Current A7 statements inside main, with Pt declared as a struct.
p := new Pt
q := p
del p
del q
```

Observed 2026-09-15 in this tree: compiles and emits two `allocator.destroy` calls
on the same allocation.

### G3. Numeric rules beyond wrapping

L5 does not settle these cases. Each row is a separate `main` body in current A7.

| Source | Observed |
| --- | --- |
| `x: u8 = 255` then `x += 1` | 2026-09-15: compiles to Zig `x += 1`, which traps in Debug and is undefined in ReleaseFast. L5 requires 0 |
| `x: i8 = -128` then `q := x / -1` | 2026-09-15: compiles to `@divTrunc(x, -1)`, which overflows |
| `x: i8 = -128` then `r := x % -1` | 2026-09-16: compiles to `@rem(x, -1)` |
| `x: i8 = -128` then `y := -x` | 2026-09-16: compiles to `(-x)`; 128 does not fit `i8` |
| `value: u8 = 1`, `count: usize = 8`, `shifted := value << count` | 2026-09-15: compiles to `value << @intCast(count)`; 8 does not fit the shift type |
| `a: u8 = 200`, `b: i32 = 5`, `c := a + b` | 2026-09-16: compiles to `(a + b)`; the widening rule for mixed operand types is undecided |
| `n: i32 = 300`, `b := cast(u8, n)` | 2026-09-16: rejected, exit 6: "Unsafe type cast (cast must be classified and range-proven: cast target range is not proven)" |
| `a: u8 = 250 + 10` | 2026-09-15: rejected, exit 6: "expected 'u8', got 'i32'" |

At least the `+=`, division and shift rows violate the fail-closed contract today;
by Zig's rules the negation row overflows the same way. Track 1 must reject them
or give them approved defined semantics.

Decide: signed `MIN / -1` and `MIN % -1`; wrapping or proved negation; shift-count
range; typed or exact constant expressions (`a` wraps to 4 or is rejected);
same-type operands or defined widening; narrowing casts with proofs; checked
allocation-size arithmetic; and the D.024/D.038 `cast` contradiction.

Recommended: typed constant evaluation that matches run time, same-type operands
with contextual literals, proofs for narrowing and shifts, and checked size
arithmetic.

Re-probed 2026-10-02 at HEAD (231d74e): `x: u8 = 255` then `x += 1` now emits `x +%= 1` in debug and release (changed-by-L5/L35, unproven case keeps wrapping per L49); `MIN / -1` still `@divTrunc(x, -1)`, `MIN % -1` still `@rem(x, -1)`, `-MIN` still `(-x)`, `u8 << usize(8)` still `value << @intCast(count)` (still open; L35 leaves signed division overflow and abs(MIN) open).

### G4. Function values and the recursion ban

A callback stored in a struct field can create recursion that the ban does not
detect (MS-7 in the 2026-09-14 GLM memory-safety review). Storing one is accepted
today:

```a7
// Current A7.
BinaryOp :: fn(i32, i32) i32

add :: fn(a: i32, b: i32) i32 {
    ret a + b
}

Calculator :: struct {
    op: BinaryOp
}

apply :: fn(op: BinaryOp, a: i32, b: i32) i32 {
    ret op(a, b)
}

main :: fn() {
    calc := Calculator{op: add}
    stored := calc.op(1, 2)
    direct := apply(add, 1, 2)
}
```

Observed 2026-09-16: compiles. The call-graph edge problem is the MS-7 finding and
was not reproduced here.

- (a) Forbid stored function values and allow direct callback arguments only.
  `stored` above is rejected; `direct` stays. Simpler to verify.
- (b) Keep stored function values and add type-informed call-graph edges. Both
  calls stay. Preserves callback tables and `examples/022` and `037`, which store
  function values.

Decide together with memory plan gate M6.

### G5. Errors, matching and composite values

Decide tagged-union syntax, payload matching, `Option` and `Result` spelling,
error propagation, struct initialization completeness and nominal identity. The
current I/O helpers panic on external failures; decide their recoverable
replacement. Collection lookup results are memory plan gate M33.

Tagged unions parse, but payload matching does not exist:

```a7
// Current A7.
Result :: union(tag) {
    ok: i32
    err: string
}

main :: fn() {
    r := Result{ok: 1}
    match r {
        case ok: {
        }
    }
}
```

Observed 2026-09-16: compiles to a Zig `union(enum)`. The emitted Zig binds
`const ok = __a7_match_1;`, so `case ok` captures the whole union as a new name.
It does not test the `ok` tag.

### G6. Source text, modules and tooling

Decide UTF-8 source with ASCII identifiers and digits, diagnostics for unclosed
comments and malformed literals, module cycles, visibility enforcement, and new
commands (`check`, `build`, `run`, `test`, `fmt`, `doctor`). Parse errors must
always fail compilation; that is a correctness fix, not a gate.

SPEC section 2.1 says source must be ASCII. Observed 2026-09-16:

| Source | Result |
| --- | --- |
| `café := 1` inside `main` | Rejected, exit 4: "Unexpected character: 'é'". Re-observed 2026-09-16 in human and JSON modes; an earlier note recorded `'Ã'`, which no longer reproduces |
| `s := "café"` inside `main` | Compiles; the string is emitted unchanged |

An unclosed comment hides the rest of the file:

```a7
// Current A7. The block comment is never closed.
/* unclosed
main :: fn() {
}
```

Observed 2026-09-16: exit 0 with zero declarations and no diagnostic.

Re-probed 2026-10-02 at HEAD (231d74e): unclosed `/*` still exits 0 with zero declarations and no diagnostic, in human and JSON modes (still open); file-scope bare statements (`x = 5`, `io.println("hi")`) now exit 5, "Expected declaration (constant, variable, or function)" (fixed, parser now fails compilation; `x := 5` at file scope is a valid global emitting `var x`).

### G7. Concurrency

Decide structured task lifetime, cancellation, join outcomes and channel close.
Depends on G5 and memory plan gate M10. A7 has no task syntax today.

```a7
// Proposed syntax. Every spelling here is undecided.
worker :: fn(out: Channel(i32), id: i32) {
    out.send(id * 2)
}

main :: fn() {
    results := Channel(i32){}
    task_group {
        spawn worker(results, 1)
        spawn worker(results, 2)
    }   // both tasks end before this scope ends
    results.close()
}
```

Open questions on this example: what happens to the second task if the first
fails, what each join reports, and whether `close` is explicit (gates M10, M26,
M27).

### G8. AI contracts

Decide the tensor literal default dtype, promotion or explicit casts, mutation and
alias syntax, non-differentiable boundaries, all-masked attention behavior,
skipped-step and retry rules, checkpoint format and compatibility, model recipes,
accuracy thresholds and the named CPU target. Depends on G1 and memory plan gates
M11 and M17–M24. SPEC section 9 is a design target; no tensor code compiles today.

```a7
// Proposed syntax. Every spelling here is undecided.
x := tensor([1.0, -2.0, 3.0])   // default dtype: f32 or f64?
loss := sum(x * x)
x[0] = 5.0                      // changes a value saved for backward
grads := backward(loss)         // without the line above: [2, -4, 6]
```

Memory plan gate M18 recommends rejecting the write to `x[0]` at compile time.

### G9. Release posture

Choose ReleaseFast once proofs are sound, or ReleaseSafe until the memory work
lands. Name supported operating systems and architectures. Changing the profile
does not fix proof errors.

```a7
// Current A7.
main :: fn() {
    x: u8 = 255
    x += 1
}
```

Observed 2026-09-16: compiles to Zig `x += 1`. By Zig's rules, Debug and
ReleaseSafe builds trap on that overflow and ReleaseFast leaves it undefined. The
program was not run.

Re-probed 2026-10-02 at HEAD (231d74e): the same program now emits `x +%= 1` in both debug and release profiles (fixed; wrapping lowering landed under L5/L35, and the unproven overflow keeps wrapping per L49).

## Work tracks

| Track | Work | Depends on | Exit evidence |
| --- | --- | --- | --- |
| 0. Authority reconciliation | Record gate decisions. Mark superseded entries in `08-decisions.md`, HANDOFF, STATUS and the safety contract without deleting them. Fix the documentation defects below | Ledger | No contradictory active rule |
| 1. Correctness repair | Reject source/output collisions. Report only current artifacts. Fail compilation on parse errors. Keep imported diagnostic origins. Fold integers exactly. Lower Zig keywords and loop captures correctly. Repair stale proof facts | None | The 12 failing pipeline tests pass. A public-CLI test rejects the parser declaration drop. GLM reviews memory-affecting fixes |
| 2. Frontend and diagnostics | Token spans, numeric validation, parser progress, literal-fit contexts, aggregate validation, JSON output integrity | G6 for text-policy changes | Valid and invalid sources through CLI human and JSON modes |
| 3a. Wrapping | Lower `+`, `-` and `*` to Zig wrapping operators; folding matches run time | L4, L5 | Independent boundary values agree across folding, run time, Debug and ReleaseFast |
| 3b. Numeric semantics | One target-aware numeric specification for checking, folding, proofs and lowering: division, remainder, negation, shifts, widening, narrowing, casts, float rules | 3a, G1, G3 | Same as 3a for every numeric operation |
| 4. Typed IR and identity | Stable declaration identities, canonical modules, explicit sequencing, CFG, effect summaries | 1, 2 | Shadowing, import and evaluation-order traces |
| 5. Proof repair | Branch joins, loop invariants, call invalidation, approval validity after transformations | 4 | Documented unsafe counterexamples reject; guarded controls compile and run |
| 6a. Memory model core | Memory plan phases B, C1, C1′, D, E and C2: internal ownership, copies, extents, storage, reuse, removal | Memory plan gates, 5, 7a, 8a | Memory plan exit evidence for those phases; GLM review of each phase |
| 6b. Memory model integration | Memory plan phases F and G: tasks, tensors and native qualification; layout and report | 6a, 9, 10, 11 | Memory plan exit evidence for F and G; GLM review |
| 7a. Optionals and matching | Tagged unions, payload matching, optionals | G5, 4 | Cross-feature matching tests |
| 7b. Results and errors | Result, error propagation, recoverable operations | 7a | Cross-feature failure and cleanup tests |
| 8a. Core collections | Owning `string`, `List`, `Map`, `Table`, `Id`, deep equality and hashing | G5, 5, memory plan gates M1, M5, M13, M33, M42, M49 | Collection corpus programs; feeds phase C1 |
| 8b. Standard library | Text, files, paths, math, time, random, process, recoverable I/O | 6a, 7b | Real boundary and recovery evidence |
| 9. Concurrency | Task and channel state machines and runtime | G7, 6a, 7b | Interleaving, blocking and shutdown evidence |
| 10. Native boundary | ABI descriptors, native handle ownership, kernel-library bridge | 6a | Native boundary qualification; GLM security review |
| 11. CPU AI | The AI sequence below | G1, G8, 3b, 6a, 10 | AI acceptance scenarios |
| 12. Docs and website | Version stamps, transcripts, search, mobile layout, focus, procedures; docs for each approved change | Continuous | Browser acceptance with recorded captures |
| 13. Release qualification | Locked-dependency audit, artifact provenance, clean install, platform matrix | All | Full gate passes with no known failures at a named revision |

Tracks 1, 2 and 12 can start now. Track 3a can start once the L5 details are
approved.

Two dependency cycles were removed on 2026-09-16 by splitting tracks. Memory plan
phase C1 needed collections from track 8, which depended on track 6, which
contained C1 (review finding M-10); collections are now track 8a, which C1 depends
on. Memory plan phase F depended on tracks 9, 10 and 11, which each depended on
track 6, which contained F; phases F and G are now track 6b, after 9, 10 and 11.
One exception is proposed for approval: minimal buffer-based input and output
(packet P9 of the execution plan) may land before track 8b.

### Documentation defects for track 0

Found during the 2026-09-16 docs cleanup. All compile-only; no program was run.

Documentation defects:

- SPEC's `fn_ptr: ref fn() void = nil` (`docs/SPEC.md:192`) is rejected with
  "Undefined type (Type 'void')".

Compiler defects for track 1:

- An unclosed `/*` comment compiles with exit 0, no declarations and no
  diagnostic. Parse errors must fail compilation.
- Statements written at file scope compile with exit 0, are silently dropped,
  and emit no `main`.
- `[n]u8` with an unbound `n` compiles and emits Zig that references an
  undefined `n`.
- `ret 0` from a function returning `u32` or `usize` is rejected, although
  `x: u32 = 0` is accepted and `ret cast(u32, 0)` works.
- `z := z` emits `const z = z;`.
- An index guarded by `if i < xs.len` is still rejected, while `for v in xs` is
  accepted. This is track 5 work.

Defects whose fix changes accepted programs, so they need approval rather than
track 1 alone:

- `case ok` on a tagged union captures the whole union instead of testing the
  tag (G5; interim rule in execution-plan packet P5).
- A string holding `é` compiles, against the documented ASCII source rule (G6;
  execution-plan packet P2).

Recorded earlier:

- `docs/SPEC.md:1155-1158` says shapes `[3, 1, 4]` and `[2, 5, 1]` broadcast to
  `[3, 2, 5, 4]`. Under the stated NumPy rules they do not broadcast.
- `docs/SPEC.md:2021` still lists `.val` in the grammar, which the reference
  surface rules exclude.
- `docs/SPEC.md:410-411` and `docs/SPEC.md:448` disagree about typed-binding
  mutability.
- `docs/SPEC.md:698-702`: the `swap` example reassigns `ref` parameter bindings,
  against L6. Observed 2026-09-16: as written it fails to parse, exit 5, "Expected
  RIGHT_PAREN, got COLON" at `$T, a: ref T`. A non-generic `i32` copy fails with
  exit 6, "Cannot assign to immutable binding: 'a' is immutable".
- The cluster CA summary in `docs/lang-safety/08-decisions.md` (lines 700-705 in
  commit `701c679`, before the file was reformatted) says `nil`
  is removed, contradicting the revised D.013.
- `examples/025_linked_list.a7` uses `isize` indices with `-1` as a sentinel,
  against the `usize` index rule.
- The safety contract's fixed-width arithmetic proof row conflicts with L5 and
  must change when wrapping lowering lands.

### Defects reproduced in Wave 0

Reproduced on 2026-09-16 against commit `701c679` by the execution plan's Wave 0
ledger (`docs/plan/audit/2026-09-16-inventory-repro.md`; IDs in brackets). Probes
were compile-only unless marked "run".

Programs wrongly rejected (fixing them only accepts more programs):

- A file with more than 1000 top-level declarations exits 5 with a parse error
  naming a valid declaration [F3].
- A `del p` in one function makes a read of an unrelated `p` in a later function
  an error [S4].
- A literal argument to a `usize` parameter is rejected [C6 note].
- `.len` on a fixed array or a string is rejected as field access on a
  non-struct [S12].
- A negative float literal divisor is rejected as possibly zero, and the error
  has no line [D7].
- Indexing or slicing a slice or string parameter is always rejected by the
  bounds proof; indexing a `ref [N]T` parameter reports "Cannot index this
  type" [S11]. This is track 5 work.

Accepted programs that Zig rejects:

- Parser warnings go to stdout, so `--format json` output is not valid JSON [F4].
- `--format json` on a match that yields a struct crashes with a `TypeError` in
  `json_formatter.py:215` and exits 1 [F5].
- Signed `/=` and `%=` emit Zig's `/=` and `%=`, which Zig rejects for runtime
  signed operands [B13].
- A shadowed local is declared as `x_1` but its uses emit `x`; Zig rejects the
  unused declaration [B10].
- `defer x = 1` emits `defer void;` [B11].
- An A7 local named `test`, `var` or `const` is emitted unescaped at its
  declaration; a local named `allocator` clashes with the emitted allocator when
  the program uses `new` or `del` [B12].
- A string `==` between parameters emits `==` on `[]const u8`, which Zig
  rejects [B3].
- A mutable untyped global holding an integer literal emits `var counter = 0;`,
  which Zig rejects [B6].
- A write into a by-value array parameter is accepted [B7].
- `del` of a variable named `p` clashes with the emitted `|p|` capture [B9, S6].

Miscompiles (programs build and compute the wrong result):

- `arr = [arr[1], arr[0]]` prints `2 2` in Debug and ReleaseFast [B1, run].
- A function-pointer field call on a local struct named `math` becomes Zig's
  `@sqrt` and prints `3 4.5` instead of `4.5 4.5` [B14, run].
- `9007199254740993 / 1` folds to `9007199254740992` [S13, run].
- `-7.5 % 2.0` folds to `0.5`; the run-time result is `-1.5` [D7, run].
- `ref fn() = nil` lowers to a pointer to a function pointer
  (`?**const fn () void`) [D1].

Unsafe programs accepted today, whose rejection needs approval (execution-plan
packet P0b):

- `x := 5; { x = 0 }; y := 10 / x` [S1]; the same with a `while` loop [S2]; the
  same after a call through a `ref i32` parameter [S3].
- `x := 5; x -= 5; y := 10 / x`: compound assignment does not update facts
  [Part A note].
- A returned slice of a local stack array [S5]; `q := p; del p; del q` [S6]; a
  double `del` in a `while` loop [S7]; `del` through a `ref` parameter, which
  frees a stack address [S8].
- `defer del p` followed by `del p` [audit A-30].
- String `==` between locals holding literals compares addresses [B3].

Behavior changes that need approval in other packets:

- Parse errors after the first declaration are dropped silently, and
  file-scope statements are dropped [F2]; `SPEC.md:254, 281, 296, 383` compile
  only because of this (packet P1).
- `...` lexes as `..` followed by `.`; `?` is not a token; `#` line comments
  are accepted; `int`, `uint` and `float` are keyword tokens the parser rejects
  [D5, D8, D9] (packet P1).
- A match case named like an outer variable compares against that variable
  instead of capturing [audit A-32] (packet P5).
- `last: Pt` without an initializer lowers to `= undefined` [D6] (gate M34).

Documentation observed against the compiler:

- Typed declarations are mutable, including at file scope, so
  `docs/SPEC.md:410-411` is wrong and `docs/SPEC.md:448` is right [D2].
- None of the three generic examples at `docs/SPEC.md:698-716` compiles [D3].
- `printf` (`docs/SPEC.md:788`) and bare `sqrt` (`docs/SPEC.md:817-822`) are
  undefined [D4].

## AI sequence

1. Tensor value semantics: shape, dtype, strides, views, broadcasting, aliasing,
   and functional updates with safe storage reuse.
2. Portable reference kernels for every required operator and dtype, including
   defined f16 and bf16 widening where CPUs lack native support.
3. Eager reverse-mode tape with iterative traversal, accumulation for shared
   operands, explicit saved-value lifetime and mutation checks.
4. Kernel bridge: OpenBLAS or BLIS for `f32` and `f64` matrix work, and optional
   oneDNN acceleration. Neither may be the only CPU path.
5. Mixed precision: f32 master weights, accumulation, optimizer state and loss
   operations; loss scaling and skipping the whole step on non-finite gradients.
6. Training state: optimizer, scheduler, RNG, data position and checkpoints.
7. Workloads: classifier training and evaluation, then decoder training and
   generation.
8. Packaged inference in a clean environment separate from training tooling.

Accelerator backend adapters stay at interface design. The hardware research
ordering does not create v1 qualification work.

## Test plan

Follow the test-quality rule in `AGENTS.md`. Every requirement row states the
requirement, input, independently derived expected result, invocation, toolchain
versions and remaining limits.

- **Pipeline:** real CLI, real files, real Zig builds. No mocks, skips or
  expected-failure markers for required behavior.
- **Numeric:** independently calculated width-boundary results, constant and
  run-time parity, Debug and ReleaseFast parity. Float cases start after G1.
- **Diagnostics:** exit category, file, line and column in human and JSON modes,
  including imported modules.
- **Safety:** each unsafe counterexample paired with a guarded program that is
  accepted. Memory-corruption fixtures are compile-time rejection checks, never
  executed.
- **Metamorphic:** renaming, harmless blocks, module splits and equivalent literals
  preserve behavior.
- **AI:** exact small matmul results; rejection of broadcasting `[3,1,4]` with
  `[2,5,1]`; gradient `[2,-4,6]` for `sum(x*x)` at `[1,-2,3]`; f64 finite
  differences at smooth points; accumulation for repeated gather indices; optimizer
  state unchanged after a skipped step; step N+1 matching after reloading a
  checkpoint in a fresh process; held-out classifier evaluation; separate decoder
  generation.
- **Tolerances:** combined absolute and relative error limits fixed before each
  run. NaN, infinity and signed zero checked separately. Bitwise equality is not
  promised across library versions, instruction sets, thread counts or devices.
- **Gate:** `./run_all_tests.sh` after each non-trivial track change.

## Assumptions

- Plan scope follows the ledger's locked decisions.
- The first CPU qualification host is the development Linux x86_64 machine until
  G9 names a platform matrix.
- Zig 0.16.0 stays the backend unless a gate approves an upgrade.
- Research reports are advisory. Their claims about external projects were not
  rechecked for this plan.
- Package-registry work stays out of scope. Package manifests and locks are limited
  to reproducible local builds.


## Current delivery sequence

The [V1 delivery roadmap](delivery-roadmap.md) reconciles the repaired baseline,
compiler foundations, grouped decisions and dependency milestones. It records
the approved core V1 scope and leaves unresolved semantics behind explicit approvals.
