# 03 — Hardware-assisted Memory Safety

> Part of the `docs/lang-safety/` series. See the
> [README](./README.md) for the full map. Siblings:
> [01 — InvisiCaps](./01-invisicaps.md) ·
> [02 — Sanitizers](./02-sanitizers.md) ·
> [04 — Comparison](./04-comparison.md) ·
> [05 — Take-aways for A7](./05-for-a7.md).

When the safety machinery moves into silicon, two things change:

- The per-access tax drops to roughly *zero* (one instruction instead of
  load + branch + slow path).
- The guarantee becomes *unforgeable* — software bugs cannot synthesize
  valid metadata, because the metadata isn't in software-visible
  address space.

This page covers the three hardware lineages that matter to a 2026 lang
designer: **CHERI capabilities**, **ARM MTE / SPARC ADI tagged memory**,
and the **pointer-integrity primitives** (ARM PAC, Intel CET).

Primary sources:

- [CHERI project page (Cambridge)](https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/)
- [CHERI FAQ](https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/cheri-faq.html)
- [Morello (Arm)](https://www.arm.com/architecture/cpu/morello)
- [ARM MTE overview](https://developer.arm.com/documentation/108035/0100/Introduction-to-the-Memory-Tagging-Extension)
- [HWASAN paper (arXiv 1802.09517)](https://arxiv.org/pdf/1802.09517.pdf)
- [Intel LAM programming reference](https://software.intel.com/content/www/us/en/develop/download/intel-architecture-instruction-set-extensions-programming-reference.html)
- [SPARC ADI overview](https://lazytyped.blogspot.com/2017/09/getting-started-with-adi.html)
- [Linux ARM64 tagged pointers](https://www.kernel.org/doc/Documentation/arm64/tagged-pointers.txt)

---

## 1. CHERI — Capability Hardware Enhanced RISC Instructions

### What it is

A multi-decade research line out of SRI/Cambridge that adds **hardware
capabilities** to a RISC ISA. Every pointer carries cryptographic-tagged
bounds and permissions in the *register* and *memory* representation,
and the MMU/load-store pipeline enforces them. The ISA has been
implemented on top of MIPS, RISC-V, and AArch64 (the
[Morello](https://www.arm.com/architecture/cpu/morello) prototype).

### Encoding (CHERI Concentrate, the deployed form)

A capability is **128 bits + 1 tag bit** (129 total). The 128 bits pack:

- 64-bit virtual address
- Compressed base / top (relative to address; ≤ ~12 bits each via
  floating-point-style encoding)
- Permission bits (load, store, execute, capability-load, capability-store,
  seal, …)
- Object type (for sealed capabilities — opaque tokens)

The tag bit is **invisible to software** — it lives in a separate
metadata plane (ECC bits, dedicated tag cache, or a tag-aware memory
controller). Any non-capability store to a memory word clears the tag;
capability-aware stores preserve it. That single mechanism is what makes
capabilities *unforgeable*: there is no instruction that synthesizes a
tag bit other than from an existing tagged value.

### Safety properties

| Property | Status |
| --- | --- |
| Spatial safety (bounds) | ✅ Hardware-enforced |
| Pointer integrity (unforgeability) | ✅ Tag bit |
| Permissions (W^X, read-only, etc.) | ✅ Per-pointer |
| Temporal safety (use-after-free) | ⚠️ Software responsibility (must revoke capabilities) |
| Type safety | ⚠️ Limited; sealed capabilities give coarse-grained types |

### CheriABI

CheriBSD demonstrates a full POSIX userspace where **every pointer in
every C/C++ program** is a CHERI capability. Most programs recompile
with no source changes. The temporal-safety gap is filled by software
revocation (Cornucopia / a CHERI sweeping revoker).

### Cost

- Pointer width doubles: 8 bytes → 16 bytes. Memory footprint and cache
  pressure both rise.
- Per-access cost is one instruction (the hardware already does the
  check); the deployed silicon shows single-digit-percent slowdowns on
  typical workloads.
- Tag-aware DRAM is a real chip cost — extra bits per cache line.

### Why it matters for software designers

CHERI is the **upper bound** of what a memory-safety model can promise
on legacy C. Any software model (Fil-C, sanitizers) is approximating
something CHERI does in hardware. The model also tells you what
*can't* be done cheaply in software: unforgeable pointers and
zero-overhead bounds checks both want hardware help.

### Relation to InvisiCaps

Fil-C explicitly bills itself as "a software implementation of CHERI"
with the trade-offs that pointer width stays at 8 bytes and temporal
safety is solved by FUGC instead of revocation sweeps. See
[01 — InvisiCaps §12](./01-invisicaps.md#12-how-it-compares-to-softbound-cheri-and-friends).

---

## 2. ARM Memory Tagging Extension (MTE)

### What it is

A v8.5-A optional extension that takes the [HWASAN
model](./02-sanitizers.md#5-hwaddresssanitizer-hwasan) and moves it
into silicon.

### Mechanism

- Every 16-byte memory granule has an associated **4-bit physical
  tag** held by the memory controller / DRAM (not in software-visible
  address space).
- Every pointer has a **4-bit logical tag** in bits 56–59 (or 59–62
  depending on configuration) of the 64-bit virtual address.
  Address-tagging (TBI) hides this from the MMU.
- The CPU checks `logical_tag == physical_tag` on every load and store.
  Mismatch raises a synchronous tag-check fault.
- Tag-update instructions (`STG`, `ST2G`, `STGP`) are the only way to
  rewrite a granule's physical tag — these have separate permission
  bits and are restricted to the allocator.

### Modes

| Mode | Behavior |
| --- | --- |
| `none` | MTE off |
| `synchronous (sync)` | Tag mismatch raises a precise fault at the offending instruction |
| `asynchronous (async)` | Mismatch sets a status register flag; checked at context switch / fault boundary. Cheaper, less precise. |
| `asymmetric (asymm)` | Sync for reads, async for writes |

Production deployments (Pixel 8+, recent Linux distros) typically run
sync in debug builds and async in production for performance.

### Safety properties

| Property | Status |
| --- | --- |
| Heap OOB (spatial) | ✅ Detected probabilistically (1/16 false-negative per access) |
| Heap use-after-free | ✅ If allocator retags on free |
| Stack OOB / UAR | ⚠️ Compiler must opt in to stack tagging |
| Type confusion | ❌ Same tag policy applies to all uses |
| Concurrency | ⚠️ Tag updates have their own ordering rules |

### Cost

- Hardware: a few percent on Pixel-class silicon. Negligible per-access
  overhead because tag check is in the load/store pipeline.
- Memory: 4 bits per 16-byte granule = **3.1 %** overhead.
- Software: allocator and compiler need to tag every allocation and
  retag on free. The kernel needs to plumb tags through context
  switches.

### Comparison to CHERI

| Dimension | CHERI | MTE |
| --- | --- | --- |
| Pointer width | 16 B | 8 B (logical tag in top bits) |
| Bounds carried by | Pointer | Allocation tag |
| Per-allocation bound | Exact | Granule-aligned (16 B) |
| Detection | Deterministic | Probabilistic (4-bit collision) |
| Unforgeable? | Yes (tag bit invisible) | Yes (physical tag stored in DRAM) |
| Use-after-free | Software (revocation sweep) | Software (allocator retags) |
| Chip support today | Morello, CHERIoT | Pixel 8+, Apple A-series (some), recent Cortex-A |

CHERI is the bigger lift; MTE is the *deployable today* version with
weaker guarantees.

---

## 3. SPARC ADI (Oracle)

ADI ("Application Data Integrity") is conceptually similar to MTE,
shipped earlier on SPARC M7/M8. Each 64-byte cache line carries a
4-bit version, and 4 bits of the virtual address store the expected
version. Mismatch traps.

ADI predates MTE by ~5 years and is the proof that **tagged-memory
silicon works at production scale**. It's mostly of historical interest
now — SPARC's commercial trajectory ended — but the design influenced
both MTE and HWASAN.

---

## 4. Intel LAM and CET

### Linear Address Masking (LAM)

Intel's analog of ARM TBI: configurable masking of the top bits of
virtual addresses so software can use them as tags. Shipped first on
Sapphire Rapids; user-space LAM (bits 62–48) enables HWASAN-style
software memory tagging on x86_64. Not a memory-safety feature on its
own — just the address-tag enabler.

### Control-flow Enforcement Technology (CET)

Two related primitives:

- **Shadow Stack (SHSTK).** Hardware-maintained shadow of every return
  address. `RET` checks the call/shadow pair; mismatch ⇒ fault. The
  silicon version of LLVM's
  [ShadowCallStack](./02-sanitizers.md#9-side-family-safestack-shadowcallstack-pac).
  Zero overhead. Ships on most recent Intel and AMD CPUs.
- **Indirect Branch Tracking (IBT).** Indirect call/jump targets must
  begin with an `ENDBR64` instruction; mismatch ⇒ fault. A coarse but
  effective forward-edge CFI primitive in hardware. The silicon analog
  of LLVM's `cfi-icall`.

Both are *integrity* primitives, not bug detectors. They make
exploitation harder rather than catching the underlying bug.

---

## 5. ARM Pointer Authentication (PAC)

### What it does

Signs **return addresses, function pointers, and (optionally) data
pointers** with a hardware MAC using a per-process key. Tamper with the
pointer and the signature no longer verifies; the auth instruction
returns an invalid (canonical-form) pointer that segfaults on
dereference.

### Mechanism

- Five secret keys live in EL1 / EL2 system registers: `APIA`, `APIB`,
  `APDA`, `APDB`, `APGA`. Userspace cannot read them.
- Sign instructions: `PACIA`, `PACIB`, `PACDA`, `PACDB`, `PACGA`. They
  combine the pointer, a 64-bit context (typically the stack pointer),
  and the key into a tweakable MAC that occupies the top 16 unused
  bits of the address.
- Auth instructions: `AUTIA`, `AUTIB`, `AUTDA`, `AUTDB`. They re-compute
  the MAC and either restore the bare pointer (on match) or set those
  bits to a poisoned pattern (on mismatch).
- Compiler integration: `-mbranch-protection=pac-ret` signs the return
  address on every function prologue (`PACIASP`) and authenticates on
  epilogue (`AUTIASP`).

### Cost

Effectively zero — sign and auth are single instructions that pipeline
fine. Apple's M-series and recent Cortex-A ship with PAC enabled by
default in iOS / macOS.

### Threat model

PAC defends against **forging** a pointer the program previously had.
It does *not* defend against:

- Replaying a valid signed pointer in the wrong place (cross-context
  attacks; mitigated by good context choice — typically `sp`).
- Forging a *new* pointer the program never signed (which is what
  CHERI/MTE close).

Use PAC alongside CFI/CET and a memory-safe allocator. Don't use it
*instead of* memory safety.

---

## 6. Putting hardware into a software language design

For A7 (this codebase) or any new AOT-compiled language whose backend
is LLVM (or, like A7, lowers through Zig which then uses LLVM), the
practical question is: **which of these features can you turn on for
free?**

The 2026 baseline answer:

| Feature | Where it lives | Action |
| --- | --- | --- |
| AArch64 PAC return-signing | `-mbranch-protection=pac-ret` in LLVM | Emit when targeting AArch64 |
| AArch64 BTI (forward CFI) | `-mbranch-protection=bti` | Emit when targeting AArch64 |
| Intel CET SHSTK | `-fcf-protection=return` | Emit when targeting x86_64 with CET |
| Intel CET IBT | `-fcf-protection=branch` | Same |
| MTE | Allocator + compiler integration | Out of scope for a high-level lang; library concern |
| CHERI | Whole-platform recompile | Out of scope unless targeting CheriBSD/Morello |

The hard part isn't enabling these flags — it's keeping the language's
own pointer semantics consistent with the hardware's. PAC requires that
return addresses are *not* observable as integers in user code (or PAC
breaks). CHERI requires that pointer arithmetic stays within bounds at
the language level (or CHERI breaks the program rather than allowing the
exploit). MTE requires the allocator to retag on free (or the language
loses use-after-free detection).

For a language that does *not* let user code mint pointers from
integers and *does* control its own allocator (A7 does both: no
unsafe casts, runtime owns memory), turning on the hardware safety
features is mostly a matter of emitting the right LLVM flags through
the backend. See [05 — Take-aways for A7](./05-for-a7.md) for the
concrete plan.

Continue to [04 — Comparison](./04-comparison.md) for a single-page
side-by-side.
