# Global constants and declaration order

Research date: 2026-09-20. The user subsequently selected development of exact-fit
untyped constants, recorded in L47. Detailed P-TYP semantics remain pending
approval. This report changes no compiler behavior.

Resolve declaration order and numeric constant conversion as separate decisions.
A7 currently resolves `RATE :: 2.0` to `f64` when it visits the declaration. Its
acceptance of a forward use in an `i32` binding comes from an unresolved type.
Other languages show that rejecting this exact constant assignment is not the
only coherent rule.

## Current A7 evidence

- `a7/passes/name_resolution.py:342-350` registers constants with `UNKNOWN`.
- `a7/passes/type_checker.py:181-193` checks declarations, including function
  bodies, in source order after registering types and function signatures.
- `a7/passes/type_checker.py:642-667` checks a constant initializer and stores its
  inferred type. `visit_literal` at lines 1203-1208 defaults floats to `f64`.
- `visit_identifier` at lines 1219-1227 returns the stored symbol type.
- `a7/types.py:113-145` rejects assigning an `f64` value to `i32`.
  `UnknownType.is_assignable_to` at lines 538-540 accepts every destination.
- `a7/passes/type_checker.py:2990-3049` gives literal AST nodes some contextual
  numeric conversion rules. Those rules do not establish untyped named constants.
- `docs/SPEC.md:2070-2084` documents integer-literal destination fitting and
  numeric widening. It does not define an untyped named numeric constant model.

These observations explain the order-dependent behavior in
[P-TYP](../packets/P-TYP-forward-globals.md). They do not make the current behavior
a deliberate compile-time constant conversion rule. All constants are not `f64`.
The initializer determines the inferred type.

## Comparison

| Language | Observed or documented behavior | Evidence strength |
| --- | --- | --- |
| Zig 0.16.0 | A constant `2.0` can initialize `i32` before or after its declaration. `2.5` cannot. Even an explicitly typed `const RATE: f64 = 2.0` passes this compile-time conversion. An ordinary `f64` function parameter cannot be returned as `i32` implicitly. | Local compile probes and official reference |
| Odin | Numeric constants can convert when the destination represents the value without precision loss. The overview gives `x: int = 1.0` and describes named untyped constants. | Official documentation only |
| Go | An untyped constant can initialize a destination that represents its value. The specification lists `42.0` as representable by `byte`, and `1.1` as not representable by `int`. | Official documentation only |
| Rust | Constant items have declared types. Assigning `const RATE: f64 = 2.0` to `i32` fails with E0308. | Local compile probe and official reference |

Sources read on the research date:

- [Zig 0.16.0 reference](https://ziglang.org/documentation/0.16.0/).
- [Odin numbers](https://odin-lang.org/docs/overview/#numbers) and
  [untyped types](https://odin-lang.org/docs/overview/#untyped-types).
- [Go representability](https://go.dev/ref/spec#Representability) and
  [assignability](https://go.dev/ref/spec#Assignability).
- [Rust constant items](https://doc.rust-lang.org/reference/items/constant-items.html).

Go permits rounding for representable floating-point destinations. Do not read
its rules as requiring exact binary representation for every decimal literal.
Zig's typed compile-time result also means that its rule cannot be summarized as
only untyped constants accepting this conversion.

## Local evidence and limits

[The preserved JSON](global-constants-evidence.json) contains eight source cases,
exit codes and compiler diagnostics. It is copied unchanged from
`tmp/a7-constant-comparison-07nq04m0/results.json`.

Version commands run during documentation:

```text
$ zig version
0.16.0
$ rustc --version
rustc 1.98.1 (48a229cea 2026-09-01)
```

These are compile probes, not execution tests or a full numeric conformance suite.
The JSON does not preserve complete compiler command lines. Odin and Go were not
installed or tested for this research. Their rows report documented rules only.
The A7 observations come from source inspection and the existing packet's native
evidence. This report did not rerun the A7 release gate.

## Research recommendation and subsequent decision

Make global type resolution independent of declaration order. Before approving
P-TYP's specific rejection rule, show the user a separate proposal for untyped
numeric constants with checked destination fitting and concrete runtime types.
That proposal would be a new A7 rule, not preservation of its current checker.

For example, the alternative would accept `RATE :: 2.0` in an `i32` destination
in both declaration orders, while rejecting `RATE :: 2.5` there. It must also
specify overflow, explicitly typed constants, constant expressions, floating-point
rounding and the default type when a value becomes a runtime variable. Do not
infer those choices from the phrase "like Zig" or "like Odin".

The archived strict P-TYP option instead preserves current resolved numeric types and
rejects both orders. Either design must fix unresolved names, dependency cycles
and string formatting without changing runtime initialization order by accident.
Research recommendations are not approval to implement either option.

The user selected "Develop exact-fit untyped constants, like Odin". The
[revised packet](../packets/P-TYP-forward-globals.md) develops that direction.
The selection does not approve implementation or all proposed arithmetic rules.
