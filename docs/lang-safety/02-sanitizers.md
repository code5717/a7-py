# 02 — Runtime Sanitizers

Status: external-technology study notes on Clang/LLVM sanitizers, written
before 2026-09-14. Current A7 decisions are in the
[decision ledger](../plan/decisions.md).

Part of the `docs/lang-safety/` series ([README](./README.md)). Siblings:
[01 — InvisiCaps](./01-invisicaps.md) ·
[03 — Hardware-assisted safety](./03-hardware.md) ·
[04 — Comparison](./04-comparison.md) ·
[05 — Take-aways for A7](./05-for-a7.md).

The Clang/LLVM sanitizers are the most widely deployed memory-safety tools
for production C and C++. They do not make a language memory-safe. They are
debug instruments that turn many UB conditions into deterministic crashes.
Their algorithms are the practical baseline a new language's safety story
must beat.

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

- Out-of-bounds heap, stack, and global access
- Use-after-free, use-after-return, use-after-scope
- Double-free, invalid free
- Initialization-order fiasco
- Memory leaks (through integrated LSan)

### Algorithm — shadow memory at 1:8

ASan reserves a shadow region. One shadow byte describes whether 8 bytes of
application memory are addressable. The mapping on 64-bit Linux:

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

The ShadowGap is mapped `PROT_NONE`. Dereferencing the shadow of the shadow
segfaults, which is how the runtime catches its own bugs.

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

The slow path handles a partly poisoned granule:

```c
size_t last_accessed_byte = (address & 7) + kAccessSize - 1;
return last_accessed_byte >= shadow_value;
```

The fast path is two loads and a branch. The branch is almost never taken,
so on a modern CPU each access costs a few cycles.

### malloc / free / quarantine

- **malloc** allocates the requested size plus redzones (typically 32 bytes
  on each side), poisons the redzone shadow, and clears the user-region
  shadow.
- **free** poisons the whole chunk's shadow with `0xfd` and puts the chunk in
  a quarantine queue. Quarantined chunks are not reused until they age out,
  so use-after-free is caught for a tunable window. The quarantine defaults
  to 256 MB.

### Stack and global redzones

For a function with a local `char a[8];`, the compiler emits:

```c
char redzone1[32];   // 32-byte aligned
char a[8];           // 32-byte aligned
char redzone2[24];
char redzone3[32];   // 32-byte aligned
```

It sets the shadow bytes around `a` to match and resets them all on return.
Globals get similar redzones at link time.

### Performance

> "The average slowdown of the instrumented program is ~2×."

Memory overhead is about 3× in practice: 1× for the program, 1/8× for
shadow, ~2× for redzones and quarantine. Mac and Linux x86_64 are the
best-supported targets.

### Flags worth knowing

| Flag | Effect |
| --- | --- |
| `-fsanitize=address` | Enable |
| `-O1` or higher | Recommended |
| `-fno-omit-frame-pointer` | Better stack traces |
| `-g` | Symbolized output |
| `ASAN_OPTIONS=halt_on_error=0` | Continue after the first error |
| `ASAN_OPTIONS=detect_leaks=1` | Integrated leak detection (default on Linux x86_64) |
| `ASAN_OPTIONS=quarantine_size_mb=N` | Tune the quarantine window |
| `ASAN_OPTIONS=verbosity=1` | Diagnostic output |

---

## 2. LeakSanitizer (LSan)

LSan is the leak detector inside or alongside ASan. It runs a mark-and-sweep
at process exit and reports every heap chunk no live pointer references.

- **Roots:** global and TLS sections, and every thread's stack and registers.
- **Mark:** scan each root word by word; any value that looks like a chunk
  pointer counts as a heap reference.
- **Sweep:** report every chunk not reachable from a root as a direct or
  indirect leak.

Modes:

- **Integrated with ASan:** default on x86_64 Linux. On macOS, enable with
  `ASAN_OPTIONS=detect_leaks=1`.
- **Stand-alone:** `-fsanitize=leak` without ASan. Lighter, but less tested.

Flags via `LSAN_OPTIONS`:

| Flag | Effect |
| --- | --- |
| `exitcode=23` | Exit code on a detected leak (default 23) |
| `max_leaks=N` | Report only the top N |
| `suppressions=/path` | Suppression file; entries look like `leak:FunctionName`, anchored with `^` / `$` |
| `report_objects=1` | List individual leaked objects with addresses |

LSan misses objects still reachable from a global that nothing will use
again: "dead" but not "lost".

---

## 3. MemorySanitizer (MSan)

### What it detects

Uninitialized reads. ASan cannot see these, because the memory is
addressable; it just holds garbage.

### Algorithm

- A separate shadow region tracks uninitialized bits exactly: one shadow bit
  per application bit. A shadow bit of 1 means the bit is poisoned
  (uninitialized).
- Arithmetic, logic, and copies propagate poison without warning. Poison
  spreads through every derived value.
- MSan warns only when poison affects observable behavior:
  - a conditional branch on a poisoned value;
  - a poisoned address used as a pointer (load or store);
  - a poisoned value passed to or returned from an uninstrumented function
    (typically libc).

Reporting on use instead of on copy keeps false positives manageable.

### Origin tracking

`-fsanitize-memory-track-origins` (and the deeper
`-fsanitize-memory-track-origins=2`) records the allocation site of each
poisoned value and carries it with the data. The warning then shows the
chain: "this came from `new int[10]` at file:line, was copied here, was
copied there, finally read at file:line".

### Cost

- ~3× slowdown without origin tracking.
- A further 1.5×–2.5× with origin tracking.
- Whole-program build: every translation unit, including libc++ and
  libstdc++, must be MSan-instrumented. Otherwise MSan reports false
  positives in stdlib internals. Pre-built MSan-clean libstdc++ images and a
  documented libc++ workflow exist.

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

With origin tracking, the trace also names the `new int[10]` call site.

### Platform support

x86_64, AArch64, PPC64, MIPS64. Requires `-fPIE -pie`.

---

## 4. ThreadSanitizer (TSan)

### What it detects

Data races: two threads access the same location concurrently, at least one
writes, and no synchronizing happens-before edge separates them. TSan also
finds some deadlocks and signal-handler-safety violations.

### Algorithm sketch

- Each location has a small shadow cell: typically 4 shadow slots of 16
  bytes each per 8 bytes of application memory.
- Each slot records (tid, epoch, access kind, size). A new access compares
  its vector-clock entry with each slot. If a different thread wrote the slot
  and that writer's epoch is not in the current thread's happens-before set,
  the access is a race.
- The runtime builds the happens-before relation by intercepting pthread,
  mutex, and atomic operations.

### Cost

> "Memory usage may increase by 5–10× and execution time by 2–20×."

This is higher than ASan because every access updates a 4-slot shadow
instead of reading one byte.

### Limitations

- All linked code must be built with `-fsanitize=thread`. Uninstrumented
  code causes both false positives and false negatives.
- Static linking of libc/libstdc++ is unsupported.
- C++ exceptions are unsupported.
- Detection is dynamic: TSan reports only races that happen in the run.

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

The diagnostic lists the read and write pair, both backtraces, and the
`pthread_create` sites.

---

## 5. HWAddressSanitizer (HWASAN)

### Pitch

HWASAN succeeds ASan on AArch64, and increasingly on x86_64 with Intel LAM.
It replaces ASan's 1:8 shadow with redzones by tagged pointers: a tag in the
top byte, which the hardware strips before address translation (top-byte
ignore, TBI). Memory overhead drops from ~3× to about 1/16, and tag
granularity matches normal allocator alignment.

### Mechanism

- **The top byte of every pointer is a tag.** AArch64 already ignores the top
  byte during address translation, so tagged pointers dereference directly.
- **Shadow holds one tag per granule** of TG bytes (16 or 64).
- **The allocator assigns a random TS-bit tag** per granule (typically 4 or 8
  bits).
- **Every load and store checks** that the pointer tag matches the granule's
  shadow tag. A mismatch crashes.

### Granule and tag size

| Configuration | Tag bits | Granule | Miss rate | Shadow overhead |
| --- | --- | --- | --- | --- |
| Common | 4 | 16 B | ~6.25 % | ~6.25 % |
| Larger | 8 | 16 B | ~0.39 % | ~6.25 % |
| Coarser | 4 | 64 B | ~6.25 % | ~1.6 % |

Detection is probabilistic. With 4 bits, about 1/16 (6.25 %) of bug instances
collide on the tag and go undetected. This is the deliberate trade against
ASan's deterministic redzones.

### Short granules

For allocations smaller than a granule (1..TG-1 bytes), the shadow byte holds
the size and the last byte of the granule holds the real tag. The check is:

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

The check is outlined into a function with a custom calling convention that
preserves most registers. This keeps register pressure low.

### Relationship to MTE

ARM's Memory Tagging Extension (MTE) implements the same model in silicon.
Tag bits live in DRAM as separate ECC-style metadata, and the MMU enforces
the check. HWASAN is the software prototype that proved the model, and the
fallback when MTE is absent. See
[03 — Hardware-assisted safety](./03-hardware.md).

### Intel LAM (x86_64)

Intel's Linear Address Masking exposes the top bits much like TBI, but only
on the newest x86_64 silicon. HWASAN on x86_64 currently emulates it through
page aliasing and covers the heap only.

---

## 6. UndefinedBehaviorSanitizer (UBSan)

UBSan is the lightweight tool for turning UB into defined behavior. It
inserts inline checks for specific UB rules and either calls a runtime to
report or traps directly.

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

| Group | Contents |
| --- | --- |
| `undefined` | Most of the above, except `float-divide-by-zero`, unsigned overflow, implicit conversion, local-bounds, vptr, and nullability |
| `integer` | Signed/unsigned overflow, shift, divide-by-zero, truncation, sign-change |
| `nullability` | The three nullability checks |
| `implicit-conversion` | Implicit integer and bitfield conversions |

### Runtime modes

| Mode | Behavior | Cost |
| --- | --- | --- |
| Default (full runtime) | Verbose diagnostic, continue after error | Small per-check overhead; needs runtime lib |
| `-fno-sanitize-recover=...` | Print and exit | Same |
| `-fsanitize-trap=...` | Trap instruction (SIGILL) | No runtime needed |
| `-fsanitize-minimal-runtime` | Tiny runtime, dedup-only logging | Reduced attack surface for prod |

`-fsanitize-trap=undefined` is the standard way to ship UBSan in production.
It needs no runtime, raises a deterministic SIGILL on UB, and costs ~0 % for
checks the optimizer removes.

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

CFI protects forward edges (indirect calls and virtual calls) from hijacking.
It checks the call target's type against what the call site expects.

### Schemes

| Flag | Check |
| --- | --- |
| `-fsanitize=cfi-vcall` | Virtual call type |
| `-fsanitize=cfi-nvcall` | Non-virtual call type |
| `-fsanitize=cfi-icall` | Indirect function call type |
| `-fsanitize=cfi-derived-cast` / `-fsanitize=cfi-unrelated-cast` | Bad casts |
| `-fsanitize=cfi-mfcall` | Member-function-pointer call |
| `-fsanitize=kcfi` | Low-overhead kernel variant; no LTO required |

### Mechanics

- Requires `-flto` or `-flto=thin` and static linking (KCFI excepted).
- At LTO time, functions with the same type signature go into a jump table.
  Indirect calls go through table entries that validate the type.
- Vtables carry class-hierarchy metadata used to check the dynamic type at
  the call site.

### Cost

> "Virtual call checking demonstrates minimal overhead—less than 1 %
> measured on the Chromium browser."

Binary size can grow by up to 15 % from jump tables and metadata.

### Threat model coverage

CFI does not fix the bug. It stops exploits that hijack indirect calls after
a memory-safety violation. Layer it with ASan in testing and UBSan-trap in
production.

---

## 8. `-fbounds-safety`

Clang's bounds-safety dialect for C. It is experimental but validated in
production: Apple's kernel and OS userspace deploy it across "millions of
lines".

### Annotations

External annotations (refer to another variable or constant):

| Annotation | Meaning |
| --- | --- |
| `__counted_by(N)` | Pointer has `N` valid elements |
| `__sized_by(N)` | Pointer has `N` valid bytes (good for `void*`) |
| `__ended_by(P)` | Iterator-style: valid up to `P` |

Internal annotations (the pointer becomes a wide pointer):

| Annotation | Layout |
| --- | --- |
| `__bidi_indexable` | (ptr, upper, lower) — bidirectional indexing |
| `__indexable` | (ptr, upper) — one-way |
| `__single` | single object; arithmetic disallowed |
| `__null_terminated` | C-string-style |
| `__terminated_by(T)` | Custom sentinel-delimited |

### Defaulting strategy

- **Locals default to `__bidi_indexable`.** They are wide pointers in
  registers. This costs some register pressure but gives full bounds
  information without annotations.
- **ABI-visible pointers default to `__single`.** Struct fields and function
  parameters keep their 8-byte ABI. The programmer or an annotation must
  carry bounds separately.

This combination makes the model adoptable for existing C. Most code
compiles unchanged, and annotations concentrate at ABI boundaries.

### Trap behavior

Bounds violations trap deterministically before the out-of-bounds access.
The compiler also requires pointer and bound updates to happen "side by side
with no side effects between them," so a wide pointer can never fall out of
sync.

### Backwards compatibility

A header defines the annotations as type attributes when the extension is on
and as nothing when it is off. The same source compiles with toolchains that
lack the extension.

---

## 9. Side family: SafeStack, ShadowCallStack, PAC

Three more LLVM features target return-address corruption, the classic
stack-smashing exploit primitive.

| Feature | What it does | Cost |
| --- | --- | --- |
| SafeStack (`-fsanitize=safe-stack`) | Splits the stack into a safe stack (return addresses, register spills) and an unsafe stack (arrays, address-taken locals). An overflow on the unsafe stack cannot reach return addresses. | < 0.1 % reported |
| ShadowCallStack (`-fsanitize=shadow-call-stack`) | Copies every return address to a separate protected shadow stack (mprotect or a pinned register). A mismatch on return aborts. AArch64 / RISC-V; widely used on Android. | A few percent |
| Pointer Authentication (PAC) (`-fsanitize=pointer-auth` on AArch64) | Signs function pointers and return addresses with a hardware MAC under a per-process key. Tampering breaks the signature, yielding an invalid pointer that crashes. | One instruction to sign or verify; near zero |

These are integrity mechanisms. They do not find bugs; they make some
exploit classes infeasible. They combine with ASan and UBSan in test builds
and can ship alone in hardened production builds.

---

## 10. Common limitations and what they tell us

Properties shared by the sanitizers above:

1. **Dynamic, not static.** They catch bugs only in the runs they observe.
   Paths the test corpus never executes produce no output. A typed language
   closes this gap by construction.
2. **Whole-program builds (except UBSan and CFI).** MSan and TSan need libc++
   and glibc rebuilt with instrumentation, so production use is rare. A
   language with a clean ABI can avoid this.
3. **No use-after-free guarantee under heap grooming.** ASan's quarantine is
   finite. After 100 million allocations the freed chunk is reused, and a
   later use-after-free reads live data without a report. Fil-C closes this
   gap: `free()` sets the capability's bounds to zero, and FUGC repoints
   stale in-memory capabilities to a free singleton before reusing the
   memory. See
   [01 — InvisiCaps §8](./01-invisicaps.md#8-fugc--the-garbage-collector-that-backs-the-model).
4. **Concurrency is the hardest case.** TSan exists because ASan-style
   checks cannot see races: the violation is a relation between two
   accesses, not a single access. A static ownership and borrowing
   discipline (Rust) avoids the shadow-cell machinery.
5. **Tagged-pointer schemes (HWASAN, MTE) are probabilistic.** With 4 tag
   bits, ~6.25 % of bugs go undetected per access. That is acceptable for
   fuzzing farms and production hardening, not for a language safety claim.
6. **CFI, SafeStack, ShadowCallStack, and PAC mitigate exploits; they do not
   detect bugs.** A new language should still enable them for native
   binaries. They harden the parts outside the language: linked C libraries
   and the kernel.
7. **UBSan-trap mode is the right baseline for an AOT compiler that emits
   unchecked arithmetic.** It is nearly free, deterministic, and prevents
   failures such as signed overflow turning into a silent infinite loop. For
   A7, which emits Zig (with its own UB rules), the analog is Zig's build
   mode: `-O ReleaseSafe` keeps runtime checks and `-O ReleaseFast` drops
   them.

> Note (2026-09-16): item 7 does not match A7's current model or plan.
> A7's example builds use `-ODebug` and `-OReleaseFast`, not ReleaseSafe
> ([`scripts/build_examples.py`](../../scripts/build_examples.py)). The
> [safety contract](../SAFETY_CONTRACT.md) does not rely on Zig runtime
> checks: the compiler must prove a risky operation safe or reject the
> program before emitting Zig. The proposed
> [memory plan](../plan/memory.md) says any remaining runtime check is
> emitted as explicit A7 code, not a Zig safety check that ReleaseFast
> removes. Ledger L5 makes `+`, `-` and `*` wrap, so they will not be
> overflow traps. As of this note, the Zig backend does not yet emit
> wrapping operators; the contract still lists range proofs for them
> ([ledger](../plan/decisions.md), superseded-material table).

Continue to [03 — Hardware-assisted safety](./03-hardware.md) for the silicon
side, or [05 — Take-aways for A7](./05-for-a7.md) for the implementation
guide.
