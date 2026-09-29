> **Source:** Claude Code audit subagent 2, collections, strings, exclusivity, optionals, unions, copy placement.  
> **Date:** 2026-09-15. Audit of docs/plan/memory.md revision 1.  
> **Status:** Advisory. Expected results are hand traces; probe results are labeled compile-only, built or executed. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

# Audit 2: collections, strings and slices, exclusivity, optionals and unions, share-until-changed

Date: 2026-09-16. Subject: `docs/plan/memory.md` (proposed, 2026-09-15), with
`docs/plan/decisions.md` L15-L19 and `docs/plan/research/memory/synthesis.md`.
Repository tree: `701c679` plus uncommitted docs; compiler sources unchanged.
No repository file was edited.

## Evidence labels

- **read** `file:line`: source read on 2026-09-15/16.
- **compile**: compile-only probe through `uv run a7 <file> --format json --output <file>.zig`
  (exit code shown; 0 success, 4 tokenize, 6 semantic).
- **build**: Zig 0.16.0 (`/tmp/a7-audit-20260914/zig/zig build-exe`) in Debug and ReleaseFast.
- **run D/RF**: executed native binary in Debug / ReleaseFast. Only harmless
  programs were run (no use-after-free, no dangling reads, no inactive union reads).
- **hand trace**: reasoning about memory.md, not observed.
- All "proposed" programs are **proposed syntax, not current A7**. Names that
  memory.md does not define (`Store(T)`, `Id(T)`, `?T`, `if v := opt`, `remove`,
  `swap_remove`, `clear`, `get`, `last`) are placeholders chosen for the audit
  and are marked where they first appear.

Probe directory: `/tmp/claude-1000/-home-cx89-Projects-pl-dev-a7-py/2f3ca81e-b15a-46d6-a619-792b7c49a803/scratchpad/audit/probes-2/`
(`q*.a7`, emitted `q*.zig`, `compile-results.txt`, `run-results.txt`,
`run-results-2.txt`).

Layer numbers follow memory.md section 4: 0 typed IR, 1 sound facts, 2 internal
ownership and exclusivity, 3 escape analysis, 4 extent inference, 5 storage
formation, 6 copy elimination and reuse, 7 static buffer planning, 8 layout.
"Lib" means the standard collection implementation (not a numbered layer);
"TC" means the type checker surface.

L19 column: **none** (user cannot tell), **perf** (only speed or peak memory),
**diag** (user sees a rejection and must rewrite), **behav** (program output
could differ from the user's expectation).

Coverage column: **C** covered by memory.md, **A** ambiguous or silent,
**X** memory.md contradicts itself or another locked direction.

---

## 1. Headline findings

1. **The current backend already miscompiles an in-place aggregate update.**
   `arr = [arr[1], arr[0]]` prints `2 2` in both Debug and ReleaseFast
   (q06, run D/RF). The emitted Zig `arr = .{ arr[1], arr[0] };` writes
   element 0 before reading it for element 1. Layer 6 "in-place update" is
   the same hazard at scale; memory.md has no evaluation-order rule (EC2-52).
2. **Overlapping `ref` arguments are accepted with no diagnostic today.**
   `setx(p.x, p)` emits `setx(&p.x, &p)` and prints `6` (last writer wins)
   (q21, compile + run D/RF). This is the canonical "two writers to the same
   place" that contract item 7 promises to reject (EC2-46).
3. **The SPEC's own swap cannot be written.** `SPEC.md:698-702` generic
   `swap($T, a: ref T, b: ref T)` fails with "Undefined type (Identifier 'a')"
   (q20). The non-generic form fails because `a = b` between two `ref`
   parameters is treated as rebinding an immutable binding (q01, q28), and
   `t: i32 = a` is "expected 'i32', got 'ref i32'" (q01b). Corpus program 14
   has no current-compiler baseline (EC2-43).
4. **memory.md's own section 2 example conflicts with gate M5.** `Node.parent:
   usize` and `ret tree.nodes.len - 1` are positions in a `List`. Once a `List`
   can remove, positions shift, and old links become valid-but-wrong; generation
   tags detect slot reuse in a pool, not shifting (EC2-05, gap G-01).
5. **Where share-until-changed copies land is unspecified.** memory.md:138-140
   settles the mechanism ("where it cannot be proven, the compiler copies rather
   than inserting counts"), but not whether the copy is at the binding or at the
   first write on each path, nor that the writer, not the viewed side, must get
   fresh storage (EC2-72, EC2-75, gap G-10).
6. **Contract item 5 does not guarantee corpus program 1.** Memory "may be held
   until that extent ends", so a process-extent cache with eviction may keep
   evicted values; corpus 1 requires "memory flat" (EC2-21, gap G-15).
7. **Views (slices) are unspecified in three ways:** read-only or writable;
   whether owner writes are allowed while a view is live (M13 only mentions
   growth); and whether a returned `string` built from a view is materialized
   or rejected (EC2-26, EC2-33, EC2-34).
8. **Unions with owning payloads are not mentioned.** Current untagged unions
   accept `string` payloads and inactive-field reads (q17, compile exit 0) (EC2-60).

---

## 2. Edge-case table

### 2.1 Collections

| ID | Case | Expected under memory.md | Layer | L19 | Cov |
| --- | --- | --- | --- | --- | --- |
| EC2-01 | Append while only an index is held | Accept | 2 | none | C (corpus 3) |
| EC2-02 | Append while a slice of the list is live | Reject: exclusivity conflict | 2 | diag | C (corpus 2, M13) |
| EC2-03 | Append to a list inside `for v in list` | Unspecified: iteration binding is neither a slice nor an index | 2 | diag or behav | A |
| EC2-04 | Remove inside an index loop (skipped element) | Accept; logic bug, not memory | Lib | behav | C (out of memory scope) |
| EC2-05 | `List` removal shifts positions held in `parent: usize` | Accept silently; link now names a different node | Lib, 2 | behav | X (section 2 vs M5) |
| EC2-06 | `swap_remove` (placeholder) moves last element into a held position | Accept silently; wrong element | Lib | behav | A |
| EC2-07 | `clear()` then index with old position | Runtime index check stops or returns none | 1, Lib | diag | A (lookup form undefined) |
| EC2-08 | `clear()`, re-append, then old position (ABA) | Accept; old position names new element | Lib | behav | A |
| EC2-09 | Store remove, then lookup of old id next tick | Accept; lookup returns none | Lib, 1 | none | C (corpus 5, M5) |
| EC2-10 | Store slot reused; old id with old generation | Lookup returns none | Lib | none | C (M5) |
| EC2-11 | Generation exhaustion on one slot | Undefined | Lib | behav | A |
| EC2-12 | Id from store A used on store B of the same type | Generation may match; wrong record returned | Lib, 3 | behav | A |
| EC2-13 | Id outlives its store; a new store of the same type is created | Same as EC2-12 | 3, 4 | behav | A |
| EC2-14 | `row := grid[0]` then `row.append(1)` (nested list) | "Everything is a value": `grid` unchanged. Python users expect aliasing | 6, TC | behav | A (element binding semantics unstated) |
| EC2-15 | `grid[i].append_all(grid[j])` with unknown `i`, `j` | Accept if by-value argument is materialized before the write | 2, 6 | none | A |
| EC2-16 | `list.append(list[0])` during growth | Accept; element value must be read before reallocation | Lib, 6 | none (if rule holds) | A |
| EC2-17 | `m[k1] = m[k2]` where inserting `k1` rehashes | Accept; right side read before insertion | Lib, 6 | none | A |
| EC2-18 | Insert or remove on a `Map` during `for k, v in m` | Reject (same class as EC2-03) | 2 | diag | A |
| EC2-19 | `m[k]` read, write, and `ref` use for a missing key | Undefined | Lib, TC | behav | A |
| EC2-20 | `list.len - 1` on an empty list | Wraps under L5 to `usize` max; later index check fails | 1, Lib | diag or behav | A |
| EC2-21 | Process-lifetime cache with eviction | Contract 5 allows holding evicted values until process end, so it does not guarantee corpus 1's flat memory | 4, 5, Lib | perf (unbounded) | A |
| EC2-22 | Append fails (out of memory) in a long-running loop | M2: ordinary values stop the program | Lib | behav | C (M2), A for "old value usable" |
| EC2-23 | `len * size_of(T)` overflow on growth | Not in L5 scope; must be a checked allocation-size computation | Lib | diag | A |
| EC2-24 | `List` of a zero-sized record | Accept; no allocation | 5 | none | A (harmless) |
| EC2-25 | `ref` parameter to a record stored as structure-of-arrays | Copy-in/copy-out needed; order visible if callee also reaches the list | 8, 2 | behav | A |

### 2.2 Strings and slices

| ID | Case | Expected under memory.md | Layer | L19 | Cov |
| --- | --- | --- | --- | --- | --- |
| EC2-26 | `first_word :: fn(s: string) string { ret s[0..i] }` | Section 3 (migrate to owned returns) and corpus 7 (reject view-typed return of a local) agree; unstated whether a view expression materializes into an owning return type | 3, 6, TC | diag or none | A |
| EC2-27 | `s = s + part` in a loop | Accept; in-place append when `s` is unique | 6 | perf | C (principle), A (M8 warning?) |
| EC2-28 | `s = part + s` (prepend) | Accept; in-place reuse must handle overlap (read old `s` while writing new buffer) | 6 | behav if wrong | A |
| EC2-29 | `s = s[1..s.len]` (view of owner assigned to owner) | Unspecified: reject (M13, L19 hit) or materialize | 3, 6 | diag or none | A |
| EC2-30 | `head := make_name()[0..3]` (view of temporary) | Unspecified: reject, or extend the temporary to the binding's scope | 3, 4 | diag or none | A |
| EC2-31 | Slice passed with `ref` owner to a callee that appends | Reject by callee summary | 2, 3 | diag | C (M13 + summaries) |
| EC2-32 | Slice live while owner passed by value | Accept | 2 | none | C |
| EC2-33 | `s := arr[0..2]; arr[0] = 7; use(s)` (no growth) | M13 silent; current prints `s[0] = 7` | 2 | behav or diag | A |
| EC2-34 | Write through a view `s[0] = 9` | Writability of views unspecified | 2, TC | diag | A |
| EC2-35 | Copy between overlapping views of one list | Needs memmove semantics or rejection | Lib, 2 | behav | A |
| EC2-36 | Non-ASCII literal and slicing inside a code point | SPEC says ASCII; compiler accepts UTF-8 bytes; memory.md silent | TC, Lib | behav | A |
| EC2-37 | Token spanning two input chunks (view kept across iteration) | Reject view escaping iteration; rewrite copies partial text | 3, 4 | diag | A (plan lists "text across chunks", no rule) |
| EC2-38 | `a == b` on strings | Content equality needed for owning `string` | TC, backend | diag today | A |
| EC2-39 | Struct with `string` field copied then field reassigned | Accept; independent | 6 | none | C |
| EC2-40 | `for ch in s { s = s + "x" }` | Same class as EC2-03 | 2 | diag | A |
| EC2-41 | Empty slice `arr[1..1]`, `arr[len..len]`, `.ptr` of empty view | Accept; `.ptr` is a public address surface | TC | none / behav | A (`.ptr` not in section 3) |
| EC2-42 | View parameter used under `if s.len > 0` | Accept; needs length facts from guards | 1 | diag today | C (layer 1) |

### 2.3 Exclusivity

| ID | Case | Expected under memory.md | Layer | L19 | Cov |
| --- | --- | --- | --- | --- | --- |
| EC2-43 | `swap(x, x)` | Reject: two writers to one place | 2 | diag | C (contract 7) |
| EC2-44 | `swap(a[i], a[j])`, unknown `i`, `j` | "decide" | 1, 2 | diag | A (corpus 14) |
| EC2-45 | `swap(a[0], a[1])` | Accept | 2 | none | C (implied) |
| EC2-46 | `setx(p.x, p)` (field and whole, both `ref`) | Reject | 2 | diag | C |
| EC2-47 | `f(p.x, p.y)` distinct fields | Accept | 2 | none | A (field-sensitivity unstated) |
| EC2-48 | `bump(a, a)` with `ref` first, by-value second | Accept; by-value is a snapshot | 2, 6 | none | A |
| EC2-49 | `sum_into(arr[0], arr)` (element `ref`, whole by value) | Accept; snapshot before write | 2, 6 | none | A |
| EC2-50 | `f(counter)` where `f` also writes global `counter` | Reject by summary | 2, 3 | diag | A (globals in summaries unstated) |
| EC2-51 | `x = x` with owning `x` | Accept; no-op; must not release before read | 2, 6 | none | A |
| EC2-52 | `arr = [arr[1], arr[0]]`, `p = Pt{x: p.y, y: p.x}` | Accept; right side fully evaluated first | 6, backend | behav (current bug) | A |
| EC2-53 | `list = with_item(list, 0, list[1])` reused in place | Accept; arguments read before reuse | 6 | behav if wrong | A |
| EC2-54 | `grow_and_set(list, list[0])`, both `ref` | Reject: whole and element overlap | 2 | diag | C (by contract 7) |
| EC2-55 | `inc2(m[k1], m[k2])` with unknown keys | Same decision as EC2-44 | 2 | diag | A |
| EC2-56 | `list.sort_by(cmp)` where `cmp` reads `list` | Reject: callback reads a place under mutation | 2, 3 | diag | A (M6 silent on reads) |
| EC2-57 | `for i in 0..n { swap(a[i], a[perm[i]]) }` | Same as EC2-44 | 1, 2 | diag | A |

### 2.4 Optionals, unions, initialization

| ID | Case | Expected under memory.md | Layer | L19 | Cov |
| --- | --- | --- | --- | --- | --- |
| EC2-58 | `?List(i32)` (placeholder) released only when present | Accept; release depends on tag | 2, 5 | none | C (optionals), A (drop rule) |
| EC2-59 | Move payload out of an optional in one branch | Accept; optional becomes none or the binding is dead | 2 | diag if use-after-move | A (other audit: moves) |
| EC2-60 | Untagged union with `string` or `List` payload | Unspecified; release impossible without tag | 2, TC | diag | A |
| EC2-61 | Tagged union variant replaced while a `ref` to the old payload is live | Reject: overlap of `r.ok` and `r` | 2 | diag | C (via contract 7) |
| EC2-62 | Struct declared without initializer containing `string`/`List` | Unspecified: default-empty or reject | 2, TC | none or diag | A |
| EC2-63 | `pts: [3]Item` where `Item` owns a `string` | Unspecified default per element | 5, TC | none | A |
| EC2-64 | `big: [1000]List(i32)` | Accept; empty lists, no allocation | 5 | perf | A |
| EC2-65 | `clear()` then growth exposes stale capacity contents | Must never be observable | Lib, 6 | behav if wrong | A |
| EC2-66 | `resize(n)` grows `len` without writing elements | Must initialize | Lib | behav if wrong | A |
| EC2-67 | Store slot reuse exposes previous record through stale id | Lookup returns none | Lib | none | C (M5) |
| EC2-68 | Arena reset between iterations while a view from last iteration survives | Reject escape | 3, 4 | diag | C (M13) |
| EC2-69 | Struct literal omitting an owning field | Unspecified | TC | diag or none | A |
| EC2-70 | `find :: fn(s: string, c: char) ?[]char` (optional view returned) | Reject under M13; rewrite returns a position | 3 | diag | C |

### 2.5 Share-until-changed and in-place reuse

| ID | Case | Expected under memory.md | Layer | L19 | Cov |
| --- | --- | --- | --- | --- | --- |
| EC2-71 | `b := a; b.items[0] = 5` copies the buffer at an element write | Accept; allocation at a write that "looks free"; M2 stop can happen there | 6, Lib | perf, behav on OOM | A |
| EC2-72 | `b := a; if c { a.append(1) } else { b.append(2) }` | Copy (memory.md:138-140); placement of the copy unstated | 2, 6 | perf | A |
| EC2-73 | `prev := cur; cur.step()` every loop iteration | Accept; one copy per iteration unless proven dead | 6 | perf | C (M8 warning) |
| EC2-74 | `b := a; mutate(b)` (`ref` parameter) | Copy before the call | 6 | perf | A |
| EC2-75 | `b := a; s := b[0..2]; a.append(1); use(s)` | Accept only if the writer (`a`) gets fresh storage | 6, 2 | behav if wrong | A |
| EC2-76 | In-place reuse while a view of the old value is live | Reuse forbidden; M13 rejects writes anyway | 6, 2 | none | C |
| EC2-77 | Sharing observed through `s.ptr` / `string.ptr` | Sharing becomes observable | TC | behav | X vs SPEC (memory.md principle "no public address-of" vs `SPEC.md:275`, `288-291` `.ptr`) |
| EC2-78 | Shared buffer given to a native kernel that writes | Uniquify before the call | 6, native | behav if wrong | A (M12 silent on sharing) |
| EC2-79 | `b := a; spawn(move b)` while `a` stays in use | Copy at the move, or reject | 6, M10 | perf | A |
| EC2-80 | Out-of-memory stop point differs between Debug and ReleaseFast because copies are elided differently | Observable only under OOM | 6, M2 | behav on OOM | A |
| EC2-81 | By-value parameter lowered as a pointer while a `ref` argument of the same call overlaps it | Must stay a snapshot | backend, 6 | behav if wrong | A |

---

## 3. Case details

Each block gives the proposed program, expected behavior, and a proposed rule
where memory.md is missing one. Current-compiler facts are in section 6.

### EC2-01 and EC2-02. Append with an index or a slice held

```a7
// Proposed syntax
main :: fn() {
    xs := List(i32){}
    xs.append(1)
    i: usize = 0
    xs.append(2)          // EC2-01: accept, i still names element 0
    head := xs[0..1]
    xs.append(3)          // EC2-02: reject, head is used below
    print(head[0])
}
```

Covered. Diagnostic wording should name the behavior: "`xs` grows while
`head` still looks at it; read `head` before the append or keep a position."

### EC2-03. Growth inside iteration

```a7
// Proposed syntax
main :: fn() {
    xs := List(i32){}
    xs.append(1)
    for v in xs {
        if v < 10 {
            xs.append(v + 10)
        }
    }
}
```

memory.md does not say what `for v in xs` holds. Two coherent readings:

- **Snapshot:** the loop iterates the value of `xs` at loop entry ("everything is
  a value"). Current fixed-array loops already behave this way (q08, q24). Cost:
  a copy when the body writes `xs`, unless proven unnecessary.
- **View:** the loop holds a view; any structural change is rejected (Fable's
  advice, `advice-fable.md:382-384`).

Proposed rule: iteration holds a read view of the collection for the loop body.
Structural changes (append, insert, remove, clear, Map insert) in the body are
exclusivity conflicts. Element writes by position (`xs[i] = ...`) in
`for i, v in xs` are accepted and do not change `v` for the current iteration.
This must be put to the user as a gate with both readings, because the
snapshot reading is what current A7 programs observe for arrays. Choosing the
view reading changes the output of currently accepted fixed-array programs
(q08, q24) and needs a section 3 breaking-change row (see G-07).

### EC2-04. Removal inside an index loop

```a7
// Proposed syntax; remove is a placeholder
main :: fn() {
    xs := List(i32){}
    xs.append(1)
    xs.append(1)
    i: usize = 0
    while i < xs.len {
        if xs[i] == 1 {
            xs.remove(i)      // next element shifts into i and is then skipped
        }
        i += 1
    }
}
```

Accept. No view is live, and the index test covers `xs[i]` because `i < xs.len`
is re-evaluated. The skipped element is a logic bug outside memory scope.

### EC2-05 and EC2-06. Removal from a `List` breaks stored positions

```a7
// Proposed syntax; remove and swap_remove are placeholders
Node :: struct {
    value: i32
    parent: usize
}

main :: fn() {
    nodes := List(Node){}
    nodes.append(Node{value: 1, parent: 0})
    nodes.append(Node{value: 2, parent: 0})
    nodes.append(Node{value: 3, parent: 1})   // parent is node "2"
    nodes.remove(0)                           // node "3" now at 1, its parent 1 names itself
    nodes.swap_remove(0)                      // last element moves to 0
}
```

memory.md section 2 blesses positions into a `List` as the shared-structure
model; M5 says "removal-capable collections use generation-tagged ids". A shifting
`remove` cannot be caught by a generation tag because no slot is reused.
Proposed rule: `List` positions are plain `usize` and `List` offers no
order-shifting removal that keeps positions meaningful; shared structure with
removal uses a distinct store type (placeholder `Store(T)` with `Id(T)`) whose
ids are generation-tagged and whose removal never moves other records. This
adds a fourth user-visible type that memory.md does not list; it needs a gate
(Q-C1).

### EC2-07 and EC2-08. `clear()` and old positions

```a7
// Proposed syntax
main :: fn() {
    xs := List(i32){}
    xs.append(5)
    i: usize = 0
    xs.clear()
    y := xs.get(i)        // placeholder: returns none
    xs.append(9)
    z := xs[i]            // 9: old position silently names a new element
}
```

Proposed rule: `List` indexing with an unproven position performs the contract-4
index test and stops the program with an index diagnostic; `get` returns an
optional. ABA on `List` positions is documented behavior. Only `Store(T)` ids
detect reuse.

### EC2-09 to EC2-13. Generation-tagged ids

```a7
// Proposed syntax; Store, Id, add, remove, get are placeholders
Enemy :: struct { hp: i32 }

main :: fn() {
    world := Store(Enemy){}
    a := world.add(Enemy{hp: 3})
    world.remove(a)
    b := world.add(Enemy{hp: 7})       // reuses slot, generation + 1
    if e := world.get(a) { }           // EC2-10: none

    other := Store(Enemy){}
    c := other.add(Enemy{hp: 1})
    if e := world.get(c) { }           // EC2-12: slot 0, generation 0 may match b's slot
    if e := world.get(a) {
        print(e.hp)                    // EC2-67: never reached; old record 3 not exposed
    }
}

keep_id :: fn() Id(Enemy) {
    local := Store(Enemy){}
    ret local.add(Enemy{hp: 1})        // EC2-13: id outlives its store
}
```

- **EC2-11 exhaustion.** Proposed rule: generation is `u32`; when a slot's
  generation would wrap, the slot is retired and never reused for the life of
  the store. Lookup never wraps. Grok requires this to be defined
  (`advice-grok.md:310`); GLM flags it (`advice-glm.md:118`).
- **EC2-12/13 cross-store ids.** Proposed rule: an `Id(T)` carries the identity
  of the store it came from when the compiler cannot prove statically which store
  it belongs to (layer 3 flow of ids); lookup compares store identity and
  generation. Where the flow is proven (single store of that type in the
  program, or the id never leaves the store's function), the tag is erased.
  Alternative: reject passing an id to a store it was not proven to come from
  (L19 diag). Gate Q-C2.

### EC2-14. Element binding in nested collections

```a7
// Proposed syntax
main :: fn() {
    grid := List(List(i32)){}
    grid.append(List(i32){})
    row := grid[0]
    row.append(1)
    print(grid[0].len)       // value semantics: 0. Python: 1.
    grid[0].append(1)        // changes grid in place
}
```

memory.md says `b := a` is an independent value but never states it for element
access; `advice-fable.md:190-197` proposes a borrow binding instead. Proposed
rule: `x := c[i]` is an independent value (shared until changed); place
expressions `c[i].f(...)` and `c[i] = v` change `c` in place. The user-visible
difference from Python is a behavior surprise and should be counted in the L19
metric.

### EC2-15 to EC2-17. Reading from a collection while changing it

```a7
// Proposed syntax
main :: fn() {
    xs := List(i32){}
    xs.append(4)
    xs.append(xs[0])                 // EC2-16

    grid := List(List(i32)){}
    grid.append(List(i32){})
    grid.append(List(i32){})
    i := pick()
    j := pick()
    grid[i].append_all(grid[j])      // EC2-15: placeholder; i may equal j

    m := Map(string, List(i32)){}
    m["a"] = List(i32){}
    m["b"] = m["a"]                  // EC2-17: may rehash while reading "a"
}
```

Proposed rule (evaluation order): every by-value argument and every right-hand
side is fully evaluated into an independent value (possibly shared) before the
mutating operation starts. The standard library implementation may not hold a
pointer to an element across its own reallocation. This is the rule C++
`vector::push_back(v[0])` implementations must follow, and the rule the current
backend violates for aggregate literals (EC2-52).

### EC2-19. Missing map keys

```a7
// Proposed syntax
main :: fn() {
    counts := Map(string, i32){}
    n := counts["x"]          // read of a missing key
    counts["x"] += 1          // compound write to a missing key
    bump(counts["y"])         // ref argument to a missing key
    for k, v in counts {
        counts[k + "!"] = v   // EC2-18: insert during iteration, reject
    }
}
```

Proposed rule: `m[k]` as a read requires presence and stops the program with a
key diagnostic when absence is not proven; `m.get(k)` returns an optional;
`m[k] = v` inserts; `m[k] += 1` and `ref m[k]` on an absent key are rejected
unless presence is proven, with the rewrite `m[k] = m.get_or(k, 0) + 1`. The
stop is a runtime check not listed in contract item 4 ("index validity tests");
the contract should say "index and key validity tests".

### EC2-20. Empty collections

```a7
// Proposed syntax
last_value :: fn(xs: List(i32)) i32 {
    ret xs[xs.len - 1]        // len 0 wraps to usize max (L5), index test fails
}
```

Proposed rule: `last()` returns an optional; diagnostics for the failed index
test on `len - 1` mention the empty case. Record under the L19 metric.

### EC2-21. Long-lived collections and removal

```a7
// Proposed syntax
cache := Map(string, string){}     // process extent

handle :: fn(key: string, value: string) {
    if cache.len >= 1000 {
        cache.remove(cache.oldest_key())   // placeholder
    }
    cache[key] = value
}
```

Contract item 5 lets the compiler hold evicted values until the process ends.
Corpus 1 requires flat memory. Proposed rule: storage owned by a collection
element is released or recycled into the collection's own free list at the
point the element is removed or overwritten. Extent-end release applies to
storage not owned by a longer-lived collection. This must be added to contract
item 5.

### EC2-22 and EC2-23. Growth failure and capacity limits

```a7
// Proposed syntax
main :: fn() {
    xs := List(u64){}
    for {
        xs.append(1)          // M2: stops with an out-of-memory diagnostic
    }
}

Empty :: struct {}

zero_sized :: fn() {
    es := List(Empty){}
    es.append(Empty{})        // EC2-24: len 1, no storage needed
}
```

M2 covers ordinary values. The size computation `capacity * element_size` is
outside L5 and must be checked (stop with the same diagnostic). The synthesis
secondary program "failed append leaving the original list usable" has no
expected result in memory.md for ordinary lists: under M2 it is unobservable,
because the program stops. State this.

### EC2-25. Layout of records and `ref` parameters

```a7
// Proposed syntax
Particle :: struct { x: f32, v: f32 }
particles := List(Particle){}          // may be lowered as structure-of-arrays

nudge :: fn(p: ref Particle) {
    p.x += particles[0].v               // reads the same list through a global
}
```

With SoA, `ref Particle` has no contiguous record. Proposed rule: layer 8 applies
only to collections whose elements are never passed as a whole `ref` record, or
lowering uses copy-in/copy-out and layer 2 rejects any other access to the same
collection during the call (already required by exclusivity). Add to the
Phase G exit: identical output including `ref` calls on elements.

### EC2-26. Returning a substring as `string`

```a7
// Proposed syntax
first_word :: fn(s: string) string {
    i: usize = 0
    for i < s.len and s[i] != ' ' {
        i += 1
    }
    ret s[0..i]
}
```

Section 3 says "functions returning slices of locals return owned values
instead"; corpus 7 rejects returning a slice of a local. These agree for a
declared `[]T` return. Neither says whether `ret s[0..i]` in a function declared
to return `string` is a type error or an implicit copy. Proposed rule:
when the declared return type is an owning type (`string`, `List(T)`), a view
expression in `ret` is materialized into an owned value (a copy, or a move when
the owner dies). Only a declared view return type (`[]T`) is rejected. Without
this rule, the most common text-processing function is a memory-aware rewrite
(L19 hit). The same rule applies to assignment into an owning binding (EC2-29,
EC2-37).

### EC2-27 and EC2-28. Concatenation in loops

```a7
// Proposed syntax
join :: fn(parts: List(string)) string {
    out := ""
    for p in parts {
        out = out + p         // EC2-27: append in place when out is unique
        out = "," + out       // EC2-28: prepend; old bytes overlap new position
    }
    ret out
}

Item :: struct {
    name: string
    qty: i32
}

more :: fn() {
    a := Item{name: "bolt", qty: 1}
    b := a
    b.name = "nut"            // EC2-39: a.name stays "bolt"
    s := "ab"
    for ch in s {
        s = s + "x"           // EC2-40: growth of s while iterating s, reject
    }
}
```

Proposed rule: in-place reuse of `x = f(x, ...)` must produce the result of
evaluating `f` on the old value; overlap moves use memmove semantics. Corpus
test: output of the loop must match an implementation with no reuse.

### EC2-29 and EC2-30. View assigned to its owner; view of a temporary

```a7
// Proposed syntax
main :: fn() {
    s := "  hello"
    s = s[2..s.len]              // EC2-29
    head := read_line()[0..3]    // EC2-30: view of a temporary
}
```

Proposed rules: EC2-29 materializes (in-place shift or copy) under the
EC2-26 rule because the target is an owning binding. EC2-30: when a view of a
temporary is bound to a name whose declared or inferred type is a view, the
temporary's extent is extended to the name's scope; no diagnostic. When bound
into an owning type, materialize.

### EC2-33 and EC2-34. Views and writes to their owner

```a7
// Proposed syntax
main :: fn() {
    arr: [4]i32 = [1, 2, 3, 4]
    s := arr[0..2]
    arr[0] = 7              // EC2-33
    print(s[0])             // current A7: prints 7 (q10)
    s[1] = 9                // EC2-34
}

grow :: fn(xs: ref List(i32), view: []i32) {
    xs.append(view[0])
}

total :: fn(xs: List(i32), view: []i32) i32 {
    if view.len > 0 {       // EC2-42: guard must prove view[0]
        ret view[0] + cast(i32, xs.len)
    }
    ret 0
}

calls :: fn() {
    xs := List(i32){}
    xs.append(1)
    grow(xs, xs[0..1])      // EC2-31: reject, callee grows the owner of view
    t := total(xs, xs[0..1]) // EC2-32: accept, owner passed by value
}
```

M13 only forbids growth. Proposed rule: views are read-only; while a view is
used later, any write to an overlapping place of its owner is an exclusivity
conflict. This rejects today's accepted `q10` program: a breaking change that is
missing from the section 3 table. The alternative (views observe later writes)
must be written down if chosen, because it makes views observably non-value.

### EC2-35. Overlapping copies

```a7
// Proposed syntax; copy_within is a placeholder
main :: fn() {
    xs := List(i32){}
    xs.append(1)
    xs.append(2)
    xs.append(3)
    xs.copy_within(0, 1, 2)    // move [1,2] to positions 1..3: result [1,1,2]
}
```

Proposed rule: overlapping copies within one collection are library operations
with memmove semantics. A general `copy(dst, src)` whose destination is a
writable place and whose source is a view of the same owner is rejected by
EC2-34's read-only-view rule.

### EC2-36. Encoding

```a7
// Proposed syntax
main :: fn() {
    t := "héllo"
    part := t[0..2]          // splits a two-byte code point
    c: char = 'é'            // outside the documented 0..127 char range
}
```

Current A7 accepts both; `part` prints `h` and a lone byte; `c` holds 233 (q22,
q23, run D/RF). Proposed rule: decide in the owning-string gate whether `string`
is ASCII (reject non-ASCII literals at tokenize time) or UTF-8 bytes (slicing by
byte, with a library code-point iterator). memory.md should reference the
decision because owning-string APIs depend on it.

### EC2-37. Text across chunks

```a7
// Proposed syntax
main :: fn() {
    carry := ""
    for {
        chunk := read_chunk()             // per-iteration extent
        if chunk.len == 0 { break }
        end := last_space(chunk)          // placeholder, returns usize
        emit(carry + chunk[0..end])
        carry = chunk[end..chunk.len]     // view assigned to an owning binding: materialize
    }
}
```

Expected: accept under the EC2-26 rule; `carry` owns its bytes. Rejection only
if `carry` were a declared view type.

### EC2-38. String equality

```a7
// Proposed syntax
main :: fn() {
    a := "ab"
    b := "a" + "b"
    if a == b { print("same") }
}
```

Owning `string` needs content equality. Current A7 accepts `==` on strings and
emits Zig that does not compile (q14). Add to Phase C exit.

### EC2-41. `.ptr` on views and strings

```a7
// Current and proposed syntax
main :: fn() {
    a := "abc"
    b := a
    same := a.ptr == b.ptr    // reveals sharing
}
```

`SPEC.md:275` and `SPEC.md:288-291` expose `ptr`. Share-until-changed and layer 8
require that addresses are not observable. Proposed rule: remove `.ptr` from the
public surface (native boundary exempt, M12). Add a section 3 row.

### EC2-43 to EC2-45, EC2-57. Swap

```a7
// Proposed syntax
swap :: fn(a: ref i32, b: ref i32) {
    t := a
    a = b
    b = t
}

main :: fn() {
    arr: [3]i32 = [1, 2, 3]
    x: i32 = 1
    swap(x, x)                 // EC2-43: reject
    swap(arr[0], arr[1])       // EC2-45: accept
    i := pick()
    j := pick()
    swap(arr[i], arr[j])       // EC2-44: decide
}
```

Proposed rule for EC2-44: reject unless layer 1 proves `i != j`, with the
diagnostic suggesting the library operation `arr.swap(i, j)` (which is correct
when `i == j`). Accepting with a runtime distinctness check is also possible, but
contract item 4 does not list distinctness tests and would need to. Note that
swapping one place with itself is harmless for `swap`, but the general rule
cannot know the callee is swap-like, so rejection is the sound default.

### EC2-46 and EC2-47. Field and whole

```a7
// Proposed syntax
Pt :: struct { x: i32, y: i32 }

setx :: fn(dst: ref i32, whole: ref Pt) {
    dst = 5
    whole.x = 6
}

main :: fn() {
    p := Pt{x: 1, y: 2}
    setx(p.x, p)        // EC2-46: reject, p.x overlaps p
    setx2(p.x, p.y)     // EC2-47: accept, disjoint paths
}
```

Places are `base + field path + index projection` (as in
`advice-fable.md:211-213`); memory.md should state field sensitivity explicitly.

### EC2-48, EC2-49, EC2-81. `ref` and by-value on the same place

```a7
// Proposed syntax
Big :: struct { head: i32, pad: [64]i32, tail: i32 }

bump :: fn(dst: ref Big, src: Big) {
    dst.head = 100
    dst.tail = src.head
}

sum_into :: fn(dst: ref i32, all: [3]i32) {
    dst = 0
    for v in all {
        dst += v
    }
}

main :: fn() {
    a := Big{}
    bump(a, a)          // EC2-48, EC2-81: expected a.tail = old a.head
    arr: [3]i32 = [1, 2, 3]
    sum_into(arr[0], arr)   // EC2-49: expected arr[0] = 6 (snapshot [1, 2, 3])
}
```

Proposed rule: a by-value argument is a snapshot at the call. The compiler may
pass it by pointer only if layer 2 proves no `ref` argument of the same call and
no write in the callee's summary overlaps it. `advice-fable.md:180-185` says the
callee "cannot observe whether it received a copy or a reference"; that is false
when another argument is a `ref` to the same place, so the advice needs this
qualifier.

### EC2-50. `ref` plus direct global write

```a7
// Proposed syntax
counter := 0

tick :: fn(c: ref i32) {
    counter += 1
    c += 1
}

main :: fn() {
    tick(counter)       // reject: two writers to counter
}
```

Proposed rule: effect summaries include global places; an argument overlapping a
place the callee writes directly is an exclusivity conflict.

### EC2-51 to EC2-53. Self-assignment and in-place reconstruction

```a7
// Proposed syntax
Pt :: struct { x: i32, y: i32 }

main :: fn() {
    xs := List(i32){}
    xs = xs                              // EC2-51: no-op
    arr: [2]i32 = [1, 2]
    arr = [arr[1], arr[0]]               // EC2-52: must yield [2, 1]
    p := Pt{x: 1, y: 2}
    p = Pt{x: p.y, y: p.x}               // EC2-52: must yield {2, 1}
    xs = with_item(xs, 0, xs[1])         // EC2-53
}
```

Proposed rule for layer 6 and the backend plan: an assignment `place = expr`
where `expr` reads any place overlapping `place` evaluates `expr` into a
temporary before the first write, unless layer 1 proves the construction order
reads each overlapping source before its destination is written. Self-assignment
of an owning value is a no-op, never release-then-move. Current backend
evidence: q06 prints `2 2` today, while the struct form q05 prints the correct
`2 1`. The difference comes from Zig's result-location handling, which A7 must
not rely on.

### EC2-54 and EC2-55. Whole and element `ref`; map keys

```a7
// Proposed syntax
grow_and_set :: fn(xs: ref List(i32), first: ref i32) {
    xs.append(0)
    first = 1
}

main :: fn() {
    xs := List(i32){}
    xs.append(5)
    grow_and_set(xs, xs[0])      // EC2-54: reject
    m := Map(string, i32){}
    inc2(m[k1], m[k2])           // EC2-55: same decision as EC2-44 (keys)
}
```

### EC2-56. Callback reading a collection under mutation

```a7
// Proposed syntax; sort_by is a placeholder, non-escaping callback per M6
weights := List(i32){}

by_weight :: fn(a: usize, b: usize) bool {
    ret weights[a] < weights[b]
}

main :: fn() {
    weights.sort_by(by_weight)    // callback reads weights while sort writes it
}
```

Proposed rule: a callback argument's summary joins the call's effect set; a
callback reading a place the callee writes is an exclusivity conflict. Rewrite:
sort a list of positions, or copy weights first.

### EC2-58 to EC2-61. Optionals and unions with owning payloads

```a7
// Proposed syntax; ?T and if v := opt are placeholders
Val :: union {
    n: i64
    s: string
}

Result :: union(tag) {
    ok: List(i32)
    err: string
}

replace :: fn(slot: ref List(i32), whole: ref Result) {
    whole = Result{err: "x"}
    slot.append(1)
}

take_if :: fn(c: bool) List(i32) {
    maybe: ?List(i32) = List(i32){}
    if c {
        if xs := maybe {
            ret xs                   // EC2-59: payload moved out on one branch
        }
    }
    ret List(i32){}                  // maybe released here only if still present
}

main :: fn() {
    maybe: ?List(i32) = none         // EC2-58: nothing to release
    v := Val{n: 42}                  // EC2-60
    r := Result{ok: List(i32){}}
    replace(r.ok, r)                 // EC2-61: reject, overlap
}
```

Proposed rule: owning payloads (`string`, `List`, `Map`, `Store`, structs that
contain them) are allowed only in tagged unions and optionals; untagged unions
are restricted to payloads with no owned storage. Replacing a tagged value
releases the previous payload after the new value is evaluated (EC2-52 order).
Ties to v1 gate G5.

### EC2-62 to EC2-66, EC2-69. Initialization and reuse

```a7
// Proposed syntax
Item :: struct {
    name: string
    tags: List(string)
    qty: i32
}

main :: fn() {
    a: Item                         // EC2-62
    pts: [3]Item                    // EC2-63
    big: [1000]List(i32)            // EC2-64
    b := Item{qty: 1}               // EC2-69
    xs := List(i32){}
    xs.append(7)
    xs.clear()
    xs.append(8)                    // EC2-65: capacity reused; only 8 is visible
    xs.resize(2)                    // EC2-66: placeholder; xs[1] must read 0, not 7
}
```

### EC2-68 and EC2-70. Views that would outlive their extent

```a7
// Proposed syntax; ?[]char is a placeholder
main :: fn() {
    last: []char = ""
    for {
        line := read_line()          // per-iteration storage
        if line.len == 0 { break }
        last = line[0..1]            // EC2-68: reject, declared view outlives line
    }
}

find :: fn(s: string, c: char) ?[]char {
    ret s[0..1]                      // EC2-70: reject; rewrite returns ?usize
}
```

Both are covered by M13. Note the contrast with EC2-37: assigning into an
owning `string` binding materializes instead.

Proposed rules: every type has a defined empty value (`""`, empty `List`, empty
`Map`, zero numbers, `none` optionals); declarations without initializers and
omitted struct-literal fields take that value, for arrays element-wise; no
allocation is performed for empty values. Untagged unions and types with no
empty value still require an initializer. Any operation that raises `len`
writes every new element. Reused capacity is never observable because views,
indices and `.ptr` are bounded by `len` (depends on EC2-41).

### EC2-71 to EC2-75. Share-until-changed

```a7
// Proposed syntax
main :: fn() {
    a := List(i32){}
    a.append(1)
    b := a
    b[0] = 5                       // EC2-71: buffer copy happens here
    c := a
    if coin() {
        a.append(2)                // EC2-72: which side changes is data-dependent
    } else {
        c.append(3)
    }
    d := a
    s := d[0..1]
    a.append(4)                    // EC2-75: a must get fresh storage; s still valid
    print(s[0])
    e := a
    grow(e)                        // EC2-74: ref parameter; copy before the call
    t := a[0..1]
    a = with_item(a, 0, 9)         // EC2-76: no in-place reuse while t is live
    print(t[0])                    // (and M13 rejects the write)
    cur := List(i32){}
    for k := cast(usize, 0); k < 3; k += 1 {
        prev := cur                // EC2-73: one copy per iteration
        cur.append(cast(i32, k))
        print(prev.len)
    }
}
```

memory.md:138-140 already answers the mechanism: "Where it cannot be proven,
the compiler copies rather than inserting counts." So no runtime shared flag is
implied. What memory.md leaves open is where the copy lands for EC2-72: at the
binding `c := a` (eager) or at the first write on each path (which needs no
runtime state if the copy is emitted per branch). Proposed rule: when the first
writer differs by path, emit the copy at the start of each writing path, or at
the binding when that is simpler; never keep per-value runtime sharing state. Copy-on-write always gives the writing side fresh storage; the
non-writing side's storage never moves while views of it may be live. M8's
report should list copies at element writes (EC2-71), because they turn O(1)
writes into O(n).

### EC2-77 to EC2-80. Observability of sharing

```a7
// Proposed syntax
main :: fn() {
    a := List(f32){}
    a.append(1.0)
    b := a
    native_scale(b, 2.0)       // EC2-78: native writes; b must be unique first
    spawn(worker, b)           // EC2-79: moved into a task while a is live
    c := a
    c[0] = 3.0                 // EC2-80: copy here may be elided in ReleaseFast
}                              // but not Debug, moving the out-of-memory stop point
```

Proposed rules: native calls with write permission (M12) and task moves (M10)
uniquify shared storage first. Out-of-memory stop points are not part of program
semantics and may differ between optimization levels (EC2-80); say so next to M2.

---

## 4. Plan gaps and contradictions, with proposed fixes

| ID | Where | Problem | Proposed fix |
| --- | --- | --- | --- |
| G-01 | Section 2 example, M5 | `usize` positions into a `List` are the shared-structure model; M5 relies on generation-tagged ids that cannot detect shifting removal | Separate removal-capable store type with generation-tagged ids; `List` positions documented as shift-sensitive (EC2-05) |
| G-02 | M5 | Generation exhaustion undefined | `u32` generation; retire slot at saturation (EC2-11) |
| G-03 | M5 | Cross-store ids and ids outliving their store | Store identity in ids unless provenance is proven, or reject unproven cross-store use (EC2-12) |
| G-04 | M13 | Only "growth" invalidates views | "Any structural change or overlapping write" (remove, clear, insert, Map insert, element write) (EC2-33) |
| G-05 | Section 2 | Iteration binding semantics undefined | Gate: snapshot vs read view (EC2-03) |
| G-06 | Section 2 | `x := c[i]` copy vs borrow undefined; advice-fable proposes borrow | State copy (value) semantics; place expressions mutate in place (EC2-14) |
| G-07 | M13, section 3 | Views read-only or writable is undefined; rejecting owner writes during a live view breaks accepted programs (q10) and is not in the section 3 table | Read-only views; add a breaking-change row (EC2-33, EC2-34) |
| G-07b | Section 3 | If iteration becomes a read view (Q-C3 b), body writes to a fixed array during `for v in arr` change from accepted-snapshot (q08, q24) to rejected | Add a breaking-change row with the q08 before/after example (EC2-03) |
| G-08 | Contract 7 vs corpus 7, 10, 12 | Contract says user rejections are exclusivity conflicts; corpus rejects escapes and cross-task ids | Widen contract 7 to "exclusivity conflicts and values that would outlive what they view" |
| G-09 | Section 3 row "slices ... return owned values", corpus 7 | Consistent for `[]T` returns; silent on a view expression returned or assigned as an owning type | Materialize into owning return types and owning bindings; reject only view-typed escape (EC2-26) |
| G-10 | Section 2 "shares storage until either side changes", section 4 principle "copies rather than inserting counts" | Mechanism consistent; copy placement for data-dependent writers and "which side gets fresh storage" unstated | Copy at the start of each writing path or at the binding; writer gets fresh storage; no runtime sharing state (EC2-72, EC2-75) |
| G-11 | Layer 6, backend plan principle | No evaluation-order rule for in-place updates; current backend already miscompiles (q06) | RHS materialized before first write when it reads an overlapping place (EC2-52) |
| G-12 | Layer 6, advice-fable passing rule | By-value-as-pointer is observable with an overlapping `ref` argument | Snapshot rule with a layer-2 disjointness condition (EC2-48) |
| G-13 | Whole plan | Unions never mentioned | Owning payloads only in tagged unions and optionals (EC2-60) |
| G-14 | Section 2 | Default values for owning types and arrays of them undefined; current `undefined` lowering (MS-9) | Defined empty values, element-wise, no allocation (EC2-62) |
| G-15 | Contract 5, corpus 1 | Contract 5 does not guarantee corpus 1: evicted cache entries may be held to process end | Collection-owned storage released or recycled at removal (EC2-21) |
| G-16 | Corpus 14 vs contract 4 | Runtime distinctness checks not in the residual-work list | Reject unless proven; library `swap(i, j)`; or amend contract 4 (EC2-44) |
| G-17 | Contract 4 | "Index validity tests" omits key-presence tests for `Map` | "Index and key validity tests" (EC2-19) |
| G-18 | Section 3, principles | `.ptr` on slices and strings exposes addresses; conflicts with "no public address-of" and share-until-changed | Remove `.ptr` from ordinary code; add section 3 row (EC2-41, EC2-77) |
| G-19 | Owning `string` row | Encoding unspecified; SPEC says ASCII while UTF-8 literals and 233-valued `char` compile | Decide in the owning-string gate (EC2-36) |
| G-20 | M6 | Non-escaping callbacks may read a place the callee mutates | Callback effects join the call's exclusivity check (EC2-56) |
| G-21 | M13 | Views of temporaries | Extend temporary to binding scope for view bindings; materialize for owning bindings (EC2-30) |
| G-22 | Layer 8 | SoA vs `ref` to a whole record | Restrict or copy-in/copy-out with exclusivity (EC2-25) |
| G-23 | Library contract | Growth, `resize`, reuse after `clear` may expose stale contents | Every `len` increase writes elements; no capacity-bounded access (EC2-65, EC2-66) |
| G-24 | M2 x layer 6 | Copy-on-write makes element writes allocate, and OOM points depend on optimization | Document as non-semantic; M8 report lists copies at writes (EC2-71, EC2-80) |
| G-25 | Phase A category list | "Values and copies" and "Exclusivity" do not name evaluation order or by-value/ref overlap | Add both to Phase A and to the falsifying corpus (proposed programs 16 and 17 below) |
| G-26 | Section 2, globals | Effect summaries over globals are implied, not stated | State that summaries include global places (EC2-50) |

Proposed additions to the Phase A falsifying corpus:

| # | Program | Expected |
| --- | --- | --- |
| 16 | `arr = [arr[1], arr[0]]` and `p = Pt{x: p.y, y: p.x}`, plus `xs = with_item(xs, 0, xs[1])` under in-place reuse | Accept; output `[2, 1]`, `{2, 1}`, and the no-reuse result, in Debug and ReleaseFast |
| 17 | `bump(a, a)` with `ref` first and large by-value second | Accept; `a.tail` equals the old `a.head` |
| 18 | `List` remove followed by use of a stored parent position | Decide G-01 |
| 19 | Evicting cache running one million requests | Peak memory flat (G-15) |
| 20 | `b := a` followed by a data-dependent write to one side, plus a view into the other | Accept; no runtime shared flag; view unchanged (G-10) |

---

## 5. New gate questions

| ID | Question | Options | Recommendation |
| --- | --- | --- | --- |
| Q-C1 | Is there a removal-capable store type separate from `List`? | (a) `List` only, positions shift; (b) `List` plus `Store(T)`/`Id(T)` with generations; (c) `List` with tombstones | (b) |
| Q-C2 | What does an id used on the wrong store do? | (a) store identity tag checked at lookup; (b) reject unproven provenance; (c) undefined | (a), erased when proven |
| Q-C3 | `for v in xs` semantics | (a) snapshot of `xs`; (b) read view, structural changes rejected | (b), with element writes by position allowed |
| Q-C4 | `x := xs[i]` | (a) independent value; (b) scope-bounded borrow binding | (a) |
| Q-C5 | Views writable? | (a) read-only; (b) writable views | (a) |
| Q-C6 | Owner writes while a view is live (no growth) | (a) reject; (b) view observes the write | (a); breaking change row needed |
| Q-C7 | View in `ret` or assigned to an owning binding | (a) materialize; (b) reject | (a) for owning targets |
| Q-C8 | `swap(a[i], a[j])` unknown indices | (a) reject with rewrite; (b) runtime distinctness check (amend contract 4) | (a) |
| Q-C9 | Missing `Map` key on read, compound write, `ref` | (a) stop with diagnostic; (b) insert default; (c) reject unless proven | read (a), compound and `ref` (c) |
| Q-C10 | Where the copy lands when the first writer is data-dependent | (a) at the binding; (b) at the start of each writing path | (b) where it avoids a copy on the non-writing path, else (a); M8 reports both |
| Q-C11 | Owning payloads in untagged unions | (a) forbid; (b) allow with no release | (a) |
| Q-C12 | Default value for declarations without initializer | (a) empty value per type; (b) reject | (a) |
| Q-C13 | `string` encoding | (a) ASCII, reject other literals; (b) UTF-8 bytes | Decide with owning `string` |
| Q-C14 | `.ptr` on slices and strings | (a) remove from ordinary code; (b) keep | (a) |
| Q-C15 | Removed elements of long-lived collections | (a) release or recycle at removal; (b) hold to extent end | (a) |

---

## 6. Current-compiler findings

All probes are in the probe directory listed above.

### 6.1 Collections

| # | Fact | Evidence |
| --- | --- | --- |
| CF-01 | No `List`, `Map`, store or arena type exists. `a7/stdlib/string.py` is a 9-line stub; the registry holds `io`, `math`, `mem`, `string` | read `a7/stdlib/string.py:1-9`, `a7/stdlib/` listing |
| CF-02 | Linked structures use positions: `examples/025_linked_list.a7:7` `next: isize` with `-1` sentinel (contrary to the `usize` rule); `026_binary_tree.a7:7-8` `left: usize`, `right: usize` with `empty: usize = 3` sentinel; neither removes nodes | read |
| CF-03 | `for v in arr` over a fixed array lowers to `for (arr) \|v\|` and iterates a copy: writing `arr[2] = 99` in the body still prints `v=3`; struct elements the same | read `a7/backends/zig.py:920-952`; q08, q24 run D/RF |
| CF-04 | Nested fixed-array copy is independent (`m2[0][0] = 9` leaves `m[0][0] = 1`) | q18 run D/RF |
| CF-05 | Array of `ref` fields: storing a `new` result in `h.items[0]` then `del p` is accepted by A7; Zig build fails only because the emitted `if (p) \|p\|` capture shadows `p` (MS-11) | q38 compile exit 0, build fail |
| CF-06 | For-in index facts have no upper bound (`IntegerInterval(0, None)`), so `arr[i + 1]` in `for i, v in src` is unprovable | read `a7/safety.py:364-371`; q31 compile exit 6 |

### 6.2 Strings and slices

| # | Fact | Evidence |
| --- | --- | --- |
| CF-07 | `string` lowers to `[]const u8`; no concatenation: `a + b` is "Requires numeric type" | read `zig.py:2087`; q13 exit 6 |
| CF-08 | `string[a..b]` has type `[]char`, not assignable to `string` | q12 exit 6 |
| CF-09 | String `==` is accepted by A7; emitted Zig fails: "operator == not allowed for type '[]const u8'" | q14 compile exit 0, build fail D/RF |
| CF-10 | Slicing or indexing a `string`/slice parameter is always rejected: length facts exist only for literals and fixed arrays, and `_facts_from_condition` learns only from `IDENTIFIER op literal`, never from `s.len` | read `a7/safety.py:602-608`, `678-703`; q11, q30 exit 6 |
| CF-11 | A view of a local stored in a returned struct is accepted by A7 (no escape analysis); Zig rejects it only because the array was emitted `const` (`expected type '[]i32', found '*const [4]i32'`) | q15 compile exit 0, build fail D/RF |
| CF-12 | Writing through a view of an array: A7 accepts; mutation analysis does not see the slice write and emits `const arr`, so Zig fails "cannot assign to constant" | q09 compile exit 0, build fail D/RF |
| CF-13 | A view observes later writes to its owner (`s := arr[0..2]; arr[0] = 7` then `s[0]` prints 7), while `arr2 := arr` stays 1 | q10 run D/RF |
| CF-14 | Empty slice `arr[1..1]` compiles and iterates zero times; `len = 0` | q25 run D/RF |
| CF-15 | Non-ASCII string literals are accepted; `t[0..2]` of `"héllo"` prints `h` and a lone byte. `c: char = 'é'` is accepted and lowers to `const c: u8 = 'é'`, which Zig builds (value 233 is inferred from Zig character-literal semantics, not printed) despite `SPEC.md:238` "ASCII character (0-127)" | q22 compile exit 0, run D/RF; q23 compile exit 0, build D/RF |
| CF-16 | `slice.ptr` types as a pointer and is treated as non-nil | read `a7/safety.py:434-435`; notes H `type_checker.py:1793-1795` |
| CF-17 | Struct with `string` field copies independently (`bolt nut`); reassigning a `string` in a loop works | q32, q39 run D/RF |

### 6.3 Exclusivity

| # | Fact | Evidence |
| --- | --- | --- |
| CF-18 | Implicit `ref` arguments accept any `IDENTIFIER`, `FIELD_ACCESS`, `INDEX` or `DEREF` lvalue with no overlap check; call arguments are visited without invalidation | read `a7/passes/type_checker.py:1392-1394`, `1868-1874`; `a7/safety.py:444-447` |
| CF-19 | `setx(p.x, p)` with both `ref` is accepted, emits `setx(&p.x, &p)`, prints 6 | q21 compile exit 0, run D/RF |
| CF-20 | `arr = [arr[1], arr[0]]` emits `arr = .{ arr[1], arr[0] };` and prints `2 2` (expected `2 1`) | q06 compile exit 0, run D/RF. **Miscompile today** |
| CF-21 | Struct rebuild `p = Pt{x: p.y, y: p.x}` prints `2 1` (correct), also through a `ref` parameter (`p.?.* = Pt{...}`) and via `a = flip(a)` | q05, q27, q26 run D/RF |
| CF-22 | `bump(a, a)` with `ref` first and by-value second emits `bump(&a, a)`; callee observed the snapshot (`a.y = 1`), also for a 66-field struct (`a.tail = 1`) and for scalars (`r = 1`). No aliasing observed under Zig 0.16.0 for these shapes | q03, q35, q33 run D/RF |
| CF-23 | `SPEC.md:698-702` generic `swap($T, a: ref T, b: ref T)` does not compile: "Undefined type (Identifier 'a')", "Cannot call undefined identifier 'swap'" | q20 exit 6 |
| CF-24 | Non-generic swap cannot be written: `a = b` between `ref` parameters is "Cannot assign to immutable binding"; `t := a` gives `t: ref i32`; `t: i32 = a` is "expected 'i32', got 'ref i32'" | q01, q28, q01b exit 6 |
| CF-25 | Two writes through one scalar `ref` parameter fail: the first `dst = 0` replaces the parameter's `non_nil` fact with the literal's fact, so `dst = 1` is "reference may be nil" | read `a7/safety.py:326-327`; q19b, q19 exit 6 |
| CF-26 | `ref [N]T` parameters cannot be indexed: "Cannot index this type: got 'ref [4]i32'" | q04, q29 exit 6 |
| CF-27 | Literal `4` passed to a `usize` parameter is a type error ("expected 'usize', got 'i32'"); the literal leniency in CLAUDE.md covers indexing only | q02 exit 6 |
| CF-28 | Self-assignment `p = p`, `arr = arr`, `s = s` compiles and runs correctly | q07 run D/RF |

### 6.4 Optionals, unions, initialization

| # | Fact | Evidence |
| --- | --- | --- |
| CF-29 | Optional types do not exist: `x: ?i32` fails at tokenize ("Unexpected character: '?'") | q36 exit 4 |
| CF-30 | `union(tag)` with a `string` payload is accepted and lowers to `union(enum)`; SPEC marks only tag inspection as unimplemented | q37 compile exit 0, build and run D/RF (no output) |
| CF-31 | Untagged union with a `string` payload and an inactive-field read is accepted by A7; Zig 0.16 catches it at compile time only because the value is `const` ("access of union field 's' while field 'n' is active") | q17 compile exit 0, build fail D/RF |
| CF-32 | `pts: [3]Pt` (array of structs, no initializer) is accepted and lowers to `[_]Pt{0} ** 3`, which Zig rejects ("expected type 'Pt', found 'comptime_int'") | read `zig.py:2133-2137`, `2143-2150`; q16 build fail D/RF |
| CF-33 | Struct locals without initializer lower to `undefined`; `h: Holder` emitted `var h: Holder = undefined` | read `zig.py:2115-2141`; q38 emitted Zig |
| CF-34 | The `initialized` fact exists but is set only for declarations without a value; `UNION_FIELD` obligations are declared and never constructed | read `a7/safety.py:144`, `184`, `308` |

### 6.5 Share-until-changed and reuse

| # | Fact | Evidence |
| --- | --- | --- |
| CF-35 | No sharing or reuse analysis exists; plain copies lower to Zig value copies (`var b = a`) | q32 emitted Zig; read `zig.py` emission paths above |
| CF-36 | The only current in-place update hazard observed is Zig result-location aggregate construction into an overlapping target (CF-20). `p = Pt{x: p.y, y: p.x}` printed `2 1` while `arr = [arr[1], arr[0]]` printed `2 2`: Zig 0.16 handled the struct and array-tuple result locations differently in these shapes, so neither is a guarantee. The backend must materialize a temporary itself | q05, q06, q26, q27 run D/RF |
| CF-37 | Backend approvals are keyed by `(id(node), operation)`; any compiler-inserted copy, release or reuse node must be created before the proof pass or carry its own approval | read `a7/safety.py:206-222` |

---

## 7. L19 metric contribution

Counting cases where an ordinary user would notice (diag or behav) under the
recommended rules:

- Diagnostics a Python programmer would meet in ordinary code: EC2-02, EC2-03,
  EC2-18, EC2-33, EC2-40, EC2-43/44/57, EC2-46, EC2-54, EC2-56. Each describes a
  behavior conflict, not memory, if the wording avoids memory vocabulary.
- Behavior surprises versus Python: EC2-05/06/08 (positions), EC2-14 (element
  copies), EC2-19 (missing keys), EC2-20 (empty `len - 1`).
- Hits avoided only by the proposed materialization rule: EC2-26, EC2-29,
  EC2-30, EC2-37. Without it, these are memory-aware rewrites.
- Performance-only: EC2-27, EC2-71, EC2-72, EC2-73 (M8 report).
