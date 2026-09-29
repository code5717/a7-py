> **Source:** Claude Code audit subagent 5, plan consistency and implementation impact.  
> **Date:** 2026-09-15. Audit of docs/plan/memory.md revision 1.  
> **Status:** Advisory. Expected results are hand traces; probe results are compile-only unless stated. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

# Audit 5: consistency and implementation impact of `docs/plan/memory.md`

Date: 2026-09-15. Tree: `master` at 701c679 plus uncommitted docs/plan changes.
Auditor: Claude (Opus 5), read-only. No repository file was edited.

Evidence labels:

- **READ**: read from the named file and line.
- **A7-COMPILE**: `MISE_UV_VERSION=0.12.6 uv run a7 <probe> --format json --output <probe>.zig`; exit code recorded.
- **ZIG-COMPILE**: generated Zig checked with `/tmp/a7-audit-20260914/zig/zig build-obj -ODebug` (Zig 0.16.0). Semantic analysis only; nothing linked or run.
- **EXECUTED**: none. No probe binary was built or run.
- **HYPOTHESIS**: reasoning not checked by a probe.

Probe sources (`*.a7`) and generated Zig (`*.zig`) are in `.../scratchpad/audit/probes-5/`. The JSON dumps and Zig caches were deleted after the shared /tmp quota filled; exit codes and messages are recorded below.

---

## Part 1. Findings

### Blockers

**F1 (blocker). Runtime checks and M2 abort contradict the fail-closed safety contract.**
- memory.md:44-46 (contract 4) allows "index validity tests where they cannot be proven away".
- memory.md:159 (M2): "Ordinary values stop the program with a clear diagnostic".
- memory.md:195 (corpus 14): "Accept only with a proof or runtime check of distinct indices; decide".
- `docs/SAFETY_CONTRACT.md:3-6`: "A7 is safe only when the compiler can prove that generated code cannot trap ... if a risky operation has no proof, semantic analysis rejects the program before Zig code is emitted."
- `docs/lang-safety/README.md:19-26`: emitted Zig "remains memory-safe when compiled with `zig build -O ReleaseFast`".
- `docs/lang-safety/README.md:139-141`: "allocation failure, stack overflow — each is rejected statically or surfaced as a typed value the user must handle."

memory.md does not say it amends these rules. It also does not say what happens when an index-validity or distinct-index check fails: a trap, an optional, or a skipped operation. M5 answers this only for id lookups.

Today `new` failure is recoverable. `allocator.create(T) catch null` (`a7/backends/zig.py:1913`) returns nil, and `docs/SPEC.md:1035-1039` documents checking for it. M2 would change that to an abort, and the breaking-change table (memory.md:109-118) does not list it.

*Fix:* add a contract item "Runtime checks and failure". Name every residual check, its failure outcome, and whether that outcome is a defined A7 value or a process stop. Amend SAFETY_CONTRACT, or make every failure a typed value. Add a breaking-change row for OOM.

**F2 (blocker). Contract item 7 is contradicted by the corpus and gates.** memory.md:53-56 says user-visible rejections *are* exclusivity conflicts. Other rejection kinds in the plan:

| Source | What is rejected | Kind |
| --- | --- | --- |
| Corpus 7 (memory.md:188) | Returning a slice of a local list | Escape |
| Corpus 10 (memory.md:191) | Sending an index without its collection | Cross-task escape |
| Corpus 11 and M6 (memory.md:192) | Stored callback capturing a local | Capture |
| Corpus 12 (memory.md:193) | Kernel retaining a slice | Retention |
| M13 (memory.md:169) | Slices "cannot be stored or returned" | Escape |

`research/memory/synthesis.md:42-44` also rejects failed inference with a diagnostic that "names the allocation, the escape and a concrete rewrite". Item 7 excludes that rejection too.

*Fix:* make item 7 a closed list of rejection classes: exclusivity, view or id escape, stored-function capture, and native retention. State whether a placement failure can ever reach users.

**F3 (blocker). The id model is self-contradictory.**
- memory.md:75-77, M1 (memory.md:157) and the example (memory.md:84, 91-93) link records by plain `usize`.
- M5 (memory.md:161) requires "generation-tagged ids" and a lookup that "returns an optional".

A `usize` cannot carry a generation. A distinct id type (synthesis.md:69 `Handle<T>`) would be visible to users, and memory.md does not name one.

Corpus 4 (memory.md:185) removes nodes while holding parent indices, which leaves stale plain indices. The example also uses the root as its own parent (`add_child(tree, 0, 1)`, memory.md:98), despite "absence uses optionals" (memory.md:72).

*Fix:* choose one model, name the type, and use an optional parent in the example.

**F4 (blocker). "Shares storage until either side changes" needs runtime state the contract excludes.**
- memory.md:68-69 promises sharing "until either side changes", and the comment at 100 repeats it.
- memory.md:138-140: uniqueness is static; "Where it cannot be proven, the compiler copies rather than inserting counts."

A change on a runtime path needs a shared/unique bit or a count. Contract 1 bans counts, and contract 4 does not list a copy-on-write test. Without runtime state, the copy happens eagerly at `b := a`. That breaks the user model and is the "hidden copy" that synthesis.md:43 forbids.

Large-value copies in loops are only a warning (M8), which puts L15's predictability at risk.

*Fix:* reword as "copy elided when provably unobservable". Either add a runtime flag to contract 4 or state that no copy is deferred. Put the synthesis conflict to the user. Make M8's copy reporting part of the contract.

### Major

**F5 (major). Phase dependencies are missing or wrong.**
- Phase C (memory.md:242-247) needs optionals, `List`, `Map` and an owning `string`. Optionals depend on G5 (plan README:168-171). Collections are v1 track 8, which depends on tracks 6 and 7 (README:213). memory.md cites neither.
- memory.md does not link M2 to G5, the error type.
- The Phase D exit (memory.md:251-253) includes corpus 10 (worker/tasks), but tasks arrive in Phase F (memory.md:260-263) with G7 and v1 track 9.
- Corpus 14 is in no phase exit.
- Corpus 11 is in the Phase F exit, but no phase implements the M6/G4 restriction.
- The capacity-limited cache for corpus 1 has no phase.
- M5's generation ids have no phase.
- Layer 7 buffer planning "especially tensor steps" (memory.md:133) is scheduled in Phase E, before tensors exist (Phase F).
- Phase C removes `new`/`del` and migrates every example before placement exists (Phase D). That requires an undescribed interim lowering, and the Phase C exit demands Debug/ReleaseFast parity for it.

*Fix:* add a dependency column. Move corpus 10 to Phase F. Assign corpus 14, M5 and the cache to phases. Describe the interim Phase C lowering.

**F6 (major). Contract 6 ("no memory vocabulary") conflicts with M7, M8, M9, M12 and L17.**
- memory.md:51-52 bans the vocabulary.
- M9 (memory.md:165) introduces "extent" and "store".
- M8 (memory.md:164) adds a "memory report" and copy warnings.
- M12 (memory.md:168) requires a "declared owned handle" in source.
- M7 (memory.md:163) makes an explicit `close` optional, which is a user-chosen release point and touches contract 3.
- L17 (decisions.md:48): "This needs new language concepts". memory.md does not say which concepts satisfy L17.
- Current surface already uses the vocabulary: `docs/SPEC.md:2098` "E2xxx: Lifetime errors"; `a7/errors.py:240,291` "Delete requires a reference type"; plan README:249 "explicit saved-value lifetime".

*Fix:* scope item 6 to ordinary source, list the concepts users do see, and rename SPEC B.1 E2xxx.

**F7 (major). The breaking-change table (memory.md:109-118) is incomplete and partly wrong.** Probe details are in part 3.

Missing rows:
- `ref` return types and stored `ref` locals. `id :: fn(a: ref i32) ref i32 { ret a }` with `y := id(x)` compiles (p11: A7 0, Zig 0). memory.md:73-74 says `ref` parameters "cannot be stored or returned".
- Exclusivity rejections as new behavior. `both(x, x)` gives `both(&x, &x)` (p5: A7 0, Zig 0). `set2(arr[i], arr[j])` with `i == j` gives `&arr[i], &arr[j]` (p10c: A7 0, Zig 0).
- `nil` for function values: `docs/SPEC.md:192` `fn_ptr: ref fn() void = nil`, plus about 20 lines in `test/test_parser_extreme_edge_cases.py:533-912`.
- Stored function locals: `examples/022_function_pointers.a7:31` has `raw: fn(i32, i32) i32 = add`. M6 does not say whether locals count as stored.
- Slice `.ptr` (`docs/SPEC.md:275`); `string` as `struct { ptr: ref u8, len: usize }` (`docs/SPEC.md:288-291`); planned `mem_alloc`/`mem_free`/`mem_realloc` (`docs/SPEC.md:1644-1646`); `T` to `ref T` conversion (`docs/SPEC.md:2072`); `cast(ref i64, p)` (`test/test_semantic_types.py:711`); tensor `data: ref T` (`docs/SPEC.md:1096,1109`).
- Keyword status of `new`, `nil` and `del` (`docs/SPEC.md:98,101`; `a7/tokens.py:186,208`).
- Copy semantics of structs holding slices or strings. Today a copy shares storage; with an owning `string` it becomes a deep copy.
- OOM behavior (F1).

Wrong row: memory.md:113 says "Self-referential `ref` fields already fail to compile".
- Declaring `Node { value: i32  next: ref Node }`, `new Node`, writing `n.value` and `del n` compiles (p18: A7 0, Zig 0).
- Only assignment fails: `n.next = nil` gives "expected 'unknown type', got 'unknown type'" (p18b: A7 6).
- These passing tests expect success: `test/test_semantic_comprehensive.py:853-874` and `test/test_semantic_generics.py:553-565`.

Imprecise row: memory.md:115. `string` lowers to `[]const u8` (p2), but A7 rejects `[]u8` into a `string` field (p19: "expected 'string', got '[]u8'"). `docs/SPEC.md:284-285` says string slices are `[]char`.

**F8 (major). The summary overstates current value semantics.** memory.md:17-22 says "Plain structs and arrays are already values." Probes show otherwise:
- **p1b** (A7 0, Zig 0): `const s1 = arr[0..4]; var s2 = s1; s2[0] = 9;` The slice copy shares `arr`, by Zig semantics; not executed.
- **p3b** (A7 0): a struct holding a slice copies only the header.
- **p20** (A7 0, Zig 0): views of a mutable buffer alias it.
- **p4** (A7 0, Zig 0): an array parameter copied in the callee is independent.
- **p4b** (A7 0, Zig 1 "cannot assign to constant"): A7 accepts `a[0] = 7` on a by-value array parameter, contrary to `docs/SPEC.md:761-770`.

*Fix:* qualify the claim to structs and arrays without slice, string or `ref` members, and list the p4b gap as a defect.

**F9 (major). The v1 plan and ledger are not reconciled.** Lines are listed in part 2.
- G7 and G8 still depend on G2, which is superseded.
- Track 6 still reads "ownership surface, deletion".
- Track 8 owns the collections that Phase C needs.
- The ledger's pending records cover only G1-G8.
- M4 re-proposes D.049 "no storable references", which the ledger records as "Not accepted" (decisions.md:90).

**F10 (major). Some architecture premises are unproven.**
- memory.md:141-142 claims an acyclic call graph and computable stack depth. But M6 allows callback arguments, `docs/SPEC.md:722-724` rejects only "common indirect cycles", and G4 is open. Depth may be computable, but stack bytes are not once dynamic values are placed on the stack.
- memory.md:145 assumes whole-program compilation. File imports are partial (`docs/STATUS.md:30-32`), and native kernels (L9, track 10) compile separately.
- memory.md:143-144 treats structure-of-arrays as legal. But `ref` element arguments take addresses (`&arr[i]`, p10c), and M13 slices of `List(Record)` assume contiguous records. SoA needs write-back or restrictions for both, and memory.md lists neither.

**F11 (major). Contract 5 conflicts with corpus 1, and "leak" is undefined.**
- memory.md:47-50 allows retention until the process extent ends.
- Corpus 1 expects "memory flat" (memory.md:182).
- Corpus 13 accepts an unbounded global table.
- memory-brainstorm.md:34-35 promises the compiler "never silently leaks".

Nothing forbids placing loop temporaries in a longer extent.

*Fix:* guarantee release at the end of the iteration for values unreachable after it. Define "leak", "pause" and "bounded".

**F12 (major). Current defects that block the foundations are not recorded.** memory.md:231 cites only notes H. New findings:
- **`del` lowering breaks on a variable named `p`.** `if (x) |p| allocator.destroy(p)` (`zig.py:1306,2390`) triggers Zig "capture 'p' shadows local constant" (p7, p12: A7 0, Zig 1). A7 accepts code that Zig rejects.
- **`del` on a `ref` parameter frees a stack slot.** It emits `allocator.destroy(&x)` (p16: A7 0, Zig 0). An invalid free accepted at both levels; not executed.
- **A returned slice of a mutable local dangles** and is accepted at both levels (p6c). With a const local, Zig rejects the `*const [3]i32` to `[]i32` coercion (p6b, p14: Zig 1).
- **A mutable global `counter := 0` emits `var counter = 0;`,** which Zig rejects as comptime_int (p17: Zig 1). This affects corpus 13.
- **Printing a `ref` parameter emits `{any}` of the pointer** (p5 generated Zig). HYPOTHESIS: prints an address.
- **`swap` cannot be written today.** `ref i32` in arithmetic is rejected with "Requires numeric type" (p10b). The SPEC `swap` (`docs/SPEC.md:698-702`) is rejected with "Cannot assign to immutable binding" (p10). Corpus 14 has no current equivalent.
- **Fact tracking is shallow.**
  - `moved_symbols` is set only by `del` and is keyed by name (`a7/safety.py:236,387-389,724-726`); `ValueFact.moved` is never set. There is no move on assignment.
  - `if` restores facts after the then-branch and does not join branches (`safety.py:343-351`).
  - `match` has no save or restore (`safety.py:373-379`).
  - `defer del` does not mark the binding deleted (`safety.py:380-384`).
  - Only identifiers are tracked, so `del h.b` and `del arr[i]` are not.

### Minor

**F13 (minor). Example details.** The section 2 example otherwise follows the rules: no recursion, no `&` or `*`, `usize` indices, and `List(Node){}` matches `docs/SPEC.md:916`. Remaining issues:
- `copy := tree` is unused, so it demonstrates nothing.
- `tree.nodes.append` assumes stdlib methods; `docs/SPEC.md:806-831` has user methods only.
- `len - 1` relies on L5 wrapping without citing G3 checked size arithmetic.

**F14 (minor). The evidence rule versus the test-plan rule.** memory.md:275-276 requires native execution. Plan README:275-277 keeps corruption fixtures compile-only. Corpus 14 and M5 need executed failure paths, which is allowed only if F1 defines the outcome. Corpus 2 and 7 are rejections, so their Phase C exit is compile-only.

**F15 (minor).** "extent" is used (memory.md:47, 130) before M9 defines it. Task and training-step extents refer to features that don't exist yet. The assumption that L19 overrides L17 is not recorded.

**F16 (minor).** memory.md:118 says heap-array impact is "None", but `test/test_semantic_types.py:446-454` asserts the text "heap arrays" (`type_checker.py:3015`). Removing `new` changes that diagnostic and its test.

**F17 (minor).** The `scripts/error_stage_common.py:161-164` fixture (`defer del x`) expects exit 6 (semantic). Removing `del` from the grammar makes it exit 5 (parse).

---

## Part 2. Statements that must change if memory.md is approved

### docs/SPEC.md
| Line | Current text |
| --- | --- |
| 40 | "**Manual memory management** with safety features" |
| 49 | "**Explicit over implicit**: No hidden allocations or conversions" |
| 98, 101 | keywords `del`, `new`, `nil` |
| 185 | "`nil` can **only** be used with reference/pointer types (`ref T`). It represents a null pointer." |
| 190-193 | `ptr: ref i32 = nil`, `fn_ptr: ref fn() void = nil`, `if ptr == nil { }` |
| 217-218 | "Value types: Copied by value" / "Reference types: Point to memory locations" |
| 272-276 | "Dynamic view into array"; "`slice.ptr` // Pointer to first element" |
| 280-291 | "String is equivalent to `struct { ptr: ref u8  len: usize }`" |
| 294-303 | "References (Pointers)": `ref i32`, `ref ref i32`, `ref fn(...)` |
| 380-401 | Reference Semantics |
| 698-702, 876 | `swap` over `ref` parameters (already rejected, p10) |
| 761-763 | "`ref` parameters can mutate the caller's storage, but the reference binding itself is compiler-managed" |
| 992-1079 | Section 8: "All local variables are stack-allocated by default", `new Box`, `del box`, "Check allocation", `defer del point`, "`new` and `del` parse, type-check, and lower" |
| 1096, 1109 | tensor `data: ref T` |
| 1644-1646 | `mem_alloc`, `mem_free`, `mem_realloc` |
| 1662, 1676, 1694-1698 | `TOKEN_NIL_LITERAL`, `TOKEN_DEL`, `TOKEN_NEW`, `TOKEN_NIL`, `TOKEN_REF` |
| 1792, 1972 | `AST_TYPE_POINTER // ref T`; grammar `\| "ref" type` |
| 2072 | "`T` to `ref T` in function calls" |
| 2085-2088 | "Heap values live until explicit `del`"; "References must not outlive referent"; "Slices must not outlive backing array" |
| 2098 | "**E2xxx**: Lifetime errors" |
| 2202-2204 | "Basic `new`/`del` validation and direct use-after-`del` rejection exist" |

### docs/SAFETY_CONTRACT.md
| Line | Current text |
| --- | --- |
| 3-6 | "cannot trap ... rejects the program before Zig code is emitted" |
| 18 | "invalid `del`" |
| 34-35 | "nil/non-nil reference state"; "initialized, moved, and deleted bindings" |
| 51-53 | "Ref field access or dereference"; "Use after `del`" |
| 57-60 | "enforces ... ref deref ... and direct use-after-`del` checks" |
| 69-78 | "`ref T` remains the nullable heap-reference surface"; planned "optional `ref T`", "`nil`: assignable only to optional refs", "`new T`: returns an optional ref" |
| 82-91 | "heap refs created by `new` must be cleaned up with `del` or `defer del`"; "implicit deep copy is not provided"; "make heap refs affine ... explicit stdlib `clone`" |

### docs/STATUS.md
| Line | Current text |
| --- | --- |
| 23-24 | Priority 4: "Split safety proofing into internal CFG, fact, obligation ..." |
| 33-34 | "full ref/del alias behavior, and ownership/lifetime guarantees are incomplete" |
| 38-39 | "`Option`, `Result`, collections, and fuller string/memory helpers are planned" |
| 43-44 | Deferred tensor and concurrency tracks (already superseded, decisions.md:80) |

### README.md
| Line | Current text |
| --- | --- |
| 12 | "Odin ... Simplicity and explicit memory management" |
| 136 | "reference dereferences, and direct use after `del`" |
| 144 | "allocation byte counts" |
| 157-160 | "ref struct fields are accessed directly after nil-proofing, and scalar/struct `new` plus `del` support defer cleanup. Heap fixed arrays (`new [N]T`) are rejected ..." |
| 161-163 | "reference dereferences ... direct use after `del` are checked" |

### docs/CHANGELOG.md
- 23-24: "ref dereferences, and direct use after `del`". Historical; add a new entry instead of editing.

### CLAUDE.md and AGENTS.md
| File:line | Current text |
| --- | --- |
| CLAUDE.md:15-16 | "there is no separate runtime" (memory.md needs allocator and check runtime code; L9 "A7 runtime") |
| CLAUDE.md:128-130, AGENTS.md:72-74 | "`new [N]T` (heap fixed arrays) is currently rejected by the compiler" |
| CLAUDE.md:131-134, AGENTS.md:75-78 | "pass lvalues directly to `ref` parameters and use ordinary field access after nil checks" |

### Public site and research contract
| File:line | Current text |
| --- | --- |
| site/public/docs/language.md:72 | "References with nil checks" |
| site/public/docs/language.md:96-98 | "`new [N]T` is rejected"; "Pass lvalues directly to `ref` parameters." |
| site/public/docs/compiler.md:65-66 | "nil reference use"; "direct use after `del`" |
| site/public/docs/status.md:33, 37 | "full ref/del alias"; "fuller string/memory helpers" |
| site/public/llms-full.txt:222, 246-248, 369-370, 411, 415 | Mirrors of the above |
| docs/lang-safety/README.md:19-26, 139-141 | ReleaseFast contract; "allocation failure ... rejected statically or surfaced as a typed value" |

### Plan documents
| File:line | Current text | Reason |
| --- | --- | --- |
| docs/plan/README.md:44-45 | "no `new [N]T`" | Moot |
| docs/plan/README.md:128-130 | G2 sub-decisions: "storable reference fields ... escaping slices and allocation failure" | Map to M4, M13, M2 |
| docs/plan/README.md:185 | G7 "depends on G2 and G5" | Point to M10 |
| docs/plan/README.md:193 | G8 "depends on G1 and G2" | Point to M11 |
| docs/plan/README.md:197-198 | G9 "ReleaseSafe until memory-model work lands" | Link M2 and phases |
| docs/plan/README.md:211 | Track 6 "Approved ownership surface, deletion, defer, provenance" | Internal ownership, no deletion |
| docs/plan/README.md:213-216 | Tracks 8, 9, 10 dependencies | Phases C, D, F need them |
| docs/plan/README.md:249 | "explicit saved-value lifetime" | F6 |
| docs/plan/README.md:275-277 | "Memory-corruption fixtures are compile-time rejection checks" | F14 |
| docs/plan/decisions.md:48 | L17 "This needs new language concepts" | F6 |
| docs/plan/decisions.md:90 | D.049 "no storable references" marked "Not accepted" | M4 reverses it |
| docs/plan/decisions.md:97-98 | "open gates G1–G8" | Add M1-M13 and G9 |
| research/memory/synthesis.md:42-44 | "no silent promotion to a longer lifetime, no hidden copy" | Contradicts memory.md:138-140 |
| research/memory/synthesis.md:89-92 | "G2 keeps affine `del` ... unreconciled" | Resolved by memory.md |
| docs/plan/memory-brainstorm.md:34-35 | "never silently leaks or frees early" | F11 |

Historical research needs "superseded" markers, not rewrites (the pattern at decisions.md:73-93):
- `docs/lang-safety/08-decisions.md` (39 matching lines)
- `HANDOFF.md` (7)
- `parameter-modes.md` (12)
- `edge-cases/02-nullable-pointers.md` (13)
- `edge-cases/10-affine-ownership.md` (4)
- `docs/audits/2026-09-14/*`

---

## Part 3. Probe results (compile-only; none executed)

| Probe | A7 | Zig | Result |
| --- | --- | --- | --- |
| p1 slice copy, const backing | 0 | 1 | "cannot assign to constant" on `s2[0] = 9`; A7 accepts a write through a view of an immutable array |
| p1b slice copy, mutable backing | 0 | 0 | `const s1 = arr[0..4]; var s2 = s1; s2[0] = 9;` Shares `arr` |
| p2 string assignment | 0 | 0 | `const b = a` header copy; `a[1..4]` view |
| p3 struct slice mutated via copy | 6 | – | Index proof fails on `h2.items[0]`; no length fact through fields |
| p3b struct slice copy | 0 | 1 | `const h2 = h` header copy; Zig const-coercion defect |
| p4 array by value, callee copy | 0 | 0 | Independent |
| p4b array by value, direct write | 0 | 1 | A7 immutability gap |
| p5 `both(x, x)` | 0 | 0 | `both(&x, &x)`; `{any}` pointer print |
| p6 return local slice, then index | 6 | – | Rejected only by the index proof |
| p6b return const local slice | 0 | 1 | Zig const error, not escape |
| p6c return mutable local slice | 0 | 0 | **Dangling slice accepted** |
| p7 `ref` field copy, then `del` | 0 | 1 | Capture `p` shadows local |
| p8 `for i: usize = 0; ...` | 5 | – | Typed for-init form unsupported (probe authoring) |
| p8b `defer del` in `while` | 0 | 0 | Per-iteration Zig `defer` |
| p9 struct with array field copy | 0 | 0 | Independent |
| p10 SPEC `swap` | 6 | – | "Cannot assign to immutable binding" |
| p10b swap with `a + 0` | 6 | – | "Requires numeric type" |
| p10c `set2(arr[i], arr[j])`, `i == j` | 0 | 0 | Element alias accepted |
| p11 `ref` returned and stored | 0 | 0 | `fn id(a: ?*i32) ?*i32` |
| p12 `q := p; del p; del q` | 0 | 1 | Double destroy emitted; Zig fails only on shadowing |
| p13 struct `ref` field from local | 6 | – | "expected 'ref i32', got 'i32'" |
| p14 struct with local slice returned | 0 | 1 | Zig const error; would dangle with `var` |
| p15 `string` returned | 0 | 0 | Header pass-through |
| p16 `del` on `ref` parameter | 0 | 0 | **`allocator.destroy(&x)` of a stack slot** |
| p17 mutable global | 0 | 1 | comptime_int `var` |
| p18 self-referential `ref` field, `new`, `del` | 0 | 0 | Compiles |
| p18b `n.next = nil` | 6 | – | "expected 'unknown type'" |
| p19 `[]u8` into `string` field | 6 | – | Type mismatch |
| p20 views of a mutable buffer | 0 | 0 | Aliasing views |

Code facts (READ):
- **Allocation.** A global `std.heap.page_allocator` is emitted when `new` or `del` appears (`zig.py:133-134,158-159`). `new T` lowers to `allocator.create(T) catch null` (`zig.py:1903-1914`). `del` lowers to `if (x) |p| allocator.destroy(p);` (`zig.py:1300-1306`; defer form at `2386-2390`).
- **References.** `ref T` lowers to `?*T`, dereferenced with `.?.*` (`zig.py:1728-1747`). `ref` arguments get an automatic `&` and force `var` storage (`test/test_ast_preprocessor.py:545`).
- **Defer.** A direct Zig `defer` (`zig.py:1272-1296`). There is no automatic cleanup.
- **Moves.** None exist; only the `del` name set (`safety.py:236,724-726`). Facts are keyed by name (`safety.py:150-176`), approvals by `id(node)` (`safety.py:199-213`). There is no CFG and calls do not invalidate facts.
- **Stdlib.** `a7/stdlib/mem.py` and `string.py` are empty stubs. There is no arena, pool, list, map or clone.
- **Build profiles.** Debug and ReleaseFast (`scripts/build_examples.py:22,25`).

---

## Part 4. Implementation impact inventory

### 4.1 Compiler modules
| Module | Lines |
| --- | --- |
| a7/tokens.py | 27, 41-42, 63-64, 68, 145, 186-187, 208-213, 801-802 |
| a7/parser.py | 34-35, 525, 588, 743-748, 1011-1015, 1457, 1470-1471, 1484, 1590, 1619, 1638-1639, 1782-1798, 2182, 2275, 2284-2288 |
| a7/ast_nodes.py | 33, 50, 56, 99, 214, 381, 395-402, 603-604 |
| a7/types.py | 17, 64-65, 192-207, 212-223 |
| a7/passes/type_checker.py | 16, 391-418, 456, 662-736, 823, 840-854, 1081-1086, 1142-1155, 1175-1176, 1384-1386, 1568, 1604, 1634-1673, 1772-1795, 1847, 1856-1873, 2517-2518, 2875-2901, 3005-3045 |
| a7/passes/semantic_validator.py | 7, 221-222, 351, 384-395, 451-453, 478-479, 483-500, 631, 936, 1130, 1371-1384 |
| a7/safety.py | 37-38, 77-79, 141-145, 182, 190, 236-247, 316-328, 380-389, 398-399, 427-453, 477-494, 599-600, 610-629, 691-702, 724-737 |
| a7/ast_preprocessor.py | 38, 188, 318-319, plus `ref` argument mutation analysis |
| a7/backends/zig.py | 14, 23, 58, 133-134, 158-159, 228-229, 372, 464-476, 565, 650, 1272-1306, 1315-1317, 1448-1461, 1500, 1715-1747, 1903-1914, 1992-2023, 2100, 2138, 2386-2390 |
| a7/errors.py | 78-79, 118, 134-141, 240-241, 291-292, 332, 349-355, 392, 409-415 |
| a7/formatters/console_formatter.py | 492-509, 652 |
| a7/formatters/json_formatter.py | 188 |
| a7/stdlib/mem.py, string.py | Stubs to replace with `List`, `Map` and owning `string` |

Total: 12 modules with direct hits, about 330 matched lines by a broad regex (type_checker 88, safety 74, zig 68, errors 36, parser 28, semantic_validator 24, types 16, ast_nodes 15, tokens 10, console 5, preprocessor 4, json 1). `name_resolution.py`, `module_resolver.py` and `generics.py` have no direct hits.

### 4.2 Examples
| Example:line | Construct |
| --- | --- |
| 011_memory.a7:12-17 | `new`, `== nil`, `defer del` |
| 013_pointers.a7:5 | `ref i32` parameter |
| 017_methods.a7:9 | `ref Counter` |
| 019_literals.a7:13, 20 | `n: ref i32 = nil`; golden output 019_literals.out |
| 022_function_pointers.a7:5-6, 20, 24, 31 | Function types; stored local function value (M6) |
| 025_linked_list.a7:7, 17, 20 | `isize` index, `-1` sentinel |
| 026_binary_tree.a7:7-8, 42 | `usize` links, sentinel 3 |
| 027_callbacks.a7:5, 19-21 | Callback argument |
| 034_string_utils.a7:29 | String view |
| 036_control_flow_edges.a7:9 | Slice view |
| 037_language_tour.a7:12, 37, 45, 64, 118-123 | Function type, `ref`, callback, slice, `new`/nil/`defer del` |
| 038:16, 040:12, 040:16, 041:17, 042:25 | `ref` struct parameters |
| 039_text_analyzer.a7:33-34 | String views |
| `string` users | 002, 004, 009, 014, 015, 019, 027, 034, 037, 038, 039, 040, 042 |

By construct:
- `new`/`defer del`: 2 examples
- `nil`: 1
- `ref` parameters: 7
- Views: 6
- `string`: 13
- Stored function value: 1
- Index-linked structures: 2

### 4.3 Tests
Lines using `new`/`del`/`nil`/`ref` in A7 snippets, 26 files:

| File | Lines |
| --- | --- |
| test_parser_extreme_edge_cases | 44 |
| test_parser_combinatorial | 31 |
| test_parser_type_combinations | 29 |
| test_parser_creative_cases | 26 |
| test_semantic_types | 19 |
| test_semantic_comprehensive | 16 |
| test_parser_comprehensive_problems | 14 |
| test_parser_advanced_edge_cases | 9 |
| test_cast_safety_matrix | 9 |
| test_parser_missing_constructs | 7 |
| test_parser_integration | 7 |
| test_semantic_errors | 6 |
| test_tokenizer_aggressive | 5 |
| test_codegen_zig | 5 |
| test_semantic_expressions | 4 |
| test_semantic_control_flow | 3 |
| test_parser_stress_tests | 3 |
| test_parser_edge_cases | 3 |
| test_parser_basic | 2 |
| test_tokenizer | 2 |
| test_semantic_generics | 2 |
| test_semantic_functions | 2 |
| test_parser_fuzzing | 2 |
| test_parser_error_handling_improvements | 2 |
| test_ast_preprocessor | 2 |
| test_parser_examples | 1 |

Behavior tests that will flip:

| File:lines | What it asserts |
| --- | --- |
| test_cast_safety_matrix.py:266-293 | Use-after-`del` rejection and reinitialization |
| test_codegen_zig.py:418, 624 | `ref` parameter lowering |
| test_codegen_zig.py:747 | `nil` ref |
| test_codegen_zig.py:864-872 | `allocator`/`create`/`destroy` |
| test_semantic_types.py:446-454, 476-544, 710-711 | Heap arrays; ref and nil typing; `cast(ref)` |
| test_semantic_errors.py:294-310 | nil and `del` on non-references |
| test_semantic_control_flow.py:1273-1333 | `defer del` |
| test_semantic_comprehensive.py:349-389, 745-758, 853-874 | ref/nil, new/del, linked list |
| test_semantic_generics.py:154, 553-565 | `ref Box($T)`, `ref Node($T)` |
| test_parser_comprehensive_problems.py:437-493 | new/del parsing |
| test_ast_preprocessor.py:545-547 | `ref` forces `var` |
| test_tokenizer.py:439, 498; test_tokenizer_aggressive.py:407, 473-477, 507-517 | Token-level `nil` and `ref` |
| test_parser_creative_cases.py:316-329, 909-990 | Pool snippet, new/del |
| test_examples_e2e.py plus golden outputs for 011, 019, 037 | Example output |

Proxy count: `pytest --collect-only -k "new or del or nil or ref or defer or pointer or deref or memory or heap or slice or string"` selects **364 of 2527** tests. This matches by name, so it is an upper bound.

Scripts: `scripts/error_stage_common.py:161-164`, used by `scripts/verify_error_stages.py` and `test/test_error_stage_matrix.py`. The untracked `test/test_pipeline_*.py` files have no hits.

### 4.4 Docs code blocks (lines matching `new`/`del`/`defer del`/`nil`)

| File | Lines |
| --- | --- |
| audits/2026-09-14/memory-safety-glm-review.md | 42 |
| lang-safety/08-decisions.md | 39 |
| research/memory/notes-h | 33 |
| SPEC.md | 26 |
| research/memory-design-codex | 18 |
| research/memory-security-glm | 17 |
| research/memory/notes-c | 13 |
| lang-safety/edge-cases/02-nullable-pointers | 13 |
| lang-safety/parameter-modes | 12 |
| research/memory/advice-grok | 11 |
| research/memory/advice-fable | 11 |
| SAFETY_CONTRACT | 9 |
| lang-safety/compile-time-knowledge | 8 |
| lang-safety/HANDOFF | 7 |
| About 30 further files | 1-6 each |

Normative files that must change: SPEC, SAFETY_CONTRACT, STATUS, README, `site/public/docs/{language,compiler,status}.md`, `llms-full.txt`, CLAUDE.md and AGENTS.md.

---

## Part 5. Missing edge-case categories and phases

1. **Deterministic placement as a contract guarantee**, not only an audit topic. Facts use `id(node)` keys and Python sets (`safety.py:236`).
2. **Compile-time cost budget.** Every new analysis must also keep the recursion-limit-100 iterative invariant (CLAUDE.md:42-49, `test/test_iterative_traversal.py:228-229`).
3. **Migration.** No deprecation window, no coexistence of `new`/`del` and `List` in Phase C, no migration diagnostics or tooling, and no approval ordering. Scale: about 364 tests, 13+ examples and 10 public docs.
4. **Debugging and profiling placement.** Debugger view of SoA records, stack traces for arena values, AST/semantic JSON exposure of extents, and the memory-report schema.
5. **Zig version dependence.** Allocator and `std.Io` APIs change between Zig releases, and there is no lowering-abstraction layer or upgrade test.
6. **Platform stack limits.** Thread and task stacks, per-OS defaults, and rules for demoting a large value to an extent.
7. **Debug versus ReleaseFast.** Checks must be A7-emitted code, not Zig safety checks, which ReleaseFast removes.
8. **Allocator choice and thread safety with tasks.** Alignment for f16/bf16 buffers. Today `page_allocator` is used per object.
9. **Checked size arithmetic** for `List` growth. L5 excludes this (decisions.md:55-57); link it to G3.
10. **Tooling surface.** `--mode doc`, console formatter NEW_EXPR, error-stage categories, `project_status.py` counts, site search.
11. **Semantics of owning values:** deep `==`, `Map` hashing of owning strings, whether `for-in` yields copies or views, mutation during iteration.
12. **Failure during automatic release or `defer`.** Ordering of resource release against `defer` LIFO.
13. **Separate compilation** of A7 modules and native libraries, versus the whole-program assumption.
14. **Size bound on storage plans per generic instantiation.**
15. **Threat model for hostile native code (M12)**, beyond "declared owned handle".

---

## Part 6. Evidence plan: falsifying test per guarantee

| # | Guarantee | Falsifying test | Feasible today |
| --- | --- | --- | --- |
| 1 | No GC, counts or pauses | Scan emitted Zig for counts; latency histogram around large extent releases | Scan yes. Latency no; "pause" undefined |
| 2 | No use after free, double free or dangling reference | (a) Compile-rejection corpus: p6c, p12, p14 var variant, p16, notes-H `dangle_refparam`. (b) Benign accepted programs under Zig DebugAllocator leak and double-free detection, with ReleaseFast parity | (a) Yes; all accepted today. (b) Harness feasible; detector unnamed in memory.md |
| 3 | Static release points | Each emitted free or reset maps to a BackendPlan release op | No; no release ops exist. After Phase B |
| 4 | Bounded deterministic runtime work | Counting allocator; identical counts across runs of the same shape | Partly, for `new`; "bounded" undefined |
| 5 | Storage returned at extent end | DebugAllocator reports no leak at exit; RSS at N versus 10N iterations | Exit leak check yes (011, 037). Loop flatness no |
| 6 | No memory vocabulary | Lint over diagnostics, stdlib names and docs | Yes; fails today (`errors.py:240,291`, SPEC:2098) |
| 7 | Rejections are exclusivity conflicts | Classify every corpus rejection | Yes; already falsified by corpus 7, 10, 11, 12 |
| 8 | Iterative destruction | Release a 10^6-deep structure on a 64 KiB thread stack; static acyclicity check of emitted deinit | After `List` exists |
| – | L19 metric | Rewrites needed beyond `new`/`del` deletion, with a threshold fixed before measuring | Metric and threshold undefined |
| – | Phase E reuse | Allocation-count and peak-RSS ratio against arena/pool Zig baselines | No acceptance ratio; baseline author bias |
| – | Phase G layout | Same stdout and exit with and without SoA, in Debug and ReleaseFast | After layer 8 |

Gaps:
- Corpus "expected results" come from the design itself. L13 needs independently derived results.
- Rejection exits are compile-only.
- Measurements need toolchain and tool pins (README:265-266).

---

## Part 7. Proposed memory.md fixes (checklist)

1. **Contract.**
   - Add "runtime checks and failure" (F1).
   - Make item 7 a closed list of rejection classes (F2).
   - Add deterministic placement and release at iteration end.
   - Define leak, pause and bounded (F11).
   - Scope item 6 to ordinary source and list the visible concepts (F6).
2. **Section 2.**
   - Reword copy elision (F4).
   - Choose the id type; use an optional parent (F3).
   - Make `copy` observable (F13).
3. **Summary.** Qualify "already values" and add the p1b, p3b, p20 and p4b facts (F8).
4. **Breaking changes.**
   - Fix row 113 (p18, p18b).
   - Add rows: `ref` returns and stored locals, exclusivity, function `nil` and stored function locals, `.ptr`, `string` struct, `mem_*`, `T`→`ref T`, `cast(ref)`, keywords, struct-with-slice copies, OOM (F7).
5. **Architecture.** Qualify the acyclic graph and stack claims, whole-program compilation, and SoA constraints (F10).
6. **Gates.** Link optionals and M2 to G5. Define M6's scope. Record the D.049 reversal.
7. **Phases.**
   - Add a dependency column.
   - Move corpus 10 to Phase F.
   - Assign corpus 14, M5 and the cache.
   - Describe the interim Phase C lowering.
   - Add a migration sub-phase.
   - List F12 defects as Phase B entry work (F5).
8. **Evidence.**
   - Use independent expected results.
   - Adopt the part 6 falsifiers.
   - Label rejection exits compile-only.
   - Name the leak and double-free detector.
   - Pin the measurement toolchain (F14).
9. **Cross-document.** Register M1-M13 in the ledger, and update plan README G7/G8/G9 and tracks 6/8/9/10 (F9).
