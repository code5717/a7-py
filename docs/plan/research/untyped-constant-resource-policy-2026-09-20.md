# Proposed compiler resource policy for untyped numeric constants

Date: 2026-09-20. Author: GLM-5.3 via OpenCode (`zai-coding-plan/glm-5.3`),
advisory external review under the security-review routing of L12. This is the
GLM-reviewed resource policy that [P-TYP](../packets/P-TYP-forward-globals.md)
names as a blocking prerequisite ("Remaining work before implementation
approval") and that the earlier [GLM review](untyped-constants-glm-review-2026-09-20.md)
requested as F2.

Status: **proposed, not implemented, not qualified.** Every number below is a
default cap selected for implementation approval. Passing the boundary tests in
§10 is the qualification step; nothing here claims qualification now. This
document records proposals and evidence only.

Scope: the untyped-constant evaluator (exact integer and rational values,
literal parsing into that evaluator, its diagnostics and backend emission).
It is not a sandbox of the whole compiler; see §9.

## What was verified for this document

Read: P-TYP packet, its GLM review, `docs/plan/decisions.md` (L4, L5, L12,
L16, L33, L47), `a7/const_eval.py` (all 155 lines), `a7/tokens.py`
(literal tokenization and current caps, lines 505-605), `a7/ast_nodes.py`
(literal construction, lines 575-604), `a7/backends/zig.py` (`_emit_literal`,
lines 1680-1737), `pyproject.toml` (`requires-python = ">=3.13"`),
`test/test_no_recursion.py` header, and — added in the correction pass — the
[nonfinite baseline](untyped-nonfinite-baseline-2026-09-20.md) with its JSON
evidence (F1 claims, §12).

Ran (closed-form arithmetic and host-fact checks only, in scratch Python, not
through the compiler; no pathological input was compiled, no Zig invoked, no
exhaustion experiment performed; no sub-agents or nested CLIs launched —
recursion guard held):

- Host Python 3.14, `sys.get_int_max_str_digits()` = 4300 (CPython default),
  minimum configurable value 640.
- `str(10**5000)` and `int("1" + "0"*5000)` raise `ValueError`; `hex(10**5000)`
  and `int(s, 16)` / `int(s, 2)` succeed (power-of-two bases are linear and
  uncapped).
- `float("1e400")` is `inf` and `float("1e-400")` is `0.0` — the current lexer
  path at `a7/tokens.py:591` and `a7/ast_nodes.py:590` does host-float
  conversion.
- Double-rounding witness (§10, T8): exact value `1.0000000596046448` rounds
  to `1.0000001192092896` when converted directly to f32 with
  round-to-nearest-ties-to-even, but to `1.0` when first rounded to f64.
  Verified by integer-arithmetic reference implementation, not by assertion.
- Correction-pass recomputation (same day, same scratch-Python method): 333
  bits doubled 20 times is 41.625 MiB, not 40 GB (30 doublings reaches
  ~44.7 GB); C5/C6 step counts recomputed from the quadratic charges (§5);
  `5e-324` is not equal to 2^-1074 (ratio ≈ 1.012) and rounds to it (T10);
  `float("1e9999")` is `inf` on the host path and `9e-99999999999999999` is
  20 characters, so C2 newly rejects literals that lex today (§8).
- Signed bitwise/complement growth check (final consistency pass, same
  method): for all a ∈ [−4096, 4096] and b ∈ [−256, 256], the magnitude bit
  length of a & b, a | b, a ^ b is ≤ max(bit length |a|, bit length |b|) + 1,
  and that of ~a is ≤ bit length |a| + 1; maximum observed growth is exactly
  1 bit (−1 ^ 1 = −2; ~3 = −4). No compiler run, no exhaustion.

Estimates marked "estimate" below (bit counts derived from sizes, expected
costs from CPython bigint implementation) are reasoning, not measurements.

## 1. Threat model: what the operator table admits

From tiny source, under exact evaluation, before any caps:

| Attack shape | Growth | Concrete example |
| --- | --- | --- |
| Chained exact `*` (squaring) | Result bits double per step | 100-char literal (~333 bits) doubled 20 times is ~42 MiB; 30 times is ~44 GB |
| Unbounded left shift | Result bits ≈ operand bits + shift count | `1 << (1 << 30)` is 2^30 bits = 128 MiB (F2's example) |
| Rational accumulation | Denominator bits add per term (before reduction) | 100 additions of 3,000-bit denominators ≈ 300k bits |
| Huge decimal exponent in a ≤100-char literal | Exact value 10^(10^98−1) | `1e` + 98 nines is exactly 100 token characters |
| Decimal rendering | `str(int)` past 4300 digits raises `ValueError` on this host | an error path that itself crashes the diagnostic |

The current lexer caps token length (`MAX_NUMBER_LENGTH = 100`,
`a7/tokens.py:15`), which bounds literal *spelling*, not value growth through
arithmetic, and does not bound the exponent magnitude encoded in those 100
characters. Current folding (`a7/const_eval.py`) is bounded only by the node's
concrete type width; the untyped proposal removes that width, so explicit
value caps must replace it.

## 2. Design principles

1. **Preflight before allocation.** Every operation that can grow a value
   computes a conservative upper bound on its result bit length from operand
   bit lengths first (O(1) on bit lengths) and rejects with a located
   diagnostic before allocating. Never allocate-then-check.
2. **Reject, never approximate** (already required by the packet). A cap
   violation is a located compile error naming the binding, operation and
   limit. No silent rounding, no truncation, no fallback to host floats.
3. **Canonical reduced form.** Rational values are always stored with
   denominator > 0 and gcd(numerator, denominator) = 1. This makes bit lengths
   canonical minima, so preflight upper bounds are as tight as the operands
   allow and comparisons cannot be inflated by non-reduced junk.
4. **Power-of-two text representations internally.** Hex is linear-time and
   exempt from the host decimal conversion cap; decimal conversion is only
   allowed under the guard of §7.
5. **Caps are compiler-internal constants.** No CLI flag, environment variable
   or source pragma can raise or lower them. Tests use an internal policy
   object with injected small caps (§10); production paths construct only the
   defaults.
6. **Deterministic evaluation.** Constant results depend on source alone, so
   qualification is reproducible.

## 3. Default caps

| ID | Cap | Default | Unit | Enforcement point |
| --- | --- | --- | --- | --- |
| C1 | Numeric token length | 100 | characters | Already enforced, `a7/tokens.py:15` (`MAX_NUMBER_LENGTH`) |
| C2 | Decimal exponent magnitude, literal `m × 10^e` | 4096, inclusive (absolute value) | power-of-ten exponent | New check at tokenization, before any exact value is constructed |
| C3 | Per-value component bit length (numerator, denominator, each separately, reduced form) | 131,072 (= 2^17, 16 KiB per component) | bits | Preflight before every growth operation (§4) |
| C4 | Transient cross-product scratch | 262,144 (= 2^18, 32 KiB) | bits, per operation | Comparisons and rational add/sub preflight, including the numerator-sum +1 carry (§4) |
| C5 | Per-initializer work budget | 2^24 | 64-bit limb-op credits | Charged per evaluation step of every evaluated constant initializer — a `::` binding, an ordinary variable initializer, or a fitting/rounding context (§5) |
| C6 | Per-compilation work budget | 2^32 | 64-bit limb-op credits | Accumulated across all constant evaluation |
| C7 | Retained exact-value memory (stored binding values + constant-value cache) | 16 | MiB of logical payload, counted as `ceil(bits/8)` per component + 64 B per entry | Every retention point: binding finalization and cache insert (§5.1) |
| C8 | Constant dependency chain depth | 65,536 (= 2^16) | bindings per chain | Iterative worklist visit counter |
| C9 | Diagnostic value rendering | 256 | characters per value; whole diagnostic ≤ 2,048 characters | Diagnostic formatter |
| C10 | Rendered dependency chain | 32 | links (first 16, ellipsis, last 16 when longer) | Diagnostic formatter |
| C11 | Emitted numeric literal | 64 | bits for integer destinations; ≤ 32 characters for float destinations, exact hexadecimal spelling preferred (§8) | Backend emitter |

Rationale for the two central numbers:

- **C3 = 2^17 bits.** The only class in §8 carrying an explicit ≤ ~390-bit
  bound is the ≤ 20-character float literal with |exponent| ≤ 99; for that
  class the margin is >300x. No size claim is made about hand-written
  constants in general — under C1+C2 alone a 100-character mantissa with
  exponent 4,096 is about 13,930 bits, margin ~9.4x. A 131,072-bit value
  costs 16 KiB of logical storage; one full-width multiplication charges
  2,048² = 2^22 limb credits (quadratic overcharge; estimate, see §5).
- **C2 = 4096.** It must be ≥ a few hundred so `1e400`-class literals keep
  an exact representable value (10^400 ≈ 1,329 bits under C3). The nonfinite
  baseline observed that `x: f64 = 1e400` currently builds and prints `inf`,
  so C2 keeps that question a *semantic* fitting decision for the packet
  (§12), not a resource rejection. It must be small
  enough that exponent-driven bit growth (~3.33 bits per power of ten) cannot
  approach C3 from a single literal: 4,096 powers of ten contribute ≈ 13,607
  bits, plus ≤ 333 mantissa bits ≈ 13,940 bits < C3.
  4,096 sits between with an order of magnitude of headroom on both sides.

Shift counts need no separate numeric cap: `a << k` has result bits ≈
bits(a) + k, so the C3 preflight on the result rejects any oversized count,
including counts whose own value is huge (comparing k against the remaining
budget is O(1) via bit lengths; the count itself must already satisfy C3 to
exist). Negative counts are rejected as proposed by the packet. A right shift
never grows its operand and needs only the sign check.

No exponentiation operator exists in A7 (`BinaryOp` in `a7/ast_nodes.py:102-129`
has no `**`); if one is ever added to constant evaluation, this policy must be
revised first, because `pow` grows faster than any preflight-per-step rule
tolerates.

## 4. Preflight obligations (before allocation)

Preflight computes conservative upper bounds from operand bit lengths in O(1);
the preflight arithmetic itself is host O(1) work and is uncharged. Bit
length means the bit length of the operand's *magnitude* (`int.bit_length()`
semantics; 0 for 0). Negative integers are exact values and, for the bitwise
operators and complement, follow two's-complement sign-extension semantics.
The evaluator must check, then allocate:

| Operation | Preflight (bits) | Notes |
| --- | --- | --- |
| Integer `+`, `-` | max(ba, bb) + 1 ≤ C3 | Sum can carry 1 bit past the wider operand |
| Integer `*` | ba + bb ≤ C3 | Primary growth path; actual product has ba+bb or ba+bb−1 bits |
| Integer truncating `/`, `%` | none (result ≤ dividend) | Divisor zero already a semantic error |
| Shift `<<` | ba + k ≤ C3, k ≥ 0 | k is the exact count value |
| Shift `>>` | k ≥ 0 only | Result shrinks |
| Bitwise `& \| ^` | max(ba, bb) + 1 ≤ C3 | Under sign extension the result magnitude is ≤ 2^max(ba,bb), so its bit length can exceed the wider operand by 1 (−1 ^ 1 = −2: 1 bit → 2); bounded small-range check, §"What was verified" |
| Rational `+`, `-` (a/b ± c/d) | cross products ba+bd ≤ C4 and bc+bb ≤ C4; denominator product bb+bd ≤ C4; numerator sum max(ba+bd, bc+bb) + 1 ≤ C4 | The +1 carry is inside the ≤ C4 check, so no unguarded C4+1 temporary exists; the unreduced fraction — the gcd inputs — is C4-scale, not C3-scale |
| Rational `*` | ba+bc ≤ C3, bb+bd ≤ C3 | |
| Rational `/` | ba+bd ≤ C3, bb+bc ≤ C3 | Divisor zero is a semantic error |
| Rational reduce (gcd) | none of its own | Inputs are the unreduced add/sub results, each ≤ C4 bits (the numerator-sum preflight includes its +1 carry); their allocation was already bounded by the C4 checks above; work is charged (§5) |
| Comparison via cross-multiply | ba+bd ≤ C4 and bc+bb ≤ C4 | May prefilter by sign and bit length when they already decide |
| Negation | none | Same size |
| Complement `~` (`UnaryOp.BIT_NOT`, `a7/ast_nodes.py:137`) | ba + 1 ≤ C3 | ~a = −a−1; magnitude can grow 1 bit (~(2^k − 1) = −2^k) |
| Fitting/rounding to f32/f64 | every internal operation passes its own row above | Integer-only arithmetic on the rational (§8), but no blanket exemption: each internal shift, division, multiplication, comparison and scan must satisfy its own preflight in this table and its own §5 charge, and its scratch stays within the C3/C4 bounds above |

Stored-result rule for rational add/sub: after the C4-bounded temporaries
exist, the fraction is reduced and the stored numerator and denominator must
each satisfy ≤ C3. This one check happens after an allocation that the C4
preflight already bounded (reduction only shrinks); it is a value check, not
an allocation guard. Every other bound above is checked before any
allocation.

**These bounds are conservative, not exact.** A product of ba- and bb-bit
integers has ba+bb or ba+bb−1 bits; a sum carries at most +1; a rational sum
can cancel down to arbitrarily few bits. Exact result sizes are not computable
in O(1) from operand sizes, so the evaluator intentionally rejects some
operations whose final stored value would have fit:

- an integer multiply with ba+bb = C3+1 whose product happens to be
  ba+bb−1 = C3 bits;
- `(a×b) − (a×c)` with wide operands and a tiny difference: the transient
  products are preflighted at full width and rejected even though the stored
  result would be small — cross-cancellation is only visible after
  allocation, and preflight cannot see it;
- a rational add whose unreduced cross products exceed C4 but whose reduced
  sum is small.

Conservative rejection is the chosen semantics. Preflight-before-allocation
(§2.1) forbids computing wide temporaries to discover a small result, and
reject-never-approximate (§2.2) forbids proceeding provisionally. Source that
hits a conservative bound gets a located compile-time resource error, not a
wrong value; authors must restructure (for example, factor out the common
term before multiplying).

## 5. Work and cost model

Units: abstract 64-bit limb-operation **credits**. A credit count is a
deterministic function of operand bit lengths, so budgets are reproducible
and depend on source alone. All charges use `ceil` and a minimum of 1 credit
per step: no evaluated step is free, so long chains of tiny operations still
drain the budgets. The charges are *intended* to overcharge typical CPython
bigint costs (quadratic mul versus Karatsuba, 2× product for gcd) — an
estimate from CPython's algorithm choices, not a proven universal upper
bound over CPython versions, and credits bound neither seconds nor RSS
(§5.1).

| Step | Charge (limb-op credits) |
| --- | --- |
| Integer/rational `+`, `-`, comparison prefilter | max(ceil(bl/64), ceil(br/64)), minimum 1 |
| Multiplication or division of components | ceil(ba/64) × ceil(bb/64), quadratic overcharge (estimate, unproven as a bound) |
| gcd-based reduction | 2 × product charge of its actual inputs — up to 2 × (C4/64)² inside a rational add (estimate) |
| Cross-multiply comparison | 2 × product charge |
| Shift `<<` / `>>` | ceil(result bits / 64), minimum 1 |
| Linear scan (normalization; digit/sticky scans inside exact→f32/f64 rounding) | ceil(operand bits / 64), minimum 1 |
| Dependency-graph node visit | 1 per worklist pop (visits bounded by C8 and by binding count) |
| Cache hit / binding-value reference | ceil(value bits / 64), minimum 1, charged to C6 |

Rounding is not priced or guarded as one linear scan: only its scan portions
charge the linear-scan row; every shift, division, multiplication and
comparison inside the exact→f32/f64 algorithm charges under its own row and
passes its own §4 preflight.

Budgets: C5 = 2^24 credits per evaluated constant initializer (an initializer
expression DAG). This covers every evaluated initializer or expression, not
only `::` bindings: constants in ordinary variable initializers and the
fitting/rounding conversions applied to them charge the same C5/C6 budgets
through the per-operation rows. At the quadratic charges that is 4
full-width (2^17-bit) multiplications, or
one full-width multiply+gcd-reduce step (3 × 2^22 ≈ 1.26×10^7 credits, 75%
of C5). A maximal-width rational add+reduce — whose gcd runs on 2^18-bit
unreduced inputs (§4) — charges ≈ 4.6×10^7 credits, 2.75 × C5: such a step
is size-legal under C3/C4 but is rejected by the per-initializer work
budget; wide rational arithmetic is C6-scale (≈ 1% of C6 per step). C6 =
2^32 per compilation: 1,024 full-width multiplications, or ~341
multiply+reduce steps. At the 1-credit minimum, each charged step
corresponds to at least one source token (≥ 1 character) in the evaluated
expression, so exhausting C6 requires ≥ 2^32 characters ≈ 4 GiB of source at
the absolute cheapest — C6 binds machine-generated or wide-value files, not
hand-written ones. No wall-clock or memory claim follows from these counts
(§5.1). Violations report the binding, the budget and the operation that
exceeded it. Diagnostic rendering and backend emission conversions are not
part of an initializer's charge; they remain bounded by §7 and C9/C11.

Accounting rules:

- Charge only operands actually evaluated. Short-circuit `and`/`or` skip the
  right operand; skipped work costs zero (§11 discusses semantics).
- Cache hits charge one linear scan (ceil(bits/64), minimum 1) to C6, so a
  million references to a cached wide constant cannot loop freely.
- C7 is enforced at every retention point (binding finalization and cache
  insert) with the §3 formula, as a located resource error, not an eviction.
  It is **logical payload accounting**: the 64 B-per-entry term is the
  policy's bookkeeping constant, not an observed CPython size. Real RSS per
  entry is higher — an ordinary small entry carries roughly 200 B of CPython
  object overhead (estimate) — so 16 MiB of logical payload is not 16 MiB of
  process RSS and is not claimed to be (§5.1). Under the formula an ordinary
  64-bit value costs 8 + 8 + 64 = 80 B of logical payload, so C7
  accommodates ~200,000 ordinary retained values — far beyond any
  hand-written file; machine-generated larger files get a clean rejection.

### 5.1 Live memory within the evaluator scope

C7 and the §4 preflights bound *logical payload* — bits of exact value
counted by the formula — and only inside the untyped-constant evaluator:

- Per-operation temporaries: every temporary is bounded by C4 bits by the
  §4 preflights — the rational-add numerator-sum check includes its +1
  carry, so no temporary reaches C4+1. The peak simultaneous set for a
  rational add is the four operand components (≤ C3 each, 64 KiB), up to
  three transient products (≤ C4 each: both cross products and the
  denominator product) and the numerator sum (≤ C4) — 4 × 32 KiB = 128 KiB
  more — for ≈ 192 KiB of logical payload, plus gcd remainder
  temporaries, each no larger than its inputs. A loose invariant covering
  every operation: at most ~10 live temporaries × 32 KiB ≈ 320 KiB logical
  per in-flight operation.
- Worklist: resolution holds references (names, locations), not value
  copies; each pending binding appears at most once (visit counters) and the
  number of bindings is bounded by source tokens, so worklist payload is
  O(bindings × small constant), independent of value sizes.
- Retained values: all stored binding values plus cache entries share the
  C7 total (16 MiB logical), checked at each retention point. Counting
  bindings as well as the cache is load-bearing: without it, a
  machine-generated file of `A :: 1 << 131000`-style bindings could retain
  ~16 KiB per ~15 source characters across an unbounded number of bindings.

These are accounting bounds on what the evaluator retains. They are not
process bounds: whole-process RSS also contains the parser, AST, modules and
interpreter overhead (§9), and nothing here measures or caps those.

## 6. Dependency graph depth and no recursion

- Resolution must use explicit worklists/stacks, no recursion, per the
  repository no-recursion rule and `test/test_no_recursion.py`; deep chains
  must compile with the Python recursion limit at 100 (the packet already
  requires this; the policy adds the numeric bound).
- C8 caps a single dependency chain at 65,536 bindings. A longer chain needs
  ≥ 65,536 links at ≥ 5 source bytes each (`A::B` is the minimal spelling) —
  ≥ ~320 KB of source, more with real names; the cap bounds
  resolution bookkeeping and diagnostics regardless of future refactors.
  Exceeding it reports the first and last 16 links (C10) and the depth.
- Cycles report their full cycle when ≤ 32 links, else the same truncated
  rendering, with source locations, as the packet requires.

## 7. Host Python integer/string conversion limits

Verified facts on the required Python (≥ 3.13; this host is 3.14):

- CPython caps *decimal* integer↔string conversion at 4,300 digits by default
  (`sys.get_int_max_str_digits()`); the value is configurable per process from
  640 upward. Conversions that exceed the cap raise `ValueError` — emission
  and diagnostics that rely on them crash, they do not degrade.
- Conversions in power-of-two bases (`hex()`, `int(s, 2)`, `int(s, 16)`,
  `int(s, 32)`) are linear and **not** subject to the cap. `str()`, `repr()`,
  `format(..., 'd')` and `int(s)` / `int(s, 10)` are capped.

Policy:

1. **Do not disable or raise the host cap globally.**
   `sys.set_int_max_str_digits(0)` or a large global value would remove a
   host-wide safety property for all unrelated code in the process. The
   compiler must not depend on the cap being at its default either.
2. Decimal conversion of a possibly-large integer is permitted only when the
   estimated decimal digit count is ≤ 600 (estimate:
   `ceil(bit_length() × 0.30103) + 1`). This stays under the smallest value
   any host can configure (640) with margin for estimate error.
3. Otherwise render in hex (linear, uncapped), optionally sliced to C9 with
   the total hex-digit count, bit length and estimated decimal magnitude
   (exponent only, from `bit_length × log10(2)`; never the full decimal).
4. As defense in depth, wrap every remaining int→str boundary in a
   `ValueError` catch that falls back to the hex form. Do not use
   `fractions.Fraction.__str__` on possibly-large values (it renders
   decimals).

Zig-side integers: Zig accepts hexadecimal integer literals (`0x...`), so the
emitter's hex path is target-compatible. (Verify the exact spelling against
Zig 0.16 during implementation; unverified here.)

## 8. Fitting, rounding and compatibility with ordinary constants

Margins for legitimate constants under C3 = 131,072 bits (all "bits" are exact
value sizes):

| Class | Worst exact size | Margin |
| --- | --- | --- |
| i8–i64, u8–u64, isize, usize literals | ≤ 64 bits | > 2,000x |
| `9007199254740993.0` (packet case) | 54 bits | > 2,000x |
| ≤ 20-char float literal with \|exponent\| ≤ 99 | ≤ ~390 bits | > 300x |
| Exact `0.1 + 0.2` chain over 100 terms of 17-digit decimals | ~5,700 bits | ~23x |
| Any ≤ 100-char literal with \|exponent\| ≤ 4096 (C2 max) | ~13,930 bits | ~9.4x |

The third row needs its exponent qualifier: 20 characters can encode an
exponent as large as `9e-99999999999999999` (exponent −10^17+1), whose exact
value is astronomically wide. Character count alone does not bound a literal;
that is exactly what C2 exists to cap.

Conclusion: every explicitly bounded class above stays below C3 — by >300x
for the small classes and ~9.4x for the widest (C2-max) literals — and exact
chains stay within C3 only because the §4/§5 caps enforce it; beyond C1+C2
no size claim is made about arbitrary hand-written constants. Even so, the
caps are not strictly adversarial-only. The current lexer accepts
any ≤ 100-character numeric token regardless of exponent magnitude, so
literals such as `1e9999` (6 characters) lex today and reach the host-float
path (`float("1e9999")` is `inf` on this host); under C2 they become located
tokenize-time resource errors. This is an intentional compatibility change —
some currently-lexing literals are newly rejected — and it needs the packet
owner's sign-off together with F1 (§12).

Rounding rules (bounding, not semantics; semantics stay with the packet):

- Exact→f64 and exact→f32 rounding must be computed from the rational with
  integer arithmetic in one correctly rounded step (F7). Never narrow via a
  host f64 (double rounding; verified witness in §10, T8). Its scans are
  linear in operand bits, but its shifts, divisions, multiplications and
  comparisons are each preflighted (§4) and charged under their own §5
  rows; rounding is not a linear-cost blanket.
- f32 and f64 *emission*: the default proposal is an exact hexadecimal
  floating literal of the already-rounded target value
  (`0x1.<mantissa hex>p<exp>`, 6 mantissa hex digits for f32, 13 for f64;
  ≤ 32 characters, C11). A hexadecimal literal denotes its value exactly
  when the mantissa fits — it does by construction — so re-parsing cannot
  re-round: not for direct f64 destinations, and not for f32 destinations
  through Zig's `comptime_float` (f128) coercion, where an exactly
  representable value coerces exactly. Verification is still required at
  implementation, for both widths: confirm the exact Zig 0.16 spelling for
  f32/f64 typed constants, and extend the T8 harness to parse each emitted
  spelling through the same path Zig uses and compare bit patterns against
  the direct correctly-rounded conversion.
- A shortest round-trip *decimal* emission is only an optional readability
  alternative, not the default. It cannot be justified by a generic
  "intermediate precision 2p+2 makes double rounding harmless" argument:
  arbitrary exact decimals can lie arbitrarily close to a rounding
  midpoint, and a decimal chosen against direct f32 rounding may round
  differently when parsed through an f128 intermediate. If decimals are
  wanted, the selection must be verified on its own — emit, re-parse
  through Zig's actual parse path, compare bit patterns — and that
  verification is in addition to the hex path's, not a substitute for it.
- Integer destinations emit ≤ 64-bit values (≤ 20 decimal digits), always
  under the 600-digit rule of §7.

## 9. Proposed limits vs qualification vs whole-compiler sandboxing

Three distinct things, deliberately separated:

1. **Proposed limits (this document).** Static compile-time caps selected now
   for implementation approval. They become real when the implementation
   lands and the tests of §10 pass. Nothing is qualified at the time of
   writing.
2. **Measured qualification.** After implementation: the boundary tests of
   §10, the packet's corpus compatibility scan, and the repository gates
   (`./run_all_tests.sh`, and `./run_release_checks.sh` before any release
   reporting), run with the caps enforced. Qualification measures that the
   caps hold and ordinary programs are untouched; it does not prove the absence
   of other resource issues.
3. **Whole-compiler sandboxing.** Out of scope and not a substitute. Per
   AGENTS.md, `a7-py` is not a sandbox for untrusted source; these caps bound
   only the untyped-constant evaluator. They do not bound parser memory on
   giant sources, module graphs, name resolution, or Zig-side comptime
   evaluation of expressions outside the untyped-constant evaluator. Host-level
   rlimits or containers may be used by CI as engineering controls but are not
   language semantics and are not proposed here.

No resource-exhaustion probe was run against any compiler build to produce
this document, and none was needed for the size arithmetic above (§1, §3,
§8): the caps are justified by that arithmetic, not by crashing
measurements. Whether maintainers later stress-run a compiler past these
limits is an engineering decision for them; this document records the fact
that no such run happened and sets no permission rule about future runs.

## 10. Required boundary tests (small, meaningful)

Each test verifies an observable requirement of this policy. None needs
values near the real size caps. Tests that verify cap *logic* use the
internal test policy object with injected tiny caps (production defaults are
constants, §2.5); T13 and T14 additionally exercise the production defaults
directly, because injected caps alone cannot show the real paths are wired.

| ID | Test | Verifies |
| --- | --- | --- |
| T1 | `x: i64 = 9223372036854775807` accepted, `...808` rejected; `u: u8 = 256` rejected | Ordinary integer fitting unaffected; destinations use exact values |
| T2 | `x: i64 = 9007199254740993.0` accepted with exact value; `f: f64 = 1e4096` parses exact; `1e4097` rejected at tokenize with location | C2 both sides; packet's host-float-loss case |
| T3 | With injected caps (C3 = 128 bits): `BIG :: 1 << 200` is rejected before allocation with a located resource diagnostic naming binding, operation and limit; `X :: 1 << 100` under the same caps passes the resource preflight (101 ≤ 128) and is then rejected only as an i64 destination overflow — a *fitting* error with a distinct diagnostic | Preflight ordering; resource and fitting rejections are distinguishable (reject-never-approximate) |
| T4 | With injected C5 = 2^16 limb-op credits: a loop-free chain of wide multiplies in one `::` rejected at the budget with the operation named; a second binding in the same file still evaluates | Per-binding budget isolation; C6 accounting across bindings |
| T5 | Oversized value diagnostic: rendered ≤ 256 characters, contains a hex prefix, total bit length and digit-count summary, no decimal expansion, message total ≤ 2,048 characters; no `ValueError` escapes | C9, §7 |
| T6 | Cycle `FIRST :: SECOND`, `SECOND :: FIRST` reports both locations; a synthetic chain deeper than an injected C8 = 4 reports first/last links with depth | C8, C10, §6 |
| T7 | Dependency chain of depth 300 compiles with Python recursion limit 100 | No-recursion requirement, §6 |
| T8 | `x: f32 = 1.0000000596046448` materializes as `1.0000001192092896` (direct rounding), not `1.0` (via-f64) | F7 single-step rounding; verified witness, §"What was verified" |
| T9 | `0.1 + 0.2 == 0.3` true untyped; with `t: f64 = 0.1` the typed comparison follows IEEE operand fitting | Packet F8 boundary, unchanged by caps |
| T10 | `5e-324`: the exact rational 5×10^-324 is *not equal* to 2^-1074 (ratio ≈ 1.012); rounded to nearest it becomes the subnormal 2^-1074 and is accepted as f64, while `1e400`-class finite overflow is rejected at fitting per the packet | Underflow-to-subnormal permitted, overflow rejected (semantics per packet; policy verifies no resource rejection occurs) |
| T11 | Emission: integer-destination literals are ≤ 20 decimal digits (or hex); float-destination literals are ≤ 32 characters and exact-hexadecimal by default (C11, §8). Because C11 bounds emission far below the §7 600-digit guard, a >600-digit *emission* cannot occur by construction; the >600-digit hex fallback is exercised on the diagnostic path (T5), and no `str()` crash is observable on either path | C11, §7 |
| T12 | No CLI flag/env var changes caps; the internal policy object is the only injection path | §2.5 |
| T13 | Production wiring, no injected policy: through the public frontend/CLI with default caps, `x: f64 = 1e4097` yields the located C2 tokenize rejection and a >100-character numeric token still yields the C1 rejection; an ordinary constants file compiles unchanged | Default caps are constructed and enforced on real paths (§2.5) |
| T14 | Integration: the packet's compatibility corpus and repository examples with numeric constants compile with default caps enforced; a mixed file (ordinary bindings plus one C2 violation) reports exactly the violating binding and its location, and the ordinary bindings still evaluate | Caps hold end-to-end without breaking ordinary programs |

T3's negative control matters: the same oversized shift must be rejected for
the *resource* reason under tiny caps and for the *fitting* reason under
default caps with a narrow destination, with distinct diagnostics.

Per the repository's test-quality rules, the injected-cap tests (T3, T4, T6)
verify cap *logic* in isolation and cannot by themselves qualify enforcement:
a policy object with tiny caps could pass its unit tests while production
paths ignore it. T2, T13 and T14 exercise the production default wiring and
real integration. Qualification is all of §10 through the repository gates,
not the injected-cap subset.

## 11. Self-review of the growth-sensitive rules

- **Multiplication.** Each step preflights ba + bb ≤ C3, so chained squaring
  stops at or before the cap (the bound is conservative, §4); there is no
  operation whose result exceeds the cap transiently except the §4 cross
  products bounded by C4. No bypass found.
- **Rational cross products.** Both cross products, the denominator product
  and the +1 carry on the numerator sum are preflighted against C4; stored
  results against C3 after mandatory reduction (§2.3). Comparisons may
  prefilter by sign and bit-length difference when that already decides the
  order, avoiding cross products entirely; the prefilter is an optimization,
  not a correctness dependency.
- **Cancellation.** `a×b − a×c` with near-equal products can keep *stored*
  values small while *transient* work stays wide. A single such step beyond
  the caps is conservatively rejected at preflight, before allocation (§4) —
  the evaluator refuses to allocate wide temporaries in order to discover a
  small result. Repeated within-cap build-and-cancel does max-width work at
  small footprint, which the limb-credit budgets C5/C6 charge; that attack
  exhausts the work budget, not the host. No bypass found.
- **Signed bitwise and complement.** Bit length is magnitude bit length
  (§4); under two's-complement sign extension, `&`, `|`, `^` can widen the
  result magnitude by 1 bit past the wider operand (−1 ^ 1 = −2), and
  complement can too (~(2^k − 1) = −2^k). Both preflight their +1 against
  C3, and rounding to f32/f64 is charged per internal operation, not as a
  blanket scan (§4). No bypass found.
- **Short-circuit.** `and`/`or` exist (`a7/ast_nodes.py:121-122`). Work
  accounting counts only evaluated operands (§5), so skipping cannot bypass
  budgets — it strictly reduces work. One semantics note for the packet owner,
  not decided here: `false and (1/0 == 0)` suppresses the untyped zero-division
  error because the right operand is never evaluated; the packet should state
  whether that is intended for constant expressions, since it mirrors runtime
  short-circuit semantics.
- **Signed zero and category rules** carry no resource impact; they are value
  tags, not sizes.

Residual risks, stated plainly: the credit model is an estimate intended to
overcharge typical CPython costs; it is not a proven universal upper bound
over CPython implementations, and credits bound work in abstract units, not
seconds or bytes of RSS (§5.1). The caps do not cover the areas listed in
§9.3. The exact-hex emission proposal (§8) rests on exactness by
construction plus Zig's parse path; its spelling and bit-pattern equality
are unverified until the T8 harness is extended at implementation time, for
both f32 and f64.

## 12. What this policy does not decide

- F1 (infinity/NaN constants): the [nonfinite
  baseline](untyped-nonfinite-baseline-2026-09-20.md) observed that
  `x: f64 = 1e400` currently builds and prints `inf`; that `1.0/0.0`-style
  divisions are already rejected (exit 6) in every tested form, so no
  zero-division route is being lost; and that inf/NaN remain reachable today
  through typed math calls, including global `::` bindings
  (`INF :: math.exp(1000.0)` prints `inf`; `NAN :: math.sqrt(-1.0)` behaves
  as NaN). Those function-call routes sit outside the untyped-constant
  evaluator and are untouched by this policy. What remains for the packet
  owner: whether `1e400`-class literal fitting keeps today's
  accept-as-`inf` behavior or rejects finite→inf overflow — C2 keeps such
  literals exactly representable, so that choice stays semantic, not
  resource-driven — plus the separate C2 compatibility change that literals
  with |exponent| > 4,096 which lex today become tokenize-time rejections
  (§8).
- G3 typed division/remainder conventions; the packet records the dependency.
- Any new operator (including exponentiation), typed constant syntax, or
  runtime bignum values (L3/L4 unchanged).

## Recommendation

Adopt §3's caps (C1–C11), §4's preflight obligations, §5's budgets and
accounting, §6's iterative resolution with depth cap, §7's conversion rules
(hex-default, no global cap change, ≤ 600-digit decimal guard), §9's scope
separation, and §10's boundary tests as the GLM-reviewed resource policy that
unblocks P-TYP's implementation-approval gate for exact arithmetic, shifts and
rational values. With that adoption, F2 is resolved as a *policy* matter;
implementation and qualification remain open work under the packet's own
approval flow. No review or implementation deadlines are imposed by this
document.

## Correction log (2026-09-20, controller pass)

A controller review found factual and accounting inconsistencies; this pass
corrects them in place. The chosen caps stay proposed and unqualified.

1. Growth arithmetic fixed: 333 bits doubled 20 times is 41.625 MiB
   (333 × 2^20 bits), not 40 GB; ~30 doublings reaches ~44.7 GB (§1).
   C5/C6 step counts recomputed from the quadratic charges — C5: 4
   full-width multiplications or ~1 multiply+reduce; C6: 1,024 / ~341 (§5).
   The nanosecond-per-limb and seconds-at-C6 claims were removed; credits
   are abstract and no wall-clock qualification is made.
2. Preflight restated as conservative upper bounds from operand bit lengths,
   not exact result lengths; the intentional conservative-rejection
   semantics (including cancellation cases where a small final result is
   rejected because its transient products are wide) is now stated
   explicitly (§4).
3. Rational-add accounting fixed: the numerator sum carries 1 bit past the
   wider cross product and that sum bound is preflighted ≤ C4; the
   denominator product needs its own ≤ C4 check; gcd inputs during add/sub
   are the C4-scale unreduced fraction, not ≤ C3; all simultaneous
   temporaries are accounted with a ≈ 192 KiB logical peak (§4, §5.1), and
   the maximal rational add+reduce is now correctly priced at ≈ 4.6×10^7
   credits, above C5 (§5).
4. Cost table now uses `ceil` and a 1-credit minimum, adds rows for shifts,
   linear scans, dependency-graph node visits and cache hits, and no longer
   claims universal CPython upper bounds — the overcharge framing is an
   unproven estimate; deterministic abstract credits are separated from
   actual RSS and time (§5, §5.1).
5. C7 restated as logical payload accounting over *all* retained exact
   values (stored bindings plus cache), not 16 MiB of Python RSS; the 64 B
   formula entry and the ~200 B observed-overhead estimate are separated —
   one is the accounting constant, the other an RSS remark (§3, §5, §5.1).
   Live temporaries, worklist and cache aggregation are bounded explicitly
   within evaluator scope (§5.1).
6. Lexer compatibility corrected: the existing 100-character lexer accepts
   exponents above 4,096 (`1e9999` lexes today and host-converts to `inf`),
   so C2 newly rejects some literals that lex today. The claims "no literal
   that lexes today is resource-rejected", "caps bind only adversarial", and
   "every ordinary 20-char float is ≤ ~70 bits" were removed; §8 margins and
   the compatibility statement were rewritten.
7. `5e-324` rounds to 2^-1074 (ratio ≈ 1.012) and is not equal to it (T10
   reworded). T3's ambiguous "fits i64?" branch and T11's impossible
   >600-digit *emission* case were fixed — the hex fallback is a diagnostic
   path, and C11 makes >600-digit emission unreachable. T13 (production
   default-cap wiring) and T14 (corpus integration) were added; injected
   small-limit unit tests alone cannot qualify enforcement per AGENTS.
8. The generic "2p+2 intermediate makes double rounding harmless" claim for
   f32 emission was removed — arbitrary exact decimals can lie arbitrarily
   close to a midpoint. Exact hexadecimal emission is now the proposed
   default (exact by construction for both f32 and f64, including through
   Zig's f128 `comptime_float` coercion), with the required verification —
   Zig spelling plus bit-pattern comparison through Zig's actual parse path —
   stated for both widths; shortest-decimal is demoted to an option needing
   its own verified search (§8).
9. The invented authorization prohibition on stress-running the compiler was
   removed; the document now records only the fact that no exhaustion probe
   was run, and leaves future stress runs to the maintainers (§9).
10. F1 updated from the nonfinite baseline: `x: f64 = 1e400` currently
    builds and prints `inf`; zero-division cases are already rejected
    (exit 6); global `INF :: math.exp(1000.0)` and `NAN :: math.sqrt(-1.0)`
    work today and sit outside the untyped-constant evaluator (§3, §12).

Final narrow consistency pass (same day, GLM-5.3) — the controller follow-up
found three remaining numerical contradictions; items 11–14 correct them in
place. The caps remain proposed and unqualified.

11. Rational-add carry unified at ≤ C4: the §4 preflight requires the
    numerator-sum bound max(cross-product bounds) + 1 ≤ C4, so every
    add/sub temporary and gcd input is ≤ C4 bits. The stale "C4+1" wording
    in the gcd row and §5.1 was removed (it described an unguarded carry
    the preflight never permits), and the rational-add peak was recounted
    as 4 × C3 + 4 × C4 bits ≈ 192 KiB logical (was miscounted ≈ 160 KiB).
    Gcd charges already used ≤ C4 inputs, 2 × (C4/64)², and are unchanged.
12. Signed bitwise and complement were unaccounted: the old bitwise row
    claimed the result cannot exceed the wider operand, false under
    sign-extension semantics (−1 ^ 1 = −2). Bit length is now defined as
    magnitude bit length (§4); bitwise `& | ^` preflights
    max(ba, bb) + 1 ≤ C3 and complement `~` preflights ba + 1 ≤ C3,
    verified by a bounded small-range arithmetic check in scratch Python —
    no compiler run, no exhaustion.
13. Exact→f32/f64 rounding no longer bypasses preflight or receives
    blanket linear pricing: each internal shift, division, multiplication,
    comparison and scan passes its own §4 preflight and §5 charge (§4, §5,
    §8). C5 is charged per evaluated constant initializer — `::` bindings,
    constants in ordinary variable initializers, and fitting/rounding
    contexts — not only `::` bindings; diagnostic and emission conversions
    are outside the initializer charge and remain bounded by §7 and C9/C11.
14. The unqualified "hand-written constants are ≤ ~390 bits" claim was
    removed; only the explicitly bounded ≤ 20-character float literal with
    |exponent| ≤ 99 example class has that size, and the general margin
    statement now defers to the C1+C2 worst case (~13,930 bits, ~9.4x)
    (§3, §8).

A full-document consistency re-read followed these edits: growth numbers,
cap cross-references, credit counts, memory-accounting statements, test IDs
and F1 references now agree with the corrected sections above. The final
pass repeated that re-read for the rational-add, bitwise, rounding and
margin statements; the document now uses one carry rule — the +1 carry is
always inside the C4 check — throughout.
