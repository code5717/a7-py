# SAF-3 isolated reachability experiment

Status: NOT READY TO APPLY. Main compiler and tests are unchanged.

The candidate carries fallthrough exit facts and moved bindings into the next
case. Integer literal and range facts distinguish direct entry from impossible
fallthrough edges. Cases still receive their previous checks even when their
outgoing fallthrough edge is known unreachable. This does not implement new
syntax, runtime checks or a new language policy.

## Results

| Case | Baseline exit | Candidate exit |
| --- | ---: | ---: |
| Original zero divisor after fall | 0 | 6 |
| Deferred zero assignment before fall | 0 | 6 |
| Integer unreachable-fall control | 0 | 0 |
| Nonzero assignment before fall | 0 | 0 |
| Fresh guard after fall | 0 | 0 |
| Two-case fall chain with zero divisor | 0 | 6 |
| Two-case fall chain with nonzero divisor | 0 | 0 |
| Delete followed by fall and use | 0 | 6 |
| Unreachable delete/fall control | 0 | 0 |
| Deferred delete followed by fall and use | 0 | 6 |
| Integer-range unreachable-fall control | 0 | 0 |
| Enum unreachable-fall control | 0 | 6 |

The enum control is a verified compatibility regression and blocks this patch.
Exact source:

```a7
// probe: compile-only
io :: import "std/io"

Choice :: enum { First, Second }
main :: fn() {
    x := 5
    k := Choice.Second
    match k {
        case Choice.First: {
            x = 0
            fall
        }
        case Choice.Second: {
            io.println("{}", 10 / x)
        }
    }
}
```

The original compiler emits Zig that builds in Debug and runs with exit 0,
stdout `2\n` and empty stderr. The candidate rejects with semantic exit 6 and
`Divisor not proven non-zero`. Case `Choice.First` never runs because the selected
value is `Choice.Second`, so its zero assignment must not enter the selected
case's facts.

`enum-safe-native.json` preserves the native build command and result.
`additional-results.json` preserves compiler commands, source and full output.
`results.json` records the first five cases and the integer safe native control.
No unsafe generated program was built or executed. Native execution was limited
to the integer and enum controls whose selected case bypasses the invalid path.

## Required design work

The integer candidate cannot classify enum case reachability. The current
`ValueFact` has an enum discriminant field, but normal enum-member expressions
do not establish it for these uses. A complete candidate must derive and
propagate known enum values, preserve them only across valid copies and joins,
and invalidate them on assignments, calls and aliases that may change them.
It must compare typed enum identities and variants, not bare matching strings.

Keep the match scrutinee snapshot separate from variables changed inside cases:
the backend evaluates the scrutinee once. Account for first matching case,
multiple patterns, literal ranges, captures and unknown selectors. Unknown
reachability must not be treated as a proven impossible edge. Preserve scope
cleanup and deferred deletes before carrying state into the next case.

Run the valid enum control and changed-enum invalidation controls before any
compatibility claim. Boolean, string and named-constant selectors also need
explicit reachability coverage. Existing global-call invalidation gaps may
invalidate assumptions used by reachability; do not use stale facts to suppress
a real fallthrough edge. No new policy or runtime fallback is selected here.

This remains a prototype, not a corpus-qualified correction. No 255-file
compatibility sweep was performed for this candidate because the concrete valid
control already fails. The proposed fix needs further design and verification.
