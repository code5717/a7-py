# SAF-6 global call mutation and SAF-3 enum fallthrough: candidate

Status: candidate evidence, 2026-09-20. The patch is not applied to the
production compiler and is not approved. Production `a7/` files were not
edited; the candidate lives in `tmp/resume-safety-candidate/` only. Nothing
here is release qualification.

## Result

An isolated candidate now rejects both original unsafe probes and 19 new
unsafe compile-only probes, keeps every safe control compiling and natively
correct in Debug and ReleaseFast, changes zero of 255 corpus exit codes, and
introduces exactly one known compatibility rejection (calling a function
through a local alias between a global fact and its use), which needs L24
approval before any application. The two pre-existing full-suite test
failures are identical on the unmodified production tree and are not caused
by the candidate.

## Design

Two mechanisms, one dependency:

1. **SAF-6 call-effect summaries** (`_summarize_call_effects`): each
   file-scope function maps to the set of mutable-global names its
   execution may assign or delete, expanded transitively over direct
   calls, or to `None` (unbounded effect). A call drops the facts of the
   globals its callee may write (`_apply_call_effects`), after the callee
   and arguments are checked, matching evaluation order. A call with an
   empty summary (the empty-function control) invalidates nothing.
2. **SAF-3 fallthrough carrying with typed enum reachability** (MATCH
   handler + `_pattern_relation`): case exit facts and moved-binding state
   ride `fall` edges into the next case; direct entry and fallthrough entry
   join when both are possible. A case whose pattern provably cannot match
   the selector value (integer interval, literal range, or enum
   discriminant identity) has its outgoing fall edge suppressed, which
   preserves the working unreachable-fall controls. Unreachable relations
   are never assumed: an unknown pattern relation leaves the case possible.

The dependency: the enum reachability proof survives only when a call that
does not change the enum global keeps its fact (empty summary) and a call
that changes it drops the fact (written set). The prior experiment's
blanket "clear mutable-global enum facts on every call" rejected the valid
empty-function control; the summary mechanism is what resolves that
blocker, recorded in
[ENUM-REPORT](../../2026-09-20-core-v1/saf3-candidate-evidence/ENUM-REPORT.md).

## Soundness rules

- Callee resolution is by declaration identity, never by name text alone:
  the callee must be a bare identifier, the name must not be shadowable by
  any local binding (parameters, variables, constants, nested function
  names, and match captures of the enclosing function, with nested
  functions inheriting enclosing names), and the name must resolve in the
  global scope to a `FUNCTION` symbol whose declaration node carries a
  summary. Anything else is unbounded.
- Unbounded callees: function values (`h := f; h()`), local aliases
  (including one named like a pure global function — the adversarial probe
  `u_saf6_shadow_named_pure`), module-qualified non-stdlib calls, and
  unknown names. Each invalidates every mutable-global fact.
- Stdlib calls are trusted only through `stdlib_canonical`, which the type
  checker sets through scoped symbol lookup to a stdlib MODULE symbol; the
  compiler stdlib cannot name a user global.
- The may-write fixpoint runs on a finite lattice, so it terminates and
  stays sound even if a call cycle ever reached this pass; the A7 source
  recursion ban is not a load-bearing assumption for termination.
- Deletion and assignment inside a callee's own `defer` count as writes.
  Writes through fields (`g.f = 0`) do not count, matching the existing
  rule that identifier-keyed facts are never derived from field values.
- Scope-exit and loop-entry invalidation observe callee writes
  (`_call_global_writes_in`): a `defer { f() }` whose `f` writes `g`
  poisons `g` after the block, and a call in a loop body poisons the
  global at loop entry. A deferred call is not havoced at its registration
  site, because it has not run there; uses before scope exit stay valid
  (`c_saf6_defer_use_before_exit`).

## Evidence

All under [safety-candidate-evidence](safety-candidate-evidence/):

- [probe-results.json](safety-candidate-evidence/probe-results.json) — 42
  probes with sources, SHA-256 hashes, before/after exit codes and errors,
  and native results. 19 unsafe probes (including the original SAF-6
  `p07_global_changed_by_call` and SAF-3 `p26_fall_zero_divisor` shapes)
  were compile-only: their generated Zig was never built or executed. 20
  safe controls accepted by the candidate were built with
  `zig build-exe -O Debug` and `-O ReleaseFast` and executed; every stdout
  and exit code matched the independently stated expectation. Branch,
  defer, loop, call-argument-order, scrutinee-reassignment and
  equal-join-retain interactions are covered. Harness:
  `tmp/resume-safety-candidate/probes/run_probes.py`.
- [candidate-diagnostics.json](safety-candidate-evidence/candidate-diagnostics.json)
  — the rejection diagnostic for every rejected probe.
- [sweep-results.json](safety-candidate-evidence/sweep-results.json) — the
  13 original critical probes re-run verbatim (only `p07` and `p26`
  changed, both to exit 6; SAF-2/4/8 lanes unchanged) and the 255-file
  tracked-or-nonignored corpus with zero exit-code changes. Harness:
  `tmp/resume-safety-candidate/probes/run_sweep.py`. Nothing was executed
  natively in the sweep.
- [saf36-candidate.patch](safety-candidate-evidence/saf36-candidate.patch)
  — `diff -u` of production `a7/safety.py` against the candidate copy.
- [candidate-hashes.txt](safety-candidate-evidence/candidate-hashes.txt)
  and
  [production-baseline-hashes.txt](safety-candidate-evidence/production-baseline-hashes.txt).
  Production `a7/safety.py` is unchanged at
  `6a8c5f12…c34169` (same hash as the after-SAF-4 baseline); candidate
  `2868aee9…74231`.
- Test suite: full pytest in the candidate copy — 2215 passed, 2 failed.
  Both failures (`test_iterative_traversal.py` low-recursion nested
  expressions, `test_no_recursion.py` stale KNOWN_RECURSIVE_GROUPS list)
  fail identically on the unmodified production tree; they are baseline
  failures, not candidate regressions.

### Native controls (executed)

| Control | Debug / ReleaseFast stdout | Exit |
| --- | --- | --- |
| `c_saf6_noop` (empty call keeps global fact) | `2\n` | 0 |
| `c_saf6_unrelated_global` (callee writes a different global) | `2\n` | 0 |
| `c_saf6_transitive_pure` (pure wrapper call) | `2\n` | 0 |
| `c_saf6_stdlib_between` (`io.println` between fact and use) | `start\n2\n` | 0 |
| `c_saf6_call_then_reestablish` / `c_saf6_guard_after_call` | `2\n` / `` | 0 |
| `c_saf6_loop_guard_relearned`, `c_saf6_noop_loop` | `2\n2\n` | 0 |
| `c_saf6_arg_eval_order` (division in argument, writing callee) | `2\n` | 0 |
| `c_saf6_defer_use_before_exit`, `c_saf6_defer_stmt_use_before_exit` | `2\n` | 0 |
| `c_saf3_int_unreachable_fall`, `c_saf3_range_unreachable_fall` | `2\n` | 0 |
| `c_saf3_nonzero_fall`, `c_saf3_fall_chain_nonzero` | `3\n` | 0 |
| `c_saf3_fresh_guard_after_fall` | `2\n` | 0 |
| `c_saf3_enum_local`, `c_saf3_enum_global_noop` | `2\n` | 0 |
| `c_saf3_enum_scrutinee_reassigned`, `c_saf3_enum_branch_equal` | `2\n` | 0 |
| `c_saf3_unreachable_delete_fall` | compile-only (see below) | — |

`c_saf3_unreachable_delete_fall` is accepted by both compilers but its Zig
does not build on either: the backend lowers `del p` inside a match case to
a capture that shadows the outer constant (pre-existing backend defect,
identical bytes of failure before and after).

## Compatibility rejection requiring approval (L24)

One class of working programs is newly rejected. Exact example
(`r_fnvalue_pure` in probe-results.json):

```a7
io :: import "std/io"

g: i32 = 5

noop :: fn() {
}

main :: fn() {
    g = 5
    h := noop
    h()
    y := 10 / g
    io.println("{}", y)
}
```

Before: exit 0; the production artifact builds in Debug and ReleaseFast and
prints `2\n` with exit 0 (recorded in `native_before`).
After: exit 6, `Divisor not proven non-zero`.

Scope of the rejection: only programs that (a) establish a mutable-global
fact (guard or assignment), then (b) call through a function value or local
alias, then (c) use that fact in a risky operation, all without
re-establishing it. A call through an alias with no intervening global-fact
use stays accepted (`r_fnvalue_no_fact_used`). The 255-file corpus contains
no such program (zero exit changes). A sound precise treatment needs
function-value alias tracking (binding the alias to the declaration and
invalidating on reassignment); that is deliberately out of this batch.
Under L24 this rejection needs explicit approval before the candidate is
applied. Per the language-change rule, the recorded research and this
document are not approval.

## Known limits, not claimed fixed

- Callee writes through `ref` parameters to caller locals (MTH-2 / KNOWN S3
  for locals) remain untracked; this candidate covers mutable globals only.
- The loop model is still single-pass (KNOWN S2). Loop-entry now forgets
  globals written by body callees, which catches use-before-call-in-loop,
  but a fact established before the loop and used in the body after a
  conditionally-skipped call remains analyzable only in visit order.
- Module-qualified calls to non-stdlib functions are unbounded (invalidate
  all mutable-global facts). No corpus program regressed.
- `del` inside a match case still fails to build natively on both compilers
  (backend defect above).
- Unreachable case bodies still contribute to the match-exit join; this
  weakens facts exactly as the current production compiler does.

## Reproduction

```
.venv/bin/python tmp/resume-safety-candidate/probes/run_probes.py
.venv/bin/python tmp/resume-safety-candidate/probes/run_sweep.py
```

The candidate copy at `tmp/resume-safety-candidate/` preserves the dirty
working tree as it stood (rsync of the live tree, excluding `.git`, `tmp`,
`site`, `.venv`, `docs`, build outputs); only its `a7/safety.py` and the
`probes/` harness differ from production. No commits were made.
