# Cross-feature interactions

Companion to `evidence-map.md`. Same citation shorthand: report names resolve
under `docs/audits/2026-09-16/compiler/`, `EXEC:` = `docs/plan/execution.md`,
`PEND:` = `tmp/packets/pending-items.md`, `LEDG1/2:` =
`docs/plan/audit/evidence/2026-09-16-ledger-part1.md` / `-part2.md`,
`P0b:` = `docs/plan/packets/P0b-unsafe-programs.md`.

## 1. Interactions a finding or pending item already records

| Interaction | What breaks | Source |
| --- | --- | --- |
| `defer` x assignment facts | A deferred assignment is applied at the `defer` site, so `10 / x` is approved after `defer x = 0` | SAF-25 `safety.md:311`; C4 closed the snapshot half (`EXEC:119`) |
| `defer` x block and branch exit | `x := 5; { defer { x = 0 } }; 10 / x` and the `if c { defer { x = 0 } }` form build and divide by zero at run time | `PEND:2` |
| `defer` x `del` x deleted-variable state | `del b; defer { b = new Box }; b.value` builds and reads freed memory; `defer { del b }; b.value` is wrongly rejected | `PEND:3`; P0b.8 `P0b:215-235`; KNOWN S10/A-30 `LEDG2:46` |
| `defer` x non-void call | `defer f()` with a non-void `f` is emitted without a discard; Zig rejects | ZIG-16 `backend.md:67` |
| `defer` x `ret`/`break`/nested `defer` | The parser accepts them inside `defer`; the validator accepts control flow in `defer` | PAR-20 `parser.md:455`; TYP-23 `types.md:482` |
| `for`-in x shadowing | The loop value variable keeps the outer variable's fact, so a divisor proof survives the rebinding | SAF-24 `safety.md:342`; ordering note "C4 lands before Z1 and Z4" `EXEC:122` |
| `for`-in capture x codegen names | Unused and shadowed loop captures emit invalid Zig (2 of the 12 failing baseline tests) | `docs/audits/2026-09-16/baseline.md:52-53`; PIP root causes 10-11 `pipeline.md:89-90` |
| `::` constants x shadowing | `::` constants are not renamed when they shadow; and file-scope constant facts are discarded at every function entry | SAF-32 `safety.md:547`; SAF-21 `safety.md:423` |
| `char`/`bool` x compound vs binary operators | `c += d` and `a &= b` are accepted (Zig builds them) while `c + d` and `a & b` are rejected | `PEND:1` |
| `match` x `fall` x facts | Match statements neither scope nor join facts, and `fall` carries state the pass never sees | SAF-3 `safety.md:107` |
| `match` expression x later scopes | A match expression consumes the scope a later match statement expects | PIP-5 `pipeline.md:183` |
| `else if` x scopes | Name resolution and the type checker disagree on scope order, so valid programs are rejected and invalid ones accepted | PIP-4 `pipeline.md:158` |
| `match` capture x any visible symbol | A capture named like a global, function or later local compares instead of capturing | PIP-21 `pipeline.md:432`; TYP-30 `types.md:552`; KNOWN A-32 `PLAN:483-484` |
| `match` x tagged union | `case ok` captures the whole union instead of testing the tag | KNOWN B2 `LEDG1:74`; `PLAN:386-388` |
| Local shadowing x module alias | A local that shadows a file-module alias has its call rewritten to the module function (miscompile) | PIP-1 `pipeline.md:95`; now covered by `test/test_module_alias_shadowing.py:103-150` (PL-02) |
| Local or struct named `io`/`math` x stdlib lowering | A value named `io` prints to stdout; a user function named `sqrt_f64` becomes a Zig builtin; a struct named `math` calls `@sqrt` | PIP-3 `pipeline.md:141`, ZIG-5 `backend.md:199`, PIP-2 `pipeline.md:122`, SAF-9 `safety.md:227`, KNOWN B14 `LEDG1:86` |
| if-expression x surrounding operator | The if-expression was emitted without parentheses, so `(if c {a} else {b}) + 10` bound wrongly | ZIG-2 `backend.md:126`; fixed by C3 (`EXEC:113`), test `test/test_zig_backend_runtime.py:137` |
| if/match expression x literal arms x runtime condition | Zig rejects the emitted `comptime_int` switch or if | ZIG-41 `backend.md:85`; ZIG-12 `backend.md:63` |
| Constant folding x type map identity | A folded literal inherits a dead node's type through `id()` reuse and prints the wrong value | SAF-7 `safety.md:181` = ZIG-1 `backend.md:95` |
| Folding x declared type x casts | Folded integer results are not checked against the declared type; negative float literals cannot be cast | SAF-14 `safety.md:381`; SAF-28 `safety.md:478` |
| Forward reference x type checking order | A symbol read before its declaration is `UnknownType`, which is assignable to everything | TYP-01 `types.md:42` |
| Recursion ban x function values and aliases | Callback trampolines, struct-field function pointers and module-qualified calls bypass the ban | TYP-02 `types.md:94`; MS-7 `docs/audits/2026-09-14/memory-safety-glm-review.md:346` |
| Recursion ban x parameter alias x same-named top-level function | `h := g; h(n)` with a top-level `g` links the call graph to `g` and reports a false recursion error | `PEND:4` |
| Generics x codegen | SPEC 7.1 inline generic functions pass semantics and fail codegen (exit 7); generic `ref` fields and header-less generics are rejected at codegen | TYP-04 `types.md:146`; ZIG-29 `backend.md:80` |
| `del` x emitted capture name | `del p` collides with the emitted `|p|` capture; the alias form `q := p; del p; del q` is accepted | KNOWN B9/S6 `LEDG1:81`, `LEDG2:42`; P0b.6 `P0b:171-192` |
| `del` x `ref` parameter | `del` through a `ref` parameter frees a stack address | KNOWN S8 `LEDG2:44`; P0b.7 `P0b:193-214` |
| Struct positional init x same-named structs | Positional initializers map fields by struct name across the whole program | SAF-31 `safety.md:513` |
| Module merge x visibility x name clash | Flat concatenation leaks names, ignores `pub`, and rejects valid programs | PIP-7 `pipeline.md:214` |
| Imports x diagnostics | Errors inside imported files exit 8, lose their span and report the wrong file | PIP-11 `pipeline.md:286`; baseline tests 6-8 `docs/audits/2026-09-16/baseline.md:48-50` |
| Globals x calls | Facts about globals survive calls that assign them | SAF-6 `safety.md:166`; P0b.3 `P0b:107-131` |
| Batch ordering as an interaction | Fixing `defer void;` (B11) or capture shadowing (B9) before C4 would turn a Zig rejection into a division by zero that builds | `EXEC:122` |

## 2. UNCHECKED interactions

No audit finding and no test covers these pairs. Method and limits: I grepped
every `test/*.py` file for both sides of each pair (file-level co-occurrence,
`grep -lE` on the first term piped into `grep -lE` on the second), then grepped
all test function names (`grep -hn 'def test' test/*.py`) for a name that joins
the two, and grepped the six 2026-09-16 reports for the pair. File-level
co-occurrence in a 1000-line parser test file is not coverage of the
interaction; where only that exists I mark the pair UNCHECKED.

| Pair | Status | What I grepped |
| --- | --- | --- |
| Generics x modules (a generic type or function reached through `alias.Name`) | UNCHECKED | 16 test files contain both `generic\|\$T` and `import`, none with a matching test name; `safety.md:688-690` says module x struct-name and builtin collisions were not tested; the MOD design adds `alias.Box(i32)` (`EXEC:67`) with no test yet; `docs/STATUS.md:30-32` calls generic module workflows follow-up work |
| `match` x optionals | UNCHECKED and unreachable today | no optional type exists (grep `-rn '\bOption\b' a7/*.py a7/*/*.py` → only unrelated names); G5/7a own it (`PLAN:211`) |
| `match` x unions (tagged tag test, untagged active field) | UNCHECKED beyond KNOWN B2 | 10 files contain both `match` and `union` (`cli_failures`, `codegen_zig`, `semantic_types`, `semantic_generics`, …); no test name joins them; ZIG-8 says union reads have no obligation (`backend.md:252`) and `backend.md:562-567` lists union field reads among the constructs with no test |
| `defer` x loops, `defer` x `break` | UNCHECKED | 12 files contain `defer` and a loop keyword, 9 contain `defer` and `break`; no test name joins them; `safety.md:649-653` lists deferred assignments among the untested unsound cases |
| `ref` parameter x `del` | partly checked | the specific case (`del` through a `ref` parameter) is KNOWN S8 with a probe `LEDG2:44` and packet row P0b.7; but no test: `grep -l 'del ' $(grep -l 'ref ' test/*.py)` gives 9 parser/semantic files with no matching test name, and `safety.md:639-643` records no rejection test for `del` obligations |
| Slices x strings (slicing a string, passing `[]char`) | UNCHECKED for the proof path | 20 files contain both; only two test names touch it (`test_string_slices_compile_and_run` in `test/test_codegen_zig.py:434`, `test_string_slice_type_is_char_slice` in `test/test_semantic_types.py:357`), and neither covers the bounds obligation — S11 says indexing or slicing a slice or string parameter is always rejected (`LEDG2:48`) |
| Methods x generics (a receiver function on a generic struct) | UNCHECKED | 15 files contain both `method\|self` and `generic`; no test name joins them; methods are not audited at all (grep `-ail 'method'` over the six reports matches only `pipeline.md`) |
| if-expression x types (arm type unification, target type) | UNCHECKED | only 2 files contain both an if-expression shape and `cast`; SAF-27 says if-expressions get no guard facts and no value fact (`safety.md:467`); `test/test_zig_backend_runtime.py:137` checks precedence only, not typing |
| Casts x constant folding | UNCHECKED | `grep -l 'fold' $(grep -l 'cast' test/*.py)` → no file; SAF-14 (folded result not checked against the declared type) and SAF-28/SAF-33 are the only records, all in `safety.md` |
| Shadowing x captures (match capture or loop capture shadowing an outer name) | partly checked | `test/test_pipeline_native.py` (shadowed-loop-capture, a known failing baseline test) and `test/test_module_alias_shadowing.py:138` (loop variable named like an alias); no test for a match capture shadowing an outer local — TYP-30/PIP-21 record the defect instead |
| Imports x visibility x generics | UNCHECKED | 6 files contain both `import` and `pub `; none contains a `pub` declaration crossing a module boundary, and no example uses `pub` (grep `-lE 'pub ' examples/*.a7` → none); PIP-7 says visibility is not enforced at all |

Additional pairs with no coverage found while reading, same method:

| Pair | Status | What I grepped |
| --- | --- | --- |
| `fall` x facts x captures | UNCHECKED | `fall` appears in 9 test files; SAF-3 states `fall` carries state the pass never sees (`safety.md:107`); no test name mentions `fall` together with a capture or a divisor |
| Labels x `match` inside a loop | checked once | `types.md:611-612` records labeled `continue`/`break` inside a match inside a loop running correctly (`f30`, `f31`); no repository test (grep `-l 'label' test/*.py` → `codegen_zig`, `parser_*`, `semantic_control_flow`, none joining match and label in a test name) |
| Nested functions x safety x codegen | recorded, not tested | SAF-20 (bodies never analyzed), SAF-16, ZIG-40, PIP-30; `EXEC:199` defers them to a packet |
