# Production readiness audit

Component: everything between "the compiler works" and "a language people can
ship with", excluding the language surface. Finding prefix `PRD`.
Auditor: independent read-only pass, 2026-09-18.

Tree audited: main working tree with the uncommitted batches C3, PR-00, T0, V1,
NOREC-0 and PL-02 applied. C1, C4 and C2 are in flight in worktrees under
`/home/cx89/Projects/pl-dev/a7-wt/` and were **not** audited.

Environment: `uv 0.12.15`, `zig 0.16.0` (`tmp/audit/2026-09-18/production/env.txt`),
`uv run a7` resolves to the working tree (`/home/cx89/Projects/pl-dev/a7-py/a7/__init__.py`,
`tmp/audit/2026-09-18/production/whichA7.txt`) on CPython 3.13.15.
Probes and raw output: `tmp/audit/2026-09-18/production/`.

The full gate (`run_all_tests.sh`, `scripts/build_examples.py`,
`scripts/verify_examples_e2e.py`, `uv build`) was **not** re-run: it writes
`build/`, `dist/` and `a7_py.egg-info` outside this audit's scratch, and other
auditors are working in the same tree. Gate results are cited from
`docs/audits/2026-09-16/baseline.md`.

## The headline

A7 today is a source-to-source translator with one entry point, `a7 <file.a7>`,
that writes a `.zig` file. Everything a user needs after that — producing a
binary, reading a diagnostic in an editor, setting a breakpoint, knowing which
compiler version built an artifact, being warned about anything — either does
not exist or is not documented. The single most damaging defect is that
`a7 x.a7 -o x.a7` silently overwrites the user's source with generated Zig and
exits 0.

## Summary

| Severity | NEW | KNOWN | Total |
| --- | --- | --- | --- |
| CRITICAL | 1 | 1 | 2 |
| HIGH | 11 | 5 | 16 |
| MEDIUM | 10 | 6 | 16 |
| LOW | 3 | 1 | 4 |
| **Total** | **25** | **13** | **38** |

Areas 4 (release, packaging, CI) and 6 (documentation) were surveyed by two
read-only assistants working from the same rules; every claim reproduced from
their reports below was re-verified directly by this auditor with the command
shown, except where marked UNVERIFIED.

## Findings

### PRD-1. CRITICAL. KNOWN (PIP-12; baseline failures #1 and #2). `--output` or `--doc-out` equal to the input destroys the source and exits 0

`compile.py:151` accepts any `output_path` and `compile.py:441-442` opens it for
writing without ever comparing it with `input_path`; the `--doc-out` write at
`compile.py:471` does the same.

Probe `tmp/audit/2026-09-18/production/p1/selfdest.a7`:

```
uv run a7 .../p1/selfdest.a7 -o .../p1/selfdest.a7
exit=0
Compiled .../selfdest.a7 -> .../selfdest.a7 (580 bytes, 2 ms)
head -3 selfdest.a7:
const std = @import("std");
var __a7_io: ?std.Io = null;
fn __a7_stdout_print(comptime fmt: []const u8, args: anytype) void {
```

The same with `--doc-out .../selfdoc.a7` replaced the source with a markdown
report (`p1/c.out`, exit 0). Both baseline tests still fail today:
`test_pipeline_artifacts.py::test_cli_rejects_input_destination_without_changing_source[--output]`
and `[--doc-out]` (`tmp/audit/2026-09-18/production/pytest_pipeline.txt`,
8 failed, 3 passed).

**Fix direction.** Reject a destination that resolves to the input path or to
any loaded module file, as a usage error, before any stage runs. Owner: batch
**CLI-01** (`docs/plan/execution.md:132`).

**Changes accepted programs?** No — it rejects a destructive invocation, not a
program.

### PRD-2. HIGH. NEW. None of the five promised workflow commands exists, and `--version` is a usage error

`docs/STATUS.md:25-26` lists as an active priority: "Add workflow commands:
`a7 check`, `a7 build`, `a7 run`, `a7 doctor`, and `a7 --version`". `a7/cli.py`
defines one positional (`file`, :21) and five options (`--mode`, `--format`,
`-o`, `--doc-out`, `--backend`, `-v`). No subcommand parser exists.

Probed (`tmp/audit/2026-09-18/production/p1/cmd_*.out`):

| Command | Exit | Output |
| --- | --- | --- |
| `a7 check` | 3 | `error: Input file not found: check` |
| `a7 build` | 3 | same shape |
| `a7 run` | 3 | same shape |
| `a7 doctor` | 3 | same shape |
| `a7 --version` | 2 | `a7: error: the following arguments are required: file` |
| `a7 --version hello.a7` | 2 | `a7: error: unrecognized arguments: --version` |

Each promised command is read as a source filename. No plan row owns them:
`grep -rn "a7 doctor\|a7 run\|a7 check\|a7 build\|a7 --version\|a7 test"
docs/plan/execution.md docs/plan/README.md docs/plan/decisions.md` returns
nothing.

**Fix direction.** A subcommand layer over the existing `CompileMode`, plus
`--version` reading `a7.__version__`. `a7 doctor` needs a Zig probe, which the
compiler does not have today (PRD-5). These commands fix distribution, not
correctness: none of them would surface PRD-33 or the doc drift in PRD-35.

**Changes accepted programs?** No.

### PRD-3. HIGH. NEW. There is no documented path from a user's `.a7` file to a binary

`README.md:34-38` documents compiling to Zig
(`uv run python main.py examples/001_hello.a7` → `examples/001_hello.zig`).
The only native build path documented is `scripts/build_examples.py`
(`README.md:82-87`), which builds the repository's `examples/` directory, not a
user program. `grep -n "zig build-exe" README.md` returns nothing.

The commands a user must actually run — none of which any document states —
are, verified end to end in `tmp/audit/2026-09-18/production/dbg/`:

```
uv run a7 hello.a7 -o hello.zig          # exit 0
zig build-exe hello.zig -ODebug -femit-bin=hello_dbg   # exit 0
./hello_dbg
```

The flags are recoverable only by reading `scripts/build_examples.py:104-112`
and `:20-27` (`-ODebug` / `-OReleaseFast`), which also runs
`zig fmt --check` on the generated file first (`:100`).

**Fix direction.** Either `a7 build` / `a7 run` (PRD-2) or, minimally, a
README section with the literal three commands.

**Changes accepted programs?** No.

### PRD-4. HIGH. KNOWN (PIP-11; baseline failure #8). A semantic error inside an imported module is attributed to the importing file, at a line that is not the error

Probe `tmp/audit/2026-09-18/production/p4/`: `proj/main_sub.a7` imports
`sub/lib.a7`; the undefined call `nope()` is at `sub/lib.a7:3`.

```
uv run a7 .../proj/main_sub.a7 --format json     exit=6
detail.file    = .../proj/main_sub.a7
detail.message = main_sub.a7:3:9: Undefined type (Identifier 'nope')
detail.span    = {start_line: 3, start_column: 9, end_line: 3, end_column: 13}
```

`main_sub.a7:3` is `main :: fn() { x := l.two() }`. The record is internally
inconsistent: the span is the offset inside `lib.a7`, while `file` and the
message prefix name the importer. An editor that jumps to `file` + `span` lands
on unrelated code. Cause: `compile.py:256-261` merges module declarations into
one program and every pass is then given `str(input_path)` as its filename
(`compile.py:271, 316, 334, 349`).

The 33-file import chain probe (`limits/chain/`) reproduces the same shape:
three errors, all reported at `main.a7:4:9`, for a name (`m1`) that appears only
in `mod0.a7`.

**Fix direction.** Carry the origin file on each declaration through the merge.
Owner: batch **CLI-02**, which `docs/plan/execution.md:132` records as needing
the S2 origin hook.

**Changes accepted programs?** No.

### PRD-5. HIGH. NEW. The compiler never checks for Zig, never checks its version, and emits Zig-0.16-only APIs with no guard

`grep -rn "subprocess\|shutil.which" a7/` returns nothing: no code path in the
compiler package invokes or probes `zig`. Only `scripts/` does
(`scripts/build_examples.py:285` `if not shutil.which("zig")`), and that script
checks presence, not version.

The generated preamble uses Zig 0.16 APIs unconditionally
(`tmp/audit/2026-09-18/production/dbg/hello.zig:2,5,9`):
`var __a7_io: ?std.Io = null`, `std.Io.File.stdout().writerStreaming(...)`,
`pub fn main(init: std.process.Init) void`. Nothing in `a7/backends/zig.py`
emits a `builtin.zig_version` check.

Consequence, INFERENCE and UNVERIFIED (only Zig 0.16.0 is installed here): on a
different Zig the user's first error is a Zig compile error inside a preamble
they never wrote, with no statement that a version is required. `a7 doctor`,
the command that would report this, does not exist (PRD-2).

**Fix direction.** Emit a `comptime` version assert in the preamble with an A7
message, and add a Zig presence/version check to `a7 doctor`.

**Changes accepted programs?** No.

### PRD-6. HIGH. KNOWN (PIP-12; baseline failures #3 and #4). A failed compile advertises a stale artifact, and a write failure advertises the destination directory

`compile.py:912` gates the artifact on `Path(result.output_path).exists()`,
not on this run having written it.

Probe `tmp/audit/2026-09-18/production/p2/`:

```
uv run a7 ok.a7  -o stale.zig --format json     exit=0
uv run a7 bad.a7 -o stale.zig --format json     exit=6
  status    = "error"
  artifacts = {"output_path": ".../p2/stale.zig"}     <- the previous program
```

and, with the destination an existing directory:

```
uv run a7 ok.a7 -o dirout --format json         exit=3
  status    = "error"
  artifacts = {"output_path": ".../p2/dirout"}        <- a directory
```

A build script that reads `artifacts.output_path` after a failed compile builds
the previous program. Writing into a read-only directory behaves correctly
(exit 3, `artifacts` empty — `p2/e.json`).

**Fix direction.** Set `artifacts` only from a write this run completed. Owner:
batch **CLI-01**.

**Changes accepted programs?** No.

### PRD-7. HIGH. NEW. Nothing maps a compiled binary back to `.a7`; a debugger and a crash both show generated Zig

Verified on a debug build of `tmp/audit/2026-09-18/production/dbg/hello.a7`
(`zig build-exe hello.zig -ODebug`, exit 0):

- `objdump --dwarf=decodedline hello_dbg` names exactly one source file,
  `hello.zig`, at lines 3-21 (`dbg/lines.txt:64336-64372`).
- `strings hello_dbg | grep -c "\.a7"` → `0`. The A7 file name is nowhere in
  the binary.
- The A7 function `main` is emitted as `__a7_user_main`
  (`dbg/hello.zig:18`); `main` is the Zig entry wrapper
  (`dbg/hello.zig:9-12`). `break main` stops in the wrapper.
- A breakpoint on the A7 statement `x := add(2, 3)` (hello.a7:7) is not
  expressible; the corresponding location is `hello.zig:19`.

A runtime trap prints the generated file, verified with a controlled
`@panic` build in the same directory (`dbg/panic.err`, exit 134):

```
thread 1109491 panic: a7 stdout write failed
.../panicdemo.zig:2:18: 0x11d7fea in deep (panicdemo.zig)
fn deep() void { @panic("a7 stdout write failed"); }
                 ^
```

That is the shape of every A7 runtime failure: Zig source lines the user never
wrote, plus Zig stdlib frames. The compiler's own panic strings are already
A7-branded (`a7/backends/zig.py:173-174`), which is the only A7 marker a user
sees.

`grep -rln "panic" test/ scripts/` returns nothing: no test asserts anything
about runtime trap output.

**Fix direction.** Emit Zig `//` provenance comments now, and a real line map
with the IR. Owner: **SRC-MAP**, Wave 3 (`docs/plan/execution.md:157`). Note
that `docs/plan/audit/language-audit-checklist.md:70` records this as "Not in
plan", which is stale — SRC-MAP exists.

**Changes accepted programs?** No.

### PRD-8. HIGH. NEW. There are no error codes, no warnings, and no warning controls; SPEC Appendix B specifies all three

`docs/SPEC.md:2094-2100` defines five error-code families (E0xxx syntax, E1xxx
type, E2xxx lifetime, E3xxx generic, E4xxx module) and `:2122-2127` four
warning families (W0xxx unused, W1xxx deprecated, W2xxx performance, W3xxx
potential bugs). `grep -rn 'E[0-9][0-9][0-9][0-9]' a7/` returns nothing;
neither does a search for `W0`.

Beyond the missing codes:

- `ErrorSeverity` (`a7/errors.py:17-23`) declares `WARNING`, `INFO` and `NOTE`.
  The only consumer, `ErrorFormatter.format_error`, assigns
  `ErrorSeverity.ERROR` in all four branches (`a7/errors.py:464-471`) and then
  never reads the variable. The severity system is dead code.
- No pass emits a warning. `a7/symbol_table.py:40,289` carry `is_used` tracking
  and a `get_unused_symbols` helper "for warnings"; nothing calls them from a
  diagnostic path. `a7/passes/type_checker.py:620` comments "This is a
  warning-level issue, not an error" and does nothing.
- The only thing the compiler ever prints as a warning is `a7/parser.py:226-228`,
  a bare `print()` to stdout (see PRD-12).
- There is no `-W`, `--warn`, `--deny`, `--allow` or `--error-format` flag
  (`a7/cli.py:23-65`), so there is nothing to select, suppress or escalate.

SPEC B.2's seven lexer strings also drift from `a7/errors.py`: SPEC gives
`"Unexpected character: 'X'"` (`:2106`) where the compiler says
`"Invalid character"` (`errors.py:164`), and `"Invalid string escape sequence"`
(`:2110`) where the compiler says `"Invalid escaped char"` (`errors.py:174`).
SPEC B.2's format block (`:2114-2120`) is
`error: <message>, line: <line>, col: <column>` followed by `help:`; the
compiler prints `error: <message> [line N: col M]` (`errors.py:481-485`)
followed by `hint:` (`errors.py:516`). KNOWN as TOK-28 per
`docs/plan/audit/language-evidence-map.md:113`; the code-family and warning-system
half is NEW.

**Fix direction.** Either implement stable codes and a warning level, or delete
Appendix B.1 and B.3 and say diagnostics are identified by message. The
decision is the owner's; no gate or packet covers it.

**Changes accepted programs?** No.

### PRD-9. HIGH. KNOWN (PIP-24). Every diagnostic goes to stdout; stderr is empty on every failure

Verified in both formats at all four failing stages
(`tmp/audit/2026-09-18/production/p5/`):

| Probe | Exit | stdout bytes | stderr bytes |
| --- | --- | --- | --- |
| unterminated string, human | 4 | 1051 | 0 |
| `x := 1 +`, human | 5 | 157 | 0 |
| undefined name, human | 6 | 1183 | 0 |
| all three, `--format json` | 4/5/6 | payload | 0 |

`display_error`/`display_errors` (`a7/errors.py:912-942`) and the JSON path
(`compile.py:848`) both write to the module-level `Console()`
(`compile.py:32`), which is stdout. The single exception is the internal
catch-all at `compile.py:493`, human format only.

So `a7 prog.a7 2>errors.txt` produces an empty file, and any pipeline that
separates data from diagnostics by stream cannot. Spans are present and carry
1-based line and column at every stage (table above,
`p5/*.json`), so the data exists; only the stream is wrong.

**Fix direction.** Diagnostics to stderr. Owner: batch **X-RICH**
(`docs/plan/execution.md:132`, PIP-13 and PIP-24).

**Changes accepted programs?** No.

### PRD-10. HIGH. KNOWN (PIP-11; baseline failure #7). A parse error in an imported module exits 8 (internal), not 5 (parse)

Probe `tmp/audit/2026-09-18/production/p4/m4.json`:

```
uv run a7 .../proj/main_sub.a7 --format json     exit=8
error.category       = "internal"
error.exception_type = "ParseError"
error.message        = "lib.a7:3:11: Expected expression after '+' operator"
error.details        = []
error.span           = null
```

The same file compiled directly exits 5 with a populated span
(`p4/n.json`). Cause: `module_resolver` parses imported files outside the
`try` that classifies parse failures (`compile.py:186-215`), so the exception
reaches the catch-all at `compile.py:491` and is labelled internal.

Exit 8 is the compiler's "this is a compiler bug" code (`README.md:63-66`), so
every user typo in an imported file is reported as a compiler crash, with no
location in the structured payload.

**Fix direction.** Classify module-load parse errors as PARSE with the module's
span. Owner: batch **CLI-02**.

**Changes accepted programs?** No.

### PRD-11. MEDIUM. NEW. A path error exits 8 (internal) instead of 3 (io)

`compile.py:130` calls `input_file.exists()` before any handler is installed for
OS errors other than the read at `:156`. With a 300-character filename
component:

```
uv run a7 .../xxx…(300).a7 --format json     exit=8
error.category       = "internal"
error.exception_type = "OSError"
error.message        = "[Errno 36] File name too long: '...'"
```

(`tmp/audit/2026-09-18/production/p3/j.json`.) A user path mistake is reported
as a compiler bug. Not recorded in `docs/audits/2026-09-16/compiler/pipeline.md`
(`grep -n "Errno 36\|too long\|ENAMETOOLONG"` returns nothing there).

**Fix direction.** Wrap the existence and suffix checks in the same `OSError`
handler as the read, mapping to `ExitCode.IO`.

**Changes accepted programs?** No.

### PRD-12. MEDIUM. KNOWN (PAR-17), with a NEW consequence: `--format json` is unparseable on a **successful** compile of a 1000-declaration program

`a7/parser.py:224-228` prints a plain-text warning to stdout when the
declaration loop hits its 1000-iteration cap. It is printed before the JSON
payload, so the payload is not valid JSON.

`tmp/audit/2026-09-18/production/limits/big1000.a7` (999 functions plus `main`,
6,995 lines):

```
uv run a7 big1000.a7 -o b2.zig --format json     exit=0
stdout line 1: Warning: Parser stopped after 1000 iterations in /home/.../big1000.a7
python: JSON BROKEN ON SUCCESS: Expecting value: line 1 column 1 (char 0)
```

The emitted Zig is complete (1000 `fn` definitions,
`grep -c "^fn \|^pub fn " big1000.zig` → 1000), so this is noise, not
truncation — but a build tool sees exit 0 and cannot parse the result.
`decl1001.a7` (1001 declarations) exits 5 with the same corrupted stream.
`PAR-17` (`docs/audits/2026-09-16/compiler/parser.md:412-423`) records the cap
and the stdout warning; the exit-0 JSON corruption is not recorded there.

Statements inside a function body are not capped: `stmt1100.a7`, 1100
assignments in one body, exits 0 (`limits`, compiler time 180 ms).

**Fix direction.** Remove the cap and rely on the progress guard; route the
warning to stderr or the result object. Owner: batch **PR-03**
(`docs/plan/execution.md:131`), with **X-JSON** for the payload.

**Changes accepted programs?** Yes for the cap removal — it accepts more.
Routing the warning off stdout changes no accepted program.

### PRD-13. MEDIUM. KNOWN in part (PIP-14). Deeply nested code fails with "maximum recursion depth exceeded" and, at different depths, two different exit codes

Generated programs of `main :: fn()` with N nested blocks
(`tmp/audit/2026-09-18/production/limits/blocks*.a7`):

| Depth | Exit | Category | Message |
| --- | --- | --- | --- |
| 127 | 0 | ok | — |
| 300 | 0 | ok | — |
| 400 | 7 | codegen | `maximum recursion depth exceeded` |
| 450 | 7 | codegen | `maximum recursion depth exceeded` |
| 500 | 8 | internal | `maximum recursion depth exceeded` |

Neither failure carries a span or names a line. The split is structural: a
backend `RecursionError` is caught at `compile.py:407-417` and mapped to
CODEGEN, while one raised earlier falls through to `compile.py:491` and is
mapped to INTERNAL. SPEC Appendix C (`docs/SPEC.md:2140`) states a **minimum**
of 127 nested blocks, which is met; the defect is the uncontrolled failure past
roughly 350 and the inconsistent classification, not the limit itself.

**Fix direction.** A located "nesting too deep" diagnostic with one exit code.
Owner: **X-DEPTH** (`docs/plan/execution.md:131`) and **R**
(`docs/plan/execution.md:170`, item 5).

**Changes accepted programs?** No for the classification; the depth conversions
in the no-recursion work accept more.

### PRD-14. MEDIUM. NEW as an Appendix C violation (root cause KNOWN as PIP-8). Import depth 32 is specified; depth 2 does not work

`docs/SPEC.md:2145` requires a minimum import depth of 32. A three-file chain
(`main.a7` imports `a.a7`, which imports `b.a7`;
`tmp/audit/2026-09-18/production/limits/chain2/`) exits 6 with three errors; a
33-file chain (`limits/chain/`) does the same. Transitive imports are never
merged — KNOWN PIP-8
(`docs/audits/2026-09-16/compiler/pipeline.md:234`) — so the stated limit is
unreachable by two orders of magnitude, and the diagnostic compounds PRD-4 by
reporting the failure at `main.a7:4:9` for a name that appears only in
`mod0.a7`.

**Fix direction.** Owned by **MOD** (`docs/plan/execution.md:171`, Wave 2R) and
packet **P-MOD**. Appendix C should say what depth is supported until then.

**Changes accepted programs?** No (it accepts more).

### PRD-15. MEDIUM. NEW. No compiler version is reachable from the command line, and the version is hard-coded twice

`a7/__init__.py:9` sets `__version__ = "0.3.0"`; `pyproject.toml:3` repeats
`version = "0.3.0"`. Neither is exposed: `a7 --version` is a usage error
(PRD-2), the JSON payload carries `schema_version`, `mode`, `input`, `backend`
and `timing_ms` but no compiler version (`compile.py:872-881`), and the
generated Zig carries no version marker (`dbg/hello.zig`). A user cannot tell
which compiler produced a `.zig` file or a binary, and neither can a bug report.

This also contradicts `docs/STATUS.md:18` ("Keep status and release facts
script-derived, not hard-coded"): the version is hard-coded in two files that
can drift.

**Fix direction.** Single source (`importlib.metadata` or `a7.__version__`),
`--version`, a `compiler_version` key in the JSON payload, and a version
comment in the emitted Zig.

**Changes accepted programs?** No.

### PRD-16. MEDIUM. NEW. There is no language version, no deprecation policy and no migration tooling

Ledger L2 (`docs/plan/decisions.md:37`) allows "Documented breaking changes …
under the approval rule" and names no version scheme, no deprecation window and
no migration path. Confirmed absent:

- No language-version construct or pragma in `docs/SPEC.md`
  (`grep -n -i version docs/SPEC.md` finds only `VERSION :: "1.0.0"` at `:438`,
  an example constant inside a code block, and "Type Conversions" headings).
- `docs/CHANGELOG.md` has no breaking-change section, no policy statement and
  no deprecation entries; its two release blocks (`Unreleased`, `0.3.0`) are
  flat bullet lists of additions.
- No `W1xxx` deprecated-feature warning can be emitted (PRD-8), so a
  deprecation could not be surfaced even if declared.

**Fix direction.** A decision the owner must make: a version scheme for the
language distinct from the compiler, what a breaking change obliges (changelog
section, deprecation warning, migration note), and whether `a7` will ever
rewrite source. No gate, packet or track covers it —
`docs/plan/audit/language-audit-checklist.md:74` records the same gap as
"Not in plan".

**Changes accepted programs?** No.

### PRD-17. MEDIUM. KNOWN (PIP-19). The default output path replaces every `.a7` substring in the path and creates a directory

`compile.py:983` is `return input_path.replace(".a7", extension)` — a substring
replace over the whole path, and `compile.py:438-440` then `makedirs` whatever
comes out.

Probe `tmp/audit/2026-09-18/production/p3/`:

| Input | Output written | Side effect |
| --- | --- | --- |
| `proj.a7src/main.a7` | `proj.zigsrc/main.zig` | created the directory `proj.zigsrc/` |
| `weird.a7.a7` | `weird.zig.zig` | — |

Paths with spaces and non-ASCII characters (`a dir ünï/prögram.a7`) are handled
correctly (exit 0, `p3/i.json`).

**Fix direction.** `Path.with_suffix`. Owner: batch **CLI-01**.

**Changes accepted programs?** No.

### PRD-18. MEDIUM. NEW. `--mode doc` writes a `.md` beside the user's source with no flag and no confirmation

`a7/cli.py:86-87`: when `--doc-out` is absent and the mode is `doc`,
`doc_path` becomes `input_path.with_suffix(".md")`. Probed: `a7 m.a7 --mode doc`
exits 0 and creates `m.md` next to the source
(`tmp/audit/2026-09-18/production/p6/`). If a `m.md` already exists it is
overwritten, by the same unguarded `open(..., "w")` at `compile.py:471` that
causes PRD-1.

**Fix direction.** Require an explicit destination, or refuse to overwrite an
existing file that this run did not create.

**Changes accepted programs?** No.

### PRD-19. MEDIUM. KNOWN (PIP-26). An unknown `--backend` exits 7 (codegen), not 2 (usage)

```
uv run a7 m.a7 --backend nosuch      exit=7
✗ Unknown backend 'nosuch'. Available backends: zig
```

(`tmp/audit/2026-09-18/production/p6/bb.out`.) `a7/cli.py:56-58` prints the
available backends in `--help` but never validates the value; the failure
surfaces from `get_backend` inside the codegen `try`
(`compile.py:397-417`). A wrapper reading exit 7 concludes the program failed
to compile.

**Fix direction.** `choices=list_backends()` on the argument.

**Changes accepted programs?** No.

### PRD-20. LOW. NEW. The JSON contract is versioned but undocumented, and messages are not stable keys

`compile.py:873` emits `"schema_version": "2.0"`. No user-facing document
mentions it: `grep -rn schema_version docs/ README.md site/public/` finds it
only in audit evidence files and `docs/plan/` fix plans. The shape — `mode`,
`status`, `input`, `backend`, `timing_ms`, `stages`, `artifacts`, `error` — is
specified nowhere a consumer can read, and `docs/plan/fix-program/frontend-fix-plan.md:639`
already flags that the planned 2.1 bump "Could break external consumers".

Within that payload, `error.details[].message` embeds the file basename and
location (`errors.py:642-654`), e.g. `sem.a7:3:10: Undefined type (Identifier
'undefined_name')`, so the message cannot be used as a match key and duplicates
the `span` field. In the PRD-4 probe one detail object says
`file: .../main_sub.a7` while its own `message` says `lib.a7:3:11:` —
self-contradictory inside a single record.

**Fix direction.** Document the schema in the user-facing docs and separate the
human message from the location. Owner: batch **X-JSON**.

**Changes accepted programs?** No.

### PRD-21. LOW. KNOWN (PIP-35). `compile_project` is dead code

`compile.py:945-979` implements whole-directory compilation and
`compile.py:1016-1025` wraps it; no CLI flag reaches either
(`a7/cli.py` has one positional file). Already recorded at
`docs/audits/2026-09-16/compiler/pipeline.md:566`.

**Changes accepted programs?** No.

### PRD-22. LOW. NEW. `a7/errors.py:844` shadows the Python built-in `ImportError`

`class ImportError(CompilerError)` redefines the built-in name inside the
module. Nothing in `a7/` raises it (`grep -rn "raise ImportError" a7/` is
empty), but any future `except ImportError` in that module would catch the wrong
class.

**Changes accepted programs?** No.

### PRD-23. LOW. NEW. `--doc-out auto` is resolved twice, by two different rules

`a7/cli.py:85` resolves `auto` with `Path.with_suffix(".md")`;
`compile.py:456-457` resolves the literal string `"auto"` with
`input_path.replace(".a7", ".md")`. The second is unreachable from the CLI but
live for library callers of `A7Compiler(doc_path="auto")`, and carries the
PRD-17 substring bug. The two paths disagree for any input whose directory name
contains `.a7`.

**Changes accepted programs?** No.

### PRD-24. HIGH. KNOWN (SEC-3, `docs/audits/2026-09-14/security-glm-review.md`). `oven-sh/setup-bun@v2` is still a mutable tag, in three workflows, two of which hold write permissions

```
$ grep -rn "oven-sh/setup-bun" .github/workflows/
.github/workflows/ci.yml:98:        uses: oven-sh/setup-bun@v2
.github/workflows/release.yml:52:        uses: oven-sh/setup-bun@v2
.github/workflows/deploy-docs.yml:28:        uses: oven-sh/setup-bun@v2
```

Every other action reference in the five workflows is pinned to a commit SHA
(22 of 25; the three exceptions are these). The `release.yml:52` job holds
`id-token: write`, `attestations: write` and `artifact-metadata: write`
(`release.yml:25-29`); the `deploy-docs.yml:28` job holds `pages: write` and
`id-token: write` (`deploy-docs.yml:8-11`). `docs/SECURITY.md:49-50` claims
"Workflow actions are pinned to immutable commits", which is false.

Dependabot cannot fix this: `.github/dependabot.yml` runs the `github-actions`
ecosystem weekly, and a floating major tag is not a bumpable pin — which is why
the three Dependabot commits in the log (`701c679`, `f3f6286`, `70e95ab`)
touched checkout, attest and claude-code-action but never setup-bun.

No plan row owns it (`docs/plan/audit/language-audit-checklist.md:42-44`
records CI as unowned).

**Changes accepted programs?** No.

### PRD-25. MEDIUM. KNOWN (SEC-4). `python -m pip install uv` is unpinned, at three sites — one more than the original finding lists

```
$ grep -rn "pip install uv" .github/workflows/
.github/workflows/release.yml:40:        run: python -m pip install uv
.github/workflows/ci.yml:35:        run: python -m pip install uv
.github/workflows/ci.yml:89:        run: python -m pip install uv
```

No version, no hash, no `astral-sh/setup-uv`. SEC-4 lists `ci.yml:35` and
`release.yml:40`; `ci.yml:89`, in the `docs` job, is a third. In `release.yml`
this runs in the job that later signs attestations. The same class applies to
`pip-audit==2.10.0` (`ci.yml:53`) and `bandit==1.9.4` (`ci.yml:57`), which are
version-pinned but not hash-pinned.

**Changes accepted programs?** No.

### PRD-26. HIGH. NEW. Only linux-x86_64 is ever built or tested, and the Zig pin makes that structural

All eight `runs-on:` lines across the five workflows are `ubuntu-latest`
(verified by `grep -rn "runs-on" .github/workflows/`). There is no matrix of
any kind. The pinned toolchain is
`zig-x86_64-linux-0.16.0.tar.xz` with a SHA-256 checked before extraction
(`.github/workflows/ci.yml:18-20,39-44`; `release.yml:18-20,44-49`), so adding a
second OS requires new download plumbing, not a matrix entry.

`pyproject.toml:6` declares `requires-python = ">=3.13"` while CI runs only
`"3.13"` (`ci.yml:32,86`; `release.yml:37,171`). Cross-compilation is not
exercised anywhere, although Zig supports it and the release archive name
already encodes a platform
(`a7-example-artifacts-linux-x86_64-zig0.16.0-<profile>.tar.gz`).

**Fix direction.** Either test a second platform or state in `README.md` and
`docs/RELEASE.md` that linux-x86_64 is the only supported target.

**Changes accepted programs?** No.

### PRD-27. HIGH. NEW. Release artifacts are not reproducible and leak the builder's filesystem layout

Verified against the artifacts already in this tree:

```
$ strings build/release/zig/bin/001_hello | grep -c "/home/cx89"
27
$ strings build/release/zig/bin/001_hello | grep "/home/cx89" | head -3
/home/cx89/Projects/pl-dev/a7-py/build/release/zig/src
/home/cx89/.local/share/mise/installs/zig/0.16.0/lib/std
/home/cx89/.cache/zig/b/93431e4305d48743b209c1d93eaded19
```

Cause: `scripts/build_examples.py:104-113` passes an absolute source path and
`-femit-bin=<absolute>`. The shipped example-artifact archive therefore names
the builder's home directory and Zig cache.

The archives themselves are not reproducible either:
`.github/workflows/release.yml:104` and `:107` call `tar -czf` with no
`--sort=name`, no `--mtime=`, no `--owner=0 --group=0 --numeric-owner`, and
gzip embeds an mtime. `SOURCE_DATE_EPOCH` is set nowhere in the repository.
`pyproject.toml:15` floats the build backend (`setuptools>=84`), which
`uv.lock` does not lock, so `uv build` resolves a fresh setuptools each run.

`scripts/generate_release_manifest.py` is deterministic where it can be
(sorted by POSIX relative path, `:73`; sha256 + size only, no timestamps,
`:97`) but records `git rev-parse HEAD` (`:33-46`) with no dirty-tree check, so
a manifest built from a modified worktree carries a clean commit SHA. The
generated `.zig` sources are clean — no header, no input path.

**Fix direction.** Build with relative paths from the source directory, add
reproducible-tar flags and `SOURCE_DATE_EPOCH`, pin the build backend, and
record tree state in the manifest.

**Changes accepted programs?** No.

### PRD-28. HIGH. NEW. The release path has never run, and nothing verifies the attestation it produces

`git tag -l` returns nothing: this repository has zero tags, and
`.github/workflows/release.yml:3-7` triggers only on `push` of `v*`. The
archive verification, manifest generation, attestation and draft-release steps
(`release.yml:109-192`) have therefore never executed. `run_all_tests.sh` does
not exercise any of them either (see PRD-29), so the entire release-integrity
chain is untested code.

`release.yml:138-145` attests the digests of `dist/SHA256SUMS`, the sdist, the
wheel, the docs-site tarball and the example-artifact tarball. Nothing in any
workflow ever verifies an attestation; `gh attestation verify` appears only as
advice in `docs/SECURITY.md:46-48`. `docs/SECURITY.md`'s claim that releases
receive attestations is therefore untested rather than false.

`release.yml` also never checks that the pushed tag matches
`pyproject.toml:3` (`version = "0.3.0"`), so a `v0.9.0` tag would ship a `0.3.0`
wheel.

**Fix direction.** A dry-run of the release job on a pre-release tag, a
tag/version consistency check, and an attestation verification step.

**Changes accepted programs?** No.

### PRD-29. MEDIUM. NEW. `run_all_tests.sh` is not the full gate its docs claim, and the local and CI test sets differ

`CLAUDE.md` states `run_all_tests.sh` "is the single source of truth for the
full gate". It runs twelve checks (`run_all_tests.sh:49-89`) and omits:

- `pip-audit` (`ci.yml:53`, `release.yml:67`)
- `bandit` (`ci.yml:57`, `release.yml:71`)
- every bun step — `bun install --frozen-lockfile`, `bun audit`, `bun run lint`,
  `bun run build`
- the whole release-integrity chain: `verify_archive_contents.py`,
  `generate_release_manifest.py`, `verify_release_manifest.py`
  (`release.yml:109-135`)
- `uv sync --locked`, so local lockfile drift is invisible

It also runs the parser, tokenizer, semantic, preprocessor, CLI, traversal,
stdlib and codegen test files twice — once as a named subset
(`:49-62`) and again inside the catch-all `uv run pytest` (`:89`). The
`test_pipeline_*.py` files reach the gate only through that final step, which
is why `docs/audits/2026-09-16/baseline.md:56-58` records the failures as
appearing only there.

Failure handling is correct: `run_check` always returns 0 (`:41`) so `set -u`
without `set -e` never aborts, `FAILED_CHECKS` increments at `:40`, and
`:95-97` exits 1. There is no `set -o pipefail`, and `:83` uses `bash -lc`, so
the package-build step depends on the user's login shell profile.

**Changes accepted programs?** No.

### PRD-30. MEDIUM. NEW. `verify_examples_e2e.py` crashes with a raw traceback when Zig is missing

`scripts/build_examples.py:285-287` guards with `shutil.which("zig")` and exits
cleanly. `scripts/verify_examples_e2e.py` has no such guard, and
`scripts/verify_examples_common.py:57-64` wraps `subprocess.run` with no
exception handling:

```
$ PATH=/usr/bin:/bin .venv/bin/python scripts/verify_examples_e2e.py
...
FileNotFoundError: [Errno 2] No such file or directory: 'zig'
```

versus

```
$ PATH=/usr/bin:/bin .venv/bin/python scripts/build_examples.py --profile debug --backend zig
zig is required for debug/release artifact builds
```

This is the first native step of both the local gate (`run_all_tests.sh:65`)
and CI, so the most common environment mistake — no Zig — produces a Python
traceback rather than a diagnostic.

Neither script's three `zig` calls carry a timeout
(`build_examples.py:96,100,104-113`; `run_cmd`'s `timeout` defaults to `None`,
`:56-68`), so a wedged toolchain hangs the gate with no output, because
`run_all_tests.sh:21` captures output into a variable.

**Changes accepted programs?** No.

### PRD-31. MEDIUM. NEW. The published package has no classifiers, no license field, no URLs, no authors and no `py.typed`, and the sdist ships the test suite

`pyproject.toml` is 26 lines. It declares no `license`, no `[project.urls]`, no
`authors`, and no `classifiers`; the built `METADATA` has no `Classifier:` and
no `Project-URL:` line at all. `find . -name py.typed -not -path "./.venv/*"`
returns nothing, so the package is untyped for consumers.

The wheel is clean (31 `a7/**` modules plus dist-info). The sdist is not:

```
$ python3 -c "import tarfile; t=tarfile.open('dist/a7_py-0.3.0.tar.gz'); n=t.getnames(); print(len(n), sum(1 for x in n if '/test/' in x))"
97 47
```

97 members including 47 files from `test/` and the `a7_py.egg-info/` directory.
There is no `MANIFEST.in`. `docs/audits/2026-09-14/security-glm-review.md:386-387`
clears this as "no tests, scripts, or site files ship", which is true of the
wheel only.

`rich>=15.0.0` (`pyproject.toml:8`) is a floor, not a pin; `uv.lock` hashes
every package for CI but a consumer installing the published wheel resolves
`rich` unhashed.

**Changes accepted programs?** No.

### PRD-32. MEDIUM. KNOWN (SEC-1, SEC-2, SEC-5 through SEC-12). Every 2026-09-14 security finding is still live

HEAD is `701c67936c70ad2b0608326e23e56cc5d38c9fdb`, which is the baseline of
`docs/audits/2026-09-14/security-glm-review.md:9`, and
`git status --porcelain -- .github scripts site/scripts pyproject.toml uv.lock
run_all_tests.sh .gitignore docs/SECURITY.md` shows only `pyproject.toml` and
`uv.lock` modified, both a dependency bump. Spot-verified above for SEC-3 and
SEC-4; the remainder re-checked line by line:

| ID | Still live? | Current evidence |
| --- | --- | --- |
| SEC-1 preview traversal, non-loopback bind | live | `site/scripts/serve.ts:21-24` decodes before `path.join`, no containment check; `:18-19` sets no `hostname` |
| SEC-2 pip-audit audits the wrong environment | live | `ci.yml:53`, `release.yml:67` run `uvx --from pip-audit==2.10.0 pip-audit --strict` inside the ephemeral tool env, not the `uv sync --locked` project env |
| SEC-3 mutable `setup-bun@v2` | live | PRD-24 |
| SEC-4 unpinned `pip install uv` | live | PRD-25 |
| SEC-5 site content injection | live | `site/scripts/build.ts:78-81` no link-scheme allowlist; `:359` interpolates JSON into an inline `<script>` without `<` escaping |
| SEC-6 escaping gaps | live | `build.ts:375` raw `canonical` in a `href`; `:693` unescaped XML in the sitemap; `escapeHtml` (`:43-48`) omits `'` |
| SEC-7 `.a7` path rewriting | live | `a7/compile.py:457` and `:983` (see PRD-17, PRD-23) |
| SEC-8 soft-404 | live | `serve.ts:23` unhandled `decodeURIComponent`; `:29` returns the 404 body with HTTP 200 |
| SEC-9 subprocess hygiene | partly live | argv lists and no `shell=True` throughout; the gaps remain: `zig` resolved from `PATH`, no timeout on the three zig calls, `bandit --skip B404,B603` global (`ci.yml:57`) |
| SEC-10 compiler DoS | holds | Re-ran an 80,000-deep parenthesis input against the modified parser: exit 8, one stderr line, no hang. `a7/tokens.py:8` still imports `re` unused; `MAX_STRING_LENGTH` (`:16`) still referenced nowhere |
| SEC-11 import-path trust boundary | live | `a7/module_resolver.py` unmodified: cache check (`:124-125`) precedes the cycle guard (`:131`); `topological_sort` (`:310`) has no callers; `add_search_path` (`:357-360`) never updates `resolved_search_paths` |
| SEC-12 secrets guardrails | live | `.gitignore` has no `.env` entry; `scripts/check_no_secrets.py:26-33` skips `.lock`, `.gz`, `.whl` wholesale |

`docs/plan/audit/language-audit-checklist.md:42-44` records CI as having no
owner. That is still true for all twelve.

**Changes accepted programs?** No.

### PRD-33. CRITICAL. NEW. `x, y := 10, 20` exits 0 and emits a Zig file that contains one variable and no program

`docs/SPEC.md:422-424` marks multiple-declaration and destructuring binding as
planned, exactly as `CLAUDE.md` requires:

```
// Multiple declaration/destructuring syntax is planned, not current:
// a, b, c: i32 = 1, 2, 3
// x, y := 10, 20
```

The compiler does not reject the second form. It ends the program at the comma
and reports success. Probe `tmp/audit/2026-09-18/production/p7/destr.a7`:

```
io :: import "std/io"
main :: fn() {
    x, y := 10, 20
    io.println("{} {}", x, y)
}
```

```
$ uv run a7 destr.a7 -o destr.zig
exit=0
$ cat destr.zig

var y = 10;
```

The whole `main` declaration is gone; `--mode ast` reports two top-level
declarations, `IMPORT` and `VAR y`. The first spelling,
`a, b, c: i32 = 1, 2, 3`, is caught — exit 5,
`Unexpected token 'io' after parsing complete program` — so the same root cause
is fatal in one spelling and silent in the other.

This violates the exit-code contract published in `README.md:65` and
`site/public/docs/compiler.md:44-53`: a build script that trusts exit 0 ships an
empty translation unit. Zig then rejects the file for having no entry point, so
the user is told the *Zig* build failed for a program A7 said it compiled.

**Fix direction.** Reject an identifier followed by `,` at statement start with
a located parse error, as the type-annotated spelling already is. Related to
PAR-03 ("Every parse error fails", packet **P-PAR**,
`docs/plan/execution.md:187`); no row names this shape.

**Changes accepted programs?** Yes: exit 0 becomes exit 5. No approval needed —
the accepted program is a miscompile, which
`docs/plan/audit/language-audit-checklist.md:123-125` exempts. Record the
disposition in packet **P-PAR**.

### PRD-34. HIGH. NEW. `@type_set(...)`, the one intrinsic the docs present as working, fails at codegen

`docs/SPEC.md:943-945` states: "Type-set syntax is implemented for predefined
sets, local `@type_set(...)` aliases, and inline constraints on declared generic
functions", and `:1546-1547` lists `@type_set` under "handled specially by the
compiler". `CLAUDE.md` exempts `@type_set` from the parsed-only marking on that
basis.

Probe `tmp/audit/2026-09-18/production/p7/ts.a7`, a single unused declaration
`Numeric :: @type_set(i32, i64, f32, f64)`:

```
exit=7
✗ 2:12: Zig backend: unsupported expression node 'TYPE_SET'
```

A generic function constrained by such an alias fails the same way. A
constraint written against a *predefined* set name compiles (exit 0), so only
the `@type_set(...)` alias half is broken — the half the SPEC singles out as
implemented. The exit code is also wrong for a language-level unsupported
construct: 7 is codegen, and `site/public/docs/compiler.md:51-52` publishes 6 for
semantic rejection.

No example in `examples/` uses `@type_set`
(`docs/plan/audit/language-audit-checklist.md:52-53`), which is why this
survived.

**Changes accepted programs?** No.

### PRD-35. HIGH. NEW. The docs published to users disagree with `docs/STATUS.md` about priorities, gaps and what works

`site/public/docs/status.md` is the site's status page and
`site/public/llms-full.txt` reproduces it verbatim. Both drift from
`docs/STATUS.md`, which `CLAUDE.md` names as authoritative:

| Topic | `docs/STATUS.md` | `site/public/docs/status.md` |
| --- | --- | --- |
| Active priorities | Six (`:18-26`) | Four (`:23-27`); the four dropped include the workflow commands (`STATUS:25-26`) and "Keep status and release facts script-derived" (`STATUS:18`) |
| Invented priorities | — | "Clearer status reporting for parsed-only language features" and "Practical stdlib additions starting with deterministic random helpers" (`:26-27`), in no other document |
| Known gaps | "Fixed-width overflow, **shifts**, union discriminant access, full ref/del alias behavior, and **ownership/lifetime guarantees** are incomplete" (`:32-34`) | "Fixed-width overflow, union discriminant access, and full ref/del alias behavior are incomplete" (`:33-34`) — two items dropped |
| File-backed imports | "File-backed imports target one combined Zig output file. Selected imports … remain follow-up work" (`:30-32`) | "File-backed imports, `using import`, and broad cross-module type checking remain follow-up work" (`:31-32`) — the leading sentence is dropped, inverting the meaning |

The last row is falsifiable and false: a probe importing a sibling `.a7` file
and calling into it
(`tmp/audit/2026-09-18/production/p8/c.a7`) exits 0 and emits the imported
function under a `module_…__` prefix, the scheme
`compile.py:570-572` defines. `CLAUDE.md`'s own description ("file-backed local
imports that currently fail closed before codegen") is stale in the same
direction.

Other published claims contradicted by probes:

- `site/public/docs/stdlib.md:36-37` and `site/public/llms-full.txt:281-282`:
  "Typed variants such as `sqrt_f32` and `sqrt_f64` are also available as bare
  builtins." Both bare `sqrt_f64(2.0)` and `math.sqrt_f64(2.0)` exit 6
  (`Undefined type (Identifier 'sqrt_f64')` and `Stdlib module 'std/math' has no
  function …`). `docs/SPEC.md:1571-1572` makes the same claim and is
  contradicted within the same file by `:1579-1580`, which files those names
  under "planned API shape, not current implementation".
- `site/public/docs/index.md:18` gives the pipeline as
  ".a7 → tokenize → parse → semantic checks → emit Zig → native binary" — five
  stages, dropping safety proof planning and AST preprocessing, which
  `README.md:130` lists and `README.md:136` calls out. `site/public/docs/compiler.md:16-24`
  gives nine, `docs/STATUS.md:9-10` six.
- `a7/cli.py:17` describes the program as "A7 Programming Language
  Compiler/Interpreter" in `--help`; `site/public/docs/index.md:12-13` says
  "The compiler is Python. There is no A7 runtime." There is no interpreter.
- `README.md:24` still says `git clone <repository-url>`, an unresolved
  placeholder; `site/public/docs/start.md:21` gives the real URL.
- No user-facing document mentions `-o/--output` or `--backend`
  (`grep -rn -- "--output\|--backend" README.md docs/SPEC.md site/public/docs/
  site/public/llms*.txt` finds only an unrelated script invocation at
  `README.md:113`), and `--verbose`/`--doc-out` appear only in `README.md:51-54`,
  never on the site — although `site/public/docs/compiler.md:29-40` presents
  itself as the CLI reference. Every documented compile therefore writes a
  `.zig` next to the user's source.
- `README.md:195` and `docs/CHANGELOG.md:25` hard-code "43" examples, against
  `docs/STATUS.md:18` ("Keep status and release facts script-derived, not
  hard-coded"). The number is currently correct.

`site/public/llms-full.txt` is in sync with all nine `site/public/docs/*.md`
bodies (it is generated by `site/scripts/build.ts:745-749`), so fixing the site
pages fixes the agent corpus.

**Changes accepted programs?** No.

### PRD-36. HIGH. NEW. `docs/SPEC.md` §12 and Appendix B describe a compiler that does not exist, and the reference contradicts itself on core syntax

§12 documents an implementation in C-style A7:

- `docs/SPEC.md:1655-1773` lists token names `TOKEN_INT_LITERAL`,
  `TOKEN_QUESTION`, `TOKEN_SIZE_OF`. `grep -c "TOKEN_INT_LITERAL" a7/tokens.py`
  → 0; the real names are `INTEGER_LITERAL` and so on (`a7/tokens.py:21`).
- `:1777-1850` lists AST kinds `AST_EXPR_BINARY`; `grep -c AST_EXPR_BINARY
  a7/ast_nodes.py` → 0.
- `:1857-1910` gives the AST as an A7 struct with `children: []ref ASTNode`.

Appendix B's error and warning code families are emitted by nothing (PRD-8).
§9 (`:1083-1444`, 362 lines, 16 % of the file) is tensor design material,
marked as a design target at `:1087-1090` but never separated.

Self-contradictions a newcomer would hit first, each verified:

| Topic | Two sides | Probe |
| --- | --- | --- |
| Generic function declaration | `:864` "The same `$T` syntax is used everywhere — no separate declaration vs reference syntax", with `:885` `identity :: fn(x: $T) $T`; against `:698` `swap :: fn($T, a: ref T, …)`, `:962-964` `abs($T: Numeric) :: fn(x: $T) $T`, and the grammar at `:1953-1954` | `:885` form → exit 7 `generic type requires an explicit generic environment`; `:705` form → exit 5; `:964` form → exit 0. `examples/014_generics.a7:5` uses the `:964` form |
| `x: i32 = 42` | `:410-411` "Immutable binding (constant)" and `:447` "Immutable with explicit type"; against `:448` "Mutable with explicit type" | `x: i32 = 42` then `x = 43` → exit 0, emits `var x: i32 = 42; x = 43;`. `:448` is right |
| Address-of / deref | `:399-401` "Public address-of and dereference operators are not part of A7."; against the grammar at `:2021` `postfix_expr "." "val"` | `.val` parses as ordinary field access, exit 6 |
| Untagged unions | `:331-338` shows `Number :: union { i: i32 … }` working and `:347` documents untagged literals; against `:1982`, where `(tag)` is mandatory in the grammar | not probed |
| `not` | used at `:623`; absent from the keyword table `:97-104`, and `:484` documents only `!` | `while running and not f()` → exit 0, emits `(!...)`; `a7/tokens.py:210` registers it |
| Status date | `:3` "Implementation Status (2026-05-08)"; `:2176` "Status snapshot (2026-05-11)" | — |
| File IO | `:1047-1048` `file := open("data.txt")`, unmarked; `site/public/docs/stdlib.md:62` says file IO is out of scope | `open(...)` → exit 6 |
| `print` / `printf` | used unmarked in §5 and §6 (`:523-526`, `:606-607`, `:676`, `:788`); filed under "planned API shape" at `:1609-1612` | both → exit 6 |
| Array `.len` | `:259` `T.len // Number of elements` | `arr.len` on `[5]i32` → exit 6; slice `.len` and `.ptr` → exit 0 |
| `@type_set` signature | `:1547` `@type_set :: fn(types: ..type)` uses the variadic syntax `:835-838` marks unrunnable | PRD-34 |

**Changes accepted programs?** No.

### PRD-37. MEDIUM. NEW. There is no conformance suite and no reference indexed by SPEC clause

`grep -rn "SPEC" test/ examples/` returns exactly one line:
`test/test_zig_backend_runtime.py:178`, a comment citing SPEC A.1 item 4. No
test file is named for a clause; `grep -rli conform test/` finds nothing. There
is therefore no way to ask "which SPEC clauses does the compiler implement", and
the drift catalogued in PRD-36 has no mechanical detector.

`scripts/check_docs_style.py` checks banned phrases over a fixed document list
(`:20-37`, `:39-70`); nothing checks a doc claim against compiler behaviour.

**Fix direction.** Either a per-clause test index, or accept that the SPEC is a
design document and mark it as such.

**Changes accepted programs?** No.

### PRD-38. MEDIUM. NEW. `docs/CHANGELOG.md` names no breaking change, has no categories and no dates

Its structure is two unlabeled bullet lists, `## Unreleased` (`:6`) and
`## 0.3.0` (`:15`), with no dates, no Added/Changed/Removed/Breaking headings
and no compare links. `:3-4` disclaims history outright.

Three breaking changes that happened are not named anywhere in it:

- Loop labels changed spelling: `docs/SPEC.md:656-658` "Loop labels use `@name`
  directly before a loop statement. The old `name: for ...` spelling is
  rejected".
- Address-of and dereference operators were removed: `docs/SPEC.md:399-400`;
  `CLAUDE.md` names the removed spellings `.adr`, `.val`, prefix `&`, prefix `*`.
- The C backend was retired: `docs/SPEC.md:2208`. `CHANGELOG.md:18` records only
  the result ("Zig is the only supported public backend") without naming the
  removal or marking it breaking.

A search for "semver", "semantic version", "version scheme", "deprecat" or
"breaking" across `README.md`, `docs/RELEASE.md`, `docs/CHANGELOG.md`,
`docs/SPEC.md`, `site/public/docs/` and `site/public/llms*.txt` returns one hit:
`docs/SPEC.md:2125`, the name of a warning category that is never emitted
(PRD-8). This is the concrete face of PRD-16.

**Changes accepted programs?** No.

## Appendix C: stated limits against measured behaviour

`docs/SPEC.md:2131-2148` gives thirteen "Minimum Limit" rows. Probes in
`tmp/audit/2026-09-18/production/limits/`. A minimum is met if the compiler
accepts at least that many; accepting more is compliant.

| Row | Stated minimum | Measured | Verdict |
| --- | --- | --- | --- |
| Identifier length | 100 | 100 accepted; 101 → exit 4 `Identifier is too long` | met exactly |
| Numeric literal length | 100 | 100 accepted; 101 → exit 4 `Number is too long` | met exactly |
| String literal length | 65,535 bytes | 65,535 and 70,000 both accepted (exit 0) | met; no cap enforced |
| Function parameters | 255 | 255 and 256 accepted | met |
| Generic parameters | 32 | 32 and 33 accepted | met |
| Nested blocks | 127 | 127, 300 accepted; 400 → exit 7; 500 → exit 8 (PRD-13) | met, then crashes |
| Array dimensions | 8 | 8 and 9 accepted | met |
| Struct fields | 1,023 | 1,023 and 1,024 accepted | met |
| Union variants | 255 | 255 and 256 accepted | met |
| Enum values | 65,535 | accepted, 2.06 s compiler time | met |
| Import depth | 32 | depth 2 fails, exit 6 (PRD-14) | **violated** |
| Defer statements per scope | 255 | 255 accepted | met |
| Match cases | 1,023 | 1,023 accepted | met |

One real limit is absent from the table: **1,000 top-level declarations**
(`a7/parser.py:153-156`). A file at or above that cap corrupts `--format json`
(PRD-12) and above it is rejected. Appendix C should state it.

## Compiler performance

Measured with `uv run a7 <file> -o <out> --format json`, wall clock around the
whole process and the compiler's own `timing_ms` from the payload
(`tmp/audit/2026-09-18/production/limits/`).

| Program | Lines | Wall | Compiler `timing_ms` |
| --- | --- | --- | --- |
| `uv run a7 --help` (startup floor) | — | 0.09 s | — |
| `examples/037_language_tour.a7` (largest example) | 143 | 0.11 s | 13 |
| `examples/030_calculator.a7` | 139 | 0.12 s | 22 |
| 1,100 statements in one function | 1,104 | 0.32 s | 180 |
| 999 functions with bodies (at the declaration cap) | 6,995 | 1.58 s | — (JSON corrupted) |
| 1,023 struct fields | 1,025 | 0.18 s | 54 |
| 65,535 enum values | 65,537 | 2.94 s | 2,059 |

Compile speed is not a problem at the sizes A7 can express. About 0.09 s of
every invocation is Python and `uv` startup, which would dominate a
`a7 check`-style edit loop. The largest program the compiler will accept is
bounded by the 1,000-declaration parser cap, not by time.

## What is missing

| Item | What exists now | What it needs | Decision owner | v1 priority |
| --- | --- | --- | --- | --- |
| `a7 build` / `a7 run` | Nothing; `a7 run` is read as a filename (PRD-2) | Subcommands that invoke `zig build-exe` with the profile flags `scripts/build_examples.py:20-27` already uses | none | P0 |
| `a7 check` | Nothing; `--mode pipeline` is the closest | A subcommand that type-checks without writing, and a fast startup path | none | P1 |
| `a7 doctor` | Nothing; no code in `a7/` probes Zig (PRD-5) | Zig presence and version check, backend list, search paths | none | P1 |
| `a7 --version` | `__version__` hard-coded in two files (PRD-15) | One source of truth, a flag, a JSON key, a marker in emitted Zig | none | P0 |
| Documented `.a7` → binary path | `README.md` stops at `.zig` (PRD-3) | Either the subcommands above, or the three literal commands in README | none | P0 |
| Diagnostics on stderr | Everything on stdout (PRD-9) | Stream split | batch **X-RICH** | P0 |
| Stable error codes | None; SPEC B.1 families unimplemented (PRD-8) | Codes assigned and frozen, or Appendix B.1 deleted | none | P1 |
| Any warning at all | `ErrorSeverity` dead; one `print()` in the parser (PRD-8) | A warning channel, a severity on each diagnostic, `-W` flags | none | P1 |
| Documented JSON schema | `schema_version: 2.0` undocumented (PRD-20) | A published schema and a compatibility rule for the planned 2.1 | batch **X-JSON** | P1 |
| Correct module error origins | Wrong file and line (PRD-4), exit 8 on parse (PRD-10) | Origin carried through the merge | batch **CLI-02** | P0 |
| Safe output paths | Source can be overwritten (PRD-1), stray directories (PRD-17) | Destination validation and `with_suffix` | batch **CLI-01** | P0 |
| Source formatter | None; no `a7 fmt`, no code in `a7/` | A canonical printer over the AST | none | P2 |
| Language server | None; `site/public/docs/status.md:45` lists "Full language server" as absent | An LSP over the existing passes; blocked on the formatter and on stable diagnostics | none | P2 |
| Syntax grammar for editors | None; no `editors/`, no `.tmLanguage`, no tree-sitter grammar in the repo | One grammar, published | none | P2 |
| Debug info back to `.a7` | Nothing; DWARF names only `.zig` (PRD-7) | Line mapping | **SRC-MAP**, Wave 3 | P1 |
| Runtime trap messages naming A7 | Zig panics with generated source (PRD-7) | A panic handler that prints A7 locations | none (depends on SRC-MAP) | P2 |
| Language version and deprecation policy | Ledger L2 allows breaking changes, names no scheme (PRD-16) | A scheme, a deprecation window, a changelog section | none | P1 |
| Migration tooling | None | Decide whether any exists for v1 | none | P3 |
| Import depth beyond 1 | Transitive imports never merged (PRD-14) | Module redesign | **MOD**, packet **P-MOD** | P0 |
| Multi-file project build | `compile_project` is dead code (PRD-21) | A project model, or an explicit decision that one file is the unit | **MOD** | P1 |

### Release, packaging and CI

| Item | What exists now | What it needs | Decision owner | v1 priority |
| --- | --- | --- | --- | --- |
| A supported-platform statement | Only `ubuntu-latest` is ever run (PRD-26) | Either a second platform in CI or a written "linux-x86_64 only" claim in README and RELEASE | none | P0 |
| Cross-compilation | Never exercised; Zig supports it and the archive name encodes a platform | A decision whether v1 ships cross targets | none | P2 |
| Reproducible builds | Absolute paths in binaries, non-reproducible tars, floating build backend (PRD-27) | Relative build paths, tar flags, `SOURCE_DATE_EPOCH`, pinned backend | none | P1 |
| A release that has run | Zero tags; the whole release job is untested (PRD-28) | A pre-release dry run and a tag/version check | none | P0 |
| Attestation verification | Produced, never verified (PRD-28) | A verification step in the release job | none | P2 |
| SHA-pinned actions | 22 of 25; three `setup-bun@v2` (PRD-24) | Pin the three; correct `docs/SECURITY.md:49-50` | none | P0 |
| Pinned `uv` install | Unpinned at three sites (PRD-25) | `astral-sh/setup-uv` at a SHA, or a pinned version with hashes | none | P1 |
| A gate that matches its description | `run_all_tests.sh` omits pip-audit, bandit, bun and the release chain (PRD-29) | Add them, or correct the claim in CLAUDE.md and AGENTS.md | none | P1 |
| Clean failure without Zig | `verify_examples_e2e.py` tracebacks (PRD-30) | A `shutil.which` guard and timeouts on the zig calls | none | P2 |
| Publishable package metadata | No classifiers, license field, URLs, authors or `py.typed`; sdist ships `test/` (PRD-31) | Metadata, a `MANIFEST.in`, `py.typed` | none | P1 |
| Owner for the 2026-09-14 security findings | All twelve still live (PRD-32) | A batch that carries them | none | P0 |

### Documentation

| Item | What exists now | What it needs | Decision owner | v1 priority |
| --- | --- | --- | --- | --- |
| One authoritative status | `docs/STATUS.md` and `site/public/docs/status.md` disagree on four of six priorities and two gaps (PRD-35) | Generate the site page from `docs/STATUS.md`, or delete one | none | P0 |
| A reference that matches the compiler | SPEC §12 documents a C implementation; core syntax contradicts itself four ways (PRD-36) | Rewrite §12 or delete it; pick one generic declaration form | packets **P-TYP**, **P-PAR** for the syntax halves; none for §12 | P0 |
| A tutorial that reaches a binary | `site/public/docs/start.md:42-43` does (verified); `README.md` stops at `.zig` (PRD-3) | Bring README to parity, document `-o` | none | P1 |
| A conformance suite | One SPEC comment in the whole test tree (PRD-37) | A per-clause index, or a statement that SPEC is a design document | none | P2 |
| A doc/behaviour checker | `scripts/check_docs_style.py` checks phrasing only | A check that compiles every fenced A7 snippet in the docs | none | P1 |
| Changelog discipline | No categories, no dates, three unnamed breaking changes (PRD-38) | Breaking-change section and a policy | none | P1 |
| Correct stdlib claims | `sqrt_f32`/`sqrt_f64` documented as available, rejected by the compiler (PRD-35) | Either register them or delete the claims in three files | Track 8b (stdlib) | P1 |

## Checked and correct

- Relative imports cannot leave the source directory:
  `a7/module_resolver.py:64-77` rejects absolute paths, `..` segments,
  backslashes and null bytes, and `_is_within_search_path` re-checks after
  `resolve()`. Probed: `import "../outside"` → exit 6 (`p4/k.json`); a symlink
  inside the directory pointing outside it → exit 6 (`p4/l.json`); a legitimate
  `import "sub/lib"` → exit 0 (`p4/m3.json`).
- Paths containing spaces and non-ASCII characters compile correctly
  (`p3/i.json`, exit 0).
- Writing into a read-only directory fails cleanly: exit 3, category `io`, and
  no artifact advertised (`p2/e.json`).
- Diagnostic spans carry 1-based line and column at every failing stage, in both
  formats (`p5/*.json`).
- The JSON payload is a single parseable object in every failure case probed,
  except when the parser cap warning precedes it (PRD-12).
- Exit codes match `README.md:63-66` for the four ordinary failure stages
  (4 tokenize, 5 parse, 6 semantic, 3 io); the exceptions are PRD-10, PRD-11 and
  PRD-19.
- Statement count inside a function body is uncapped (1,100 statements, exit 0).
- Appendix C's identifier and numeric-literal limits are enforced exactly at the
  stated boundary, with a correct located diagnostic.
- The Zig toolchain is pinned by URL and SHA-256, verified before extraction, in
  both CI and release (`.github/workflows/ci.yml:18-20,39-44`;
  `release.yml:18-20,44-49`). This is the strongest pin in the repository.
- 22 of the 25 action references across the five workflows are pinned to commit
  SHAs; permissions are split so that the release job holding `attestations:
  write` does not hold `contents: write` (`release.yml:25-29` versus `:162-163`),
  and no workflow uses `pull_request_target`.
- `run_all_tests.sh` fails correctly: `run_check` always returns 0 so `set -u`
  without `set -e` never aborts, `FAILED_CHECKS` increments at `:40`, and
  `:95-97` exits 1.
- `scripts/verify_archive_contents.py:14-56` rejects absolute paths, `..` after
  `posixpath.normpath`, escaping sym/hardlink targets and non-regular members,
  and documents why it avoids the `lstrip("./")` laundering trap.
- `scripts/verify_release_manifest.py:50-65` rejects `..` and confines absolute
  paths; `generate_release_manifest.py:73` sorts entries deterministically and
  records no timestamps.
- The published wheel contains only `a7/**` plus dist-info; nothing else ships
  in it.
- `site/public/llms-full.txt` is in sync with all nine `site/public/docs/*.md`
  bodies, because `site/scripts/build.ts:745-749` generates it.
- `site/public/docs/start.md:21-43` is a complete getting-started path that does
  reach a running binary; its commands were executed against a copy in scratch
  and print `Hello, World!`.
- The exit-code tables in `README.md:65` and `site/public/docs/compiler.md:44-53`
  are identical, and the mode lists in `README.md:46-54`,
  `site/public/docs/start.md:62-69`, `compiler.md:31-38` and `a7 --help` agree.
- Variadic parameters and the reserved intrinsics are marked parsed-only in the
  docs and rejected by the compiler with a matching message
  (`docs/SPEC.md:833-838`, `:1550-1563`; probes exit 6 with
  "parsed for future support"), which is what `CLAUDE.md` requires.

## Test gaps

- **No test exercises the promised workflow commands** because they do not
  exist. When they land there is no harness for a subcommand CLI:
  `test/test_cli_failures.py` and `test/test_error_stage_matrix.py` both assume
  one positional file.
- **No test asserts stream separation.** No test in `test/` checks that a
  diagnostic reached stderr rather than stdout, which is why PRD-9 has survived.
- **No test captures runtime behaviour of a failing binary.**
  `grep -rln "panic" test/ scripts/` is empty; `scripts/build_examples.py:135-145`
  treats any non-zero exit as a failure and compares only successful stdout with
  a golden fixture, so no trap message is ever asserted.
- **`test/test_release_tooling.py:48` asserts `'"schema_version": "2.0"' in
  result.stdout`** — string containment, which passes on the corrupted stdout
  produced in PRD-12. It does not prove the output is valid JSON.
- **`test/test_parser_fuzzing.py:486-497` asserts exactly 1000 declarations**,
  the cap boundary, so it locks in the defect rather than testing a requirement
  (already noted by PAR-17). Passing it says nothing about programs of any real
  size.
- **No test covers the Appendix C limit table.** Nine of the thirteen rows have
  no test at any boundary; `grep -rn "Appendix C" test/` finds nothing.
- **No test covers a bad or missing Zig toolchain.**
  `scripts/build_examples.py:285` has the only check, and it is not exercised by
  a test that removes `zig` from `PATH`.
- **No test covers path robustness**: long paths (PRD-11), directory names
  containing `.a7` (PRD-17), output equal to input for a *module* file rather
  than the entry file.
- **No test compiles the A7 snippets in the docs.**
  `scripts/check_docs_style.py` checks banned phrasing over a fixed file list
  (`:20-37`, `:39-70`) and nothing else, which is why every contradiction in
  PRD-35 and PRD-36 survives the gate.
- **The release-integrity chain has no test and has never run.**
  `verify_archive_contents.py`, `generate_release_manifest.py` and
  `verify_release_manifest.py` are exercised only by `release.yml:109-135`, and
  `git tag -l` is empty (PRD-28).
- **No test pins the Zig version.** `scripts/build_examples.py:285` checks
  presence; nothing compares `zig version` with `0.16.0`, and
  `scripts/project_status.py:21` hard-codes the string.
- **`test/test_error_stage_matrix.py` asserts a magic total of 61** cases
  (already noted in `docs/audits/2026-09-16/compiler/pipeline.md:608`), so
  adding a case fails the test for the wrong reason.

## The ten things most in the way

Ranked by what stops someone outside this repository from shipping with A7.

1. **A compile can silently destroy the user's source.** `a7 x.a7 -o x.a7`
   replaced `selfdest.a7` with generated Zig and exited 0 (PRD-1).
2. **`a7 x.a7` cannot produce a program.** No `a7 build` or `a7 run` exists —
   all four promised commands are read as filenames, exit 3 — and no document
   contains the string `zig build-exe` (PRD-2, PRD-3).
3. **Exit 0 is not trustworthy.** `x, y := 10, 20` exits 0 and emits a Zig file
   whose entire content is `var y = 10;` (PRD-33).
4. **An error in an imported file points at the wrong file and line, or is
   reported as a compiler crash.** A semantic error at `sub/lib.a7:3` was
   reported as `main_sub.a7:3:9` in a record that also said `file:
   .../main_sub.a7`; a parse error in the same file exited 8 (PRD-4, PRD-10).
5. **A crash shows the user code they never wrote.** The debug binary's line
   table names only `hello.zig`, `strings | grep -c "\.a7"` is 0, and a panic
   trace quotes generated Zig with Zig stdlib frames (PRD-7).
6. **There is no version anyone can query.** `a7 --version` exits 2; `0.3.0`
   is hard-coded in two files; no version reaches the JSON payload or the
   emitted Zig, and there is no language version or deprecation policy at all
   (PRD-15, PRD-16, PRD-38).
7. **Diagnostics cannot be separated from output.** Every error in both formats
   goes to stdout; stderr was empty in all six stage probes (PRD-9). There is
   no error code, no warning, and no warning control, against SPEC Appendix B
   (PRD-8).
8. **Imports do not compose.** Appendix C requires depth 32; a three-file chain
   fails at depth 2 because transitive imports are never merged (PRD-14).
9. **The published docs disagree with the compiler and with each other.** The
   site's status page drops four of six priorities and inverts the file-import
   gap; `sqrt_f64` is advertised in three files and exits 6; SPEC §12
   documents token and AST names that do not exist (PRD-35, PRD-36).
10. **Nothing about the release is reproducible, tested, or multi-platform.**
    Release binaries embed `/home/cx89/Projects/pl-dev/a7-py/...` (27 hits);
    `git tag -l` is empty so the release workflow has never run; all eight
    `runs-on` lines are `ubuntu-latest`; and all twelve 2026-09-14 security
    findings are still live with no owner (PRD-24 through PRD-32).

## Not verified

- The full release gate (`./run_all_tests.sh`), the example artifact builds and
  `uv build` were not re-run, for the reason stated at the top. Gate results are
  quoted from `docs/audits/2026-09-16/baseline.md`.
- Behaviour on a Zig other than 0.16.0 (PRD-5). Only 0.16.0 is installed; the
  claim that another version fails inside the generated preamble is INFERENCE
  from `dbg/hello.zig:2,5,9` and from the absence of any version check.
- Behaviour on any platform other than linux-x86_64.
- What a debugger session actually displays. The DWARF line table and a real
  panic trace were read (PRD-7); no debugger was run, per the audit rules.
- Whether the `a7-wt/` worktrees for C1, C4 and C2 change any of this.
- SPEC Appendix C's "String literal length" as a *maximum*: `MAX_STRING_LENGTH`
  is reported unused by TOK-21; not independently re-checked here.
- Whether any `https://code5717.github.io/a7-py/...` URL in `README.md:186-189`
  or `site/public/llms.txt` resolves. No network request was made.
- The exact predicate `actions/attest` emits at runtime
  (`release.yml:138-145`); `predicate-type` is optional at the pinned SHA, so
  the step is well-formed, but no run exists to inspect.
- Whether remote tags exist. `git tag -l` is empty locally; no remote was
  queried.
- Untagged test files (`test_pipeline_*.py`, `test_no_recursion.py` and six
  others) are present in this working tree but not in the commit. A clean CI
  checkout at `701c679` would run a smaller pytest set than a local gate run.
  Not confirmed against an actual CI run.
- SPEC `:1982` (mandatory `(tag)` in the union grammar) against the parser: not
  probed.
- SPEC `:284` `[]char` versus `:289` `ref u8` as the string element type: not
  probed.

## Method note

Two read-only assistants surveyed areas 4 and 6 under the same rules. Their
reports are in `tmp/audit/2026-09-18/production/ci/notes.md` and in this
session's transcript. Every finding above that originates with them was
re-executed here before being written down: the three `setup-bun@v2` lines, the
three `pip install uv` lines, the eight `runs-on` lines, `git tag -l`, the
absent `py.typed`, the sdist member count (97 members, 47 from `test/`), the
27 `/home/cx89` hits in the release binary, the `verify_examples_e2e.py`
traceback with Zig off `PATH`, the `run_all_tests.sh` control flow, the
`serve.ts` and `build.ts` lines behind SEC-1, SEC-5, SEC-6 and SEC-8, the
`module_resolver.py` lines behind SEC-11, the missing `.env` rule in
`.gitignore`, the destructuring miscompile, the `@type_set` codegen failure, the
site-versus-STATUS priority lists, and six further doc claims re-run in
`tmp/audit/2026-09-18/production/p8/`: bare `sqrt_f64` and `math.sqrt_f64` (both
exit 6), a sibling file-backed import (exit 0), `a, b, c: i32 = 1, 2, 3`
(exit 5), `x: i32 = 42` followed by `x = 43` (exit 0, emits `var x: i32 = 42;
x = 43;`), `not` as an operator (exit 0, emits `(r and (!f()))`), and `arr.len`
on `[5]i32` (exit 6).

Claims in PRD-35 and PRD-36 that were **not** re-executed here, and rest on the
assistant's probes under `tmp/audit/2026-09-18/production/docs/probes/`: bare
`print`/`printf` and `open()` exiting 6, slice `.len`/`.ptr` succeeding, the
generic-declaration probes (`identity :: fn(x: $T) $T` exit 7, the `where` form
exit 5, `abs($T: Numeric)` exit 0), the generic-struct probes, and the `.val`
field-access result. Two assistant claims were corrected in the process: the
sdist ships 47 test files, not 48, and the emitted module-function prefix is
cited from `compile.py:570-572` rather than from a quoted symbol name.

claims checked: 147
