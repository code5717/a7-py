All checks complete. Final verification state: 29 + 35 + 44 focused tests pass; review done.

# Review: iterative `_format_type`, console formatter, and recursion-scanner inventory

**Verdict: CHANGES REQUIRED** — one live crash (F1) in the in-scope `ConsoleFormatter.format_type`; everything else in the batch is verified correct and compatible.

## Verified correct

1. **Exact normal-output compatibility (`a7/types.py:528`)** — differential probe against a recursive oracle over 12,000 randomized types (all kinds, shared substructure, nested/multi-member type sets): zero mismatches. Committed exact spellings (22 cases incl. variadic/typed-variadic functions, generic struct params, `@type_set` sorting) all pass.
2. **Cycles** — all six structural cycle shapes (self, mutual, function-param, struct-field, type-set member, type-set self-membership) raise `RecursionError` (same class as before; no caller in `a7/` catches by message). Named records terminate at their name (`ref Node`), matching the pinned test. The active/leave protocol pairs correctly across the `sort` continuation — no false positives on shared children in any sibling/param/return/constraint combination probed.
3. **Deep input / resources** — linear: depth 1500 → 1.5 ms, 150 000 → 130 ms (810 k chars) at recursion limit 100; 20 000-deep function chain 16 ms; 5000-param function and 3000-member sorted type set ~2 ms. No hashing or `equals` on the render path.
4. **Console statement/type formatting** — baseline AST render matches the captured pre-conversion string; nested type order exact (`fn(Pair([]i32, [3]ref i32), i32) Result(i32)`); 400-deep DEFER/BLOCK/type chains render at limit 100 with width-bounded output. `_walk_scope` (`console_formatter.py:231`) is cycle-safe (id-visited), deterministic pre-order.
5. **Rich literal escaping** — source-panel titles (`Text()`), token values (`Text(repr())`), and literal details (`escape` + 20-char truncation) are literal; probed with `[/oops]` payloads. Type spellings and identifiers cannot form markup (`[3]`/`[]` aren't tags in Rich 15; identifiers are ASCII alnum/`_`).
6. **Scanner inventory** — scan of `a7/` (820 functions, 24 groups) contains nothing from types `__str__`/`_format_type` or `a7/formatters`; ratchet enforces the inventory in both directions (35 tests pass). Remaining types.py groups are exactly the documented `equals`/`__hash__` leftovers.

## Findings

| # | Severity | Finding | Probe |
|---|----------|---------|-------|
| F1 | **Medium** (live crash) | `format_type` (`console_formatter.py:488`) has no `TYPE_SET`/`TYPE_ALIAS` case; the `hasattr(current, "type_name")` fallback is always true on ASTNode (all dataclass fields default to `None`), so it appends `None` and `"".join` raises `TypeError`. Parser accepts `@type_set` in any type position (`parser.py:670`), so `x: @type_set(i32, i64) = 5` under `--mode ast` renders tokens then dies: exit 8, "Unexpected error: sequence item 0: expected str instance, NoneType found" | `uv run a7 --mode ast` on that 3-line file |
| F2 | Low | Cyclic AST nodes make `format_type` and `_add_statements_to_tree` loop unboundedly to MemoryError (then SIGSEGV under RLIMIT); the recursive predecessors raised `RecursionError` quickly. Unreachable via the parser (fresh nodes only) — defense-in-depth regression, inconsistent with types.py `_format_type`, which detects cycles and raises | `probe6_cycle.py` (node.element_type = node) |
| F3 | Low (latent) | `_display_semantic` (`console_formatter.py:147`) prints error messages unescaped; a message containing `[/...]` raises `MarkupError` (probed directly — reachable via `_format_match_pattern` embedding string-literal values, `type_checker.py:2590`). Not reachable through the CLI today: semantic errors exit via `compile.py:403-407` to the safe `errors.py` formatter, and this branch only runs on success | `probe4_semantic.py` |
| F4 | Info | Same unguarded-`hasattr` pattern prints nil literals as `literal nil None` (cosmetic) | `--mode ast` on `cb: ref fn(i32) bool = nil` |
| F5 | Info | Types whose correct spelling is exponential (function as param and return at every level) render exponentially; inherent to the spelling, shared with the old code below its frame limit; no output-size cap | `probe2b.py` (2^625 chars at depth 2500) |

Provenance caveat: the frozen copy has no git history, so F1/F3/F4 cannot be attributed to or excluded from this batch; F1 sits in a function the batch rewrote and is untested, so it is in scope either way.

## Scanner limitations (acceptable, note)
- Frozenset `__hash__` correctly not flagged (CPython uses stored hashes), but `frozenset([...])` construction hashes members at insertion — runtime data recursion no static call-graph rule sees; same class as the acknowledged dataclass `__eq__`/`__repr__` groups.
- `TypeSet.__hash__` recursion through members is therefore unlisted by design, consistent with the remaining `__hash__` group.

## Test gaps
- No `format_type` case for `TYPE_SET`/`TYPE_ALIAS` nodes (would have caught F1).
- No cyclic-AST test for console walkers (types.py has one for its cycles).
- No direct tests for `_walk_scope`/`_collect_symbols`/`_display_semantic` — the converted symbol-table walk is untested anywhere in `test/`.
- No semantic-error-message markup test (F3).
- Depth pins stop at 1500/400 (scaling verified linear manually here).

## Limitations of this review
No git history in the frozen copy → no direct diff against pre-conversion code; compatibility rests on the committed captured baselines plus the oracle differential. `docs/` is absent from the copy, so CHANGELOG/SPEC/STATUS alignment could not be checked. Full native gate not run (out of scope per instructions); focused tests run: `test_iterative_types.py` + `test_iterative_console.py` (29), `test_no_recursion.py` (35), `test_iterative_traversal.py` (44) — all pass.

**Required change (small):** give `format_type` a `TYPE_SET`/`TYPE_ALIAS` branch (or guard the `type_name`/`name` fallbacks against `None`) and add the regression test; optionally a visited-set or depth cap for F2. With that, this batch is PASS-worthy.
