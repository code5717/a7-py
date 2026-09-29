# Guide content verification

The initial documentation verification ran on 2026-09-19 with Zig 0.16.0.
The focused probe tables below were refreshed after the authorized compiler
repairs. The example-suite result remains the earlier run described separately.
The checkout had pre-existing compiler and documentation modifications. Results
therefore describe that working tree, not an immutable release revision.

## Source review

The guide content was checked against `README.md`, `docs/RELEASE.md`,
`docs/STATUS.md`, `a7/cli.py`, `a7/compile.py`, the standard-library registry,
stdlib call validation in `a7/passes/type_checker.py`, Zig lowering, all example
filenames, the tour and generic sources, and output fixtures.

The release command sequence now retains the repository working directory with
subshells for site commands. Bun is a contributor dependency, not a requirement
for compiling A7. The example index includes every current top-level `.a7` file
and links each actual golden output fixture. The guides distinguish expected
output from compiler progress and separate compile from native execution.

## Native example verification

Command, run from `site/`:

```bash
uv run python ../scripts/verify_examples_e2e.py --json-report docs/examples-verification.json
```

Result: exit 0, `Examples verified: 43/43`. Each result checks A7 compilation,
Zig AST validation, native build, native execution, and comparison with the
existing golden fixture. This includes the hello, complete tour, generic
function and struct, and math module examples. No golden fixtures changed.
See [the JSON report](examples-verification.json).

## Focused stdlib and CLI probes

Reproduce from the repository root:

```bash
uv run python site/docs/verify-content.py
```

The probe script asserts expected compile stages and native stdout, including
the repaired brace and signed absolute-value cases. Inspect each result in
[content-probes.json](content-probes.json). Temporary source is retained in
that report; the temporary build directories are removed after the run.

| Probe | A7 result | Native result or diagnostic |
| --- | --- | --- |
| All eleven math calls with ordinary valid inputs | exit 0 | exit 0; stdout `2 4 1 2 0 1 0 0 1 2 3` plus newline |
| `print`, `println`, `eprintln`, including empty calls | exit 0 | exit 0; expected stdout and stderr streams |
| `math.sqrt(4)` | exit 6 | Integer argument rejected; requires `f32` or `f64` |
| Nonliteral io format string | exit 6 | Format string literal restriction |
| Placeholder with no corresponding argument | exit 6 | Wrong argument count |
| `math.sqrt_f64(4.0)` | exit 6 | Unknown stdlib call |
| `io.println("{{}}")` | exit 0 | exit 0; stdout `{}` plus newline |
| `fn(x: i32) i32` returning `math.abs(x)` | exit 0 | exit 0; stdout `4` plus newline for input `-4` |
| All six CLI modes on hello | exit 0 | JSON status `ok`, schema `2.0`, stage and artifact fields inspected |

The escaped-brace and signed-absolute-value failures recorded in the original
language audit are repaired for these inputs. The minimum signed absolute-value
input remains unqualified. The historical audit artifacts retain the original
diagnostics.

The guide lists the current CLI flags based on `uv run a7 --help` and
`a7/cli.py`. The mode probes confirm that `pipeline` has no default artifact,
`compile` writes Zig, and `doc` writes Markdown. Broader error-stage testing and
the full release gate remain the coordinating session's verification work.

## Limits

The math probe checks one ordinary input per operation. It does not establish
all numeric types, domain boundaries, non-finite behavior, overflow behavior,
or general signed-integer absolute-value composition. The guides state those
limits. This report does not claim browser, accessibility, deployment, or full
release-gate acceptance; those require separate integrated evidence.

## Independent reference audit

After the first content pass, a second review inspected all twelve language
reference pages against their intended coverage. Function types and callbacks,
C-style loops, labeled breaks and continues, match alternatives and ranges,
match expressions with captures, restricted fallthrough, arrays, slice lengths,
string slicing, and generic constraints now have concrete examples in addition
to descriptions and evidence links.

Reproduce the additional source probes from the repository root:

```bash
uv run python site/docs/verify-reference-content.py
```

See [reference-probes.json](reference-probes.json) for source and actual results.

| Probe | Result |
| --- | --- |
| Raw function type, alias, callback argument | A7 exit 0, Zig run exit 0, stdout `11 11` |
| Non-final match case ending in `fall` | A7 exit 0, Zig run exit 0, stdout lines `one` and `two` |
| Match expression with capture | A7 exit 0, Zig run exit 0, stdout `5` |
| Literal, alternative, and range match patterns | A7 exit 0, Zig run exit 0, stdout `range` |
| Slice indexing/length, fixed-array addition, character-slice iteration | A7 exit 0, Zig run exit 0, stdout lines `20 2`, `4 6`, `A 1` |
| Zero-initialized fixed array and nested array literal | A7 exit 0, Zig run exit 0, stdout `0 3` |
| Direct `string.len` access | A7 exit 6, field access on non-struct `string` |
| Scalar-fill fixed-array initialization | A7 exit 6, array/scalar type mismatch |
| Top-level local `@type_set` alias | A7 exit 7, unsupported `TYPE_SET` codegen node |
| Predefined `Numeric` generic constraint | A7 exit 0, Zig run exit 0, stdout `42` |
| Inline `@type_set(i32, i64)` generic constraint | A7 exit 0, Zig run exit 0, stdout `42` |

The array, declaration, generic, and builtin pages now state the observed
restrictions. Earlier specification-derived claims of scalar-fill support and
direct string length access were removed. Local type-set aliases are explicitly
separated from the predefined and inline constraints that reached native execution.
The module page has source and restriction coverage, but no new cross-module
qualification claim was added by this audit.

`python3 scripts/check_docs_style.py` passed after these changes. Local links in
the ten guides were checked against Markdown targets and repository source files.
