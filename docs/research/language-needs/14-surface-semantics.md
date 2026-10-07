# 14 — Surface semantics: format, capacity, maps, overloading, iteration

Scope: string interpolation + format grammar, dynamic-array capacity model,
map literal syntax, operator-overloading stance, for-in over user types.
Sister doc `03-collections-stdlib.md` owns List/Map API; this doc owns syntax.

## 1. Current A7 state (with locations)

- Print: `a7/stdlib/io.py:10-24` registers `print`/`println`/`eprintln`
  (canonical `std.io.*`, no `printf` entry — `grep printf a7/` is empty).
  Backend `a7/backends/zig.py:168-204` emits `__a7_stdout_print` /
  `__a7_stderr_print` helpers; `zig.py:2470-2501` emits calls, appending
  `\n` for `println`/`eprintln`; `zig.py:2551-2583` converts each bare `{}`
  to a Zig placeholder, escaping stray braces to `{{`/`}}`.
  `zig.py:2521-2549` picks the spec per arg: `s` (string), `c` (char),
  `` (numbers/bool), `any` fallback.
- There is no interpolation syntax (`$"..."`, f-strings) anywhere in the
  tokenizer/parser. `SPEC.md:717-721` shows `printf("[{}] = {}\n", ...)`
  and `SPEC.md:1723` lists `printf :: fn(fmt: string, args: ..)`, but
  `SPEC.md:943-962` marks variadic runtime lowering as not implemented.
  Effective rule today: first arg is a comptime-known format string.
- for-in: `a7/parser.py:1145-1187` parses `for v in it` (`FOR_IN`) and
  `for i, v in it` (`FOR_IN_INDEXED`); scopes in
  `a7/passes/name_resolution.py:469-482`; types in
  `a7/passes/type_checker.py:1178-1226` — iterable must be array, slice,
  or `string` (element `char`), index var is `usize`, else
  `REQUIRES_ARRAY_OR_SLICE`. Backend `a7/backends/zig.py:1079-1151`
  lowers to Zig `for (it) |v|` / `for (it, 0..) |v, i|`.
- No dynamic array, map, range-iterable, or overloadable operator exists.
  `string` is a borrowed `{ptr, len}` view (`SPEC.md:325`); slices are
  `[]T`; `..` builds slices/patterns, not for-in ranges, so
  `for i in 0..10` is rejected today. `docs/plan/decisions.md` has no
  overloading/interpolation decision recorded.

## 2. What others do

| Item | Zig | Odin | Rust | Go | Python |
|---|---|---|---|---|---|
| Format | comptime `std.fmt`: `{s} {d} {any} {x} {e:.3}`, no interpolation | `fmt.printf` with `%v %d %s` verbs, no interpolation | `format!`: `"{} {x:.2} {name}"`, full grammar: `[[fill]align][sign][#][0][w][.prec][type]`, named args | `fmt.Printf`: `%v %d %s %T` + flags/width/precision | f-strings + `str.format` mini-language, same grammar family as Rust |
| Growth | `ArrayList`: explicit allocator, `len`/`capacity`, `ensureTotalCapacity`, doubling-ish | builtin `dynamic` array: `len`/`cap`, `append`, growth runtime-managed | `Vec`: `len`/`capacity`, amortized doubling, `reserve`/`reserve_exact`/`shrink_to_fit` | slice `len`/`cap`, `append` doubling-ish (shrinks toward 1.25x) | `list`: over-allocated growth (~1.125x), no cap exposed |
| Map lit | none (init calls) | `map[K]V{key = value}` | `HashMap::from([(k,v)])`, `map!` macro (not std) | `map[K]V{k: v}` | `{k: v}` |
| Overload | none | none (plain procs) | opt-in via `Add`/`Index`/etc. traits | none | dunders (`__add__`, `__iter__`) |
| for-in | `for (slice) |v|`, `0..n` multi-capture | `for x in coll`, `for i in 0..<10`, builtin map/array/string | `IntoIterator` protocol; `for x in coll` desugars to `into_iter/next` | `range` over slice/map/chan/int (1.22+) | `__iter__`/`__next__` protocol |

Lesson: every non-GC language here refuses interpolation and overloading
except via explicit traits; ranges/iteration start as a small builtin set
(array/slice/int-range/map) and only Rust/Python generalize to a protocol.

## 3. Proposals (A7 spellings)

```a7
io.println("Hello, {}!", name)       // current: bare {} only, comptime fmt
io.println("Hex {x} fixed {d:.2}", n, x)  // proposed passthrough subset
s := "x={x} y={y}"                   // REJECTED: no $"..." interpolation
l := List(i32)::new()
l.reserve(64)                        // len == 0, cap >= 64; len <= cap invariant
l.push(1)                            // doubling 0->4->8...; may move storage
m := Map(string, i32){}              // empty; no literal until Map ships
m.put("a", 1)
c := a + b                           // numeric/fixed-array only; no overloads
for i in 0..n { }                    // proposed: half-open int range
for v in list.items() { }            // proposed view adapter, not protocol
```

- Format: freeze today (`{}` + `{{`/`}}` escape, comptime string) as v1.
  Later add a passthrough subset (`{s} {d} {c} {x} {e} {any}`,
  optional `.N` precision) validated against Zig `std.fmt`; never accept
  a runtime-computed format string.
- Interpolation: refuse `$"..."`/f-strings. They duplicate the format
  path, complicate the ASCII-only lexer, and hide allocations.
- Capacity: decide before `List` lands — `{ptr, len: usize, cap: usize}`,
  `len <= cap` invariant, `reserve` exact, `push` doubles from 4,
  growth failure follows the M2 `try_push`-vs-stop decision, and any
  reallocation invalidates stored slices (feeds M13/M39).
- Map literal: none until `Map` exists; then `Map(K,V){k: v}` constructor
  form, not a new bracket syntax (avoids array-literal ambiguity).
- Overloading: refuse for v1. Keep `+`/`==`/`[]` builtin-only; custom
  types get named functions. Revisit only via generic-constraint traits,
  after generics specialization completes (STATUS priority 5).
- Iteration: add `for i in 0..n` (half-open, `usize`) plus explicit
  adapters (`list.items()`, `map.keys()`); no user-type protocol until
  traits exist. A future protocol should be one hook
  (e.g. `iter() -> {next() Option(T)}`), not dunder sprawl.

## 4. Verdicts

| Item | Verdict | Reason |
|---|---|---|
| Freeze current `{}` format behavior | need now | Already shipped; document comptime-string + escape rule |
| Format mini-language subset | later | Needs collections + real programs first; passthrough to Zig |
| String interpolation `$"..."` | never | Duplicates format path; hides allocations (explicit-over-implicit) |
| Capacity model (len/cap/growth/invalidation) | need now | Spec decision blocks `List`; small text, no impl required |
| Map literal syntax | later | No `Map` type yet; constructor form suffices when it lands |
| Operator overloading | never (v1) | Conflicts with simplicity stance; revisit via traits only |
| Int range `for i in 0..n` + adapters | need now/small | Closes obvious for-in gap without a protocol |
| General iterator protocol | later | Needs generics + `Option` + traits; premature today |
