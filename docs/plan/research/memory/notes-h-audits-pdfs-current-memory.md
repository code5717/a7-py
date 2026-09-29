> **Source:** Claude Code reading subagent, group H, full read of saved repository research.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../decisions.md).

# H. Audits, pointer-syntax PDFs, and the current A7 memory surface — notes for the L15 brainstorm

Date: 2026-09-15. Read-only research. Repository: `/home/cx89/Projects/pl-dev/a7-py`
(working tree at `701c679` + uncommitted docs; `a7/` last changed in `f793ff4`, i.e. the
compiler source is the same tree the 2026-09-14 audits examined, so their line cites still
resolve).

Sources read completely: `docs/audits/2026-09-14/memory-safety-glm-review.md` (784 lines),
`compiler-review.md` (146), `security-glm-review.md` (463), `language-contract-review.md`
(181), all 7 `evidence/pdf-text/POINTER_SYNTAX_ANALYSIS*.txt` (base read in full, variants
diffed word-by-word), `evidence/pdf-inventory.json`, `docs/SAFETY_CONTRACT.md` (98),
`docs/SPEC.md` §2.6 nil/array init (180-208), §3.3-3.5 (250-401), §6.2-6.3 (719-790), §8
(992-1079), Appendix A.4/E (2083-2089, 2174-2215), `docs/plan/decisions.md` (95), `docs/plan/README.md`
G1-G9 (50-191), all 15 `repros/glm-memsafe-*.a7` fixtures.
Also consulted (not required, cited only where noted): `examples/011_memory.a7`,
`013_pointers.a7`, `025_linked_list.a7`, `026_binary_tree.a7`,
`docs/plan/research/memory-design-codex.md` lines 38-55 and 138-160 (the 3.9k-line
`docs/plan/research/` set exists and was NOT read in full).

Conventions:
- "verified" = I read that source line myself on 2026-09-15.
- "per GLM" / "per C-review" = cited from the audit, not re-read.
- "PROBE" = my own 2026-09-15 compile-only probe under the scratchpad
  (`.../scratchpad/probes/*.a7`), run through `.venv/bin/python main.py`. Nothing was
  built with Zig or executed. These findings are NOT in the audits.
- **Inference:** marks my own reasoning, not a sourced fact.

---

## 1. Current A7 memory surface — documented vs implemented

### 1.1 Documented model (one paragraph)

Value types copy (`SAFETY_CONTRACT.md:84`); locals are stack-allocated and "All automatically
freed" at scope exit (`SPEC.md:996-1002`); heap is manual: `new T` returns a maybe-nil ref,
must be nil-checked, and "heap refs created by `new` must be cleaned up with `del` or `defer
del`" (`SAFETY_CONTRACT.md:85`); "Heap values live until explicit `del`" (`SPEC.md:2086`);
"References must not outlive referent" / "Slices must not outlive backing array"
(`SPEC.md:2087-2088`) are stated as rules with no enforcement note. `SPEC.md:1075-1079`
admits "Ownership, borrowing, or lifetime analysis ... Static double-free or use-after-free
prevention beyond the current basic shape checks" are not implemented. Next phase is "make
heap refs affine, reject conflicting mutable aliases, and add explicit stdlib `clone`"
(`SAFETY_CONTRACT.md:90-91`).

### 1.2 Construct-by-construct

| Construct | Documented | Implemented (file:line) |
| --- | --- | --- |
| `new T` | `SPEC.md:1012-1018` (`box := new Box; if box == nil { ret } ... del box`); `new T(args)`/`new T{...}` "not current syntax" (`SPEC.md:1033`); `new [N]T` banned (CLAUDE.md) | Type: `ReferenceType(referent_type=alloc_type)`, arrays rejected with "new [N]T heap arrays are not implemented" (`type_checker.py:3005-3017`, verified). Lowering: `allocator.create(T) catch null` (`zig.py:1913`, verified) with global `std.heap.page_allocator` (`zig.py:159`, verified). A dead `allocator.alloc(elem, size) catch null` path for arrays remains (`zig.py:1909-1912`, verified). Allocation failure becomes silent `null`. |
| `del x` | "validated for reference-like values, and direct reads after `del` are rejected until the binding is reassigned" (`SPEC.md:1071-1072`) | Validator: only "operand has ReferenceType" (`semantic_validator.py:384-396`, verified) — no heap provenance. Safety: `_mark_deleted` adds the syntactic identifier *name* to a single `moved_symbols` set (`safety.py:724-726`, verified); reads of that name error "was moved or deleted earlier" (`safety.py:397-399`, `:728-737`). Lowering: `if ({expr}) \|p\| allocator.destroy(p);` — fixed capture name `p`, no nulling (`zig.py:1300-1306`, verified). |
| leak (no `del`) | "must be cleaned up" (`SAFETY_CONTRACT.md:85`) | Not checked. `self.allocations: Set[str] = set()` "Track allocations for new/del validation" is never used (`semantic_validator.py:45-46`); `visit_new_expr` is a stub: "In a more complete implementation, we'd track which variable holds the reference and ensure it's del'd" / `pass` (`semantic_validator.py:491-499`, verified). PROBE `leak.a7` (`p := new Pt` only) → exit 0, emits `const p = allocator.create(Pt) catch null; _ = p;`. |
| `defer` | LIFO, scope exit (`SPEC.md:1042-1063`); blessed idiom `defer del value_box` (`examples/011_memory.a7:17`) | Validator records defer (`semantic_validator.py:380-381`). Safety visits a deferred `del`'s operand *without* marking it deleted (`safety.py:379-386`, verified). Lowering is 1:1 Zig `defer` (`zig.py:1272-1298`, verified). |
| `ref T` (params) | Caller passes plain lvalue; callee writes `value = 100` (`SPEC.md:305-310`, `383-388`); "`T` to `ref T` in function calls" implicit conversion (`SPEC.md:2072`); binding immutable, referent mutable (`SPEC.md:761-763`) — matches L6 | Type lowers to nullable `?*T` (`zig.py:2100-2104`, verified). Call sites emit `&arg` for indices in `implicit_ref_args` (`zig.py:1661-1666`, verified). Field access/write through ref emits `.?` / `.?.*` after a non-nil approval (`zig.py:1713-1749`, per GLM). |
| `.adr` / `.val` / `&` / `*` | Absent from public syntax (`SAFETY_CONTRACT.md:64-67`, `SPEC.md:399-401`) | `.adr`/`.val` rejected: "'.{field_name}' is not reference syntax; pass lvalues directly to ref parameters" (`type_checker.py:1784-1791`, verified). Parser tests still accept them (`test_parser_combinatorical.py:867-896`, per GLM §6). |
| `nil` | Only for `ref T`; "represents a null pointer" (`SPEC.md:185`); `fn_ptr: ref fn() void = nil` (`SPEC.md:192`) | Maybe-nil until proven (`SAFETY_CONTRACT.md:77-78`); non-nil fact learned from guards/early return (`safety.py:663-668`, `:698-702` per GLM); failure message "reference may be nil" (`safety.py:629`, verified). Planned split `ref T` non-null / optional `ref T` (`SAFETY_CONTRACT.md:69-76`) not implemented. |
| `ref ref T` | `SPEC.md:299-300` | PROBE `refref.a7` (`p: ref ref i32 = nil`) → exit 0. |
| returning a ref | not discussed | PROBE `retref.a7` (`mk :: fn() ref Pt { p := new Pt; ret p }`) → exit 0 (ownership transfer by return is unconstrained). |
| Slices | "Dynamic view into array"; `slice.ptr`, `slice.len` (`SPEC.md:269-277`); "String is equivalent to `struct { ptr: ref u8, len: usize }`" (`SPEC.md:287-291`) | `slice.ptr` types as `PointerType(element)` (`type_checker.py:1793-1795`, verified) — **inference:** a public pointer-valued surface despite "no address-of". Slicing needs `slice` approval then raw `obj[s..e]` (`zig.py:1688-1694`, verified). Unknown-length slice indexing fails closed (`glm-memsafe-neg-slice-index.a7`). No lifetime tracking (MS-8). |
| Arrays | Fixed stack arrays, `T.len`, element-wise `+` (`SPEC.md:252-267`); "No initializer (zero-initialized)" and "Single value (all elements): `arr: [5]i32 = 0`" (`SPEC.md:201-204`) | Index needs `index` approval, raw `obj[i]` or `obj[@intCast(i)]` (`zig.py:1670-1686`, verified). Array defaults are zero-filled `[_]T{0} ** N` (`zig.py:2133-2137`, verified). Single-value init is rejected (MS-12 drift). Inferred array literals lower to Zig tuples `.{ ... }` (`zig.py:1897-1901`), which cannot be runtime-indexed (MS-12, C2). |
| Unions | `Number :: union {...}; value := Number{i: 42}; same_value: i32 = value.i` (`SPEC.md:331-338`); tagged `union(tag)` "reserved syntax and is not implemented" (`SPEC.md:349-350`) | Untagged → plain Zig `union`, tagged → `union(enum)` (`zig.py:607-626`, verified). `ObligationKind.UNION_FIELD` declared (`safety.py:184`, verified) and never constructed (per GLM). |
| Struct ref fields | `SAFETY_CONTRACT.md:66-67` "ref struct fields are accessed directly after nil-proofing" (ambiguous: fields *of* a ref, or fields *of type* ref) | Examples only use `ref Struct` **parameters** (`examples/017_methods.a7:9`, `038:16`, `040:12,16`, `041:17`, `042:25`). PROBE `structref*.a7`: a **self-referential** field `next: ref Node` fails type-check — "Assignment type mismatch: expected 'ref unknown type', got 'ref Node'" (also on `a.next = nil`: "expected 'unknown type', got 'unknown type'"), exit 6. PROBE `reffield_other.a7`: a **non-self** field `Holder :: struct { p: ref Pt }` works. So ref-linked lists/trees cannot be written today; `examples/025_linked_list.a7:5-8` (`next: isize`) and `026_binary_tree.a7:5-9` (`left: usize`, `right: usize`) use index links instead. |
| Uninitialized locals | "No initializer (zero-initialized)" (`SPEC.md:202`) | `_default_value`: ints `0`, floats `0.0`, bool `false`, string `""`, arrays zero-filled, pointers `null`, **everything else `undefined`** (structs, unions, slices, refs declared via non-`TYPE_POINTER` nodes) (`zig.py:2115-2141`, verified). Safety `initialized` fact exists (`safety.py:144`) but is never read (per GLM). |
| Recursion (stack) | Banned (`SPEC.md:721-726`) | Name-keyed call graph over bare identifiers (`semantic_validator.py:501-544`, `:803-818`, per GLM); struct-field fn pointers and module-qualified calls bypass (MS-7). |

### 1.3 Proof engine facts that any L15 analysis would inherit

- Facts are `ValueFact{interval, nonzero, known_length, non_nil, maybe_nil, initialized,
  moved, enum_discriminant}` (`safety.py:137-146`, verified) — no alias, provenance,
  region, or lifetime field.
- `FactMap.by_symbol: dict[str, ValueFact]` is keyed by **name string**
  (`safety.py:152`, `:159-168`, verified). Reset per function (`safety.py:290`), but
  `moved_symbols` is not (C4).
- BLOCK: `saved = copy_symbols(); ...; restore_symbols(saved)` (`safety.py:301-306`,
  verified); IF (`:335-342`, restores after the then-branch, verified), WHILE/FOR
  (`:352`, `:363`, per grep) and FOR_IN (`:364-371`, verified) also restore. MATCH
  begins at `:372`; its handling was not read.
- CALL: visits callee and args only (`safety.py:444-447`, verified).
- Overflow proof: unconditional `return` (`safety.py:631-636`, verified).
- Divisor proof has no float branch: `_prove_nonzero_divisor` (`safety.py:559-565`,
  verified). PROBE `fdiv.a7` (`zero: f64 = 0.0; ratio := zero / zero`) → exit 6
  "division/modulo divisor must be non-zero: divisor may be zero" (same result as
  `docs/plan/README.md:74-76`).
- Backend approvals keyed by `(id(node), operation)` (`safety.py:208-222`, per GLM);
  codegen fails closed (`zig.py:1786-1795`, per GLM).
- Release profile is `-OReleaseFast` (`scripts/build_examples.py:25`, per GLM), which
  removes Zig's bounds/null/union/overflow backstops (GLM §5 table, lines 502-517).

---

## 2. Confirmed memory defects and the effect of an automatic compile-time model (L15)

Legend for the L15 column:
- **Eliminated** — the user-facing construct that causes it disappears if the user no longer
  writes `del`.
- **Moved** — the bug class disappears from user code but the *same* analysis obligation
  moves into the compiler (it must now insert frees correctly).
- **Foundational** — L15 does not remove it; an automatic model *depends on* fixing it
  first, more than the manual model did.
- **Orthogonal** — unaffected.
All L15 verdicts are **inference**.

| ID | Class (audit's) | Fixture / evidence | Mechanism (cite) | L15 effect |
| --- | --- | --- | --- | --- |
| MS-1 / C2 | Undisclosed defect, critical | `glm-memsafe-join-stale-index.a7` (`y: usize = 0; if c { y = 5 }; arr[y] = 1`, lines 3-8); C-review `a7audit_branch_zero.a7`, `a7audit_branch_bounds.a7`, `a7audit_loop_bounds.a7` | Snapshot-restore at block exit discards writes to outer bindings (`safety.py:301-306`); Debug panic observed for branch_zero (C-review:44) | **Foundational.** Any compile-time liveness/"last use" or drop-flag analysis needs a correct join over branches and a loop fixpoint. If `x` is freed on one branch only, a snapshot-restore engine would forget it — producing either a double free or a use-after-free in compiler-inserted code. |
| MS-2 / C3 | Undisclosed defect, critical | `glm-memsafe-call-del-stale-nil.a7` (`kill :: fn(pp: ref Pt) { del pp }` lines 5-7; `kill(q); q.x = 1` lines 14-15). Note: the fixture uses `pp`, while report text at memsafe:253 shows `p`. C-review `a7audit_ref_zero.a7` (Debug panic, ReleaseFast SIGSEGV, C-review:62) | Calls invalidate nothing (`safety.py:444-447`) | Split: the **`del`-through-callee** half is **eliminated** (users cannot free through a `ref` param). The **value/nil-staleness across calls** half is **foundational**: an automatic model needs per-call effect summaries ("does the callee consume, store, or retain this argument?"). **Inference:** the recursion ban makes the call graph a DAG, so bottom-up summaries are computable without a fixpoint — but only if MS-7 bypasses are closed. |
| C1 | P1 | `a7audit_compound_zero.a7` (`d: i32 = 1; d -= 1; 10 / d`); Debug `panic: division by zero` observed (C-review:28) | `set_symbol(node.target.name, rhs)` records RHS as result (`safety.py:327`, per C-review:22) | **Orthogonal to memory ownership, foundational to fact soundness.** Any size/length facts used for automatic buffer reuse would inherit it. |
| C4 | P2 | `a7audit_deleted_name.a7` (unused fn deletes local `p`; unrelated `p: i32` in `main` rejected) | One global name-string moved set, reset only at analysis start (`safety.py:288-294`, `395-399`, `724-726`) | **Moved/foundational.** Binding identity (not names) is prerequisite for any automatic ownership tracking. C-review:78 already asks to "key ownership state by resolved binding identity". |
| MS-3 | Documented gap, silent acceptance, high | `glm-memsafe-alias-double-del.a7` (`pp := new Pt; q := pp; del pp; del q`, lines 6-9); same program observed 2026-09-15 in `docs/plan/README.md:107-116` | Name-keyed moved set, no points-to (`safety.py:724-726`, `137-146`) | **Eliminated as written, moved in substance.** Without `del`, no double free by users; but the compiler must decide *who* frees the allocation after `q := pp` — move (invalidate `pp`), copy-with-sharing (needs RC or a region), or reject. |
| MS-3 variant | **PROBE, not in audits** | `reffield_other.a7`: `h := Holder{p: a}; del a; q := h.p; if q == nil { ret }; q.x = 5` → exit 0; emitted `if (a) \|p\| allocator.destroy(p); var q = h.p; ... q.?.x = 5;` | Aliases through struct fields are untracked | Same as MS-3, harder: aliasing through aggregate fields. Under L15 an owned field must be either the unique owner (move semantics) or a non-owning handle. |
| MS-4 | Defect by silence, high | `glm-memsafe-defer-del-double.a7` (`pp := new Pt; defer del pp; del pp`, lines 6-8) | Deferred `del` not marked (`safety.py:379-386`); `del` does not null (`zig.py:1306`) | **Eliminated** if `del`/`defer del` leave the language. If they remain as an optional early-release (as Odin/Zig style might suggest), still needs scheduled-cleanup conflict tracking (GLM §7.3c, memsafe:579-587). |
| MS-5 | Defect by silence, high | `glm-memsafe-del-ref-param.a7` (`bad :: fn(x: ref i32) { del x }; v := 3; bad(v)`) → emits `allocator.destroy` on `&v` (memsafe:319-320) | `ref T` type does not distinguish heap from stack referents (`semantic_validator.py:384-396`; auto-`&` `zig.py:1661-1666`) | **Eliminated** as user-visible free; **moved** as a type question: L15 must separate *owning* heap refs from *borrowed* refs (auto-`&` lvalues), or the compiler cannot know which to free. |
| MS-6 | Documented gap, high | `glm-memsafe-union-inactive-field.a7` (`u := U{a: n}; ret u.b`, lines 7-8) | `UNION_FIELD` never constructed (`safety.py:184`) | **Changed / worsened.** Not a memory-ownership bug today, but under L15 a union holding an owning ref makes the automatic destructor depend on the active variant — untagged unions become unmanageable (**inference**). Pushes toward tagged-only unions for any ref-containing payload (G5). |
| MS-7a | Undisclosed defect, high | `glm-memsafe-recursion-struct-fnptr.a7` (`s := Cb{f: spin}; ... ret s.f(n - 1)`, lines 6-10) | Call graph only follows bare identifiers (`semantic_validator.py:803-818`, `:1091-1104`) | **Foundational (indirect).** If L15 relies on the acyclic call graph for summaries or bounded stack (DOD programs), bypasses break that premise. G4 (`docs/plan/README.md:152-158`). |
| MS-7b | Undisclosed defect, high | `repros/glm-memsafe-recursion-module/main.a7` (`helper :: import "./helper"`; `task` calls `ret helper.work(n - 1)`, lines 1-8) + `helper.a7` (`work :: fn(n: i32) i32 { ret task(n) }`, lines 1-3). This directory is the 16th fixture counted at memsafe:753. | `_annotate_file_module_calls` leaves FIELD_ACCESS callee (`compile.py:574-595`) | Same as 7a. |
| MS-8 | Documented gap + silence, high | `glm-memsafe-slice-stack-escape.a7` (`buf: [4]i32 = ...; ret buf[0..4]`, lines 2-4) | No escape analysis anywhere | **Foundational — becomes the core of L15.** Compile-time automatic memory is essentially escape + lifetime inference; the audits show zero existing machinery. |
| MS-8 pointer analogue | GLM marked **[HYP]** (memsafe:388-389); **now compile-confirmed by PROBE** | `dangle_refparam.a7`: `keep :: fn(v: ref Pt) Holder { ret Holder{p: v} }; mk :: fn() Holder { t := Pt{x: 1}; ret keep(t) }` → exit 0; emits `var t = Pt{ .x = 1 }; return keep(&t);` then `q.?.x = 5` in `main` through the dangling stack address. Related `store_refparam.a7`, `ret_refparam.a7` accepted (those two instances are not dangling, since `t` lives in `main`). | Auto-`&` refs are ordinary values that can be stored/returned | **Foundational.** Borrowed (auto-`&`) refs must be non-escaping, or their lifetime must be tracked into return values. |
| MS-9 | Defect by silence, medium | `glm-memsafe-uninit-struct-slice.a7` (`p: Point; v := p.x; s: []i32`, lines 8-10) | `_default_value` → `undefined` (`zig.py:2115-2141`) | **Changed.** Orthogonal today, but under L15 an automatic destructor running on an `undefined` owning-ref field frees garbage — so definite initialization becomes a memory-safety prerequisite (**inference**). |
| MS-10 | Documented gap | (no fixture) | `safety.py:631-636` | **Orthogonal.** Already reframed by L5 (wrapping `+ - *`); allocation-size arithmetic remains a G3 item and matters to L15 buffer sizing. |
| MS-11 | Defect (codegen) | `glm-memsafe-del-var-named-p.a7` (`p := new Point; del p`) → Zig `capture 'p' shadows local constant` | `zig.py:1306` fixed `\|p\|` | **Eliminated** if user `del` goes away, but compiler-inserted frees must use fresh names (same lesson). |
| MS-12 | Verified drift | `arr: [3]i32 = 0` rejected vs `SPEC.md:203`; ref literal write | `type_checker.py:834-838` | **Orthogonal.** |
| C5, C6 | P2 codegen | `a7audit_reserved.a7`, `a7audit_unused_iterator.a7`, `a7audit_shadow_iterator.a7` | `zig.py:637-690`, `920-952` | **Orthogonal**, but compiler-generated cleanup code must go through one identifier-escaping path (**inference**). |
| C7 | P2 | 1200-term flat expression → `RecursionError` | `type_checker.py:1118`, `1129`, `1194-1195` | **Orthogonal**; any new ownership pass must be iterative (CLAUDE.md invariant). |
| Leak | **PROBE, not in audits** | `leak.a7` exit 0 | `semantic_validator.py:491-499` stub | **Eliminated** by construction under L15 (the compiler inserts the free). |
| Self-ref ref field | **PROBE, not in audits** | `structref*.a7` exit 6 | type resolution of `ref Node` inside `Node` yields "ref unknown type" | **Changed.** Today it is a type-checker limitation, but it hides the hardest L15 case (owned recursive/cyclic structures). |
| LH-1 | Latent hazard | none | approvals keyed by raw `id()` (`safety.py:208-222`) | **Worsened (inference).** If L15 inserts free/drop nodes after safety proof, those new nodes have no approvals and `id()` reuse becomes live. Insertion must happen before proof or carry approvals. |
| LH-2 | Latent hazard | none | dead `GenericMonomorphizer` (`generics.py:121-243`) | **Changed (inference).** Generic `$T` bodies lower to Zig `comptime` (`zig.py:432-436`); whether `$T` owns heap memory is unknown when the body is checked once — L15 needs per-instantiation drop glue or a constraint. |

Security review (`security-glm-review.md`) explicitly excludes memory semantics (line 13-14:
"Memory-semantics findings are owned by `memory-safety-glm-review.md` and are excluded
here"). Its only L15-relevant points: A7 "is **not a sandbox**" (line 17), and
compiler-process DoS/recursion robustness (SEC-10, lines 289-312). No MS-style defects.

Language-contract review (`language-contract-review.md`) has no memory defects; relevant
items are LC-D01 (`SAFETY_CONTRACT` fail-closed promise vs incomplete enforcement, and
`SPEC.md` A.4 lifetime rules stated "without an adjacent implementation qualification",
line 144) and the roadmap criterion "Safety qualification covers ... alias invalidation,
lifetime escape, and indirect recursion" (line 157-159).

---

## 3. Pointer-syntax PDFs

### 3.1 Inventory and duplicates

All seven PDFs were produced 2025-09-23 (`pdf-inventory.json`: CreationDate 00:13-00:18
+03), i.e. about one year before the current reference model. All `qpdf` checks pass.

| Text file | Lines | Producer (inventory) | Relationship to base |
| --- | --- | --- | --- |
| `POINTER_SYNTAX_ANALYSIS.txt` | 614 | wkhtmltopdf, 12 pp | **Base; read in full.** |
| `_wkhtmltopdf_direct.txt` | 611 | wkhtmltopdf, 10 pp | **Word-identical** to base (empty word diff). |
| `_html_styled.txt` | 538 | wkhtmltopdf, 9 pp | Near-duplicate; differences are only ligatures (`ﬁ`→`fi`), hyphenation, table-cell wrapping and missing running page headers (`A7 Pointer Syntax Analysis`). |
| `_compact.txt` | 558 | pandoc/pdfTeX, 9 pp | Near-duplicate; caret glyph `ˆ` instead of `^` (e.g. `ptrˆ`), ligatures, layout. |
| `_dark.txt` | 563 | pandoc/pdfTeX, 10 pp | Same as compact (identical diff profile). |
| `_latex.txt` | 522 | pandoc/pdfTeX, 10 pp | Same as compact plus table-of-contents dot leaders/page numbers and `ADR (x)` spacing (latex:298). |
| `_beamer.txt` | 120 | pandoc/pdfTeX beamer, 8 slides | **Truncated** slide deck (3,770 chars): title, ToC, C only (lines 33-47), the A7 "current" block (49-65), options 1-2 (67-83), readability table (85-95), start of the feature matrix (97-102), and the hybrid recommendation (103-119). Nothing new. |

Conclusion: there is one document, analysed once below (line numbers are from the base file).

### 3.2 Summary of the analysis

1. **Survey of 17 languages** (lines 16-340): C `&x`/`*p`/`->`; C++ references and smart
   pointers; Rust `&`/`&mut`, `unsafe` raw pointers, auto-deref, `Box`; Zig `&x`/`p.*`,
   optional pointers `?*i32` unwrapped with `if (maybe_ptr) |p|` (89-93), auto-deref
   fields, slices; Odin `&x`/`p^`, `rawptr`, slices as fat pointers (133-136); Jai `*x`
   address-of and `<<p` deref (141-159); Go (no pointer arithmetic, 169-170); Swift
   `.pointee`, class references hide pointers (204-207); D `ref` params (218-221); Nim
   `addr`/`p[]` and managed `ref object` types with auto-deref (246-253); V; Carbon;
   Pascal `@`/`^`; Ada `'Access`/`.all`, `P : Point_Ptr := new Point` (320-323);
   Modula-2 `ADR`/`^`.
2. **"A7 Current Syntax"** (344-376), labelled "Property-based approach (current
   implementation)": `ptr: ref i32 = x.adr`, `value := ptr.val`, `ptr.val = 100`,
   `ptr_ptr.val.val`, `point_ptr.val.x = 10.0` ("Explicit deref for field access"),
   `swap(x.adr, y.adr)` ("Pass addresses explicitly"). **Obsolete** — rejected by
   `type_checker.py:1784-1791`.
3. **Eight proposed alternatives** (380-482): C-like `&`/`*`; Odin postfix `x&`/`p^`;
   Zig `&`/`.*`; keywords `addr`/`deref`; Pascal-ish `@x`/`^p`; unified property
   `x.ref`/`p.val` or `x.&`/`p.*`; **Option 7 "Context-Sensitive"** — "Type system handles
   most cases", `ptr: ref i32 = x // Auto-address when needed`, `value: i32 = ptr //
   Auto-deref when needed` (459-469); method/pipeline style.
4. **Comparative analysis** (486-546): readability table; feature matrix with columns
   Address-of / Dereference / Auto-deref fields / Null safety / Arithmetic, A7 row
   `x.adr  ptr.val  No  Yes  TBD` (525); beginner ranking puts `.adr/.val` first (530).
5. **Recommendation** (549-614): "Hybrid Approach" — `ptr := &x`, `value := ptr^`, auto
   deref for fields, "Property syntax still available for clarity" (`x.adr`, `ptr.val`),
   "Multiple approaches coexist" (553-578); alternative "Pure Zig-style" (589-599); final
   "Overall Best: - Hybrid: Support both &x/ptr^ AND x.adr/ptr.val" (612-613).

The PDFs discuss **syntax only**: no ownership, lifetime, allocation, deallocation, aliasing,
or safety semantics beyond a one-word "Null safety" column.

### 3.3 What remains relevant to L15 despite obsolete syntax

- **Option 7 ≈ today's model.** "Auto-address when needed / Auto-deref when needed"
  (459-469) is essentially what A7 shipped: implicit `&` at ref call sites
  (`zig.py:1661-1666`), implicit deref on assignment (`SPEC.md:385-386`). **Inference:** an
  L15 design that keeps pointers invisible needs the compiler to know, at every implicit
  address-of, whether the resulting ref may escape — the syntax choice already committed
  A7 to compiler-owned lifetime reasoning.
- **Auto-deref for fields everywhere** (391-392, 561-562, 613-614) survives as
  `counter.value += 1` (`SPEC.md:394-396`).
- **Zig optional pointer + capture** (89-93) is exactly the current lowering
  (`?*T`, `if (x) |p|`) and the planned non-null / optional split
  (`SAFETY_CONTRACT.md:69-76`).
- **Nim `ref object` managed pointers** (246-253), **Swift class references** (204-207) and
  **Go "Interfaces hide pointers"** (181-183) are the only surveyed precedents for pointers
  whose reclamation is not the programmer's job. **Inference / to verify externally:** Nim's
  current ARC/ORC memory management (compile-time-inserted moves, destructors and reference
  counts) is the closest match to "GC-like but resolved at compile time" among them; Swift
  ARC is the runtime-counted counterpart.
- **Ada `new Point` with access types** (320-323) shows `new` without a matching user
  `free`; Ada storage pools are a precedent for allocator-scoped lifetimes (**inference**).
- **Slices as fat pointers** (Zig 102-105, Odin 133-136) — the DOD-relevant non-owning
  view that A7 already has; its lifetime is the MS-8 problem.
- **"Arithmetic" column** (505, A7 = "TBD" at 525) — pointer arithmetic is still
  undecided in writing; L15 + DOD handle/index idioms argue for none (**inference**).
- **Rust `&` vs `&mut`** (55-58) maps onto the L6 read-vs-referent-mutation permission.
- **Jai's context-sensitive `ptr: *int = *x`** (159) — the only Jai material in the repo
  evidence; says nothing about Jai memory management.

---

## 4. Claims that conflict with L15 (automatic compile-time memory) or L16 (IEEE floats)

### 4.1 Conflicts with L15

| Where | Quote | Conflict |
| --- | --- | --- |
| `docs/SPEC.md:2086` | "Heap values live until explicit `del`" | Manual lifetime is the specified rule. |
| `docs/SPEC.md:1012-1018`, `:1025-1031` | `box := new Box` ... `del box`; `point := new Point` ... `del point` | Manual deletion is the documented idiom. |
| `docs/SPEC.md:1050-1054` | `point := new Point` / `defer del point` / "Both cleaned up automatically" | "Automatically" here means user-scheduled `defer`, not compiler-inferred. |
| `docs/SPEC.md:1073` | "`defer del value` can express manual cleanup at scope exit." | Manual model. |
| `docs/SPEC.md:1077` | Not yet implemented: "Ownership, borrowing, or lifetime analysis that proves absence of dangling pointers." | Framed as future add-on analysis on top of manual `del`, not an automatic model. |
| `docs/SAFETY_CONTRACT.md:85` | "heap refs created by `new` must be cleaned up with `del` or `defer del`" | Directly contradicts automatic cleanup. |
| `docs/SAFETY_CONTRACT.md:86-87` | "direct use after `del` is a compile-time error" / "assignment after `del` reinitializes the binding" | Presupposes user `del`. |
| `docs/SAFETY_CONTRACT.md:90-91` | "The next ownership phase will make heap refs affine, reject conflicting mutable aliases, and add explicit stdlib `clone`" | Affine refs are compatible with L15 only if the compiler, not the user, performs the final release. Needs restating. |
| `docs/SAFETY_CONTRACT.md:53` | "Use after `del` ... deleted binding is not read again before reassignment" | Risk row built around manual `del`. |
| `examples/011_memory.a7:17` | `defer del value_box` | Blessed example; removing `del` is a breaking change under L2 and the approval rule (`docs/plan/decisions.md:21-27`: "everything that changes, ask me with examples"). |
| `memory-safety-glm-review.md:565-588` (§7 decision 3) | "`del` must be legal only where the value *at that program point* provably flows from a `new`" ... "`defer del` should be modeled as **scheduled cleanup**" | Remediation assumes user `del` stays. Reframe it: the same provenance facts would decide where the *compiler* inserts frees. |
| `memory-safety-glm-review.md:589-594` (§7 decision 4) | "reject `q := p` copies of ref-typed values (breaking change), or diagnose only conflicting `del`s via ... 'allocation state' tracked per `new` site" | Same presupposition. |
| `memory-safety-glm-review.md:679-684` (Phase 1c) | "`del` discipline: path-valid heap-provenance requirement ..., null-after-del emission, and scheduled-cleanup conflict tracking for `defer del`" | Phase plan assumes manual `del`. |
| `docs/plan/README.md:118-122` (G2) | "(a) Syntax-free affine references (recommended first)" / "(c) Regions or arenas later" | G2 option (a) is recommended as affine plus manual `del`, while regions/arenas (the likely DOD compile-time form) are deferred to "later". L15 inverts that priority. G2 is still listed as open (`decisions.md:66`: "Research complete; gate G2"), so L15 should be recorded as partly resolving G2. |
| `docs/plan/research/memory-design-codex.md:148` (not in required list) | "**Alternative A is the best starting point for A7.** It preserves explicit allocation and gives `del` a coherent consuming meaning." | Recommends a manual consuming `del`. |
| `docs/plan/research/memory-design-codex.md:55` (not in required list) | "Jai — Insufficient current authoritative evidence established. No ownership guarantee or current syntax recommendation is derived from Jai." | L15 names Jai as a model, but the repo's research has no usable Jai evidence. |
| `docs/lang-safety/README.md:20-26` (as quoted at memsafe:149) | "Statically rejects **every** memory-safety-violating program; ... no unsafe escape hatch" | **Inference:** Jai, Odin and Zig all rely on manual allocators and unchecked escape hatches. "In the style of Jai/Odin/Zig" and "no unsafe escape hatch" pull in opposite directions. The user must choose. |
| `pointer-syntax PDFs` base:344-376 | "Property-based approach (current implementation)" `x.adr` / `ptr.val` | Obsolete; also conflicts with the locked no-address-of rule. |
| base:553-578, 612-614 | "ptr := &x", "value := ptr^", "Overall Best: - Hybrid: Support both &x/ptr^ AND x.adr/ptr.val" | Conflicts with the no-public-address-of/deref rule (CLAUDE.md; `SAFETY_CONTRACT.md:64-67`). **Inference:** user-visible address-of also makes compile-time automatic reclamation much harder because arbitrary addresses can be taken and stored. |
| base:525 | A7 row "Arithmetic ... TBD" | Pointer arithmetic is undecided; must be "no" for any sound compile-time model (**inference**). |

Not a conflict, but note: `SPEC.md:996-1002` "All local variables are stack-allocated ...
All automatically freed" already matches L15's direction for the stack.

### 4.2 Conflicts with L16 (Zig/C IEEE floats)

| Where | Quote | Conflict |
| --- | --- | --- |
| `docs/SAFETY_CONTRACT.md:48` | "Division or modulo | divisor is non-zero" (no integer/float distinction) | Under IEEE, `x / 0.0` is `±inf` or NaN, an ordinary value. |
| `a7/safety.py:559-565` (verified) + PROBE `fdiv.a7` | `"division/modulo divisor must be non-zero"` → "divisor may be zero", exit 6 for `zero / zero` on `f64` | The implementation applies the integer rule to floats (also recorded at `docs/plan/README.md:74-76`). |
| `docs/plan/decisions.md:79` (superseded record) | D.001 "No NaN, no inf" for `number` | Already superseded; listed for completeness. |
| `docs/plan/README.md:64-65` | "accepted research promises finite-only values" | Research promise to be removed (G1 recommendation agrees with L16). |
| `docs/SPEC.md:236-237` | `f32` "IEEE 754 single", `f64` "IEEE 754 double" | **Consistent** with L16. |
| `a7/safety.py:545-546` | "float-to-int cast requires finite integral range proof" | **Consistent** with L16; float→int remains a proof obligation because Zig `@intFromFloat` is UB out of range (memsafe:509). |

No audit claim conflicts with L4/L5/L6 beyond what `decisions.md:86` already marks superseded
(`SAFETY_CONTRACT.md:54` range proofs for `+ - *`).

---

## 5. Hard cases for any L15 design (drawn from these sources)

Each case gives the source, the minimal A7 shape, and why it is hard. The "why" parts are
**inference** unless cited.

1. **Copy of an owning ref** — `glm-memsafe-alias-double-del.a7:6-9` (`q := pp`). Who owns the
   allocation afterwards: move (`pp` becomes dead), share (RC/region), or reject?
   `SAFETY_CONTRACT.md:84` says "value types copy by value", but refs are not value types.
2. **Aliasing through aggregates** — PROBE `reffield_other.a7` (`Holder{p: a}` then use via
   `h.p`). Field-sensitive ownership is needed; DOD code stores references in arrays of
   structs.
3. **Conditional release / joins** — MS-1 (`safety.py:301-306`). If an owner is consumed
   on one branch only, the compiler needs drop flags (a runtime bit) or must reject. Is a
   drop flag acceptable under "everything resolved compile-time"?
4. **Loops** — loop bodies are visited once with restore (`safety.py:345-363`, per GLM).
   Examples: allocate per iteration, or keep the last iteration's value. Needs a fixpoint.
   For DOD, per-frame or per-iteration scratch arenas are the idiomatic answer.
5. **Ownership across calls** — MS-2 (`kill(q)`), C3 (`zero(d)`). Callee may consume, store,
   or only borrow. Needs signatures or inferred summaries. L6 approves the permission
   principle only; "No parameter-mode syntax is approved" (`decisions.md:55-56`). Proposed
   D.040/D.041/D.049 parameter modes "Not accepted" (`decisions.md:87`).
6. **Heap vs stack referents in one type** — MS-5 (`del` on `&v`). `ref T` covers both
   `new` results and auto-`&` lvalues (`zig.py:1661-1666`). An automatic model must split
   owning from borrowed.
7. **Escapes of borrowed storage** — MS-8 (`ret buf[0..4]`), PROBE `dangle_refparam.a7`
   (`ret keep(t)` storing `&t` in a returned struct). Needs lifetime/escape inference
   across returns and aggregate construction.
8. **Returning owned refs** — PROBE `retref.a7` (`mk :: fn() ref Pt { p := new Pt; ret p }`)
   — ownership transfer out of a function; this is the "factory" pattern DOD code uses for
   pools.
9. **Recursive and cyclic structures** — PROBE `structref*.a7` shows self-referential
   `ref Node` fields currently fail to type-check; examples `025`/`026` use `isize`/`usize`
   index links. Cycles are the classic case compile-time schemes cannot reclaim (RC leaks,
   affine forbids). **Inference:** the index/handle idiom is already DOD-shaped, and
   `memory-design-codex.md:157` suggests "checked indices or generation-bearing handles for
   shared graph relationships".
10. **Unions containing owners** — MS-6. The destructor depends on the active variant;
    untagged unions (`SPEC.md:331-338`) cannot be dropped safely.
11. **Uninitialized owners** — MS-9 (`zig.py:2141` → `undefined`). An automatic drop of an
    uninitialized field frees garbage. Requires definite initialization.
12. **Allocation failure** — `new` lowers to `catch null` (`zig.py:1913`) and forces a nil
    check (`SPEC.md:1035-1039`). Automatic cleanup must work on partially constructed
    aggregates; `memory-design-codex.md:210` warns that cleanup "cannot assume allocating a
    worklist will succeed during out-of-memory recovery".
13. **Deep destruction without recursion** — A7 bans source recursion, and compiler
    internals must be iterative (CLAUDE.md). Compiler-generated drop glue for nested owned
    structures must also be iterative or bounded (same `memory-design-codex.md:210`
    concern).
14. **`defer` interaction** — MS-4. If explicit early release survives (`del` or an arena
    `reset`), conflicts with automatic release must be diagnosed.
15. **Stored function values** — MS-7a (`Cb{f: spin}`). Closures or callbacks that capture
    owners, plus call-graph soundness for summaries. G4 (`docs/plan/README.md:152-158`).
16. **Cross-module flow** — MS-7b; modules are inlined into one program
    (`compile.py:235-261`, per GLM), and per-module name-resolution errors are discarded
    (LH-4, `module_resolver.py:162-166`). Whole-program analysis is possible today but may
    not survive separate compilation.
17. **Generics** — generic bodies are checked once and lowered as Zig `comptime`
    (`zig.py:432-436`, per GLM); whether `$T` owns memory is unknown at check time (LH-2).
18. **Compiler-inserted code vs. proof approvals** — LH-1 (`id()`-keyed approvals,
    `safety.py:208-222`). Inserted frees or moves must be created before the safety proof
    or carry approvals.
19. **Release profile has no backstop** — ReleaseFast removes all Zig checks
    (memsafe:187-192); page_allocator "has no double-free/UAF detection in any mode"
    (memsafe:512). An unsound compile-time free is silent corruption. G9 is still open
    (`docs/plan/README.md:187-191`).
20. **Name-keyed state** — C4 and `safety.py:152`. An ownership pass needs binding
    identity, not strings.
21. **Nullable refs** — `ref T` is `?*T` today (`zig.py:2100-2104`); the non-null split is
    planned (`SAFETY_CONTRACT.md:69-76`). Moved-from owners could become "nil"
    (Zig/Odin-like) or statically dead (affine).
22. **Pointer-valued escape hatches in the public surface** — `slice.ptr`
    (`SPEC.md:275`, `type_checker.py:1793-1795`), `string.ptr: ref u8` (`SPEC.md:288-291`),
    `fn_ptr: ref fn() void` (`SPEC.md:192`). Are these owning, borrowed, or raw?
23. **Tensors / autodiff saved values** — "Tensor saved-value lifetime depends on this gate"
    (`docs/plan/README.md:125-126`); G8 depends on G2 (`:184-185`); L9 A7-owned tensors.
    Large buffers with graph-scoped lifetimes are a natural region/arena fit, but the
    autodiff tape must retain saved values across the forward and backward passes.
24. **Concurrency** (L1) — G7 depends on G2 (`docs/plan/README.md:176-177`); allocator
    lifetime under task transfer (`memory-design-codex.md:488`).
25. **Compound updates to size facts** — C1 (`safety.py:327`). Any compile-time buffer
    sizing or reuse proof inherits it.

---

## 6. Open questions for the user brainstorm

1. **What does "as Jai, Odin and Zig" mean?** Those languages have *no* automatic memory
   management: explicit allocators, arenas and temporary storage, plus `defer` (Odin/Zig).
   Does L15 mean (a) "no runtime GC, like them", with the compiler inserting frees; (b)
   "allocator/arena-centred like them", with the compiler proving that arena lifetimes are
   respected; or (c) both? (Inference: the quote "something like garbage collection ... resolved compile-time" reads as (a)+(c).)
2. **Does user-visible `del` survive?** Remove it, keep it as an optional early release, or
   keep it only for arenas/pools (`reset`)? `examples/011_memory.a7:17` and `SPEC.md` §8
   change either way (approval rule applies).
3. **Is any runtime bookkeeping allowed?** Drop flags (one bit per conditionally-moved
   owner), reference counts for shared ownership, generation counters in handles. Or
   must everything be static, rejecting programs that need them?
4. **Unit of lifetime for DOD:** per-object ownership (affine/moves), per-region/arena
   (scope, frame, request, training step), or both with arenas as the default for bulk data?
5. **What happens when inference fails:** reject with a diagnostic (fail closed, as
   `SAFETY_CONTRACT.md:3-6`), require an annotation, or fall back to a runtime mechanism?
6. **Aliasing policy for `q := p`:** move, share, or error? And through struct fields and
   array elements?
7. **Borrowed vs owning refs:** should auto-`&` refs from `ref` params be statically
   non-escaping (reject `dangle_refparam.a7`)? Should the type system distinguish the two
   (no new keyword per L6 unless approved)?
8. **Linked and cyclic data:** fix self-referential `ref Node` fields as owning trees, or
   make index/generational handles (the `025`/`026` style) the blessed DOD graph idiom?
9. **Unions:** forbid owners in untagged unions; require tagged unions (G5) for any
   ref-carrying payload?
10. **Initialization:** adopt definite assignment (GLM §7.8) as part of L15, since automatic
    drop requires it?
11. **Stored function values** (G4): forbid storage, or allow with type-informed call-graph
    edges? This matters if summaries rely on the acyclic call graph.
12. **Allocation failure:** keep `new` → maybe-nil, or move to error results (G5)? How
    does automatic cleanup behave on partial construction?
13. **Allocator selection:** global `page_allocator` today (`zig.py:159`). An Odin-style
    implicit `context.allocator`, explicit allocator parameters (Zig), or
    compiler-chosen allocators (stack promotion, arena per scope)?
14. **Escape hatch:** is an `unsafe`/raw-allocator escape hatch acceptable (as in
    Jai/Odin/Zig), given `docs/lang-safety/README.md`'s "no unsafe escape hatch"?
15. **Ordering vs soundness repairs:** agree that MS-1, MS-2, C1-C4 (joins, call effects,
    binding identity) come before any L15 work, since an automatic model depends on them?
16. **Tensor memory:** should tensors (L9) be the first client of the region model (e.g.
    step-scoped arenas plus explicitly retained parameters and optimizer state)?
17. **Release posture (G9):** ReleaseSafe until L15 proofs are qualified?
18. **Does L15 resolve G2?** Record which G2 sub-decisions (`docs/plan/README.md:124-126`:
    storable reference fields, untagged-union access, uninitialized values, escaping slices,
    allocation failure) L15 settles and which stay open.

---

## 7. External references worth following up

Status: "repo-cited" = URL appears in `docs/plan/research/memory-design-codex.md:38-55`
(not re-fetched). "lead" = from my background knowledge; verify before relying on it.

Compile-time or low-runtime automatic memory:
- Koka / Perceus, garbage-free reference counting with reuse — repo-cited:
  https://www.microsoft.com/en-us/research/publication/perceus-garbage-free-reference-counting-with-reuse ,
  https://github.com/koka-lang/koka
- Regions: Tofte–Talpin 1997 — repo-cited: https://web.cs.ucla.edu/~palsberg/tba/papers/tofte-talpin-iandc97.pdf ;
  MLKit regions with tracing GC — https://elsman.com/mlkit/pdf/tagfreegc.pdf , https://elsman.com/mlkit/doc
- Hylo (formerly Val), mutable value semantics — repo-cited: https://hylo-lang.org/introduction/ ,
  https://arxiv.org/abs/2106.12678
- Vale, single ownership plus generational references and planned region borrowing — repo-cited: https://vale.dev/ (alpha; planned features are not evidence)
- Swift ownership: SE-0377, SE-0390, SE-0446 non-escapable — repo-cited (see codex:44)
- Rust Tree Borrows (PLDI 2025) — repo-cited: https://plf.inf.ethz.ch/research/pldi25-tree-borrows.html
- **Lead:** Nim ARC/ORC (compile-time-inserted destructors, moves, and cycle collector) —
  nim-lang.org docs "destructors" / "ARC/ORC" (verify current version).
- **Lead:** Lobster's compile-time reference-count elision / ownership analysis
  (Wouter van Oortmerssen) — strongest precedent for "GC-like, mostly compile-time".
- **Lead:** Mojo ASAP destruction (destroy at last use, not scope end).
- **Lead:** Cyclone regions (Grossman et al., PLDI 2002) — safe manual regions in a C-like language.
- **Lead:** ASAP memory management (Proust, 2017 thesis) — compile-time static deallocation.

Jai / Odin / Zig (the named style):
- Zig 0.16.0 language docs and release notes (allocators, `defer`/`errdefer`, "limited
  diagnostics for trivial returned local addresses" per codex:98) — repo-cited:
  https://ziglang.org/documentation/0.16.0/ , https://ziglang.org/download/0.16.0/release-notes.html
- Odin overview (context allocator, `temp_allocator`) and `core/mem/allocators.odin` — repo-cited:
  https://odin-lang.org/docs/overview/
- **Lead:** Jai — no authoritative spec (codex:55). Community sources on the temporary
  storage allocator and `context` push are the only material. Treat as anecdotal.
- **Lead:** Ryan Fleury, "Untangling Lifetimes: The Arena Allocator"; Andrew Kelley's
  "Practical DOD" talk; Mike Acton "Data-Oriented Design and C++" (CppCon 2014) — DOD
  memory idioms (arenas, SoA, handles).
- **Lead:** Generational indices / handles (e.g. "Handles are the better pointers", floooh
  blog 2018) — matches examples `025`/`026` and codex:157.

A7-internal follow-ups (not read in full here):
`docs/plan/research/memory-design-codex.md` (695 lines),
`docs/plan/research/memory-security-glm.md` (345),
`docs/plan/research/ownership-zig-odin-glm.md` (222),
`docs/lang-safety/parameter-modes.md`, `docs/lang-safety/edge-cases/`.

---

## Appendix: probe files (scratchpad, compile-only, not executed)

`/tmp/claude-1000/-home-cx89-Projects-pl-dev-a7-py/2f3ca81e-b15a-46d6-a619-792b7c49a803/scratchpad/probes/`

| Probe | Exit | Observation |
| --- | --- | --- |
| `leak.a7` | 0 | `new` without `del` accepted, no diagnostic |
| `refref.a7` | 0 | `ref ref i32 = nil` accepted |
| `retref.a7` | 0 | returning a `new` ref accepted |
| `structref.a7`, `structref2.a7`, `structref3.a7`, `structref_chain.a7` | 6 | self-referential `next: ref Node` → "ref unknown type" mismatches |
| `reffield_other.a7` | 0 | `Holder{p: a}`, `del a`, write through `h.p` → emitted UAF write |
| `store_refparam.a7`, `ret_refparam.a7` | 0 | auto-`&` ref stored in returned struct / returned directly (not dangling in these instances) |
| `dangle_refparam.a7` | 0 | `mk` returns `keep(&t)` of its own local → dangling stack address written in `main` |
| `fdiv.a7` | 6 | `f64` `0.0 / 0.0` rejected by integer divisor rule (L16 conflict) |
