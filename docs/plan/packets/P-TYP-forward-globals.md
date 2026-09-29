# P-TYP: global resolution and untyped numeric constants

Status: implementation authorized and in progress, 2026-09-20. The user selected
"Develop exact-fit untyped constants, like Odin" and confirmed "continue" after
rejecting a repeated approval request. See the superseding L47 authorization in
[decisions](../decisions.md).

Resolve global dependencies before checking function bodies. Preserve an untyped
numeric constant's value until an operation requires a concrete numeric type.
An integer destination accepts the value only if it is integral and in range.

## Baseline behavior and approved compatibility changes

This current A7 program builds and prints `2`:

```a7
io :: import "std/io"
show :: fn() {
    n: i32 = RATE
    io.println("{}", n)
}
RATE :: 2.0
main :: fn() { show() }
```

Moving `RATE` above `show` currently rejects the assignment because the checker
then knows its inferred type is `f64`. The forward case passes through an
unresolved type. Proposed behavior accepts both orders and prints `2`.
Replacing `2.0` with `2.5` rejects both orders because an integer cannot retain
the fractional part. Values outside `i32` also reject in both orders.

Forward string constants currently produce byte-list formatting where the same
constant declared earlier prints its text. The proposal makes both orders print
the text. Native baseline evidence and the earlier limited corpus experiment
remain in [the historical proposal](P-TYP-forward-globals-strict-history.md).
That experiment tested strict global ordering only. It does not establish the
compatibility of untyped constants or their arithmetic.

This change adds accepted programs, can reject programs that escaped checking
through unresolved types, and can change constant-expression results and when
rounding occurs. The measurements below list the changed classes approved under L47. No
zero-impact claim is made.

## Proposed constant rules

### Which values remain untyped

Numeric literals and numeric `::` bindings whose values are formed entirely
from supported untyped constant expressions remain untyped. An expression with
a concrete typed operand follows the typed-operation rules below. Local constants follow the
same fitting rules as global constants. Local visibility rules stay unchanged.
A `::` binding initialized by an ordinary function call does not become an
invitation to execute that function during compilation. Its type follows the
function's declared result under existing rules.

"Untyped" is a compiler property, not a new public `number` type. Runtime
variables, fields, parameters and return values retain concrete widths.
Named aliases of an untyped constant preserve its value and numeric category.
The destination of one use must not specialize the shared declaration for
other uses.

```a7
COUNT :: 200
small: u8 = COUNT      // Accept: 200 fits
wide: i64 = COUNT     // Accept independently
negative: i8 = COUNT  // Reject: exceeds 127
```

### Integer destinations

Use the exact mathematical value, not a previously rounded Python or backend
float. Accept only an integral value in the destination's signed or unsigned
range. Never truncate, wrap or saturate during implicit constant fitting.

```a7
WHOLE :: 2.0
FRACTION :: 2.5
TOO_LARGE :: 256
NEGATIVE :: -1
x: i32 = WHOLE        // Accept: 2
y: i32 = FRACTION     // Reject: fractional value
z: u8 = TOO_LARGE     // Reject: exceeds 255
u: usize = NEGATIVE   // Reject: negative value
```

Each rejection above is a separate test program. A compiler must not accept
`9007199254740993.0` as the neighboring integer because an intermediate host
float lost its last digit. Destination bounds use the compilation target's
width, including `usize` and `isize`.

### Floating-point destinations

Propose round-to-nearest, ties-to-even directly at the destination width.
Do not round through host `f64` before `f32`, which can double-round. Ordinary
`0.1` therefore remains usable as `f32` or `f64`. Preserve negative zero when
materializing a signed zero literal or a typed IEEE value. Reject implicit
fitting when a finite exact constant would overflow to infinity. Permit normal
IEEE rounding and underflow, with boundary cases tested explicitly.

Exact integer fitting does not imply exact binary representation of every
floating-point constant. Existing typed runtime NaN and infinity remain covered
by L16. No new nonfinite literal spelling is proposed. Untyped division by zero is
explicitly proposed to reject in the operator table. This can remove current
overflowing-literal routes to infinity. Existing typed math-call constants
remain available, as verified below. Rejecting overflowing literals is still a
compatibility change approved under L47.

### Explicit nonfinite constants

Keep existing typed math calls as a way to construct nonfinite constants:

```a7
io :: import "std/io"
math :: import "std/math"
INF :: math.exp(1000.0)
NAN :: math.sqrt(-1.0)
main :: fn() {
    io.println("{}", INF)
    io.println("{} {}", NAN == NAN, NAN != NAN)
}
```

Separate baseline programs build and run in Debug and ReleaseFast, producing
`inf` and `false true`. See the
[nonfinite baseline](../research/untyped-nonfinite-baseline-2026-09-20.md).
Calls retain their declared concrete type. The compiler need not evaluate
user functions to infer the result type, and this packet introduces no new
`inf` or `nan` syntax.

The same baseline confirms that `1e400` fitted to `f64` currently builds as infinity.
Proposed implicit finite fitting rejects that use; use the typed math-call route when infinity
is intended. The baseline also confirms that literal and typed zero-division
cases already reject with `Divisor not proven non-zero`. This packet does not
approve making those divisions executable. NaN and infinity as ordinary values
do not imply that every operation producing them is already supported.

An exact comparison such as `1e400 == 1e400` needs no float destination and
therefore evaluates to true without overflow. The rejection rule applies at
materialization, not merely because a literal exceeds `f64`. Resource limits
still apply to evaluation before any comparison folds away its operands.

### Materialization and typed values

A mutable inferred variable takes a concrete default type. Propose retaining
`i32` for the integer category and `f64` for the floating category. An out-of-range
integer default produces an error asking for an explicit destination type;
it does not silently choose a larger width. A float-spelled integral constant
keeps the floating category until a destination requests an integer.

```a7
RATE :: 2.0
exact: i32 = RATE     // Accept: untyped value fits
runtime := RATE      // Materialize as f64
n: i32 = runtime     // Reject: runtime f64 needs explicit conversion
```

An explicitly concrete numeric value stays typed, even when the compiler knows
its value. Do not add Zig's broader typed compile-time float-to-integer
conversion. A function returning `f64` also remains typed. This packet introduces
no typed-constant declaration syntax. Existing declaration spelling must be
verified against the parser before documentation offers a typed `::` example.

The proposed formatting default changes another working program:

```a7
io :: import "std/io"
main :: fn() { io.println("{}", 9007199254740993 / 1) }
```

Current A7 prints `9007199254740993` in both native profiles. The candidate
rejects it because a formatting argument has no numeric destination and the
exact quotient exceeds the proposed `i32` default. An explicit destination
preserves the output:

```a7
io :: import "std/io"
main :: fn() {
    value: i64 = 9007199254740993 / 1
    io.println("{}", value)
}
```

Both versions of the compiler accept the explicit form in both profiles.
See the [baseline](../research/untyped-formatting-baseline-2026-09-20.json)
and [candidate evidence](../research/untyped-candidate-followup-2026-09-20/formatting-results.json).
L47 approves this rejection alongside literal overflow and changed arithmetic.
The candidate's two adjusted legacy tests reflect this compatibility change;
they are not evidence that the original sources still work.

At a typed numeric operation, fit an untyped operand to the required concrete
type, then apply the approved rules for that type. Known typed values must not
be reclassified as untyped merely because constant folding is possible.

### Constant arithmetic

Propose exact untyped `+`, `-`, unary negation and `*`. Preserve exact decimal
literal values and do not round intermediate untyped results. No machine width
exists at this stage, so these operations do not wrap. Fixed-width typed integer
operations retain L5's wrapping behavior.

```a7
SUM :: 255 + 1
wide: u16 = SUM       // Accept: 256
small: u8 = SUM       // Reject: 256 does not fit
```

This can differ from today's early `i32` inference and early float rounding.
For example, exact `(0.1 + 0.2) == 0.3` would be true for wholly untyped operands.
The proposal must expose this consequence rather than silently extend it from
the simple `2.0` fitting example. A second measured change is
`x: f64 = 1e308 * 10.0 / 100.0`: current native builds print `inf` in both
profiles, while exact untyped evaluation would fit the finite result `1e307`.
[The baseline evidence](../research/untyped-intermediate-baseline-2026-09-20.json)
records this program. Typed operands must continue to use typed IEEE arithmetic;
only wholly untyped arithmetic gets the exact rule.

The following operator table is proposed for wholly untyped operands. A
GLM-reviewed compiler resource policy is a blocking prerequisite to implementing
exact arithmetic, shifts or rational values. Reject resource-limit violations
with bounded diagnostics; never substitute approximate values. An
integer-category expression stays integer-category unless a floating-category
operand participates. Integral floating values retain the floating category.

| Operation | Proposed rule | Example result |
| --- | --- | --- |
| `+`, `-`, `*` | Exact arithmetic; floating category if either operand has it | `255 + 1` is integer 256 |
| `/` with two integer-category operands | Quotient truncated toward zero | `5 / 2` is 2; `-5 / 2` is -2 |
| `/` with a floating-category operand | Exact rational result, rounded only at materialization | `5.0 / 2` is 2.5 |
| `%` | `a - trunc(a / b) * b`, retaining the operand category rule | `-5.5 % 2.0` is -1.5 |
| Division or remainder by zero | Located constant-evaluation error | `1.0 / 0.0` rejects as an untyped expression |
| Comparisons | Compare exact values; produce a concrete boolean | `2 == 2.0` is true |
| Bitwise operators | Integer-category operands only; mathematical integers with sign extension | `2.0 & 3` rejects; where supported, `~x` means `-x - 1` |
| Left shift | Integer-category operands; nonnegative shift count; exact multiplication by a power of two | `1 << 8` is 256 |
| Right shift | Integer-category operands; nonnegative shift count; arithmetic shift | `-3 >> 1` is -2 |

This table applies only to operators already present in A7. It adds no operator
spelling. Typed float remainder retains L33. Typed IEEE operations retain L16,
including its nonfinite values; rejecting zero division in the untyped exact
category does not ban typed IEEE infinity or NaN.

For signed zero in the floating category, propose the IEEE sign rules for
negation, multiplication, division and remainder. Under round-to-nearest,
opposite-sign exact cancellation produces positive zero; adding two negative
zeros preserves negative zero. Comparisons treat the two zeros as equal.

Negative shift counts produce a located constant-expression error. Typed
integer division and remainder remain pending under G3; the proposed untyped
truncation convention must be considered when that gate is decided.

Destination typing does not change division semantics. `RATIO :: 5 / 2` is 2
even when later assigned to `f64`; `RATIO :: 5.0 / 2` is 2.5 and cannot fit an
integer. Explicitly typed operands establish concrete arithmetic before any
later assignment. This distinction needs native examples in the compatibility
report because it can change previously rounded constant results.

## Contexts that require a type

| Context | Proposed behavior |
| --- | --- |
| Annotated variable, field, concrete parameter or return | Fit directly to the declared numeric destination |
| Inferred mutable variable | Materialize the category default, `i32` or `f64` |
| Typed numeric operand, except shift counts | Fit the untyped operand to that concrete numeric type before the operation |
| Shift with a typed operand | The left operand determines the result type. A typed count never supplies a type for the left operand; default an untyped left operand before a typed shift. Validate the count separately under the existing typed shift rules |
| Explicit `cast(T, value)` | Materialize an untyped operand to its category default, then apply the existing explicit-cast rules. The result has type `T`; this packet adds no new cast conversion or truncation permission |
| Variadic formatting with no numeric destination | Materialize the category default; keep existing formatting rules |
| Fixed-array length or index destination | Require an integral value fitting `usize`; preserve existing index rules |
| Pattern against a typed numeric subject | Fit to the subject type before checking duplicate or overlapping patterns |
| Generic parameter with a known concrete numeric expectation | Fit to that expectation |
| Generic inference with no concrete numeric expectation | Supply the category default; add no new overload ranking or generic specialization rule |
| Array or aggregate with a declared element type | Fit each numeric element to its declared destination |
| Aggregate with no declared element type | Use existing aggregate inference with category defaults; add no new heterogeneous numeric inference |

For example, `cast(i32, 2.5)` first supplies a concrete `f64` operand to the
existing cast checker. It must not acquire implicit-fitting permission or a new
truncation rule from this packet. Likewise, `cast(u8, 256)` follows the existing
out-of-range cast policy after materializing `i32`. Current compile-only probes reject both: `cast(i32, 2.5)` requires a finite
integral range proof, and `cast(u8, 256)` reports that the target range is not
proven. Preserve these rejections under the proposal. Direct `x: i64 = BIG` remains the
proposed way to fit an exact constant beyond the default `i32` range.

Mixed typed/untyped operations need an explicit compatibility check. Under this
proposal, an `i8` value plus untyped `200` rejects because `200` cannot fit `i8`.
An `f32` value plus untyped `1e100` rejects for overflow. Do not silently retain
current widening for those cases while documenting destination fitting.

Where a default cannot represent a value, report that default and suggest an
explicitly typed intermediate. For example, pass `wide: i64 = BIG` to formatting
instead of passing `BIG` without a destination.

A boolean or string is not a numeric destination. Existing conversion policy
for nonnumeric types remains in force. An untyped constant cannot acquire a
runtime address or representation without first acquiring a concrete type.

## Global resolution

Register declarations and signatures, then resolve the types and required
constant values with explicit dependency worklists. Do not recurse. Check
function bodies after their global dependencies have resolved.

```a7
FIRST :: SECOND
SECOND :: 2.0
main :: fn() { n: i32 = FIRST }
```

The proposal accepts this dependency chain in either declaration order. An
unknown name fails at its reference. A value dependency cycle such as
`FIRST :: SECOND` with `SECOND :: FIRST` fails with the dependency chain and
source locations. An explicit type may resolve type inference without making
an invalid value cycle valid. Do not confuse legal forward function signatures
with cyclic constant values.

Global resolution must not reorder runtime initializer evaluation, run user
functions at compile time, or change module lookup or local visibility. Ordinary
initializer calls with known return types continue to use those types. Cases
whose type depends on unresolved generic inference require located diagnostics,
not permissive `UNKNOWN` operations.

## Proposed resource limits

GLM developed and corrected a [concrete resource policy](../research/untyped-constant-resource-policy-2026-09-20.md).
[The review record](../research/untyped-resource-review-evidence-2026-09-20/README.md)
preserves the initial errors and follow-up corrections. L47 approves these
limits; the isolated candidate did not enforce them.

| Limit | Proposed default |
| --- | --- |
| Numeric token length | Keep the existing 100-character limit |
| Absolute decimal exponent | 4,096 |
| Reduced exact numerator or denominator | 131,072 magnitude bits per component |
| Transient component | 262,144 bits, including any addition carry |
| Work per evaluated initializer or fitting context | 2^24 abstract limb-operation credits |
| Work per compilation | 2^32 abstract limb-operation credits |
| Retained exact bindings and cache | 16 MiB of logical payload under the policy formula |
| Dependency-chain depth | 65,536 bindings, processed iteratively |
| Rendered diagnostic value | 256 characters; whole diagnostic at most 2,048 |
| Rendered dependency chain | At most 32 links, preserving both ends |
| Emitted target numeric representation | Integer payload at most 64 bits; float representation bounded by its target encoding |

Credits are deterministic accounting units, not elapsed-time guarantees. Logical
payload is not process RSS. Check conservative growth bounds and charge work
before allocating large intermediates. Signed bitwise operations include a
possible extra magnitude bit. Rounding's internal shifts and divisions must use
the same checks. Do not disable Python's integer-to-decimal conversion limit.

Conservative bounds can reject an expression whose final reduced result would
fit. This is an explicit proposed compiler-limit rule, not silent approximation.
Tests must cover actual production-policy wiring as well as small injected-limit
fixtures. Unit fixtures alone cannot qualify resource enforcement.

A measured compatibility example is `x: f64 = 1e9999`, which currently builds
and prints `inf` in both native profiles. The proposed exponent limit rejects
it during tokenization. [The evidence](../research/untyped-exponent-baseline-2026-09-20.json)
is a small ordinary baseline program, not a resource-exhaustion experiment.
The existing typed math-call route remains available for intentional infinity.

The policy's short-circuit accounting does not approve new dead-code or unsafe
program acceptance. Preserve existing semantic checks. Any change to their
acceptance requires its own concrete compatibility example under the language
approval rule.

## Implementation requirements

1. Preserve numeric token spelling and source spans through parsing. Do not
   construct a host float before exact-value checking.
2. Represent untyped integer and floating categories separately from runtime
   types. Retain exact values and signed-zero information where required.
3. Resolve constant dependencies with worklists. Cache context-independent
   values, not a concrete type chosen by the first use.
4. Apply destination fitting at semantic boundaries. Keep typed arithmetic and
   explicit casts on their existing paths unless a separately approved rule
   changes them.
5. Emit constants using the resolved use-site type. Verify that Zig compilation
   does not add a second conversion or intermediate rounding step.
6. Update diagnostics, SPEC, examples and generated documentation only after
   the new behavior passes its compatibility checks and release gate.

Keep this implementation bounded to constants and global dependencies. It does
not require replacing the compiler's entire typed representation first.

## Diagnostics and acceptance

Diagnostics must identify the use site, destination type and offending value
without unbounded rendering. Show a bounded exact representation when feasible;
otherwise show the source span, numeric category and size summary. Never round
a displayed value as if it were exact. Distinguish fractional values, out-of-range values, unknown names,
dependency cycles, negative shifts, default-type overflow, resource limits and
unsupported constant operations. Preserve the declaration
location as supporting context. Invalid programs emit no new usable artifact.
An old artifact from an earlier successful compilation must not be mistaken for
output from a failed invocation.

Acceptance must verify observable behavior:

- Both orders of the `RATE` example print `2`; both string orders print `hello`.
- Fractional and range failures reject in both orders with valid nearby controls.
- One constant can feed different fitting destinations without first-use bias.
- Decimal values beyond host-float precision retain the exact integer value.
- Defaults, explicit widths and typed function results preserve the proposed
  boundary between constants and runtime values.
- Float rounding, signed zero, underflow and overflow follow the selected rules.
- Untyped arithmetic and typed wrapping differ only where the approved contract
  says they should. Test actual returned or printed values.
- Dependency chains resolve; cycles and missing names fail with useful locations.
  Deep chains work at Python recursion limit 100.
- Successful native cases run in Debug and ReleaseFast. A fresh repository corpus
  comparison records acceptance, diagnostics and behavior changes. Complete the
  release gate after implementation, with generated-doc parity checked.

These are requirements for future tests, not claims that tests already pass.
No coverage percentage or test-count target qualifies this change.

## Measured compatibility examples

[Ten current compiler probes](../research/untyped-constants-baseline-2026-09-20.json)
preserve sources, commands, diagnostics and emitted Zig. These are compile-only
results. A separate [native follow-up](../research/untyped-constants-native-2026-09-20.json)
built the six accepted cases with Zig 0.16.0 in Debug and ReleaseFast. Results
matched between profiles.

| Current source case | Current A7 result | Proposed result |
| --- | --- | --- |
| `cast(i32, 2.5)` | Rejects for missing integral range proof | Still reject |
| `cast(u8, 256)` | Rejects for target range proof | Still reject |
| Typed `i8` plus literal or named constant `200` | Emits an `i32` result, but Zig rejects `200` in the `i8` operation | Reject fitting `200` to `i8` |
| Typed `f32` plus literal `1e100` | Builds and prints `inf` | Reject implicit fitting overflow |
| Typed `f32` plus named constant `1e100` | Builds and prints `inf`, despite an emitted `f64` result declaration | Reject implicit fitting overflow |
| `5 / 2` assigned to `f64` | Builds and prints 2 | Retain 2 |
| `5.0 / 2` assigned to `f64` | Builds and prints 2.5 | Retain 2.5 |
| `5.0 / 2` assigned to `i32` | Rejects a type mismatch | Reject the fractional value |
| `9007199254740993.0` assigned to `i64` | Rejects a type mismatch | Accept the exact integer |

These measurements expose additional compatibility changes beyond the original
`RATE` example. In particular, mixed-operand fitting would remove some current
widening behavior. The large-float cases are confirmed working programs whose
acceptance would change. L47 now approves that consequence.

### Expanded baseline

The [255-file baseline](../research/untyped-corpus-baseline-2026-09-20.json)
records each source hash, compile command, status, errors and generated Zig
against a frozen copy of the current compiler. A7 accepts 135 files. The
inventory is repository `.a7` files listed by `rg`, excluding `tmp` and
`site/node_modules`. It excludes source strings embedded in Python tests.
The [first candidate comparison](../research/untyped-candidate-2026-09-20/controller-review.md)
accepts 136 files, with one newly accepted literal-fitting reproducer and five
other generated-text changes. No accepted file became rejected in that bounded
inventory. It is a partial prototype and leaves numeric/context gaps; it does
not qualify the complete proposal.

[Nineteen operator and context probes](../research/untyped-contexts-baseline-2026-09-20.json)
cover calls, returns, fields, arrays, patterns, generic defaults, arithmetic and
typed wrapping. Six pass A7 and native compilation in both profiles. Current
`0.1 + 0.2 == 0.3` prints `false`, so exact untyped arithmetic would change a
working program to `true`. Typed `u8` wrapping prints `0` and must stay unchanged.
The generic default probe prints `2`; its result must keep a concrete `f64`
type even though the printed value looks integral.

The rejected context probes are baseline evidence, not proof that all those
features should reject under the proposal. Full commands, diagnostics and source
are preserved. Prototype coverage must report unsupported contexts separately.

## Prototype evidence and remaining implementation

The [numeric follow-up](../research/untyped-candidate-followup-2026-09-20/REPORT.md)
fixes the first prototype's overflow, rounding and division failures. Its native
matrix verifies the listed numeric cases, including existing global infinity/NaN math
calls. The [independent IEEE verification](../research/untyped-ieee-verification-2026-09-20/README.md)
checks fixed mathematical expectations through a separate stored-bit observer:
17 accepted rows pass in Debug and ReleaseFast; two overflow rows reject at A7
stage. Expected bits come from the [independent cases](../research/untyped-ieee-acceptance-2026-09-20.md),
not from the candidate conversion routine.

Selected regression checks report 52 passes and one baseline-reproduced stale
recursion-list failure. Two candidate tests first needed explicit wide
intermediates because of the proposed formatting default. Their original
sources do not pass unchanged. The production recursion allowlist was corrected
separately after confirming that those old recursive groups no longer exist;
the focused production checks then passed all 41 cases.

The controller's second frozen-candidate scan uses the original 255-file source
inventory and verifies every source hash. It accepts 136 files against the
baseline's 135. One literal-fitting reproducer becomes accepted; thirteen files
have generated-code or diagnostic differences in total. The scan is compile-only.
It omits source strings embedded in tests and does not establish full product
compatibility. An initial rerun included newly archived research fixtures; that
non-comparable run is preserved separately and excluded from the result.

Implementation remains isolated. Before any production implementation can be
called complete:

- Finish untyped binding storage without provisional default-f64 materialization
  of the declaration itself. A binding's value must survive until a use needs a
  concrete type, including large values later reduced by exact arithmetic.
- Complete the operator/context table, including exact bitwise operations and
  shifts, array indices and lengths, pattern fitting and generic inference.
- Implement the proposed resource policy and verify actual enforcement through
  the real compiler paths. Injected-limit fixtures are supporting evidence only.
- Complete dependency-chain diagnostics, target-width handling and every
  compatibility change revealed by the full implementation.
- Report a failed global initializer once. GLM found duplicate evaluation
  diagnostics; the controller confirmed that `BAD :: 1.0 / 0.0` prints the same
  error three times. [The reproduction](../research/untyped-candidate-followup-2026-09-20/duplicate-diagnostic.json)
  records exit 6 and no new artifact.
- Run the compiler/package and release checks on the completed production change,
  and update SPEC, examples and generated public documentation.

No full release gate or resource-enforcement qualification is claimed for this
experiment. L47 authorizes implementation of these rules and resource limits. Preserve the original baseline and
failed-prototype evidence when continuing implementation.

## Review disposition and implementation blockers

[GLM's advisory report](../research/untyped-constants-glm-review-2026-09-20.md)
completed with process exit 0. An independent Codex review also checked constant
fitting, shift contexts, explicit casts and mixed-operand compatibility.

- F1's missing-route concern is resolved by native evidence of global
  `INF :: math.exp(1000.0)` and `NAN :: math.sqrt(-1.0)` in both profiles.
  The proposal preserves these existing typed routes. Rejecting `1e400`
  still changes a working program and remains in the approved compatibility examples.
  Zero-division cases already reject; do not describe them as newly rejected
  working programs.
- F2 now has a GLM-reviewed concrete policy, including two corrective passes.
  Enforcement remains an implementation and verification blocker. No resource
  caps were added to the candidate and no exhaustion probe was executed.
- F3 is clarified: rejecting untyped zero division is an explicit proposal;
  typed IEEE nonfinite values remain allowed under L16.
- F4, F5 and F6 now specify negative-shift/default failures, the G3 dependency
  and floating-category exclusion from bitwise operations.
- F7 now requires direct rounding to the destination width without double
  rounding through a host float.
- F8 concerns explanation. An untyped `0.1 + 0.2 == 0.3` compares exact values.
  A typed `f64` operand first converts its untyped counterpart to `f64`, so
  typed arithmetic remains IEEE arithmetic. Do not fold the typed version
  using untyped exact-value rules.

The original design report and the later resource-policy reviews are advisory.
The numerical prototype has separate evidence and limitations above. Policy
review does not establish resource enforcement or release readiness. F1 has an
existing typed route; the literal-overflow and resource-limit changes remain
approved compatibility changes.

[GLM's final frozen-candidate review](../research/untyped-candidate-glm-2026-09-20/README.md)
completed with exit 0. It found no wrong numeric result in its bounded checks.
Its duplicate-diagnostic finding is reproduced and remains open. Its comparison
clarification is reflected above. A follow-up source review did not substantiate
its mixed-integer bypass concern; the linked disposition records why. Full
numeric-context qualification is still required. The reviewer ran no native builds; native
evidence comes from the separate recorded compiler and IEEE checks.

## Sources and preserved evidence

[The comparison report](../research/global-constants-2026-09-20.md) records
primary Odin, Go, Zig and Rust documentation and local Zig/Rust probes.
[The strict proposal archive](P-TYP-forward-globals-strict-history.md) preserves
the earlier A7 native evidence and corpus experiment without treating that
proposal as approved. Implementation status is tracked in the production evidence; historical
prototype reports retain their original approval status.
