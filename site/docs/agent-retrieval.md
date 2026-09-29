# Agent retrieval trial

Date: 2026-09-19. Result: all five information-retrieval tasks passed. This trial checks discovery and documented answers. It does not certify compiler semantics, build success, or runtime behavior.

## Method

An independent agent began at `http://127.0.0.1:4174/a7-py/llms.txt`, followed its Markdown links, and retrieved pages with curl without JavaScript. Published `https://code5717.github.io` origins were replaced with `http://127.0.0.1:4174`. No repository files or compiler source were read. No installation, compilation, or program execution commands were run. The only filesystem write was this report.

## Fetched URLs

All existing URLs below returned HTTP 200. Markdown and llms.txt responses used `text/plain; charset=utf-8`.

- http://127.0.0.1:4174/a7-py/llms.txt
- http://127.0.0.1:4174/a7-py/docs/start.md
- http://127.0.0.1:4174/a7-py/docs/language/memory.md
- http://127.0.0.1:4174/a7-py/docs/language/generics.md
- http://127.0.0.1:4174/a7-py/docs/examples.md
- http://127.0.0.1:4174/a7-py/docs/compiler.md
- http://127.0.0.1:4174/a7-py/docs/status.md
- http://127.0.0.1:4174/a7-py/docs/manifest.json
- http://127.0.0.1:4174/a7-py/docs/tour.md
- http://127.0.0.1:4174/a7-py/docs/language/functions.md

The missing-path probe was `http://127.0.0.1:4174/a7-py/docs/retrieval-missing-page.md`. It returned HTTP 404 with `text/plain;charset=utf-8`. The manifest returned HTTP 200 with `application/json; charset=utf-8`. Both transport checks passed. The initial manifest body exceeded the tool output budget, so this report makes no completeness claim about its contents. Its response headers were checked again separately.

## Retrieved answers

### Install and run a first program

Pass. `docs/start.md` states the prerequisites: Python 3.13 or newer, uv, Git, and Zig 0.16.0 on PATH. It supplies the following commands:

```bash
git clone https://github.com/code5717/a7-py.git
cd a7-py
uv sync
uv run python --version
zig version
uv run a7 examples/001_hello.a7
zig run examples/001_hello.zig
```

The documented expected output is `Hello, World!`. A7 emits Zig source. The separate Zig command runs the program. The page also gives `zig build-exe examples/001_hello.zig -femit-bin=hello` and `./hello` for a retained executable, with the Windows `.exe` variant.

### Pass a mutable struct through a reference parameter

Pass for retrieval. `docs/language/functions.md` provides this declaration:

```a7
Counter :: struct {
    value: i32
}
increment :: fn(counter: ref Counter) {
    counter.value += 1
}
```

The same page explicitly says to call `increment(counter)`. `docs/language/memory.md` explains that the ordinary lvalue refers to caller storage and that the caller observes the changed field. No public address-of or dereference operator belongs at the call. Receiver syntax such as `counter.increment()` is planned, not current support.

The function page's excerpt does not include a complete caller initialization and output assertion. The tour demonstrates split declaration and assignment for a scalar reference argument. The retrieved pages give enough syntax to answer the task, but this trial did not validate a newly composed full struct program. Reference passing does not establish complete alias or lifetime safety.

### Explain a limitation with its support qualification

Pass. `docs/language/generics.md` labels generics limited. It says a top-level alias such as `IntOnly :: @type_set(i32, i64)` passes semantic checking but fails Zig code generation on an unsupported `TYPE_SET` node. A predefined `Numeric` constraint and an inline `$T: @type_set(i32, i64)` constraint work in the documented direct-call examples. These do not establish arbitrary call-chain or cross-module specialization. This qualification prevents confusing semantic recognition with executable support.

### Find a runnable generic example and expected output link

Pass for discovery. Both `docs/tour.md` and `docs/examples.md` identify the checked-in example and its command pair:

```bash
uv run a7 examples/014_generics.a7
zig run examples/014_generics.zig
```

- Source: https://github.com/code5717/a7-py/blob/master/examples/014_generics.a7
- Expected output: https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/014_generics.out

The tour describes integer and string identity calls, boxes, nested boxes, and a pair. The example index explicitly warns that the fixture is expected output, not evidence that a fresh checkout has passed. These external GitHub links were discovered but not fetched, so their HTTP availability and current contents remain unchecked.

### Interpret compiler exit code 6

Pass. `docs/compiler.md` defines code 6 as a semantic error. Check types, language rules, or safety obligations. With `--format json`, inspect the process exit code and error details, including individual diagnostics and originating module locations. Zig build failures and program exit codes belong to separate processes and do not use the A7 compiler table.

## Ambiguities and boundaries

No broken local links appeared among the selected pages. The deliberate missing path returned 404 rather than an HTML success fallback. The pages distinguished current support, limitations, expected outputs, and future plans. The mutable-struct task required combining the function declaration with the memory page's caller-storage explanation. A complete small caller example on the memory page would reduce that retrieval step.

This was selective retrieval, not an exhaustive link crawl. External evidence links, all manifest entries, and compiler execution remain outside this trial's results.

## Follow-up after the caller example was added

At 2026-09-19 18:43:59 UTC, a fresh curl request to `http://127.0.0.1:4174/a7-py/docs/language/memory.md` returned HTTP 200 with `text/plain; charset=utf-8`. The page now includes a complete program with the `std/io` import, `Counter` declaration, `increment(counter: ref Counter)` function, and `main` caller. The caller initializes `counter`, sets `counter.value = 41`, calls `increment(counter)`, and prints the field. The documented output is `42`.

The earlier missing-caller observation is resolved. A reader can now retrieve the complete mutable-struct reference example from the memory page alone. This follow-up checked the served documentation only; it did not compile or execute the program.
