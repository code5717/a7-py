# `docs/lang-safety/` — Memory-Safety Reference for A7

Research notes for the A7 language design. The contract A7 commits to:

> **The A7 compiler statically rejects every program that would
> exhibit a memory-safety violation. The Zig code it emits is
> memory-safe on its own and remains memory-safe when compiled with
> `zig build -O ReleaseFast` (every Zig runtime safety check
> disabled). Memory safety is a property of the emitted source, not
> of the backend's flags. The language has no `unsafe` escape
> hatch.**

That contract drives every file in this directory.

| # | File | What's in it | When you need it |
| --- | --- | --- | --- |
| 01 | [`01-invisicaps.md`](./01-invisicaps.md) | Fil-C's InvisiCaps capability model, FUGC garbage collector, FilPizlonator LLVM pass, disassembly walkthrough | Read to understand how a *runtime* memory-safety system works on legacy C (and why A7 doesn't need one) |
| 02 | [`02-sanitizers.md`](./02-sanitizers.md) | ASan, MSan, LSan, TSan, HWASAN, UBSan, CFI, `-fbounds-safety`, SafeStack, ShadowCallStack, PAC | Read to understand the *dynamic* baseline A7 must clear *statically* |
| 03 | [`03-hardware.md`](./03-hardware.md) | CHERI / Morello, ARM MTE, SPARC ADI, Intel LAM / CET, ARM PAC | Read when deciding which hardware-hardening flags to plumb through to non-A7 code (linked C, OS) |
| 04 | [`04-comparison.md`](./04-comparison.md) | Coverage matrix, cost matrix, decision tree, four ideas worth stealing | Read to pick a single mechanism per safety property |
| 05 | [`05-for-a7.md`](./05-for-a7.md) | **The zero-runtime-error contract for A7**: phased plan, codegen discipline (the emitted Zig must be safe under `-O ReleaseFast`), the no-trap test that operationalises it | The implementation guide |
| 06 | [`06-compile-time-safety.md`](./06-compile-time-safety.md) | Catalog of compile-time safety techniques: definite assignment, non-null types, sum types, affine types, borrow checking, region inference, generational references, mutable value semantics, reference capabilities, refinement types, dependent types, effect systems, comptime | Read when implementing any specific static-analysis pass |
| 07 | [`07-language-review.md`](./07-language-review.md) | **Audit of the current A7 codebase against the contract.** Per-feature gaps with `file:line` citations, severity ranking, proposed minimal changes, recommended change order | Read before proposing any safety-related PR — this tells you what to fix and in what order |
| 08 | [`08-decisions.md`](./08-decisions.md) | **Phase C decisions document.** Cluster CA (type-system foundations + numeric vocabulary, 23 decisions) is ACCEPTED. Clusters CB-CG pending. | The source of truth for what A7 has committed to |
| -- | [`narrowing.md`](./narrowing.md) | **Flow-sensitive narrowing — research notes for Cluster CD.** Subtype-style refinement: "after `if b != 0`, `b` has the non-zero subtype". Recognised patterns, invalidation rules, precision/cost trade-offs, what A7 v1 supports | Read before Cluster CD; powers the safety contract |
| -- | [`conversions.md`](./conversions.md) | **Conversions — research notes for Cluster CB.** Catalogs the post-CA conversion surface, compares method-style vs constructor-style vs operator-style across 9 languages, and documents the narrowing-driven check-elision principle | Read before Cluster CB; covers method-style conversion design |
| -- | [`compile-time-knowledge.md`](./compile-time-knowledge.md) | **The central principle.** "The cast is allowed because the compiler knows the value." Formalises the knowledge-accumulation model behind A7's safety contract. Three knowledge tiers (sufficient, insufficient-recoverable, insufficient-irrecoverable), worked examples, theoretical foundations (abstract interpretation, refinement types, epistemic logic), and how the compiler enforces it | Read for the unifying mental model behind every safety rule |
| -- | [`parameter-modes.md`](./parameter-modes.md) | **Parameter modes — research notes for Cluster CC.** Designs ownership and parameter-passing under the contract: `borrow`/`inout`/`consume`, immutable params by default (Odin), no storable refs, call-site exclusivity, channels + isolated owned data for concurrency. Compares Hylo / Swift / Mojo / Odin. | Read before Cluster CC |
| ⭐ | [`HANDOFF.md`](./HANDOFF.md) | **Read this first if you are picking up this work.** Self-contained handoff: current state, codex's findings, the 4 design questions awaiting user decision, the 9-pass compiler architecture, the cast() classifier table, three-phase delivery, codebase pointers, what to do next | The entry point for continuing the design work |
| -- | [`codex-review.md`](./codex-review.md) | Saved output of codex's first critical review (152 lines) — soundness/ergonomics/performance/implementation/inconsistencies/precedent flags | Cited from HANDOFF.md |

## Phase A — Edge-case enumerations (`edge-cases/`)

For each of the 12 gaps in `07-language-review.md`, a deep
enumeration of subcases, interactions with the other 11 gaps,
failure modes, and open questions to be decided in Phase C.

| File | Gap |
| --- | --- |
| [`edge-cases/01-cast.md`](./edge-cases/01-cast.md) | Cast classification (lossless / truncating / bit-cast / forbidden) |
| [`edge-cases/02-nullable-pointers.md`](./edge-cases/02-nullable-pointers.md) | Splitting `ref T` (non-null) from `?ref T` |
| [`edge-cases/03-definite-assignment.md`](./edge-cases/03-definite-assignment.md) | Flow-sensitive must-be-assigned analysis |
| [`edge-cases/04-nonzero-division.md`](./edge-cases/04-nonzero-division.md) | `NonZero<T>` and division/modulo discipline |
| [`edge-cases/05-stack-budget.md`](./edge-cases/05-stack-budget.md) | Compile-time max-stack-depth proof |
| [`edge-cases/06-typed-arithmetic.md`](./edge-cases/06-typed-arithmetic.md) | Range tracking + typed overflow operators |
| [`edge-cases/07-bounded-indexing.md`](./edge-cases/07-bounded-indexing.md) | The four-pattern bound proof + `try_get` |
| [`edge-cases/08-option-result.md`](./edge-cases/08-option-result.md) | `Option<T>` / `Result<T, E>` stdlib shapes |
| [`edge-cases/09-refinement-lite.md`](./edge-cases/09-refinement-lite.md) | Refinement-lite type kit (`Bounded`, `Index`, `NonZero`, `Fin`) |
| [`edge-cases/10-affine-ownership.md`](./edge-cases/10-affine-ownership.md) | Affine ownership + `inout`/`borrow` parameter modes |
| [`edge-cases/11-finite-floats.md`](./edge-cases/11-finite-floats.md) | `Fin<F>` and NaN/inf discipline |
| [`edge-cases/12-ffi-boundary.md`](./edge-cases/12-ffi-boundary.md) | FFI: the one boundary at which the language stops enforcing |

## Phase B — Comparative deep-dives (`comparative/`)

How reference languages handle each of the 12 gaps, and what A7
should and should not steal. See
[`comparative/README.md`](./comparative/README.md) for the
in-directory index plus cross-cutting insights.

| File | Language | Why study it |
| --- | --- | --- |
| [`comparative/ada.md`](./comparative/ada.md) | Ada / SPARK | Industrial reference for static safety; SPARK ownership is Rust-inspired in production |
| [`comparative/ada-deep-dive.md`](./comparative/ada-deep-dive.md) | Ada — whole language | Distinct types, packages, generics, tasking, aspect specifications — inspirations beyond the 12 gaps |
| [`comparative/rust.md`](./comparative/rust.md) | Rust | Upper bound of expressiveness; the bar to clear |
| [`comparative/hylo.md`](./comparative/hylo.md) | Hylo | Compile-time memory safety **without lifetime annotations** — A7's target model |
| [`comparative/zig.md`](./comparative/zig.md) | Zig | A7's backend; what `-O ReleaseFast` removes |
| [`comparative/cyclone.md`](./comparative/cyclone.md) | Cyclone | First safe-C dialect; region inference; 8% migration cost from legacy C |
| [`comparative/pony.md`](./comparative/pony.md) | Pony | Six reference capabilities for race-free concurrency |
| [`comparative/austral.md`](./comparative/austral.md) | Austral | Pure linear types; 600-line borrow checker |
| [`comparative/swift.md`](./comparative/swift.md) | Swift | Largest production deployment of `borrowing`/`consuming`/`inout` |
| [`comparative/mojo.md`](./comparative/mojo.md) | Mojo | Current incumbent doing essentially what A7 plans |
| [`comparative/vale.md`](./comparative/vale.md) | Vale | Generational references as runtime-tinged fallback |
| [`comparative/inko-koka-verona.md`](./comparative/inko-koka-verona.md) | Inko, Koka, Verona | Short profiles: isolated heaps, effect tracking, region-based concurrency |

## How this directory was assembled

Sources (all fetched as primary research, not summarised from secondary
material):

- Fil-C: <https://fil-c.org/invisicaps.html>,
  <https://fil-c.org/invisicaps_by_example.html>,
  <https://fil-c.org/gimso.html>,
  <https://fil-c.org/fugc.html>,
  <https://fil-c.org/compiler.html>,
  <https://fil-c.org/compiler_example.html>,
  <https://fil-c.org/documentation.html>,
  <https://fil-c.org/meet_fil.html>,
  <https://github.com/pizlonator/fil-c/blob/deluge/Manifesto.md>
- Google Sanitizers: <https://github.com/google/sanitizers> and the
  per-tool wiki pages (AddressSanitizer, AddressSanitizerAlgorithm,
  MemorySanitizer, AddressSanitizerLeakSanitizer,
  ThreadSanitizerCppManual)
- Clang docs: <https://clang.llvm.org/docs/index.html>,
  <https://clang.llvm.org/docs/HardwareAssistedAddressSanitizerDesign.html>,
  <https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html>,
  <https://clang.llvm.org/docs/ControlFlowIntegrity.html>,
  <https://clang.llvm.org/docs/BoundsSafety.html>
- Hardware: CHERI (Cambridge), Morello (Arm), MTE (Arm developer docs),
  HWASAN paper (arXiv 1802.09517), Intel LAM, SPARC ADI
- Background literature: SoftBound (PLDI 2009), CETS, Dijkstra
  concurrent GC, Doligez-Leroy-Gonthier, Fiji VM, Schism

All external URLs are linked inline from each file. Nothing here is
authoritative for any of the source projects — these are study notes.

## The contract in one paragraph

A7's safety story is **not** "the runtime catches it." It is "the
compiler proves the bug cannot occur, and the emitted Zig encodes
that proof structurally — no flag, no runtime check, no trap." The
operational test is in [`05-for-a7.md` §4.8.13](./05-for-a7.md#48-codegen-discipline--what-the-emitted-zig-must-look-like):
walk the emitted Zig source for every example, fail the build if
`@panic`, `@trap`, `__builtin_trap`, or unannotated `unreachable`
appears. Build everything with `zig build-exe -O ReleaseFast`. Run
the test corpus. Zero crashes.

## Quick recommendations

1. **A7 is not C.** Most of what Fil-C and the sanitizers solve is
   *already solved by A7's type system* — no `inttoptr`, no
   unrestricted unions, no recursion, slices instead of pointer
   arithmetic.
2. **The compile-time contract closes everything else.** Nullability,
   use-after-free, slice bounds, integer overflow, division by zero,
   allocation failure, stack overflow — each is rejected statically
   or surfaced as a typed value the user must handle.
3. **The emitted Zig must be safe by shape, not by Zig flags.** A7
   discharges each safety obligation; the codegen lowers to a Zig
   construct that structurally cannot violate it.
   `-O ReleaseFast` is the test: if A7's claim holds, disabling every
   Zig runtime check changes nothing observable.
4. **Don't build a Fil-C clone.** Software capabilities exist to
   handle pointer forgery in legacy C; A7 doesn't permit forgery, so
   the problem doesn't arise.
5. **Hardware flags harden non-A7 code, not A7 code.** PAC, BTI, CET
   protect linked C libraries and the kernel. A7-emitted code is
   already safe by construction; the flags are a separate, additive
   defence.

The "what to build first" plan is in
[`05-for-a7.md` §5](./05-for-a7.md#5-phased-plan-zero-runtime-error-ordering).
The catalog of static techniques is in
[`06-compile-time-safety.md`](./06-compile-time-safety.md).
