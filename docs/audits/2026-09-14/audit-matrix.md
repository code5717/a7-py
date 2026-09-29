# Detailed audit scope for agreement

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it.

This is the proposed scope for qualifying A7, not a claim that every check below
has run. The companion review reports distinguish observed failures from open
questions. Implementation remains pending agreement on the completion roadmap.
Documentation cleanup is separately authorized.

## What completion should mean

Define a supported v1 language before counting missing features. Each supported
construct needs specified semantics, compiler diagnostics, backend behavior,
examples, and public documentation. Unsupported constructs need explicit
diagnostics. A parser accepting syntax does not establish language support.

Track each requirement through these states:

1. Design decision recorded, including rejected alternatives and limits.
2. Implementation inspected against that decision.
3. Positive and negative compiler tests pass through the public pipeline.
4. Accepted programs produce the expected native behavior in debug and release.
5. Documentation and installation workflows agree with the implementation.
6. Release evidence records the exact source revision and toolchain.

Use four outcomes for individual audit checks: verified, failed, untested, or
blocked. Keep deliberately deferred features in a separate register.

## Language contract and syntax

| Audit question | Concrete probes | Acceptance evidence |
| --- | --- | --- |
| Which SPEC sections are implemented, partially implemented, or proposals? | Map each grammar production and semantic rule to parser, semantic, safety, backend, and tests. Include multiple returns, destructuring, variadics, unions, imports, and generics. | A feature matrix with no unqualified planned feature presented as supported. |
| Do tokens preserve exact source locations? | Mixed line endings, tabs, Unicode, nested comments, escaped strings, unterminated literals, malformed numeric prefixes, EOF at every token boundary. | Stable token spans and source diagnostics, with no traceback for invalid source. |
| Does precedence match the specification? | Mixed unary/binary operators, casts, calls, indexing, chained comparisons and assignments. Compare ASTs and observable results. | Explicit precedence examples and tests independent of codegen implementation. |
| Does nesting fail predictably? | Long flat sums, deeply nested blocks/types/calls, long comments, large declarations. Test advertised implementation limits at the boundary and one step beyond. | Supported cases succeed; resource limits produce A7 diagnostics rather than Python recursion errors. |
| Are declarations and scope consistent? | Nested shadowing, duplicate names, unused variables, enum members, forward references, backend-reserved names such as `error`, and loop capture names. | Every valid A7 name lowers correctly. Invalid declarations fail before Zig. |

## Error messages, error checking, and recovery

| Audit question | Concrete probes | Acceptance evidence |
| --- | --- | --- |
| Does each failure belong to the right stage? | Malformed escape, invalid token, incomplete grammar, undefined name, type mismatch, unsupported backend feature, missing import, output I/O failure. Repeat errors in imported modules. | Stable documented exit category, no source error disguised as an internal fault. |
| Does the diagnostic identify the actual source? | Multiline and Unicode input, imported errors, nested includes, generated/renamed nodes, missing EOF token. | Correct original filename, line, column, underline extent and source excerpt. |
| Can the user fix the error from its message? | Missing delimiter, wrong type, ambiguous generic, unsupported reference syntax, failed safety proof, unavailable stdlib member. | Explain what failed and the relevant expected form. Advice must not recommend forbidden or unimplemented syntax. |
| Do later checks create misleading cascades? | One unresolved type followed by member access and calls; multiple independent errors in one file. | Primary errors remain clear; dependent noise is suppressed without hiding independent errors. |
| Are errors consistently machine-readable? | All modes and both formats, unusual filenames, non-ASCII text, backend exception, interrupted or denied writes. | Valid JSON with documented fields and accurate artifacts; stderr/stdout behavior is explicit. |
| Are internal failures debuggable without corrupting artifacts? | Controlled internal exception at a named test boundary, then a normal compile using a fresh and reused compiler instance. | Internal error classification is distinct; old source survives, incomplete artifacts are not advertised, state does not leak. Mock limits are named. |
| Are diagnostic identifiers stable enough for tooling? | Compare error type/code, message, advice and severity across equivalent syntax and imports. | A documented stability policy. Tests assert meaning and location rather than incidental pretty-print layout. |
| Does recovery preserve the original problem? | Missing closing brace, malformed generic argument, missing separator, unexpected token in a nested block. | No infinite parser loop or swallowed trailing program; first error points to the relevant edit. Record fail-fast behavior if intentional. |

## Transformations, optimizations, and pass invariants

For every pass, record its input assumptions, changed nodes, preserved metadata,
output guarantee, and the next consumer. Trace complete programs through these
boundaries instead of validating each pass only against its own output shape.

| Pass or boundary | Concrete probes | Acceptance evidence |
| --- | --- | --- |
| Import combination and name qualification | Multiple aliases, private duplicate names, nested imports and imported errors. | One combined program preserves symbol identity, visibility, call targets and source origins. |
| Generic inference and specialization | Same function at two types, nested generic calls, constraints and imported generics. | Specializations preserve types, effects, source locations and call-graph checks. |
| Struct initializer normalization | Named fields in a different order, omitted fields, positional syntax and effectful field expressions. | Layout normalization does not change specified evaluation order or silently fill required values. |
| Field sugar and reference lowering | Same field names in distinct types, nil checks, writes through ref fields and alias calls. | Exactly the intended storage is read/written, with valid approvals. |
| Stdlib call resolution | Shadow a module alias or function name; import two names; call unsupported members. | Only the resolved stdlib symbol receives a backend mapping. |
| Mutation and usage analysis | Ref calls, field/element writes, loop captures, shadowing and nested functions. | Mutable storage is not emitted as const; genuine unused Zig bindings do not break otherwise valid A7. |
| Shadow renaming | Locals, parameters, loops, nested functions and names reserved by Zig. | Declaration and every use share one identity without capturing another binding. |
| Nested function hoisting | Free variables, same nested names, function pointers and use before declaration. | Explicit capture policy; moved functions retain behavior or receive an A7 diagnostic if unsupported. |
| Constant folding | Integers above 2^53, negative division/remainder, typed overflow boundaries, floats and mixed constants. | Exact integer semantics and correct type preservation. Folded and non-folded forms agree. |
| Short-circuit and dead paths | Right operand mutates state or would fail; false/true guards; return before an expression. | Only semantically evaluated paths execute. Optimization never creates or removes observable side effects incorrectly. |
| Metadata after replacement | Folded node inside a cast/index, renamed function in an error, combined imported declarations. | Types, spans, symbol identities and operation-specific proof approvals remain valid or are recomputed. |
| Pass repetition and compiler reuse | Process the same source twice using fresh instances; reuse a compiler and compare valid outcomes after a failure. | Determinism where specified; no stale struct definitions, symbols, deletion state or approvals cross compilation units. |
| Backend serialization | Large AST, strings with escapes, keywords and generated symbols. | Emitted Zig builds, diagnostics remain bounded and original meaning survives printing. |

## Types, numbers, and value semantics

| Audit question | Concrete probes | Acceptance evidence |
| --- | --- | --- |
| Are implicit conversions deliberate? | Signed/unsigned comparisons, integer literals at each type boundary, mixed-width arithmetic, generic literals, constants versus mutable variables. | A conversion table and matching positive/negative tests. No accidental Zig coercion defines A7 behavior. |
| What happens on integer overflow? | Minimum/maximum plus one, negating the signed minimum, multiplication overflow, signed minimum divided by -1. Repeat for constants and runtime inputs. | An explicit reject, trap, checked-result, or wrapping policy that agrees across build profiles. |
| Are division and modulo semantics complete? | Zero after `-=`, branch assignment, loops, `ref` calls and aliases; negative operands; signed division edge cases. | Proofs use current values and correct arithmetic semantics. Unproved operations are rejected according to the contract. |
| Are shifts and bitwise operations defined? | Shift by zero, width minus one, width, oversized value, negative count, signed operands. | Defined signedness and count rules with diagnostics before backend rejection. |
| What is the floating-point policy? | NaN, infinity, signed zero, underflow, overflow, comparisons and float-to-int boundaries. | Record whether finite-only research is adopted or deferred. Implemented behavior matches that decision. |
| Are casts and type aliases consistent? | Chained casts, aliases of aliases, narrowing after guards, casts after mutation, arrays of aliases, imported aliases. | Each conversion receives the documented check and cannot reuse stale range evidence. |
| Are evaluation order and copying defined? | Calls with observable side effects in arguments and binary expressions; struct/array assignment followed by mutation. | Explicit ordering and value/reference semantics verified by native outputs. |

Note (2026-09-16): the overflow question is decided for integer `+`, `-` and `*`
by ledger L5 (wrapping); other operators stay open under gate G3. The
floating-point question is decided by L16 (IEEE values; details in gate G1), so
finite-only research is not adopted.

## Safety proof correctness

This is the first remediation priority. A successful proof built from stale
facts is a compiler correctness failure even when Zig later traps.

| Audit question | Concrete probes | Acceptance evidence |
| --- | --- | --- |
| Does assignment update the actual resulting value? | `d = 1; d -= 1`, multiplication by zero, increments, field and indexed assignments. | Transfer rules model the operator or conservatively discard the affected fact. |
| Do facts survive scope only when justified? | Inner blocks mutate outer variables; shadowed locals share a spelling; both branches assign different ranges. | Scope exit preserves outer writes, removes local facts, and merges branch states conservatively. |
| Are facts valid on every loop iteration? | Array index grows past bounds; loop body changes a divisor; zero, one and many iterations; break/continue paths. | A loop invariant or conservative invalidation covers all iterations, not only entry values. |
| Do calls invalidate affected state? | Direct `ref` mutation, nested `ref` calls, two aliases to one value, callbacks that mutate referenced state. | Effect summaries or conservative invalidation prevent stale nil, range, length and liveness proofs. |
| Are proof facts attached to symbol identity? | Same name in nested scopes, imported names, hoisted functions and generic specializations. | Facts cannot leak between distinct variables or instantiated functions. |
| Do guards cover exactly the guarded path? | Reversed comparisons, `&&` and `||`, early returns, unreachable branches, negation, else paths. | A risky operation is approved only on paths where its required fact holds. |
| Can backend transformations invalidate approval? | Constant folding, substitution, desugaring, hoisting and specialization after proof planning. | Each emitted risky operation retains valid operand-specific approval or is rechecked. |
| Does the safety contract overstate its coverage? | Trace every promised check to a rejecting counterexample and a valid accepted example. | Public claims name current limits, including overflow, shifts, aliases and lifetimes. |

## References, memory, and aggregate types

| Audit question | Concrete probes | Acceptance evidence |
| --- | --- | --- |
| Is nullable reference access correctly guarded? | Read/write fields before and after nil checks, reassignment after guards, nested reference fields. | Every relevant access uses current non-nil evidence. |
| What exactly does `del` invalidate? | Direct use after delete, aliases, double delete, delete in one branch, deferred delete, nested cleanup. | Supported guarantees are enforced; remaining alias limitations are explicit. |
| Can references escape their storage? | Return a reference to a local, store it in an outer object, pass through a callback or module boundary. | A defined lifetime policy and proof tests, or an explicit restriction until implemented. |
| Is initialization complete? | Uninitialized locals, partially initialized structs, early return, conditional assignment, reads through references. | Read-before-initialization behavior is specified and validated. |
| Are arrays, slices and strings distinguished? | Empty arrays/slices, zero/end indexes, reversed bounds, index equal to length, non-`usize` variables, length after reassignment. | Bounds and index-type rules match all accepted container kinds. |
| What is string length measuring? | ASCII, multibyte UTF-8, embedded zero and slicing across byte boundaries. | Byte versus code-point semantics are explicit. No unsupported text guarantees are implied. |
| Are union reads valid? | Write one field and read another; tagged workflows; copies and branch-dependent variants. | Choose and enforce the current union contract before advertising discriminant safety. |
| Is allocation failure part of the language? | Scalar/struct allocation, cleanup after early exit, unsupported heap fixed arrays. | Allocation and failure behavior are documented. `new [N]T` remains rejected until designed. |

Note (2026-09-16): the target memory model for `del`, aliasing, escapes and
lifetimes is set by ledger L15, L17–L19 and L21; see the
[memory plan](../../plan/memory.md). The probes remain valid checks of current
behavior.

## Functions, recursion, generics, and modules

| Audit question | Concrete probes | Acceptance evidence |
| --- | --- | --- |
| Does the recursion ban cover the actual call graph? | Direct/mutual calls, local function aliases, callbacks, imported cycles and specialized generic calls. | Every prohibited cycle receives an A7 diagnostic with a useful call chain. Tests do not depend on recursive A7 algorithms. |
| Are function types compatible by the intended rules? | Raw and aliased types, return mismatch, `ref` modes, higher-order functions, reassigned callbacks. | Consistent checks at declarations, assignments, arguments and returns. |
| Is generic specialization complete for its advertised subset? | Two concrete types in one program, generic call chains, constraints, type sets, generic structs and function values. | Correct specialization identity and propagation, or early diagnostics for unsupported forms. |
| Are imports canonical and isolated? | Relative imports at different depths, two aliases of one file, same names from different files, visibility and exported types. | One consistent module identity with correct namespaces and visibility. |
| What is the module-cycle policy? | A imports B imports A; cycles with no cross-calls; cycles involving declarations. | Decide whether cycles are prohibited. Loader, graph validation, diagnostics and docs must agree. |
| Can modules change safety or generic behavior? | A valid single-file program split into modules; imported generic/ref functions and aliases. | Equivalent behavior within the supported module subset, with explicit limits elsewhere. |
| Does module path validation match the trust boundary? | Absolute paths, `..`, symlinks and configured search roots using harmless fixtures. | Enforce the documented filesystem boundary with canonical paths. |

## Backend and standard library

| Audit question | Concrete probes | Acceptance evidence |
| --- | --- | --- |
| Can every accepted construct be built by pinned Zig? | Reserved identifiers, unused loop captures, shadowing, empty functions, all supported literals and returns. | Full public compiler followed by Zig build, not code-string assertions alone. |
| Do debug and release have equivalent language results? | Boundary arithmetic, bounds, memory operations and side-effect ordering. | Defined differences only; exact outputs for valid programs in both profiles. |
| Are platform assumptions explicit? | `usize`/`isize`, integer width, path separators, executable naming and newline behavior. | Qualify each supported platform; label untested targets. |
| Do `std/io` and `std/math` contracts match generated helpers? | Argument arity/types, formatted values, stdout versus stderr, empty output, math boundary inputs. | Registry, semantic checking, helper generation and docs agree. |
| Do unsupported library needs fail clearly? | Missing module/member, unsupported collection/string helpers, invalid format arguments. | A7 diagnostics explain the supported alternative without pretending planned APIs exist. |

## CLI, packaging, and release operation

| Audit question | Concrete probes | Acceptance evidence |
| --- | --- | --- |
| Can compilation damage inputs or misreport outputs? | Output equals source, symlink/hardlink collisions, imported-source destinations, output/doc collision, failed compile with an old artifact. | Reject collisions before writes and report only artifacts created by the current invocation. |
| Is every mode usable by automation? | Human/JSON output across tokenize/parse/semantic/codegen/I/O failures; stdout/stderr separation; exit codes. | Parseable JSON, accurate stages and stable documented exit codes. |
| Does a new user reach a running program? | Clean checkout, `uv sync`, compile, Zig build, execute; then repeat from a clean installed wheel. | A copied documented sequence reaches expected stdout without an undocumented directory change or dependency. |
| Are missing dependencies diagnosable? | Missing uv, wrong Python, absent/wrong Zig, unavailable Bun. | Actionable instructions distinguish setup failures from A7 source errors. Decide scope of planned `doctor` and workflow commands. |
| Are release claims backed by artifacts? | Full local gate, clean-wheel install, checksums, archive membership, workflow/source parity. | Evidence for a fixed revision and toolchain. Local success does not imply remote CI or published release success. |
| Do separate dependency checks run? | Pinned pip-audit, Bandit and Bun audit commands in RELEASE.md. | Verify the audited inventory includes the intended locked project dependencies. Record findings or provider/network blockers separately from unit tests. GLM owns cybersecurity qualification. |

## Website and developer experience

| Journey or concern | Detailed checks | Acceptance evidence |
| --- | --- | --- |
| First visit | Can a reader identify A7, its maturity, A7 versus Zig version, supported workflow and limitations? Is the compiler map understandable? | Current desktop/mobile screenshots and correct package/toolchain facts. Preserve the Field Manual design. |
| Install and run | Copy the complete setup block; follow dependency links; compile/build/run hello-world; identify expected output and recovery steps. | Successful clean-environment walkthrough with every command run in the documented directory. |
| Find an answer | Agree heading-only or full-content search, then search `usize`, `println`, `--format`, `recursion`, unknown terms and multiword queries. Test slow/missing index and clear/reopen behavior. | Results match the agreed search scope; useful empty/error states and reachable mobile search. |
| Read a reference | Headings, numbered procedures, tables, fenced code, deep links, page navigation, TOC and long lines. | Correct semantic HTML and valid anchors. Procedures remain ordered lists. |
| Keyboard and assistive technology | Skip link, focus visibility/order, modal containment, Escape return, search selection announcements, tab-panel associations. | Browser and screen-reader checks. Source inspection alone is not accessibility qualification. |
| Responsive presentation | Narrow phone, wide phone, tablet, desktop, 200% zoom, long code/table overflow and touch target reachability. | Saved current captures with measured clipping and overflow checks. |
| Motion and contrast | Reduced-motion behavior, scroll reveal fallback, text/background color pairs and focus indicators. | Computed contrast checks plus rendered verification. No content lost when scripting or observers fail. |
| Truthful examples | Homepage terminal output, release status, stage labels, version badges and feature descriptions. | Real representative outputs clearly labeled as examples; no static success claim presented as current status. |
| Agent access | Raw Markdown, HTML/raw cross-links, llms index, full corpus equality and authoritative source links. | Direct fetches work and content matches generated pages. Full corpus scope is explicit. |
| HTTP and deployment | Project base path, nonexistent routes, malformed URLs, safe preview path handling, MIME types and cache/deploy behavior. | Correct responses and no files served outside the intended preview root. Remote hosting verified separately. |

## Documentation preservation and organization

- Inventory current guidance, accepted design decisions, proposals, research,
  historical reports, generated summaries and PDFs before reorganizing.
- Keep README and RELEASE authority visible. Separate intended safety guarantees
  from currently enforced behavior without deleting either.
- Preserve all unique rationale, rejected alternatives, examples, qualifications,
  dates and source citations. Merging requires a source-to-destination map.
- Prefer navigation improvements to file moves. Preserve old paths or provide
  redirects when a move is eventually approved.
- Compare original and final bytes for untouched artifacts. Review every deleted
  text line in changed files; formatting changes must not alter code examples.
- Validate local links, heading fragments and generated corpus parity. Report
  historical broken links without silently removing their provenance.
- Keep incompatible research snapshots visible and label their status. Do not
  resolve a language-design conflict by deleting the older argument.

## Test quality and audit method

Start with reported guarantees and create the smallest program that would
invalidate each one. Then compare the direct compiler path with the test helper
path. A helper that suppresses semantic errors cannot establish acceptance.

Use metamorphic checks where a separate expected output is hard to maintain:
rename variables, add harmless blocks, replace a literal with an equivalent
expression, split a supported program into modules, and compile in both profiles.
These changes should preserve defined behavior. Use bounded generators and
shrinking to turn discovered failures into readable regressions in a later
implementation phase.

Measure coverage by semantic rule and control-flow case, not only line count.
Include zero/one/many iterations, both branch outcomes, alias/no-alias calls,
each exit path and each public compilation mode. Native fixture success and a
high test count do not prove the absence of stale safety facts.

## Decisions to settle before implementation

1. Is the next milestone a reliable current subset or a larger v1 language?
2. Which arithmetic, union and lifetime guarantees must v1 enforce?
3. Will unproved safe programs be rejected conservatively until stronger proofs
   exist, consistent with the current safety contract?
4. What exact module and generic subset belongs in v1?
5. Which new CLI workflows belong in the same release, and which stay later?
6. Which operating systems and architectures will receive native qualification?
7. Which current SPEC implementation limits are commitments versus proposals?

Keep new numeric types, tensor/AI/GPU features, package registry, concurrency and
new ownership models outside the immediate correctness milestone unless chosen
explicitly. Their absence should not hide or excuse defects in current claims.

Note (2026-09-16): questions 1 and 2 and this boundary are superseded. Ledger L1
and L7 put the broader language, concurrency and CPU AI in v1; L3–L5 and L16 set
the numeric direction; L15, L17–L19 set the memory direction. Package-registry
work stays out of scope. Questions 3–7 map to gates in the
[v1 plan](../../plan/README.md).
