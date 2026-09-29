# 04 — Approaches Compared

Status: comparison of the approaches in notes 01–03, written before
2026-09-14. Current A7 decisions are in the
[decision ledger](../plan/decisions.md).

Part of the `docs/lang-safety/` series ([README](./README.md)). Siblings:
[01 — InvisiCaps](./01-invisicaps.md) ·
[02 — Sanitizers](./02-sanitizers.md) ·
[03 — Hardware-assisted safety](./03-hardware.md) ·
[05 — Take-aways for A7](./05-for-a7.md).

This page condenses notes 01–03. Use it to pick the cheapest mechanism that
delivers a given safety property.

## 1. Coverage matrix

Legend: **Yes** deterministic · **Prob** probabilistic · **Part** partial or
opt-in · **No** none · **n/a** not applicable.

| | Spatial<br>(OOB) | Temporal<br>(UAF) | Init.<br>(read uninit) | Type<br>confusion | Concurrency<br>(races) | Forward CFI<br>(call hijack) | Backward CFI<br>(ret hijack) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Plain C (no checks) | No | No | No | No | No | No | No |
| ASan | Yes | Part (quarantine bypassable) | No | No | No | No | No |
| HWASAN | Prob (~6.25 % miss) | Prob | No | No | No | No | No |
| MSan | No | No | Yes | No | No | No | No |
| TSan | No | No | No | No | Yes | No | No |
| UBSan | Part (`-fsanitize=bounds`, static only) | No | Part (some) | Part (vptr, function) | No | Part (function) | No |
| CFI (`-fsanitize=cfi-*`) | No | No | No | Part (cast checks) | No | Yes | No |
| SafeStack | No | No | No | No | No | No | Part |
| ShadowCallStack | No | No | No | No | No | No | Yes |
| `-fbounds-safety` | Yes | No | No | No | No | No | No |
| Fil-C / InvisiCaps + FUGC | Yes | Yes | Yes (zero init) | Yes | Yes (atomic) | Yes (function caps) | Yes |
| MTE (sync mode) | Prob (4-bit) | Prob | No | No | Part | No | No |
| MTE + CET / PAC | Prob | Prob | No | No | Part | Yes | Yes |
| CHERI | Yes | Part (revocation sweep) | No | Part (sealed caps) | Part | Yes | Yes |
| Rust (safe subset) | Yes (compile time) | Yes | Yes | Yes | Yes (Send/Sync) | n/a | n/a |
| A7 (as written before 2026-09-14) | Part (no runtime checks emitted yet) | Part (no recursion + no UAF yet) | Part (no `undef` analog at codegen) | Yes (no unsafe casts) | Yes (no shared mutable; no threads yet) | n/a | n/a |

The original A7 row had one cell more than the table has columns. It is
shown here with the two concurrency cells merged.

> Note (2026-09-16): the A7 row is out of date. Checked against
> [SAFETY_CONTRACT](../SAFETY_CONTRACT.md), [STATUS](../STATUS.md),
> [SPEC](../SPEC.md), the [memory plan](../plan/memory.md) and the
> `a7/` source:
>
> | Property | Current A7 |
> | --- | --- |
> | Spatial | Compile-time proof, not runtime checks. Indexing needs a `usize` index proven `< len`, slicing needs `start <= end <= len`, or the compiler rejects the program. |
> | Temporal | Part. Direct use after `del` is rejected. Ownership and lifetime analysis is incomplete (SPEC §8.4). |
> | Init. | Part. Reading a variable that no path assigned is accepted after a zero-iteration loop (memory plan, gate M34). |
> | Type confusion | Part. Casts involving `ref` or function types are forbidden (`a7/cast_classifier.py`). Untagged unions allow reading any member, and union discriminant proofs are incomplete. |
> | Concurrency | n/a. The compiler has no thread support; concurrency is a deferred track. Ledger L1 puts concurrency in v1. |
> | CFI | Not assessed. A7 has stored function values (`examples/022`, `037`). |

## 2. Cost matrix

| Approach | CPU overhead | Memory overhead | Build cost | Where it pays off |
| --- | --- | --- | --- | --- |
| ASan | ~2× | ~3× | All TUs instrumented | CI / fuzzing / dev |
| HWASAN | ~1.5× | ~6 % | AArch64 / x86_64 LAM | Mobile fuzzing, prod hardening |
| MSan | ~3× (+ 1.5–2.5× origins) | ~2× | Whole-world rebuild | CI only |
| TSan | 2–20× | 5–10× | Whole-world rebuild | CI; concurrency-heavy code |
| UBSan (full) | < 5 % typ. | minimal | Per-TU opt-in | CI |
| UBSan (`-fsanitize-trap`) | ~0 % | 0 | Per-TU opt-in | Production |
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

> Note (2026-09-16): for A7, the "Optional GC" branch is ruled out.
> Ledger L15 requires automatic memory management with no runtime
> collector, resolved at compile time.

## 4. The four ideas worth stealing

Four techniques recur across notes 01–03. Any new language that wants strong
safety guarantees can reuse them.

### 4.1 Wide pointers when you can afford them, narrow pointers at ABI boundaries

This is the key idea of `-fbounds-safety`. Locals are wide
`(ptr, lower, upper)`. Struct fields and function parameters stay one word,
so the ABI does not change. Most of the cost lands in registers, not in
memory layout. Fil-C uses the same idea: flight pointers are wide, and
pointers at rest are narrow with the capability in a shadow.

### 4.2 Aux tables keyed by capability, not by address

SoftBound's flat, address-keyed shadow needs synchronization under threads,
which makes it expensive. Fil-C's per-object aux allocation is reached from
the capability, so it follows the capability's ownership: no extra locking
and no contention on a shared table. When a shadow table seems necessary,
ask whether it can be reached from the pointer's metadata instead.

### 4.3 Bounds-checking on slices is more useful than bounds-checking on pointers

Rust slices, Go slices, and `-fbounds-safety`'s `__counted_by` all make
"pointer + length" the primary aggregate type for arrays. Bounds checks move
from every pointer (expensive) to every slice access (cheap, and the
optimizer can hoist most of them out of loops).

A7 already has slices as a first-class type. The lesson is not to expose raw
pointers to user code at all. Keep them inside the compiler's lowering, where
the compiler can prove bounds statically.

```a7
// Current A7 (compiled 2026-09-16): rejected, exit 6,
// "index must satisfy 0 <= index < len: index bounds are not proven".
// SAFETY_CONTRACT requires a usize index proven < xs.len, but the safety
// pass does not derive that fact from an `if i < xs.len` guard on a slice
// parameter, whose length is not statically known. Same result as the
// verified example in 05-for-a7.md section 3.5.
get :: fn(xs: []i32, i: usize) i32 {
    if i < xs.len {
        ret xs[i]
    }
    ret 0
}
```

> Note (2026-09-16): current SPEC still exposes pointer-like surface:
> `slice.ptr`, and `mem_alloc`/`mem_free`/`mem_realloc` taking or
> returning `ref u8` ([SPEC](../SPEC.md) §3 Slices and §11). The proposed
> [memory plan](../plan/memory.md) removes these from the public surface
> and makes slices temporary views that cannot be stored or returned
> (gate M13). It is not yet approved.

### 4.4 Use-after-free needs a collector or a sweep

Static analysis cannot catch every use-after-free in code that lets pointers
escape into data structures. One of these is needed:

| Option | Examples |
| --- | --- |
| The runtime keeps freed capabilities alive until proven unreachable | Fil-C / FUGC; Cornucopia on CHERI |
| The language forbids the escape | Rust's borrow checker; no aliased mutable references |
| The hardware traps the access, probabilistically | MTE / HWASAN |

A7's recursion ban follows the second option: it shrinks the program set to
one where lifetime analysis can be total. The follow-on question, and the
main topic of note 05, is whether a little runtime help (for example
region-based allocation, or a single-cycle generational collector) simplifies
the type system enough to be worth it.

> Note (2026-09-16): superseded by ledger L15 and L17–L22. A7 memory will
> be automatic, resolved at compile time, and invisible to users, with no
> garbage collector and no reference counting. The proposed
> [memory plan](../plan/memory.md) follows the second option: the
> compiler places values in stack slots, arenas and pools, and rejects
> escapes such as stored or returned `ref` values and slices that outlive
> their owner. Stale handles use generation-tagged ids instead of pointers.
>
> ```a7
> // Proposed (from the memory plan; not current syntax)
> Node :: struct {
>     value: i32
>     parent: ?Id(Node)
> }
>
> Tree :: struct {
>     nodes: Table(Node)
> }
>
> main :: fn() {
>     tree := Tree{nodes: Table(Node){}}
>     root := tree.nodes.insert(Node{value: 1, parent: none})
>     child := tree.nodes.insert(Node{value: 2, parent: root})
>     tree.nodes.remove(child)
>     // looking up child now returns none, never another record
> }   // tree released here, iteratively
> ```

Continue to [05 — Take-aways for A7](./05-for-a7.md).
