# 04 — Approaches Compared

> Part of the `docs/lang-safety/` series. See the
> [README](./README.md) for the full map. Siblings:
> [01 — InvisiCaps](./01-invisicaps.md) ·
> [02 — Sanitizers](./02-sanitizers.md) ·
> [03 — Hardware-assisted safety](./03-hardware.md) ·
> [05 — Take-aways for A7](./05-for-a7.md).

One page that condenses the previous three. The job of this page is to
let you pick, for any given safety property, the cheapest mechanism
that delivers it.

## 1. Coverage matrix

✅ deterministic · 🟡 probabilistic · ⚠️ partial / requires opt-in · ❌ none

| | Spatial<br>(OOB) | Temporal<br>(UAF) | Init.<br>(read uninit) | Type<br>confusion | Concurrency<br>(races) | Forward CFI<br>(call hijack) | Backward CFI<br>(ret hijack) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Plain C (no checks)** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **ASan** | ✅ | ⚠️ (quarantine bypassable) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **HWASAN** | 🟡 (~6.25 %) | 🟡 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **MSan** | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **TSan** | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **UBSan** | ⚠️ (`-fsanitize=bounds`, static only) | ❌ | ⚠️ (some) | ⚠️ (vptr, function) | ❌ | ⚠️ (function) | ❌ |
| **CFI (`-fsanitize=cfi-*`)** | ❌ | ❌ | ❌ | ⚠️ (cast checks) | ❌ | ✅ | ❌ |
| **SafeStack** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ |
| **ShadowCallStack** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **`-fbounds-safety`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Fil-C / InvisiCaps + FUGC** | ✅ | ✅ | ✅ (zero init) | ✅ | ✅ (atomic) | ✅ (function caps) | ✅ |
| **MTE (sync mode)** | 🟡 (4-bit) | 🟡 | ❌ | ❌ | ⚠️ | ❌ | ❌ |
| **MTE + CET / PAC** | 🟡 | 🟡 | ❌ | ❌ | ⚠️ | ✅ | ✅ |
| **CHERI** | ✅ | ⚠️ (revocation sweep) | ❌ | ⚠️ (sealed caps) | ⚠️ | ✅ | ✅ |
| **Rust (safe subset)** | ✅ (compile time) | ✅ | ✅ | ✅ | ✅ (Send/Sync) | n/a | n/a |
| **A7 (current, static)** | ⚠️ (no runtime checks emitted yet) | ⚠️ (no recursion + no UAF yet) | ⚠️ (no `undef` analog at codegen) | ✅ (no unsafe casts) | ✅ (no shared mutable) | ✅ (no threads yet) | n/a | n/a |

## 2. Cost matrix

| Approach | CPU overhead | Memory overhead | Build cost | Where it pays off |
| --- | --- | --- | --- | --- |
| ASan | ~2× | ~3× | All TUs instrumented | CI / fuzzing / dev |
| HWASAN | ~1.5× | ~6 % | AArch64 / x86_64 LAM | Mobile fuzzing, prod hardening |
| MSan | ~3× (+ 1.5–2.5× origins) | ~2× | Whole-world rebuild | CI only |
| TSan | 2–20× | 5–10× | Whole-world rebuild | CI; concurrency-heavy code |
| UBSan (full) | < 5 % typ. | minimal | Per-TU opt-in | CI |
| UBSan (`-fsanitize-trap`) | ~0 % | 0 | Per-TU opt-in | **Production** |
| CFI (vcall) | < 1 % | up to 15 % binary | Requires LTO | Production |
| SafeStack | < 0.1 % | small | Per-TU opt-in | Production |
| ShadowCallStack | small | small | Per-TU opt-in | Production (Android) |
| PAC | ~0 % | 0 | AArch64 only | Production (default on Apple) |
| `-fbounds-safety` | low (single-digit %) | wide-ptr locals only | Annotation effort | Production (Apple OS) |
| Fil-C | 1.5–4× | small per-object aux | clang fork | Memory-safe ports of C |
| MTE (async) | few % | 3.1 % | Allocator + kernel | Production (Pixel 8+) |
| CHERI / Morello | low single-digit % | 2× pointer width | New ISA / port | Research; CheriBSD |
| Rust safe | 0 % | 0 | Whole-program type-check | New code |

## 3. Decision tree

```
Are you writing a NEW language, or hardening EXISTING C?
│
├── NEW language
│   │
│   ├── Want zero runtime cost?
│   │     → Static safety (Rust-style borrow/ownership)
│   │       + emit hardware CFI/PAC/CET flags through the backend.
│   │
│   └── Need runtime checks for unavoidable dynamic cases?
│         → Wide pointers for slices/dynamic arrays (`-fbounds-safety` style).
│         → Optional GC for cycles / lifetimes you can't prove.
│         → Optional UBSan-trap on emitted code as a belt-and-braces.
│
└── EXISTING C
    │
    ├── Have hardware? (Morello / MTE phone / CET CPU)
    │     → Use the hardware: CHERI, MTE-sync in dev / MTE-async in prod,
    │       CET + PAC always on.
    │
    ├── Want zero source changes and full safety?
    │     → Fil-C (recompile with the FilPizlonator clang fork).
    │
    └── Want incremental adoption?
          → ASan + MSan + UBSan in CI.
          → UBSan-trap, CFI, SafeStack/SCS, PAC in production.
          → `-fbounds-safety` annotations on hot data structures.
```

## 4. The four ideas worth stealing

After reading the three primary docs side by side, there are four
recurring techniques. Any new language design that wants strong safety
guarantees can reuse them.

### 4.1 Wide pointers when you can afford them, narrow pointers at ABI boundaries

This is `-fbounds-safety`'s key insight. Locals are wide
`(ptr, lower, upper)`; struct fields and function parameters stay
single-word so the ABI doesn't change. Most of the cost is paid in
*registers*, not in *memory layout*. The same idea drives Fil-C: flight
pointers are wide, pointers at rest are narrow with the capability in a
shadow.

### 4.2 Aux tables keyed by capability, not by address

SoftBound's flat address-keyed shadow needs synchronization under
threads, which is why it's expensive. Fil-C's per-object aux allocation
is reachable *from the capability*, so it inherits the capability's
ownership — no extra locking, no shared shadow table contention.
Whenever a shadow table seems necessary, ask whether it can be reached
from the pointer's metadata instead.

### 4.3 Bounds-checking on slices is more useful than bounds-checking on pointers

The Rust slice / Go slice / `-fbounds-safety __counted_by` patterns all
encode "pointer + length" as the *primary* aggregate type for arrays.
That moves bounds checking from "every pointer" (expensive) to "every
slice access" (cheap, and the optimizer can hoist most of them out of
loops). A7 already has slices as a first-class type. The lesson is to
*not* expose raw pointers to user code at all — keep them inside the
runtime where the compiler can prove bounds statically.

### 4.4 Use-after-free needs a collector or a sweep

No amount of static analysis catches every UAF in code that lets
pointers escape into data structures. Either:

- The runtime keeps freed capabilities alive until proven unreachable
  (Fil-C / FUGC, Cornucopia on CHERI).
- The language forbids the escape (Rust's borrow checker, ban on
  aliasing mutable references).
- The hardware traps the access (MTE / HWASAN — probabilistically).

A7's existing recursion ban is in the spirit of the second option:
shrink the set of programs to one where the lifetime analysis can be
total. The follow-on question — and §05's main topic — is whether a
small amount of runtime help (e.g. region-based allocation, or a
single-cycle generational collector) buys enough simplicity in the
type system to be worth it.

Continue to [05 — Take-aways for A7](./05-for-a7.md).
