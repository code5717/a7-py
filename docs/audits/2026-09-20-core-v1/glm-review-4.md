Attribution verified against the baseline: `format_type` in pre-conversion-console.py:487 recursed only for GENERIC/FUNCTION leaves (slice-wrapper loop and `_add_statements_to_tree` were already iterative; TYPE_SET hit the `None` fallback pre-conversion), and DEFER recursed via `format_statement_label` (pre-conversion-console.py:788). Now run the focused tests:

All cycle guards, type-set display, and shared-child repetition verified. Now: confirm only display files changed, normal end-to-end output unchanged, the unclaimed tree-attachment cycle still open, and check the isolated low-recursion failure:

# Review: console formatter follow-up (F1/F2 closure)

**Verdict: PASS.** F1 and the true F2 regressions are closed; attribution in the closure notes matches the baseline; claims about open items are accurate; no runtime semantics changed.

## Attribution verified (pre-conversion-console.py)

- `format_type` (pre-conversion-console.py:487): wrapper loop for array/slice/pointer was already iterative; only GENERIC/FUNCTION leaves recursed (lines 525, 532, 536) → those cycles raised `RecursionError` in the baseline and regressed to unbounded traversal during conversion. Slice-wrapper cycles already looped pre-conversion (line 496-507). TYPE_SET hit `leaf = current.type_name` = `None` → `TypeError` at join (lines 542-556) — **F1 was pre-existing, not a conversion regression; my original attribution is corrected.**
- DEFER recursed via `format_statement_label(stmt.statement)` (pre-conversion-console.py:788) → baseline `RecursionError`, regressed during conversion.
- `_add_statements_to_tree` was already iterative and identical in the baseline (lines 805-825) → tree-attachment cycles pre-existing.

## Closure verification (probes + tests)

- **F1 closed**: `@type_set([]i32, [2]i32)`, `@type_set()`, `types=None` → `@type_set()`; `--mode ast` on `x: @type_set(i32, i64) = 5` exits 0 and displays it (asserted by the new CLI test; suite passes). Same-family fallback crashes fixed by the `or`-chain + `str(part)` join: nameless identifier → `identifier`, TYPE_ALIAS → name or kind, `__inline__` string passthrough preserved.
- **F2 regressed paths closed**: generic self/mutual → `Box(<cycle>)`, `A(B(<cycle>))`; function self/mutual → `fn(<cycle>)` (bounded, odd-looking but terminating); defer self/mutual → `[blue]DEFER[/blue] → ... [dim]<cycle>[/dim]`. The pre-existing unbounded slice/pointer wrapper cycles are now also bounded (`[]<cycle>`, `[]ref <cycle>`) — strictly better than baseline.
- **Shared children repeat** (active/exit protocol sound): `Pair(fn(i32) i32, fn(i32) i32)` and param+return sharing `fn(fn(i32) i32) fn(i32) i32` — no false suppression.
- **Normal output unchanged**: kinds.a7 end-to-end AST render byte-identical to my previous review; `fn()`, bare `Box`, `ref ?` fallbacks all preserved; `test_iterative_types.py` still 25 passed (types.py untouched).
- **Scope confirmed**: mtime scan shows only `console_formatter.py` + `test_console_review_regressions.py` changed; scanner ratchet 35 passed (no new recursion).
- **Tests**: 7 console + 31 CLI = 38 focused passed (matches the notes' count).

## Open items — verified as claimed, not fixed

- `_add_statements_to_tree` block-attachment cycles: still unbounded (probe → MemoryError/SIGSEGV under RLIMIT). Pre-existing, explicitly unclaimed.
- F3 (`_display_semantic` MarkupError, latent/unreachable via CLI), F4 (`literal nil None` — still present in output), F5 (exponential spellings) — recorded as limits, verified still open.

## Low-recursion test

`test_iterative_traversal.py::TestLowRecursionLimit::test_nested_expressions_10_levels` **passes in this copy** (1 passed, 0.04 s) with the identical patch applied — the isolated-dir failure in formatter-closure-notes.md is environmental (their run used the main checkout's venv), not caused by the formatter patch. Consistent with the main-gate pass; no further action needed.

## Limits of this review

- `example-comparison.json`/`baseline-comparison.json`/`hashes.json` are not in this copy, so the 43-comparison claim is accepted indirectly (committed captured-baseline test, my independent byte-comparison, 22+3 exact-string assertions).
- `@type_set(...)` display has no pre-conversion reference (baseline crashed there) — new display behavior by design, test-pinned.
- Cosmetic pre-existing quirks unchanged (e.g., `[None]` array size if the size node lacks a value — same in baseline).

**PASS for the formatter follow-up.**
