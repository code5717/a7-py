# Original critical safety probes and SAF-2 candidate

After integrating SAF-4, nine of the same 13 original probes reject with semantic
exit 6. Four still compile and emit Zig. No unsafe generated program was built
or executed.

The [post-SAF-4 results](critical-safety-after-saf4.json) retain exact sources,
source SHA256 values and all 32 compiler-file hashes before and after the rerun.
Every compiler-file hash stayed unchanged during these checks. The sole outcome
change is `p03_early_return_else_assign`, which changed from exit 0 to exit 6,
reports `Divisor not proven non-zero` and leaves no Zig artifact. This closes
that original SAF-4 trigger, not every possible control-flow safety defect.

SAF-2, SAF-3's fallthrough case, SAF-6 and SAF-8 remain open and accepted. All
other selected probe results are unchanged. The table below retains the initial
pre-SAF-4 results; [the original sources and results](critical-safety-revalidation.json)
preserve that earlier comparison.

| Finding | Initial result before SAF-4 integration |
| --- | --- |
| SAF-2, arbitrary field named `ptr` | Accepted |
| SAF-3, match case fact leakage, two cases | Both reject |
| SAF-3, `fall` followed by zero divisor | Accepted |
| SAF-4, early-return guard followed by else assignment | Accepted |
| SAF-5, quotient incorrectly known nonzero | Rejects |
| SAF-6, call mutates global divisor | Accepted |
| SAF-8, repeated field deletion | Accepted |
| SAF-11, original arithmetic interval finding, three cases | All reject |
| SAF-26, unbraced else leakage, two cases | Both reject |

These results revalidate the listed triggers only. They do not close every
variant or establish native behavior.

## SAF-2 isolated candidate

The spelling-only rule in `a7/safety.py` marks every field called `ptr` non-null.
An isolated one-line candidate restricts that rule to a slice's actual pointer
field. The type checker exposes `.ptr` on slices; string fields are not newly
introduced by this candidate.

The candidate rejects the original nil-field dereference. Renaming that field
to `link` already rejects on the baseline. A scalar field named `ptr` remains
usable. A guarded local reference read from the field, plus an actual slice
pointer, runs with output `7`, `9`, `2` in Debug and ReleaseFast.

The first four candidate tests passed. Against the baseline, the same tests had
one expected failure for the unsound `ptr` field and three passes. A 255-file
repository A7 comparison accepted 135 files before and after, with no changed
exit status or emitted Zig. This excludes temporary probes and test-source
strings and does not establish compatibility.

A further valid control exposed a compatibility regression:

```a7
io :: import "std/io"
Inner :: struct { value: i32 }
Outer :: struct { ptr: ref Inner }
main :: fn() {
    allocated := new Inner
    if allocated != nil {
        allocated.value = 7
        o := Outer{ptr: allocated}
        if o.ptr != nil { io.println("{}", o.ptr.value) }
        del allocated
    }
}
```

The baseline builds and prints `7`. The candidate rejects with semantic exit 6
because current guard facts only track identifier names, not field paths. The
added fifth test deliberately records this failure. The patch must not be
applied in its present form.

Evidence and the unapplied patch are in
`tmp/saf2-candidate-qnlak3ib/`. `summary.json` records the corpus result;
`direct-guard-results.json` records the compatibility case;
`saf2-not-ready.patch` contains the isolated change and tests. No main compiler
or test files were changed.

## Approval boundary

`docs/plan/execution.md` labels P0b revision 3 approved and lists SAF-2 under SD.
L24 in `docs/plan/decisions.md` separately requires a packet when a change alters
a program that compiles and works today. The direct-guard example does work.
No explicit approval for rejecting this example was located. The controlling
session therefore required preserving that behavior or presenting its change;
the current candidate is blocked by the compatibility regression.

A preliminary native control also hit the existing Zig capture-shadowing defect
when the allocation was named `p`. Renaming the test allocation to `allocated`
avoided that separate defect. The candidate makes no claim to repair it.
