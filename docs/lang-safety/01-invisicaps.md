# 01 — InvisiCaps: The Fil-C Capability Model

Status: external-technology study notes on Fil-C, written before 2026-09-14.
Current A7 decisions are in the [decision ledger](../plan/decisions.md).

Part of the `docs/lang-safety/` series ([README](./README.md)). Siblings:
[02 — Sanitizers](./02-sanitizers.md) ·
[03 — Hardware-assisted safety](./03-hardware.md) ·
[04 — Comparison](./04-comparison.md) ·
[05 — Take-aways for A7](./05-for-a7.md).

These notes summarize Fil-C's pointer capability system from the primary
sources at <https://fil-c.org> and the project's Manifesto. They are not
affiliated with Fil-C. Fil-C is © Epic Games, Apache2 / BSD licensed.

Primary sources:

- <https://fil-c.org/invisicaps.html> — the capability model
- <https://fil-c.org/invisicaps_by_example.html> — worked examples
- <https://fil-c.org/gimso.html> — Garbage In, Memory Safety Out semantics
- <https://fil-c.org/fugc.html> — Fil's Unbelievable Garbage Collector
- <https://fil-c.org/compiler.html> — the FilPizlonator LLVM pass
- <https://fil-c.org/compiler_example.html> — annotated disassembly
- <https://fil-c.org/documentation.html> — documentation index
- <https://fil-c.org/meet_fil.html> — project background
- <https://github.com/pizlonator/fil-c/blob/deluge/Manifesto.md> — Manifesto

---

## 1. What Fil-C is

Fil-C is a fork of clang 20.1.8. It compiles ordinary C and C++ into a
memory-safe program by giving LLVM IR memory-safe semantics.

Every pointer carries a *capability*: a runtime token naming the object the
pointer may reach and the bounds of that object. The capability is invisible:
`sizeof(T*) == 8` on a 64-bit host. In registers the capability travels next
to the pointer. In memory it lives in a *shadow address space*.

FUGC manages allocations. It is a concurrent, on-the-fly, accurate,
non-moving garbage collector. Calling `free()` is legal but optional. It
gives the capability zero bounds; it does not reclaim memory.

The motto is "Garbage In, Memory Safety Out!" (GIMSO). However broken or
adversarial the input program is, the worst outcome is a Fil-C panic, never a
memory-safety violation.

Per the Manifesto, Fil-C is 1.5× slower than C in good cases and about 4×
slower in worst cases. It runs unmodified ports of curl, OpenSSL, OpenSSH,
zlib, pcre, SQLite, CPython, ICU, libc++/libc++abi, and musl.

## 2. Why InvisiCaps — what the previous models could not do

InvisiCaps are the third capability representation in Fil-C. The earlier
models show the design pressure:

| Model | Pointer size | Use-after-free | Type changes after malloc | Thread-safe | Overhead |
| --- | --- | --- | --- | --- | --- |
| PLUT (Pointer / Lower / Upper / Type) | 256 bits | No | Type fixed at allocation | No | — |
| SideCaps (Sidecar + capability) | 64 bits | No | Type fixed at allocation | Yes | ≈200× |
| MonoCaps (Monotonic capabilities) | 128 bits | Yes (deterministic panic) | Limited; C++ support added | Yes | ≈10× |
| InvisiCaps | 64 bits | Yes | Yes — meaningful unions, int↔ptr ping-pong | Yes | ≈4× worst case |

What InvisiCaps gain:

1. **Native pointer size on 64-bit hosts.** Plain C data structures keep
   their ABI shape.
2. **Dynamic type reinterpretation works.** A program can store an int, load
   it as a pointer, store a pointer, and load it as an int, repeatedly. When
   the pointer's provenance is destroyed it loses its capability, and any
   access through it traps deterministically.
3. **Atomic pointer operations are lock-free**, even though the capability
   lives elsewhere in memory.
4. **Use-after-free traps even after the memory is reclaimed.** The GC
   repoints stale capabilities to a free singleton instead of letting them
   dangle.

The project describes InvisiCaps as a "practical, totally thread-safe
variant of [SoftBound]" and as "a software implementation of [CHERI]" with
smaller pointers and explicit use-after-free handling. §12 compares them.

## 3. The flight pointer

A *flight pointer* is a pointer in registers or local data flow, in transit
between memory accesses. It is a 2-tuple:

```
(lower, intval)
   |       \__ the raw 64-bit address visible to C code
   \__________ the lower bound; immutable; cannot be forged by C code
```

The allocator sets `lower`. Every pointer derived from an allocation inherits
that `lower`. Arithmetic (GEP, pointer addition, casts, masking, XORing low
bits) changes `intval` but never changes `lower`. This is the structural
invariant of the model.

`lower` points just above the object's 16-byte header:

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

`upper` is read at a negative offset from `lower` (`-0x10` in the disassembly
walkthrough). `aux_word` is read at `-0x8`.

`aux_word` packs three things:

- **Low 48 bits:** a pointer to the *aux allocation*, which stores the
  invisible capabilities of pointers stored in the payload. NULL if the
  object holds no pointers.
- **High 16 bits:** flags. They encode object alignment (so the GC can find
  the true allocation base across alignment padding), special-object type
  tags, freed/readonly flags, and similar bits.
- **Special objects** whose payload is not data (function pointers, threads,
  mmap regions) set flag bits and store the callable address or true
  entrypoint in the same word.

### 3.1 The four legal access predicates

Per GIMSO, an access of `N` bytes through pointer `P` is legal only if all of
these hold:

```
P.intval >= P.capability->lower
P.intval <  P.capability->upper
P.intval + N <= P.capability->upper
```

These three lines are one bounds predicate. The heading's count of four
matches the predicate kinds the pass inserts (§9.1): bounds, readonly,
not-freed, and alignment. Section 11.5 shows the readonly and freed flags
checked in one byte test.

The runtime compiles the upper-bound test in one of three forms, chosen to
avoid integer-overflow attacks:

| Form | When used |
| --- | --- |
| `P <= upper - S` | `S` is a known constant; the usual compiler output |
| `P < upper && P + S <= upper` | `S` is dynamic; used in the runtime |
| `P < upper` | `S` equals the access alignment, so the bound implies the size |

If a check fails, the slow path prints a `filc safety error` panic and
aborts.

## 4. Pointers at rest — the invisible capability

The new idea is how a pointer is stored to memory. In flight, the capability
rides in another register. In memory, an explicit fat pointer would either
double the width of every pointer (breaking ABI and unions) or need a shadow
table with a load barrier on every pointer read.

InvisiCaps avoid both with a per-object aux allocation:

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

- Payload bytes store the `intval` of each embedded pointer, as legacy C
  does. `(char*)&p` reads sensible address bits.
- Aux bytes at the same offset store the `lower` of the embedded pointer.
  Each aligned 8-byte aux slot mirrors an aligned 8-byte payload slot.
- The aux allocation is itself an InvisiCap object, but the program never
  gets a capability into it. Only the runtime and the FilPizlonator pass can
  address it.
- An object with no pointer fields has a NULL `aux_word` and no aux
  allocation. Strings and pixel buffers pay no space overhead. This is why
  "the space overhead of InvisiCaps is nowhere near 2×."

### 4.1 The inductive hypothesis

The source page states the property that keeps the model closed under all
operations:

> Every flight pointer's *lower* points to the top of an object header
> whose aux word contains a way to get the *lowers* for all pointers
> stored to that object's payload.

Loading a pointer therefore reduces to:

```text
;; pseudo-code for *(T**)p in non-atomic mode
intval        = LoadFromPrimarySpace(p.intval)    ; the address bits
aux_base      = (p.lower → header.aux_word) & 0x0000FFFFFFFFFFFF
capability    = aux_base[p.intval - p.lower]      ; the invisible lower
return (lower = capability, intval = intval)
```

Storing a pointer is the mirror image: write `intval` to the payload and
`lower` to the aux allocation at the same offset.

### 4.2 GIMSO load/store semantics, restated

The canonical lowered forms from gimso.html:

```
;; non-atomic pointer load
CapabilityOrAtomicBox = LoadFromShadowSpace(P.intval)
Intval                = LoadFromPrimarySpace(P.intval)
return MakePointer(capability = CapabilityOrAtomicBox, intval = Intval)

;; non-atomic pointer store
StoreToPrimarySpace(P.intval, V.intval)
StoreToShadowSpace (P.intval, V.capability)
```

The access predicates (§3.1) run before both. The shadow address space is
conceptual; the aux allocation implements it.

## 5. Atomic InvisiCaps

`_Atomic`, `volatile`, and `std::atomic` pointers must survive races without
tearing the (intval, capability) pair. Fil-C adds an atomic box behind the
aux slot:

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

- The box holds a full flight pointer in 16 bytes. It is read and written
  with `cmpxchg16b`-class instructions.
- The `intval` is also mirrored into the payload, so a non-atomic integer
  load of the field still sees the address bits.
- A store need not allocate a new box each time. The implementation may
  reuse a box for repeated writes to the same location.
- A racing non-atomic store can corrupt the `intval` mirror but not the box.
  The pair never tears into an unsafe pointer. The worst outcome is "time
  travel": a stale but well-formed pointer, which traps if its bounds do not
  fit the access.

In `invisicaps_by_example.html` test #18, a non-atomic pointer race panics
about once per hundred runs with `ptr < lower`. Declaring `int* _Atomic ptr`
removes the race.

## 6. Special objects

The flag bits and the 48-bit slot of `aux_word` also encode non-data objects.

### 6.1 Function pointers

- `intval` is the entrypoint visible to C.
- `lower` points to a function capability with `upper == lower`, so any data
  access fails the upper-bound check.
- The flag bits mark a function capability. The 48-bit slot stores the true
  entrypoint that an indirect call must match.
- Calling-convention mismatches between caller and callee are detected at
  run time. Argument and return sizes are part of the function-capability
  protocol.

### 6.2 Threads, mmap regions, Sys-V shared memory

- Pointers refer to internal `zthread` or region objects. Their bounds equal
  `lower` (no payload access), and flag bits select the variant.
- Runtime functions that take a thread pointer read the flag bits to check
  the type before touching the payload.

### 6.3 Freed objects

- `free(p)` sets `upper := lower`, so every later bounds check fails.
- A "free" bit in the aux word feeds diagnostics (`free` appears in panic
  dumps).
- FUGC also repoints in-memory capabilities of the freed object to a global
  free singleton. A stale pointer still traps after the memory is reclaimed
  and reused. See §8.

### 6.4 Aligned / mmap allocations

- Flag bits record the requested alignment so the GC can find the true
  allocation base across alignment padding.
- A flag marks objects that need special GC handling (mmap, shared memory).

## 7. Worked examples (from `invisicaps_by_example.html`)

The example page is the quickest way to learn the model. Every panic has
this format:

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

The catalogue below keeps every example's safety classification:

| # | Hazard | Source sketch | Result |
| --- | --- | --- | --- |
| 1 | OOB write | `char* p = malloc(16); p[42] = 100;` | `ptr >= upper` |
| 2 | OOB but inside another object | `x[y - x] = '!';` | `ptr >= upper`; the capability of `x` does not cover `y` |
| 3 | Address wrap | `p -= (uintptr_t)p; p += UINT_MAX; *(int*)p = 42;` | `ptr >= upper`, intval `0xFFFFFFFFFFFFFFFF` |
| 4 | Negative offset to syscall | `write(1, "hello\n" - 100, 6)` | `ptr < lower` |
| 5 | Oversized syscall read | `write(1, "hello\n", 100)` | `upper - ptr = 8`, expected 100 |
| 6 | Pointer in memory shows aux | `*(int**)p = malloc(4)` | `%P` prints `aux=<addr>` |
| 7 | Integer-then-pointer reinterpretation | `*(int*)p = 666; int* p2 = *(int**)p;` | Loaded pointer has a `<null>` capability; access panics |
| 8 | Pointer-then-integer reinterpretation | Read the low 32 bits of an embedded pointer | Works; non-pointer type confusion is allowed |
| 9 | Store pointer, overwrite intval bits, reload | Embedded pointer keeps its capability after the intval is rewritten | `ptr < lower`: the capability survives but the intval no longer fits its bounds |
| 10 | int↔float reinterpretation | `*(float*)&x` | Allowed; no pointer involved |
| 11 | Unions of int / pointer / double | `union u { ... }` | All field reads succeed; only dereferencing an int-shaped pointer traps |
| 12 | Read a function pointer's bytes | `(int)*((char*)foo)` | `cannot read pointer to special object` |
| 13 | Call a `malloc` chunk as a function | `foo()` where `foo = malloc(16)` | `cannot access pointer as function, object isn't even special` |
| 14 | Offset function pointer | `(char*)foo + 42`, then call | `cannot access pointer as function with ptr != aux` |
| 15 | Plain use-after-free | `free(p); *p = 42;` | `cannot write pointer to free object`, with `upper == lower` |
| 16 | UAF with heap grooming | 100M reallocations between free and use | Still panics; FUGC keeps the freed capability alive |
| 17 | UAF through a pointer stored in another object | `free(*p); ... **p = 42` | Panics; the capability was swapped to the free singleton |
| 18 | Pointer race | Non-atomic shared `int* ptr` changed by two threads | Occasional `ptr < lower` panic; fixed by `_Atomic` |
| 19 | XOR then undo a pointer in local data flow | `(const char*)((uintptr_t)str ^ 1)` | Works; the compiler recovers the capability through `ptrtoint`→`inttoptr` |
| 20 | Same as #19 through a global `uintptr_t` | Round trip through a global | Panics on dereference; the load is a bare `inttoptr` with no provenance |
| 21 | Cast `42` to a pointer | `(int*)42` | Can be carried around; traps on dereference |
| 22–26 | Bad linking: arity mismatch, type mismatch, function as data, data as function, `const` mixup | Mismatched declarations across translation units | Each traps at the use site, not at link time, because Fil-C drops the ODR assumption |
| 27 | Variadic underflow | `foo(10, 666)` | Reading the 2nd `va_arg` traps with `ptr >= upper`; the heap va-buffer is sized to the actual arguments |
| 28 | Variadic type mismatch | int passed, string expected | `cannot read pointer with null object`; the int landed in a pointer slot with no capability |
| 29 | `va_list` escaping its frame | Use `va_list` after return | Works; variadic arguments live in a heap-allocated readonly object that outlives the frame |
| 30 | Pure leak | 1 trillion bytes allocated without `free` | FUGC reclaims; RSS stays at ~5–7 MB |

Example 19 relies on real abstract interpretation: the `inttoptr`
capability-recovery rule in §10.

## 8. FUGC — the garbage collector that backs the model

InvisiCaps work only if bounds metadata stays alive. FUGC keeps it alive.
The Manifesto describes FUGC as a parallel, concurrent, on-the-fly,
grey-stack, Dijkstra, accurate, non-moving collector:

| Property | Meaning in FUGC |
| --- | --- |
| Parallel | Marking and sweeping run on multiple threads. |
| Concurrent | GC threads are separate from mutator threads. A mutator blocks only in the slow path of an allocation. |
| On-the-fly | No global stop-the-world. The GC uses soft handshakes (ragged safepoints): it asks each thread to run a small callback at its next safepoint. The callback scans that thread's stack; its cost is bounded by stack height and is usually below a `malloc` slow path. |
| Grey-stack | Stacks are rescanned to a fixpoint, so there is no load barrier. Each iteration is another soft handshake; it converges in a few rounds in practice. |
| Dijkstra | A store barrier marks the target of every pointer store during marking. The barrier is a CAS with relaxed ordering, on the slow path only. |
| Accurate | FilPizlonator tells the runtime where every pointer lives on the stack and in globals. Pointers out of heap objects can only live in aux allocations. |
| Non-moving | Objects never move, which keeps concurrency cheap. The one exception is free-singleton repointing. |

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

Other details:

- **Safepoints.** FilPizlonator emits `pollchecks` at loop back-edges and
  other bounded points. The fast path is a load and a conditional branch.
  The slow path runs the pollcheck callback, which carries the soft
  handshakes.
- **Enter/exit.** A thread blocking in a syscall announces that it is
  parked, so the GC can run its callback on the thread's behalf.
- **Stop-the-world** is an optional mode. `fork(2)` uses it, and
  `FUGC_STW=1` enables it for debugging.
- **Sweeping** uses bit-vector SIMD in libpas's Verse heap config. FUGC
  spends "<5% of its time sweeping."
- **Free repoints to a singleton.** When FUGC reclaims a freed object, it
  rewrites every in-memory capability of that object to a global free
  singleton with `lower == upper`. The aux allocation makes this cheap:
  pointer fields sit at known offsets with known capabilities. Stale copies
  on stacks and in registers already have `upper == lower` from `free()`.
- **Finalizers and weak references.** The runtime provides `zgc_finq`
  (Java-style finalizer queues), `zweak` (weak references without queues; no
  phantom or soft variants), and `zweak_map` (a WeakMap with iteration).

The use-after-free guarantee rests on three facts together:

1. `free()` sets `upper := lower` on the freed object's capability, so every
   flight pointer naming it traps.
2. Before reclaiming the memory, FUGC rewrites every in-memory pointer
   naming the freed capability to name the free singleton, so pointers
   loaded after the next GC also trap.
3. Memory is reused only after both steps, so no capability is ever silently
   retargeted.

## 9. The FilPizlonator compilation pipeline

The compiler is clang 20.1.8 plus one new LLVM pass and two small CodeGen
changes.

### 9.1 The LLVM pass — `llvm::FilPizlonatorPass`

The pass runs after a mostly standard clang mid-end pipeline (SROA, inliner,
DCE, redundant load/store elimination, InstCombine), so GIMSO rewrites see
clean IR. The pass:

- Rewrites every pointer SSA value into a `(capability, intval)` tuple, the
  IR-level flight pointer.
- Inserts bounds, readonly, not-freed, and alignment predicates before every
  memory access, including SIMD loads/stores, atomic operations, and
  memcpy/memset/memmove intrinsics.
- Lowers heap allocations to FUGC allocator calls with an inlined fast path.
- Rewrites the calling convention. Arguments and returns pass in 8-byte
  aligned slots, each holding an intval and a capability, through a
  thread-local argument buffer (see §11.3).
- Drops the `nuw`/`nsw`/`inbounds`/`inrange` UB flags from `getelementptr`
  and arithmetic. GIMSO defines those behaviors instead of leaving them
  undefined.
- Implements the `inttoptr` abstract interpretation that recovers
  capabilities for round-tripped pointers (§10).
- Generates pollchecks at safepoints, stack maps for FUGC, and Pizderson
  frames (per-call stack records that give FUGC a precise view of
  capabilities held in registers).
- Lowers unsupported IR (most `cleanuppad`, `catchswitch`, `callbr`,
  branching inline assembly) to always-panic code instead of miscompiling.

> "Either the pass will fail to generate any output (the compiler will
> crash), or the generated IR follows the memory safety doctrine."

### 9.2 Clang CodeGen tweaks

- **CGAtomic** keeps pointer atomics typed as `ptr` in IR instead of bitcasting
  them through integers, which would erase provenance before FilPizlonator
  runs.
- **C++ vtables and pointer-to-member values** are emitted with explicit
  `ptr` types instead of integer-sized blobs, so capabilities survive virtual
  dispatch and PMF call lowering.

### 9.3 The driver

The clang driver links the Fil-C runtime stack:

| Component | Role |
| --- | --- |
| `libpizlo.so` | Fil-C runtime, including FUGC |
| `-lyoloc` / `-lyolom` | musl-derived libc and libm |
| `-lyolort` | LLVM compiler-rt build |
| `-lyolounwind` | glibc-style unwind stubs |
| `filc_crt.o` / `filc_mincrt.o` | Start-up trampolines |
| `ld-yolo-x86_64.so` | Custom ELF loader |

Four distribution layouts are supported:

| Layout | Lookup |
| --- | --- |
| `pizfix` | Relative to the driver binary (`../../pizfix`) |
| `/opt/fil` | Centralised under `/opt/fil` |
| `filnix` | A small wrapper script |
| `Pizlix` | System default paths (`/usr/include`, `/lib`) |

### 9.4 Optimisations the pass currently performs

- **Allocation inlining:** the allocator fast path is inlined at call sites.
- **Bounds-check scheduling:** redundant checks are removed within a basic
  block. The project says this can still improve.
- **Local escape analysis:** `alloca`s that SROA cannot promote stay on the
  stack if FilPizlonator proves they do not escape.
- **InstCombine after lowering:** InstCombine runs again to clean up the
  lowered IR.

The compiler page lists twelve issues (16–27 in the pizlonator/fil-c
tracker) for the next optimisations: pinning the thread pointer in a
register, removing redundant function-capability checks for linker-resolved
getters, skipping malloc-getter overhead, preserving more registers across
slow paths, integrating with native unwinding, and others.

## 10. The `inttoptr` capability-recovery rule

GIMSO calls `inttoptr` "super unsafe": a naive implementation would let any
integer become a usable pointer. Fil-C runs an LLVM-level abstract
interpreter that recovers capabilities for common C idioms: low-bit tagging,
alignment masking, XOR encoding.

The abstract domain for each SSA value's inferred capability:

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

`inttoptr i` then produces:

```
if i.inferred_capability is Definite(C):
    return MakePointer(capability = C, intval = i)
else:
    return MakePointer(capability = NULL, intval = i)
```

This explains three examples from §7:

| Example | Why |
| --- | --- |
| 19 works | XOR then XOR stays in local data flow; the lattice stays `Definite` |
| 20 panics | The integer passes through a global; the load starts the lattice at `⊥` |
| 21 traps on dereference | A synthesized integer never had a capability to recover |

## 11. Disassembly walkthrough — what the model costs

`compiler_example.html` annotates the x86_64 assembly FilPizlonator emits for
an `insert_sorted` linked-list function.

### 11.1 Linker thunk

Every public function gets a `pizlonated_<name>` thunk. It returns the flight
pointer to the function: the entry point in `%rax` and the capability in
`%rdx`. Callers perform this lookup before an indirect call.

```asm
pizlonated_insert_sorted:
    lea 0x9(%rip),%rax      ; entrypoint
    lea 0x29ca(%rip),%rdx   ; capability
    ret
```

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

The thread pointer arrives in `%rdi`. This is a known inefficiency; Issue 16
asks for a pinned register. The thread object holds the stack limit, the top
Pizderson frame, the argument buffers, and the GC pollcheck word.

A Pizderson frame is a small per-call stack record listing live capabilities
for the GC's accurate stack scan. It is a non-moving variant of Henderson
frames.

### 11.3 Calling convention

Arguments and returns pass through thread-local buffers, not registers:

```asm
mov  0x80(%rdi),%r13     ; arg.intval     at thread+0x80
mov  0x180(%rdi),%r12    ; arg.capability at thread+0x180
...
mov  %r8,0x80(%rbx)      ; ret.intval
mov  %rsi,0x180(%rbx)    ; ret.capability
mov  $0x8,%edx           ; return_size = 8
xor  %eax,%eax           ; has_exception = 0
```

The size word lets caller and callee detect arity mismatches at run time.
This is how examples 22–25 panic instead of corrupting memory.

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

This is the full check sequence for one indirect call. Issue 20 notes that
the offset check is redundant for pizlonated getters, whose result is never
offset, so the sequence can be shorter.

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

A pointer store costs four test/branch pairs before the write. The
`testb $0x6, -0x2(%rsi)` folds the readonly and freed tests into one byte
read, using bits in the high byte of the upper-bound pointer.

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

The aux load `(%rax, %rbp, 1)` is the whole mechanism for recovering a stored
pointer's capability:

- It costs one extra load per pointer load.
- It reuses the data load's offset (`%rbp`), so no separate index is
  computed.
- The atomic-box test is a single bit and branches only to a slow path.

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

On the fast path the Dijkstra barrier is one global byte load and a
conditional jump. The CAS that marks the new target runs only during
marking.

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

The fast path is one `testb` against a thread-local byte. The slow path runs
the pending soft-handshake callback and the GC mark/sweep gating logic.

## 12. How it compares to SoftBound, CHERI, and friends

Fil-C positions itself against SoftBound and CHERI. The research literature
gives numbers for both.

### 12.1 SoftBound / CETS

- **Spatial (SoftBound) and temporal (CETS) checks for C.** Both use disjoint
  metadata, a shadow table indexed by pointer address, so the C ABI is
  preserved.
  ([Project page](https://acg.cis.upenn.edu/softbound/),
  [PLDI'09 paper](https://people.cs.rutgers.edu/~santosh.nagarakatte/papers/pldi09_softbound.pdf))
- **Reported overheads:** SoftBound+CETS averages a 76% slowdown on SPEC.
  CETS alone averages ~48%; store-only SoftBound, 22%. Pointer-heavy
  benchmarks reach 175% for the disjoint metadata.
  ([Drops/Dagstuhl survey](https://drops.dagstuhl.de/opus/volltexte/2015/5026/pdf/16.pdf),
  [Revisited 2024](https://dl.acm.org/doi/pdf/10.1145/3642974.3652285))
- **Thread safety is the main weakness.** The disjoint table must stay
  consistent under races. Fil-C's older SideCaps, roughly SoftBound plus a
  capability, measured ≈200× before InvisiCaps and FUGC.

InvisiCaps keep disjoint metadata but replace the flat shadow table with
per-object aux allocations. The aux table is reached from the capability,
not from the raw address. That removes the thread-safety problem, because
the aux pointer travels with the pointer in flight, and lets the GC walk
metadata efficiently.

### 12.2 CHERI / Morello

- **Hardware capabilities.** CHERI extends the architecture (ARMv8 in
  Morello, plus RISC-V and MIPS variants) with 128-bit pointers and a hidden
  tag bit (129 bits in total). The capability holds base, top, address,
  permissions, and the unforgeability tag.
  ([Cambridge CHERI](https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/),
  [Morello](https://www.thegoodpenguin.co.uk/blog/introducing-arm-morello-cheri-architecture/))
- **CheriABI** runs a recompiled POSIX userspace with spatial and referential
  memory safety end to end.
  ([CheriBSD security analysis](https://arxiv.org/html/2601.19074))
- **Trade-offs.** Capabilities double pointer width, which adds memory and
  bandwidth pressure. The hardware covers spatial safety only; temporal
  safety (use-after-free) is left to software.

InvisiCaps compared with CHERI:

| | InvisiCaps | CHERI |
| --- | --- | --- |
| Pointer width | Host width (`sizeof(T*) == 8` on x86_64) | 16 bytes plus tag |
| Temporal safety | Built in: deterministic panic via free-singleton repointing (§8) | Left to software |
| Integrity source | Compilation only; FilPizlonator must process every translation unit | Hardware tag bit |
| Cost | ~4× worst case, in software | Claimed under 2×, in hardware |

### 12.3 No-FAT, Checked C, Cyclone

- **Checked C** (Microsoft Research) adds checked types to C through
  programmer annotations. It gets source-level safety with low overhead but
  needs porting work. Fil-C aims for zero source changes, which rules out
  annotation-based models.
  ([Checked C fat-pointer paper](https://www.cs.rochester.edu/u/jzhou41/papers/checkedc.pdf))
- **No-FAT** (Columbia) uses hardware support to avoid fat pointers by
  encoding bounds in unused address bits, at the cost of fixed allocation
  classes.
  ([ISCA'21 paper](https://www.cs.columbia.edu/~mtarek/files/preprint_ISCA21_NoFAT.pdf))
- **Cyclone, Rust**, and similar languages are sound by design but cannot run
  legacy C without translation.

The InvisiCaps niche: pure software, zero source changes, no hardware
extension, full spatial and temporal safety, including under races.

## 13. Bug classes Fil-C eliminates by construction

| Bug class | Mechanism |
| --- | --- |
| Out-of-bounds read / write | Bounds check against `[lower, upper)` on every access |
| Out-of-bounds into a different object | A capability covers exactly one object; arithmetic preserves the capability |
| Use-after-free | `free()` sets `upper := lower`; FUGC repoints stale heap capabilities to the free singleton; deterministic panic before and after reclamation |
| Double-free | The free flag is sticky; a second `free()` panics |
| Uninitialised reads | All allocations are zero-initialised; LLVM `undef`/`poison` lowers to zero |
| Type confusion (int ↔ ptr) | Reading an int as a pointer yields a null capability; dereference panics |
| Type confusion across links | No ODR assumption; mismatched globals panic at use |
| Function-pointer confusion | Function capabilities have `upper == lower` and a separate entrypoint slot; offset and arity mismatches panic |
| Variadic misuse | Arguments live in a heap-allocated readonly object sized to the actual call; under- and over-reads panic |
| Integer overflow in pointer arithmetic | UB flags stripped; the overflowed address fails the bounds check |
| Race on a pointer | Non-atomic: a torn (cap, intval) pair is unusable and panics on use. Atomic: the 16-byte atomic box prevents tearing |
| Buffer overflow into stack metadata | Pizderson frames lie outside every capability's bounds |
| Spilled-register tampering | Stack spill slots are bounded by the frame's capability |

## 14. What is preserved vs. what changes about C

**Preserved:**

- Integer arithmetic and control flow. UB flags are stripped, but observable
  results on integer values are identical.
- Pointer arithmetic via GEP, subject to bounds checks.
- Unions of integer and pointer fields, including ping-pong between members.
- `memcpy`/`memmove`/`memset`, with capability propagation. `memcpy` always
  lowers to `memmove`.
- Variadic functions.
- C++ exceptions via the Itanium ABI (`call`, `invoke`, `landingpad`,
  `resume`).
- `setjmp`/`longjmp`.
- Signal handlers, including `malloc` inside a handler, because stack
  allocations are heap-allocated.

**Changed:**

- No undefined behaviour. Every UB construct becomes defined behaviour or a
  panic.
- All memory is zero-initialised.
- Capabilities cannot be forged. Allocation is the only way to create one;
  `free()` is the only way to narrow one.
- ODR is dropped. Identifiers with mismatched types across translation units
  trap at the use site.
- Function pointers are special. They cannot be read as data, their integer
  bits cannot be inspected, and offsetting them breaks callability.
- Inline assembly is effectively banned. Only blank
  `asm volatile("" : : : "memory");`-style barriers are accepted.
- FilPizlonator rejects the LLVM instructions `callbr`, `catchswitch`,
  `cleanuppad`, `catchpad`, `catchreturn`, and `cleanupreturn`.

## 15. Limitations and open issues (as of the Manifesto / project tracker)

- **Performance.** 1.5× best case, ~4× worst case. The known levers are in
  [issues 16–27](https://github.com/pizlonator/fil-c/issues): thread-pointer
  pinning, accurate stack scanning, calling-convention redesign,
  malloc-getter elision, register-alloc origin hoisting, pollcheck pruning,
  slow-path register preservation, native unwinder integration, and others.
- **Platform.** Linux x86_64 only.
- **Configure scripts.** Some autoconf probes that rely on UB or inline
  assembly need changes.
- **Inline assembly.** Non-blank asm is rejected.
- **Installation.** The Manifesto says the compiler "currently relies on you
  *not* installing" it; use it from the build tree.
- **Pizderson frames** stand in for a full accurate stack scanner. The
  compiler stores registers to frames at suboptimal points, which costs
  register pressure.
- **`-O` is required.** Without `-O` the compiler crashes.
- **`-g` is required for good panic messages**, because semantic origins come
  from DWARF.

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

1. **The capability lives with the pointer, not with the address.** This
   makes InvisiCaps thread-safe and union-safe at once. A shadow table keyed
   by address (SoftBound) needs synchronisation; a capability reached from
   the pointer does not.
2. **Use-after-free is a GC problem, not a checking problem.** A checking
   pass alone cannot keep a freed capability recognisably freed after its
   memory is reused. That needs an accurate collector keeping capabilities
   reachable. Fil-C's `free()` is effectively a hint to the collector.
3. **`sizeof(T*) == 8` is compatible with spatial and temporal safety.** The
   cost is a per-object aux allocation, paid only by objects that hold
   pointers. Strings and pixel data pay nothing.
4. **`inttoptr` is a precise abstract-interpretation problem.** A small
   intra-procedural lattice (`⊥`, `Definite(C)`, `⊤`) recovers most C
   tagged-pointer idioms without losing soundness.
5. **Safepoints, store barriers, and pollchecks are the cost of concurrent
   safety.** Each is a fast load and branch. Together they make accurate
   concurrent GC viable in a systems language.
6. **A statically checked language such as A7 can avoid many of these costs**
   by ruling out the idioms at compile time: no `inttoptr` round trips, no
   unrestricted unions, no UB pointer arithmetic. The open question is which
   Fil-C guarantees an A7 program gives up without the runtime machinery.
   A7's ban on source recursion has the same spirit as Fil-C's ban on
   unchecked function-pointer reinterpretation: both shrink the program set
   to one where static analysis can be total.

> Note (2026-09-16): take-away 6 overstates current A7. Casts involving
> `ref` or function types are forbidden
> ([`a7/cast_classifier.py`](../../a7/cast_classifier.py)), so there is no
> `inttoptr` round trip. But A7 has untagged unions today, and any member
> can be read ([SPEC §3 Unions](../SPEC.md),
> [`examples/016_unions.a7`](../../examples/016_unions.a7)). Union
> discriminant proofs are incomplete ([STATUS](../STATUS.md),
> [SAFETY_CONTRACT](../SAFETY_CONTRACT.md)).
>
> ```a7
> // Current A7 (from examples/016_unions.a7)
> io :: import "std/io"
>
> Value :: union {
>     int_val: i32
>     float_val: f64
> }
>
> main :: fn() {
>     int_value := Value{int_val: 42}
>     io.println("int: {}", int_value.int_val)
> }
> ```
>
> Take-away 2 (use-after-free needs a collector) does not carry over as a
> plan. Ledger L15 rules out a runtime collector. The proposed
> [memory plan](../plan/memory.md) removes `del` from ordinary code and
> rejects stored or returned `ref` values instead. It is not yet approved.
