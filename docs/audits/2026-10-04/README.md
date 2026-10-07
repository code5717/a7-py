# Audit, 2026-10-04

Scope: the whole repository at commit `c8face6` plus the uncommitted
working tree of that day. Sixteen read-only reviews and one full gate
run. The gate passed 10 of 10 checks while the reviews reproduced
regressions, safety-proof holes and programs that pass `a7` and fail
the Zig build.

| File | Content |
| --- | --- |
| [findings.md](findings.md) | Every finding, by phase, with row IDs (P0-1, P2-52, T-1 and so on). Appendix A lists findings without a table row. Appendices B to J embed the ledger audit, the seven second-round reports and the stdlib proposal. |
| [repair-plan.md](repair-plan.md) | The plan the user approved on 2026-10-04: decisions, working rules, waves 0 to 8, verification. |
| [stdlib-proposal.md](stdlib-proposal.md) | Design proposal for a general-purpose standard library. Design only. |

Decisions taken from this audit are ledger entries L58 to L70 in
[the decision ledger](../../plan/decisions.md). Open work is tracked in
[the delivery roadmap](../../plan/delivery-roadmap.md), section R.

Limits. Findings marked R were read, not reproduced. The reviewers'
probe programs (about 3,700 files, 23 MB) stay in the ignored directory
`tmp/audit-2026-10-04/probes/`; paths in the findings that start with
`probes/` or name a session scratchpad refer to it and do not exist on
a clean checkout. `./run_release_checks.sh` was not run. Line numbers
refer to the working tree of 2026-10-04.
