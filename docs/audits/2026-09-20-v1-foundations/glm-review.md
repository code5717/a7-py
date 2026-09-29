All verification complete. Final report:

---

# A7 V1 foundations — GLM-5.3 external review (advisory)

**Verdict (scoped):** The NOREC-0b scanner work and the three helper conversions are correct within their stated limits, with no false positives found and behavior preservation verified differentially. No unsupported completion claim was found in the batch's own artifacts. Two medium findings remain: the `execution.md` half of NOREC-0b sub-item (4) is undelivered (and now stale after the mid-review apply), and two scanner false-negative escapes are not named in the stated limits. V1 is not delivered; the full gate was not run in this review.

## Timeline event (affects evidence reading)

During this review, at 2026-09-20 00:19:17, the controlling session applied the helper patch, the v2 scanner, and the shrunk ratchet to the main tree (mtimes of `a7/safety.py`, `a7/symbol_table.py`, `a7/backends/zig.py`, `test/norec_scan.py`, `test/test_no_recursion.py`). Before that moment I verified the claimed "before" state (helper tests 3/3 failing on main; main scanner byte-identical to `tmp/norec0b/baseline/`). After it I re-verified on main: 35/35 no-recursion tests, 3/3 helper depth tests, 207/207 in `test_audit_safety_repairs` + `test_codegen_zig` + `test_module_resolver` + `test_iterative_traversal`, and the group ratchet shrank 31 → 28 by exactly the three converted groups (`base_identifier`, `_int_literal`, `SymbolTable.dump`). The landed scanner is byte-identical to the candidate (`fb7f92fa…`); the landed test file differs from the candidate only by removing those three ratchet entries.

## Findings

| # | Severity | Finding |
|---|---|---|
| F1 | MEDIUM | NOREC-0b sub-item (4), second half, undelivered: `docs/plan/execution.md`'s conversion table (lines 174-184) still lacks the `a7/types.py` `__str__`/`__hash__` cycles, any `base_identifier` entry, and a batch for the 44 recursive dataclass methods (my scan confirms 44 dataclass findings on the current tree). Post-apply it is also stale in the other direction: line 180 still lists the `_int_literal` loop as a pending conversion although it is now done. `docs/plan/audit/open-items.md:112` remains open accordingly. |
| F2 | MEDIUM | Two confirmed scanner false negatives are not covered by the stated limits wording: (a) `dict(run=self.run, …)` constructor — cycle missed; (b) `self.work += [lambda…]` followed by `pop()()` — cycle missed. Three further misses are within the documented limits and confirmed: dict item assignment `d["k"]=self.run`, factory-returned tables (`self.make()["run"]()`), `functools.partial` queued callbacks. Evidence: `tmp/v1-delivery-2026-09-20/glm-probes/probe-candidate.out` (all five report `groups: []` where a true runtime cycle exists). Add (a)/(b) to the limits list in the scanner docstring and `verification.md`. |
| F3 | LOW | Evidence drift in `tmp/norec0b/verification.md`: it records v1 numbers (32 passed; baseline 13 failed/19 passed) but the delivered candidate is v2 — measured 35 passed, and baseline discrimination is 15 failed/20 passed. Also `candidate/` was overwritten v1→v2 in place, so `norec0b-v1-hashes.json` no longer matches the files it names (v1 hash `80817119…` vs current `fb7f92fa…`). |
| F4 | LOW | `tmp/v1-delivery-2026-09-20/baseline-gate.log` reports "9/9 checks, 2,087 tests", which matches the older GLM remediation snapshot lineage, not a fresh gate of the current dirty tree (the Sept-19 cleanup reported 2,629 tests, `open-items.md:37-39`). The roadmap already discounts it; do not cite it as current-baseline evidence. |
| F5 | LOW | Forward references in the drafts: `delivery-roadmap.md:28` links `docs/audits/2026-09-20-v1-foundations/` (does not exist); `memory-reconciliation.md`'s final home `docs/plan/research/memory/delivery-reconciliation.md` does not exist yet. Acceptable for drafts; must exist before docs land. |
| F6 | LOW | W5 oracle ambiguity: "value sum 397" is the sum over the six-request stream (65+66+67+65+68+66); miss-loaded values sum to 332. State which. All other oracle arithmetic verified correct (W1 49,995,000; W4 334 records/333,666; W7 328,350; W9 13 and [4,6]). |

## Verified claims (independently reproduced)

- **Dictionary dispatch, constant vs dynamic keys.** Constant `d['leaf']()` and `d.get('leaf')()` select only the matching value (v2 key-selection in `_callable_targets`, candidate `norec_scan.py:1198-1224`); dynamic `d[k]` and `d.get(k)` conservatively reach all values. Verified by the candidate tests and my dynamic-`.get` probe. Class-body, `__init__`-instance, and module-level tables are each modeled (three parametrized tests).
- **Immediate vs queued lambdas.** Separate lambda nodes; queuing (`append`/`extend`/`insert` + `pop`/`popleft`) adds lambda→target edges without owner→lambda edges. Immediate invocation (`(lambda…)()`, local/attr call, `pop()()`) still reports cycles; callback parameters resolve to lambda nodes. My probe confirms a true `run→lambda→run` cycle through a queue is caught, and queuing-only produces no false cycle.
- **Untyped `self.attribute` delegation.** `self.worker.run()` with unknown receiver records all same-named methods as *unresolved candidates* (no edges in normal mode; all edges in conservative mode). `_is_self_attr` (`norec_scan.py:864-872`) gates this; annotated self-attributes still resolve normally.
- **Generated dataclass repr.** `_Func.parent` is `field(repr=False)`; the self-scan test now also asserts `dataclass_findings == []`. With the baseline scanner this assert fails (`test_the_scanner_itself_has_no_recursion` among the 15), so the fix is discriminated.
- **Unresolved-edge scan agreement.** Direct dual scans of `a7/`: 31 groups pre-apply and 28 post-apply, identical sets in normal and conservative modes; unresolved 35, deepcopy 1, dataclass 44 unchanged; edge deltas vs baseline are exactly the lambda-node attribution split. No allowlist entries were added — the ratchet only shrank.
- **Helper behavior preservation.** Randomized differential corpora (300 unary chains incl. non-NEG and float/None boundaries, 400 mutation targets incl. DEREF/ADDRESS_OF boundaries, 120 random scope trees) produce byte-identical results between the recursive and iterative implementations (`glm-probes/helpers-{main,cand}.json`, `diff_helpers.py`).
- **Depth at recursion limit 100.** 5000-deep unary chains, 5000-deep field/index targets, 2000-deep scope nesting all pass at limit 100 in subprocesses, in the isolated package and on post-apply main. Main's existing `test_iterative_traversal.py` (63 tests) does not cover these three helpers, so the new tests add real coverage rather than duplicating it.

## Test validity

The new scanner tests assert observable outputs (group tuples, edge sets, unresolved candidate tuples) and 15/35 fail against the preserved baseline — they discriminate, not mirror. The helper tests run in subprocesses with the limit set after imports and assert exact outputs including the dump text. No mock-only or coverage-illusion patterns found in the added tests.

## Remaining limits

Scanner (beyond F2): `singledispatch`, container protocols beyond list/deque append-family, callable factories with inferred returns, dictionary item assignment — all outside the model; dynamic keys reach every stored value (conservative); container storage is class-scoped across instances (may over-approximate edges, the safe direction). None of the reviewed artifacts claims a recursion-free compiler; `verification.md` explicitly disclaims it and the roadmap records "scanner retains recursive groups". Helper scope is exactly three functions; the other 25 recursive groups in `a7/` are untouched. The final full gate (`run_all_tests.sh`) was not run here and remains pending; nothing in this batch marks V1 delivered.

## Tool/provider failures

- First `curl -sI` on both paper URLs printed nothing; retry with `-sS` showed the Perceus URL is a 301 (resolves to 200 after redirect, 635 KB) and the FP² URL is a direct 200 (1.0 MB PDF). URL citations in `memory-reconciliation.md` are valid.
- `pypdf`/`PyPDF2` unavailable in the environment, so the papers' section-level content claims were not re-verified beyond URL validity and abstract-level knowledge — recorded as an unchecked limit.
- No sub-agents were needed; none launched. No model/agent CLI invoked. No A7 programs were executed.
