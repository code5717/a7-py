# Stdlib proposal, 2026-10-04

Status: research and design only. Nothing here is approved. Every item
that changes A7 syntax or behavior needs a before/after packet and the
user's approval under AGENTS.md "Language change approval". No tracked
file was edited. No pytest or gate script was run.

Recommendation in one paragraph: build the stdlib as a hybrid. A small
set of typed hooks stays in the Python registry and lowers to Zig. All
other stdlib code ships as `.a7` files inside the wheel. The compiler
already resolves and runs A7-source `std/...` modules (probe D1 below).
Phase A lists eighteen modules that need no heap, including event
readers for JSON and YAML. Lists, maps, and
owning strings wait for the memory decision (L51, L57), because L42
makes a growable list a shared handle, which a plain A7 struct cannot
express.

Change during this session: the user wrote "add json and yaml parsers
into stdlib" on 2026-10-04. Sections 3.21-3.23 add `std/json`,
`std/yaml`, and a shared document tree. This reverses the roadmap B8
row "YAML/TOML NEVER" for YAML. Nothing was implemented in the
compiler; the request is recorded here as design, and it needs a
ledger entry and a roadmap edit that I did not make (tracked files).

Evidence labels: "V" = I ran a probe and saw the output. "R" = I read
the file. "M" = from memory, not checked this session. Probe sources
are in the session scratchpad under `scratchpad/stdlib/` (`cat/` and `cat2/` module
stubs, `ex/` the section 3 examples, `iso/` and `iso2/` isolation probes, `demo/` the runnable demo, `old/` first
rounds, `cat-results.txt`, `iso-results.txt`). The scratchpad is
session-local; the load-bearing probes are quoted in this file.

## 0. What the probes found

All runs used `uv run a7 --mode pipeline FILE` (add `--lib` for files
without `main`) and `uv run a7 run FILE`, Zig 0.16.0.

| ID | Finding | Ev |
| --- | --- | --- |
| D1 | An A7-source stdlib module resolves and runs today. A file at `<entry dir>/stdlib/std/strings.a7` loads through `strings :: import "std/strings"`, and its functions return typed values (`usize`, `bool`). The search path is `a7/compile.py:276-280`. | V |
| D2 | A nine-import demo (eight A7-source modules, 241 lines, plus `std/io`) ran natively: `13 passed, 1 failed` with one deliberate failure. Front-end time rose from 0.15-0.24 s (hello world) to 0.31-0.38 s. | V |
| D3 | The third search path is `Path(__file__).parent.parent / "stdlib"`, which is the repo root, outside the `a7` package. No such directory exists. `pyproject.toml` ships `include = ["a7*"]` only, so a wheel would not carry it. | R |
| D4 | Functions are namespaced per module; types are not. Two modules that each define `helper :: fn` ran correctly (printed `1 2`). Two modules that each define `P :: struct` exit 6 `Already defined: Struct 'P'`. A type from an imported module is used bare (`Tally{...}`); `coll.Pair(i32, i32)` exits 5 `Expected expression`. | V |
| D5 | Generic functions work in the `name($T) :: fn(x: $T)` form with `$T` at every use. Bare `T` in a signature exits 6 `Undefined type (Type 'T')`. Explicit type arguments at a call (`push(i32, s, 5)`) exit 6. | V |
| D6 | A generic function that builds or returns a generic type fails codegen. `wrap($T) :: fn(v: $T) Box($T) { ret Box($T){value: v} }` and the `Option($T)` equivalent exit 7 `Zig backend: generic type requires an explicit generic environment`. Taking `Box($T)`, `ref Box($T)`, `Option($T)`, `[]$T`, or `fn($T) bool` as a parameter exits 0. Returning a concrete `Option(usize)` from a generic function exits 0. | V |
| D7 | Index proofs hold for one bound on one identifier. Works: `while i < xs.len { xs[i] }`, a guarded parameter index, a guarded index into a field array (`s.items[n]` with `n` a parameter). Fails with exit 6 `Index not proven in bounds`: an index loaded from a struct field (`n := s.count; if n < 8 { items[n] }`), `xs[0]` under `if 0 < xs.len`, two slices under two guards (`while i < dst.len { if i < src.len { dst[i] = src[i] } }`), `if a and b` guards. | V |
| D8 | Slice bounds with runtime values are mostly unprovable: `xs[from..xs.len]` under `if from <= xs.len`, `xs[0..0]`, and `s[0..]` exit 6. `a[n..4]` on a fixed array under `if n <= 4` runs. | V |
| D9 | Strings are thin. Works: `for ch in s`, `s[i]` with a literal-bounded counter, printing, passing, storing in structs. Fails: `s.len` (exit 6), `string` to `[]u8` or `[]char` (exit 6), `cast(u8, ch)` and `cast(char, b)` (exit 6, "only primitive numeric casts"), `c >= 'A'` (exit 6), `s == "hello"` (a7 exits 0, Zig fails: `cannot compare strings with ==`). `case '0'..'9':` on a `char` runs. | V |
| D10 | No heap buffers. `new [16]u8` exits 6 (`expected 'scalar or struct allocation'`). `Node :: struct { next: ref Node }` exits 6 (`expected 'ref unknown type'`). `new Box` with a nil check, `ret b`, and `del b` runs. | V |
| D11 | A `string` payload cannot be matched: `case .some(name):` on `Option(string)` exits 6 and names M33/M49. `Option(string)` as a return type checks. | V |
| D12 | `match io.read_line(buf[0..16])` exits 6: the checker types the call as void and demands a format string. `r := io.println_ok("x")` compiles and runs. | V |
| D13 | Wrapping `u64` math, shifts by literals, xor, and `%` under a `while y != 0` or `if bound != 0` guard run. FNV-1a over `[3]u8` printed `4452171178779021548`. Narrowing `cast(u8, d)` under `if d < 10` and float-to-int casts exit 6. | V |
| D15 | A checked accessor written in A7 passes the prover and removes most D7 failures. `at(xs, i, fallback)` and `put(xs, i, v)` each hold one guard. `bytes.copy`, `bytes.eq`, and a two-cursor `reverse` written through them ran (`4 true`, `4 -1 true`). | V |
| D16 | An import alias cannot equal a function name in the imported module. `sort :: import "std/sort"` with `sort($T) :: fn` inside exits 6 `Already defined: Import alias 'sort'`. The alias `sorting` runs. | V |
| D17 | A JSON event reader written in A7 (140 lines, no heap, no recursion) runs today. For the bytes of `{"a":[12,true]}` it printed `object_start 0..1`, `key 2..3`, `array_start 5..6`, `number 6..8`, `true 9..13`, `array_end 13..14`, `object_end 14..15`. Source: `ex/stdlib/std/json.a7`. | V |
| D14 | Function-pointer parameters run (`min_by(xs, less)` with `Less :: fn(i32, i32) bool`). Methods (`c.inc()`), `for i in 0..3`, variadic lowering, and one-line `if c { ret S{...} }` do not (exit 6, 5, 6, 5). | V |

## 1. Scope

### What "general purpose" should mean for A7 v1

Proposed definition: a program in the L44 class (text scanning, syntax
trees, symbol tables, multi-file tools) and an ordinary command-line
tool can be written with the stdlib alone, with no Zig written by the
user and no manual memory calls (L19, L21).

Concretely, v1 covers: console and file I/O with recoverable errors,
text and bytes, number parsing and formatting, math, growable lists,
maps, sorting and searching, arguments, environment, exit codes, time,
seeded random numbers, JSON and YAML parsing, and a test helper. Sources: L36 ("useful
libraries"), roadmap sequence step 5 ("strings, collections and
practical input/file/path operations"), roadmap milestones "Usable
core" and "Standard library and native boundary".

Constraints from the ledger that shape every API:

- L17, L19, L21: no allocator parameters and no manual free in stdlib
  signatures. This rules out the Zig convention of passing an
  allocator to each call.
- L42: `b := a` on a growable list shares one list. Copies are explicit.
- L39: prefer compile-time proof; checked execution is allowed where
  proof is unavailable. A bounds-checked `get` fits this.
- L41: native code goes through Zig. Application code does not manage
  raw native pointers.
- L31: `import "io"` and `import "math"` are stdlib spellings.
- L48: stdout is buffered; stderr flushes per call.
- L4, L5: explicit integer widths; `+ - *` wrap.
- L38: stdlib workloads count against the 1.10x C limit.

### What stays out of v1

| Item | Source | Approval on disk |
| --- | --- | --- |
| Package registry | CLAUDE.md "Out of Scope", STATUS:225 | Yes (project rule) |
| Networking, TLS, HTTP | research 10 section 4, research 25 section 6 | None; research only |
| TOML, binary formats | roadmap B8 "NEVER", research 25 section 4 | None (`ledger-audit.md` row "Roadmap A6 ... B8 NEVER items, A8") |
| YAML anchors, aliases, tags, merge keys, multi-document streams | this proposal (3.22, decision U13) | None |
| Regex in the language; a regex library only "on a qualified use case" | roadmap B8, research 25 section 2 | None |
| Fresh crypto primitives | roadmap B8, research 25 section 3 | None |
| C++ interop | roadmap B8 | None |
| SIMD intrinsics, string interpolation, general overloading | roadmap A8 "Locked cuts" | None (PLAN.md P4-10; A8's "GC" cut contradicts L37) |
| Async syntax | roadmap A6 "never" | None (PLAN.md P4-10) |
| Calendar, time zones | research 16 section 7, research 25 section 5 | None |
| Tensors, concurrency | L36 (later tracks) | Yes |

JSON and YAML were out of v1 in the roadmap (B8: "JSON later.
YAML/TOML NEVER"). The user's 2026-10-04 message moves both in.

Seven of these rows rest on research files or this proposal only. `decisions.md:29-30`
says research recommendations are not approval. This proposal follows
them as working assumptions and lists them as decision U11.

## 2. Survey

Every claim in this section is from memory (M). None was checked
against source this session.

| Language | How the small core is organized | What fits A7 | What does not fit |
| --- | --- | --- | --- |
| Zig std | One `std` namespace; `mem`, `fmt`, `fs`, `process`, `time`, `Random`, `ArrayList`, hash maps, `testing`. Containers take an allocator. Generic containers are functions that return types. Format strings are checked at compile time. | Compile-time format checking (A7 already checks placeholder counts). `testing` as an ordinary module. Caller-buffer APIs (`bufPrint`). | Allocator parameters (L17, L19, L21). |
| Go | Flat package list: `fmt`, `strings`, `bytes`, `strconv`, `os`, `io`, `sort`, `time`, `math`, `errors`, `path/filepath`. Slices and maps are builtins with reference identity. Errors are returned values. | The package split and names. Reference identity for growable collections matches L42. `strings` and `bytes` as mirror modules. `strconv` separate from `fmt`. | Interfaces (`io.Reader`), closures in `sort.Slice`, garbage collector. |
| Odin core | `core:fmt`, `strings`, `slice`, `os`, `time`, `math`, `mem`, `strconv`, `unicode/utf8`. Dynamic arrays and maps are language builtins. An implicit `context` carries the allocator. Free functions, no methods. | Free-function style matches A7 today (no methods). Builtin dynamic array and map: the compiler knows the type, the library holds the helpers. `strings.Builder` for growable text. | The visible `context` and explicit `delete`. |
| Rust core/std | `core` has no allocation and no OS; `alloc` adds heap types; `std` adds the OS. `Option` and `Result` are in `core` and in the prelude. | The three-layer split maps onto the phases here: phase A is the "core" layer (no heap), phase B the "alloc" layer, and OS modules sit beside both. Prelude for `Option`/`Result`. | Traits, iterators with closures, lifetimes. |
| Hare | Small modules (`fmt`, `strings`, `bytes`, `os`, `fs`, `io`, `strconv`, `sort`, `time`). Errors are tagged unions matched by the caller. Many functions write into caller buffers. | Tagged-union errors matched explicitly are what A7 has today. Caller-buffer APIs let phase A ship before a memory model. | Manual `free`. |
| C3 | `std::core`, `std::io`, `std::collections`, with generic modules and optionals for errors. | Generic container modules. | Macros, temp allocator calls visible to the user. |

Ideas that survive A7's limits (no recursion, no closures, value
semantics, no methods):

1. Free functions grouped by module, first argument is the subject
   (`strings.len(s)`). Odin and Go show this scales.
2. Errors as tagged unions matched by the caller (Hare). A7 has this.
3. Function-pointer parameters replace closures for `sort_by` (D14).
4. Caller-buffer variants (`format_i64(buf, v)`) need no allocator.
5. The compiler owns growable collection types; the library owns the
   helpers (Odin, Go). L42 forces this for A7.
6. Iterative algorithms only: insertion sort, heap sort, or iterative
   merge sort instead of recursive quicksort; explicit stacks for tree
   walks.

## 3. Module catalog

Status words per signature:

- RUNS: real body, compiled and ran natively in the demo (D2).
- CHECKS: signature with a stub body passes `--mode pipeline --lib`.
  The body still has to be written or hooked.
- FAILS n: exits `n` today; the error follows.
- PLANNED: needs the named missing feature.

"Hook" means a typed registry entry lowered to a Zig helper (section
4). Zig helper names in the lowering lines are from memory of Zig std
and were not compiled against 0.16.0 (M).

Shared types used below. Today each file must declare them itself,
and a second declaration in any imported module exits 6 (D4):

```a7
Option :: union(tag) {
    some: $T,
    none: bool,
}
Result :: union(tag) {
    ok: $T,
    err: $E,
}
```

### 3.1 `std/io` (hook; exists)

Purpose: console input and output.

```a7
print    :: fn(fmt: string, args: ..)                        // RUNS (registry)
println  :: fn(fmt: string, args: ..)                        // RUNS (registry)
eprintln :: fn(fmt: string, args: ..)                        // RUNS (registry)
eprint   :: fn(fmt: string, args: ..)                        // PLANNED: new registry row
println_ok :: fn(fmt: string, args: ..) Result(usize, IoErr) // statement form RUNS; match FAILS 6 (D12)
read_line  :: fn(buf: []u8) Result(usize, IoErr)             // FAILS 6 (D12); PLAN.md P1-4 second-read bug
flush      :: fn() Result(usize, IoErr)                      // PLANNED: new registry row
format_into :: fn(buf: []u8, fmt: string, args: ..) Result(usize, IoErr) // PLANNED: new registry row
```

The `args: ..` spelling parses (`--mode ast` exit 0) and exits 6 at
check: "Variadic parameters are parsed for future support". The
registry handles these calls without a declared signature, so the
lines above describe the call shape and are not A7 source.

- Errors: `IoErr :: enum { WriteFailed, FlushFailed, ReadFailed }`
  (matches `__a7_IoErr`, `a7/backends/zig.py:270`).
- Allocation: none. `read_line` fills the caller's buffer.
- Lowering: the existing `__a7_stdout_print`, `__a7_stderr_print`,
  `__a7_stdout_print_ok`, `__a7_stdin_read_line` helpers.
- Stays a hook because A7 has no variadics and the format string is
  checked at compile time.

```a7
io :: import "std/io"
main :: fn() {
    buf: [8]u8 = [0, 0, 0, 0, 0, 0, 0, 0]
    match io.read_line(buf[0..8]) {
        case .ok(n): { io.println("read {} bytes", n) }
        case .err(e): { io.eprintln("no input") }
    }
}
```

Status: parses; FAILS 6 today (D12): `expected 'string', got '[]u8'
(io format argument)` and `expected 'tagged union', got 'void'`.

`format_into` writes formatted text into a caller buffer (Zig
`std.fmt.bufPrint`, M). It sits in `std/io` because it shares the
format-string checker path; there is no separate `std/fmt` module in
this proposal. `IoErr` gains a `NoSpace` tag for it.

### 3.2 `std/slices` (A7 source)

Purpose: checked element access and small generic slice helpers. This
module is what lets other stdlib code pass the index prover (D15).

```a7
at($T)       :: fn(xs: []$T, i: usize, fallback: $T) $T   // RUNS
put($T)      :: fn(xs: []$T, i: usize, v: $T) bool        // RUNS (through reverse)
swap($T)     :: fn(xs: []$T, i: usize, j: usize) bool     // RUNS (through reverse)
reverse($T)  :: fn(xs: []$T)                              // RUNS
contains($T) :: fn(xs: []$T, v: $T) bool                  // RUNS
count($T)    :: fn(xs: []$T, v: $T) usize                 // CHECKS (real body)
get($T)      :: fn(xs: []$T, i: usize) Option($T)         // FAILS 7 (D6)
```

- Errors: `at` returns the fallback when `i` is out of range. `put`
  and `swap` return false and change nothing. `get` is the `Option`
  form and waits for R3.
- Allocation: none. Lowering: ordinary A7. Each accessor is one
  compare; Zig can inline it (inference, not measured).

```a7
io :: import "std/io"
slices :: import "std/slices"
main :: fn() {
    xs: [4]i32 = [1, 2, 3, 4]
    slices.reverse(xs[0..4])
    io.println("{} {} {}", xs[0], slices.at(xs[0..4], 9, -1), slices.contains(xs[0..4], 3))
}
```

Status: RUNS, printed `4 -1 true`.

### 3.3 `std/option`, `std/result` (A7 source)

Purpose: the two shared unions and small helpers.

```a7
is_some($T)   :: fn(o: Option($T)) bool                    // CHECKS in isolation (iso/g5)
unwrap_or($T) :: fn(o: Option($T), fallback: $T) $T        // CHECKS in isolation (iso2)
is_ok($T, $E) :: fn(r: Result($T, $E)) bool                // CHECKS in isolation (iso2)
ok_or($T, $E) :: fn(r: Result($T, $E), fallback: $T) $T    // CHECKS in isolation (iso2)
some($T)      :: fn(v: $T) Option($T)                      // FAILS 7 (D6)
```

The stub file `cat/option.a7` exits 7 because of `some`. Each of the
other four exits 0 in a file of its own.

- Errors: none. Allocation: none. Lowering: ordinary A7.
- There is no `unwrap` that panics in this proposal; see decision U2.

```a7
port := unwrap_or(parse_port(text), 8080)
```

### 3.4 `std/strings` (A7 source over three hooks)

Purpose: read-only operations on `string` views.

```a7
len           :: fn(s: string) usize                // RUNS as an O(n) loop; hook makes it O(1)
eq            :: fn(a: string, b: string) bool      // CHECKS; body needs a hook (D9)
compare       :: fn(a: string, b: string) Order     // CHECKS; hook
starts_with   :: fn(s: string, prefix: string) bool // CHECKS; needs `byte_at` or a hook
ends_with     :: fn(s: string, suffix: string) bool // CHECKS
contains      :: fn(s: string, needle: string) bool // CHECKS
count_char    :: fn(s: string, needle: char) usize  // RUNS
index_of_char :: fn(s: string, needle: char) Option(usize) // see the last bullet
sub           :: fn(s: string, start: usize, end: usize) string  // CHECKS; hook (D8)
trim          :: fn(s: string) string               // CHECKS; needs `sub`
```

`Order :: enum { Less, Equal, Greater }`.

- Errors: none. `sub` clamps `start` and `end` to the length (proposed;
  decision U2 covers the alternative of returning `Option(string)`).
- Allocation: none. Every result is a view into the argument.
- Hooks needed: `len`, `eq`/`compare`, `sub`. Lowering: `s.len`,
  `std.mem.eql(u8, a, b)`, `std.mem.order`, `s[a..b]` (M).
- `index_of_char` returns `Option(usize)`. AGENTS.md "A7 Source Rules"
  reserves `isize` for signed offsets, and PLAN.md P3-27 flags the
  `-1` sentinel in `examples/025`. The demo ran an `isize`/`-1` draft
  of this function; the `Option(usize)` shape ran as `bytes.index_of`
  (3.6), not under this name.

```a7
io :: import "std/io"
strings :: import "std/strings"
main :: fn() {
    io.println("{} {}", strings.len("hello"), strings.count_char("banana", 'a'))
}
```

Status: RUNS today with the module at `<entry>/stdlib/std/strings.a7`;
printed `5 3`.

### 3.5 `std/ascii` (A7 source)

Purpose: byte-range character classes.

```a7
is_digit    :: fn(c: char) bool   // RUNS (match on '0'..'9')
is_alpha    :: fn(c: char) bool   // CHECKS (two range arms)
is_space    :: fn(c: char) bool   // CHECKS (== chain)
is_upper    :: fn(c: char) bool   // FAILS 6 as `c >= 'A' and c <= 'Z'` (PLAN.md P2-38); write with a range arm
to_upper    :: fn(c: char) char   // CHECKS; body needs char arithmetic (P2-38) or a 26-arm match
to_lower    :: fn(c: char) char   // CHECKS; same
digit_value :: fn(c: char) i32    // RUNS as a 10-arm match; -1 when not a digit
```

- Errors: none. Allocation: none. Lowering: ordinary A7.

```a7
io :: import "std/io"
ascii :: import "std/ascii"
main :: fn() {
    digits := 0
    for ch in "a1b22" {
        if ascii.is_digit(ch) {
            digits += ascii.digit_value(ch)
        }
    }
    io.println("{}", digits)
}
```

Status: RUNS, printed `5`.

### 3.6 `std/bytes` (A7 source; `std/mem` folded in)

Purpose: operations on `[]u8`. I propose no separate `std/mem`: SPEC
11.2's `mem_alloc`, `mem_free`, `mem_realloc` conflict with L19, and
the remaining four functions are these.

```a7
fill        :: fn(dst: []u8, value: u8)              // RUNS
index_of    :: fn(xs: []u8, value: u8) Option(usize) // RUNS
copy        :: fn(dst: []u8, src: []u8) usize        // RUNS when written through at/put (D15); direct form FAILS 6 (D7)
eq          :: fn(a: []u8, b: []u8) bool             // RUNS through at (D15); direct form FAILS 6 (D7)
compare     :: fn(a: []u8, b: []u8) Order            // PLANNED; same shape as eq
from_string :: fn(s: string) []u8                    // FAILS 6: "expected '[]u8', got 'string'"; hook
```

- Errors: none. `copy` copies `min(dst.len, src.len)` bytes and returns
  the count. `index_of` returns `.none` when absent.
- Allocation: none.
- Lowering: A7 source. `from_string` is a hook (the two types share a
  Zig representation, M). `copy` could later lower to `@memcpy` if the
  L38 measurements ask for it.

```a7
io :: import "std/io"
bytes :: import "std/bytes"
main :: fn() {
    src: [4]u8 = [1, 2, 3, 4]
    dst: [4]u8 = [0, 0, 0, 0]
    n := bytes.copy(dst[0..4], src[0..4])
    io.println("{} {}", n, bytes.eq(dst[0..4], src[0..4]))
    match bytes.index_of(dst[0..4], 3) {
        case .some(i): { io.println("found at {}", i) }
        case .none: { io.println("absent") }
    }
}
```

Status: RUNS, printed `4 true` and `found at 2`.

A caution on probe reading: `cat/bytes.a7` standalone reported only the
`from_string` type error. The direct `copy` and `eq` index errors
appeared only when the module was imported without that function. A
type error stops the pipeline before the safety pass.

### 3.7 `std/math` (hook + A7 source)

Purpose: numeric functions and constants.

```a7
// registry today, RUNS: sqrt abs floor ceil sin cos tan log exp min max
pow   :: fn(base: f64, exp: f64) f64                       // FAILS 6 today: "no function 'pow'"; new hook
round :: fn(x: f64) f64                                    // new hook (PLAN.md P3-26: examples/043 names `round`)
PI :: 3.141592653589793                                    // CHECKS as a constant in an A7 file; `math.pi` FAILS 6
clamp($T) :: fn(x: $T, lo: $T, hi: $T) $T where T: Numeric // RUNS
gcd   :: fn(a: u64, b: u64) u64                            // RUNS
sign  :: fn(x: i64) i64                                    // CHECKS
is_nan :: fn(x: f64) bool                                  // CHECKS
```

- Errors: none in this list. Checked integer arithmetic
  (`add_checked :: fn(a: i64, b: i64) Option(i64)`) belongs to the
  numerics packet (roadmap A4), not here.
- Allocation: none.
- Lowering: hooks to `@sqrt`-style builtins and `std.math.pow` (M);
  the rest is A7.
- `std/math` is a virtual module today. Mixing registry functions and
  A7 functions under one name needs the rule in section 4.

```a7
io :: import "std/io"
math :: import "std/math"
mathx :: import "std/mathx"
main :: fn() {
    io.println("{} {} {}", math.sqrt(16.0), mathx.gcd(48, 18), mathx.clamp(15, 0, 10))
}
```

Status: RUNS, printed `4 6 10`. The probe put the A7 functions in a
module named `mathx` because `std/math` is registry-only today.

### 3.8 `std/conv` (A7 source)

Purpose: text to number and number to text, no format string.

```a7
parse_i64  :: fn(s: string) Result(i64, ParseErr)                       // CHECKS (stub body)
parse_u64  :: fn(s: string) Result(u64, ParseErr)                       // CHECKS
parse_f64  :: fn(s: string) Result(f64, ParseErr)                       // CHECKS; hook body (std.fmt.parseFloat, M)
parse_bool :: fn(s: string) Result(bool, ParseErr)                      // CHECKS; needs strings.eq
format_i64 :: fn(buf: []u8, value: i64) Result(usize, FmtErr)           // CHECKS; body blocked by D13 narrowing cast
format_f64 :: fn(buf: []u8, value: f64, digits: u8) Result(usize, FmtErr) // CHECKS; hook body
```

`ParseErr :: enum { Empty, BadDigit, Overflow }`.

- Allocation: none; output goes to the caller's buffer.
- `parse_i64` is writable in A7 today with `for ch in s` and
  `ascii.digit_value`: `iso2/parse_run.a7` printed `ok 123` for
  `"123"` and `err` for `"1x"`. The first draft used `cast(i32, ch)`,
  which exits 6. Overflow detection needs the numerics packet or a
  compare-before-multiply guard.

```a7
io :: import "std/io"
conv :: import "std/conv"
main :: fn() {
    match conv.parse_i64("42") {
        case .ok(v): { io.println("{}", v) }
        case .err(e): { io.eprintln("not a number") }
    }
}
```

Status: compiles and runs against the stub module, which always
returns `.err` (printed `not a number`). The real loop ran as a
user-defined `parse` in `iso2/parse_run.a7`.

### 3.9 `std/sort` (A7 source)

Purpose: sort and search slices.

```a7
sort_i32 :: fn(xs: []i32)                                         // RUNS (insertion sort, nested single guards)
sort($T) :: fn(xs: []$T) where T: Numeric                         // RUNS across modules on i32 and f64 (iso2/xmod_generic)
sort_by($T) :: fn(xs: []$T, less: fn($T, $T) bool)                // parameter shape CHECKS (iso/g7)
is_sorted($T) :: fn(xs: []$T) bool where T: Numeric               // CHECKS (stub)
index_of($T) :: fn(xs: []$T, target: $T) Option(usize)            // CHECKS (iso/g8)
binary_search($T) :: fn(xs: []$T, target: $T) Option(usize) where T: Numeric // CHECKS (stub)
// reverse lives in std/slices (3.2)
min_of($T) :: fn(xs: []$T) Option($T) where T: Numeric            // FAILS 7 (D6)
```

The stub file `cat/sort.a7` exits 7 because of `min_of` (D6). With
`min_of` removed the file exits 0 (`iso2/sort_generic.a7`). A program
that imports the generic `sort` from a bundled-style module printed
`1 5` for `[4, 2, 5, 1, 3]` and `0.5 2.5` for `[2.5, 0.5, 1.5]`.

- Errors: none. Allocation: none (in place).
- Algorithm: insertion sort below a small length, then iterative heap
  sort. No recursion, no auxiliary buffer. Stable sort (iterative
  merge) needs a scratch buffer and waits for phase B.
- The index proof costs: `sort_i32` needs three nested `if` guards per
  swap today. `slices.swap` (3.2) hides them.
- D16: with a function named `sort` inside, the alias `sort` exits 6.
  Until PLAN.md P2-8 is fixed, callers must pick another alias.

```a7
io :: import "std/io"
sorting :: import "std/sort"
main :: fn() {
    xs: [5]i32 = [4, 2, 5, 1, 3]
    sorting.sort(xs[0..5])
    match sorting.index_of(xs[0..5], 4) {
        case .some(i): { io.println("4 is at {}", i) }
        case .none: { io.println("absent") }
    }
}
```

Status: RUNS, printed `4 is at 3`. With the alias `sort` it exits 6.

### 3.10 `std/hash` (A7 source)

Purpose: non-cryptographic hashes for maps and checksums.

```a7
fnv1a     :: fn(data: []u8) u64      // RUNS; `fnv1a("key" bytes)` = 4452171178779021548
of_string :: fn(s: string) u64       // CHECKS; body blocked: no char-to-u64 cast (D9); hook or `bytes.from_string`
of_u64    :: fn(x: u64) u64          // CHECKS (real body, multiply-xorshift mix)
combine   :: fn(a: u64, b: u64) u64  // CHECKS (real body)
fnv1a_seeded :: fn(data: []u8, seed: u64) u64 // RUNS; for per-process map seeds
```

- Errors: none. Allocation: none. Lowering: ordinary A7.
- Not for security. The doc comment must say so (roadmap B8 crypto rule).

```a7
io :: import "std/io"
hash :: import "std/hash"
main :: fn() {
    key: [3]u8 = [107, 101, 121]
    io.println("{}", hash.fnv1a(key[0..3]))
    io.println("{}", hash.fnv1a_seeded(key[0..3], 7) != hash.fnv1a(key[0..3]))
}
```

Status: RUNS, printed `4452171178779021548` and `true`.

### 3.11 `std/random` (A7 source + one hook)

Purpose: seeded pseudo-random numbers.

```a7
Rng :: struct {
    state: u64
}
seeded   :: fn(seed: u64) Rng              // RUNS
next_u64 :: fn(r: ref Rng) u64             // RUNS (xorshift64)
below    :: fn(r: ref Rng, bound: u64) u64 // RUNS; returns 0 when bound is 0
next_f64 :: fn(r: ref Rng) f64             // CHECKS (real body)
shuffle($T) :: fn(r: ref Rng, xs: []$T)    // CHECKS as stub; body writable with slices.swap (D15), not run
from_os  :: fn() Rng                       // hook: seed from the OS
```

- Errors: none. Allocation: none; the caller holds the `Rng` value.
- Explicit state instead of a hidden global keeps runs reproducible.
  A module-level `state: u64` global also runs today (probe q15).
- `below` uses `%`, which has modulo bias. Acceptable for v1; the doc
  must say it.

```a7
io :: import "std/io"
random :: import "std/random"
main :: fn() {
    rng := random.seeded(42)
    io.println("{}", random.below(rng, 6) < 6)
}
```

Status: RUNS, printed `true`.

### 3.12 `std/time` (hook + A7 source)

```a7
Instant :: struct {
    ns: i64
}
now_unix_ms :: fn() i64                              // hook
monotonic   :: fn() Instant                          // hook
elapsed_ms  :: fn(start: Instant, end: Instant) i64  // CHECKS (real body)
sleep_ms    :: fn(ms: u64)                           // hook
since_ms    :: fn(start: Instant) i64                // CHECKS (real body over monotonic)
now_unix_s  :: fn() i64                              // CHECKS (real body over now_unix_ms)
```

- Errors: none. A clock failure panics (decision U2).
- Allocation: none.
- Lowering: Zig 0.16 moved clocks and sleep behind `std.Io` (the
  backend already stores `init.io` in `__a7_io`, `zig.py:293-294`).
  Exact 0.16 call names are unchecked (M).
- No calendar, no time zones (section 1).

```a7
io :: import "std/io"
time :: import "std/time"
main :: fn() {
    start := time.monotonic()
    time.sleep_ms(10)
    io.println("{} ms", time.since_ms(start))
}
```

Status: compiles and runs against a stub module whose hooks return 0
(printed `0 ms`). The real hooks do not exist.

### 3.13 `std/os` (hook)

Purpose: arguments, environment, exit.

```a7
arg_count :: fn() usize                                 // hook; CHECKS
arg_or    :: fn(index: usize, fallback: string) string  // hook; CHECKS
arg       :: fn(index: usize) Option(string)            // CHECKS; caller's match FAILS 6 (D11)
env_or    :: fn(name: string, fallback: string) string  // hook; CHECKS
env       :: fn(name: string) Option(string)            // same D11 blocker
exit      :: fn(code: u8)                               // hook; flushes stdout first (L48)
```

- Errors: absence is `Option`. Until `string` payloads bind (PLAN.md
  P1-1, M33/M49), phase A ships only the `_or` forms.
- Allocation: none visible. Argument and environment strings live for
  the whole process.
- Lowering: `std.process.Init` carries arguments and environment in
  0.16 (M; the backend's `main(init: std.process.Init)` is at
  `zig.py:293`). `exit` lowers to `std.process.exit` after
  `__a7_stdout_flush()`.
- `main :: fn()` keeps its shape (SPEC 10.2.2). Arguments come from
  the module, not from `main` parameters.

```a7
os :: import "std/os"
io :: import "std/io"
main :: fn() {
    name := os.arg_or(1, "world")
    io.println("hello {}", name)
}
```

Status: compiles and runs against a stub module (printed
`hello world`). No `std/os` hook exists.

### 3.14 `std/fs` (hook)

Purpose: whole-file operations first, handles second.

```a7
FsErr :: enum { NotFound, Denied, TooLarge, IsDir, Io }
read_into   :: fn(path: string, buf: []u8) Result(usize, FsErr)    // CHECKS; hook
write_bytes :: fn(path: string, data: []u8) Result(usize, FsErr)   // CHECKS; hook
write_text  :: fn(path: string, text: string) Result(usize, FsErr) // CHECKS; hook
append_text :: fn(path: string, text: string) Result(usize, FsErr) // CHECKS; hook
exists      :: fn(path: string) bool                               // CHECKS; hook
remove      :: fn(path: string) Result(bool, FsErr)                // CHECKS; hook
make_dir    :: fn(path: string) Result(bool, FsErr)                // CHECKS; hook
// phase B
read_text   :: fn(path: string) Result(Text, FsErr)                // PLANNED: owning text type
open        :: fn(path: string) Result(File, FsErr)                // CHECKS as a signature
close       :: fn(f: ref File)                                     // CHECKS as a signature
```

- Errors: every OS failure maps to one `FsErr` tag. `read_into`
  returns `TooLarge` when the file exceeds the buffer, and writes
  nothing past it.
- Allocation: none in phase A. `read_text` allocates and waits for
  the memory decision.
- Lowering: `std.Io.Dir.cwd()` file calls with the stored `__a7_io`
  (M, unchecked against 0.16).
- `Result(bool, FsErr)` for `remove` is a workaround: a payload-free
  `ok` tag needs a unit type, which A7 lacks. Decision U2 covers it.
- Directory listing waits for phase B (it returns a list of names).

```a7
io :: import "std/io"
fs :: import "std/fs"
main :: fn() {
    buf: [8]u8 = [0, 0, 0, 0, 0, 0, 0, 0]
    match fs.read_into("notes.txt", buf[0..8]) {
        case .ok(n): { io.println("{} bytes", n) }
        case .err(e): { io.eprintln("cannot read notes.txt") }
    }
}
```

Status: compiles and runs against a stub module that always returns
`.err` (printed `cannot read notes.txt`). The real hook needs R1 and
R13. A real program wants a larger buffer; an uninitialized
`buf: [4096]u8` is PLAN.md P2-42 / D-G today.

### 3.15 `std/path` (A7 source over `strings.sub`)

```a7
base      :: fn(p: string) string   // CHECKS as stub; needs strings.sub
dir       :: fn(p: string) string   // CHECKS as stub
ext       :: fn(p: string) string   // CHECKS as stub
is_abs    :: fn(p: string) bool     // CHECKS (real body)
join_into :: fn(buf: []u8, a: string, b: string) Result(usize, PathErr) // CHECKS as stub
```

- Linux `/` separator only (roadmap: Linux x86-64 is the first target).
- Allocation: none. `join` returning an owning string is phase B.

```a7
io :: import "std/io"
path :: import "std/path"
main :: fn() {
    io.println("{} {}", path.base("/tmp/a.txt"), path.is_abs("/tmp/a.txt"))
}
```

Status: compiles and runs against a stub whose `base` returns its
argument (printed `/tmp/a.txt true`). `is_abs` has its real body.

### 3.16 `std/testing` (A7 source)

Purpose: checks for golden programs, with a count and an exit status.

```a7
Tally :: struct {
    passed: u32
    failed: u32
}
check        :: fn(t: ref Tally, cond: bool, name: string)             // RUNS
check_eq_i64 :: fn(t: ref Tally, got: i64, want: i64, name: string)    // RUNS
check_eq($T) :: fn(t: ref Tally, got: $T, want: $T, name: string)      // CHECKS
report       :: fn(t: Tally) bool                                      // RUNS
panic        :: fn(msg: string)                                        // hook: print, flush, abort
```

- Errors: none; failures are counted and printed to stderr.
- Allocation: none.
- `panic` must flush stdout first (PLAN.md P2-45 drops buffered output
  on a panic today).

```a7
io :: import "std/io"
strings :: import "std/strings"
testing :: import "std/testing"
main :: fn() {
    t := Tally{passed: 0, failed: 0}
    testing.check(t, strings.len("hello") == 5, "strings.len")
    ok := testing.report(t)
}
```

Status: RUNS, printed `1 passed, 0 failed`. `Tally` is written bare
because `testing.Tally` does not parse (D4). The D2 demo printed
`FAIL deliberate failure: got 2, want 3` and `13 passed, 1 failed`.

### 3.17 `std/utf8`, `std/hex`, `std/base64` (A7 source)

```a7
valid         :: fn(data: []u8) bool                                // CHECKS (stub)
count_runes   :: fn(data: []u8) Result(usize, Utf8Err)              // CHECKS (stub)
decode_rune   :: fn(data: []u8, at: usize) Result(u32, Utf8Err)     // CHECKS (stub)
encode_rune   :: fn(buf: []u8, rune: u32) Result(usize, EncErr)     // CHECKS (stub)
hex_encode    :: fn(dst: []u8, src: []u8) Result(usize, EncErr)     // CHECKS (stub)
hex_decode    :: fn(dst: []u8, src: []u8) Result(usize, EncErr)     // CHECKS (stub)
base64_encode :: fn(dst: []u8, src: []u8) Result(usize, EncErr)     // CHECKS (stub)
```

- Allocation: none; caller buffers.
- Bodies read one slice and write another at different indexes. D15
  covers the indexing; the D13 narrowing-cast limit still blocks them.
  Phase B.

```a7
io :: import "std/io"
utf8 :: import "std/utf8"
main :: fn() {
    src: [2]u8 = [202, 254]
    dst: [4]u8 = [0, 0, 0, 0]
    match utf8.hex_encode(dst[0..4], src[0..2]) {
        case .ok(n): { io.println("{} hex digits", n) }
        case .err(e): { io.eprintln("buffer too small") }
    }
}
```

Status: compiles and runs against a stub that always returns `.err`
(printed `buffer too small`).
- `char` is a byte today (SPEC 2.1; PLAN.md P2-21 notes `'€'` into
  `u8`). A rune type is a language decision and is not proposed here.

### 3.18 `std/list` (compiler type + hooks; phase B)

Purpose: growable array.

```a7
make($T)  :: fn() List($T)                               // PLANNED
push($T)  :: fn(l: List($T), value: $T)                  // PLANNED
pop($T)   :: fn(l: List($T)) Option($T)                  // PLANNED; D6 and D11 apply
get($T)   :: fn(l: List($T), index: usize) Option($T)    // PLANNED; roadmap B3
set($T)   :: fn(l: List($T), index: usize, value: $T) bool // PLANNED
len($T)   :: fn(l: List($T)) usize                       // PLANNED
items($T) :: fn(l: List($T)) []$T                        // PLANNED; view lifetime is gate M13
copy($T)  :: fn(l: List($T)) List($T)                    // PLANNED; the explicit copy L42 requires
clear($T) :: fn(l: List($T))                             // PLANNED
```

My stub (`cat/list.a7`) exits 6 on a stub artifact (a phantom field
needed to carry `$T`), so no row here is verified beyond parsing.

Why this cannot be an A7 struct today:

1. L42: `b := a` shares the list. A7 structs copy on assignment, so a
   struct `{ptr, len, cap}` would give two lengths over one buffer.
2. D10: no heap buffer of runtime size exists (`new [N]T` rejected).
3. D7: `l.items[l.len]` is not provable from a field-loaded length.
4. D6: `make` and `pop` return generic types from generic functions.

So `List(T)` is a compiler-known handle type. The parameter is `List($T)`,
not `ref List($T)`, because the value is already a shared handle.

- Errors: `get` and `pop` return `Option`. Growth failure: decision
  U6 (gate M2: `try_push` vs stop).
- Allocation: the runtime, by whichever mechanism wins Wave B. No
  allocator parameter (L17, L19).
- Lowering: a Zig generic `__a7_List(T)` holding `std.ArrayList(T)`
  behind a pointer (M).

```a7
io :: import "std/io"
list :: import "std/list"
main :: fn() {
    xs := list.make(i32)
    list.push(xs, 3)
    ys := xs
    list.push(ys, 4)
    io.println("{}", list.len(xs))
}
```

Status: parses (`--mode ast` exit 0); pipeline exits 3 `Module
'std/list' not found`. Intended output is `2`: `ys` and `xs` are one
list (L42). `list.make(i32)` passes a type as an argument, which
exits 6 for user generics today (D5).

### 3.19 `std/map`, `std/set` (compiler type + hooks; phase B)

```a7
make($K, $V)   :: fn() Map($K, $V)                          // PLANNED
put($K, $V)    :: fn(m: Map($K, $V), key: $K, value: $V)    // PLANNED
get($K, $V)    :: fn(m: Map($K, $V), key: $K) Option($V)    // PLANNED
has($K, $V)    :: fn(m: Map($K, $V), key: $K) bool          // PLANNED
remove($K, $V) :: fn(m: Map($K, $V), key: $K) bool          // PLANNED
len($K, $V)    :: fn(m: Map($K, $V)) usize                  // PLANNED
```

- Keys in v1: integers, `bool`, `char`, enums, `string`. Struct keys
  need derived equality and hashing (research 03 section 4 step 4),
  which is a language feature and is not proposed here.
- Iteration order: insertion order (proposed), so golden outputs are
  stable. Research 03 section 5 asks for hash determinism (M40).
- `Set(K)` is `Map(K, bool)` with `add`, `has`, `remove`, `len`.
- Lowering: Zig `std.AutoArrayHashMap` / `std.StringArrayHashMap`,
  which keep insertion order (M).
- Same four blockers as `List`, plus string equality (D9).

```a7
io :: import "std/io"
map :: import "std/map"
main :: fn() {
    counts := map.make(string, i64)
    map.put(counts, "a", 1)
    match map.get(counts, "a") {
        case .some(n): { io.println("{}", n) }
        case .none: { io.println("absent") }
    }
}
```

Status: parses; pipeline exits 3 `Module 'std/map' not found`.

### 3.20 `std/ring` (A7 source; phase A if D6 is fixed)

Purpose: fixed-capacity queue over caller storage. It gives worklists
(the no-recursion idiom) before the heap exists.

```a7
Ring :: struct {
    data: []$T
    head: usize
    count: usize
}
over($T)      :: fn(storage: []$T) Ring($T)           // FAILS 7 (D6)
push_back($T) :: fn(r: ref Ring($T), value: $T) bool  // parameter shape CHECKS; body hits D7
pop_front($T) :: fn(r: ref Ring($T)) Option($T)       // FAILS 7 (D6)
is_full($T)   :: fn(r: Ring($T)) bool                 // CHECKS (real body, iso2)
is_empty($T)  :: fn(r: Ring($T)) bool                 // PLANNED; same shape as is_full
len($T)       :: fn(r: Ring($T)) usize                // PLANNED
```

- Errors: `push_back` returns false when full. Allocation: none.
- This module is the smallest test of "containers in A7 source". It
  fails today on D6. D15 covers its indexing (not run for this module).

```a7
io :: import "std/io"
ring :: import "std/ring"
main :: fn() {
    storage: [4]usize = [0, 0, 0, 0]
    work := ring.over(storage[0..4])
    ok := ring.push_back(work, 2)
    match ring.pop_front(work) {
        case .some(node): { io.println("visit {}", node) }
        case .none: { io.println("done") }
    }
}
```

Status: parses; pipeline exits 3 `Module 'std/ring' not found`.

### 3.21 `std/json` (A7 source; reader and writer in phase A)

Purpose: read and write JSON without a heap. The reader is a pull
parser: each `next` call returns one event that points into the input
bytes. Nesting is a counter and a bit stack inside the reader, so no
recursion is needed.

```a7
Kind :: enum { ObjectStart, ObjectEnd, ArrayStart, ArrayEnd, Key, String, Number, True, False, Null, End, Invalid }
JsonErr :: enum { Syntax, TooDeep, NoSpace, NotANumber, BadEscape, WrongKind }
Event :: struct {
    kind: Kind
    start: usize
    end: usize
}
reader        :: fn(data: []u8) Reader                                   // RUNS
next          :: fn(r: ref Reader) Event                                 // RUNS (D17)
kind_name     :: fn(k: Kind) string                                      // RUNS
skip_value    :: fn(r: ref Reader) bool                                  // CHECKS (stub)
text_is       :: fn(r: Reader, ev: Event, want: string) bool             // CHECKS (stub); body needs R7
number_f64    :: fn(r: Reader, ev: Event) Result(f64, JsonErr)           // CHECKS (stub)
number_i64    :: fn(r: Reader, ev: Event) Result(i64, JsonErr)           // CHECKS (stub)
unescape_into :: fn(r: Reader, ev: Event, buf: []u8) Result(usize, JsonErr) // CHECKS (stub); body needs R23
validate      :: fn(data: []u8) Result(usize, JsonErr)                   // CHECKS (stub)
// writer over a caller buffer
writer       :: fn(buf: []u8) Writer                                     // CHECKS (stub)
begin_object :: fn(w: ref Writer)                                        // CHECKS (stub); also end_object, begin_array, end_array
key          :: fn(w: ref Writer, name: string)                          // CHECKS (stub)
put_string   :: fn(w: ref Writer, value: string)                         // CHECKS (stub); also put_i64, put_f64, put_bool, put_null
finish       :: fn(w: Writer) Result(usize, JsonErr)                     // CHECKS (stub)
```

- Errors: a malformed input yields one `Invalid` event, then `End`.
  `validate` walks the whole input first and returns the byte offset
  of the first error. Nesting deeper than 64 gives `TooDeep`. The
  writer records the first failure and `finish` reports it, so calls
  need no per-call match.
- Allocation: none. Events hold offsets into the caller's bytes.
  A string event with escapes is copied out with `unescape_into`.
- Lowering: ordinary A7. `number_f64` uses the `conv.parse_f64` hook.
- An event is a struct, not a union with a text payload, because a
  `string` payload cannot be matched today (D11).
- The probe reader does not validate: it skips commas and colons as
  whitespace and trusts the first letter of `true`, `false`, `null`.
  The shipped reader must track "expect value / expect key / expect
  comma" per level. That is a state enum plus the bit stack; still no
  recursion.
- Input is `[]u8`. A `string` literal cannot become `[]u8` today (D9),
  so the probe spelled the document as byte values.

```a7
io :: import "std/io"
json :: import "std/json"
main :: fn() {
    // the bytes of {"a":[12,true]}
    text: [15]u8 = [123, 34, 97, 34, 58, 91, 49, 50, 44, 116, 114, 117, 101, 93, 125]
    r := json.reader(text[0..15])
    running := true
    while running {
        ev := json.next(r)
        if ev.kind == Kind.End {
            running = false
        } else {
            io.println("{} {}..{}", json.kind_name(ev.kind), ev.start, ev.end)
        }
    }
    io.println("depth seen {}", r.depth)
}
```

Status: RUNS. Output: `object_start 0..1`, `key 2..3`,
`array_start 5..6`, `number 6..8`, `true 9..13`, `array_end 13..14`,
`object_end 14..15`, `depth seen 2`. With `bytes.from_string` (R7) the
second line of `main` becomes `r := json.reader(bytes.from_string(doc))`.

### 3.22 `std/yaml` (A7 source; reader in phase A, subset)

Purpose: read configuration-style YAML with the same event model as
`std/json`.

Proposed subset (decision U13). YAML rules here are from memory (M):

- In: block mappings and block sequences nested by space indentation;
  flow sequences `[a, b]` and flow mappings `{a: b}`; plain,
  single-quoted, and double-quoted scalars; `|` and `>` block scalars;
  `#` comments; one document with an optional leading `---`.
- Scalar typing follows the YAML 1.2 core schema: `null` and `~`;
  `true` and `false`; integers; floats; everything else is text. `no`,
  `yes`, `on`, `off` are text.
- Out, reported as `Unsupported` with a line number: anchors (`&a`),
  aliases (`*a`), tags (`!t`), merge keys (`<<`), complex keys (`?`),
  more than one document. Tabs in indentation report `TabIndent`.
- Reason for the cut: aliases let a small file expand without bound,
  the failure research 25 section 4 names. Without aliases the
  document is a tree, the same shape as JSON.

```a7
Kind :: enum { MapStart, MapEnd, SeqStart, SeqEnd, Key, Scalar, DocStart, End, Invalid }
ScalarKind :: enum { Null, Bool, Int, Float, Text }
YamlErr :: enum { Syntax, BadIndent, TabIndent, TooDeep, Unsupported, NoSpace, WrongKind }
Event :: struct {
    kind: Kind
    start: usize
    end: usize
    line: u32
}
next         :: fn(r: ref Reader) Event                                  // CHECKS (stub)
error_of     :: fn(r: Reader) YamlErr                                    // CHECKS (stub)
scalar_kind  :: fn(r: Reader, ev: Event) ScalarKind                      // CHECKS (stub)
text_is      :: fn(r: Reader, ev: Event, want: string) bool              // CHECKS (stub)
scalar_i64   :: fn(r: Reader, ev: Event) Result(i64, YamlErr)            // CHECKS (stub)
scalar_f64   :: fn(r: Reader, ev: Event) Result(f64, YamlErr)            // CHECKS (stub)
scalar_bool  :: fn(r: Reader, ev: Event) Result(bool, YamlErr)           // CHECKS (stub)
unquote_into :: fn(r: Reader, ev: Event, buf: []u8) Result(usize, YamlErr) // CHECKS (stub)
skip_value   :: fn(r: ref Reader) bool                                   // CHECKS (stub)
validate     :: fn(data: []u8) Result(usize, YamlErr)                    // CHECKS (stub)
```

- Errors: as `std/json`, plus a line number on each event. `MapEnd`
  and `SeqEnd` are produced when indentation drops.
- Allocation: none. The reader holds an indentation stack of 64 levels
  as a fixed array field. Writing to that field with a field-loaded
  depth needs a `slices.put`-style accessor (D15) or R14.
- Lowering: ordinary A7. No Zig YAML library exists in Zig std (M), so
  a hook is not an option; this module is A7 source or nothing.
- No YAML writer in v1. `std/json` output is valid YAML flow style (M).
- `Kind`, `Event`, and `Reader` collide with the `std/json` names
  while types share one namespace (D4): a program that imports both
  exits 6. Until R9, the names carry a prefix (`YamlKind`, `YamlEvent`).

```a7
io :: import "std/io"
yaml :: import "std/yaml"
main :: fn() {
    // bytes of "port: 8080\n"
    text: [11]u8 = [112, 111, 114, 116, 58, 32, 56, 48, 56, 48, 10]
    r := yaml.reader(text[0..11])
    key := yaml.next(r)
    value := yaml.next(r)
    match yaml.scalar_i64(r, value) {
        case .ok(port): { io.println("port {}", port) }
        case .err(e): { io.eprintln("port is not a number") }
    }
}
```

Status: compiles and runs against a stub module whose `next` returns
`End` and whose `scalar_i64` returns `.err` (printed
`port is not a number`). Intended output is `port 8080`. No YAML
reader body was written; the signatures pass `--mode pipeline --lib`
over stub bodies (`cat2/yaml_api.a7`, exit 0).

### 3.23 `std/data` (document tree for JSON and YAML; phase B)

Purpose: parse a whole document into a tree and look values up by key
or index. One tree type serves both formats.

```a7
ValueKind :: enum { Null, Bool, Number, Text, List, Map }
DataErr :: enum { Syntax, TooDeep, Unsupported, WrongKind }
parse_json :: fn(text: []u8) Result(Doc, DataErr)   // CHECKS (stub)
parse_yaml :: fn(text: []u8) Result(Doc, DataErr)   // CHECKS (stub)
root    :: fn(d: Doc) Value                         // CHECKS (stub)
kind    :: fn(v: Value) ValueKind                   // CHECKS (stub)
get     :: fn(v: Value, key: string) Option(Value)  // CHECKS (stub)
at      :: fn(v: Value, index: usize) Option(Value) // CHECKS (stub)
len     :: fn(v: Value) usize                       // CHECKS (stub)
as_f64  :: fn(v: Value) Option(f64)                 // CHECKS (stub); also as_i64, as_bool
as_text :: fn(v: Value) Option(string)              // CHECKS as a signature; the caller's match FAILS 6 (D11)
text_or :: fn(v: Value, fallback: string) string    // CHECKS (stub)
to_json :: fn(d: Doc, buf: []u8) Result(usize, DataErr) // PLANNED
```

- Design: `Doc` owns a flat node table. `Value` is a small copyable
  struct `{doc, node}` holding an index, so it binds in a `match`
  today. Children link by index (first child, next sibling), the
  pattern `examples/025` and `026` use, so no self-referential `ref`
  is needed (D10). The builder runs the event reader with an explicit
  stack of open containers.
- Errors: `parse_*` returns `DataErr`. Lookups return `Option`.
- Allocation: the node table and copied text grow, so this module
  needs `List` and owning text, and waits for the memory decision.
  A phase A variant over caller storage is possible:
  `parse_json_into(text, nodes: []Node) Result(Doc, DataErr)`.
- Lowering: A7 source over `std/list`.

```a7
io :: import "std/io"
data :: import "std/data"
main :: fn() {
    src: [2]u8 = [123, 125]
    match data.parse_json(src[0..2]) {
        case .ok(doc): {
            match data.get(data.root(doc), "port") {
                case .some(v): { io.println("{}", data.text_or(v, "?")) }
                case .none: { io.println("no port") }
            }
        }
        case .err(e): { io.eprintln("bad json") }
    }
}
```

Status: compiles and runs against a stub module that always returns
`.err` (printed `bad json`; `cat2/tree_use.a7`, imported as
`./tree_api`). The nested match over `Result(Doc, DataErr)` and
`Option(Value)` type-checks today.

### 3.24 Later modules (phase C)

| Module | Sketch | Blocker |
| --- | --- | --- |
| `std/text` | Owning, growable text: `make`, `push_str`, `push_char`, `view`, `len` (phase B) | Memory decision; research 03 section 3 `String` |
| `std/process` | `run :: fn(cmd: List(string)) Result(RunResult, ProcErr)` | `List`, owning text |
| `std/log` | Levels over `io.eprintln` | Variadics or a hook |
| `std/net` | `dial_tcp`, `listen_tcp` | Concurrency track (research 10 section 4) |

## 4. Architecture

### Options

(a) Registry only. Every function is a Python `StdlibFunction` plus
Zig emission in `a7/backends/zig.py`.

- Typing: each function needs checker code. Today `std.io.*` returns
  `VOID` and `std.math.*` goes through `_validate_math_call`
  (`type_checker.py:2151-2156`).
- Cost: the io family alone spans about 140 lines of emission
  (`zig.py:250-303`, `2190-2210`, `2812-2880`). One hundred functions at
  that rate grows a 3,097-line file PLAN.md Phase 5 already wants split.
- Generic containers lower straight to Zig generics, so D6 and D7 do
  not block them.
- The stdlib is invisible to A7 tooling (`--mode doc`, diagnostics).

(b) A7 source only, with thin intrinsics.

- Typing is free: D1 returned typed values with no checker change.
- Blocked today by D6, D8, D9, D10. D7 has a workaround in A7 (D15).
- Needs an `extern` or intrinsic declaration form, which is new syntax.

(c) Hybrid. Recommended.

- Layer 0, hooks: about 40 typed registry entries for what A7 cannot
  express: formatted printing, OS calls, string primitives, and the
  `List`/`Map` handle types.
- Layer 1, A7 source: everything else, in `.a7` files.
- No new syntax. The hook declaration lives in Python, not in A7.

### How hooks get types

Extend `StdlibFunction` with a signature written in A7 type syntax:

```python
StdlibFunction(module="fs", name="read_into",
    signature="fn(path: string, buf: []u8) Result(usize, FsErr)",
    backend_map={"zig": "__a7_fs_read_into"})
```

The checker parses the signature once with the existing type parser
and uses it for every hook call. This replaces the special cases in
`_visit_stdlib_module_call` and is the general form of G5B-2
(PLAN.md Phase 6 item 2). Printing keeps its format-string path.

Each hook's Zig body lives in a `.zig` snippet file under
`a7/stdlib/rt/`. The backend copies a snippet into the single output
file only when a call uses it, as it already does for the io preamble
(`_io_streams_needed`). Output stays one Zig file (STATUS:81).

`Result` and `FsErr` in that signature must name real A7 types. They
come from a bundled A7 source file (below), which is why the type
namespace problem (D4) is a prerequisite.

### How `std/...` imports resolve

Today (R): `ModuleResolver` checks the registry aliases first, then
searches the entry directory, `<entry>/stdlib`, and the repo-root
`stdlib` (D3).

Proposed order:

1. Registry (virtual) modules: `std/io` and hook-only modules.
2. Bundled A7 modules: `a7/stdlib/src/std/<name>.a7`.
3. User files, relative to the importing file (L30).

Three things change, and each needs approval:

- The bundled directory moves inside the package (D3 is a bug today:
  the path points outside the wheel).
- `std/` becomes reserved: a user's `std/strings.a7` or
  `stdlib/std/strings.a7` no longer shadows the shipped module. Today
  it does (D1 relied on that). Decision U10.
- A module is either virtual or A7 source. `std/math` needs both
  (hooks for `sqrt`, A7 for `clamp`). Proposed rule: an A7 std module
  may import a hook module named `std/sys/<name>` and wrap it. Zig
  inlines the wrapper (inference, not measured). The alternative is to
  let the registry supply names the A7 file does not define.

### Generic containers under today's generics

- Slice algorithms (`sort_by($T)`, `index_of($T)`, `count($T)`): A7
  source. Parameter-position generics work (D6).
- Anything that returns `Option($T)`, `Ring($T)`, or `Box($T)` from a
  generic function: blocked by D6 until PLAN.md P2-49 is fixed.
- `List($T)` and `Map($K, $V)`: compiler-known handle types lowered to
  Zig generics, per L42. The A7-side `std/list` file holds only
  helpers that need no handle internals.
- Fixed-capacity containers with a size parameter (`Buf($T, $N)`):
  `Buf(4)` does not parse (STATUS:103). Not used in this proposal.

### Testing

- One golden program per module under `examples/std/` (or a new
  `test/stdlib/`), each printing a `testing.report` line, each with an
  expected-output file, each built and run in debug and release. This
  follows the existing example E2E pattern (AGENTS.md "Verification
  Commands").
- One failure-path program per fallible hook: missing file, read-only
  directory, full buffer, bad digit. Research 03 section 5 and
  roadmap B6 ask for real failure recovery.
- A stage-boundary check for the bundled sources: every bundled `.a7`
  file passes `a7 check --lib`, and one program that calls every
  public function builds with `zig build-exe`. Zig analyses function
  bodies lazily, so an uncalled stdlib function is never checked by
  Zig (L32 records the same effect). PLAN.md Phase 1b item 3 proposes
  this check for user code.
- No test may mirror the registry dict (PLAN.md T-8 lists 44 such
  tests in `test_stdlib_registry.py`).

### Wheel packaging

- Put sources at `a7/stdlib/src/std/*.a7` and snippets at
  `a7/stdlib/rt/*.zig`. Add them as setuptools package data
  (`[tool.setuptools.package-data] a7 = ["stdlib/src/std/*.a7",
  "stdlib/rt/*.zig"]`).
- Resolve them with `Path(__file__).parent / "stdlib" / "src"` from
  `a7/compile.py`.
- `scripts/verify_wheel_install.py` gains one program that imports a
  bundled A7 module, so a wheel without the files fails the gate.
- Not verified: I did not run `uv build`. The claim that the current
  wheel would miss a repo-root `stdlib/` is from reading
  `pyproject.toml:24-26`.

### Compile-time cost

- Measured (V): hello world 0.15-0.24 s; the nine-import demo
  0.31-0.38 s. Eight A7 modules of 241 lines cost about 0.15 s of
  front-end time. Three runs each, same machine, not a benchmark.
- Only imported modules are parsed. A program that imports `std/io`
  alone pays nothing new.
- A7 checks every function of an imported module, called or not
  (L32). Cost grows with module size, so modules stay small and
  single-purpose.
- Zig builds only what is called. Zig build time was not measured.
- If front-end time becomes a problem: cache parsed std ASTs keyed by
  compiler version. Not needed at the measured numbers.

## 5. Dependency graph

Prerequisites, each mapped to PLAN.md or marked new.

| ID | Prerequisite | PLAN.md row | Probe |
| --- | --- | --- | --- |
| R1 | Checker types hook calls from a declared signature | Phase 6 item 2 (G5B-2); roadmap A3, B2 | D12 |
| R2 | `read_line` second-read fix | P1-4 | not rerun |
| R3 | Generic function may build and return `G($T)` | P2-49 (nearest: `Pair($B, $A){...}` in a generic body) | D6 |
| R4 | Inline-`$T` form or one documented spelling | P3-13, P2-40 | D5 |
| R5 | Owning or `string` payloads bind in `match` | P1-1; roadmap A5 (M33/M49) | D11 |
| R6 | String equality | P2-47, P2-35 | D9 |
| R7 | String length, byte view, `char`/`u8` casts, `char` ordering | P2-38 for ordering; the rest is new (STATUS:152 says `string.len` is rejected on purpose) | D9 |
| R8 | Memory model decision | Phase 6 item 3 (Wave B); L51, L57; roadmap A5 | D10 |
| R9 | Type names scoped per module | P2-8 | D4 |
| R10 | Module-qualified types (`m.T`, `m.G(i32)`) | P3-18 | D4 |
| R11 | Visibility enforced (`_name` private, L27) | SPEC 10.4; P4-8 (P-MOD unapproved) | not probed |
| R12 | Slices as parameters | none needed; works | p03 |
| R13 | Hook mechanism (typed registry + Zig snippets) | new; direction in L41 | - |
| R14 | Index proof from a field-loaded value | new; nearest is STATUS priority 4 and SAF-2 | D7 |
| R15 | Index proof with two bounds on one index; literal index against a slice length. Not blocking: D15 works around it at one compare per access | new | D7, D15 |
| R16 | Runtime slice bounds (`xs[a..b]`) | new | D8 |
| R17 | Heap buffer of runtime size | new for A7 source; AGENTS.md says `new [N]T` is rejected "until the language model is defined" | D10 |
| R18 | Self-referential `ref` struct field | P2-30 | D10 |
| R19 | Defined initial values for buffers | P2-42, P3-21, D-G | not rerun |
| R20 | Stdout flushed on panic | P2-45 | not rerun |
| R21 | Bundled directory inside the package; `std/` reserved | new | D3 |
| R22 | Variadic lowering (only if `io.format_into` or `log` move to A7 source) | STATUS:118 | D14 |
| R23 | Narrowing cast under a range guard | new; nearest is numerics roadmap A4 | D13 |
| R24 | Unit payload for `Result` (`ok` with no value) | new | - |

Module to prerequisite:

| Module | Needs |
| --- | --- |
| `io` (typed) | R1, R2; R13 for `format_into` |
| `slices` | none; R3 for `get` |
| `option`, `result` | R9 or a prelude (U3); R3 for constructors |
| `strings` | R13 (three hooks), R6, R7; R16 if `sub` is A7 |
| `ascii` | none for the match-based forms; P2-38 for comparisons |
| `bytes` | none (accessors, D15); R7 for `from_string` |
| `math` | R13 for `pow`/`round`; the virtual-plus-source rule |
| `conv` | R9 (shared `Result`), R23 for `format_i64`, R13 for floats |
| `sort` | R3 for `min_of`; R9 so the alias `sort` works (D16) |
| `hash` | R7 for `of_string` |
| `random` | R13 for `from_os` |
| `time`, `os`, `fs` | R1, R13, R9; R5 for `arg`/`env`; R19 for buffers; R24 optional |
| `path` | `strings.sub` |
| `testing` | R20 for `panic`; runs today otherwise |
| `ring` | R3 |
| `list`, `map`, `set`, `text` | R8, R3, R5, R6, R10 |
| `utf8`, `hex`, `base64` | R23 |
| `json` (reader, writer) | none for `next` (D17); R7 for string input and `text_is`; R23 for `unescape_into` and number output; R9 for the shared `Result` |
| `yaml` (reader) | same as `json`; R9 or prefixed names to import beside `json` (D4) |
| `data` (tree) | `list`, `text`, R5 for `as_text`, R8 |
| `process`, `log`, `net` | `list`, `map`, `text`; R22 for `log` |

## 6. Phased roadmap

### Phase A: no heap

Starts after PLAN.md Phases 0-2 land and after R1, R9, R13, R21.
Eighteen modules: `io` (typed), `option`/`result` (counted as one),
`slices`, `strings`, `ascii`, `bytes`, `math`, `conv`, `sort`, `hash`,
`random`, `time`, `os`, `fs` (caller-buffer forms), `path`, `testing`,
`json` (event reader and writer), `yaml` (event reader).

What already runs with no compiler change (D2, D15, D17, section 3):
`strings.len`, `count_char`; `ascii.is_digit`, `digit_value`;
`slices.at`, `put`, `swap`, `reverse`, `contains`; `bytes.fill`,
`index_of`, `copy`, `eq`; `math.gcd`, `clamp`; `sort.sort`,
`sort_i32`, `index_of`; `hash.fnv1a`, `fnv1a_seeded`; `random.seeded`,
`next_u64`, `below`; `testing.check`, `check_eq_i64`, `report`;
`json.reader`, `next`, `kind_name`.

Exit criteria, each a program with a golden output file, run in debug
and release:

1. `wc`: reads a file named by `os.arg_or(1, "input.txt")` into a
   64 KiB buffer with `fs.read_into`, prints line, word, and byte
   counts. A missing file prints one error line and exits 1 through
   `os.exit`.
2. `sum`: reads integers from stdin with `io.read_line` and
   `conv.parse_i64`, prints the total, reports the first bad line by
   number. Covers PLAN.md P1-4.
3. `sorted`: fills 1,000 values from `random.seeded(1)`, sorts with
   `sort.sort_by`, checks `sort.is_sorted`, prints the first five.
4. `selftest`: one `testing.Tally` over every phase A function;
   prints `N passed, 0 failed`.
5. `jsonlint`: reads a file with `fs.read_into`, runs
   `json.validate`, prints `ok` or `error at byte N`, then prints one
   line per event. A second run on a file with a missing brace prints
   the error offset.
6. `config`: reads a YAML file with nested maps, a list, a quoted
   string, and a comment; prints `server.port = 8080` style lines. A
   file with an anchor prints `unsupported at line N` and exits 1.
7. A wheel installed in a clean venv builds and runs program 4.

### Phase B: heap types

Starts after the memory mechanism is selected (L51, L57, Wave B memo)
and after R3, R5, R6, R10. Modules: `text`, `list`, `map`, `set`,
`data` (JSON and YAML tree), `fs.read_text`, directory listing, `ring`,
`utf8`/`hex`/`base64`, `slices.get`, `sort.min_of`.

Exit criteria:

1. `wordfreq`: reads a file of any size with `fs.read_text`, counts
   words in a `Map(string, i64)`, prints the ten most frequent, sorted.
2. `tokens`: a tokenizer for a small expression language that returns
   a `List(Token)`; the L44 acceptance class.
3. `shared`: `b := a` then `list.push(b, x)` and `list.len(a)` prints
   the new length; `c := list.copy(a)` stays independent (L42).
4. A loop that builds and drops 10N lists keeps peak memory flat
   (research 03 section 5), measured under the L38 rule.
5. `data` round-trip: `parse_json` on a nested document, `to_json`
   back, output equals a golden file. `parse_yaml` on the equivalent
   YAML file prints the same JSON.

### Phase C: later

`process`, `log`, then `net` with the concurrency track.

Exit criteria:

1. `process.run` of `echo` returns exit code 0 and the output text.
2. A loopback TCP echo program (research 10 section 5).

## 7. Decisions for the user

Each row is a proposal. None is approved.

Snippets in this section are fragments unless a status is given. I
ran three: U1 option 2 (`name.len()` exits 6), U7 option 1 (runs,
through `bytes.copy`), and U12 option 2 (`extern fn` exits 5,
`Function declarations must have names`). The `{ ... }` bodies in U3
stand for omitted code and do not parse.

### U1. Function spelling: `strings.len(s)` or `s.len()`

Today: methods do not exist. `c.inc()` exits 6 (`Struct 'Counter' has
no field 'inc'`). `s.len` on a string exits 6.

- Option 1 (recommended): free functions in modules. No language change.
- Option 2: add method-call sugar, so `x.f(a)` means `f(x, a)`.
  A language change with its own packet.

```a7
// Option 1
n := strings.len(name)
list.push(xs, 3)
// Option 2
n := name.len()
xs.push(3)
```

### U2. Failing operations: panic, `Result`, or both

Today: `io.println` panics on a write failure. `io.println_ok`
returns a `Result` that only a statement can discard (D12).

- Option 1 (recommended): one name per operation. An operation that
  can fail for reasons outside the program (files, input, parsing)
  returns `Result` or `Option`. Printing to the console keeps the
  panicking `println`; `println_ok` stays as the one checked form.
- Option 2: every fallible function ships twice, `read_into` and
  `must_read_into`.

```a7
// Option 1
match fs.read_into("a.txt", buf[0..4096]) {
    case .ok(n): { io.println("{}", n) }
    case .err(e): { io.eprintln("read failed") }
}
// Option 2 adds
n := fs.must_read_into("a.txt", buf[0..4096])   // panics on failure
```

Sub-questions with the same shape. A search returns `Option(usize)`
(as proposed; AGENTS.md keeps `isize` for offsets and P3-27 flags the
`-1` sentinel) or `isize` with `-1`. `fs.remove` returns
`Result(bool, FsErr)` (as proposed) or A7 gains a no-payload `ok`.

```a7
match bytes.index_of(data[0..4], 3) {       // proposed; ran, printed "found at 2"
    case .some(i): { io.println("found at {}", i) }
    case .none: { io.println("absent") }
}
i := bytes.index_of(data[0..4], 3)          // alternative: i is isize, -1 when absent
```

### U3. Who declares `Option` and `Result`

Today: each program declares its own. A second declaration in an
imported module exits 6 `Already defined` (D4). So a stdlib that
declares `Result` breaks every program that already declares one.

- Option 1 (recommended): the compiler provides `Option` and `Result`
  to every file. A user declaration of either name becomes an error
  (roadmap B4 states this shape). Programs that declare them today
  must delete the declaration.
- Option 2: wait for per-module type scoping (PLAN.md P2-8, P3-18),
  then write `opt.Option(i32)`.

```a7
// Today: required in each program
Result :: union(tag) {
    ok: $T,
    err: $E,
}
parse :: fn(s: string) Result(i32, ParseErr) { ... }

// Option 1: the declaration above is deleted; the rest is unchanged
parse :: fn(s: string) Result(i32, ParseErr) { ... }

// Option 2
res :: import "std/result"
parse :: fn(s: string) res.Result(i32, ParseErr) { ... }
```

### U4. Auto-import

Today: nothing is imported unless written. A program that prints
needs `io :: import "std/io"`.

- Option 1 (recommended): keep explicit imports for modules. Only the
  two type names in U3 are always present.
- Option 2: `io` is always available without an import.

```a7
// Option 1 (today)
io :: import "std/io"
main :: fn() {
    io.println("hi")
}
// Option 2
main :: fn() {
    io.println("hi")
}
```

Option 2 breaks a program with a local named `io` (L28 makes that
clash an error).

### U5. Bare names for new modules

Today: `import "io"` and `import "math"` mean the stdlib (L31), so a
local `io.a7` cannot be imported.

- Option 1 (recommended): new modules use the `std/` prefix only.
  `import "strings"` keeps meaning a local `strings.a7`.
- Option 2: every stdlib module also gets a bare name. A user file
  named `list.a7`, `path.a7`, `time.a7`, `sort.a7`, or `testing.a7`
  becomes unimportable.

```a7
strings :: import "std/strings"   // stdlib under both options
strings :: import "strings"       // Option 1: local strings.a7. Option 2: stdlib
```

### U6. Lists: sharing, copying, growth failure

Today: no list type exists. L42 records "Share the same list" for
`b := a`. Copy spelling and failure behavior are open in L42.

- Proposed: `list.copy(a)` is the copy spelling. `list.push` stops the
  program with a message when memory runs out; `list.try_push` returns
  `bool` for programs that must recover (gate M2).
- A function that returns a list returns the handle; the caller and
  the function share it. Nobody frees it by hand (L19).

```a7
a := list.make(i32)
list.push(a, 1)
b := a                 // same list
c := list.copy(a)      // independent
list.push(b, 2)
io.println("{} {}", list.len(a), list.len(c))   // 2 1
```

### U7. Unproven indexes inside the stdlib

Today: an index the prover cannot bound exits 6. A loop over two
slices fails on it (D7).

- Option 1 (recommended): stdlib code goes through `slices.at` and
  `slices.put` (3.2). They are ordinary A7, they compile today, and
  they are public, so user code gets the same tool. Each access costs
  one compare in every build profile, which is the checked execution
  L39 allows.
- Option 2: bundled std files compile in a mode where unproven indexes
  become runtime-checked and stop the program. User code keeps exit 6.
  Two rule sets.
- Option 3: wait for the prover (R14, R15) and ship the affected
  functions as Zig hooks until then.

```a7
// Today: exits 6 at dst[i]
while i < dst.len {
    if i < src.len {
        dst[i] = src[i]
    }
    i += 1
}
// Option 1: compiles and runs today
while i < dst.len {
    ok := slices.put(dst, i, slices.at(src, i, 0))
    i += 1
}
```

### U8. String length and bytes

Today: `s.len` exits 6 (STATUS:152 lists the rejection as deliberate).
A string cannot become `[]u8`. The only way to count is
`for ch in s { n += 1 }`.

- Option 1 (recommended): `strings.len(s)` and
  `bytes.from_string(s)` as hooks. No field on `string`.
- Option 2: allow `s.len` like slices (`xs.len` works today).

```a7
n := strings.len(name)   // Option 1
n := name.len            // Option 2
```

### U9. Arguments before `string` payloads work

Today: `match os.arg(1) { case .some(name): ... }` cannot compile
(D11), whatever `os.arg` does.

- Option 1 (recommended): phase A ships `os.arg_or(1, "default")` and
  `os.env_or("HOME", "")` only. `os.arg` arrives with R5.
- Option 2: hold `std/os` until R5.

```a7
name := os.arg_or(1, "world")   // Option 1, phase A
```

### U10. May a project replace a stdlib module?

Today: a file at `<entry>/stdlib/std/strings.a7` is found before any
bundled module (and no bundled module exists). Probe D1 used this.

- Option 1 (recommended): `std/...` always means the shipped module.
  A project file at that path is ignored with a warning, or is an
  error.
- Option 2: project files win, so a project can patch the stdlib.

```a7
strings :: import "std/strings"
// Option 1: always a7's own strings module
// Option 2: ./stdlib/std/strings.a7 if the project has one
```

### U11. Confirm the "never" and "later" list

Today: the roadmap marks TOML "NEVER", regex "library-only", crypto
"wrapper-only", async syntax "never". The ledger holds no approval
for these (`ledger-audit.md`, last table row). JSON and YAML left this
list on 2026-10-04 (see U13).

Question: for each row of the section 1 table marked "None", say
approved, not approved, or decide later. Example of one row: under
"TOML never", a program that must read `Cargo.toml`-style files has no
stdlib module for it and no `std/toml` is ever added; it reads JSON or
YAML instead.

### U12. How hooks are declared

Today: a hook is a Python dict entry with no types
(`a7/stdlib/io.py`). The checker hard-codes each family.

- Option 1 (recommended): typed registry entries (section 4). No A7
  syntax change. Users cannot add hooks.
- Option 2: an A7 declaration form for external functions, which also
  serves the L41 native interface later. New syntax, own packet.

```a7
// Option 2 sketch, not valid today
now_unix_ms :: extern fn() i64
```

### U13. How much YAML

Today: no YAML module exists, and roadmap B8 says "YAML/TOML NEVER".
Your message of 2026-10-04 asks for a YAML parser.

- Option 1 (recommended): the subset in 3.22. Anchors, aliases, tags,
  merge keys, and multi-document files are rejected with a line
  number.
- Option 2: full YAML 1.2, including anchors and aliases. Aliases
  need a size limit to stop one small file from expanding without
  bound, and the document stops being a tree.

```yaml
# Option 1 and 2 both read this
server:
  port: 8080
  hosts: [a, b]
# Option 1 rejects this with "unsupported at line 2"; Option 2 reads it
base: &b {port: 8080}
dev: *b
```

Also needed from you: one line for the ledger that records JSON and
YAML as v1 stdlib modules, since the roadmap row says the opposite.

### U14. JSON and YAML: events first, or wait for the tree

Today: neither exists. A document tree needs growable lists, which
wait for the memory decision. An event reader needs nothing (D17).

- Option 1 (recommended): phase A ships the event readers and the
  JSON writer. Phase B adds `std/data` with `parse_json`/`parse_yaml`
  and key lookup.
- Option 2: ship nothing until the tree exists. One API, later.

```a7
// Option 1, phase A: walk events (ran today)
ev := json.next(r)
if ev.kind == Kind.Key {
    io.println("key at {}..{}", ev.start, ev.end)
}
// Phase B under both options: look up by key
match data.get(data.root(doc), "port") {
    case .some(v): { io.println("{}", data.text_or(v, "?")) }
    case .none: { io.println("no port") }
}
```

## 8. Risks and what I did not verify

Risks:

1. Phase A depends on PLAN.md Phases 0-2. Several stdlib bodies sit on
   known wrong-result bugs: uninitialized buffers (P2-42), dropped
   stdout on panic (P2-45), `1 << n` (P2-47), untyped constant wrap
   (P2-1; `hash` and `random` use large `u64` literals, which printed
   correct values in D13 with typed variables).
2. Stdlib code in A7 pays one compare per element access through
   `slices.at`/`put` (D15) until the prover handles two bounds (R15)
   and field-loaded indexes (R14). The cost against the L38 limit is
   not measured. If it fails that limit, hot loops (`copy`, `eq`,
   `sort`, the JSON and YAML readers) become Zig hooks.
3. L42 makes `List` a handle while structs stay values. Users will
   meet two assignment rules. The memory packet has to state this.
4. D4: until type names are scoped (R9), every public stdlib type name
   (`Order`, `Rng`, `Tally`, `FsErr`, `File`) is taken from every
   program that imports the module. A user struct named `File` would
   exit 6 after importing `std/fs`.
5. Zig 0.16 `std.Io` is new and differs from earlier releases. Hook
   bodies for files, clocks, arguments, and environment may need more
   Zig than the one-line lowerings named in section 3.
6. Zig analyses lazily. A bundled function nobody calls is never
   compiled by Zig, so a stdlib bug can ship unless the all-functions
   program in section 4 exists.
7. Front-end cost is linear in imported stdlib lines. Measured at
   241 lines only.
8. The roadmap's stdlib IDs B1-B8 collide with memory IDs B0-B3
   (PLAN.md P4-13). This file uses R, D, and U prefixes to avoid a
   third collision.

Not verified:

- Every statement about Zig std, Go, Odin, Rust, Hare, and C3 in
  section 2, and every Zig call name in section 3. From memory.
- No hook was written or compiled. All hook rows are designs. The
  `time`, `os`, `fs`, `path`, `conv`, and `utf8` examples ran against
  stub A7 modules with placeholder bodies; their printed output shows
  that the call and match shapes compile, not that the modules work.
- `strings.index_of_char` with the `Option(usize)` return, `shuffle`
  through `slices.swap`, and `slices.count` were not run.
- The cost of `slices.at`/`put` against direct indexing.
- The JSON reader ran on one 15-byte input. It does not validate
  (it accepts `tru!` as `true`, and commas anywhere). No YAML code ran;
  the YAML rows are signatures over stub bodies.
- YAML 1.2 rules quoted in 3.22 are from memory.
- Stub bodies prove that a signature parses and type-checks, not that
  the function can be implemented.
- Every `list`/`map` signature beyond parsing.
- Release-profile behavior beyond two programs: the D2 demo and the
  cross-module generic sort printed the same output under
  `a7 run --profile release`. All other runs used debug.
- `uv build` and wheel contents (D3 is from reading two files).
- PLAN.md rows cited as prerequisites were not re-run unless the
  table in section 5 names a probe.
- No pytest, no gate script, per the task rules.
- L42's interaction with arena-per-function lowering (roadmap A5): a
  list returned from a function must outlive that function's arena.
  Research 22 section 4 proposes a hidden caller-arena parameter; I
  did not evaluate it.
