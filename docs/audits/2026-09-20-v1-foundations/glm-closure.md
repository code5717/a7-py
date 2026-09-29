All dispositions verified. Final updated report:

---

# A7 V1 foundations — GLM-5.3 external review, round 2 (disposition verification)

**Updated verdict (scoped):** All six controller dispositions check out against current files. I retract F4 — my staleness inference was wrong, and I confirm the baseline gate evidence as a fresh run. F1, F2, F3, F5, F6 are resolved as delivered. Two count errors in my round-1 report are corrected below. The scanner's dynamic-call limits remain documented limits, not defects. The final full gate on the changed compiler is still running and no result is claimed here. V1 remains not delivered, and the evidence README says so correctly.

## Retraction: F4 (baseline gate freshness)

Retracted. My round-1 claim inferred staleness from the 2,087-test count alone; I did not examine `baseline-inputs.json` at the time. What the evidence actually shows, verified now:

- `docs/audits/2026-09-20-v1-foundations/baseline-inputs.json` — 1,055 path/sha256 entries; I re-hashed all 1,055 against current disk: only 16 mismatch, all explained by the batch's own post-gate edits (3 helper files, 2 test files, 5 docs) and the 6 PDFs already deleted in the worktree. The other 1,039 paths still match byte-for-byte.
- `baseline-content-verification.json` — 1,055 checked, `changed: []`, `gate_exit: 0`, archive sha256 recorded (matches `tmp/v1-delivery-2026-09-20/baseline-source.tar.gz`, 5.6 MB).
- `run_all_tests.sh:50` runs `uv run pytest --tb=short -q` with `testpaths = ["test"]` — scoped collection. The historical 2,629 count came from a whole-tree walk before `testpaths` was pinned (`open-items.md:76-80` documents that failure mode), so it was never the right expectation for a scoped run.
- Count arithmetic closes exactly: current `--collect-only` = **2,106** = 2,087 + 19 (no_recursion 19→35, helpers +3).

One residual provenance nuance (INFO, not a defect): `baseline-status.txt` shows the six PDFs deleted in the worktree at gate time, yet they appear in the input manifest with hashes and in the post-gate check as unchanged — so the manifest hashed tracked (git) content rather than worktree bytes for those paths. "No path changed during the gate" is a tracked-content claim. It does not affect gate freshness; the PDFs are docs, not compiler inputs.

## Corrections to my round-1 report

Both controller corrections confirmed by `--collect-only`:
- 28 recursive groups remain after the three removals (31 − 3). My "other 25" was an arithmetic error.
- `test/test_iterative_traversal.py` has **44** tests. My "63" was the combined pre-apply run (44 traversal + 19 then-existing no_recursion tests). Current: no_recursion 35, traversal 44, helpers 3 → the README's "82 focused tests" and `targeted-tests.log` ("82 passed in 2.51s") are arithmetically exact.

## Disposition verification

| # | Disposition | Verified evidence |
|---|---|---|
| F1 | Resolved | `docs/plan/execution.md:176` types.py row now covers `equals`/`__str__`/`__hash__`; `:177,:180,:183` mark `dump`, `_int_literal`, mutation-base "converted 2026-09-20"; `:185-189` NOREC-DATA paragraph records the 44 generated methods (matches my scan: dataclass findings = 44) with honest caveats; reconciliation section `:528-545` states 31→28 and that limit-100 helper tests "do not qualify deep programs through the entire pipeline"; `open-items.md:246-254` supersedes NOREC-0b "for those specific mechanisms" only. |
| F2 | Resolved (documentation-only, as claimed) | `test/norec_scan.py:64-71` header now names `dict(...)` construction, augmented container assignment, `functools.partial`; `verification-v2.md` records them and notes the archived v2 hashes predate the header clarification. I independently re-derived the AST-equivalence claim: parsing current `test/norec_scan.py` and `tmp/norec0b/v2/norec_scan.py`, stripping docstrings, `ast.dump` equality = **True**. Executable scanner behavior is unchanged; my round-1 probe results remain valid. |
| F3 | Resolved | Delivered evidence is `verification-v2.md` + frozen `v2/` snapshots + `norec0b-v2-hashes.json`/`norec0b-v2.patch` (hashes match `v2/` files on disk); v1 `verification.md` preserved as historical. The delivered report's numbers (35 passed; 15 failed/20 passed on baseline) match my own measurements exactly. |
| F5 | Resolved | `docs/plan/delivery-roadmap.md` and `docs/plan/research/memory/delivery-reconciliation.md` delivered; link checker over both files: zero broken relative `.md` links (including `../audits/2026-09-20-v1-foundations/README.md` and the remediation snapshot). |
| F6 | Resolved | Delivered W5 reads "sum of all six returned values 397" (`delivery-reconciliation.md:78`). |

## State of the tree (frozen-inputs check)

Main-tree `a7/` and scanner/test files are unchanged since the 00:19:17 apply (helper files byte-identical to candidate; scanner sha `3f20da2a…`, AST-equivalent to frozen v2 `fb7f92fa…`; landed ratchet differs from candidate only by the three removed entries). Post-apply results previously verified by me stand: 35/35 no-recursion, 28 groups normal == conservative, unresolved 35, deepcopy 1, dataclass 44, helper depth tests 3/3 at recursion limit 100. The evidence README correctly states "The baseline gate is not a result for the changed compiler" and that final full-gate verification is pending. The controller's `glm-review.md` records my round-1 report verbatim — no fidelity loss.

## Outstanding findings

None of F1–F6 remain open. Remaining items are, in my assessment, properly classified already: the scanner's unmodelled dynamic-call forms (documented in the header and `verification-v2.md`; my five confirmed false-negative probes stand as limits, not defects), the pending final full gate on the changed compiler, and the INFO-level manifest provenance nuance above.

## Verification evidence (this round)

`baseline-inputs.json` full re-hash (1,055 paths, 16 explained mismatches); `pytest --collect-only` → 2,106 total / 79 for the two files (44+35) / 3 helpers; AST-equivalence re-derivation (docstring-stripped `ast.dump` equality True); link checks on both delivered docs; re-reads of `execution.md`, `open-items.md`, scanner header, `README.md`, `targeted-tests.log`, `glm-review.md`.

## Tool events

One bash output exceeded the display limit (`baseline-inputs.json` structure dump) and was truncated to a saved file; I re-read the needed fields with targeted commands. No provider failures; no sub-agents or model CLIs invoked; no A7 programs executed; no input files modified.

## Scoped verdict

Round-1 findings are fully dispositioned: F4 retracted with correction, F1/F2/F3/F5/F6 verified resolved, and my two count errors corrected. The delivered batch (scanner v2 + three helper conversions + evidence set + docs) is consistent, honestly scoped, and independently reproducible from the archived snapshots. Nothing in the delivered artifacts claims the final gate, V1 delivery, or complete dynamic-call analysis. Final gate result remains outstanding by design.
