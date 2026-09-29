# `docs/lang-safety/` — Memory-Safety Reference for A7

Status: index for memory-safety research, proposals, decision records and
reviews written before 2026-09-14. Current user decisions are in the
[v1 decision ledger](../plan/decisions.md), which supersedes parts of this
directory.

## Reading status

This directory keeps safety-design research, proposals, accepted design
decisions and review snapshots. An accepted design decision does not mean the
compiler implements it. Code pointers and implementation assessments describe
the code their authors examined.

Where to find current information:

| Need | Read |
| --- | --- |
| Usage and release guidance | [repository README](../../README.md), [release checklist](../RELEASE.md) |
| What the compiler enforces today | [compiler safety contract](../SAFETY_CONTRACT.md) |
| Current gaps | [STATUS.md](../STATUS.md) |
| User decisions (ledger L1–L22) | [docs/plan/decisions.md](../plan/decisions.md) |
| V1 plan and approval gates | [docs/plan/README.md](../plan/README.md), [memory plan](../plan/memory.md) |
| Other repository docs | [documentation index](../README.md) |

### Superseded directions (2026-09-16)

The ledger replaces these parts of the research. The original text stays in
place.

| Research direction | Replaced by |
| --- | --- |
| `int`, `uint`, `number` as primary types; width types FFI-only (D.001, D.002) | Explicit widths only; `number` removed (L3, L4) |
| Non-overflowing arithmetic through bignum promotion (D.003); range proofs for `+ - *` | `+`, `-`, `*` wrap (L5). Division, shifts, narrowing casts and size arithmetic stay under gate G3 |
| Finite-only floats (`Fin<F>`, "no NaN, no inf") | IEEE 754 floats as in Zig and C (L16; gate G1) |
| Parameter-mode keywords, inferred modes, no storable references (proposed D.040, D.041, D.049) | Not accepted. Immutable argument bindings with no mode syntax (L6); ownership becomes internal ([memory plan](../plan/memory.md)) |
| Explicit ownership with `new`/`del` (current syntax) | Direction: memory is automatic, resolved at compile time and invisible to users (L15, L17–L22; [memory plan](../plan/memory.md)). Removing `del` still needs approval |
| `cast(T, x)` kept (D.024) or removed (D.038) | Neither; open under gate G3 |

## Research contract and reading map

The contract this research designs toward:

> **The A7 compiler statically rejects every program that would
> exhibit a memory-safety violation. The Zig code it emits is
> memory-safe on its own and remains memory-safe when compiled with
> `zig build -O ReleaseFast` (every Zig runtime safety check
> disabled). Memory safety is a property of the emitted source, not
> of the backend's flags. The language has no `unsafe` escape
> hatch.**

Every file in this directory is shaped by that contract.

> Note (2026-09-16): this is a design goal, not the enforced state.
> [SAFETY_CONTRACT.md](../SAFETY_CONTRACT.md) lists what is enforced. The
> [memory plan](../plan/memory.md) §1 proposes amending this contract (gate
> M16). Plan gate G9 leaves open whether releases use ReleaseFast or
> ReleaseSafe.

| # | File | Contents | When you need it |
| --- | --- | --- | --- |
| 01 | [`01-invisicaps.md`](./01-invisicaps.md) | Fil-C's InvisiCaps capability model, FUGC garbage collector, FilPizlonator LLVM pass, disassembly walkthrough | To understand how a *runtime* memory-safety system works on legacy C, and why A7 doesn't need one |
| 02 | [`02-sanitizers.md`](./02-sanitizers.md) | ASan, MSan, LSan, TSan, HWASAN, UBSan, CFI, `-fbounds-safety`, SafeStack, ShadowCallStack, PAC | To understand the *dynamic* baseline A7 must clear *statically* |
| 03 | [`03-hardware.md`](./03-hardware.md) | CHERI / Morello, ARM MTE, SPARC ADI, Intel LAM / CET, ARM PAC | When deciding which hardware-hardening flags to pass through for non-A7 code (linked C, OS) |
| 04 | [`04-comparison.md`](./04-comparison.md) | Coverage matrix, cost matrix, decision tree, four ideas worth taking | To pick one mechanism per safety property |
| 05 | [`05-for-a7.md`](./05-for-a7.md) | The zero-runtime-error contract for A7: phased plan, codegen discipline (emitted Zig must be safe under `-O ReleaseFast`), and the no-trap test that checks it | The implementation guide |
| 06 | [`06-compile-time-safety.md`](./06-compile-time-safety.md) | Catalog of compile-time techniques: definite assignment, non-null types, sum types, affine types, borrow checking, region inference, generational references, mutable value semantics, reference capabilities, refinement types, dependent types, effect systems, comptime | When implementing a specific static-analysis pass |
| 07 | [`07-language-review.md`](./07-language-review.md) | Audit of the A7 codebase against the contract: per-feature gaps with `file:line` citations, severity ranking, minimal changes, recommended order | Before proposing a safety-related PR. Note (2026-09-16): the audit predates `a7/safety.py`; check gaps against SAFETY_CONTRACT and STATUS |
| 08 | [`08-decisions.md`](./08-decisions.md) | Phase C decisions document. Cluster CA (type-system foundations and numeric vocabulary, 23 decisions) is ACCEPTED. Clusters CB–CG pending | Was the source of truth for what A7 committed to. Note (2026-09-16): [HANDOFF.md](./HANDOFF.md) §2 records CB as ACCEPTED on 2026-05-11 and CC as proposed; the ledger supersedes D.001–D.005 and other numeric decisions |
| -- | [`narrowing.md`](./narrowing.md) | Flow-sensitive narrowing, research for Cluster CD. Subtype-style refinement ("after `if b != 0`, `b` has the non-zero subtype"): recognized patterns, invalidation rules, precision/cost trade-offs, what v1 supports | Before Cluster CD; the contract depends on it |
| -- | [`conversions.md`](./conversions.md) | Conversions, research for Cluster CB. The post-CA conversion surface; method-style vs constructor-style vs operator-style across 9 languages; the narrowing-driven check-elision principle | Before Cluster CB; covers method-style conversion design |
| -- | [`compile-time-knowledge.md`](./compile-time-knowledge.md) | The central principle: "the cast is allowed because the compiler knows the value." The knowledge-accumulation model behind the contract; three knowledge tiers (sufficient, insufficient-recoverable, insufficient-irrecoverable); worked examples; foundations (abstract interpretation, refinement types, epistemic logic); enforcement | For the model behind every safety rule |
| -- | [`parameter-modes.md`](./parameter-modes.md) | Parameter modes, research for Cluster CC: `borrow`/`inout`/`consume`, immutable params by default (Odin), no storable refs, call-site exclusivity, channels plus isolated owned data. Compares Hylo, Swift, Mojo, Odin | Before Cluster CC. Note (2026-09-16): superseded by L6 and the memory plan |
| Start | [`HANDOFF.md`](./HANDOFF.md) | Handoff for continuing the work: state as of 2026-05-11, Codex's findings, the 4 design questions, the 9-pass architecture, the cast() classifier table, three-phase delivery, codebase pointers, next steps. Now carries 2026-09-16 status notes | The entry point for the history of this design work |
| -- | [`codex-review.md`](./codex-review.md) | Codex's first critical review: soundness, ergonomics, performance, implementation, inconsistencies, precedent flags. Now with a findings-status table | Cited from HANDOFF.md |

## Phase A — Edge-case enumerations (`edge-cases/`)

For each of the 12 gaps in `07-language-review.md`: subcases, interactions with
the other 11 gaps, failure modes, and open questions for Phase C.

| File | Gap |
| --- | --- |
| [`edge-cases/01-cast.md`](./edge-cases/01-cast.md) | Cast classification (lossless / truncating / bit-cast / forbidden) |
| [`edge-cases/02-nullable-pointers.md`](./edge-cases/02-nullable-pointers.md) | Splitting `ref T` (non-null) from `?ref T` |
| [`edge-cases/03-definite-assignment.md`](./edge-cases/03-definite-assignment.md) | Flow-sensitive must-be-assigned analysis |
| [`edge-cases/04-nonzero-division.md`](./edge-cases/04-nonzero-division.md) | `NonZero<T>` and division/modulo discipline |
| [`edge-cases/05-stack-budget.md`](./edge-cases/05-stack-budget.md) | Compile-time max-stack-depth proof |
| [`edge-cases/06-typed-arithmetic.md`](./edge-cases/06-typed-arithmetic.md) | Range tracking and typed overflow operators |
| [`edge-cases/07-bounded-indexing.md`](./edge-cases/07-bounded-indexing.md) | The four-pattern bound proof and `try_get` |
| [`edge-cases/08-option-result.md`](./edge-cases/08-option-result.md) | `Option<T>` / `Result<T, E>` stdlib shapes |
| [`edge-cases/09-refinement-lite.md`](./edge-cases/09-refinement-lite.md) | Refinement-lite type kit (`Bounded`, `Index`, `NonZero`, `Fin`) |
| [`edge-cases/10-affine-ownership.md`](./edge-cases/10-affine-ownership.md) | Affine ownership and `inout`/`borrow` parameter modes |
| [`edge-cases/11-finite-floats.md`](./edge-cases/11-finite-floats.md) | `Fin<F>` and NaN/inf discipline |
| [`edge-cases/12-ffi-boundary.md`](./edge-cases/12-ffi-boundary.md) | FFI: the one boundary where the language stops enforcing |

> Note (2026-09-16): gap 06 is affected by L5 (wrapping `+ - *`), gap 10 by L6
> and the memory plan, gap 11 by L16 (IEEE floats, finite-only withdrawn), and
> gap 08 is open under gate G5.

## Phase B — Comparative deep-dives (`comparative/`)

How reference languages handle each of the 12 gaps, and what A7 should and
should not take. [`comparative/README.md`](./comparative/README.md) has the
in-directory index and cross-cutting insights.

| File | Language | Why study it |
| --- | --- | --- |
| [`comparative/ada.md`](./comparative/ada.md) | Ada / SPARK | Industrial reference for static safety; SPARK's ownership model is Rust-inspired and in production |
| [`comparative/ada-deep-dive.md`](./comparative/ada-deep-dive.md) | Ada — whole language | Distinct types, packages, generics, tasking, aspect specifications — ideas beyond the 12 gaps |
| [`comparative/rust.md`](./comparative/rust.md) | Rust | Upper bound of expressiveness; the bar to clear |
| [`comparative/hylo.md`](./comparative/hylo.md) | Hylo | Compile-time memory safety **without lifetime annotations** — A7's target model |
| [`comparative/zig.md`](./comparative/zig.md) | Zig | A7's backend; what `-O ReleaseFast` removes |
| [`comparative/cyclone.md`](./comparative/cyclone.md) | Cyclone | First safe-C dialect; region inference; 8% migration cost from legacy C |
| [`comparative/pony.md`](./comparative/pony.md) | Pony | Six reference capabilities for race-free concurrency |
| [`comparative/austral.md`](./comparative/austral.md) | Austral | Pure linear types; 600-line borrow checker |
| [`comparative/swift.md`](./comparative/swift.md) | Swift | Largest production deployment of `borrowing`/`consuming`/`inout` |
| [`comparative/mojo.md`](./comparative/mojo.md) | Mojo | Current language doing much of what A7 plans |
| [`comparative/vale.md`](./comparative/vale.md) | Vale | Generational references as a runtime-tinged fallback |
| [`comparative/inko-koka-verona.md`](./comparative/inko-koka-verona.md) | Inko, Koka, Verona | Short profiles: isolated heaps, effect tracking, region-based concurrency |

## How this directory was assembled

Sources, all read as primary material rather than summarized from secondary
sources:

- Fil-C: <https://fil-c.org/invisicaps.html>,
  <https://fil-c.org/invisicaps_by_example.html>,
  <https://fil-c.org/gimso.html>,
  <https://fil-c.org/fugc.html>,
  <https://fil-c.org/compiler.html>,
  <https://fil-c.org/compiler_example.html>,
  <https://fil-c.org/documentation.html>,
  <https://fil-c.org/meet_fil.html>,
  <https://github.com/pizlonator/fil-c/blob/deluge/Manifesto.md>
- Google Sanitizers: <https://github.com/google/sanitizers> and the per-tool
  wiki pages (AddressSanitizer, AddressSanitizerAlgorithm, MemorySanitizer,
  AddressSanitizerLeakSanitizer, ThreadSanitizerCppManual)
- Clang docs: <https://clang.llvm.org/docs/index.html>,
  <https://clang.llvm.org/docs/HardwareAssistedAddressSanitizerDesign.html>,
  <https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html>,
  <https://clang.llvm.org/docs/ControlFlowIntegrity.html>,
  <https://clang.llvm.org/docs/BoundsSafety.html>
- Hardware: CHERI (Cambridge), Morello (Arm), MTE (Arm developer docs), HWASAN
  paper (arXiv 1802.09517), Intel LAM, SPARC ADI
- Background literature: SoftBound (PLDI 2009), CETS, Dijkstra concurrent GC,
  Doligez-Leroy-Gonthier, Fiji VM, Schism

Each file links its external URLs inline. These are study notes, not
authoritative for any source project.

## The contract in one paragraph

A7's safety story is **not** "the runtime catches it." It is "the compiler
proves the bug cannot occur, and the emitted Zig encodes that proof in its
structure: no flag, no runtime check, no trap."

The operational test is in
[`05-for-a7.md` §4.8.13](./05-for-a7.md#48-codegen-discipline--what-the-emitted-zig-must-look-like):

1. Scan the emitted Zig for every example; fail the build if `@panic`, `@trap`,
   `__builtin_trap` or unannotated `unreachable` appears.
2. Build everything with `zig build-exe -O ReleaseFast`.
3. Run the test corpus. Expect zero crashes.

> Note (2026-09-16): plan gate G3 records current programs that compile to Zig
> which traps in Debug or is undefined in ReleaseFast (`u8` overflow on `+=`,
> `i8` `-128 / -1`, an out-of-range shift count). The test above would not pass
> today. G9 decides the release profile.

## Quick recommendations

1. **A7 is not C.** A7's type system already rules out most of what Fil-C and
   the sanitizers address: no `inttoptr`, no unrestricted unions, no recursion,
   slices instead of pointer arithmetic.
2. **The compile-time contract covers the rest.** Nullability, use-after-free,
   slice bounds, integer overflow, division by zero, allocation failure and
   stack overflow are each rejected statically or surfaced as a typed value the
   user must handle.
   *Note (2026-09-16): integer `+ - *` now wrap (L5) instead of being rejected.
   The proposed memory plan handles use-after-free and allocation without user
   allocation. Stack overflow has no computable model yet
   ([codex-review.md](./codex-review.md)).*
3. **The emitted Zig must be safe by shape, not by Zig flags.** A7 discharges
   each safety obligation, then lowers it to a Zig construct that cannot violate
   it. `-O ReleaseFast` is the test: if A7's claim holds, disabling every Zig
   runtime check changes nothing observable.
4. **Don't build a Fil-C clone.** Software capabilities handle pointer forgery
   in legacy C. A7 does not permit forgery, so the problem does not arise.
5. **Hardware flags harden non-A7 code, not A7 code.** PAC, BTI and CET protect
   linked C libraries and the kernel. A7-emitted code is meant to be safe by
   construction; the flags are a separate, additional defence.

The build order is in
[`05-for-a7.md` §5](./05-for-a7.md#5-phased-plan-zero-runtime-error-ordering).
The catalog of static techniques is in
[`06-compile-time-safety.md`](./06-compile-time-safety.md).
