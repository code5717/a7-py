<task id="ses_f44deb3f3ffeomH3Mcv4Ce4Kmh" state="completed">
<task_result>
# A7 Type System Review — GLM-5.3, 2026-09-19 (read-only)

## What I read in full

`a7/types.py` (608), `a7/generics.py` (416), `a7/cast_classifier.py` (83), `a7/const_eval.py` (155), `a7/passes/type_checker.py` (3104), `a7/safety.py` (902), `a7/ast_preprocessor.py` (677), `a7/semantic_context.py` (411). In part: `a7/backends/zig.py` (binary/cast/index/slice/call/assignment/type emission, ~1355-2200), `a7/parser.py` (alias and type parsing), `a7/passes/semantic_validator.py` (grep + excerpt), `a7/stdlib/math.py`, `a7/compile.py` (pass order), `docs/SPEC.md` §A.2, `docs/plan/decisions.md`. Zig-side semantics verified against the official Zig 0.14.0 language reference (operators table, `@abs`), fetched read-only.

---

## Part 1 — Prior findings: verification status

**P1. Array `+` is 1-D only; rank-2 diagnostic reports two identical types — CONFIRMED, LOW.**
type_checker.py:1223-1235. For `a: [2][2]f64`, `b: [2][2]f64`, `a + b`: sizes match (2==2), element `[2]f64` equals `[2]f64`, but `_is_numeric_compatible(ArrayType)` is False (ArrayType never overrides `is_numeric`, types.py:48-50), so the error fires: `"add between [2][2]f64 and [2][2]f64"`. Expected: either element-wise support for nested numeric arrays or a diagnostic that names the actual reason ("nested arrays not supported"). Actual: identical types reported as incompatible. Still present, unchanged.

**P2. const_eval "fits the type" is effectively "fits i32" — CONFIRMED, LOW (consequence), MEDIUM (root cause).**
Chain: type_checker.py:1187-1188 types every integer literal `I32`; type_checker.py:1244-1249 types literal-literal arithmetic as left type (I32); compile.py runs type check (line 325-327) before the preprocessor (line 413-418); the preprocessor folds with `self.type_map.get(id(node))` (ast_preprocessor.py:621, 573). So every foldable integer node has type i32, and the u8/u16/u32/u64/usize layouts in const_eval.py:31-36 are unreachable (const_eval.py:38,47-56). No wrong folding results (out-of-i32 results stay unfolded), but e.g. `x: u64 = 4000000000 + 4000000000` is rejected earlier at the assignment check anyway (binary is typed i32, `I32.is_assignable_to(U64)` is False). Root defect is contextual literal typing (see N4), not const_eval itself.

**P3. `::` constant as array size makes the array unindexable (SAF-21) — CONFIRMED, HIGH.**
`N :: 3; arr: [N]i32` → the size node is an IDENTIFIER; `extract_int_value` (type_checker.py:380-384) only accepts INTEGER literal nodes, so `resolve_type_node` builds `ArrayType(size=None)` (type_checker.py:397-398, 413-415). Consequences: `arr[0]` — safety `_object_length` returns `type_.size` = None (safety.py:767-770), so `_prove_index` always errors "index bounds are not proven" (safety.py:732-739); array-literal init fails at `len(elements) != expected_type.size` → `3 != None` with "[None]i32" in the message (type_checker.py:2981-2988). The backend would actually have emitted valid Zig (`[N]i32` with file-scope `const N`, zig.py:2095); the rejection is purely front-end. Expected: const identifiers resolved to their literal values in array-size position.

**P4. char supports only ==/!= (LNG-02) — CONFIRMED, MEDIUM (language gap).**
Ordering: `_types_are_comparable` with `ordering=True` requires numeric (type_checker.py:3052-3053); `CHAR.is_numeric()` is False (types.py:89-94) → `'a' < 'b'` rejected. Arithmetic: `'a' + 1` rejected at type_checker.py:1236-1238. Cast: `'a' as u32` rejected at cast_classifier.py:46-47 (char not numeric). Equality works via `equals` (type_checker.py:3054). Still present.

**P5. Parameter/field/call values can never be an index regardless of guard (LNG-04) — CONFIRMED, HIGH.**
Two independent blockers:
- Type side: `_validate_index_bound` accepts only `usize`-typed expressions or non-negative integer literals (type_checker.py:1739-1749). An `i32`/`i64` index is rejected even inside `if i >= 0`.
- Safety side: parameters get facts from `_fact_from_type_node`, which returns an empty fact for non-pointer types (safety.py:644-649) — no interval at all; `_prove_index` needs a full `0 <= i < len` interval (safety.py:732-739); and `_facts_from_condition` only learns lower bounds from `>=`/`>` in the positive branch — an upper bound from `if i < 4` is never learned (safety.py:843-868). So even a guarded `usize` param cannot index: `fn f(a: [4]i32, i: usize) { if i < 4 { a[i] } }` → "index bounds are not proven". Expected: guard-derived range facts; actual: literal or exactly-proven intervals only.

**P6. `if c != 0` guard does not survive a cast on the divisor (LNG-12) — CONFIRMED, MEDIUM.**
`_cast_fact` returns the source fact (interval + nonzero) only when the source interval fits an integer target (safety.py:717-719); otherwise it returns `ValueFact()`, dropping `nonzero`. A guard-derived `!= 0` fact carries `nonzero=True` with interval None (safety.py:860-862, params have no interval per P5), so `x / (d as i32)` — even an identity cast — loses the proof and errors "divisor may be zero" (safety.py:724-730), while `x / d` passes. Casts to float targets always drop the fact (target not in `INTEGER_RANGES`). Still present.

**P7. math.abs on signed ints yields unsigned Zig result conflicting with signed A7 type (TYP-19) — CONFIRMED, HIGH.**
`_validate_math_call` requires only "numeric" for `abs` and returns `arg_types[0]` (type_checker.py:1489-1532). The backend emits bare `@abs(x)` (zig.py:1707-1713; stdlib/math.py:13). Zig reference (0.14.0, @abs): "The return type is always an unsigned integer of the same bit width as the operand if the operand is an integer." So `x: i32 = -5; y := math.abs(x)` types `y` as i32 but emits `const y: i32 = @abs(x);` → Zig build failure (expected i32, found u32). Float `math.abs(-5.0)` (the only exercised form, examples/018_modules.a7:11) is fine. Still present.

**P8. Generic receiver `ref $T` cannot read a field (MTH-7) — CONFIRMED, MEDIUM.**
`visit_field_access`: the ReferenceType branch handles only Struct and Union referents (type_checker.py:1784-1804); a `GenericParamType` referent falls through the `adr/val` check (1806-1813) and the Slice/Struct/Union/Enum branches to the generic else → `FIELD_ACCESS_ON_NON_STRUCT` (1847-1860). Note `ref Box($T)` works via `_resolve_generic_instance_struct` (1786-1789); only bare `$T` is broken. Still present.

**P9. Type alias of struct unresolvable (VIS-1) — CONFIRMED, MEDIUM.**
`_is_type_start()` accepts only primitive keyword tokens plus REF and GENERIC_TYPE — not IDENTIFIER (parser.py:1510-1518). So `Ctr :: Counter` fails the alias branch (parser.py:489) and parses as a constant with identifier value (parser.py:499-506). Type-side effect: using `Ctr` in type position looks up a CONSTANT symbol, which `_resolve_type_leaf` rejects with UNDEFINED_TYPE (type_checker.py:439-451), since name_resolution typed it via `visit_const_decl` as a StructType-valued constant. The alias machinery itself (`register_type_alias`, type_checker.py:198-232 → `resolve_type_node` → `_resolve_type_leaf` TYPE_IDENTIFIER → STRUCT symbol) would resolve a struct alias correctly if the parser produced it. Still present; fix is parser-side.

---

## Part 2 — New findings

**N1. Mixed-sign/width binary arithmetic and comparisons are accepted; result type is the left operand; no coercion is emitted — HIGH, confirmed code defect.**
type_checker.py:1236-1249: after only checking both sides are numeric, the result is `left_type` for integers (floats win if present); there is no requirement that one operand be assignable to the other. `_types_are_comparable` accepts any two numeric types for comparisons (type_checker.py:3049-3056). The backend emits `({left} {op} {right})` with no coercion (zig.py:1678-1679). Consequences, per Zig's operator table ("Invokes Peer Type Resolution"):
- `u: u32 = 1; i: i32 = -1; u > i` — A7 accepts; Zig peer resolution fails on mixed sign → build error.
- `a: i8 = 100; b: i64 = 200; c := a + b` — A7 types `c` as i8 (left); Zig computes the peer type i64 and then fails assigning i64 to the i8 binding (or, if the value were used directly, silently disagrees with A7's recorded type). With the safety overflow check disabled (see N10), nothing catches this.
Snippet: `fn main() { a: i8 = 100; b: i64 = 200; c := a + b; io.println("{}", c) }` — expected: rejection or a common-type rule; actual: accepted, typed i8, Zig build fails (mixed-width binding) — and for mixed sign, fails at the operator.

**N2. Compound `/=` and `%=` on signed integers or floats are accepted but lower to Zig `/=`/`%=` — HIGH, confirmed code defect (core instance of the "223 compound-assignment programs" family).**
Type check: `DIV_ASSIGN`/`MOD_ASSIGN` are arithmetic ops requiring only numeric operands (type_checker.py:864-894); `f: f64 = 1.5; f %= 2.0;` and `x: i32 = 7; x /= y;` both pass (safety only proves divisor≠0, safety.py:459-460). Backend: `_assign_op_to_zig` maps them to `/=` and `%=` (zig.py:2409-2422). Zig operator table: `/` — "Signed integer operands must be comptime-known and positive... use @divTrunc/@divFloor/@divExact instead"; `%` — "Signed or floating-point operands must be comptime-known and positive... use @rem or @mod instead." So every runtime signed or float `x /= y` / `x %= y` fails the Zig build. The binary forms are lowered correctly (`@divTrunc`, `@rem`, zig.py:1667,1669) — the compound forms were never converted. Unsigned `/=`/`%=` are fine. Verified against Zig 0.14.0 docs; the repo pins Zig 0.16.0 (assumed unchanged — flagged below).

**N3. SPEC A.2 "Array to slice (safe widening)" is not implemented anywhere — HIGH, confirmed SPEC/code defect.**
`ArrayType` never overrides `is_assignable_to` (types.py:149-169), so array→slice fails at every position: assignment/initializer (type_checker.py:2917), call arguments (type_checker.py:1418), return (semantic_context.py:373), if-expression branches (type_checker.py:2006). Generic inference alone handles the pair (type_checker.py:1631-1634), which makes the subsequent assignability check fail with a confusing error. `fn sum(s: []i32) ...; arr: [3]i32; sum(arr)` → ARGUMENT_TYPE_MISMATCH, and `s: []i32 = arr` → ASSIGNMENT_TYPE_MISMATCH. Zig itself coerces arrays to slices implicitly, so the backend would work; the rejection is purely the front end contradicting docs/SPEC.md:2076.

**N4. "Integer literals to any integer type if in range" applies only to initializers — MEDIUM, confirmed SPEC/code defect.**
The literal-range logic lives in `_is_initializer_assignable_to` (type_checker.py:2888-2917, ranges at 2946-2962) and is used for var/const/assignment/struct/union/match-pattern positions only. It is not used for:
- call arguments — `fn f(x: u8)` called as `f(200)` → ARGUMENT_TYPE_MISMATCH (type_checker.py:1418 uses raw `is_assignable_to`; `I32→U8` is False);
- returns — `fn f() u8 { return 200; }` → RETURN_TYPE_MISMATCH (semantic_context.py:373);
- if-expression branches — see N8.
No example in `examples/` defines unsigned-parameter functions (grep), so this is latent but directly contradicts docs/SPEC.md:2078.

**N5. Implicit int→float conversions allowed, contradicting SPEC A.2 — MEDIUM, confirmed defect (SPEC drift + Zig-reject family).**
types.py:137-138: any signed or unsigned int `is_assignable_to` any float. So `f: f32 = someU64;` is accepted silently (u64→f32 can lose 29 bits), and `math.min(u, 1.5)` returns f64 (type_checker.py:1519-1523). SPEC A.2 (docs/SPEC.md:2075) lists exactly three implicit conversions; this is a fourth. Zig rejects runtime int→float coercion, so these join the accepted-A7/Zig-rejected family. Related: `_integer_literal_fits_type` returns True for any integer literal with a float target regardless of representability (type_checker.py:2962) — `f: f32 = 16777217` accepted; Zig errors ("float type 'f32' cannot represent integer value"). LOW/MEDIUM sub-case.

**N6. Partial struct literals accepted; Zig requires all fields — MEDIUM, confirmed defect.**
`visit_struct_init` checks only that provided field names exist and types match; there is no missing-field check (type_checker.py:2780-2809), and none in semantic_validator (grep: no "missing field" logic; STRUCT_INIT visit at semantic_validator.py:467-472 only walks values). The backend emits only provided fields (zig.py:1938-1963). `struct Counter { value: i32, count: i32 }` + `c := Counter{value: 0}` → A7 accepts, Zig errors "missing struct field: count". Union init does enforce exactly one field (type_checker.py:2811-2821); structs enforce nothing.

**N7. Unary minus on unsigned accepted — LOW/MEDIUM, likely Zig-rejected (one inference flagged).**
`NEG` requires only numeric (type_checker.py:1283-1286); `u: u8 = 1; v := -u` types `v` as u8 and emits `(-u)`. Zig's negation is documented for "Integers, Floats" without an unsigned caveat in the operator table; I believe unsigned negation is a compile error in Zig but did not find the explicit sentence in the 0.14 reference — marked unchecked. Even if Zig accepted it, A7's result type (u8) is semantically wrong for `-u` under any wrapping interpretation.

**N8. if-expression requires exact type equality while match-expression widens — MEDIUM design inconsistency / wrong rejection.**
`visit_if_expr` errors unless `then_type.equals(else_type)` (type_checker.py:2006-2014); `visit_match_expr` unifies via mutual `is_assignable_to` (type_checker.py:2082-2099). So `x: i64 = 5; m := if c { 1 } else { x }` → IF_EXPR_TYPE_MISMATCH (i32 literal vs i64) while the equivalent match expression is accepted. This also violates SPEC A.2 claim 3 in the if-expr position. Expected: same literal/widening rules as match.

**N9. `FunctionType` breaks the equals/hash contract — LOW latent code defect.**
`equals` ignores `is_variadic`, `variadic_type`, and `generic_param_order` (types.py:249-265), but `__hash__` includes `generic_param_order` (types.py:277-278), and the dataclass-generated `__eq__` (from `@dataclass(frozen=True)`) compares all fields, disagreeing with `equals`. Two function types can be `equals()` with different hashes (dict lookups miss) or `==` but not `equals()` (variadic flag). Today FunctionType is not used as a dict key in the paths I read (the monomorphizer keys on name+args), so impact is latent, but any future caching keyed on FunctionType hits this.

**N10. Integer-overflow proof is disabled by an early `return`, with dead code after it — LOW (documented) but interacts with N1.**
`_prove_integer_overflow` returns immediately; lines safety.py:802-811 are unreachable (safety.py:796-811). The comment says this is intentional ("left for a dedicated follow-up"). Combined with N1's left-type rule (`i8 + i64` typed i8) nothing bounds arithmetic results; Zig debug builds will panic on overflow. As a standalone item it's a stated design decision; the interaction with N1 is the defect.

**N11. Shift by negative amount accepted → runtime panic — LOW/MEDIUM.**
`1 << -1` or `x << y` with negative y: no type check (type_checker.py:1268-1273 only requires integral), no safety obligation, and the backend emits `@intCast(-1)` into the shift-amount type (zig.py:1670-1677), which is a checked runtime panic in Debug/ReleaseSafe. Expected: compile-time rejection of negative literal shift amounts, or a safety obligation.

**N12. `GenericMonomorphizer` is dead code and its struct instantiation crashes — LOW latent.**
`instantiate_struct` reads `field.type` and constructs `StructField(name=..., type=...)` (generics.py:224-225); the dataclass field is `field_type` (types.py:281-288) → AttributeError/TypeError if ever called. The class is never imported outside generics.py (grep). Its name mangling `f"{name}__{'__'.join(str(t))}"` (generics.py:172-173, 218-219) also collides (`Pair(i32, i64)` → `"Pair(Pair(i32, i64)"`-style names with parens/commas in identifiers, and a user function already named `f__u8` collides with generic `f` at `u8`). Either delete or fix; today unused, so latent.

**N13. Type checker's nonnegative-fact machinery is dead — LOW.**
`_nonnegative_vars` is maintained (type_checker.py:61, 772-778, 921, 1911-1950) but its only consumer `_expression_is_known_nonnegative` (type_checker.py:1960-1967) has no callers; safety.py re-derives facts independently. Dead code duplicating safety's job, inviting divergence (it already diverges: safety handles `<= -1`, the checker handles `LE` with literal < 0 differently).

---

## Part 3 — Cast classifier and const_eval specific notes

- cast_classifier.py is internally consistent with safety's use: FORBIDDEN signed→unsigned without nonneg proof, unsigned→signed only when strictly wider (cast_classifier.py:55-69), float→int allowed by classification but gated by safety's literal-integral-float proof (safety.py:710-711, 819-826) — conservative and sound. Two asymmetries worth a design pass: (a) unsigned→signed at equal width can never be approved even with an upper-bound proof (no proof channel exists, unlike `source_nonnegative`); (b) int→float is EXPLICIT_NUMERIC with no representability consideration (mirrors N5).
- const_eval.py arithmetic itself is correct (truncating div/mod matches @divTrunc/@rem; shift bounds checked; float non-finite results fold deliberately, docstring lines 9-19). Its only defect is inherited: the type entry is always i32/f64 (P2).

## Part 4 — What I could not fully verify

- I did not run the compiler or any test (read-only constraint). All A7-side behavior is from code reading; all Zig-side rejections are from the Zig 0.14.0 official reference. The repo's toolchain is Zig 0.16.0 (AGENTS.md artifact names); I did not verify that `/=`/`%=` signed/float restrictions and `@abs` unsigned-return are unchanged in 0.16 (high confidence, unchecked).
- The "223 compound-assignment programs" figure is from the task prompt; I found nothing in the repo recording it. I verified representative instances instead (N2, N5, N6, N7).
- `x %= y` on unsigned ints is valid Zig and was not further checked against A7 semantics beyond typing.
- Multi-file struct-name collisions via `StructType.equals` comparing by name only (types.py:313-315) — I did not trace module_resolver scoping to confirm a reachable confusion; design question, not a confirmed defect.
- Whether `examples/` ever passes an array to a slice-typed function (N3's live-ness) — grep suggests no; N3 is latent but SPEC-mandated.
- The for-in-indexed index fact `IntegerInterval(0, None)` (safety.py:498) — I did not construct a case where user code indexes by the loop's own index variable; if such code exists it would always fail the bounds proof; flagged as probable wrong rejection, unverified end to end.
</task_result>
</task>