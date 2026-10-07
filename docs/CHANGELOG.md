# Changelog

This file tracks only current release-facing changes. Historical review notes
belong in git history, not in long Markdown logs.

## Unreleased

The combined stage13 source passed the full release gate with 3,756 tests and
one expected failure. All 51 examples passed in every profile. See
[Status](STATUS.md) for source identity, other checks and remaining gaps.
This does not qualify full V1.

- L76 keeps import aliases local to their declaring file. Parsed forwarding
  rejects with semantic exit 6 and a direct-import example. Unsupported multi-dot
  type annotations and struct literals retain parse exit 5.
- Local generic declaration aliases that are never reassigned, passed by
  reference or captured by another function retain
  concrete body obligations. Other callable origins remain incomplete; general
  runtime generic dispatch is not implemented.

- File modules now use separate semantic scopes, name-based top-level privacy
  and distinct nominal identities. Qualified types, struct literals, constant
  array lengths and generic bodies keep their defining file's bindings.
  Semantic reports retain file and lexical owners. Imported constant writes
  name the qualified constant in the diagnostic.
- Known direct global reference stores propagate allocation identity through
  calls. Deletion invalidates represented caller aliases while live replacements
  remain usable. Equivalent positive increments on alternative loop paths can
  prove one trip without weakening post-loop deletion checks. Global nil-state
  and parameter proof gaps remain open.
- The docs-site lockfile uses source-map-js 1.2.2, fixing the upstream indexed
  source-map denial-of-service advisory GHSA-68fv-2mgg-jv7q.

- The L74 safety repair rejects nil reference-field access, repeated field
  deletion, and direct reference alias use after deletion with exit 6. Guarded
  access, distinct allocations and fresh reassignment remain accepted. Aliases
  through array elements and joined allocation field paths remain unqualified.
- File imports resolve relative to the importing file. Parent paths work within
  the entry directory; paths and symlinks that escape it remain rejected.
  Canonical file identity unifies alternate spellings for caches and cycles.
  Per-module semantic scopes now precede whole-program identity lowering.
- Local bindings that reuse their own file's import aliases now fail with
  semantic exit 6 under L28. Parameters, loop bindings and match captures follow
  the same rule; field names and another file's aliases remain independent.
- Capture-free nested functions receive symbols, signatures and body checking.
  Forward calls and returned nested functions compile. Wide enum values use
  the existing backend tag selection instead of an unconditional i32 check.
- Generic local initializers are checked against concrete call-site types,
  including forwarded generic calls. A numeric initializer instantiated as
  `string` now fails with exit 6 before Zig generation. Constant range-pattern
  aliases resolve with a loop instead of recursive calls.
- Bound generic callback signatures survive local assignment and branch
  selection. Generic `if`/`match` initializers use concrete destination fitting.
- AST structural equality and debug display handle deep parsed trees with
  explicit worklists, preserving declared-field comparison and cycle behavior.
- Statement, expression, type and pattern parsing use worklists, preserving
  token order, lookahead recovery and the existing 256-level logical nesting
  limit.
- Type resolution uses a stack for compound types and alias dependencies.
  Alias caches distinguish declarations with the same name. A string assigned
  through a shadowed integer alias now fails with semantic exit 6.
- Type diagnostic representations use an explicit stack while preserving
  inherited dataclass fields, evaluation order and cycle markers.
- Array-literal arms in `if` and `match` fit declared element types, including
  nested arrays, generic locals and bound callback arguments. Overflow and
  typed-array narrowing remain semantic errors.
- Type-checker statements, expressions and patterns use worklists, preserving
  scope, facts, initializer fitting and diagnostic order.
- Zig statement, expression and type emission use worklists, preserving output
  bytes, emission order and diagnostic causes in the checked comparisons.
- Safety statement traversal uses suspended frames. The recursive-group,
  deepcopy and generated-method exception lists are empty in the frozen
  integration. Compact allocation graphs remove the measured factory-origin
  expansion.
- Bounded exact callee effects propagate reference-field replacement/deletion
  through supported calls. Nested-function global deletion reaches callers;
  global body effects apply after argument evaluation. General alias/lifetime
  analysis remains incomplete.
- Semantic call-summary helpers and inferred-type emission use explicit stacks.

- Safety expression traversal uses an explicit stack. Long runtime expression
  chains reach code generation without exhausting the Python call stack.
  Statement traversal now uses a separate worklist.
- The local gate uses `A7_PYTEST_WORKERS`, from 1 to 8, with a default of 8.
  Invalid values fail before any check runs.

- Type checker: types can be used before their declaration, and a
  struct that holds itself by value exits 6. `nil` has its own type:
  `p = nil` on a reference works; `x == nil` on a non-reference exits
  6. Assignment to a field or element of a constant, of a by-value
  parameter or of a string exits 6. `i32 & i64`, arithmetic on an
  unconstrained `$T`, and `==` on structs or arrays exit 6. A typed
  integer no longer converts to a float without `cast` (ledger L72).
  `case NAME:` compares against a file-scope constant wherever it is
  declared. An unknown generic constraint exits 6. An if-expression
  takes its destination type. Each mistake reports once, and an
  undefined variable is reported as an undefined identifier.
- Backend: inline generic functions (`identity :: fn(x: $T) $T`) and
  file-scope `@type_set` aliases compile and run. Strings compare by
  content in `==`, `!=` and `match`. Names such as `u1`, `std` and
  `void` work as identifiers. `xs := [1, 2, 3]` is a typed array, so a
  run-time index and `for v in xs` work. A nested function that
  captures nothing is hoisted; one that reads an enclosing variable
  exits 7 and names it. Internal fallbacks that emitted wrong code now
  raise an error.
- Parser (ledger L62): a statement ends at a newline, `}` or end of file,
  and list items need a comma (struct fields, enum variants and union
  fields may use a newline instead). `x := 1 2`, `Pair(i32 i64)` and
  `enum { A B C }` exit 5. A number runs into no identifier: `123abc`
  and `1.5.3` exit 4. Also rejected: `1 = 2`, a parameter without a
  type, a second `else:` in a match, `if c ret` without a block, an
  if-expression without `else`, `pub import "x"`, a char literal above
  code point 255. Now accepted: a long `if` condition ending in a name,
  a struct literal inside a one-line `if` body, `f :: fn()` with the
  brace on the next line, `cb: fn()` as a struct field, a positional
  struct literal over several lines, `using import "p"` (parsed and
  recorded). Char-literal errors say what is wrong. Nested call
  arguments parse in linear time. No example or bench program changed.
- Diagnostics: human-readable errors go to stderr in every command and
  name their file on a `--> path:line:col` line, including errors in
  imported modules. `a7 check` prints the same snippet and hint as a
  compile. Safety-proof errors carry a hint that shows the accepted
  guard, such as `if n != 0 { ... }`. A message that contains `[` no
  longer breaks the output.
- JSON output is schema `3.0`: each detail has `code` and `hint`, its
  `message` no longer repeats `file:line:col`, proof failures have type
  `SafetyError`, and `check --layout --format json` adds a `layout`
  key. Very deep programs produce valid JSON.
- CLI: the default output path is derived from the file name only, so a
  directory named `x.a7proj` is left alone. `-o` refuses a destination
  that ends in `.a7`. `--mode semantic` accepts programs that import
  file modules. `a7 --version` works beside other arguments.
- `check --layout` matches Zig's sizes and offsets for unions,
  single-variant enums and function-pointer fields in the `debug` and
  `release` profiles; `fast` drops the hidden tag of an untagged union.
- Build profiles: `--profile release` now builds with Zig ReleaseSafe and
  keeps runtime checks; the new `--profile fast` builds with ReleaseFast.
  Compatibility: a release build that used to run unchecked now traps
  where debug traps and runs slower on print- and allocation-heavy code;
  use `fast` for the old behavior.
- Initialization: a declaration without an initializer and every `new T`
  start as all zeros (nil for references, empty for slices). They read
  garbage before. Function-pointer locals are the exception and still
  need a value before use.
- Integer edges are defined in every profile: `MIN / -1` and `-MIN` wrap
  to `MIN`, `MIN % -1` is 0, `math.abs(MIN)` is `MIN`. A shift by a
  run-time count outside the bit width panics with "shift count out of
  range". `x <<= n`, `1 << n` and `~5` build.
- Output: stdout flushes before a panic and at each newline on a
  terminal. A write to a closed pipe (`prog | head -1`) ends the program
  quietly with status 0.
- Recursion ban: recursion through a function value (an alias of an
  alias, a struct field, an array element, a returned function, a
  function constant, an if-expression) exits 6. `ret`, `break`,
  `continue` or `fall` leaving a `defer` exits 6. A nested function
  body gets the same control-flow and return checks as a top-level one.
  `while true { ... ret ... }` needs no trailing `ret`.
- Safety: programs that passed the proof and then crashed are now
  rejected with exit 6. A fact no longer survives a loop that may run
  zero times, a `defer` is proven at scope exit instead of at its own
  line, a shadowed name no longer lends its facts to the outer name, a
  call to a user function forgets facts about file-scope variables, and
  an arm reached by `fall` no longer ignores the falling arm. Deleting
  a value twice through `defer del` exits 6. `if b == nil { continue }`
  now proves `b` non-nil afterwards. Compatibility: a guard may need
  repeating after a loop or a call.
- Generics: `union(tag)` declarations with `$T` fields specialize
  positionally like structs, so `Result(i32, string){ok: 1}` passes
  and `r.ok` resolves; a wrong field type or unknown field exits 6.
  Pinned in `test/test_generics_fast_union.py`.
- Generics: conflicting `$T` bindings at one call site exit 6 with
  `GENERIC_PARAM_MISMATCH` naming both types; matching bindings still
  pass. Generic enums are skipped (no payload types). A wrong number of
  type arguments exits 6 and names the expected parameters.
- Generics: `$N` value params on fns, structs, and unions. `$N` takes
  `usize`, `bool`, or small int values through named constants
  (`Buf(SIZE)` with `SIZE :: 4`, including folded constants such as
  `SUM :: 2 + 2`); distinct values are distinct types. A value of the
  wrong kind or range, a type for a value parameter, or a value for a
  type parameter exits 6 at annotations and literals. Literal value
  args and call-site inference stay open. Pinned in
  `test/test_generics_value_params.py`.
- Generics: minimal `where` conjunctions (`where T: Numeric`) on
  generic fns, structs, and unions. Richer predicates and `where` on
  enums exit 6. Pinned in `test/test_where_clauses.py`.
- Match: tagged-union arms use leading-dot patterns. `case .none:`
  tests a tag, `case .ok(v):` binds a copy of the payload, and `else:`
  opts out. A bare `case tag:` exits 6; uncovered tags produce one
  error listing each missing tag. A payload that is or holds a `string`
  cannot bind by value. A `ref` to a tagged union matches the same way.
  Pinned in `test/test_match_payload.py` and
  `test/test_match_dot_e2e.py`.
- Stdlib: `io.println_ok` and `io.read_line` construct `Result`
  union values in generated code. `read_line` keeps one stdin reader
  for the program, flushes stdout first, and reports end of input and
  a read error as different `err` values. Matching on the call still exits 6
  until the checker types them as `Result`; `get`/`pop` and `or{}`
  with `use` stay deferred. Pinned in `test/test_stdlib_result.py`.
- Codegen: single parens in conditions and left-assoc chains; native
  `switch` for a match whose scrutinee is an integer, char, bool or enum
  and whose arms are constants (other matches keep the if-chain). No
  runtime behavior change. `ref` parameters stay `?*T`. A capture in a
  `del` no longer collides with a user variable named `p`. A `defer`
  takes any statement; a directly deferred `ret`, `break`, `continue`
  or `fall` exits 7. New examples `049_expense_ledger` and
  `050_tip_split`. Pinned in `test/test_codegen_emit.py`,
  `test/test_match_dot_e2e.py` and `test/test_del_defer_codegen.py`.
- Tests: pin duplicate-import exits (same path, `./` spelling, symlink,
  reused alias), unclosed and nested-unclosed comment exits, and
  imported-file stage attribution in `test/test_import_error_stages.py`.
- Match ranges: a constant reversed range (`case 10..1`, including
  const-alias, char, and match-expression forms) exits 6 with
  `invalid_pattern`; swap the endpoints to fix. Ranges with bounds known
  only at run time keep matching nothing. Pinned in
  `test/test_match_ranges_break.py`.
- Docs: align SPEC sections 2.1, 2.2, 2.3, 2.5, 2.6, float-to-int proof,
  10.2 through 10.2.2, 10.4, 11.2, 12.1, the limits table, and Appendix D
  with current behavior; no behavior change.

- A declaration initializer reads the outer binding, so `y :: y + 1` inside a
  block means the outer `y` plus one. Match-expression arms use their own
  scopes, so a later match statement no longer resolves arm bindings to an
  outer declaration. A bare call to an imported module's function from the
  entry file exits 6 and names the qualified spelling.
- Constant arithmetic is exact and then fitted to its destination
  (ledger L61). `MONTH_MS :: 30 * 24 * 60 * 60 * 1000` into an `i64` is
  2592000000. `x: i32 = 2147483647 + 1` exits 6. `0.1 + 0.2 == 0.3` is
  true. `b: f64 = 1e308 * 10.0` and a float division by constant zero
  exit 6. `1 << 40` into an `i64` folds exactly. An untyped integer with
  no destination type defaults to `i32` everywhere, so
  `io.println("{}", 5000000000)` exits 6 and needs a typed value.
  A literal such as `1e999999999` exits 6 instead of hanging the
  compiler. Compatibility: programs that relied on a wrapped or
  infinite constant, or on an `i64` default, now exit 6 or print the
  exact value. An integer zero divisor stays for the safety proof.
- A file with no `main :: fn()` entry point is rejected at the Entry Point
  stage with exit 6 instead of passing check and failing late at the Zig
  build. Imported modules are exempt; only the entry file needs `main`.
  `a7 check --lib` (and `main.py --lib`) checks a library file without one;
  `build` and `run` still require it.
- Resolve bare calls inside imported modules to the defining module and emit
  the module prefix, so sibling calls build. Type-check alias calls `h.f()`
  with generic inference and comptime arguments, and reject calls to functions
  the module does not define with exit 6.
- Load transitive import chains to a fixed point. Enforce struct generic
  constraints at instantiation with exit 6, and raise a codegen error for an
  unresolvable generic return type instead of emitting void.

- Add `a7 check FILE --layout`. It prints each named struct's Zig memory
  layout: alignment-ordered field offsets, size, 64B lines touched, line-use
  percent, and field-access counts as a hot/cold hint. Offsets match Zig
  0.16.0 `@offsetOf` ground truth, pinned by tests.
- Add `aos_walk`, `soa_walk`, `stride_walk`, and `kv_append` benches. The
  AoS/SoA pair runs identical work on identical footprints: parallel arrays
  measure 1.59x faster than a 24-byte struct array (0.174s vs 0.277s,
  ReleaseFast medians of five on one host). `stride_walk` measures line
  utilization; A7 has no threads, so it is not a coherence test.
- Add a ten-program bench corpus and `scripts/bench_perf.py`. It times
  ReleaseFast builds (median of N runs, trimmed for five or more) and compares them with
  per-host pins in `bench/pins/<host>.json`. `run_all_tests.sh` runs it
  report-only; `--gate` exits 1 past 1.15 times the pinned median.

- Release builds allocate through `std.heap.smp_allocator`. Debug builds keep
  `std.heap.page_allocator`.

- Buffer stdout print helpers in one persistent 4096-byte writer, flushed at
  program exit and before every stderr write. Stderr keeps per-call flush, so
  stdout content always precedes later stderr content for completed programs.
  Release builds lower proven-range integer `+`, `-`, `*` and compound forms
  to non-wrapping operators; debug builds and unproven cases keep wrapping.
  Add `--no-nonwrap` to force wrapping and `--build-profile` plumbing to
  select the build profile.

- Display type-set AST nodes without crashing. Bound malformed type and defer
  cycles in console output while preserving repeated shared nodes.

- Keep the continuing branch's actual safety facts after an early return. A later
  assignment, mutating call or deferred write cannot restore an old nonzero guard.
- Discard unused loop-update call results while preserving continue/break order.
- Exercise installed check/build/run/doctor/version commands from both wheel and
  source-distribution builds, including exact version identity and error cases.

- Add `a7 check`, `a7 build`, `a7 run`, `a7 doctor`, and `a7 --version`.
  Native builds protect loaded sources and require Zig 0.16.0. Reuse the loaded
  source list instead of parsing imports twice.
- Render nested type names and console labels with explicit stacks. Escape
  token values, AST literal details and source-panel filenames in Rich output.
- Preserve fixed-array assignment evaluation order, escape control bytes in Zig
  character literals, and discard deferred return values and unused constant results.

- Load deep module dependency chains iteratively and discard incomplete cache
  entries after a failed load, so fixing a missing dependency permits a clean retry.
- Verify installed wheels and source distributions by running a multi-file
  program in Zig debug and release profiles outside the checkout.
- Add one local/CI release command with tag/version/changelog checks, docs checks,
  locked dependency audits and static scanning. Resolve Git before the secret scan.
- Record the core V1 scope, automatic runtime memory option, 10% performance
  target, Zig integration and later A7-written compiler direction.

- Replace recursion in integer-literal extraction, mutation-base analysis and
  symbol-table dumps with iteration. Strengthen the internal recursion scanner
  for dispatch dictionaries and deferred callbacks. Full compiler conversion
  remains in progress.

- Reject malformed declarations without dropping source, and report malformed
  numeric separators and unsupported ellipses as tokenizer errors.
- Invalidate safety facts across branches, loops, mutating reference calls,
  and deferred deletion. Reject the audit's accepted-crashing programs before
  native output. Example guards now state the bounds and divisors they require.
- Align arithmetic types with native operands, apply defined wrapping to integer
  addition, subtraction and multiplication, and repair compound division and
  remainder lowering.
- Repair IO brace escaping, signed absolute-value result typing, backend names,
  string array defaults, and generic array/slice field types.
- Accept in-range literals in argument and return contexts and literal constant
  array bounds. Diagnose invalid entrypoint signatures and import cycles.
- Preserve match-expression fallback nodes in JSON output. Replace classifier-
  derived cast test expectations with an independent policy table.

- Rebuilt the documentation site with light and dark themes, persistent navigation,
  a guided tour, an example index, and twelve language reference topics.
- Added Markdown twins, feature metadata, body-text search, and explicit generated
  export checks. Removed invented compiler-success transcripts and documented
  native failures found while checking reference examples.

- A deferred statement that assigns inside a loop no longer leaves a stale
  proof behind, so `while ... { defer x -= 5; y := 10 / x }` is rejected
  instead of dividing by zero at run time.
- Corrected three documents that said typed math spellings such as `sqrt_f64`
  are callable bare builtins; they exit 6.
- Aligned the public status page with `docs/STATUS.md`: six active priorities
  and the three known gaps the page had dropped.
- Pinned `oven-sh/setup-bun` to a commit and `uv` to a version in CI, release
  and docs workflows.
- Prevented output and documentation writes from overwriting source modules or
  each other. Artifact reports now describe files written by the current run.
- Corrected operator-token columns and preserved imported diagnostic locations.
- Corrected Zig keyword escaping and unused or shadowed loop captures.

- Constant float remainder now uses the Zig runtime truncation rule, including negative
  dividends and signed zero.

- Confined docs preview requests and release manifest reads to their allowed
  directories, with regression checks for encoded paths and symlinks.
- Dependency audits now read exported locked project requirements.
- Release packaging reuses gate-verified distributions and native examples.
- Removed repeated pytest subsets from the local gate and duplicate AST child
  enumeration from preprocessing. Parser block errors propagate directly.
- Reconciled public status, recursion limits, and research/audit navigation.
- Render numbered documentation steps as ordered lists.
- Removed six alternate historical pointer PDFs and retained the main report.
- Repository secret checks now honor Git ignore rules for untracked files while
  still checking tracked ignored files.

- Consolidated project-status documentation around the current Zig-only
  compiler surface and removed stale review/audit handoff files.
- Added `scripts/project_status.py` as the source for example counts and small
  release facts.
- Release archive verification now derives example counts from the repository
  instead of duplicating fixed numbers.

## 0.3.0

- Installed `a7` CLI entrypoint.
- Zig is the only supported public backend.
- Added debug and release example artifact verification.
- Added wheel install smoke verification.
- Added checksum and archive-content verification for release artifacts.
- Added internal safety proof planning and operation-specific backend approvals
  for casts, division/modulo, bounds-sensitive indexing/slicing, ref
  dereferences, and direct use after `del`.
- Expanded the verified example suite to 43 runnable programs.
