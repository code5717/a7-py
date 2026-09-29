# Closure Verdict — GLM-5.3, 2026-09-19 (third run, focused)

**One reproducible bug remains in the repaired match family: expression matches without `else` still pass A7 (exit 0) and fail the Zig build.** Everything else in the three repaired families — statement-match no-else lowering with `fall`, slice-length relations and invalidation, backing-array mutability, deletion guards, loop-local index restoration — verified fixed or intentionally conservative. Tree unchanged during this run (HEAD `701c679`, 149 dirty paths, identical start and end).

## Verified closures (commands and results)

Focused tests: `PYTHONPATH=. uv run pytest test/test_audit_safety_repairs.py test/test_audit_backend_repairs.py -q` → **34 passed** (104.6s), including `match-without-else` pinning `one/done` in Debug+ReleaseFast, `slice_get(a[0..3],2)` → `4`, slice-reassignment rejection, the three deletion-guard fixtures, and `for-shadow` safe-255 / rejected-300.

My own cases (all in `/tmp/a7-glm53-repair-closure/`, script `run.sh` compiles → `zig build-exe` → runs):

| Case | Result |
|---|---|
| `m_no_else_unmatched` (statement match, no else, unmatched value) | exit 0 → native `done one done` — unmatched arm executes nothing, following statement still runs ✓ |
| `m_fall_braced_no_else` (`fall` in braced case, no else) | exit 0 → native `b c end` — fall-through preserved under the conditional-chain lowering ✓ |
| `m_bool_no_else` | exit 6 "Missing bool case(s): false" — bool/enum exhaustiveness still enforced ✓ |
| `s_while_len` (`while i < s.len { s[i]; i += 1 }`) | exit 0 → native `1 2 3` — the idiomatic loop-invariant pattern works ✓ |
| `s_literal_bound` (known-len slice, literal bound) | exit 0 ✓ |
| `s_index_mutated2` (`j := i; if i < s.len { j += 1; s[j] }`) | exit 6 "Index not proven in bounds" — mutating the index after the guard invalidates the relation ✓ sound |
| `s_backing_mut` (`s := arr[0..3]; s[1] = 9; print arr[1]`) | exit 0 → native `9` — backing-array mutability fixed (discarding-const gone) ✓ |
| `g_nil_resurrect` (`del b; if b == nil { b.value = 1 }`) | exit 6 "Use after move or delete" — nil guard cannot resurrect a deleted binding ✓ |
| `g_defer_del_read` (`defer { del b }; if b != nil { b.value = 1 }`) | exit 0, clean run — **correct acceptance**: the defer fires at scope exit, after the guarded read ✓ |
| `g_loop_del_after` (del in loop, read after loop) | exit 6 "Use after move or delete" ✓ |

## Remaining bug (reproducible)

**Expression match without `else`** — `pick :: fn(x: i32) i32 { ret match x { case 1: 10 } }` (`m_expr_no_else_run.a7`; assignment form `y := match x { case 1: 10 }` identical):
- A7 exit 0; `zig build-exe` → `error: switch must handle all possibilities` (`out/m_expr_no_else_run.zig:15:12`).
- The repair lowered *statement* matches to conditional chains but expression matches still emit a Zig `switch`. This is the same accepted-A7/Zig-rejected class as the repaired statement form and needs no approval packet under the L24 rule; a non-exhaustive expression match is also semantically undefined (no value for unmatched inputs), so rejecting it preserves meaning.

## Conservative limitation (not a bug)

`s_elem_mut`: writing an element through the same slice between guard and index (`if i < s.len { s[0] = 5; ret s[i] }`) rejects "Index not proven in bounds". Length cannot change, so the program is safe, but this matches the controller's stated "borrowing the slice for mutation invalidates the relation" policy — safe-direction over-rejection; document it if users hit it.

## Corrections and limits

- Prime example: confirmed `examples/032_prime_numbers.a7:12` contains `if d > n / d { break }` — the loop still stops at √n without `d*d` overflow; my previous "complexity change" note was wrong and is withdrawn.
- Scope held: I did not probe retained ownership/alias design, abs(MIN), dynamic shifts, or module syntax, and make no global soundness claim — the relation/join machinery is verified on the executed paths only. Full gate not rerun (controller's responsibility). No source changes, commits, or external messages; artifacts in `/tmp/a7-glm53-repair-closure/`.
