# 03 — Hardware-assisted Memory Safety

Status: external-technology study notes on hardware safety features, written
before 2026-09-14. Current A7 decisions are in the
[decision ledger](../plan/decisions.md).

Part of the `docs/lang-safety/` series ([README](./README.md)). Siblings:
[01 — InvisiCaps](./01-invisicaps.md) ·
[02 — Sanitizers](./02-sanitizers.md) ·
[04 — Comparison](./04-comparison.md) ·
[05 — Take-aways for A7](./05-for-a7.md).

Moving safety checks into silicon changes two things:

- **Cost.** The per-access check drops to about one instruction, instead of
  a load, a branch, and a slow path.
- **Forgeability.** Software bugs cannot create valid metadata, because the
  metadata is outside software-visible address space.

This page covers three hardware lineages:

1. CHERI capabilities;
2. tagged memory: ARM MTE and SPARC ADI;
3. pointer-integrity primitives: ARM PAC and Intel CET.

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

CHERI is a long-running SRI/Cambridge research line that adds hardware
capabilities to a RISC instruction set. Every pointer carries tagged bounds
and permissions in both its register and memory form, and the CPU's
load/store pipeline enforces them. CHERI has been implemented on MIPS,
RISC-V, and AArch64 (the [Morello](https://www.arm.com/architecture/cpu/morello)
prototype).

### Encoding (CHERI Concentrate, the deployed form)

A capability is 128 bits plus 1 tag bit (129 in total). The 128 bits hold:

- a 64-bit virtual address;
- compressed base and top, relative to the address (about 12 bits or fewer
  each, using a floating-point-style encoding);
- permission bits (load, store, execute, capability-load, capability-store,
  seal, and others);
- an object type, for sealed capabilities (opaque tokens).

Software cannot see the tag bit. It lives in a separate metadata plane: ECC
bits, a dedicated tag cache, or a tag-aware memory controller. A
non-capability store to a memory word clears the tag; a capability-aware
store keeps it. This one rule makes capabilities unforgeable: no instruction
creates a tag bit except by copying an existing tagged value.

### Safety properties

| Property | Status |
| --- | --- |
| Spatial safety (bounds) | Yes: hardware-enforced |
| Pointer integrity (unforgeability) | Yes: tag bit |
| Permissions (W^X, read-only, etc.) | Yes: per pointer |
| Temporal safety (use-after-free) | Partial: software must revoke capabilities |
| Type safety | Partial: sealed capabilities give coarse types |

### CheriABI

CheriBSD runs a full POSIX userspace where every pointer in every C/C++
program is a CHERI capability. Most programs recompile without source
changes. Software revocation (Cornucopia, a CHERI sweeping revoker) fills the
temporal-safety gap.

### Cost

- Pointers double from 8 bytes to 16. Memory footprint and cache pressure
  both rise.
- A check costs about one instruction, because the hardware performs it.
  Deployed silicon shows single-digit-percent slowdowns on typical
  workloads.
- Tag-aware DRAM costs chip area: extra bits per cache line.

### Why it matters for software designers

CHERI is the upper bound of what a memory-safety model can promise for
legacy C. Software models (Fil-C, sanitizers) approximate what CHERI does in
hardware. CHERI also shows what software cannot do cheaply: unforgeable
pointers and near-free bounds checks both need hardware help.

### Relation to InvisiCaps

Fil-C calls itself "a software implementation of CHERI". Its trade-offs:
pointers stay 8 bytes wide, and FUGC provides temporal safety instead of
revocation sweeps. See
[01 — InvisiCaps §12](./01-invisicaps.md#12-how-it-compares-to-softbound-cheri-and-friends).

---

## 2. ARM Memory Tagging Extension (MTE)

### What it is

MTE is an optional Armv8.5-A extension that moves the
[HWASAN model](./02-sanitizers.md#5-hwaddresssanitizer-hwasan) into silicon.

### Mechanism

- Every 16-byte memory granule has a 4-bit physical tag, held by the memory
  controller or DRAM, outside software-visible address space.
- Every pointer has a 4-bit logical tag in bits 56–59 (or 59–62, depending
  on configuration) of the 64-bit virtual address. Top-byte ignore (TBI)
  hides the tag from the MMU.
- On every load and store the CPU checks `logical_tag == physical_tag`. A
  mismatch raises a synchronous tag-check fault.
- Only the tag-update instructions (`STG`, `ST2G`, `STGP`) rewrite a
  granule's physical tag. They have separate permission bits and are
  restricted to the allocator.

### Modes

| Mode | Behavior |
| --- | --- |
| `none` | MTE off |
| `synchronous (sync)` | A mismatch raises a precise fault at the offending instruction |
| `asynchronous (async)` | A mismatch sets a status-register flag, checked at context switch or fault boundary. Cheaper, less precise |
| `asymmetric (asymm)` | Sync for reads, async for writes |

Production deployments (Pixel 8+, recent Linux distributions) typically run
sync in debug builds and async in production.

### Safety properties

| Property | Status |
| --- | --- |
| Heap OOB (spatial) | Probabilistic: 1/16 false-negative per access |
| Heap use-after-free | Yes, if the allocator retags on free |
| Stack OOB / UAR | Partial: the compiler must opt in to stack tagging |
| Type confusion | No: the same tag policy applies to all uses |
| Concurrency | Partial: tag updates have their own ordering rules |

### Cost

- **CPU:** a few percent on Pixel-class silicon. The tag check sits in the
  load/store pipeline, so per-access overhead is negligible.
- **Memory:** 4 bits per 16-byte granule, a 3.1 % overhead.
- **Software:** the allocator and compiler must tag every allocation and
  retag on free. The kernel must carry tags through context switches.

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

CHERI is the larger undertaking. MTE is deployable today, with weaker
guarantees.

---

## 3. SPARC ADI (Oracle)

ADI (Application Data Integrity) is similar to MTE and shipped earlier, on
SPARC M7/M8. Each 64-byte cache line carries a 4-bit version, and 4 bits of
the virtual address hold the expected version. A mismatch traps.

ADI predates MTE by about 5 years and showed that tagged-memory silicon works
at production scale. SPARC's commercial line has ended, so ADI is now mostly
historical, but its design influenced both MTE and HWASAN.

---

## 4. Intel LAM and CET

### Linear Address Masking (LAM)

LAM is Intel's analog of ARM TBI: configurable masking of the top bits of
virtual addresses, so software can use them as tags. It first shipped on
Sapphire Rapids. User-space LAM (bits 62–48) enables HWASAN-style software
tagging on x86_64. LAM is not a memory-safety feature by itself; it only
makes address tags possible.

### Control-flow Enforcement Technology (CET)

CET has two primitives:

| Primitive | Mechanism | Software analog |
| --- | --- | --- |
| Shadow Stack (SHSTK) | The hardware keeps a shadow copy of every return address. `RET` compares the two; a mismatch faults. Zero overhead. Ships on most recent Intel and AMD CPUs. | LLVM [ShadowCallStack](./02-sanitizers.md#9-side-family-safestack-shadowcallstack-pac) |
| Indirect Branch Tracking (IBT) | Indirect call and jump targets must start with `ENDBR64`; otherwise the CPU faults. Coarse but effective forward-edge CFI. | LLVM `cfi-icall` |

Both are integrity primitives. They make exploitation harder; they do not
catch the underlying bug.

---

## 5. ARM Pointer Authentication (PAC)

### What it does

PAC signs return addresses, function pointers, and optionally data pointers
with a hardware MAC under a per-process key. If the pointer is changed, the
signature no longer verifies. The verify instruction then returns an invalid
(non-canonical) pointer that faults on dereference.

### Mechanism

- **Keys.** Five secret keys live in EL1/EL2 system registers: `APIA`,
  `APIB`, `APDA`, `APDB`, `APGA`. Userspace cannot read them.
- **Sign.** `PACIA`, `PACIB`, `PACDA`, `PACDB`, `PACGA` combine the pointer, a
  64-bit context (typically the stack pointer), and the key into a tweakable
  MAC stored in the top 16 unused address bits.
- **Verify.** `AUTIA`, `AUTIB`, `AUTDA`, `AUTDB` recompute the MAC. On a
  match they restore the bare pointer; on a mismatch they set those bits to a
  poisoned pattern.
- **Compiler integration.** `-mbranch-protection=pac-ret` signs the return
  address in every function prologue (`PACIASP`) and verifies it in the
  epilogue (`AUTIASP`).

### Cost

Near zero. Signing and verifying are single instructions that pipeline well.
Apple M-series and recent Cortex-A chips ship PAC, enabled by default in iOS
and macOS.

### Threat model

PAC stops an attacker from forging a changed version of a pointer the
program signed. It does not stop:

- replaying a valid signed pointer in the wrong place (cross-context attacks;
  a good context such as `sp` mitigates this);
- creating a new pointer the program never signed. CHERI and MTE address
  that.

Use PAC together with CFI/CET and a memory-safe allocator, not as a
replacement for memory safety.

---

## 6. Putting hardware into a software language design

For A7 or any AOT-compiled language with an LLVM backend (A7 lowers through
Zig, which uses LLVM), the practical question is which of these features can
be enabled for free.

The 2026 baseline:

| Feature | Where it lives | Action |
| --- | --- | --- |
| AArch64 PAC return-signing | `-mbranch-protection=pac-ret` in LLVM | Emit when targeting AArch64 |
| AArch64 BTI (forward CFI) | `-mbranch-protection=bti` | Emit when targeting AArch64 |
| Intel CET SHSTK | `-fcf-protection=return` | Emit when targeting x86_64 with CET |
| Intel CET IBT | `-fcf-protection=branch` | Same |
| MTE | Allocator + compiler integration | Out of scope for a high-level language; a library concern |
| CHERI | Whole-platform recompile | Out of scope unless targeting CheriBSD/Morello |

Enabling the flags is easy. The hard part is keeping the language's pointer
semantics consistent with the hardware:

| Hardware | Language requirement | If violated |
| --- | --- | --- |
| PAC | Return addresses are never observable as integers in user code | PAC breaks |
| CHERI | Pointer arithmetic stays within bounds at the language level | CHERI stops the program instead of allowing the exploit |
| MTE | The allocator retags on free | The language loses use-after-free detection |

A language that forbids minting pointers from integers and controls its own
allocator can turn these features on mostly by passing the right flags
through the backend. The original text claimed A7 does both ("no unsafe
casts, runtime owns memory"). See
[05 — Take-aways for A7](./05-for-a7.md) for the concrete plan.

> Note (2026-09-16): half of that claim is stale.
>
> - **Casts:** still true. Casts involving `ref` or function types are
>   forbidden ([`a7/cast_classifier.py`](../../a7/cast_classifier.py)).
> - **Memory:** A7 has no runtime (see `CLAUDE.md`). Today heap memory is
>   manual: `new` returns a nullable `ref`, and the program frees it with
>   `del` or `defer del` ([SPEC §8.2](../SPEC.md),
>   [SAFETY_CONTRACT](../SAFETY_CONTRACT.md)). SPEC also lists
>   `slice.ptr` and `mem_alloc`/`mem_free` returning `ref u8`.
> - **Direction:** ledger L15 and L17–L22 make memory automatic and
>   resolved at compile time, with no runtime collector. The proposed
>   [memory plan](../plan/memory.md) lowers placement to stack slots,
>   arenas and pools, and removes `new`, `del` and `slice.ptr` from the
>   public surface. It is not yet approved.
> - **Backend:** A7 passes only a Zig `-O` mode today
>   ([`scripts/build_examples.py`](../../scripts/build_examples.py)). The
>   flags in the table above are clang/LLVM spellings; the matching Zig
>   options were not checked for this note.
>
> ```a7
> // Current A7 (from SPEC §8.2): manual heap reference.
> // Compiled 2026-09-16 in the complete form below: accepted (exit 0).
> // The statements must sit inside a function. At file scope the compiler
> // still exits 0 but silently drops them and emits no `main`.
> Box :: struct {
>     value: i32
> }
>
> main :: fn() {
>     box := new Box
>     if box == nil {
>         ret
>     }
>     box.value = 42
>     del box
> }
> ```

Continue to [04 — Comparison](./04-comparison.md) for a one-page side-by-side
view.
