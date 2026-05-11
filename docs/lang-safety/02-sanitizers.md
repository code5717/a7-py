# 02 — Runtime Sanitizers

> Part of the `docs/lang-safety/` series. See the
> [README](./README.md) for the full map. Siblings:
> [01 — InvisiCaps](./01-invisicaps.md) ·
> [03 — Hardware-assisted safety](./03-hardware.md) ·
> [04 — Comparison](./04-comparison.md) ·
> [05 — Take-aways for A7](./05-for-a7.md).

The Clang/LLVM sanitizers are the most widely-deployed memory-safety
tooling in production C and C++. They are *not* full memory-safety
languages — they are debug instruments that turn many UB conditions into
deterministic crashes. Their algorithms are the practical baseline that
any new language's safety story has to clear.

Primary sources:

- <https://github.com/google/sanitizers> — Google's sanitizers (archived;
  active code now lives in `compiler-rt` under LLVM)
- <https://github.com/google/sanitizers/wiki/AddressSanitizer> and
  [`AddressSanitizerAlgorithm`](https://github.com/google/sanitizers/wiki/AddressSanitizerAlgorithm)
- <https://github.com/google/sanitizers/wiki/MemorySanitizer>
- <https://github.com/google/sanitizers/wiki/AddressSanitizerLeakSanitizer>
- <https://github.com/google/sanitizers/wiki/ThreadSanitizerCppManual>
- <https://clang.llvm.org/docs/HardwareAssistedAddressSanitizerDesign.html>
- <https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html>
- <https://clang.llvm.org/docs/ControlFlowIntegrity.html>
- <https://clang.llvm.org/docs/BoundsSafety.html>
- <https://clang.llvm.org/docs/index.html> (index of all sanitizers)
- [ASan USENIX ATC 2012 paper](https://www.usenix.org/system/files/conference/atc12/atc12-final39.pdf)
- [HWASAN arXiv paper](https://arxiv.org/pdf/1802.09517.pdf)

## Table of Contents

1. [AddressSanitizer (ASan)](#1-addresssanitizer-asan)
2. [LeakSanitizer (LSan)](#2-leaksanitizer-lsan)
3. [MemorySanitizer (MSan)](#3-memorysanitizer-msan)
4. [ThreadSanitizer (TSan)](#4-threadsanitizer-tsan)
5. [HWAddressSanitizer (HWASAN)](#5-hwaddresssanitizer-hwasan)
6. [UndefinedBehaviorSanitizer (UBSan)](#6-undefinedbehaviorsanitizer-ubsan)
7. [Control Flow Integrity (CFI)](#7-control-flow-integrity-cfi)
8. [`-fbounds-safety`](#8--fbounds-safety)
9. [Side family: SafeStack, ShadowCallStack, PAC](#9-side-family-safestack-shadowcallstack-pac)
10. [Common limitations and what they tell us](#10-common-limitations-and-what-they-tell-us)

---

## 1. AddressSanitizer (ASan)

### Bug classes detected

- Out-of-bounds heap / stack / global access
- Use-after-free, use-after-return, use-after-scope
- Double-free, invalid free
- Initialization-order fiasco
- (Through integrated LSan) memory leaks

### Algorithm — shadow memory at 1:8

ASan reserves a shadow region where one byte of shadow describes the
addressability of 8 bytes of application memory. The mapping (64-bit
Linux):

```
Shadow = (Mem >> 3) + 0x7fff8000
```

Memory layout:

| Region | Range |
| --- | --- |
| LowMem | `0x000000000000–0x00007fff7fff` |
| LowShadow | `0x00007fff8000–0x00008fff6fff` |
| ShadowGap | `0x00008fff7000–0x02008fff6fff` |
| HighShadow | `0x02008fff7000–0x10007fff7fff` |
| HighMem | `0x10007fff8000–0x7fffffffffff` |

The ShadowGap is mapped `PROT_NONE` so any attempt to dereference the
shadow of the shadow itself segfaults — that's how the runtime detects
its own bugs.

### Shadow byte values

| Value | Meaning |
| --- | --- |
| `0x00` | All 8 bytes are addressable |
| `0x01–0x07` | The first `k` bytes are addressable; the remaining `8-k` are poisoned |
| `0xfa` | Heap left redzone |
| `0xfb` | Heap right redzone |
| `0xfd` | Heap freed (quarantine) |
| `0xf1` | Stack left redzone |
| `0xf2` | Stack mid redzone |
| `0xf3` | Stack right redzone |
| `0xf5` | Stack-use-after-return |
| `0xf6` | Stack-use-after-scope |
| `0xf9` | Global redzone |

### Instrumentation

Before every memory access of size `kAccessSize` (1, 2, 4, 8, or 16):

```c
byte *shadow_address = MemToShadow(address);
byte  shadow_value   = *shadow_address;
if (shadow_value) {
    if (SlowPathCheck(shadow_value, address, kAccessSize)) {
        ReportError(address, kAccessSize, kIsWrite);
    }
}
```

The slow-path check handles partial poisoning of a granule:

```c
size_t last_accessed_byte = (address & 7) + kAccessSize - 1;
return last_accessed_byte >= shadow_value;
```

Two loads + a branch on the fast path. The branch is almost always
not-taken, so on a modern CPU the instrumentation is mostly a few cycles
per access.

### malloc / free / quarantine

- **malloc** allocates the requested size *plus* redzones (typically 32
  bytes on either side), poisons the redzone shadow bytes, and clears
  the user-region shadow.
- **free** poisons the entire chunk's shadow with `0xfd` and pushes it
  into a *quarantine* queue. Quarantined chunks are not reused until
  they age out, so use-after-free is caught for a tunable window.
  Quarantine size defaults to 256 MB.

### Stack and global redzones

For a function with a local `char a[8];`, the compiler emits:

```c
char redzone1[32];   // 32-byte aligned
char a[8];           // 32-byte aligned
char redzone2[24];
char redzone3[32];   // 32-byte aligned
```

and initializes shadow bytes around `a` accordingly. On return, all
shadow bytes are reset. Globals are surrounded by similar redzones at
link time.

### Performance

> "The average slowdown of the instrumented program is ~2×."

Memory overhead is roughly **3×** in practice (1× for the program, 1/8×
for shadow, ~2× for redzones + quarantine). Mac and Linux x86_64 are the
best-supported targets.

### Flags worth knowing

- `-fsanitize=address` — enable
- `-O1` or higher recommended
- `-fno-omit-frame-pointer` — better stack traces
- `-g` — symbolized output
- `ASAN_OPTIONS=halt_on_error=0` — continue after the first error
- `ASAN_OPTIONS=detect_leaks=1` — integrated leak detection (default on
  Linux x86_64)
- `ASAN_OPTIONS=quarantine_size_mb=N` — tune the quarantine window
- `ASAN_OPTIONS=verbosity=1` — diagnostic noise

---

## 2. LeakSanitizer (LSan)

LSan is the leak detector inside (or alongside) ASan. It is essentially
a **mark-and-sweep run at process exit** that reports any heap chunk
that no live pointer references.

- Roots: global and TLS sections, every thread's stack and registers.
- Marker: scans each root word-by-word, treating any value that looks
  like a chunk pointer as a heap reference.
- Sweep: every heap chunk not reachable from any root is reported as a
  *direct* or *indirect* leak.

Modes:

- **Integrated** with ASan: default on x86_64 Linux. On macOS, enable via
  `ASAN_OPTIONS=detect_leaks=1`.
- **Stand-alone**: `-fsanitize=leak` without ASan; lighter weight but less
  battle-tested.

Flags via `LSAN_OPTIONS`:

- `exitcode=23` — exit code on detected leak (default 23)
- `max_leaks=N` — report only top N
- `suppressions=/path` — suppression file; entries look like
  `leak:FunctionName`, anchored with `^` / `$`
- `report_objects=1` — list individual leaked objects with addresses

LSan misses leaks of objects still reachable from a global, even if
nothing will ever use them ("dead" but not "lost").

---

## 3. MemorySanitizer (MSan)

### What it detects

Uninitialized reads — the things ASan can't see because the memory *is*
addressable, just full of garbage.

### Algorithm

- A separate shadow region tracks **uninitialized bits** with bit-exact
  precision. One bit of shadow per application bit; a shadow bit of 1
  means "this bit is poisoned (uninitialized)".
- Arithmetic, logic, and copies **propagate** the poison rather than
  warning. The poison spreads silently through every derived value.
- A warning is issued only when poison influences observable behavior:
  - A conditional branch on a poisoned value.
  - A poisoned address used as a pointer (load / store).
  - A poisoned value passed to or returned from an *uninstrumented*
    function (typically libc).

This "report on use, not on copy" rule is what keeps the false-positive
rate manageable.

### Origin tracking

`-fsanitize-memory-track-origins` (and the deeper
`-fsanitize-memory-track-origins=2`) records the allocation site of
every poisoned value and propagates that origin with the data. The
warning then includes the chain "this came from `new int[10]` at
file:line, was copied here, was copied there, finally read at file:line".

### Cost

- ~3× slowdown without origin tracking.
- Additional **1.5×–2.5×** on top with origin tracking.
- Whole-program build requirement: every translation unit, including
  libc++ and libstdc++, must be MSan-instrumented or MSan will report
  false positives on stdlib internals. There are pre-built MSan-clean
  libstdc++ images and a documented libc++ workflow.

### Example

```c
int* a = new int[10];
a[5] = 0;
if (a[argc])      // UMR: a[1..argc-1] never written
    printf("xx\n");
```

```
==6726== WARNING: MemorySanitizer: UMR (uninitialized-memory-read)
    #0 0x7fd1c2944171 in main umr.cc:6
```

With origin tracking, the trace includes the originating `new int[10]`
call site.

### Platform support

x86_64, AArch64, PPC64, MIPS64. Requires `-fPIE -pie`.

---

## 4. ThreadSanitizer (TSan)

### What it detects

Data races (two threads access the same location concurrently with at
least one writer and no synchronizing happens-before edge between
them), as well as some deadlock and signal-handler-safety violations.

### Algorithm sketch

- For each memory location, TSan keeps a small **shadow cell** (a few
  bytes — typically 4 shadow slots, each 16 bytes — per 8 bytes of
  application memory).
- Each slot records (tid, epoch, access kind, size). A new access
  compares its vector-clock entry against the slot's: if the slot was
  written by a *different* thread and the writer's epoch is not in the
  current thread's happens-before set, it's a race.
- The happens-before relation is built from pthread/mutex/atomic ops,
  which the runtime interposes.

### Cost

> "Memory usage may increase by 5–10× and execution time by 2–20×."

Higher than ASan because every memory access updates a 4-slot shadow,
not just reads a byte.

### Limitations

- All linked code must be `-fsanitize=thread`-built; non-instrumented
  code can cause both false positives and false negatives.
- Static linking of libc/libstdc++ unsupported.
- C++ exceptions not supported.
- Detection is dynamic — only races that actually happen in this run
  are reported.

### Example

```cpp
int Global;
void *Thread1(void *_) { Global++; return NULL; }
void *Thread2(void *_) { Global--; return NULL; }
int main() {
    pthread_t t[2];
    pthread_create(&t[0], NULL, Thread1, NULL);
    pthread_create(&t[1], NULL, Thread2, NULL);
    pthread_join(t[0], NULL);
    pthread_join(t[1], NULL);
}
```

Diagnostic lists the read+write pair, both backtraces, and the
`pthread_create` sites.

---

## 5. HWAddressSanitizer (HWASAN)

### Pitch

HWASAN is ASan's successor for AArch64 (and increasingly x86_64 with
Intel LAM). It replaces the 1:8 shadow-with-redzones scheme with
**tagged pointers** — a top-byte ignore (TBI) tag that the hardware
strips before address translation. Memory overhead drops from ~3× to
roughly 1/16, and tagging granularity matches the natural allocator
alignment.

### Mechanism

- **Top byte of every pointer is a tag.** AArch64 already ignores the
  top byte in address translation (TBI), so tagged pointers can be
  dereferenced directly.
- **Memory is tagged in shadow at granule TG bytes** (16 or 64). One
  shadow byte stores the tag for one granule.
- **Allocator assigns a random TS-bit tag** (typically 4 or 8 bits per
  granule).
- **Every load / store checks** that the pointer tag matches the shadow
  tag for that granule. Mismatch ⇒ crash.

### Granule and tag size

| Configuration | Tag bits | Granule | Miss rate | Shadow overhead |
| --- | --- | --- | --- | --- |
| Common | 4 | 16 B | ~6.25 % | ~6.25 % |
| Larger | 8 | 16 B | ~0.39 % | ~6.25 % |
| Coarser | 4 | 64 B | ~6.25 % | ~1.6 % |

The detection is **probabilistic**: with 4 bits, ~1 / 16 = 6.25 % of bug
instances can collide on the tag and slip through. This is the explicit
trade against ASan's deterministic redzones.

### Short granules

For allocations smaller than a granule (1..TG-1 bytes), the shadow byte
holds the *size* and the *last byte of the granule* carries the actual
tag. The instrumented check is:

```
tag_match = (pointer_tag == shadow_byte)
         || (shadow_byte <= 15
             && access_end <= shadow_byte
             && pointer_tag == load_byte(granule_end - 1))
```

### Generated code (AArch64)

For `int foo(int *a) { return *a; }`:

```asm
foo:
    stp     x30, x20, [sp, #-16]!
    adrp    x20, :got:__hwasan_shadow
    ldr     x20, [x20, :got_lo12:__hwasan_shadow]
    bl      __hwasan_check_x0_2_short_v2
    ldr     w0, [x0]
    ldp     x30, x20, [sp], #16
    ret
```

The check is outlined into a function with a *custom calling
convention* that preserves most registers — that's how HWASAN keeps
register pressure manageable.

### Relationship to MTE

ARM **Memory Tagging Extension (MTE)** does the same thing in hardware,
on actual silicon: tag bits stored in DRAM via separate ECC-style
metadata, tag check enforced by the MMU. HWASAN is the software
prototype that proves the model and is the fallback when MTE is absent.
See [03 — Hardware-assisted safety](./03-hardware.md).

### Intel LAM (x86_64)

Intel's Linear Address Masking exposes the top byte similarly to TBI but
is only on the newest x86_64 silicon. HWASAN on x86_64 currently
emulates this via page aliasing and supports the heap only.

---

## 6. UndefinedBehaviorSanitizer (UBSan)

UBSan is the lightweight UB-into-defined-behavior tool. It inserts
inline checks for specific UB rules and either calls a runtime to
diagnose, or traps directly.

### The full check menu

| Flag | UB caught |
| --- | --- |
| `-fsanitize=alignment` | Misaligned pointer/reference use |
| `-fsanitize=bool` | Loading non-{0,1} into `bool` |
| `-fsanitize=builtin` | Invalid arguments to compiler builtins |
| `-fsanitize=bounds` | Static-bound array OOB |
| `-fsanitize=enum` | Loading out-of-range enum |
| `-fsanitize=float-cast-overflow` | Float→int overflow |
| `-fsanitize=float-divide-by-zero` | FP divide-by-zero |
| `-fsanitize=function` | Indirect call through wrong type |
| `-fsanitize=implicit-unsigned-integer-truncation` | Lossy uint→uint |
| `-fsanitize=implicit-signed-integer-truncation` | Lossy signed conversion |
| `-fsanitize=implicit-integer-sign-change` | Sign-changing conversion |
| `-fsanitize=integer-divide-by-zero` | Integer divide-by-zero |
| `-fsanitize=implicit-bitfield-conversion` | Lossy bitfield conversion |
| `-fsanitize=nonnull-attribute` | NULL into `nonnull` param |
| `-fsanitize=null` | NULL dereference |
| `-fsanitize=nullability-arg`/`-assign`/`-return` | NULL through Nullable annotations |
| `-fsanitize=objc-cast` | Bad ObjC pointer casts (Darwin) |
| `-fsanitize=object-size` | OOB detected via `__builtin_object_size` |
| `-fsanitize=pointer-overflow` | Pointer arithmetic overflow |
| `-fsanitize=return` | Falling off non-void function |
| `-fsanitize=returns-nonnull-attribute` | NULL return from `__attribute__((returns_nonnull))` |
| `-fsanitize=shift` | OOB / negative shift |
| `-fsanitize=unsigned-shift-base` | Unsigned left-shift overflow |
| `-fsanitize=signed-integer-overflow` | Signed overflow (incl. `INT_MIN/-1`) |
| `-fsanitize=unreachable` | Reached `__builtin_unreachable` |
| `-fsanitize=unsigned-integer-overflow` | Unsigned overflow (not UB in C, but often a bug) |
| `-fsanitize=vla-bound` | VLA with non-positive length |
| `-fsanitize=vptr` | Wrong dynamic type / dead object call |

### Groups

- `undefined` — most of the above except `float-divide-by-zero`,
  unsigned overflow, implicit conversion, local-bounds, vptr, and
  nullability.
- `integer` — signed/unsigned overflow + shift + divide-by-zero +
  truncation + sign-change.
- `nullability` — the three nullability checks.
- `implicit-conversion` — implicit integer + bitfield conversions.

### Runtime modes

| Mode | Behavior | Cost |
| --- | --- | --- |
| Default (full runtime) | Verbose diagnostic, continue after error | Small per-check overhead; needs runtime lib |
| `-fno-sanitize-recover=...` | Print and exit | Same |
| `-fsanitize-trap=...` | Trap instruction (SIGILL) | No runtime needed |
| `-fsanitize-minimal-runtime` | Tiny runtime, dedup-only logging | Reduced attack surface for prod |

`-fsanitize-trap=undefined` is the standard way to ship UBSan in
**production**: zero runtime, deterministic SIGILL on UB, ~0 % overhead
for checks the optimizer can elide entirely.

### Example

```cpp
// test.cc
int main() { int x = 0x7fffffff; return x + 1; }
```

```
test.cc:3:5: runtime error: signed integer overflow:
  2147483647 + 1 cannot be represented in type 'int'
```

### Fine-grained control

```c
__attribute__((no_sanitize("undefined")))               // Disable everything
__attribute__((no_sanitize("signed-integer-overflow"))) // Disable one rule
__attribute__((overflow_behavior(wrap)))                // Define wrap semantics
__attribute__((overflow_behavior(trap)))                // Force trap even under -fwrapv
```

Runtime suppressions:

```
# UBSAN_OPTIONS=suppressions=/path/to/file
signed-integer-overflow:file-with-known-overflow.cpp
alignment:function_doing_unaligned_access
vptr:libfoo.so
```

---

## 7. Control Flow Integrity (CFI)

CFI defends *forward edges* (indirect calls, virtual calls) against
hijacking by checking the call target's type against the call-site
expectation.

### Schemes

- `-fsanitize=cfi-vcall` — virtual call type check
- `-fsanitize=cfi-nvcall` — non-virtual call type check
- `-fsanitize=cfi-icall` — indirect function call type check
- `-fsanitize=cfi-derived-cast` / `-fsanitize=cfi-unrelated-cast` — bad
  cast detection
- `-fsanitize=cfi-mfcall` — member-function-pointer call check
- `-fsanitize=kcfi` — low-overhead kernel variant, no LTO required

### Mechanics

- Requires `-flto` or `-flto=thin` and static linking (KCFI is the
  exception).
- At LTO time, classes/functions of the same type signature are placed
  into a *jump table*. Indirect calls go through table entries that
  validate type identity.
- Vtables get class hierarchy metadata used to verify dynamic type at
  call site.

### Cost

> "Virtual call checking demonstrates minimal overhead—less than 1 %
> measured on the Chromium browser."

Binary size can grow up to **15 %** because of the jump tables and the
extra metadata.

### Threat model coverage

CFI does *not* fix the bug — it stops the **exploit** that depends on
indirect-call hijacking after a memory-safety violation has occurred.
Combine with ASan (in test) and UBSan-trap (in prod) for a layered
defense.

---

## 8. `-fbounds-safety`

Clang's experimental but production-validated bounds-safety dialect for
C. Apple's kernel and OS userspace are the proof-of-concept production
deployment ("millions of lines").

### Annotations

External (refer to another variable / constant):

| Annotation | Meaning |
| --- | --- |
| `__counted_by(N)` | Pointer has `N` valid elements |
| `__sized_by(N)` | Pointer has `N` valid bytes (good for `void*`) |
| `__ended_by(P)` | Iterator-style: valid up to `P` |

Internal (pointer becomes a "wide pointer"):

| Annotation | Layout |
| --- | --- |
| `__bidi_indexable` | (ptr, upper, lower) — bidirectional indexing |
| `__indexable` | (ptr, upper) — one-way |
| `__single` | single object; arithmetic disallowed |
| `__null_terminated` | C-string-style |
| `__terminated_by(T)` | Custom sentinel-delimited |

### Defaulting strategy (the clever bit)

- **Locals default to `__bidi_indexable`**: they're wide pointers in
  registers, paying a small register-pressure cost but giving full
  bounds info "for free".
- **ABI-visible pointers default to `__single`**: struct fields,
  function parameters keep their 8-byte ABI; bounds must be carried
  separately by the programmer or an annotation.

This combination is what makes the model adoptable on existing C: most
code compiles unchanged, and the annotations needed are concentrated at
ABI boundaries.

### Trap behavior

Bounds violations *deterministically trap before* the out-of-bounds
access occurs. The compiler also enforces that pointer-and-bound
updates happen "side by side with no side effects between them," so
the wide pointer can never desynchronize.

### Backwards compatibility

A header macro-defines the annotations as type attributes when the
extension is enabled and as nothing when it isn't — so the same source
compiles with a non-supporting toolchain.

---

## 9. Side family: SafeStack, ShadowCallStack, PAC

Three more LLVM features that target **return-address corruption** —
the classic stack-smashing exploit primitive.

| Feature | What it does | Cost |
| --- | --- | --- |
| **SafeStack** (`-fsanitize=safe-stack`) | Splits the stack into a "safe stack" (return addresses, register spills) and an "unsafe stack" (arrays, address-taken locals). Buffer overflow on the unsafe stack can't touch return addresses. | < 0.1 % overhead reported. |
| **ShadowCallStack** (`-fsanitize=shadow-call-stack`) | Mirrors every return address into a separate, hardware-protected (mprotect / register-pinned) shadow stack. Mismatch on return ⇒ abort. AArch64 / RISC-V; Android uses it widely. | A few percent. |
| **Pointer Authentication (PAC)** (`-fsanitize=pointer-auth` on AArch64) | Signs pointers (function pointers, return addresses) with a hardware-generated MAC using a per-process key. Tampering changes the signature ⇒ invalid pointer ⇒ crash. | Single-instruction sign/auth; near-zero overhead. |

These are *integrity* mechanisms — they don't catch bugs, they make
some classes of exploits infeasible. They compose well with ASan / UBSan
in the test build and ship in production hardened by themselves.

---

## 10. Common limitations and what they tell us

Cross-cutting properties of every sanitizer above:

1. **Dynamic, not static.** They catch bugs in the runs they observe.
   Code paths never executed by your test corpus produce zero output.
   This is exactly the gap that a typed language closes by construction.
2. **Whole-program build needed (except UBSan and CFI).** MSan and TSan
   demand that libc++ / glibc be rebuilt with instrumentation, which is
   why production deployment is rare. A language with a clean ABI can
   sidestep this entirely.
3. **No use-after-free guarantee under heap grooming.** ASan's
   quarantine is finite. Pour 100 million allocations through it and the
   freed chunk is reused; the next use-after-free reads adjacent live
   data and reports nothing. This is the exact gap Fil-C's
   FUGC fills by keeping freed capabilities alive in shadow until the
   collector proves nothing else references them — see
   [01 — InvisiCaps §8](./01-invisicaps.md#8-fugc--the-garbage-collector-that-backs-the-model).
4. **Concurrency is the hardest case.** TSan exists *because* races are
   not addressable by ASan-style instrumentation alone — the violation
   isn't at a single access, it's at the relation between two. A static
   ownership / borrow discipline (Rust) avoids the entire shadow-cell
   apparatus.
5. **Tagged-pointer schemes (HWASAN, MTE) are probabilistic.** With 4
   tag bits, ~6.25 % of bugs go undetected per access. Acceptable for
   *fuzz farms* and *production hardening*; not acceptable for a
   *language safety claim*.
6. **CFI, SafeStack, ShadowCallStack, PAC are exploit mitigations, not
   bug detectors.** A new language should still emit them when targeting
   native binaries, because they harden against bugs in **non-language
   parts** of the system (linked C libraries, the kernel).
7. **UBSan-trap mode is the right baseline for any AOT compiler that
   emits unchecked arithmetic.** It's nearly free, deterministic, and
   prevents the "signed overflow turned silent infinite loop" class of
   failures. If A7 emits Zig (which has its own UB semantics), the
   corresponding setting in Zig (`-O ReleaseSafe` keeps checks;
   `-O ReleaseFast` drops them) is the analog.

Continue to [03 — Hardware-assisted safety](./03-hardware.md) for the
silicon side of the story, or jump to
[05 — Take-aways for A7](./05-for-a7.md) for the implementation guide.
