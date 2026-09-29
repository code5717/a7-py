# Memory plan edge-case audit

Status: summary of five audits of [memory plan](../../memory.md) revision 1,
2026-09-15. Revision 2 applied audits 1, 3, 4 and 5. Audit 2 arrived later and is
applied in revision 3. Full reports are in [audit](audit/).

Expected results in the audits are hand traces. Probe results are compile-only
unless a report states otherwise.

## Reports

| Report | Scope | Edge cases | Applied in |
| --- | --- | --- | --- |
| [Audit 1](audit/audit-1-values-moves-extents.md) | Values, moves, extents, escape, control flow, generics | 80 | Revision 2 |
| [Audit 2](audit/audit-2-collections-strings-exclusivity.md) | Collections, strings, exclusivity, optionals, unions, copy placement | 81 | Revision 3 |
| [Audit 3](audit/audit-3-concurrency-failure-native.md) | Concurrency, failure, native boundaries, resources | 68 | Revision 2 |
| [Audit 4](audit/audit-4-tensors-autodiff.md) | Tensors, autodiff, AI workloads | 72 | Revision 2 |
| [Audit 5](audit/audit-5-consistency-impact.md) | Plan consistency, current compiler, implementation impact | Findings F1–F17 | Revision 2 |

A GLM review of memory safety and security (L12) completed on 2026-09-16 after two
failed attempts. It reviews revision 2 rather than revision 1, and its findings
are in the [review index](review/README.md).

### Gate numbers in audit 4

Audit 4 numbered its proposed gates before the plan assigned M14 and M15. Read
its numbers as follows:

| Audit 4 | M14 | M15 | M16 | M17 | M18 | M19 | M20 | M21 | M22 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Plan | M17 | M18 | M19 | M20 | M21 | M22 | M23 | M2 | M24 |

## Blockers in revision 1

| # | Finding | Sources | Revision 2 response |
| --- | --- | --- | --- |
| B1 | Runtime checks and program stop on out-of-memory contradict the fail-closed safety contract | Audit 5 F1 | Contract items 7 and 12 name every residual check and its outcome; gate M16 amends the safety contract |
| B2 | Rejections are not only exclusivity conflicts | Audits 1, 5 | Contract item 8 listed nine rejection classes; the reviews found eight more, and revision 3 lists seventeen |
| B3 | A plain `usize` cannot carry a generation | Audits 3, 5 | Positions stay `usize`; removal uses `Id(T)` with generations |
| B4 | "Shares storage until changed" needs runtime state | Audits 1, 4, 5 | Copy is the meaning of assignment; copies are removed only when provably unobservable |
| B5 | Unbounded retention in loops | Audits 1, 3, 5 | Contract item 5 adds the iteration release floor |
| B6 | Out-of-memory policy by value type gives contradictory results | Audits 3, 4 | Gate M2 decides by owning extent |
| B7 | Resources cannot be plain values | Audit 3 | Resources are move-only |
| B8 | Changing a saved tensor both copies and rejects | Audit 4 | Rejection class 7 and gate M18 |
| B9 | Breaking-change table incomplete, one row wrong | Audits 1, 3, 5 | Table rebuilt from probes |

## Audit 2 items and where they landed

Audit 2 reviewed revision 1. Revision 2 already replaced removable `usize` links
with `Id(T)` in a `Table`, and replaced share-until-changed with copy semantics.
Revision 3 places the rest:

| Item | Where it landed |
| --- | --- |
| What a `for` loop binding holds, and whether `x := list[i]` copies | Gate M30 for the binding, gate M33 for the lookup. Every reviewer who examined M33 recommends a view rather than a copy; the memory plan records that the gate has not adopted it |
| Snapshot or read view for the loop binding, and structural change during iteration (G-05, Q-C3) | Gate M51, which puts both readings to the user. A read view brings the G-07b breaking-change row for fixed-array bodies that write to the owner |
| Whether slices are read-only, and whether the owner may change while a slice is live. Today `s := arr[0..2]; arr[0] = 7` runs and `s[0]` then prints 7 (CF-13) | Gate M13: views are read-only, and any structural change or overlapping write while a view is live is rejected (G-04). Rejection class 2, plus a breaking-change row (G-07) |
| `List` positions after a removal that shifts later elements (G-01) | Gate M1: positions are shift-sensitive, and removal-capable storage is `Table(T)` |
| Whether `ret s[0..i]` from a function returning `string` copies | Gates M13 and M32; returning a view is rejection class 15 |
| Unions that own storage, and defaults for storage-owning types | Gate M49 |
| Missing `Map` keys | Gates M33 and M39 |
| Ids used with the wrong table | Gate M42 |
| `.ptr` exposure | Removed from the public surface in the breaking-change table |
| Releasing or recycling an element's storage when it is removed, so an evicting cache keeps memory flat | Contract item 5, with corpus program 25 |
| Evaluation order of aggregate assignment: read every source before any write | Contract item 5, with corpus program 24 |

## Current-compiler defects

Found during the audits. Compile-only unless noted. Probe IDs (`p`, `q`) and
fact IDs (`CF-`) refer to the named audit.

**Wrong output (built and executed in Debug and ReleaseFast)**

- `arr = [arr[1], arr[0]]` prints `2 2`. The emitted Zig
  `arr = .{ arr[1], arr[0] };` writes element 0 before reading it (audit 2
  CF-20).

**Unsafe programs accepted**

- `ref` locals, `ref` returns, `ref` values stored in struct fields or globals,
  and returned slices of locals compile and can dangle. Examples from audit 1:
  `id :: fn(p: ref Pt) ref Pt { ret p }` (p23) and
  `get :: fn() []i32 { buf: [4]i32 = [1, 2, 3, 4]; buf[0] = 5; ret buf[0..2] }`
  (q13).
- Aliased `ref` arguments compile: `both(x, x)`, and `set2(arr[i], arr[j])` with
  `i == j` (audit 5 p5, p10c).
- Overlapping `ref` writes `setx(p.x, p)` compile and run. The emitted call is
  `setx(&p.x, &p)`, and the program prints `6` (audit 2 CF-19).
- `del` through a `ref` parameter frees a stack slot, and a later use is accepted.
  Audit 3 p13: `drop_it :: fn(p: ref Box) { del p }`, then the caller writes
  `b.value = 1`. Audit 5 p16 emits `allocator.destroy(&x)`.
- A double `del` inside a `while` loop is accepted (audit 1 p06).
- A read of a variable that no path assigned is accepted after a zero-iteration
  loop: `last: Pt; for x in empty { last = x }; print(last.x)` (audit 1 EC1-C08).
- Untagged unions accept `string` fields and reads of the inactive field (audit 2
  CF-31).

**Valid programs rejected**

- A second write through a scalar `ref` parameter is rejected because a proof fact
  is overwritten. The first `dst = 0` replaces the parameter's non-nil fact, so
  `dst = 1` fails with "reference may be nil" (audit 2 CF-25).
- Use-after-`del` tracking is keyed by name and ignores branch joins. A `del p` in
  a `then` branch makes reads of `p` in the `else` branch fail, and
  `{ p := new Pt; del p }; p := 5; q := p + 1` is rejected at the unrelated `p`
  (audit 1 p08, p17).
- Block-form `defer { io.println(..); del b }` is tracked as an immediate delete,
  so a later use of `b` fails with "Use after move or delete". The
  single-statement `defer del b` form is not affected (audit 3 p09, p11).
- `ref [N]T` parameters cannot be indexed ("Cannot index this type: got
  'ref [4]i32'"), and slice or string parameters cannot be indexed or sliced
  (audit 2 CF-26, CF-10).

**Accepted by A7 but rejected when Zig builds the output**

- String `==` ("operator == not allowed for type '[]const u8'"), uninitialized
  arrays of structs (`pts: [3]Pt` lowers to `[_]Pt{0} ** 3`), and writes through a
  slice, which emit `const arr` (audit 2 CF-09, CF-32, CF-12).
- A mutable global: `counter := 0` emits `var counter = 0;`, which Zig rejects as
  `comptime_int` (audit 5 p17).
- Writes to by-value array parameters, such as `a[0] = 7` (audit 5 p4b), and to
  `for-in` bindings, such as `for v in arr { v.x = 9 }` (audit 1 p20).
- `del` of a variable named `p`. The lowering `if (x) |p| allocator.destroy(p)`
  triggers "capture 'p' shadows local constant", and A7 still exits 0 (audit 5 p7,
  p12).

**Other**

- `c: char = 'é'` compiles as `char` despite the ASCII rule; it lowers to
  `const c: u8 = 'é'` (audit 2 CF-15).
- `?T` is not tokenized: `x: ?i32` fails with "Unexpected character: '?'" (audit 2
  CF-29).
- `--format json` exits 1 on a `match` expression that yields a struct, instead of
  the documented internal-error exit 8 (audit 1 F12).
- The SPEC `swap` example does not compile (audit 1 F11, audit 2 CF-23).
- `examples/025_linked_list.a7` uses `isize` indices with `-1`.
- No native declaration syntax exists: `cos :: extern fn(x: f64) f64` fails with
  "Undefined type (Identifier 'extern')" (audit 3 p05).

## Implementation impact

From audit 5: 12 compiler modules (about 330 matching lines), 13 or more examples
with golden outputs, 26 test files with about 364 of 2,527 tests matching by name,
one error-stage fixture, and 10 public documentation files.

## Gate questions

The audits' open questions became memory plan gates M2, M6, M7, M10–M13 and
M16–M36. Questions from audit 2 and the reviews will be added in revision 3.
