<!-- Preserved 2026-09-19 from tmp/research/runtime-model/sources/claim6/SOURCES.md. Repository home-path prefixes normalized; claims and verification statements below are historical. Saved files remain beside the original temporary manifest. -->

# Claim 6 — primary sources
Claim under audit: "First-class differential memory arenas. Dynamic memory allocation is
partitioned into structured, contiguous arena spaces rather than an opaque global heap. The
runtime tracks dirty page deltas and mutation regions at hardware cache-line resolution. This
enables near-zero-cost delta snapshots for time travel, instant state rollbacks, and effortless
zero-copy network serialization for multiplayer synchronization."

Ruling target: "at hardware cache-line resolution" and "near-zero-cost".
All quotes below were verified with `grep -o -F` against the named saved file (see verify.sh).

---

### Linux soft-dirty PTEs
URL: https://docs.kernel.org/admin-guide/mm/soft-dirty.html
Saved: soft-dirty.html -> soft-dirty.txt / Read: 2026-09-18 / Kind: kernel doc
Quote (grep-verified): "The soft-dirty is a bit on a PTE which helps to track which pages a task writes to."
Quote (grep-verified): "The bit 55 of the 64-bit qword is the soft-dirty one. If set, the respective PTE was written to since step 1."
Quote (grep-verified): "Internally, to do this tracking, the writable bit is cleared from PTEs when the soft-dirty bit is cleared."
Quote (grep-verified): "the #PF-s that occur after that are processed fast"
Note: Granularity = one PTE = one page (4 KiB base page on x86-64). Mechanism is write-protect +
page fault, read out via /proc/PID/pagemap. No sub-page resolution exists in the interface. The
kernel's own cost statement is qualitative ("processed fast"), not a number.

---

### Linux userfaultfd write-protect mode
URL: https://docs.kernel.org/admin-guide/mm/userfaultfd.html
Saved: userfaultfd.html -> userfaultfd.txt / Read: 2026-09-18 / Kind: kernel doc
Quote (grep-verified): "It supports range operations by default, so one can enable tracking on any range of memory as long as page aligned."
Quote (grep-verified): "In async mode, there will be no message generated when a write operation happens, meanwhile the write-protection will be resolved automatically by the kernel."
Quote (grep-verified): "It can be seen as a more accurate version of soft-dirty tracking"
Quote (grep-verified): "The dirty result will not be affected by vma changes (e.g. vma merging) because the dirty is only tracked by the pte."
Note: Granularity = the PTE, and registration ranges must be page aligned. Sync mode delivers one
userspace message per faulting page; async mode resolves in-kernel and is read back from
/proc/pagemap. Still page resolution. The kernel doc gives no per-fault cost number —
"not readable — no quote" for a cost figure.

---

### Boehm-Demers-Weiser GC — virtual dirty bit mechanisms
URL: https://raw.githubusercontent.com/bdwgc/bdwgc/master/docs/gcdescr.md
Saved: bdwgc-gcdescr.md -> bdwgc-gcdescr.norm.txt / Read: 2026-09-18 / Kind: implementation doc (primary, project's own)
Quote (grep-verified): "We keep track of modified pages using one of several distinct mechanisms:"
Quote (grep-verified): "(`MPROTECT_VDB`) By write-protecting physical pages and catching write faults."
Quote (grep-verified): "(`SOFT_VDB`) By retrieving Linux soft-dirty bit information from `/proc`."
Quote (grep-verified): "(`UFFDWP_VDB`) By using the Linux `userfaultfd` subsystem in the write-protect mode."
Quote (grep-verified): "performance may actually be better with `mprotect` and signals"
Quote (grep-verified): "When marking completes, the set of modified pages is retrieved"
Note: The production GC that actually ships mprotect-based dirty tracking calls the unit a *page*
throughout; the retrieved set is a "set of modified pages". The saved bdwgc-os_dep.c defines `GC_write_fault_handler`; that this costs one signal-handler
invocation per page per epoch is INFERENCE from the mechanism, not a quoted measurement. No cache-line option exists in
the list of mechanisms.

---

### Intel SDM Vol. 3C — Page-Modification Logging (PML)
URL: https://cdrdv2-public.intel.com/789585/326019-sdm-vol-3c.pdf (326019-081US, September 2023)
Saved: intel-sdm-vol3c.pdf -> intel-sdm-vol3c.txt / Read: 2026-09-18 / Kind: vendor spec
Quote (grep-verified): "Software can enable page-modification logging by setting the “enable PML” VM-execution control"
Quote (grep-verified): "The page-modification log consists of 512 64-bit entries"
Quote (grep-verified): "Bits 11:0 of the value written are always 0 (the guest-physical address written is thus 4-KByte aligned)."
Quote (grep-verified): "When accessed and dirty flags for EPT are enabled, software can track writes to guest-physical addresses using a feature called page-modification logging."
Quote (grep-verified): "Whenever there is a write to a guest-physical address, the processor sets the dirty flag"
Quote (grep-verified): "in the EPT paging-structure entry that identifies the final physical address for the guest-physical address"
Note: PML is the closest thing x86 has to a hardware-maintained dirty *set*, and it is explicitly
4-KByte granular — the low 12 address bits are forced to zero. It is a VMX feature: enabled by a
"VM-execution control", logging *guest-physical* addresses, i.e. usable by a hypervisor, not by an
application runtime. Log capacity is 512 entries before a VM exit.

---

### Arm — hardware management of dirty state (DBM), Armv8.1-A
URL: https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Learn%20the%20Architecture/Armv8-A%20memory%20model%20guide.pdf
Saved: arm-cd6c2a.pdf -> arm-memmodel.txt / Read: 2026-09-18 / Kind: vendor doc (Arm, ARM062-948681440-3279)
Quote (grep-verified): "Armv8.1-A introduced the ability for the processor to manage the dirty state of a block or page."
Quote (grep-verified): "Dirty state records whether the block or page has been written to."
Quote (grep-verified): "When managing dirty state is enabled, software initially creates the translation table entry with the access permission set to ReadOnly and the DBM (Dirty Bit Modifier) bit set."
Quote (grep-verified): "The page would be marked as Read-Only, resulting in an exception (permission fault) on the first write."
Note: Granularity = "a block or page" (the doc's own words). That the unit is the translation
granule, and that Arm granules are 4/16/64 KiB, is INFERENCE — not stated in the fetched text. The state lives in a translation table entry. No cache-line resolution.
The full Arm ARM (DDI0487) itself was not fetched — this is Arm's own published guide.

---

### HotSpot (OpenJDK) card table size
URL: https://raw.githubusercontent.com/openjdk/jdk/master/src/hotspot/share/gc/shared/gc_globals.hpp
Saved: hotspot-gc_globals.hpp -> hotspot-gc_globals.norm.txt / Read: 2026-09-18 / Kind: implementation source (primary)
Quote (grep-verified): "product(uint, GCCardSizeInBytes, 512,"
Quote (grep-verified): "\"Card table entry size (in bytes) for card based collectors\""
Quote (grep-verified): "constexpr uint MaxGCCardSizeInBytes = NOT_LP64(512) LP64_ONLY(1024);"
Note: Default card = 512 bytes; maximum 1024 on 64-bit. Eight cache lines per card at the low end.
This is a software write barrier: the compiler emits a store to the card byte on every reference
store. See cardTable.hpp (also saved) for `_card_shift` / `_card_size`.

---

### .NET (CoreCLR) card table size
URL: https://raw.githubusercontent.com/dotnet/runtime/main/src/coreclr/gc/gcpriv.h
Saved: coreclr-gcpriv.h -> coreclr-gcpriv.norm.txt / Read: 2026-09-18 / Kind: implementation source (primary)
Quote (grep-verified): "#define GC_PAGE_SIZE 0x1000"
Quote (grep-verified): "#define card_word_width ((size_t)32)"
Quote (grep-verified): "#define card_size ((size_t)(2*GC_PAGE_SIZE/card_word_width))"
Quote (grep-verified): "The value of card_size is determined empirically according to the average size of an object"
Note: Arithmetic: 2 * 0x1000 / 32 = 256 bytes per card on 64-bit (128 bytes on 32-bit, where the
`2*` is absent). This is the finest card granularity found in any shipped runtime, and it is still
4x a 64-byte cache line. The comment states it is chosen by average object size, not by cache line.

---

### .NET GC — cards are set by JIT-emitted write barriers
URL: https://raw.githubusercontent.com/dotnet/runtime/main/docs/design/coreclr/botr/garbage-collection.md
Saved: dotnet-gc-botr.md -> dotnet-gc-botr.norm.txt / Read: 2026-09-18 / Kind: vendor design doc
Quote (grep-verified): "The GC uses cards for the older generation marking. Cards are set by JIT helpers during assignment operations."
Quote (grep-verified): "If the JIT helper sees an object in the ephemeral range it will set the byte that contains the card representing the source location."
Note: Card marking is compiler-inserted instrumentation on *reference* assignments only, and is
filtered (only ephemeral-range targets). It does not observe scalar stores.

---

### Go write barrier
URL: https://raw.githubusercontent.com/golang/go/master/src/runtime/mbarrier.go
Saved: go-mbarrier.go -> go-mbarrier.norm.txt / Read: 2026-09-18 / Kind: implementation source (primary)
Quote (grep-verified): "For the concurrent garbage collector, the Go compiler implements // updates to pointer-valued fields that may be in heap objects by // emitting calls to write barriers."
Quote (grep-verified): "The main write barrier for // individual pointer writes is gcWriteBarrier and is implemented in // assembly."
Note: Granularity is the individual pointer-valued field (a word), but it is compiler-emitted code
on pointer stores only — the runtime never sees an ordinary scalar store. Not a hardware mechanism
and not a dirty-region map.

---

### Blackburn & Hosking, "Barriers: Friend or Foe?", ISMM 2004 — MEASURED barrier cost
URL: https://www.steveblackburn.org/pubs/papers/wb-ismm-2004.pdf
Saved: wb-ismm-2004.pdf -> wb-ismm-2004.txt / Read: 2026-09-18 / Kind: research paper, measured result
Quote (grep-verified): "the average overhead for a reasonable generational write barrier was less than 2% on average, and less that 6% in the worst case"
Quote (grep-verified): "The average costs are 1.01%, 0.80%, and 4.59% for the AMD, P4 and PPC respectively."
Quote (grep-verified): "the card barrier assumes a heap divided into fixed-size 2k -byte logical cards"
Quote (grep-verified): "where typically 7 ≤ k ≤ 10"
Quote (grep-verified): "we dispel the assumption that barrier overhead should be a primary motivator for such efforts"
Note: This is the price of the compiler-instrumentation alternative to hardware dirty tracking.
Card barrier mutator overhead measured at 1.01% (AMD), 0.80% (P4), 4.59% (PPC); the headline
generational write-barrier figure is <2% average, <6% worst case. Hardware vintage is 2004: the paper says
"We perform our experiments on three architectures: Athlon, Pentium 4, and Power PC." (grep-verified
in wb-ismm-2004.txt), in Jikes RVM on SPECjvm98 + pseudojbb. Card sizes surveyed are
2^7..2^10 bytes = 128..1024 bytes — the paper's own definition of "typical" never reaches 64 bytes.
Critically, these barriers instrument *reference stores only*; a general state-delta tracker must
instrument every store, so 1-2% is a lower bound for the claim's use case (inference, not measured).

---

### Intel SDM Vol. 1 — Intel TSX tracks read/write sets at cache-line granularity
URL: https://cdrdv2-public.intel.com/671436/253665-sdm-vol-1.pdf (253665-078US, December 2022)
Saved: intel-sdm-vol1.pdf -> intel-sdm-vol1.txt / Read: 2026-09-18 / Kind: vendor spec
Quote (grep-verified): "Intel TSX maintains the read- and write-sets at the granularity of a cache line."
Quote (grep-verified): "Since Intel TSX detects data conflicts at the granularity of a cache line, unrelated data locations placed in the same cache line will be detected as conflicts."
Quote (grep-verified): "the amount of data accessed in the region may exceed an implementation-specific capacity"
Note: This is the ONE documented commodity-x86 mechanism that tracks writes at 64-byte
granularity. It is not a readable dirty set: the write-set is internal state used to abort on
conflict, and capacity is implementation-specific and bounded by cache geometry. There is no
instruction to enumerate it.

---

### Intel SDM Vol. 1 — CLFLUSH / CLFLUSHOPT / CLWB are cacheability control, not dirty readout
URL: https://cdrdv2-public.intel.com/671436/253665-sdm-vol-1.pdf
Saved: intel-sdm-vol1.pdf -> intel-sdm-vol1.txt / Read: 2026-09-18 / Kind: vendor spec
Quote (grep-verified): "TLB and Cacheability control: CLFLUSH, CLFLUSHOPT, CLWB, INVD, WBINVD, INVLPG, INVPCID"
Note: The SDM classifies CLWB/CLFLUSHOPT as cacheability control (write-back/invalidate of a named
line). They act on an address software already supplies; they report nothing back. The per-
instruction description lives in SDM Vol. 2A, which returned HTTP 403 from cdrdv2-public —
"not readable — no quote" for the full instruction text.

---

### Intel — TSX disabled by default via microcode
URL: https://www.intel.com/content/www/us/en/support/articles/000059422/processors.html
Saved: intel-tsx-support.html -> intel-tsx-support.txt (HTML entity-decoded) / Read: 2026-09-18 / Kind: vendor doc
Quote (grep-verified): "Intel® TSX will be disabled by default."
Quote (grep-verified): "The processor will force abort all Restricted Transactional Memory (RTM) transactions by default."
Quote (grep-verified): "A new CPUID bit CPUID.07H.0H.EDX[11](RTM_ALWAYS_ABORT) will be enumerated, which is set to indicate to updated software that the loaded microcode is forcing RTM abort."
Quote (grep-verified): "Additionally, Intel TSX will be disabled by default in two additional CPUIDs with IPU 2021.2."
Note: On the listed parts, IPU 2021.1+ microcode force-aborts all RTM transactions. Claims that
TSX was *removed* from later microarchitectures appeared only in search snippets and secondary
press; not verified here and not relied on.

---

### GGPO — rollback netcode state snapshots
URL: https://raw.githubusercontent.com/pond3r/ggpo/master/src/include/ggponet.h
Saved: ggponet.h -> ggponet.norm.txt / Read: 2026-09-18 / Kind: implementation source (primary, shipped SDK)
Quote (grep-verified): "save_game_state - The client should allocate a buffer, copy the * entire contents of the current game state into it, and copy the * length into the *len parameter."
Quote (grep-verified): "bool (__cdecl *save_game_state)(unsigned char **buffer, int *len, int *checksum, int frame);"
Note: (`//` and `*` are the source files own comment markers, preserved verbatim.) The reference rollback-netcode SDK's snapshot API is a full byte-copy of the whole game
state per frame, not a delta. Confirms snapshot/rollback over a contiguous state region is
established practice; it also shows the shipped state of the art is bulk copy, not dirty-delta.

---

### GGPO — what rollback is
URL: https://raw.githubusercontent.com/pond3r/ggpo/master/doc/README.md
Saved: ggpo-readme.md -> ggpo-readme.norm.txt / Read: 2026-09-18 / Kind: vendor doc
Quote (grep-verified): "The term \"rollback\" refers to the process of rewinding state and predicting new outcomes based on new, more correct information about a player's input."
Quote (grep-verified): "Rollback networking is designed to be integrated into a fully deterministic peer-to-peer engine."
Note: Supports the uncontroversial half of the claim (arena + snapshot + rollback is real and
shipped), and adds a precondition the claim omits: full determinism.

---

### NEGATIVE FINDING — nothing exposes cache-line dirty state to software
Kind: absence, established from the sources above
What was checked, by fetched primary source:
- Intel PML: 4-KByte aligned log entries, VMX-only (SDM Vol. 3C 29.3.6, quoted above).
- x86 PTE / EPT dirty flags: per paging-structure entry, i.e. per page (SDM Vol. 3C 29.3.5; see the
  two grep-verified sentences in the PML block above).
- Arm DBM: "a block or page" (Arm guide, quoted above).
- Linux soft-dirty: "a bit on a PTE ... which pages a task writes to" (kernel doc, quoted above).
- Linux userfaultfd-WP: "as long as page aligned" (kernel doc, quoted above).
- Intel TSX/RTM: cache-line granularity but conflict-detection only, no enumeration instruction,
  and force-aborted by microcode on the listed parts (SDM Vol. 1 + Intel support article, above).
- CLWB / CLFLUSHOPT: classified by the SDM as "TLB and Cacheability control" — they flush a line
  whose address software already knows; they return no dirty set (SDM Vol. 1, quoted above).
- Every shipped software card table found is coarser than a cache line: HotSpot 512 B default,
  CoreCLR 256 B on 64-bit, Jikes RVM survey 128-1024 B.
Discovery searches run in this session (WebSearch, discovery only, nothing quoted from snippets):
Blackburn/Hosking ISMM 2004 PDF; Intel SDM PML "4-KByte page"; Intel TSX disable /
RTM_ALWAYS_ABORT; Arm DBM / dirty state / translation granule. A further query specifically for a
commodity-CPU API exposing per-cache-line dirty state could not be run — the session's WebSearch
budget was exhausted — so this negative is established from the vendor specs above rather than
from an exhaustive search. Not readable / not fetched: Intel SDM Vol. 2A (403), Intel TSX
Deprecation PDF 643557 (403), Arm ARM DDI0487 (not fetched).
