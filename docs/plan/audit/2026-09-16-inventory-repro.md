# Wave 0: inventory reproduction and compatibility scan

Status: authored summary, 2026-09-16. It records what the known defects do at commit
`701c679`; it decides nothing. The defect list derived from it is in the
[v1 plan](../README.md#defects-reproduced-in-wave-0). Packets that ask for decisions
are in [packets](../packets/).

## Evidence

| File | Content |
| --- | --- |
| [Ledger part 1](evidence/2026-09-16-ledger-part1.md) | Frontend, CLI, typing and backend items (F, T, B) and the failing baseline tests |
| [Ledger part 2](evidence/2026-09-16-ledger-part2.md) | Safety and memory items (S), docs claims (D), compatibility scan (parts C and D) |
| [Baseline](../../audits/2026-09-16/baseline.md) | Full gate before any change: 11 of 12 checks pass, 12 known failing tests |

Both ledgers are preserved verbatim. The probe programs, emitted Zig and logs they
cite are under `tmp/`, which is not tracked.

## Method

- Every probe starts with `// probe: compile-only` or `// probe: run-allowed`.
  Compile-only probes were checked with `zig build-obj -fno-emit-bin` and never
  built into executables or run. Run-allowed probes were built in Debug and
  ReleaseFast and run; only five were (B1, B14, S13 and two D7 probes).
- `zig ast-check` misses some type errors, such as `==` on `[]const u8`, so every
  Zig result uses `zig build-obj -fno-emit-bin` on the emitted file.
- The compatibility scan captured the 2105 unique A7 sources that pytest passes to
  the compiler, plus the 43 examples and the code blocks in the docs (2216 programs
  in part D). Each proposed rule ran as a strict copy of the safety pass and was
  diffed against the real pass. Every detector was first confirmed on a probe.

## Results

| Ledger | Items | Reproduced | Not reproduced | Different |
| --- | --- | --- | --- | --- |
| Part 1 (F, T, B) | 28 rows | 27 | 1: the `é` identifier diagnostic is already correct | 0 |
| Part 2 A (S) | 13 | 11 | Negative-operand integer folding matches run time (S13 part) | S11 slice parameters type-check but always fail the bounds proof |
| Part 2 B (D) | 9 | 9 | 0 | 0 |

Findings not in the earlier inventory:

- Local variables holding string literals compared with `==` build and compare
  addresses [B3].
- A function-pointer field call on a local struct named `math` becomes `@sqrt`
  [B14].
- `x := 5; x -= 5; y := 10 / x` is approved: compound assignment records the
  right-hand value [part A note, part D].
- `-7.5 % 2.0` folds to `0.5`; run time gives `-1.5` [D7].
- `.len` on a fixed array or string is rejected [S12]; a literal argument to a
  `usize` parameter is rejected [C6 note].

## Compatibility scan

| Proposed change | Programs affected |
| --- | --- |
| Block facts survive block exit | 0 |
| Loop-body assignments drop facts at loop entry | 5 examples: 029, 030, 032, 041, 042 |
| Escape-aware call invalidation | 0 |
| Compound assignment updates facts (interval variant), alone | 0 |
| The same, combined with the block rule as scanned (facts dropped at an `if` join) | 1: `examples/026_binary_tree.a7:62`. A join that keeps the range of both branches was not scanned; it would keep `top` in `[0, 1]` (inference) |
| Compound assignment drops the fact | 1: `examples/026_binary_tree.a7:49, 56, 62` |
| Returned local slice, double `del`, `del` through `ref` | 0 |
| Rejecting non-foldable string `==` | 0 (doc conflict `docs/SPEC.md:537`) |
| Rejecting untyped globals that Zig rejects | 0 |
| Rejecting every untyped global | 2 tests and 7 doc snippets |
| Parse errors always fail; file-scope statements rejected | `examples/003_comments.a7`, 3 tests, 4 SPEC snippets |
| Accepting `ret 0` from `u32` and `usize` | 0 |

The five examples affected by the loop rule are correct programs that today are
approved for the wrong reason; packet P0b explains the choice.

Part E measured the rules as they would be implemented, over 2440 programs (Part D's
2216 plus 224 code blocks from `site/public/llms-full.txt` and `docs/lang-safety/`):

| Rules combined | Programs affected |
| --- | --- |
| Block and branch facts joined as the range of all paths | 0 |
| The same, plus compound assignment computed as a range | 0 |
| The same, plus escape-aware call invalidation | 0 |
| The same, plus the loop rule that drops facts | 6 examples (026, 029, 030, 032, 041, 042) and `docs/lang-safety/edge-cases/03-definite-assignment.md:206` |
| The same, plus a fixpoint loop rule with widening and bounds from loop conditions | 2 examples: `026_binary_tree.a7:49, 56, 62`, `030_calculator.a7:62` |

Probes also showed that today a `while i < 10` loop indexing a 5-element array with
`i` is approved and builds. Extra docs hits for other rules: `z := z` and
`dynamic: [n]u8` in `docs/lang-safety/` (rejecting them); five `ret 0` sites in
`docs/lang-safety/` whose "Rejected (exit 6)" comments go stale (accepting `ret 0`);
six code blocks in `docs/lang-safety/` affected by parse strictness.
