# 04 — Generics Completion

Scope: generic enums/unions, value params (`$N`), where-clause constraints,
user specialization, stdlib generic functions as values, silent first-wins inference.

## 1. Current mechanics (file:line)

- Types: `GenericParamType` (`a7/types.py:427`), `GenericInstanceType` (`a7/types.py:453`),
  `TypeSet` (`a7/types.py:482`), `FunctionType.generic_param_order` (`a7/types.py:256`).
- Constraint resolution: `resolve_generic_constraint` (`a7/types.py:956`) handles only
  predefined sets (`Numeric`, `Integer`, `SignedInt`, `UnsignedInt`, `Float`) and inline
  `@type_set(...)` of primitives (`a7/types.py:989`). Local alias unwrap in
  `TypeCheckingPass._resolve_generic_constraint_node` (`a7/passes/type_checker.py:397`).
- Declared-form constraints (`Name($T: Numeric) :: fn...`) stored per-function
  (`type_checker.py:346,677,733`) and per-struct (`type_checker.py:435`).
  Inline `$T` in fn bodies resolves against `_generic_constraints` (`type_checker.py:638`).
- Call-site inference: `_infer_generic_types` (`type_checker.py:2013`) walks
  param/arg pairs on an explicit stack; handles `ref`, pointer, array/slice,
  nested `FunctionType`, `GenericInstanceType` (`type_checker.py:2041-2063`).
  Substitution: `_substitute_generic` (`type_checker.py:2067`); constraint check:
  `_check_generic_constraints` (`type_checker.py:1964`); call wiring (`type_checker.py:1777`).
- Backend: generic fns emit Zig `comptime T: type` params (`a7/backends/zig.py:562`);
  generic structs emit comptime fn returning struct (`zig.py:650`); call args from
  `node.generic_mapping` in `generic_param_order` (`zig.py:1891`).
- `where` is lexed (`a7/tokens.py:90`) but no grammar rule consumes it
  (SPEC §2.4, §6.1: planned, not current). No value-param, specialization, or
  generic-enum/union support in the checker.

## 2. Gaps

1. Generic enums/unions: SPEC §7.2 shows `Option`/`Result` with `$T` fields, but
   `register_enum_type` (`type_checker.py:447`) and `register_union_type`
   (`type_checker.py:471`) drop `node.generic_params` and build plain
   `EnumType`/`UnionType`. No `GenericInstanceType` path for enum/union init or
   match exhaustiveness over instantiations. Pure implementation gap.
2. Value params (`$N`): no lexer/parser/type form. SPEC §9.1 `Tensor($T, $N: u8)`
   is design-target only. Needs syntax + const-eval + monomorphization keying.
   Gate: user decision on spelling (`$N` vs `comptime N: usize`) and allowed
   kinds (ints only? bools? strings?).
3. Where-clauses: only single inline `: Set` per param exists. No multi-param,
   cross-param (`T == U`), member (`T: Addable with op +`), or negative bounds.
   Gate: user decision — minimal (conjunction of set memberships) vs full predicates.
4. User specialization: none. Comment at `type_checker.py:2028`: "no overload or
   specialization ranking". All specialization is automatic call-site monomorphization.
   Gate: user decision — allow explicit `fn f(i32)` alongside `fn f($T)`, and
   priority rule (exact beats generic? ambiguity error?).
5. Generic fns as values: passing `identity` (uninstantiated) as a `fn` arg has no
   binding site; inference only fires at direct calls (`type_checker.py:1778`).
   Partial machinery exists (nested `FunctionType` zip, `type_checker.py:2057`).
   Needs: explicit instantiation syntax (`identity(i32)`) usable as a value.
   Mostly implementation once syntax is gated.
6. Silent first-wins: `bind()` (`type_checker.py:2021`) keeps the first binding
   when a later arg disagrees and reports nothing; `_check_generic_constraints`
   only sees the winner. `f(a: $T, b: $T)` with `(i32, string)` silently picks
   one side, then arg-check may or may not fire downstream. Pure implementation:
   emit a conflict error naming both sites.

## 3. How others handle it

- Zig `comptime`: no constraints at all; duck-typing + `@compileError` inside body.
  Specialization is implicit per instantiation. Value params are just `comptime N: usize`.
  Lesson: A7 already lowers to this; constraints are a frontend-only check Zig never sees.
- Odin `where`: `where T: typeid, N: int` clauses with boolean comptime predicates
  (`size_of(T) == 8`), plus explicit specialization by overloading on concrete types.
  Closest model for A7's minimal where-clause.
- Rust traits: constraints are trait bounds (`T: Add + Copy`), checked at definition
  and use; specialization is unstable/restricted (coherence + overlap rules).
  Lesson: capability bounds subsume type-sets but need a trait/interface design A7 lacks.
- C++ concepts: `requires` clauses + `concept` definitions; partial/explicit
  specialization with partial-ordering rules, ambiguity = hard error.
  Lesson: take the ambiguity-is-error rule; skip partial ordering for now.

## 4. Proposals

| # | Proposal | Example | Gate vs impl |
|---|----------|---------|--------------|
| 1 | Generic enums/unions: store `generic_params` on `EnumType`/`UnionType`, monomorphize like structs | `Opt(i32){Some: 1}` | impl |
| 2 | Value params: `$N` binds `usize` const; part of instance key; array sizes may reference it | `Buf :: struct { data: [$N]u8 }` | gate (spelling, kinds) |
| 3 | Minimal where-clause: `where T: Numeric, U: Numeric` conjunction only; desugar to per-param sets | `fn add(a: $T, b: $T) $T where T: Numeric` | gate (minimal vs full) |
| 4 | Explicit specialization: concrete overload wins over generic; two generics overlapping = error | `fn f(x: i32)` beats `fn f(x: $T)` | gate (priority rule) |
| 5 | Generic fn as value: require explicit type args when passing/storing (`f(i32)`), infer at let-binding with annotation | `apply(id(i32), 1)` | gate (syntax) + impl |
| 6 | Inference conflict: `bind()` records span; second disagreeing bind = error `conflicting types for $T: i32 vs string` | `f(a: $T, b: $T)` | impl |

Order: 6, 1 (no syntax changes), then 3-minimal, 5, 2, 4.
