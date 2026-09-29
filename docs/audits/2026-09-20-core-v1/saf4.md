# SAF-4 isolated repair verification

The isolated repair rejects the original early-return/else-mutation trigger.
All 255 tracked or nonignored `.a7` files retain the same compiler exit code
and error payload. The patch is prepared outside the active checkout; this
report does not claim the integrated compiler or full release gate passed.

## Defect and repair

The [original source](saf4-evidence/original-source.json) returns when `v == 0`,
but its continuing `else` branch assigns `v = 0`. The current compiler still
approves `10 / v` afterward. It exits 0 and emits division by the zeroed value.
The unsafe program was never built or executed natively in this verification.

The `IF_STMT` visitor already applies each guard before visiting its branch and
retains the continuing branch's final facts when the other branch returns.
The later `_learn_after_stmt` call reinstates the old negated guard and overwrites
the mutation's effect. The [patch](saf4-evidence/saf4.patch) removes that call and
its obsolete helper. It adds no new language rule or recursive traversal.

After the repair, the original exits 6 with `Divisor not proven non-zero` at
line 11. The regression checks semantic JSON diagnostics and absence of the
requested Zig file. Additional cases replace the assignment with a mutating
reference call or deferred assignment. They are also rejected before native
output.

## Safe controls and compatibility

The accepted controls cover an early return without `else`, an unchanged `else`,
a nonzero assignment and a fresh guard after mutation. Real Zig execution in
Debug and ReleaseFast produces exactly `5 5 5 0 0` followed by a newline.

Before and after package copies compiled the 43 repository examples in pipeline
mode. All remained accepted. The original trigger alone changed from exit 0
to exit 6 in that [comparison](saf4-evidence/compatibility.json).

A broader scan enumerated source with:

```bash
git ls-files -z --cached --others --exclude-standard -- '*.a7'
```

It deduplicated existing files and compiled each through both isolated package
copies using `--mode pipeline --format json`. The
[summary](saf4-evidence/corpus-summary.json) records 255 files, zero exit-code
changes and zero error-payload changes. Source hashes remained unchanged across
the scan. The [per-file record](saf4-evidence/corpus-compatibility.json) retains
hashes, exit codes and errors. No corpus program was executed natively.

This scan does not include A7 embedded in Python tests or Markdown fences and
does not repeat the historical 2,440-program scan. It cannot prove that every
previously working program retains acceptance.

## Checks and authorization

The isolated interpreter used the active environment's dependencies. Executed:

```bash
python -m pytest test/test_saf4_early_return.py test/test_audit_safety_repairs.py -q
python -m pytest test/test_safety_precursors.py -q
```

Results: [21 passed](saf4-evidence/focused-tests.log) and
[22 passed](saf4-evidence/precursor-tests.log).
[Hashes](saf4-evidence/hashes.json) identify the before/after safety source and
the added test. No active compiler or test file changed while the release gate
was running.

`docs/plan/execution.md` identifies S1 as approved P0b revision 3 and names
deletion of `_learn_after_stmt` for SAF-4. It assigns the behavior to P0b.13.
The older packet file still says proposed revision 2; that historical mismatch
does not establish approval by itself. L24 distinguishes crash and miscompile
repairs from changes to working programs. The controlling session confirmed
that this repair falls within the existing crash/miscompile and branch-fact
correction scope, subject to compatibility verification.

Previously accepted source that relies on the invalidated guard now fails.
Valid nonzero assignments and fresh guards remain accepted in the tested
controls. Syntax, numeric policy and lifetime rules are unchanged. General
branch, alias and lifetime safety remain separate work. Integration completed in the second combined release gate. GLM review 3 passed
the repair and seven independent probes. The later safety revalidation still
records SAF-2, SAF-3, SAF-6 and SAF-8 as open.
