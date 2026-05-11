# 01 — InvisiCaps: The Fil-C Capability Model

> Part of the `docs/lang-safety/` series. See the
> [README](./README.md) for the full map. Siblings:
> [02 — Sanitizers](./02-sanitizers.md) ·
> [03 — Hardware-assisted safety](./03-hardware.md) ·
> [04 — Comparison](./04-comparison.md) ·
> [05 — Take-aways for A7](./05-for-a7.md).

A deep-dive study of Fil-C's pointer capability system, distilled from the
primary sources at <https://fil-c.org> and the project's Manifesto. This
document is research notes — not affiliated with Fil-C — collected for use as
reference material when reasoning about memory-safety models that might
inform the A7 language design. Fil-C is © Epic Games, Apache2 / BSD licensed.

Primary sources fetched:

- <https://fil-c.org/invisicaps.html> — the canonical capability model writeup
- <https://fil-c.org/invisicaps_by_example.html> — worked examples
- <https://fil-c.org/gimso.html> — Garbage In, Memory Safety Out semantics
- <https://fil-c.org/fugc.html> — Fil's Unbelievable Garbage Collector
- <https://fil-c.org/compiler.html> — the FilPizlonator LLVM pass
- <https://fil-c.org/compiler_example.html> — annotated disassembly
- <https://fil-c.org/documentation.html> — documentation index
- <https://fil-c.org/meet_fil.html> — project background
- <https://github.com/pizlonator/fil-c/blob/deluge/Manifesto.md> — Manifesto

---

## 1. What Fil-C is, in one paragraph

Fil-C is a fork of clang 20.1.8 that compiles ordinary C and C++ source into
a memory-safe runtime by ascribing memory-safe semantics to LLVM IR. Every
pointer carries a *capability* — a runtime token describing the object it is
allowed to reach into and the bounds within that object. The capability is
**invisible** in the sense that `sizeof(T*) == 8` on a 64-bit host: the
capability rides alongside the pointer in registers, and lives in a *shadow
address space* when the pointer is at rest in memory. Allocations are managed
by FUGC, a concurrent, on-the-fly, accurate, non-moving garbage collector;
calling `free()` is legal but optional and turns the capability into one with
zero bounds rather than reclaiming memory. The project's motto is
**"Garbage In, Memory Safety Out!"** (GIMSO): regardless of how broken or
adversarial the input program is, the worst observable outcome is a Fil-C
panic — never a memory-safety violation.

Per the Manifesto, Fil-C is currently **1.5× slower than C in good cases and
about 4× slower in worst cases**, and has run unmodified ports of curl,
OpenSSL, OpenSSH, zlib, pcre, SQLite, CPython, ICU, libc++/libc++abi, and
musl.

## 2. Why InvisiCaps — what the previous models could not do

InvisiCaps are the third iteration of Fil-C's capability representation.
Their predecessors document the design pressure:

| Model | Pointer size | Use-after-free | Type changes after malloc | Thread-safe | Overhead |
| --- | --- | --- | --- | --- | --- |
| **PLUT** (Pointer / Lower / Upper / Type) | 256 bits | No | Type fixed at allocation | No | — |
| **SideCaps** (Sidecar + capability) | 64 bits | No | Type fixed at allocation | Yes | ≈200× |
| **MonoCaps** (Monotonic capabilities) | 128 bits | Yes (deterministic panic) | Limited; C++ support added | Yes | ≈10× |
| **InvisiCaps** | 64 bits | Yes | **Yes — meaningful unions, int↔ptr ping-pong** | Yes | ≈4× worst case |

The headline wins of InvisiCaps:

1. **Native pointer size on 64-bit hosts.** No ABI shape change for plain C
   data structures.
2. **Dynamic type reinterpretation works.** You can store an int, load it as
   a pointer, store a pointer, load it as an int — even ping-pong — without
   losing memory safety (the pointer simply loses its capability when its
   provenance is destroyed; access then traps deterministically).
3. **Atomic pointer operations are lock-free** even though the pointer's
   capability lives elsewhere in memory.
4. **Use-after-free traps even after the underlying memory is reclaimed**,
   because the GC repoints stale capabilities to a free singleton rather
   than letting them dangle.

The project positions InvisiCaps as a "practical, totally thread-safe
variant of [SoftBound]" and as "a software implementation of [CHERI]" with
smaller pointers and explicit use-after-free handling. The trade-offs against
those academic baselines are taken up in §11.

## 3. The flight pointer

A *flight pointer* is what Fil-C calls a pointer that is currently being
carried in registers or local data flow — pointers in transit between memory
accesses. A flight pointer is a 2-tuple:

```
(lower, intval)
   |       \__ the raw 64-bit address visible to C code
   \__________ the lower bound; immutable; cannot be forged by C code
```

The `lower` is set by the allocator. Any pointer derived from the result of
an allocation inherits that `lower`. Arithmetic on the pointer (GEP, pointer
addition, casts, masking, XORing low bits, …) changes `intval` but
**never** changes `lower`. This is the structural invariant of the whole
model.

The `lower` does not just live on its own; it points *just above* the
object's 16-byte header. The header carries:

```
        [ object header (16 bytes) ]
        [ upper_bound_pointer       ]  ← capability metadata
        [ aux_word                  ]
lower → [ payload byte 0            ]
        [ payload byte 1            ]
        [ ...                       ]
        [ payload byte upper-lower-1]
upper → [ next object / padding     ]
```

`upper` is read from a negative offset from `lower` (typically `-0x10` in
the disassembly walkthrough). `aux_word` is read from `-0x8`.

The `aux_word` packs three things:

- The low **48 bits**: a pointer to an *aux allocation* — the place that
  stores invisible capabilities for any pointers stored inside the payload.
  NULL if the object has no pointer fields.
- The upper **16 bits**: flags. They encode object alignment (so the GC can
  recover the true allocation base across alignment padding), special-object
  type tags, freed/readonly flags, and similar bits.
- The aux pointer doubles as a marker for special objects whose payload
  isn't really data — function pointers, threads, mmap regions, etc. — by
  setting flag bits and overlaying the "callable address" or "true
  entrypoint" into the same word.

### 3.1 The four legal access predicates

Per the GIMSO semantics, an access of `N` bytes through pointer `P` is
*legal* iff:

```
P.intval >= P.capability->lower
P.intval <  P.capability->upper
P.intval + N <= P.capability->upper
```

Three different compilation strategies for the upper-bound test appear in
the runtime, picked to avoid integer-overflow attacks:

- `P <= upper - S` (preferred when `S` is a known constant; emitted by the
  compiler most of the time)
- `P < upper && P + S <= upper` (used in runtime, when `S` is dynamic)
- `P < upper` (when `S` equals the access alignment, so the bound implies
  the size)

If any check fails, the runtime calls into the slow-path that prints a
`filc safety error` panic and aborts.

## 4. Pointers at rest — the invisible capability

The novel piece is what happens when a pointer is *stored to memory*. In
flight, the capability rides in another register. In memory, an explicit
"fat pointer" representation would either (a) double the in-memory width of
every pointer, breaking ABI and unions, or (b) require a shadow table that
costs a load barrier on every pointer read.

InvisiCaps thread the needle by using a **per-object auxiliary
allocation**:

```
Object #1 (contains a pointer at rest)        Aux allocation for Object #1
+----------------------------------+           +-------------------------+
| header.upper                     |           | byte 0  ← capability    |
| header.aux_word ─────────────────┼─────────► | byte 8     for the      |
| payload byte 0  ← intval of      |           | byte 16    pointer at   |
| payload byte 8     the stored ptr|           | ...        offset 0     |
| ...                              |           +-------------------------+
+----------------------------------+
```

- Payload bytes store the **intval** of any embedded pointer, exactly as
  legacy C would store them. So `(char*)&p` reads sensible address bits.
- Aux allocation bytes — at the *same offset* as the payload — store the
  **lower** of the embedded pointer. Each aligned 8-byte slot in the aux
  allocation parallels an aligned 8-byte slot in the payload.
- The aux allocation is itself an InvisiCap object, but the program never
  gets a capability pointing into it — only the runtime and the FilPizlonator
  pass can address it.
- **If an object has no pointer fields, its `aux_word` is NULL** and no aux
  allocation is created. Strings and pixel buffers pay zero space overhead.
  This is why "the space overhead of InvisiCaps is nowhere near 2×."

### 4.1 The inductive hypothesis

The structural property that makes the whole model close under operations
is stated in the source page as:

> Every flight pointer's *lower* points to the top of an object header
> whose aux word contains a way to get the *lowers* for all pointers
> stored to that object's payload.

Loading a pointer therefore boils down to:

```text
;; pseudo-code for *(T**)p in non-atomic mode
intval        = LoadFromPrimarySpace(p.intval)    ; the address bits
aux_base      = (p.lower → header.aux_word) & 0x0000FFFFFFFFFFFF
capability    = aux_base[p.intval - p.lower]      ; the invisible lower
return (lower = capability, intval = intval)
```

Storing a pointer is the mirror image: write the `intval` to the payload,
write the `lower` to the aux allocation at the matching offset.

### 4.2 GIMSO load/store semantics, restated

From the gimso.html page, the canonical lowered forms are:

```
;; non-atomic pointer load
CapabilityOrAtomicBox = LoadFromShadowSpace(P.intval)
Intval                = LoadFromPrimarySpace(P.intval)
return MakePointer(capability = CapabilityOrAtomicBox, intval = Intval)

;; non-atomic pointer store
StoreToPrimarySpace(P.intval, V.intval)
StoreToShadowSpace (P.intval, V.capability)
```

Both are preceded by the four-predicate bounds check. The shadow address
space is conceptual; the implementation is the aux allocation.

## 5. Atomic InvisiCaps

`_Atomic`, `volatile`, and `std::atomic` pointers need to survive races
without tearing the (intval, capability) pair. Fil-C handles this with an
**atomic box** indirection in the aux slot:

```
Aux slot for an atomic pointer field
+---------+
| low bit |   0 → slot holds a plain lower; 1 → slot holds a tagged
| 0/1     |       pointer to an atomic box
+---------+

Atomic box (16 bytes, 16-byte aligned)
+----------+----------+
| capability | intval |    ← stored/loaded with 128-bit atomics
+----------+----------+
```

- The atomic box stores a full flight pointer (capability + intval) in 16
  bytes and is read/written with `cmpxchg16b`-class instructions.
- The intval is **also** mirrored back into the payload so that a
  non-atomic integer load of the field still observes the address bits.
- Storing an atomic pointer doesn't have to allocate a fresh box every
  time; the implementation may reuse a box when repeatedly writing to the
  same location.
- A racing non-atomic store can corrupt the intval mirror but **cannot**
  corrupt the box itself, so the (capability, intval) pair never tears in a
  way that would yield an unsafe pointer. The worst outcome of a race is
  "time travel" — observing a stale but well-formed pointer — followed by
  a trap if its bounds don't fit the current access.

In `invisicaps_by_example.html` test #18, a non-atomic pointer race panics
about once in a hundred runs with `ptr < lower`. Switching the declaration
to `int* _Atomic ptr` eliminates the race and runs reliably.

## 6. Special objects

The `aux_word`'s flag bits and 48-bit pointer slot are reused to encode
non-data objects:

### 6.1 Function pointers

- `intval` is the function entrypoint visible to C.
- `lower` points to a function capability whose `upper == lower` — so any
  data access fails the upper-bound check.
- The aux word's flag bits identify this as a function capability, and its
  48-bit slot stores the *true* entrypoint that an indirect call must
  match.
- Dynamic calling convention mismatches between caller and callee are also
  detected; argument and return sizes are part of the function-capability
  protocol.

### 6.2 Threads, mmap regions, Sys-V shared memory

- Pointers are to internal `zthread`/region abstractions with bounds
  equal to lower (no payload access) and flag bits selecting the
  variant.
- Runtime functions that take a thread pointer verify the type by reading
  the flag bits before touching the payload.

### 6.3 Freed objects

- `free(p)` sets the object's `upper := lower` so every subsequent bounds
  check fails.
- A "free" bit in the aux word powers diagnostic messages (`free` shows up
  in panic dumps).
- FUGC additionally **repoints** in-memory capabilities that referred to
  the freed object to a global *free singleton* capability, so even after
  the underlying memory is reclaimed and rebound, a stale pointer still
  traps deterministically. See §8.

### 6.4 Aligned / mmap allocations

- Flag bits in the aux word record the requested alignment so the GC can
  recover the true allocation base across alignment padding.
- A flag distinguishes objects that need bespoke GC handling (mmap,
  shared memory).

## 7. Worked examples (from `invisicaps_by_example.html`)

The example page is the most efficient way to internalise the model. The
panic format used throughout is:

```
filc safety error: <reason>.
    pointer: <intval>,<lower>,<upper>[,<flags>]
    expected <N> [writable] bytes [with ptr aligned to ...].
semantic origin:
    <file>:<line>:<col>: <function>
check scheduled at:
    <stack of where the check ran>
[<pid>] filc panic: thwarted a futile attempt to violate memory safety.
```

A condensed catalogue of the worked examples, lossless on the safety
classification:

| # | Hazard | Source sketch | Diagnostic |
| --- | --- | --- | --- |
| 1 | OOB write | `char* p = malloc(16); p[42] = 100;` | `ptr >= upper` |
| 2 | OOB but inside *another* object | `x[y - x] = '!';` | `ptr >= upper` — capability of `x` doesn't cover `y` |
| 3 | Address-wrap | `p -= (uintptr_t)p; p += UINT_MAX; *(int*)p = 42;` | `ptr >= upper`, intval `0xFFFFFFFFFFFFFFFF` |
| 4 | Negative offset to syscall | `write(1, "hello\n" - 100, 6)` | `ptr < lower` |
| 5 | Oversized syscall read | `write(1, "hello\n", 100)` | `upper - ptr = 8`, expected 100 |
| 6 | Pointer in memory shows aux | `*(int**)p = malloc(4)` | `%P` prints `aux=<addr>` |
| 7 | Integer-then-pointer reinterpretation | `*(int*)p = 666; int* p2 = *(int**)p;` | Loaded pointer has `<null>` capability — access panics |
| 8 | Pointer-then-integer reinterpretation | Read low 32 bits of an embedded pointer | Works — non-pointer type confusion is allowed |
| 9 | Store ptr, overwrite intval bits, reload | Embedded pointer retains its capability even after the intval is rewritten | Access panics with `ptr < lower` because the capability is preserved but the intval no longer fits its bounds |
| 10 | int↔float reinterpret | `*(float*)&x` | Allowed — no pointer involved |
| 11 | Sophisticated unions (int / pointer / double) | `union u { ... }` | All field-level reads succeed; only an attempt to *dereference* an int-shaped pointer traps |
| 12 | Read a function pointer's bytes | `(int)*((char*)foo)` | `cannot read pointer to special object` |
| 13 | Call a `malloc`-returned chunk as a function | `foo()` where `foo = malloc(16)` | `cannot access pointer as function, object isn't even special` |
| 14 | Offset function pointer | `(char*)foo + 42` then call | `cannot access pointer as function with ptr != aux` |
| 15 | Plain use-after-free | `free(p); *p = 42;` | `cannot write pointer to free object`, with `upper == lower` |
| 16 | UAF with heap grooming (100M reallocations between free and use) | Still panics | FUGC keeps the freed capability alive |
| 17 | UAF where pointer escaped into another object | `free(*p); ... **p = 42` | Capability has been swapped to the free singleton |
| 18 | Pointer race | non-atomic shared `int* ptr` mutated from two threads | Occasional `ptr < lower` panic; fixed by `_Atomic` |
| 19 | XOR-then-undo a pointer in local data flow | `(const char*)((uintptr_t)str ^ 1)` works because the compiler recovers the capability through `ptrtoint`→`inttoptr` |
| 20 | Same as #19 but through a global `uintptr_t` | Capability lost — load is a bare `inttoptr` with no provenance — panic on dereference |
| 21 | Cast `42` to a pointer | OK to carry around, traps on dereference |
| 22–26 | Bad linking (arity mismatch, type mismatch, function-as-data, data-as-function, `const` mixup) | Each scenario traps at the *use* site, not the link site, because Fil-C drops the ODR assumption |
| 27 | Variadic underflow (`foo(10, 666)`) | Reading the 2nd va_arg traps with `ptr >= upper` because the heap-allocated va-buffer is sized to the actual arguments |
| 28 | Variadic type mismatch (int passed, string expected) | `cannot read pointer with null object` — the int was promoted into a pointer slot with no capability |
| 29 | `va_list` escaping its frame | Works — variadic args live in a heap-allocated readonly object that outlives the frame |
| 30 | Pure leak (1 trillion bytes allocated without free) | FUGC reclaims; RSS stays at ~5–7 MB |

The compiler is doing real abstract interpretation in example 19 — that's
the `inttoptr` capability-recovery rule described in §10.

## 8. FUGC — the garbage collector that backs the model

InvisiCaps only work if the bounds metadata stays alive. That is FUGC's
job. FUGC is described in the Manifesto as a **parallel, concurrent,
on-the-fly, grey-stack, Dijkstra, accurate, non-moving** collector.

Dimension by dimension:

- **Parallel.** Marking and sweeping run on multiple threads.
- **Concurrent.** GC threads are disjoint from mutator threads; the only
  blocking the mutator sees is the slow path of an allocation.
- **On-the-fly.** No global stop-the-world. Synchronisation is via
  **soft handshakes** (a.k.a. ragged safepoints): the GC requests that
  each thread run a small callback at its next safepoint. The callback
  scans the requesting thread's stack and is bounded by stack height —
  typically faster than a `malloc` slow path.
- **Grey-stack.** Stacks are rescanned to a fixpoint, so there is no load
  barrier. Each fixpoint iteration is another soft handshake; in practice
  it converges in a few rounds.
- **Dijkstra.** A *store* barrier marks the target of any pointer store
  during marking. The barrier is a CAS with relaxed ordering on the slow
  path only.
- **Accurate.** The FilPizlonator pass tells the runtime exactly where every
  pointer lives on the stack and in globals; outgoing pointers from heap
  objects can only live in aux allocations.
- **Non-moving.** Objects don't relocate, which keeps concurrency cheap.
  The one exception is the free-singleton repointing.

The collector loop, from `fugc.html` and the Manifesto:

```
1. Wait for the GC trigger.
2. Turn on the store barrier; soft handshake with a no-op callback.
3. Turn on black allocation (new objects pre-marked); soft handshake that
   resets thread-local caches.
4. Mark global roots.
5. Soft handshake requesting stack scan + cache reset.
   If all mark stacks are empty, jump to step 7.
6. Trace: drain the mark stack, marking outgoing references. Go to 5.
7. Turn off the store barrier, prepare for sweep; soft handshake to reset
   caches.
8. Sweep. New allocations are black or white depending on whether their
   page has been swept yet.
9. Return to 1.
```

Other FUGC-relevant details:

- **Safepoints** are emitted by FilPizlonator as `pollchecks` at loop
  back-edges and other bounded points. The fast path is a load and
  conditional branch; the slow path runs a pollcheck callback (which is
  what the GC piggybacks soft handshakes on).
- **Enter/exit** lets a thread blocking in a syscall publish "I'm
  parked" so the GC can run its callback on the parked thread's behalf.
- **Stop-the-world** is supported as a non-default mode, used by
  `fork(2)` and as the `FUGC_STW=1` debugging switch.
- **Sweeping is bit-vector SIMD** in libpas's Verse heap config; FUGC
  spends "<5% of its time sweeping."
- **Free repoints to a singleton.** When FUGC reclaims a freed object,
  any in-memory capability that pointed at it is rewritten to a global
  free-singleton object with `lower == upper`. The aux allocation makes
  this efficient — pointer fields are at known offsets and have known
  capabilities. Stale local copies on stacks/registers will already have
  `upper == lower` from `free()` itself.
- **Finalizers / weak refs.** The runtime exposes `zgc_finq` (Java-style
  finalizer queues), `zweak` (weak references without queues, no phantom
  or soft variants), and `zweak_map` (a WeakMap with iteration).

The "real" use-after-free guarantee is the conjunction:

1. `free()` sets `upper := lower` on the freed object's capability ⇒
   every flight pointer that still names that capability traps.
2. FUGC scans the heap before reclaiming the memory and rewrites every
   in-memory pointer that named the freed capability to name the free
   singleton ⇒ pointers loaded *after* the next GC also trap.
3. Memory is reused only after both of the above have happened ⇒ no
   capability is ever silently retargeted.

## 9. The FilPizlonator compilation pipeline

Fil-C's compiler is a fork of clang 20.1.8 with one new LLVM pass and
two surgical CodeGen tweaks.

### 9.1 The LLVM pass — `llvm::FilPizlonatorPass`

It is run after a fairly normal `clang` mid-end pipeline (SROA, inliner,
DCE, redundant load/store elimination, InstCombine) so that the GIMSO
rewrites can target reasonably clean IR. The pass:

- Rewrites every pointer SSA value into a 2-tuple `(capability, intval)`
  — the IR-level flight pointer.
- Inserts the bounds-check / readonly / not-free / aligned predicates
  before every memory access, including SIMD loads/stores, atomic ops,
  and memcpy/memset/memmove intrinsics.
- Lowers heap allocations to direct FUGC allocator calls (with an inlining
  fast path).
- Rewrites the calling convention so that arguments and returns are
  passed in 8-byte aligned slots, each carrying an intval *and* a
  capability through a thread-local argument buffer (see §10).
- Drops `nuw`/`nsw`/`inbounds`/`inrange` UB flags from `getelementptr`
  and arithmetic — GIMSO defines those behaviors rather than letting them
  be UB.
- Implements the `inttoptr` abstract interpretation that recovers
  capabilities for round-tripped pointers (§10).
- Generates pollchecks at safepoints, stack maps for FUGC, and Pizderson
  frames (the per-call stack-allocated structure that gives FUGC a precise
  view of in-register capabilities).
- Rejects unsupported IR (most `cleanuppad`, `catchswitch`,
  `callbr`, branching inline assembly) by lowering them to *always-panic*
  rather than silently miscompiling.

> "Either the pass will fail to generate any output (the compiler will
> crash), or the generated IR follows the memory safety doctrine."

### 9.2 Clang CodeGen tweaks

- **CGAtomic** is patched so that pointer atomics stay typed as `ptr` in
  IR instead of being bitcast through integers (which would erase the
  pointer's provenance before the FilPizlonator pass saw it).
- **C++ vtables and pointer-to-member representations** are emitted with
  explicit `ptr` types instead of integer-sized blobs so capabilities
  survive virtual dispatch and PMF call lowering.

### 9.3 The driver

The clang driver is extended to link against the Fil-C runtime stack:

- `libpizlo.so` — Fil-C runtime, including FUGC.
- `-lyoloc` / `-lyolom` — Fil-C's musl-derived libc and libm.
- `-lyolort` — Fil-C's LLVM compiler-rt build.
- `-lyolounwind` — glibc-style unwind stubs.
- `filc_crt.o` / `filc_mincrt.o` — start-up trampolines.
- `ld-yolo-x86_64.so` — bespoke ELF loader.

Four distribution layouts are supported:

| Layout | Lookup |
| --- | --- |
| `pizfix` | Relative to the driver binary (`../../pizfix`) |
| `/opt/fil` | Centralised under `/opt/fil` |
| `filnix` | A small wrapper script |
| `Pizlix` | System default paths (`/usr/include`, `/lib`) |

### 9.4 Optimisations the pass currently performs

- **Allocation inlining** — fast-path allocator inlined into call sites.
- **Bounds-check scheduling** — redundant checks are eliminated within a
  basic block (acknowledged as still improvable).
- **Local escape analysis** — `alloca`s that SROA cannot promote can still
  be stack-allocated if FilPizlonator's analysis proves they don't escape.
- **InstCombine after lowering** — InstCombine is rerun after pizlonation
  to clean up the lowered IR.

The compiler page lists twelve issues (16–27 in the pizlonator/fil-c
tracker) describing the next round of optimisations — pinning the thread
pointer in a register, eliminating redundant function-capability checks for
linker-resolved getters, skipping malloc-getter overhead, preserving more
registers across slow paths, integrating with native unwinding, and so on.

## 10. The `inttoptr` capability-recovery rule

GIMSO singles out `inttoptr` as "super unsafe" — a naive implementation
would let any integer become a usable pointer. Fil-C uses an LLVM-level
abstract interpreter to recover capabilities for the patterns C programmers
actually use (low-bit tagging, alignment masking, XOR encoding, …).

The abstract domain over each SSA value's *inferred capability* is:

```
⊥  (BOTTOM)        — nothing yet known
Definite(C)        — value is known to carry capability C
⊤  (TOP)           — value mixes capabilities; capability is lost
```

Transfer rules:

- `ptrtoint v`         → `Definite(v.capability)`
- `call`/`load`/`atomic`/`icmp`/`bitcast`-from-int → `⊥`
- `phi`/`select`       → fresh phi/select over the operand lattice
- Merge `Definite(A)`, `Definite(B)` where `A != B` → `⊤`
- `⊤` is sticky

Then `inttoptr i` produces:

```
if i.inferred_capability is Definite(C):
    return MakePointer(capability = C, intval = i)
else:
    return MakePointer(capability = NULL, intval = i)
```

That is why example 19 works (XOR-then-XOR in local data flow) and
example 20 panics (the integer round-trips through a global, which is a
load that initialises the lattice to ⊥). It's also why example 21
returns a usable address-only pointer that traps on dereference: pure
synthesised integers never had a capability to recover.

## 11. Disassembly walkthrough — what the model costs

`compiler_example.html` annotates the x86_64 assembly that FilPizlonator
emits for an `insert_sorted` linked-list function. The structural pieces:

### 11.1 Linker thunk

Every public function gets a `pizlonated_<name>` thunk that returns the
*flight pointer to the function* — the actual entry point in `%rax` and
the capability pointer in `%rdx`:

```asm
pizlonated_insert_sorted:
    lea 0x9(%rip),%rax      ; entrypoint
    lea 0x29ca(%rip),%rdx   ; capability
    ret
```

This is the lookup that callers perform before doing an indirect call.

### 11.2 Prologue, stack-overflow check, Pizderson frame

```asm
push %rbp ... push %rbx
sub  $0x58,%rsp
cmp  %rsp,(%rdi)         ; thread.stack_limit at %rdi+0
jae  stack_overflow

mov  0x10(%rdi),%rcx     ; parent Pizderson frame
mov  %rcx,0x28(%rsp)
lea  0x28(%rsp),%rcx
mov  %rcx,0x10(%rdi)     ; push self onto thread frame list
lea  origin_metadata(%rip),%rcx
mov  %rcx,0x30(%rsp)     ; record origin
```

The **thread pointer** is passed in `%rdi` (a known inefficiency — Issue
16 asks for a pinned register). It carries the stack limit, top
Pizderson frame, argument buffers, and the GC pollcheck word.

A **Pizderson frame** is a small per-call stack record that lists the live
capabilities for the GC's accurate stack scan — a non-moving variant of
the Henderson-frame technique.

### 11.3 Calling convention

Arguments and returns are passed through thread-local buffers, not
registers:

```asm
mov  0x80(%rdi),%r13     ; arg.intval     at thread+0x80
mov  0x180(%rdi),%r12    ; arg.capability at thread+0x180
...
mov  %r8,0x80(%rbx)      ; ret.intval
mov  %rsi,0x180(%rbx)    ; ret.capability
mov  $0x8,%edx           ; return_size = 8
xor  %eax,%eax           ; has_exception = 0
```

The size word lets caller and callee detect arity mismatches at runtime —
this is how examples 22–25 panic instead of corrupting memory.

### 11.4 Function-pointer call sequence (calling `malloc`)

```asm
call pizlonated_malloc        ; returns (entrypoint in %rax, cap in %rdx)
test %rdx,%rdx                ; cap non-null?
je   check_fail
mov  -0x8(%rdx),%rcx          ; cap.aux_word
movabs $0x3c0000000000000,%rsi
and  %rcx,%rsi                ; mask flag bits
cmp  $0x40000000000000,%rsi   ; is_function?
jne  check_fail
movabs $0xffffffffffff,%rsi
and  %rsi,%rcx                ; mask out flag bits → true entrypoint
cmp  %rcx,%rax                ; intval matches?
jne  check_fail
mov  $0x8,%esi                ; arg buffer size = 8
mov  %rbx,%rdi                ; thread
call *%rax                    ; do the call
test $0x1,%al                 ; exception flag
jne  propagate_exception
cmp  $0x7,%rdx                ; return_size > 7?
jbe  check_return_fail
```

That's the full check sequence for one indirect call. Issue 20 in the
project tracker notes that the offset check is currently redundant for
pizlonated getters (their result is never offset), so this can be
shortened.

### 11.5 The bounds check at a normal store

For `node->value = value` (an `int` at offset 8 in `node`):

```asm
test  %rsi,%rsi              ; cap != null
je    check_fail
testb $0x6,-0x2(%rsi)        ; not readonly?
jne   check_fail
lea   0x8(%rdi),%rax         ; addr = ptr + 8
cmp   %rsi,%rax              ; addr >= lower?
jb    check_fail
mov   -0x10(%rsi),%rcx       ; cap.upper
add   $-4,%rcx               ; -= sizeof(int)
cmp   %rcx,%rax              ; addr <= upper - 4?
ja    check_fail
mov   %r10d,(%rax)           ; STORE
```

Five test/branch pairs per pointer store. The `testb $0x6, -0x2(%rsi)`
folds two flag tests (readonly, freed) into a single byte read using bits
from the upper-bound pointer's tail byte.

### 11.6 Loading an embedded pointer through the aux allocation

For `*next_ptr` where `next_ptr` is an `int**`:

```asm
mov  %r13,%rbp                ; intval
sub  %r12,%rbp                ; offset = intval - lower
jb   check_fail               ; underflow (ptr < lower)?
cmp  -0x10(%r12),%r13         ; intval < upper?
jae  check_fail
mov  -0x8(%r12),%rax          ; aux_word
and  %rdx,%rax                ; mask 48-bit pointer
je   slow_path_null_aux       ; objects-without-pointers slow path
mov  (%rax,%rbp,1),%r15       ; loaded.capability  (* the key line *)
test $0x1,%r15b               ; atomic-box bit?
jne  unbox_atomic
mov  0(%r13),%r14             ; loaded.intval
```

The aux load `(%rax, %rbp, 1)` is the entire mechanism by which a stored
pointer's capability is recovered on load. Notice that:

- It is **one extra load** per pointer load.
- It uses the *same offset* as the data load (`%rbp`), so the address
  generator only needs a constant — no separate index computation.
- The atomic-box test is one bit, only on the slow path.

### 11.7 The store barrier at a pointer store

```asm
mov  is_marking(%rip),%r9
test %r15,%r15                ; storing null?
je   skip_barrier
cmpb $0x0,(%r9)               ; GC marking phase?
jne  barrier_slow
skip_barrier:
mov  %rcx,(%rax,%rdi,1)       ; aux: capability
mov  %r14,(%r8)               ; payload: intval
```

The Dijkstra barrier is one global byte load and a conditional jump on
the fast path. The CAS to mark the new target only runs during marking.

### 11.8 The pollcheck

Loop back-edges look like:

```asm
testb $0xe,0x8(%rbx)          ; thread.pollcheck_word
jne   pollcheck_slow
mov   %r15,0x40(%rsp)         ; save capability into Pizderson frame
mov   %r14,%r13               ; next iteration
mov   %r15,%r12
test  $0x7,%r13b              ; alignment recheck
je    loop_header
```

The fast path is one `testb` against a thread-local byte. The slow path
runs the pending soft-handshake callback and the GC mark/sweep gating
logic.

## 12. How it compares to SoftBound, CHERI, and friends

These are the two systems Fil-C explicitly positions itself against. The
research literature gives concrete numbers:

### 12.1 SoftBound / CETS

- **Spatial (SoftBound) + temporal (CETS) checks for C.** Both use
  **disjoint metadata** — a shadow table indexed by pointer address — so
  the C ABI is preserved. ([Project page](https://acg.cis.upenn.edu/softbound/),
  [PLDI'09 paper](https://people.cs.rutgers.edu/~santosh.nagarakatte/papers/pldi09_softbound.pdf))
- **Reported overheads:** SoftBound+CETS averages **76% slowdown** on
  SPEC; CETS alone averages ~48%; store-only SoftBound 22%. Pointer-heavy
  benchmarks have been reported as bad as **175%** for the disjoint
  metadata.
  ([Drops/Dagstuhl survey](https://drops.dagstuhl.de/opus/volltexte/2015/5026/pdf/16.pdf),
  [Revisited 2024](https://dl.acm.org/doi/pdf/10.1145/3642974.3652285))
- **Thread safety** is the big known weakness — the disjoint table has
  to be kept coherent under races, which is why Fil-C's older SideCaps
  (which is more or less SoftBound + capability) clocked ≈200× before
  InvisiCaps and FUGC were introduced.

InvisiCaps share the disjoint-metadata idea but replace a flat shadow
table with **per-object aux allocations**. The aux table is reachable
from the *capability*, not from the *raw address*, which removes the
thread-safety problem (the aux pointer rides with the pointer, in flight)
and lets the GC walk metadata efficiently.

### 12.2 CHERI / Morello

- **Hardware capabilities.** CHERI extends the architecture (ARMv8 in
  Morello, also RISC-V and MIPS variants) with **128-bit pointers** plus
  a hidden tag bit (so really 129 bits) carrying base, top, address,
  permissions, and an unforgeability tag.
  ([Cambridge CHERI](https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/),
  [Morello](https://www.thegoodpenguin.co.uk/blog/introducing-arm-morello-cheri-architecture/))
- **CheriABI** runs a recompiled POSIX userspace with spatial and
  referential memory safety end-to-end.
  ([CheriBSD security analysis](https://arxiv.org/html/2601.19074))
- **Trade-offs.** Capabilities double pointer width — substantial memory
  and bandwidth pressure — and the model only covers spatial safety
  natively; **temporal safety (use-after-free) is left to software**.

InvisiCaps' positioning against CHERI:

- ✔ Pointer width matches the host (`sizeof(T*) == 8` on x86_64).
- ✔ Temporal safety is first-class (use-after-free is a deterministic
   panic, via §8's free-singleton repointing).
- ✘ No hardware tag; integrity is purely a property of compilation — i.e.
   the FilPizlonator pass has to be applied to every translation unit.
- ✘ Software cost: ~4× worst case vs. CHERI's claimed sub-2× hardware
   overhead.

### 12.3 No-FAT, Checked C, Cyclone

Briefly:

- **Checked C** (Microsoft Research) adds checked types to C with
  programmer annotations, getting source-level safety with low overhead
  but requiring porting effort. Fil-C explicitly chases zero-source-change
  compatibility, which is incompatible with annotation-based models.
  ([Checked C fat-pointer paper](https://www.cs.rochester.edu/u/jzhou41/papers/checkedc.pdf))
- **No-FAT** (Columbia) pursues hardware support that avoids fat
  pointers entirely by encoding bounds in unused address bits, at the
  cost of fixed allocation classes.
  ([ISCA'21 paper](https://www.cs.columbia.edu/~mtarek/files/preprint_ISCA21_NoFAT.pdf))
- **Cyclone**, **Rust** and friends are sound by language design but
  unable to run legacy C without translation.

InvisiCaps' niche is therefore: *pure software, zero source changes, no
hardware extension, full spatial and temporal safety, including across
races*.

## 13. Bug classes Fil-C eliminates by construction

| Bug class | Mechanism |
| --- | --- |
| Out-of-bounds read / write | Bounds check against `[lower, upper)` on every access |
| Out-of-bounds into a *different* object | A capability covers exactly one object; arithmetic preserves the capability |
| Use-after-free | `free()` sets `upper := lower`; FUGC repoints stale heap capabilities to the free singleton; deterministic panic before *and* after reclamation |
| Double-free | Free flag is sticky; second `free()` panics |
| Uninitialised reads | All allocations zero-initialised; LLVM `undef`/`poison` lowered to zero |
| Type confusion (int ↔ ptr) | Reading an int as a pointer yields null capability; dereference panics |
| Type confusion across links | Linker keeps no ODR assumptions; mismatched globals panic at use |
| Function-pointer confusion | Function capabilities have `upper == lower` and a separate entrypoint slot; offset/arity mismatches panic |
| Variadic mis-usage | Args live in a heap-allocated readonly object sized to the actual call; under/over-read panics |
| Integer overflow in pointer arithmetic | UB flags stripped; access still bound-checked, overflow address simply fails bounds check |
| Race on pointer | Non-atomic: tearing produces an unusable (cap, intval) pair that panics on use. Atomic: 16-byte atomic box prevents tearing |
| Buffer-overflow into stack metadata | Pizderson frames live outside any capability's bounds |
| Spilled-register tampering | Stack spill slots are themselves bound by the frame's capability |

## 14. What is preserved vs. what changes about C

**Preserved.** Integer arithmetic and control flow are unchanged (the UB
flags are stripped, but observable semantics on the integer values are
identical). Pointer arithmetic via GEP is preserved up to bounds
checks. Unions of integer and pointer fields work, including ping-pong
between members. `memcpy`/`memmove`/`memset` work, with capability
propagation (`memcpy` is always lowered to `memmove`). Variadic functions
work. C++ exceptions work via the Itanium ABI (`call`, `invoke`,
`landingpad`, `resume`). `setjmp`/`longjmp` work. Signal handlers work,
including `malloc` from inside a handler (because stack allocations are
heap-allocated).

**Changed.**

- No undefined behaviour: every UB construct becomes either defined
  behaviour or a panic.
- All memory is zero-initialised.
- Capabilities cannot be forged. The only way to create a capability is to
  allocate. The only way to *narrow* one is to `free()`.
- ODR is dropped. Identifiers with mismatched types between TUs trap at
  the use site instead of being trusted.
- Function pointers are special — they cannot be dereferenced as data;
  their integer bits cannot be inspected; offsets break callability.
- Inline assembly is essentially banned (only blank `asm volatile("" : :
  : "memory");`-style barriers are accepted).
- `callbr`, `catchswitch`, `cleanuppad`, `catchpad`, `catchreturn`, and
  `cleanupreturn` LLVM instructions are rejected by FilPizlonator.

## 15. Limitations and open issues (as of the Manifesto / project tracker)

- **Performance.** 1.5× best case, ~4× worst case. The known levers are
  enumerated in [issues 16–27](https://github.com/pizlonator/fil-c/issues)
  (thread-pointer pinning, accurate stack scanning, calling-convention
  redesign, malloc-getter elision, register-alloc origin hoisting,
  pollcheck pruning, slow-path register preservation, native unwinder
  integration, …).
- **Platform.** Currently Linux x86_64 only.
- **Configure-script churn.** Some autoconf probes that lean on UB or
  inline assembly need tweaks.
- **Inline assembly.** Non-blank asm is rejected.
- **Compiler installation.** The Manifesto notes the compiler "currently
  relies on you *not* installing" it — use it from the build tree.
- **Pizderson frames** are a workaround for not having a full accurate
  stack scanner; the compiler emits register-to-frame stores at
  suboptimal points, costing register pressure.
- **`-O` is required.** Without `-O`, the compiler currently crashes.
- **`-g` is required for good panic messages**, since semantic origins
  come from DWARF.

## 16. The link graph

### Fil-C site (canonical docs)

- [Home](https://fil-c.org/) · [Installing](https://fil-c.org/installation.html) · [Documentation](https://fil-c.org/documentation.html)
- [Meet Fil](https://fil-c.org/meet_fil.html)
- [How Fil-C Works](https://fil-c.org/how.html)
- [InvisiCaps: The Fil-C Capability Model](https://fil-c.org/invisicaps.html)
- [InvisiCaps by Example](https://fil-c.org/invisicaps_by_example.html)
- [Garbage In, Memory Safety Out!](https://fil-c.org/gimso.html)
- [Fil's Unbelievable C Compiler](https://fil-c.org/compiler.html)
- [Explanation of Fil-C Disassembly](https://fil-c.org/compiler_example.html)
- [Fil's Unbelievable Garbage Collector](https://fil-c.org/fugc.html)
- [`stdfil.h` Reference](https://fil-c.org/stdfil.html)
- [Fil-C Runtime](https://fil-c.org/runtime.html)
- [Pizfix: The Original Fil-C Staging Area](https://fil-c.org/pizfix.html)
- [`/opt/fil`](https://fil-c.org/optfil.html)
- [Pizlix: Memory Safe Linux From Scratch](https://fil-c.org/pizlix.html)
- [Safepoints and Fil-C](https://fil-c.org/safepoints.html)
- [Constant-Time Crypto](https://fil-c.org/constant_time_crypto.html)
- [Linux Sandboxes and Fil-C](https://fil-c.org/seccomp.html)
- [List of programs ported to Fil-C](https://fil-c.org/programs_that_work.html)

### GitHub / source

- [Manifesto.md](https://github.com/pizlonator/fil-c/blob/deluge/Manifesto.md)
- [FilPizlonator pass](https://github.com/pizlonator/fil-c/blob/deluge/llvm/lib/Transforms/Instrumentation/FilPizlonator.cpp)
- [FUGC implementation](https://github.com/pizlonator/fil-c/blob/deluge/libpas/src/libpas/fugc.c)
- [Runtime](https://github.com/pizlonator/fil-c/blob/deluge/libpas/src/libpas/filc_runtime.c)
- [Verse heap config](https://github.com/pizlonator/fil-c/blob/deluge/libpas/src/libpas/verse_heap.h)
- [Unwind header](https://github.com/pizlonator/fil-c/blob/deluge/filc/include/unwind.h)
- [Exception-handling API](https://github.com/pizlonator/fil-c/blob/deluge/filc/include/pizlonated_eh_landing_pad.h)
- [`gimso_semantics.md` (work-in-progress)](https://github.com/pizlonator/fil-c/blob/deluge/gimso_semantics.md)
- [Releases](https://github.com/pizlonator/fil-c/releases)
- [Repository](https://github.com/pizlonator/fil-c)
- Open optimisation issues: [16](https://github.com/pizlonator/fil-c/issues/16) · [17](https://github.com/pizlonator/fil-c/issues/17) · [18](https://github.com/pizlonator/fil-c/issues/18) · [19](https://github.com/pizlonator/fil-c/issues/19) · [20](https://github.com/pizlonator/fil-c/issues/20) · [21](https://github.com/pizlonator/fil-c/issues/21) · [22](https://github.com/pizlonator/fil-c/issues/22) · [23](https://github.com/pizlonator/fil-c/issues/23) · [24](https://github.com/pizlonator/fil-c/issues/24) · [25](https://github.com/pizlonator/fil-c/issues/25) · [26](https://github.com/pizlonator/fil-c/issues/26) · [27](https://github.com/pizlonator/fil-c/issues/27)

### Pizlonated example ports

- [memory-safe curl](https://github.com/pizlonator/deluded-curl-8.5.0)
- [memory-safe OpenSSH](https://github.com/pizlonator/deluded-openssh-portable)
- [memory-safe OpenSSL](https://github.com/pizlonator/deluded-openssl-3.2.0)
- [memory-safe zlib](https://github.com/pizlonator/deluded-zlib-1.3)
- [memory-safe pcre](https://github.com/pizlonator/pizlonated-pcre-8.39)
- [memory-safe CPython](https://github.com/pizlonator/pizlonated-cpython) (it [found a CPython bug](https://github.com/python/cpython/issues/118534))
- [memory-safe SQLite](https://github.com/pizlonator/pizlonated-sqlite)
- [memory-safe ICU](https://github.com/pizlonator/pizlonated-icu)
- [memory-safe musl](https://github.com/pizlonator/deluded-musl)

### Author

- Filip Pizlo — [@filpizlo](https://x.com/filpizlo) · [filpizlo.com](http://www.filpizlo.com/)

### Background reading referenced by Fil-C

- [SoftBound (PLDI'09)](https://dl.acm.org/doi/10.1145/1543135.1542504) — the disjoint-metadata predecessor of InvisiCaps' "pointers at rest"
- [CHERI (Cambridge)](https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/) — the hardware capability ancestor
- [SoftBound+CETS revisited (2024)](https://dl.acm.org/doi/pdf/10.1145/3642974.3652285)
- [Pointer-based checking survey, Dagstuhl 2015](https://drops.dagstuhl.de/opus/volltexte/2015/5026/pdf/16.pdf)
- [Checked C fat pointers](https://www.cs.rochester.edu/u/jzhou41/papers/checkedc.pdf)
- [No-FAT (ISCA'21)](https://www.cs.columbia.edu/~mtarek/files/preprint_ISCA21_NoFAT.pdf)
- [Dijkstra concurrent GC](https://lamport.azurewebsites.net/pubs/garbage.pdf)
- [Doligez-Leroy concurrent GC](https://xavierleroy.org/publi/concurrent-gc.pdf), [Doligez-Gonthier POPL'94](http://moscova.inria.fr/~doligez/publications/doligez-gonthier-popl-1994.pdf)
- [Henderson accurate GC frames](https://dl.acm.org/doi/10.1145/512429.512449)
- [Fiji VM (EuroSys'10)](http://www.filpizlo.com/papers/pizlo-eurosys2010-fijivm.pdf) and [Schism (PLDI'10)](http://www.filpizlo.com/papers/pizlo-pldi2010-schism.pdf) — Filip Pizlo's earlier GC work
- [LLVM greedy register allocator](https://blog.llvm.org/2011/09/greedy-register-allocation-in-llvm-30.html)
- [GNU IFUNC](https://sourceware.org/glibc/wiki/GNU_IFUNC)
- [OpenJDK safepoints write-up](https://foojay.io/today/the-inner-workings-of-safepoints/)
- [WebKit libpas docs](https://github.com/WebKit/WebKit/blob/main/Source/bmalloc/libpas/Documentation.md)

## 17. Take-aways for a language designer

If you're reading this because you're thinking about safety models for a
new language (the working assumption here, given the repo):

1. **The capability lives with the pointer, not with the address.**
   That's the move that makes InvisiCaps thread-safe and union-safe at
   once. A shadow table keyed by address (SoftBound) needs synchronisation;
   a capability keyed off the pointer itself does not.
2. **Use-after-free is a GC problem, not a checking problem.** A pure
   checking pass cannot guarantee that a freed capability stays
   recognisably freed once its memory is reused, unless an accurate
   collector is keeping the capabilities reachable. Fil-C's `free()` is
   essentially a hint to the collector.
3. **You can keep `sizeof(T*) == 8`** *and* still have spatial+temporal
   safety, by paying a per-object aux allocation only when the object
   actually contains pointers. Strings and pixel data pay zero.
4. **`inttoptr` is a precise abstract-interpretation problem.** A small
   intra-procedural lattice (`⊥`, `Definite(C)`, `⊤`) recovers most C
   tagged-pointer idioms without compromising soundness.
5. **Safepoints, store barriers, and pollchecks are the cost of
   concurrent safety.** Each is a fast load-and-branch; together they
   make accurate concurrent GC viable in a systems language.
6. **A statically-checked language (like A7) can sidestep many of these
   costs** by ruling out the idioms (no `inttoptr` round-tripping, no
   unrestricted unions, no UB pointer arithmetic) at compile time. The
   open question is which Fil-C-style guarantees an A7 program *gives up*
   when it cannot afford the runtime machinery — for instance, A7's
   ban on source-level recursion is in the same spirit as Fil-C's ban
   on unchecked function-pointer reinterpretation: both shrink the set of
   programs to one whose static analysis can be made total.
