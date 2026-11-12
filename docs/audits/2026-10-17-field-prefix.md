# Allocation field-prefix lookup

The candidate searches a field path from its last dot toward its first dot and
selects the first registered prefix. This preserves the longest-prefix rule
without sorting the allocation-place registry. It changes no A7 language rule.

## Scope and controls

Fifteen adversarial lookup cases, registry mutation checks and six operation-count
probes passed. Eleven paired compiler controls preserve five byte-identical Zig
outputs and six identical semantic failures. The factory-holder positive and
deleted-child negative reach the changed helper six times per source version.
The original nine compiler controls did not reach that helper.

With 32, 64 and 128 unrelated registry entries, the baseline visits 33, 65 and
129 entries. The candidate visits none and performs one membership lookup and
one retrieval in these probes. With deeper field paths, membership lookups grow
with path depth. String slicing and hashing still cost work. These counts do
not measure elapsed time or a whole-compiler speedup.

The bounded candidate, first failed evidence-serialization attempt, corrected
execution and independent review remain in
`tmp/v1-completion-2026-10-17/field-prefix-candidate/`.

## Full pytest qualification

Frozen source manifest
`8bb066b384f27ac20787bf74716bfe685392c8f33d8cf078ff5bc803d9647a74`
contains 1,726 files. Owner 23009 terminated with exit 0: 5,153 tests passed and
one known strict scalar-printing expected failure remained, in 831.02 seconds.
Exactly four scanner tests were excluded under the user's instruction.
All nine observer processes exited 0. The controller rehashed the frozen source,
command streams and observer reports after completion.

The packet is
`tmp/v1-completion-2026-10-17/field-prefix-full-qualification/`.
`OWNER-TERMINAL.json` records the terminal tool result. The results file SHA256 is
`5d0456c3e3614cb129d7413b6b3a63cf801af6d2d9e3d4333d1e7b2764864e19`.
Candidate `safety.py` SHA256 is
`e4cc2a048d597953776620d3d251ce3c15dcefb7af72c6dc0378855d38a1824e`.

The independent execution audit passed. Its `FINAL-REVIEW.md` SHA256 is
`de09327b472b60685a61456dcc31d2c16a1fcf1888a03b6473ee5dd6f356856b`.
The controller integrated the exact qualified safety file after rechecking the
destination and preserving its previous contents. All 334 compiler/test files
then matched the frozen source. Transfer evidence is in
`tmp/v1-completion-2026-10-17/field-prefix-integration/verification.json`.

This result covers the frozen lookup candidate. It does not qualify the separate conditional-global
repair, later documentation edits, the complete release wrapper or V1.
The [current status](../STATUS.md) records lifetime failures discovered outside
the frozen suite. Passing this suite does not close those failures.
