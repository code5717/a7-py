# Collections and stdlib needs

Scope: owning `string`, `List`, `Map`, `Table`, `Id`, deep equality/hashing,
and std modules `string`, `mem`, `collections` plus text/files/paths/time/
random/process APIs. Sources: `docs/SPEC.md` §3/§11, `docs/STATUS.md`,
`docs/plan/README.md` tracks 8a/8b, `docs/plan/memory.md` gates M1–M51.

## 1. Current A7 state

- `string` is a borrowed `{ptr: ref u8, len: usize}` view (`SPEC.md:325`).
  No owning string, no growable text type. Repeated concatenation is
  quadratic (memory.md §9 known gap).
- Slice of string is `[]char`. Slices are freely stored/returned today;
  M13 would make them temporary read-only views. String helpers
  (`str_len`, `str_compare`, `str_find`, ...) exist only as planned API
  shape (`SPEC.md:1690+`), not implemented.
- No `List`, `Map`, `Table`, `Id`, `Option`/`Result` lookup types.
  `a7/stdlib/` has only `io` (print/println/eprintln) and `math`
  (sqrt/abs/floor/ceil/sin/cos/tan/log/exp/min/max). `std/string`,
  `std/mem`, `std/collections` are named in SPEC §10.3 as planned only.
- I/O helpers panic on failure. Recoverable I/O is track 7b work;
  collection lookup results are gate M33.
- Deep equality/hashing of owning values is an open gap (memory.md §9)
  that `Map` needs before phase C1.

## 2. What others provide

- Zig std: `ArrayList` (unmanaged + managed forms), `StringHashMap` /
  `AutoHashMap` / `HashMap` with explicit allocator + wyhash/Fxhash,
  `std.mem` (copy/set/compare/split/indexOf/replace), `std.fs`
  (files/paths), `std.time`, `std.Random` (xoshiro/SplitMix),
  `std.process` (args/env). No GC; caller threads allocator through all.
- Odin core: `dynamic` arrays + `map[K]V` as builtins, `strings.Builder`
  for growable text, `slice`, `os`, `time`, `rand`, `filepath`, `fmt`.
  Builtin map keeps the common case small; no hash choice exposed.
- Go: `string` immutable + `strings.Builder`, slice/map builtins with
  reference semantics, `bytes`, `os`, `path/filepath`, `time`, `math/rand`.
  GC hides ownership; not a model to copy, but the API breadth is the bar.
- Rust std: `String` (owning, UTF-8) vs `&str` (borrowed), `Vec<T>`,
  `HashMap` (SwissTable + RandomState), `Hash`/`Eq` derive traits,
  `std::fs`/`std::path`/`std::time`/`std::process`. Closest ownership
  analog: own/borrow split plus derived equality/hashing.

Lesson for A7: split owning vs borrowed (`String` vs `string` view,
like Rust), ship one default hash (like Odin/Go), keep allocator
implicit via extents (unlike Zig's explicit allocator argument).

## 3. Minimal API proposal (A7 spellings)

```
String :: struct { ptr: ref u8, len: usize, cap: usize }  // owning, byte buffer
s := String::from("lit")   // copy literal into owned storage
s.push(c: char); s.push_str(t: string)
t := s.borrow()            // string view, M13 rules apply
s.clear(); s.len(); s.is_empty()
```
`List(T)`: `new`, `push`, `pop() Option(T)`, `get(i) Option(T)`,
`set(i, v)`, `len`, `clear`, `reserve`, `remove(i)` (swap or shift,
documented). Index `l[i]` keeps proof-or-reject (M39); `get` is the
checked spelling.
`Map(K, V)`: `new`, `get(k) Option(V)` (copy, M33), `put(k, v)`,
`remove(k) bool`, `contains(k) bool`, `len`. Place-expression update
`m[k] = f(m[k])` accepted per memory.md row 24.
`Table(T)` + `Id(T)`: `add(v) Id(T)`, `get(id) Option(T)`,
`remove(id) bool`, generation-tagged 64-bit id (M5/M42).
`str::` fns: `len, compare, find, contains, starts_with, ends_with,
split_first, to_owned`. `mem::` fns: `copy, move, set, zero, compare,
equal`. `collections` re-exports List/Map/Table/Id.
Equality/hashing: derive `Eq` + `Hash` on structs of comparable
fields; `==` on owning types is deep compare; Map uses derived
hash with one fixed default (Fx-style, seeded per process).
stdlib: `io.read_line() Result(String)`, `fs.read_file(path)
Result(String)`, `fs.write_file`, `path.join/base/ext`,
`time.now/millis/sleep`, `rand.seed/next/range/shuffle`,
`process.args/exit/env`. All fallible fns return `Result`, never panic.

## 4. Ordering and dependencies

1. `Option` + payload matching first (track 7a). `get`/`pop` have no
   spelling without it. M33 (optional-copy lookup) depends on this.
2. Owning `String` + `mem::*` next. Unlocks `fs.read_file` and error
   messages. Needs extent/ownership decision for growth failure (M2:
   `try_push` vs stop).
3. `List(T)` next. Needs M1 (positions are shift-sensitive `usize`),
   M13 (no stored slices into it), M39 (index validity). Feeds memory
   phase C1.
4. Deep equality + default hash next. Blocks `Map` (memory.md §9).
5. `Map(K, V)` then `Table(T)`/`Id(T)` (M5 generations, M42 64-bit
   width/exhaustion, M49 union/defaults for empty slots).
6. stdlib files/paths/time/random/process last (track 8b), after 7b
   recoverable errors. Each fallible op gets a real-failure test.

M1/M5/M13/M33 are preconditions, not parallel work. Track 8a feeds
phase C1; track 8b needs 6a + 7b (`plan/README.md:365+`).

## 5. Test plan per type

- `String`: round-trip literal/owned/borrow; push_str growth exactness;
  OOM path per M2; quadratic-concat benchmark retired by Builder test.
- `List`: push/pop/get/set bounds; `remove` shift semantics with held
  positions (M1 rejection or documented invalidation); 10N loop memory
  flatness; Debug + ReleaseFast agreement.
- `Map`: get-missing returns none; put/remove round-trip; deep-key
  equality (two equal but distinct Strings hit same slot); hash
  determinism across two compiles (M40); wrong-type id use rejected.
- `Table`/`Id`: stale-id lookup returns none after reuse (M5);
  generation exhaustion diagnostic (M42); removal then add reuses slot
  with bumped generation.
- eq/hash: derived impl on nested owning struct; `==` agrees between
  const-fold and runtime; fuzz keys for collision behavior.
- stdlib: read missing file returns err (not panic); write/read
  round-trip through temp dir; path join on Linux separators; sleep
  bounds; seeded rand reproducibility; args echo program.
- Gate rule: collection tests run natively in Debug and ReleaseFast
  with Zig debug-allocator leak checks (memory.md §8); rejection
  cases are compile-only and labeled.
