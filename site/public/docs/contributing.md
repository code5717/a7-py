# Contributing

A7 is an open project. Contributions are welcome — read this before
sending a PR.

## Before you start

1. **Read the [Status](/a7-py/compiler/status) page.** It lists active
   priorities and deferred tracks. Don't open a PR against a deferred
   track without a design discussion first.
2. **Read [Why A7](/a7-py/learn/why).** The design philosophy is the
   filter that decides whether a feature lands.
3. **Run `./run_all_tests.sh` on `master`.** Confirm your checkout is
   clean before changing anything.

## Workflow

```bash
# 1. Fork & clone
git clone https://github.com/<you>/a7-py.git
cd a7-py
uv sync

# 2. Branch
git checkout -b feature/short-name

# 3. Make changes — see "House rules" below

# 4. Run the gate
./run_all_tests.sh

# 5. Commit + push + open a PR
```

## House rules

These are non-negotiable. PRs that violate them get a comment, not a
merge.

### Compiler internals are iterative

Semantic passes, AST preprocessing, formatter walks, and most backend
emission paths use explicit stacks, not recursion. CI runs the
supported pipeline at Python recursion limit `100`. Don't reintroduce
recursion in compiler internals. The parser is the exception (recursive
descent, depth-bounded by source nesting).

### A7 source recursion is banned

Don't add examples, tests, or docs that rely on recursive A7 functions.
The semantic validator rejects them anyway, but seeing them in the docs
suggests they work.

### `usize` for sizes and indices

Use `usize` for array indices, lengths, capacities, allocation byte
counts, and slice bounds. `isize` is reserved for signed pointer-sized
offsets. Most signed-integer arithmetic uses `i32` or `i64` explicitly.

### `new [N]T` is currently rejected

Don't write examples, tests, or docs that allocate heap fixed arrays.
Use stack arrays or slices. This will change when the language model
for heap fixed arrays is defined — not before.

### No address-of / dereference operators in source

`&`, `*`, `.adr`, `.val` are not public A7 syntax. Pass lvalues directly
to `ref` parameters and use `.` field access after nil checks.

### Docs and code stay in sync

If your change affects a user-visible behaviour, update — in the same PR:

- `README.md`
- `docs/SPEC.md`
- `docs/STATUS.md`
- `docs/CHANGELOG.md`
- The matching page under `site/public/docs/`

`site/public/llms.txt` and `llms-full.txt` are auto-regenerated; commit
the updated files after running `npm run build` under `site/`.

## What lands easily

- New example programs that exercise existing language features.
- Bug fixes with regression tests.
- Diagnostic message improvements.
- New stdlib functions in shipped modules (`std/io`, `std/math`,
  `std/mem`, `std/string`, `std/debug`, `std/random`).
- New compiler-internal pass refactors that *increase* iterative
  coverage.

## What needs a design discussion first

Open an issue and tag it `design` before writing code:

- New language constructs (new keyword, new operator).
- Changes to semantic-pass order.
- New backends.
- New stdlib modules.
- Changes to safety proof obligations.
- Anything touching the [Deferred tracks](/a7-py/compiler/status#deferred-tracks).

## Commit messages

Keep them short. Imperative mood. Include why, not what.

```text
Reject mutual recursion via function-pointer aliases

Caught a case where an alias variable could be assigned a function
that called back through the same alias. Reachability needed a worklist
expansion to detect.
```

Co-authors and reviewers get credit in trailers, not in the subject.

## Reporting bugs

Open an issue at <https://github.com/Airbus5717/a7-py/issues>. Include:

- A7 source that triggers the bug (minimal repro preferred).
- CLI command and flags.
- Full output, including exit code.
- The commit SHA of your checkout (`git rev-parse HEAD`).
- Zig version (`zig version`).

## Code of conduct

Be kind. Critique code, not people. Disagreement is fine; condescension
is not.
