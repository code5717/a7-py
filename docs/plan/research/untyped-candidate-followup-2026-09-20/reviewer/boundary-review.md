# Numeric boundary review

This review covers the copied candidate only. No production or candidate source was edited by the reviewer.

Required rational-to-IEEE controls include ties with both even and odd lower significands, a carry into the next exponent, both signs, half the minimum subnormal, the largest-subnormal/minimum-normal boundary, maximum finite, and overflow. Target encoding must come from rational rounding, not a host f64 intermediate. A bitcast of a bounded unsigned integer can prevent Zig comptime_float from rounding the decimal again.

For division, integer-category operands truncate toward zero. A floating-category operand preserves rational division. Nonterminating rationals such as 1.0 / 3.0 need the same direct target rounding as terminating rationals. The expression (1.0 / 3.0) * 3.0 == 1.0 must compare before fitting. Remainder is left minus trunc(left/right) times right, so its sign follows the dividend. Signed-zero division follows the signs of both operands; zero remainder follows the dividend.

Useful controls include -5 / 2 == -2, 5 / -2 == -2, -5 % 2 == -1, 5 % -2 == 1, -5.0 % 2 == -1.0, and -4.0 % 2.0 producing negative zero.

Fitting must run at default mutable and formatting destinations as well as explicit variable, parameter, return, and aggregate destinations already supported by the candidate. Pure exact comparisons do not require a float destination. Typed identifiers and call results must stay outside exact binding evaluation. Global math.exp and math.sqrt constants are important controls because later preprocessing may turn them into nonfinite literals.

The old candidate's explicit constant-declaration type check bypasses the shared initializer fitting helper. Check whether this route needs fitting when updating the candidate. This observation does not establish public syntax support for explicitly typed constants.
