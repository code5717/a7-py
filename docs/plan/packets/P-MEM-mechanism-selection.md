# P-MEM: automatic memory mechanism selection

Status: proposed, not approved. This packet compares eligible mechanisms under
L37–L39 and L42. It does **not** select a production memory runtime, change A7
syntax, or authorize implementation. Record a ledger disposition before any
runtime work. Needs ledger approval before implement.

Authority:

- [L37](../decisions.md): compiler-managed runtime tracking is allowed when
  static analysis is insufficient; no mechanism is selected.
- [L38](../decisions.md): each required equivalent workload must keep median
  runtime and peak live memory ≤ 1.10× a reviewed C baseline, including
  bookkeeping; no candidate is qualified.
- [L39](../decisions.md): prefer compile-time proof; allow checked execution
  where proof is unavailable; required checks stay in release builds.
- [L42](../decisions.md): growable-list assignment shares identity; explicit
  copies create independent data.
- Historical [memory plan](../memory.md) (rev 3, 2026-09-16): unapproved detail;
  its absolute ban on collectors/counting is superseded by L37.
- [Delivery roadmap](../delivery-roadmap.md) memory sections and
  [STATUS Planned work](../../STATUS.md).
- Vision audit (2026-11-12 store doc `docs/a7-vision-audit.md`): select a
  mechanism and qualify L38; W1–W5 fixtures do not qualify L38.

## Current vs proposed behavior

### Current (observable today)

| Topic | Behavior |
| --- | --- |
| Surface | `new T` / `del` / `nil` references remain in the language and examples |
| Value copies | Plain structs and fixed arrays without slice/`ref` members copy on `:=` |
| Slice / string | Slice assignment and structs holding slices share storage |
| Growable lists | No production `List`/`Map`/`Table` automatic-memory surface |
| Runtime | No production A7 memory runtime; Zig owns generated allocation today |
| Mechanism | Unselected (L37). Arena/RC prototypes exist as standalone fixtures only |
| L38 | Unqualified for every required workload |

Compile-checked probes from the historical plan (2026-09-15/16): after
`b := a; b.x = 2` on a plain struct, `a.x` stays 1; after
`arr2 := arr; arr2[0] = 9` on a fixed array, `arr[0]` stays 1. Slice-backed
copies share storage. Returning a slice of a mutable local is accepted and can
dangle. Aliased `ref` arguments such as `both(x, x)` are accepted.

### Proposed (if this packet is approved after measurement)

Ordinary programs allocate and free nothing by name. The compiler places
storage, inserts releases, and may insert runtime tracking only where static
proof fails (L37, L39). Growable collections follow L42:

```a7
// Proposed shared identity (L42). Not implemented.
a := List(i32){}
a.append(1)
b := a
b.append(2)          // a and b observe the same list
c := copy(a)         // spelling TBD; independent data
c.append(3)          // a/b unchanged by c's append
```

Structs and fixed arrays without shared collection members keep today's value
copy behavior unless a later packet changes them. Escape that cannot be proven
safe is either a rejection with a rewrite or a compiler-inserted owned copy
(choice still open; see reconciliation). Exactly-once cleanup and bounded
retention hold for long-running bounded workloads. Each required workload must
pass the L38 protocol below before that mechanism is called production-ready.

This packet asks only for: (1) a preferred candidate class for the next
measurement campaign, (2) approval of the L38 protocol, (3) a later ledger entry
after measured results. It does not authorize shipping that candidate.

## W1–W5 evidence summary

Roadmap step 4 names the seven required shapes: shared lists, explicit copies,
cyclic graphs, returned data, bounded caches, retained text, failure cleanup.
W1–W5 are the first five fixture families. They are Debug/O0 standalone
correctness probes with requested-backing peaks. They are not L38
qualification, automatic A7 lowering, or production mechanism selection.
Records live under `docs/audits/2026-10-07/`.

| Workload | What was checked | Native checks | Requested backing peaks (bytes) | Still open |
| --- | --- | --- | --- | --- |
| W1 growth | 10,000 values, growth failures, logical handle across realloc, stop-before-publish corruption | 112 after alignment repair (first Zig attempt failed before any workload) | C/arena 196,608; RC 196,672 | Timing, full runtime storage, competitive realloc/segmented alts, L38 |
| W2 shared + snapshot | Shared row update seen on both live paths; historical snapshot independent; failure cleanup | 75 Debug | C/arena 48; RC 144 | Timing, complete runtime memory, optimized builds, L38 |
| W3 cycles | Real node cycles, deletion, allocation-failure cleanup, intact-cycle abort | 75 Debug | Peak C/arena 96, RC 192; after delete C 72 / arena 96 / RC 144; arena keeps 24 dead payload until teardown | General cycle collection, timing, L38 |
| W4 returned records | 1,000 produced, 334 returned (keys % 3 == 0); exact copy vs compact-in-place; producer cleanup | 138 (24 workload cases) | C/arena exact 22,368 / compact 17,024; RC exact 22,440 / compact 17,072 | Timing, complete peak memory, L38 |
| W5 bounded cache | Independent models agree at 10k and 100k accesses; inline and fixed-pool C baselines | 84 each C baseline (O0) | Declared inventories 651 (inline) and 475 (pool); not measured peaks | Managed arena/RC native run, large workloads, optimized execution, full accounting, L38 |

Foundation context (STATUS): small arena/RC fixtures passed 134 Debug checks; a
strengthened trace checker accepts 24 archived traces and rejects 710
count/layout mutations. That does not cover the seven shapes or L38.

RC overhead in these fixtures is header/metadata cost, not a measured runtime
ratio. W3 RC clears that container's owned edges before releasing roots; that is
not a general cycle collector. Arena on W3 retains dead payload until teardown.

## Mechanism comparison

Eligible under L37. None selected. Figures below cite W1–W5 requested peaks or
stated design properties, not L38 medians.

| Candidate | Fits L42 shared lists | Cycles (W3) | Ordinary-code simplicity (L19) | Pause / determinism | Likely L38 risk | Evidence so far |
| --- | --- | --- | --- | --- | --- | --- |
| Static reuse / extents / placement | Needs moves, regions, or rewrites; shared growable identity is hard without runtime or language restriction | Same-extent cycles can die at reset; cross-extent graphs need ids/tables or rejection | Best when proofs succeed; rejections and new concepts (`Table`/`Id`) appear on escape | Deterministic release points; no scan pauses | Copy fallback and rejection rate; compiler analysis cost | Historical plan preferred this; M29 soundness gate not closed; no L38 run |
| RC + cycle policy | Natural for L42 share-on-assign | Needs cycle detection, explicit edge clearing, or ban; W3 prototype is edge-clear, not general CC | Counts are invisible but headers and cycle rules are not free concepts in diagnostics | Teardown can be bursty; atomics if shared across tasks later | Header bytes already +64 (W1), 3× (W2), 2× (W3) vs C/arena requested peaks | W1–W4 RC fixtures pass bounded Debug correctness |
| Tracing GC | Can preserve shared identity | Handles cycles by reachability | Low source vocabulary; runtime and tooling vocabulary rises | Pauses or concurrent marking conflict with historical no-pause goal and L20 C-like targets unless highly constrained | Peak live + heap reserve and bookkeeping vs 1.10× | Eligible under L37; no A7 workload prototype under the L38 protocol |
| Hybrid (static first + RC where unproven + explicit cycle policy) | Static for non-escaping values; RC for shared collections | Policy required: reject, extent-reset, targeted clearing, or deferred CC | Matches L39 (“prove first, check when needed”) | Releases stay mostly explicit; residual RC work is local | Bookkeeping must still clear 1.10× including headers | Matches arena/RC prototype direction already measured for correctness |

Reconciliation notes that still affect any choice: Perceus does not prove a
count-free design; FP² uniqueness at definitions is not call-site sharing;
escape may reject or copy; M33 optional-copy vs temporary view is unsettled;
M48 ordinary/advanced split is not approval.

## Concrete recommendation

**Preferred candidate class for the next measurement campaign: hybrid.**

1. Default path: compile-time ownership, extents, and proven reuse (static
   placement). Prefer proof over runtime (L39).
2. Where static proof cannot preserve L42 shared growable identity or required
   escape behavior: insert RC (or an equivalent uniqueness/count check) only on
   those values.
3. Cycle policy for W3-class graphs must be stated before measurement: targeted
   ownership clearing, extent-local reset, typed ids/tables, or a bounded cycle
   collector. The W3 RC edge-clear prototype is a starting comparison point, not
   a selected collector.
4. Do **not** adopt tracing as the primary mechanism unless hybrid fails L38 on
   named workloads with reviewed baselines. Tracing remains an eligible
   comparison baseline under L37.
5. Do **not** remove `new`/`del`/`nil` or ship collections until a later
   subtractive packet passes after the mechanism clears L38 on the required
   shapes.

**This recommendation is for ledger review only.** It is not silent adoption.
No production memory runtime may be implemented from this packet alone.

If measurement shows no candidate meets L38, report measured tradeoffs to the
user. Do not relax the 1.10× limits silently (roadmap rule).

## L38 measurement protocol

Authority: L38 text; delivery roadmap “Required measurements” and memory
qualification controls (five warmups, thirty measured samples).

### Gate

For each required equivalent workload and each candidate under test:

- Median wall time ≤ 1.10 × reviewed C baseline.
- Peak live allocated bytes ≤ 1.10 × reviewed C baseline, **including** runtime
  bookkeeping.
- Also report, but do not substitute for the two limits above: reserved memory,
  RSS, allocation count, copy bytes, cleanup time, A7 compile time, Zig compile
  time, emitted code size.

Correctness failures, leaks, double frees, or silent semantic drift reject the
candidate for that workload. Compile-only acceptance is not native evidence.

### Procedure

1. Freeze workload specs, inputs, oracles, and candidate acceptance rules before
   the series. Independent derivation of expected results; do not copy oracles
   from a candidate.
2. Pin Linux x86-64 host, CPU, RAM, kernel, power policy, Zig/C toolchains,
   flags, and source revision. Record working-tree patch if any.
3. Independent authors write C baselines from the specs (not from candidate
   sources). Baselines preserve algorithm, outputs, identity semantics, and
   failure handling. Review competitiveness before the timed series.
4. Profiles: at least ReleaseFast (or agreed release-equivalent) for L38 timing
   and peak-live; Debug/sanitizer runs are separate correctness tracks.
5. Per workload × candidate × profile:
   - **5 warmup** process runs (discarded from medians).
   - **30 measured** fresh-process runs.
   - Alternate baseline and candidate order across the series.
   - Record every sample, median, and p95.
   - Keep checksum/oracle work outside timed regions.
6. Scale workloads that are too short for stable timing before the series; do
   not claim L38 on sub-millisecond noise.
7. For bounded cache/request shapes, compare N and 10N with fixed per-iteration
   input size; report RSS and live bytes so allocator caching cannot hide
   retention.
8. Instrument counts and peaks on a dedicated instrumented build; measure wall
   time on a separate uninstrumented build when instrumentation distorts timing.
9. One workload fails ⇒ that candidate is not L38-qualified for that workload.
   Aggregate gates do not substitute.

### Required workload set before “mechanism selected”

Minimum for a selection ledger entry:

- The seven roadmap shapes (shared lists, explicit copies, cyclic graphs,
  returned data, bounded caches, retained text, failure cleanup), mapped today
  to W2/L42, explicit-copy controls, W3, W4, W5, W8-class text retention, and
  W6-class cleanup from
  [delivery-reconciliation.md](../research/memory/delivery-reconciliation.md).
- W1 growth remains in the comparison set.
- Promote only after native correctness, then L38. Proxy compile-only counters
  and host-pin ratios do not satisfy L38.

## Compatibility impact

| If approved later | Impact |
| --- | --- |
| Hybrid measurement campaign only | No user-facing language change; new prototypes and harnesses under plan/tmp audit paths |
| Mechanism selected after L38 | Additive collections and invisible releases first; `new`/`del`/`nil` removal needs a separate subtractive packet (historical plan phase C2) |
| L42 shared lists | Breaks any assumption that growable assignment deep-copies; structs/fixed arrays unchanged unless separately approved |
| Escape reject vs copy | Changes which programs compile; needs before/after examples in a follow-up packet |
| Safety contract | M16-style amendment of `SAFETY_CONTRACT.md` only after residual checks and rejection list are final |
| Fail-closed migration | L39 requires an explicit migration packet before weakening current fail-closed behavior |

No CHANGELOG language-feature claim belongs to this packet. Docs must keep
saying mechanism unselected until a ledger entry says otherwise.

## Decision requested

Please record one ledger disposition:

1. **Approve hybrid as the primary measurement candidate** (plus L38 protocol
   above), still unselected for production until measured results return; or
2. **Redirect** to another primary candidate (static-only, RC+CC, tracing, or a
   named other hybrid); or
3. **Defer** measurement until named prerequisites (for example M29 soundness
   suite, collections surface packet, or baseline authors) land.

Until that disposition exists: no production memory runtime implementation,
no claim that a mechanism is selected, and no silent L38 limit change.

**Needs ledger approval before implement.**
