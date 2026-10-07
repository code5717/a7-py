# 13 — Comptime, Reflection, and Macros for A7

Scope: compile-time execution, `@typeInfo`-style introspection, macro/mixin code
generation, and what each unblocks: serialization, generic algorithms, test framework.

## 1. What A7 has today

- Literal-only folding. `a7/const_eval.py:93` folds numeric binary ops on two
  literals; `fold_unary` handles `-x` only. Anything with identifiers, calls,
  or control flow returns `None` and stays unfolded.
- Exact rational layer. `a7/exact_constants.py:81` evaluates `+ - * / %` over
  `Fraction` pairs with per-op f64 shadows; no calls, no branches, no loops.
  Cache is by declaration identity; the module never follows calls.
- No comptime surface. No `comptime` block, no `const fn`, no `@typeInfo`,
  no `@type_name`, no `static assert`, no macro/mixin syntax. Builtins doc
  lists `@type_id`/`@type_name` as unavailable with no reflection interface.
- Lowering already leans on Zig comptime. Generic fns emit
  `comptime T: type` params; generic structs emit comptime fns returning
  structs. A7 gets monomorphization free but exposes none of it to users.

Verdict on today: constant folding is a correctness guard (f64 overflow must
fold before Zig sees `comptime_float`/f128), not a metaprogramming story.

## 2. How others do it

- Zig comptime: one mechanism for generics, reflection, and codegen. Any
  `comptime` param, block, or var runs normal Zig at compile time. Types are
  values (`comptime T: type`). `@typeInfo(T)` returns a tagged union
  (struct/enum/union/fn/int/pointer fields); `@Type(info)` builds a type back;
  `inline for` unrolls field loops; `@field(x, name)` indexes by comptime
  string; `@compileError` rejects bad instantiations. Limits: branch quota
  (~1000, raisable), no syscalls, no string-to-code eval, no host detection.
- D CTFE: any ordinary function runs at compile time when args are known —
  no marker. Same source serves both phases (`ctRegex` pattern). Interpreter
  covers a large subset minus asm, raw pointers, syscalls. Non-constant args
  fall back to runtime silently.
- Nim macros: full AST transform in Nim itself (`macro`, `static` blocks,
  `quote do:`). Most powerful, most complex: hygiene, two-phase debugging,
  slow builds. Templates cover the easy 80%.
- Odin `when`: deliberately no CTE. `when cond` is a compile-time branch on
  a constant; `size_of`/`typeid`/`intrinsics` answer fixed queries. Lookup
  tables must be hand-written or generated offline. Simple, predictable, weak.
- Rust `const fn`: opt-in marker, allowlist grows slowly (traits still
  restricted). Safe and boring: no AST access, no type construction. Proc
  macros are the escape hatch — separate crates, token-stream in/out.

Lesson: Zig's point (types as values + field iteration + type construction)
covers serialization and generic algorithms with one small surface. Nim-style
AST macros are not needed to get there; Odin's `when` alone is not enough.

## 3. What each feature unblocks

- Serialization (`toJson`/`fromJson` without hand-written per-type code):
  needs struct field list + field access by name + per-field type dispatch.
  Zig sketch: `inline for (@typeInfo(T).@"struct".fields)`. Nothing else
  suffices; generics alone still need one impl per shape.
- Generic algorithms (`sum`, `map`, `sorted`, `contains` over any container):
  needs capability query ("has `len`?", "element type?") plus constrained
  generics (`04-generics.md` gaps 2–4). Reflection answers the query;
  `where` clauses enforce it with a readable error.
- Language-level test framework (`test "name" { ... }`, runner, filters):
  needs comptime collection of test blocks plus string/bool comptime values.
  Without comptime, tests are a build-script convention, not a language item.

## 4. Concrete proposal for A7

Keep it Zig-shaped, A7-spelled. Three layers, each gated separately.

```
const N :: 2 + 3 * 4              // comptime-known const; folds in A7 today
comptime { assert(N == 14) }       // phase 1: comptime block + static assert

fn makeArray($N: usize) -> [$N]u8  // phase 1: value params ride on comptime
  where $N > 0                     // reuses where-clause work from 04-generics

fn toJson($T)(x: $T) -> string      // phase 2: reflection
  where Struct($T) {
  var out := "{"
  comptime for f in fields($T) {    // inline/unrolled loop over field metadata
    out += f.name + ": " + toJson(field(x, f.name))
  }
  return out + "}"
}

test "round trip" {                 // phase 3: sugar over comptime collection
  assert(toJson(Point{x: 1, y: 2}) == "{\"x\": 1, \"y\": 2}")
}
```

Builtins (minimal set, all comptime-only):

| Builtin | Meaning | Notes |
|---|---|---|
| `comptime { }` block | run at compile time | Zig parity; quota-capped |
| `fields($T)` | field name/type list | struct/enum/union only |
| `field(x, name)` | value by comptime name | Zig `@field` parity |
| `typeName($T)` | name string | diagnostics, test labels |
| `compiles(expr)` | bool probe | D `__traits(compiles)` parity; powers `where` |
| `compileError(msg)` | fail build with message | constraint diagnostics |

No AST-input macros in this proposal. `comptime for` + `fields` + `field`
generate code from types; that covers serialization and containers. Anything
needing new syntax stays a language change with a normal RFC.

## 5. Dependency ordering

1. `comptime` values + blocks + `static assert` (needs: const-eval of calls
   and branches — extend `const_eval.py`/`exact_constants.py` or add a small
   tree-walk interpreter with step quota; no type work).
2. Value params `$N` (needs step 1; rides on `04-generics.md` proposal 2).
3. `where` predicates over `compiles(...)` (needs step 1; joint with
   `04-generics.md` proposal 3).
4. `fields`/`field`/`typeName`/`compiles`/`compileError` (needs 1–3; checker
   exposes metadata it already has; backend lowers to Zig `@typeInfo` where
   possible instead of reimplementing).
5. `comptime for` unrolling (needs 4; desugar to repeated instantiation).
6. `test` blocks + runner (needs 1, 5; collect + filter + report).

Steps 1–3 are usable without 4–6. Do not start 4 before `$N` lands: array
sizes and field counts are both `usize` comptime values and share machinery.

## 6. Verdicts

| Sub-item | Verdict | Reason |
|---|---|---|
| `comptime` blocks/vars, eval branch quota | need now | unlocks `$N`, `where`, tests; Zig backend expects it |
| `const`-evaluable calls + branches (mini-CTFE) | need now | same-source both phases (D lesson); quota stops hangs |
| `fields` / `field` / `typeName` introspection | need now | serialization is impossible without it; small surface |
| `compiles` probe + `compileError` | need now | turns duck-typing failures into readable errors |
| `comptime for` field iteration | need now | the loop form of the above; desugars cheaply |
| Value params `$N: usize` | need now | joint with generics report; array sizes need it |
| `test` blocks + runner + `assert` | later | high value but needs steps 1–5; script it until then |
| Type construction (`@Type` inverse) | later | useful (nullable wrappers, tuples) but not blocking |
| String mixins / AST macros (Nim-style) | never | power/cost ratio is wrong; `comptime for` covers the cases |
| Proc-macro crates / plugin system | never | build-complexity tax; revisit only if 4–5 prove insufficient |

Total new syntax if all "need now" lands: `comptime` block, `comptime for`,
five builtins, `$N` params. Everything else is library code.
