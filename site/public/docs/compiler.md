---
title: Compiler
nav: Compiler
group: Reference
summary: CLI modes, flags, JSON diagnostics, artifacts, exit codes, and the Zig boundary.
order: 31
---

# Compiler

The installed entry point is `a7.cli:main`. Run `uv run a7` from a synced
checkout, or use the equivalent `uv run python main.py` wrapper. Zig is the
only public backend. File-first commands emit Zig. The `build` and `run`
commands also invoke Zig 0.16.0.

## Pipeline

1. Read the input source.
2. Tokenize it into literals, identifiers, keywords, and punctuation.
3. Parse tokens into an abstract syntax tree.
4. Resolve names and imports, including file-backed modules.
5. Check types and validate language rules, including the source recursion ban.
6. Plan and discharge safety obligations for risky operations.
7. Preprocess the AST for backend emission.
8. Emit one combined Zig file.
9. For `build` and `run`, invoke Zig to build a native binary.
10. For `run`, execute the binary.

File-first compilation and `check` stop before the native build. A successful
A7 compilation does not by itself prove that Zig can build or execute the result.
The [example verifier](https://github.com/code5717/a7-py/blob/master/scripts/verify_examples_e2e.py)
checks all three steps and compares program output with fixtures.

## Workflow commands

| Command | Behavior |
| --- | --- |
| `a7 --version` | Print the installed package version. |
| `a7 doctor` | Report package, Python, platform and Zig versions. |
| `a7 check FILE [--format FORMAT] [--lib]` | Run the full A7 pipeline without writing files or requiring Zig. |
| `a7 build FILE [-o PATH] [--profile PROFILE]` | Build a native executable, defaulting to `./<source-stem>`. |
| `a7 run FILE [--profile PROFILE] -- [ARGS]` | Build a temporary executable and run it in the caller's working directory. |

`check` accepts `--format human` or `--format json`, with human output by default.
The entry file must define `main :: fn()`; without one, `check` exits 6 and
names `--lib`. `check --lib` accepts a library file with no entry point.
Imported modules never need their own `main`.
Both native commands require exactly Zig 0.16.0. The default profile is `debug`,
which selects Zig Debug. `release` selects ReleaseSafe and keeps runtime
checks. `fast` selects ReleaseFast and removes them. No profile closes the
current alias or lifetime safety gaps.

`doctor` exits with code 2 for missing or incompatible Zig. It also returns 2
outside the V1 qualification target of Linux x86_64 and Python 3.13. Package
installation on another environment does not establish its qualification.

`run` forwards arguments after `--` and returns the native process exit status.
A signal termination becomes `128 + signal number` on Unix. This is a process
interface only: A7 `main` takes no parameters or return value, and the standard
library has no argument-reading API.

`build` creates its output before replacing an existing executable. A failed
native build leaves the old executable unchanged. Output cannot replace an A7
source, an imported source, a filesystem alias of either, or a directory.

## Legacy CLI modes

| Mode | Work performed | Default written artifact |
| --- | --- | --- |
| `compile` | Full A7 pipeline and Zig emission | Input path with `.zig` suffix |
| `tokens` | Tokenize only | None |
| `ast` | Tokenize and parse | None |
| `semantic` | Parse and run semantic passes | None |
| `pipeline` | Full A7 pipeline including code generation | None |
| `doc` | Full A7 pipeline and documentation report | Input path with `.md` suffix |

`compile` is the default. `pipeline` writes a documentation report only when
`--doc-out` is supplied. `semantic` does not establish backend support.

## Legacy flags

| Argument | Accepted values and behavior |
| --- | --- |
| `file` | Required input `.a7` source path |
| `--mode` | `compile`, `tokens`, `ast`, `semantic`, `pipeline`, `doc` |
| `--format` | `human` by default, or `json` |
| `-o`, `--output` | Zig output path; valid only in `compile` mode |
| `--doc-out PATH` | Markdown report destination in `compile`, `pipeline`, or `doc` modes |
| `--doc-out auto` | Replace the input suffix with `.md` |
| `--backend` | `zig` by default; unknown backends fail |
| `-v`, `--verbose` | Show detailed compiler output in human format |
| `-h`, `--help` | Show CLI usage |

```bash
uv run a7 examples/001_hello.a7 --mode tokens
uv run a7 examples/001_hello.a7 --mode ast --format json
uv run a7 examples/001_hello.a7 --mode semantic
uv run a7 examples/001_hello.a7 --mode pipeline --format json
uv run a7 examples/001_hello.a7 -o /tmp/hello.zig
uv run a7 examples/001_hello.a7 --doc-out /tmp/hello.md
uv run a7 examples/001_hello.a7 --mode doc --doc-out /tmp/hello-report.md
```

## JSON output

Legacy `--format json` and `check --format json` emit a JSON object with schema version `3.0`. Read the process
exit code as well as the payload. CLI argument parsing failures use argparse's
usage text on stderr, even if `--format json` was requested.

| Field | Meaning |
| --- | --- |
| `schema_version` | Payload schema, currently `3.0` |
| `mode` | Requested compiler mode |
| `status` | `ok` or `error` |
| `input` | Input path |
| `backend` | Backend name |
| `timing_ms` | Invocation timing; not a benchmark |
| `stages` | Stages reached, with tokens, AST, semantic results, or generated source |
| `artifacts` | Paths actually written by this invocation |
| `error` | Present on failure, with category, message, details, span, and exception type. Each entry in `details` has `type`, `code` (the diagnostic code or null), `message`, `hint` (or null), `file`, and `span` when known |
| `layout` | Present with `check --layout --format json`: struct sizes, alignments and field offsets |

The `stages` keys are `tokenize`, `parse`, `semantic`, and `codegen`, when
reached. Their contents depend on the stage. For example, a successful codegen
stage contains `output_code` and `bytes`. An absent stage was not completed.
An empty `artifacts` object is normal in `pipeline` mode.

## Diagnostics and exit codes

| Code | Meaning | Response |
| --- | --- | --- |
| 0 | Success | Continue to the next toolchain step if needed. |
| 2 | Usage or toolchain error | Check arguments, output options and `a7 doctor`. |
| 3 | I/O error | Check file paths, permissions, and output destinations. |
| 4 | Tokenize error | Inspect the reported source character or literal. |
| 5 | Parse error | Check syntax at the reported location. |
| 6 | Semantic error | Check types, language rules, or safety obligations. |
| 7 | Codegen or native build error | Check backend restrictions or Zig diagnostics and preserve the failing input. |
| 8 | Internal error | Preserve the source, traceback or JSON diagnostic, and compiler revision for a bug report. |

Source diagnostics retain the originating module's file and location. Error
`details` can hold multiple diagnostics; do not report only the top-level message
when the individual errors explain the failure. `build` and `run` map Zig build failures to code 7. After a successful build,
`run` returns the program exit status instead of a compiler status.

## Artifacts

Output and documentation paths cannot overwrite an input module or one another,
including symlink and hard-link aliases. JSON artifact paths describe files
written during the current invocation, not stale files found on disk.
Multi-file input still produces a single combined Zig source file.
The `doc` report is compiler-generated information about an input program; it
is separate from this website's Markdown reference.

## Safety stance

Source recursion is banned. The semantic validator rejects direct and mutual
recursion and tracked local function-pointer alias cycles. Compiler internals
have their own ongoing conversion to stacks and worklists. Type-checker
statements now use a worklist for blocks, branches, loops and match arms.
Expression checking and type resolution still contain recursive calls.

Safety checks cover narrowing casts, division and modulo denominators, indexing
and slice bounds, nil reference use, and direct use after `del`. Alias and
lifetime gaps remain. These checks do not prove complete memory safety, and
compilation is not sandboxing. See [memory](/a7-py/docs/language/memory.md) and
[status](/a7-py/docs/status.md).

## Zig backend

The public backend targets Zig 0.16.0. Keep compile, build, and run results
separate when reporting a feature's status. Use the debug and release artifact
builders on [Release](/a7-py/docs/release.md) for native execution checks.

Evidence: [CLI arguments](https://github.com/code5717/a7-py/blob/master/a7/cli.py),
[pipeline and JSON schema](https://github.com/code5717/a7-py/blob/master/a7/compile.py),
and [error-stage verifier](https://github.com/code5717/a7-py/blob/master/scripts/verify_error_stages.py).

## Entry points and import cycles

A root function named `main` must have no parameters or return value. A file
without `main` can still compile as a library; A7 does not infer an executable
entry point for it. File import cycles report a circular-dependency diagnostic.
