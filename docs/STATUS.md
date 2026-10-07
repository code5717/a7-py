# A7 Status

This is the single working status document for current gaps, roadmap, and
implementation priorities. Keep `docs/CHANGELOG.md` short and release-facing.

## V1 completion boundary

V1 is not complete. L73 requires core language and automatic memory, useful
libraries and tools, structured concurrency, CPU AI, actual GPU execution and
self-hosting parity before publication. The [delivery roadmap](plan/delivery-roadmap.md)
records the sequence and requirement-specific evidence. Unresolved designs need
approval before dependent changes; L69 already authorizes file-module scopes.

The current readonly-call integration matches frozen source manifest `cf6a985d`.
Its full release gate passed 3,896 tests with one expected failure and all 11
compiler/package checks. All 51 examples passed E2E and artifact checks in each
profile; package installation, site and dependency/static checks passed.
All 1,617 frozen file hashes and modes stayed unchanged. The
[readonly verification record](audits/2026-10-07/readonly-v3-verification.json)
separates these results from independent reviews and six native controls.
Final evidence prose is checked separately. The
[October 7 qualification history](audits/2026-10-07/qualification.md) preserves
earlier checkpoints, failed runs and their recoveries. V1 remains incomplete.

GPU execution is deferred under L75. The
[Zig GPU research](research/2026-10-07-zig-gpu-support.md) separates installed
0.16, stable 0.17 and development support, host APIs and compile-only results.
It does not qualify device execution. L73's GPU publication requirement stays open.

The [published documentation checkpoint](audits/2026-10-07/published-docs-verification.json)
passed 16 HTTP content comparisons against the frozen build. Browser interaction
and responsive rendering remain unverified because no browser connection was
available. This does not satisfy final publication acceptance.

## Current Surface

- Zig is the only supported public backend.
- Constant float remainder follows the runtime truncation rule, including the
  dividend sign and negative zero.
- The compiler pipeline covers tokenization, parsing, semantic analysis,
  internal safety proof planning, AST preprocessing, and Zig code generation.
- Output paths cannot overwrite input modules. Diagnostics retain module origins;
  artifact reports exclude stale files.
- Source recursion is banned. Use loops, explicit stacks, queues, and
  index-based worklists.
- `a7 check FILE --layout` reports struct memory layout (alignment-ordered
  offsets, size, 64B line use, field-access counts), matching the emitted
  Zig binary in the `debug` and `release` profiles. `fast` drops the hidden
  tag of an untagged union.
- The bench corpus measures layout effects: the AoS/SoA pair proves
  parallel arrays 1.59x faster than struct arrays for subset-field loops
  (`bench/`, `scripts/bench_perf.py`).
- The example suite is verified against golden output fixtures. Current counts:
  `uv run python scripts/project_status.py`.
- The perf gate times the ten-program `bench/` suite as median-of-N
  ReleaseFast (`--profile fast`) runs against per-host pins in `bench/pins/<host>.json`.
  `run_all_tests.sh` runs `scripts/bench_perf.py` report-only; `--gate` exits 1
  past 1.15 times the pinned median.

The safety pass keys facts by declaration, not by name, and joins state
at branches, loops and scope exits (2026-10-04 repair):

- After a loop, the state is the loop-entry state with everything the loop
  can assign forgotten and everything it can delete marked moved. The
  negated loop condition holds only when no `break` can leave the loop.
- A deferred statement is proven at every exit of its block (end, `ret`,
  `break`, `continue`), in reverse registration order.
- A call to a non-stdlib function forgets every fact about a file-scope
  variable. A `ref` argument passed to a function value or other unknown
  callee counts as deleted.
- An arm reached by `fall` starts from the join of both entry states.
- A match capture, a loop variable and a shadowing local each start with
  no inherited fact.

This closes the audit's loop, defer, shadowing and callee-identity holes,
SAF-3 fallthrough division and SAF-6 global mutation across calls (ledger
L71). The approved L74 repair rejects SAF-2 user-field `ptr` nil access,
SAF-8 repeated field deletion, and direct reference alias use after deletion
(`c := b; del b; c.value`). The seven original valid controls ran in all three profiles against an
earlier safety.py revision, as recorded in the
[qualification boundary](audits/2026-10-07/qualification.md). Later nested-record,
wrapper and match repairs are included in the passing integration gate.
Aliases through array elements and joined allocation field paths remain open
release blockers. On the reviewed snapshot, deletion through a borrowed
aggregate left a caller alias alive in the proof state; callee field replacement
could retain the previous allocation's identity. The same snapshot rejected
valid parent/sibling use after child-only deletion and valid parent use when a
callee deleted an unrelated local allocation. The bounded exact-callee repair passes focused semantic and native controls,
including borrowed-field deletion, replacement and parent/sibling preservation.
It also repairs nested-function global summaries and delays global body effects
until after argument evaluation. These repairs are included in the passing
integration gate.
Exact replay permits at most one transitive conditional and source-sized expanded
work. A doubling call chain can exceed this budget at depth three; this is a
work bound, not a fixed depth guarantee. Selected-child lifetime dependencies
now preserve the represented aliases without marking every possible child
deleted. Focused and independent compile-only checks, native controls in all
profiles and the integration gate pass. Stores through a selected holder can still leave an original base's
field facts stale, and joined-holder nil-write invalidation remains incomplete.
Other paths retain incomplete legacy analysis. A later candidate repairs
loop-head deletion through a reference-field argument and a loop-local alias.
It preserves unrelated allocations, fresh factory returns and valid one-trip
loops. It also separates returning cleanup from continuing paths. That candidate
passes 294 focused nonnative tests and replays 65 reviewer cases. GLM review matched 165 behavioral cases; the full integration gate above
predates it.
Independent review also found exponential fresh-origin expansion in a small
acyclic factory chain. Compact allocation graphs now retain 196 nodes for the
depth-64 reproducer. Independent comparison of 16 programs preserves exits,
diagnostics and generated Zig; 159 integrated focused tests pass. The depth-64
valid control runs in all three profiles. GLM review matched 68 paired programs
and reproduced the resource counts. The published `1857e03` integration run passed 3,602 tests
with one expected failure, 51 examples in each build profile, and native package
installation. Its secrets check failed because the snapshot lacked Git metadata.
After metadata recovery, that check and all skipped release checks passed on
unchanged sources. The later integration candidate propagates direct global
reference stores and deletion effects across known calls. It preserves captured
arguments, saved old globals and distinct live replacements. Its one-trip proof
also accepts separate positive increments on alternative paths when every
backedge crosses the bound without wrapping. Post-loop deletion checks remain.
Global nil-state summaries and parameter proof obligations remain incomplete;
the unsafe nullability/branch-precision trial `68f` is excluded. Nil-origin
trial `f521` is also excluded after a confirmed valid false-branch control
regressed. Conditional origin relations and callee preconditions remain open.
The integrated literal-return repair selects precise return facts for simple
direct callees and literal boolean arguments. Its frozen 1,601-file snapshot
passed the full release gate: 3,772 tests passed, one expected failure, and
all 11 compiler/package checks passed. Native controls passed in debug,
release and fast profiles, including later-argument mutation of a reference.
The external review completed 73 compile-only pairs: 17 new rejections,
four valid acceptances, 30 unchanged acceptances and 22 unchanged rejections.
Its first invocation failed a provider rate limit; the retry completed.
General effectful returns and nonliteral selectors remain open. That literal-return
checkpoint used safety source `0d8b3938`; the current readonly integration uses
`c51f8378` with readonly requirements `aeefd7cf`. It adds rejection-only call
requirements for represented branches, defers and certified loops. The earlier
stale-counter and borrowed-scalar failures are preserved in isolated candidates;
their repairs passed independent review and the latest full release gate.
General callee and container proofs remain incomplete.
See the [container-identity proposal](plan/packets/P-REF-container-identities.md)
for the separate array/slice/selected-value decision boundary.
The October 4 runtime-contract
repair defines signed minimum-value arithmetic and checks runtime shift counts;
those former gaps no longer describe that checkpoint. See
`test/test_checked_arithmetic_edges.py` and `test/test_build_profiles.py`. A loop that deletes and then reassigns one
reference in its body is rejected. The checks do not establish complete
alias or lifetime safety. Pinned in `test/test_safety_loop_facts.py`,
`test/test_safety_defer_facts.py`, `test/test_safety_binding_identity.py`
and `test/test_safety_stale_facts.py`.

## Active implementation priorities

1. Keep status and release facts script-derived, not hard-coded.
2. Qualify per-file module scopes and reporting in the combined release gate.
3. Resolve the numeric gates in [the v1 plan](plan/README.md) before changing
   arithmetic or casts. Decisions L3 and L4 retain explicit-width integers and
   reject `int`, `uint`, and `number`.
4. Split safety proofing into internal CFG, fact, obligation, proof-discharge,
   and backend-plan stages.
5. Finish generic specialization before broad cross-module generic workflows.
6. Maintain installed-distribution checks for `a7 check`, `a7 build`, `a7 run`,
   `a7 doctor` and `a7 --version`. Wheel and source-distribution workflows pass
   on the current Linux x86-64 target.
7. Keep both recursion scans empty and extend deep pipeline checks for new
   compiler paths. All currently scanned recursive groups, deepcopy calls and
   generated-method cycles are removed. Dynamic external Python callbacks remain
   outside the structural traversal guarantee. See the
   [delivery roadmap](plan/delivery-roadmap.md).

## Known Gaps

- Exact-fit untyped constants are implemented with one evaluator
  (`a7/exact_constants.py`): exact arithmetic, then a fit to the
  destination (ledger L61). Enforced limits: float exponent 4,096 and
  131,072-bit components. Not enforced: the work-credit, cache-size and
  dependency-depth limits in SPEC Appendix C. The match-pattern
  duplicate check still compares float constants as `f64`. Bitwise `~`
  is not folded. Declaration-order-independent global typing follows
  [P-TYP](plan/packets/P-TYP-forward-globals.md).
- Both candidate recursion scanner modes report empty recursive-group,
  deepcopy and generated-method lists. Safety statements; parser statements,
  expressions and types; checker statements,
  expressions and type resolution; backend statements, expressions and types;
  and AST structural comparison/display now use explicit worklists. These
  paths are included in the qualified integration checkpoint. The earlier frozen
  expression snapshot passed 3,082 nonnative tests. Parser review matched 111
  independent cases; backend debug and release each passed all 51 examples.
  Expression GLM reviews passed within their assigned scopes. Safety traversal
  review passed. The combined snapshot passed 3,602 tests with one expected
  failure; secrets and skipped release checks passed after metadata recovery.
  The [follow-up record](audits/2026-10-07/iterative-followup-verification.json)
  identifies each source and its evidence. Passing selected deep inputs does
  not establish the full no-recursion requirement. Arbitrary external Python
  payload callbacks remain outside the AST structural traversal guarantee.

- A labeled loop whose label is never targeted no longer emits a label: the
  fix landed with commit `ed0baff`, and the never-targeted case is pinned in
  both profiles by the `unused-labels` case in
  `test/test_resume_backend_bindings.py`.

- Local constant usage is now tracked by declaration identity. A declaration
  initializer reads the outer binding, and match-expression arms use their own
  scopes, so sibling-scope collisions and nested shadowing resolve to the
  binding their position in the block selects. Both cases are pinned in both
  profiles by `test/test_resume_backend_bindings.py`. The [review
  follow-up](audits/2026-09-20-core-v1/backend-glm-followup.md) preserves the
  original reproducers.

- File-backed imports now have separate semantic scopes, private top-level names
  and distinct nominal type identities. Qualified types, struct literals,
  constant array lengths and generic bodies resolve in their defining files.
  Reports retain file and lexical owners. One combined Zig output preserves
  existing module and declaration order. L28 still rejects local bindings that
  reuse their own file's aliases; fields remain independent. Selected imports,
  `using import` and hardlink identity remain open. L76 keeps import aliases local
  to their declaring file. Parsed forwarding rejects with semantic exit 6 and
  direct-import guidance; ordinary public wrappers and struct fields remain
  valid. Unsupported multi-dot type annotations and literals retain parse exit
  5. The [approved packet](plan/packets/P-MOD-import-forwarding.md) records this
  boundary.
  Stage10's full compiler gate exited 1: 3,689 tests passed, one obsolete `__`
  fixture failed and one expected failure remained. The other ten compiler
  checks and all 51 examples in every profile passed; outer release checks did
  not run. The corrected fixture received independent review. Stage12 passed
  3,305 nonnative tests. Stage13 combines modules, constant diagnostics, global
  aliases, equivalent loop increments, immutable generic aliases, the symbol-kind
  guard and L76 v2. Manifest `c37e0c08` passed 3,337 nonnative tests in 51.26
  seconds. Two targeted native tests passed: corrected local-name collisions in
  debug/fast and direct imports/public wrappers in all three profiles. The
  combined immutable-alias control built and produced its expected output in
  all three profiles. Full manifest `27c4c26e` then passed the complete release
  gate: 3,756 tests with one expected failure, all 11 compiler/package checks,
  51 examples in every profile, site checks and dependency/security checks.
  All 1,599 frozen file hashes and modes remained unchanged. L76 core and
  diagnostic-delta external reviews found no scoped blocker. Rendered browser
  checks could not run because no browser connection was available. These
  results do not qualify full V1.
- Local aliases of same-file generic declarations that are never reassigned,
  passed by reference or captured by another function now
  preserve concrete body obligations. Imported, module-global, parameter, mutable,
  selected and captured origins remain incomplete. General runtime generic
  dispatch is not implemented.
- An entry file must define `main :: fn()`; a file without one exits 6 at the
  Entry Point stage. Imported modules are exempt. `a7 check --lib` checks a
  library file without an entry point; `build` and `run` still require one.
- Integer `+`, `-`, and `*`, including compound forms, keep wrapping by
  default. Release builds lower proven-range results to non-wrapping
  operators; `--no-nonwrap` forces wrapping everywhere. Union discriminant
  access, full ref/del alias behavior and ownership/lifetime guarantees
  remain incomplete.
- Generic `union(tag)` types now specialize positionally like structs:
  `Result(i32, string){ok: 1}` checks and field access resolves.
  Conflicting `$T` bindings at one call site exit 6
  (`GENERIC_PARAM_MISMATCH`). Generic enums stay out of scope (no
  payload types to specialize). Pinned in
  `test/test_generics_fast_union.py`.
- `$N` value params (`usize`, `bool`, small ints) work on generic fns,
  structs, and unions for declarations and named-constant
  instantiation (`Buf(SIZE)` with `SIZE :: 4`). A bare `$N` as a type,
  a value of the wrong kind or range, a type for a value param, or a
  value for a type param exits 6 at annotations and literals.
  Literal value args (`Buf(4)`) do not parse yet, fn calls cannot
  infer `$N` yet, and a value param cannot be forwarded to another
  generic (`inner: Buf($N)` exits 6). Pinned in
  `test/test_generics_value_params.py`.
- Minimal `where` conjunctions (`where T: Numeric`,
  `where T: Numeric, U: Float`) work on generic fns, structs, and
  unions. Richer predicates, unknown names, and `where` on enums
  exit 6. Pinned in `test/test_where_clauses.py`.
- Two functions with the same name exit 6 (`ALREADY_DEFINED`),
  whatever their signatures. Overloading is parked (ledger L59).
  Pinned in `test/test_duplicate_function_names.py`.
- Generic local literal/array and scalar if/match initializers and bound callback arguments
  are checked against concrete instantiations. Callback assignment and branch
  selection preserve their bound signature. Focused semantic and debug/fast
  native controls and the integration gate pass.
  Callback provenance through record fields and array elements, and generic
  declarations stored as runtime function pointers, remain open.
  A later candidate fits ordinary and generic if/match array-literal arms,
  including nested arrays. It passed 206 focused tests and combined debug/fast
  native controls. GLM review found no introduced regression. The repair is
  included in the frozen integration and recovered release checks above.
  A further candidate fits literal arms to a concrete typed array arm. Its
  244 focused tests, 13 independent source cases and debug/fast execution of
  both branches pass. GLM review matched 79 independent compile-only programs
  without an introduced regression. The bounded immutable local-alias repair
  preserves obligations for same-file aliases whose copy chain is never
  reassigned, passed by reference or captured by another function.
  Imported, module-global, parameter, mutable, selected, captured and aggregate
  origins remain incomplete. The earlier local-flow trial stays excluded because
  it loses branch correlations. No general runtime generic representation is
  implemented.
  An unresolved generic element destination such as
  `[2]$T` still fails before instantiation; a separate repair must preserve
  obligations through callable aliases. General call-chain propagation of
  generic inference stays open.
- Multiple return values, destructuring, and variadic runtime
  lowering are not current backend features. Tagged unions match
  through leading-dot arms (see below); other tag workflows stay open.
- Tagged-union payload matching works end to end. `case .none:` tests
  a tag, `case .ok(v):` binds a copy of the payload, and `else:` and
  `_` opt out of exhaustiveness. A bare `case tag:` exits 6, and a
  match with uncovered tags and no `else` reports one exit-6 error
  listing each missing tag. A payload that is or holds a `string`
  (directly, in a struct field, or in a fixed array) cannot bind by
  value and exits 6; match the tag without a binding. A `ref` to a
  tagged union matches the same way. Pinned in
  `test/test_match_payload.py` and `test/test_match_dot_e2e.py`.
- Package-owned `Option(T)` and `Result(T, E)` are available in every file.
  Redeclaring either name fails at semantic exit 6. Members may retain those names.
  `io.println_ok` and `io.read_line` return canonical `Result(usize, io.IoErr)`;
  saved values, wrapper returns and cross-file signatures use the same identity.
  `read_line` requires one mutable `[]u8` and counts a consumed newline.
  Module operations and `io.IoErr` require explicit imports in each file.
  Literal `std/` paths cannot fall back to project files; explicit relative
  paths keep existing containment rules. `get`/`pop`, collection modules and
  `or{}`/`use` remain deferred. Pinned in `test/test_stdlib_signature_typing.py`
  and `test/test_stdlib_result.py`.
- Zig emission changed in two pinned ways with no runtime behavior
  change: single parens in conditions and left-assoc chains, and native
  `switch` for a match whose scrutinee is an integer, char, bool or
  enum and whose arms are constants. Every other match (floats,
  strings, runtime arm values, `fall` arms) keeps the if-chain.
  Strings compare by content in `==`, `!=` and `match`. `ref`
  parameters lower to `?*T` (ledger L60). `ret`, `break`, `continue`
  or `fall` leaving a `defer`, directly or from inside a
  `defer { ... }` block, exits 6. Inline generic functions
  (`fn(x: $T) $T`) and file-scope `@type_set` aliases compile and run.
  New examples
  `049_expense_ledger` and `050_tip_split` run end to end. Pinned in
  `test/test_codegen_emit.py` and `test/test_del_defer_codegen.py`.
- The recursion ban follows function values by type, not by flow: an
  indirect call may reach any function of the same type that is used as
  a value. A function that is itself used as a value and calls through a
  value of its own type exits 6 even when it never recurses. Pinned in
  `test/test_recursion_ban_function_values.py`.
- A function-pointer local without an initializer has no zero value;
  calling it before assignment passes `a7` and fails the Zig build.
- `main` cannot return an exit status: a program exits 0, or 134 on a
  panic.
- Collections and fuller string/memory helpers are planned
  stdlib work.

The focused native probes record these repaired behaviors and remaining limits:

- Escaped IO braces compile and print literal braces. Signed-integer
  `math.abs` preserves the declared signed result type; its minimum negative
  input wraps to that same negative value.
- Scalar-filled fixed-array initializers and direct `string.len` access are rejected.

- Duplicate imports are rejected (fixed). The same path twice, alternate
  spellings (`helper` vs `./helper`), symlinked paths, and a reused alias
  each exit 6. Pinned by `test_duplicate_import_same_path_exits_6`,
  `test_duplicate_import_alternate_spelling_exits_6`,
  `test_duplicate_import_second_alias_exits_6`, and
  `test_duplicate_import_through_symlink_exits_6` in
  `test/test_import_error_stages.py`. Different files importing one module
  stays legal (`test_different_files_importing_same_module_stays_legal`).
- Unclosed block comments are tokenizer errors (fixed). A plain unclosed
  `/*` and a nested-unclosed `/*` each exit 4 at the comment start. Pinned
  by `test_unclosed_block_comment_exits_4` and
  `test_unclosed_nested_block_comment_exits_4` in
  `test/test_import_error_stages.py`.
- Imported-file errors keep their own stage and file (fixed). A tokenize
  failure in a dependency exits 4 with category `tokenize`; a parse
  failure exits 5 with category `parse`; each names the imported file.
  Missing, unreadable, and permission-denied imports exit 3 with category
  `io`. Pinned by `test_imported_tokenize_failure_exits_4`,
  `test_imported_parse_failure_exits_5`, `test_missing_import_exits_3`,
  `test_unreadable_import_exits_3`, and
  `test_permission_denied_import_exits_3` in
  `test/test_import_error_stages.py`.
- Reversed constant match ranges are rejected (fixed). `case 10..1` and the
  const-alias, char, and match-expression forms each exit 6 with
  `invalid_pattern`; swap the endpoints to fix. Bounds known only at run
  time keep the prior rule: an empty range matches nothing through the
  if-chain. Pinned by `TestReversedConstantRanges` and
  `TestDynamicEmptyRange` in `test/test_match_ranges_break.py`. The
  constant form failed the Zig build, so the fix needed no packet.
- An unlabeled `break` or `continue` in a match case inside a loop
  targets the enclosing loop, in both the `switch` and if-chain
  lowerings (ledger L58). Pinned by `TestBreakInMatchCase` in
  `test/test_match_ranges_break.py`, which runs the binaries.
- SPEC text now matches the implementation; behavior unchanged. Updated
  sections: 2.1 source encoding, 2.2 comments, 2.3 identifiers, 2.5
  operators and folds and release nonwrap, 2.6 literal rules,
  float-to-int literal-only proof, 10.2 through 10.2.2 module
  identity and cycles and entry, 10.4 visibility intent, 11.2 stdlib
  generations, 12.1 token list, the limits table, and Appendix D
  escapes (`docs/SPEC.md`; phases 2a/2b/2c).
- Call, index, slice, field-access, unary, assignment and parenthesised
  nodes carry spans from their first to their last token.
- An undefined bare identifier in a `case` pattern silently becomes a capture
  binding instead of an undefined-name error (probed: `case Blu:` matches
  everything; capture rule owned by packet P5/NR-03).
- Some failure payloads carry no span: a failed JSON `stages.parse` reports
  `ok: false` with no message or span, and several parse diagnostics lack
  source context (PAR-14).

See [documentation verification](../site/docs/content-verification.md) for source,
commands, diagnostics, and supported alternatives. Historical audit reports retain
the earlier failures. Current repairs have regressions in `test/test_audit_type_boundaries.py` and
`test/test_audit_backend_repairs.py`.

## Planned work

Automatic memory is required for V1. Runtime help is allowed, but no production
mechanism is selected. The Python compiler remains the bootstrap implementation;
Zig handles generated code and runtime/native integration. L73 also requires
structured concurrency, CPU AI, actual GPU execution and self-hosting parity.
These requirements remain unqualified. A package registry stays outside scope.

Small standalone arena/RC foundation fixtures passed 134 checks using Debug
LLVM/LLD and a shared C-O0 allocation shim. The instrumented revision records
explicit-root aliasing, returned values, metadata and allocation-failure cleanup.
Independent review found weaknesses in its trace checker. A separate strengthened
checker accepts all 24 archived traces and rejects 710 count/layout mutations.
The frozen sources and original execution evidence remain unchanged.
These results do not qualify the seven required workload shapes, automatic A7
lowering or L38. Runtime category budgets are not measured stack bounds.
The W4 returned-record prototypes and independent C baseline passed 138 native
checks, including 24 workload cases. Each successful case checks all 334 returned
records after producer cleanup. Independent and GLM reviews found no source
blocker in this bounded fixture. Timing, complete peak memory and L38 remain
unqualified. The first W1 native attempt stopped at a Zig type-instantiation error before
any workload executed. After an explicit alignment type repair, the frozen retry
passed 112 checks, including 42 growth cases and controlled corruption tests.
The repaired program stops before publishing corrupted storage and frees each
allocation once. Timing, complete runtime storage and L38 remain unqualified.
The W2 shared-row and explicit-snapshot prototypes passed 75 Debug native checks.
Both live paths observe the update; the historical snapshot preserves its values.
Allocation and copy failures clean up verified owners. Named corrupt-count/queue
cases exit 6 with recorded residual storage rather than claiming safe reclamation.
Normal requested backing peaks are 48 bytes for C/arena and 144 for RC. These
exclude unmeasured runtime storage and do not qualify timing or L38. See the
[W2 record](audits/2026-10-07/memory-w2-verification.json).
W3 passes 75 Debug native checks of actual node cycles, deletion,
allocation-failure cleanup, intact-cycle abort and output failures.
Independent trace review confirms those bounded observations. Requested
backing peaks are 96 bytes for C/arena and 192 for RC; stack and other
runtime storage remain unmeasured. The RC prototype clears this
container's owned edges before releasing roots. General cycle collection,
timing and L38 remain unqualified. See the
[W3 record](audits/2026-10-07/memory-w3-verification.json).
W5's independent cache models agree on both workload sizes and failure
retry behavior. Native implementations and their memory/performance
qualification remain pending.
Canonical Option/Result and typed existing stdlib hooks are integrated. The frozen
compiler/package gate passed 3,826 tests with one expected failure and all 11
checks. The release wrapper then failed a stale generated docs manifest. After
regeneration, site and remaining dependency/static checks passed separately;
all compiler, test and package source bytes were unchanged. The
[qualification record](audits/2026-10-07/stdlib-b2-verification.json) preserves
both results. Readonly V3 is now integrated after its full release gate.
It uses implicit-borrow annotations and distinct Boolean/integer environment
keys. These fix the isolated V2 candidate's valid-call rejection and unsafe-call
acceptance. Independent review checks 16 sources across three snapshots; GLM
review matches 37 matrix cases and preserves 126 prior results. Six valid native
controls pass across all three profiles. Caller-local selectors and summaries
outside the existing work certificate can still leave unsafe reads unresolved.
The compiler does not treat those unresolved predicates as safety proofs.
The [delivery roadmap](plan/delivery-roadmap.md) owns their work order and exits.

## Audit evidence

The [audit index](audits/README.md) separates dated findings from current checks.
A passing example suite does not establish that all accepted programs are safe
or that the compiler implements the full specification. The
[execution plan](plan/execution.md) tracks correctness repair and approval packets.
