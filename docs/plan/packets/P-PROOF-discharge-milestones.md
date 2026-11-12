# P-PROOF: formal proof-discharge milestones

Status: implementation packet for rewrite-facing formal discharge. Not a
language-syntax approval packet. No CompCert or end-to-end verified-compiler
claim. Coordinates with Track 1 safety/alias work: this packet names the
module split and first discharge kinds; it does not expand alias proofs.

## Goal

Split today's monolithic safety proofing into named stages, and land a thin
**proof-discharge** boundary that records obligation kind, evidence, or reject
diagnostics. First machine-checkable, CPU-scalable milestones pin behaviors
the compiler already enforces.

## Stage split (STATUS priority #4)

| Stage | Owns | Current home (reference tree) |
| --- | --- | --- |
| CFG | Control-flow joins, loop exits, defer exits | `a7/passes/safety.py` (FactMap joins / ExitFrame) |
| Fact | Intervals, nil, lengths, discriminants, allocation identity | `a7/passes/safety.py` (`ValueFact`, allocation graph) |
| Obligation | Collect risky-op requirements | `a7/passes/safety.py` (`Obligation`, `ObligationKind`) |
| Proof-discharge | Prove or reject; record evidence | `a7/proof_discharge.py` (thin boundary) + call sites |
| Backend-plan | Approved lowerings for codegen | `BackendPlan` in `a7/proof_discharge.py`; consumed by `a7/backends/zig.py` |

Related non-safety discharges already live outside the safety walk:

- Recursion ban: `a7/passes/semantic_validator.py` (call/value graph)
- Tagged-union match exhaustiveness: `a7/passes/semantic_validator.py` (tag-set)
- Constant fold / exact fit: `a7/exact_constants.py` plus typed destinations

The rewrite may relocate CFG/fact collection; discharge and backend-plan remain
pure functions of collected obligations and facts.

## Milestones

### (a) Constant-fold congruence (pinned int wrap + selected floats)

**Lemma sketch.** For pinned integer widths and operators `+`, `-`, `*`, the
wrapping lowering of two constants equals the modular wrap model for that
width. For selected float cases, typed IEEE evaluation matches the oracle used
by `test/test_float_nonfinite_folding.py` / exact-constant refusal at
destination. Exact untyped constants remain exact until `materialize` (L61);
out-of-range destinations reject rather than wrap.

**Discharge kind.** `CONSTANT_FOLD_CONGRUENCE`

**Exit.** Named records for the pinned table; gate tests green. No claim that
every fold path is externally machine-checked.

### (b) Recursion-ban call/value graph soundness

**Lemma sketch.** Direct, mutual, and local function-value alias cycles on the
static call/value graph are rejected (exit 6). Acyclic groups accept. The
analysis may reject some non-recursive programs that share function types
(documented false positives).

**Discharge kind.** `RECURSION_BAN`

**Exit.** Each reported cycle and each validated acyclic function group
produces a discharge record. Existing semantic tests remain authoritative for
behavior.

### (c) Tagged-union match exhaustiveness (tag-set lemma)

**Lemma sketch.** For a tagged union with tag set `T`, a match without `else`
or wildcard is exhaustive iff the covered tag set equals `T`. Missing tags
reject with `NON_EXHAUSTIVE_MATCH`. Bare identifier arms over tagged unions
remain invalid (whole-value capture).

**Discharge kind.** `MATCH_EXHAUSTIVENESS`

**Exit.** Exhaustive and non-exhaustive controls record proven/rejected
discharges. Existing semantic tests remain authoritative.

### (d) Obligation record API

Every discharge writes a record:

- `kind` — `DischargeKind` or safety `ObligationKind` name
- `proven` — true when discharged; false when rejected
- `evidence` — short machine-oriented reason string
- optional `subject` / `span` — union name, function name, fold case, or source span

Rejected safety obligations still emit diagnostics through the existing
`SafetyError` path. The ledger is observational for milestones (a)–(c) and the
rewrite handbook; it does not replace exit codes.

## Out of scope

- Full CFG/fact module extraction from `safety.py` (Track 1 conflict risk)
- External proof assistants, CompCert-style translation validation
- Alias/lifetime completeness (Track 1 / SAFETY_CONTRACT gaps)
- Learning optimizer (Track 7; depends on these checkers)

## Coordination

If a Track 1 safety branch is rewriting `a7/passes/safety.py`, keep this
packet's code landing to: (1) `a7/proof_discharge.py`, (2) validator ledger
hooks, (3) docs/tests. Defer invasive CFG/fact splits until that branch
merges. Re-export `Obligation` / `BackendPlan` from `safety` for compatibility.

## Acceptance

1. Packet present at `docs/plan/packets/P-PROOF-discharge-milestones.md`.
2. Thin `a7/proof_discharge.py` boundary with ledger API; safety types moved
   or re-exported without behavior change.
3. Tests name the three milestone discharges.
4. `docs/STATUS.md` and `docs/SAFETY_CONTRACT.md` point here.
5. Focused pytest green; `./run_all_tests.sh` when code lands.
