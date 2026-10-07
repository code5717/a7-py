# A7 Programming Language Specification

This reference describes the current compiler where source and regression tests
establish behavior. Sections marked parsed-only, reserved, or proposed do not
promise executable programs. Approved rules that are not yet enforced are
identified separately.

The [project README](../README.md) and [release checklist](RELEASE.md) are the
user-facing authorities. [Status](STATUS.md) records implementation gaps, and
the [decision ledger](plan/decisions.md) records approvals. This document is not
a release qualification report. Examples are independent fragments unless they
include the imports and entry point needed to compile on their own.

## Table of Contents

1. [Introduction](#1-introduction)
2. [Lexical Structure](#2-lexical-structure)
3. [Type System](#3-type-system)
4. [Declarations and Expressions](#4-declarations-and-expressions)
5. [Control Flow](#5-control-flow)
6. [Functions](#6-functions)
7. [Generics](#7-generics)
8. [Memory Management](#8-memory-management)
9. [Planned Array Programming for AI](#9-planned-array-programming-for-ai)
10. [Modules and Visibility](#10-modules-and-visibility)
11. [Built-in Functions and Operators](#11-built-in-functions-and-operators)
12. [Tokens and AST Components](#12-tokens-and-ast-components)
13. [Grammar Summary](#13-grammar-summary)

---

## 1. Introduction

### 1.1 Language Overview

A7 is a statically typed procedural language. The Python compiler tokenizes,
parses, checks, and emits Zig source. Zig is the supported native backend.
The language has fixed arrays, slices, structs, tagged and untagged unions,
compile-time generics, and explicit heap allocation with `new` and `del`.

### 1.2 Design Philosophy

Design decisions and their compatibility boundaries live in the
[decision ledger](plan/decisions.md). File-module isolation is approved but
not yet implemented throughout the semantic pipeline. Tensor operations and
accelerator APIs are [design proposals](design/array-programming.md).
General lifetime and aliasing proofs remain outside the current
[safety contract](SAFETY_CONTRACT.md).

---

## 2. Lexical Structure

### 2.1 Source Encoding

A7 source files are UTF-8. A leading UTF-8 byte-order mark is stripped
before tokenizing (`a7/tokens.py:240-244`). The standard file extension
is `.a7`.

Identifiers, keywords, and numeric literals use ASCII characters only
(see §2.3 and §2.6). String and character literal contents and comments
may hold non-ASCII characters; the tokenizer passes them through and
later passes validate their range. For example, `"café"` lexes as one
string literal, while `café` outside a literal is rejected at the first
non-ASCII character.

**Whitespace Rules:**
- Spaces (U+0020) and carriage returns (U+000D) are skipped
- Tab characters (U+0009) are **not supported** and cause a lexical error
- Vertical tab (U+000B) and form feed (U+000C) are not whitespace: each is
  rejected as an unexpected character
- Newlines (U+000A) and `;` each produce a statement terminator token.
  Consecutive terminators collapse into one, so `;;`, blank lines, and a
  `;` at a line end contribute a single terminator

### 2.2 Comments

```a7
// Single-line comment extends to end of line

# Hash comments work the same way: to end of line

/*
   Multi-line comment
   /* Can be nested */
*/
```

`//` and `#` each start a line comment that runs to (but not including)
the newline; the newline still produces its terminator. `/*` opens a
block comment that may nest. An unterminated `/*` is a lexical error that
points at the comment's start instead of silently dropping the file.

### 2.3 Identifiers

```ebnf
identifier = ("_" | letter) (letter | digit | "_")*
letter     = "a"..."z" | "A"..."Z"  ; ASCII letters only
digit      = "0"..."9"              ; ASCII digits only
```

**Identifier Rules:**
- Identifiers are case-sensitive
- Must start with an ASCII letter (a-z, A-Z) or underscore
- Can contain ASCII letters, digits (0-9), and underscores
- **Unicode characters are not supported** in identifiers
- L27 approves file-private top-level `_name` and compiler-reserved `__name`.
  The tokenizer currently accepts both; module visibility enforcement remains
  incomplete. See §10.4 for the implementation boundary
- Maximum length: 100 characters

### 2.4 Keywords

Reserved words with grammar rules:

```
and        bool       break      case       char       continue   defer
del        else       enum       f32        f64        fall       false
fn         for        i8         i16        i32        i64        if
import     in         isize      match      new        nil        not
or         pub        ref        ret        string     struct     true
u8         u16        u32        u64        union      usize      while
```

Lexed as keyword tokens but consumed by no grammar rule yet:

```
as         where
```

`as` is reserved for a future cast spelling; today only `cast(T, v)` works.
`where` opens a generic constraint clause. Only conjunctions of set
memberships are current (`where T: Numeric`); richer predicates are
rejected (see §6.1 and §7.3).

Lexed but unused (kept for future use, rejected or ignored by the parser):

```
let        int        uint       float
```

Not keywords: `cast`, `const`, `self`, `size_of`, `type`, `using`, and `var`
lex as ordinary identifiers even though older drafts of this table listed
them. `using import "p"` and `cast(T, v)` work through identifier matching,
not keyword tokens. `not` is a keyword (prefix negation) that older drafts
of this table omitted. See PAR-22 in `docs/audits/2026-09-16/compiler/parser.md`.

### 2.5 Operators and Punctuation

```
// Arithmetic
+    -    *    /    %

// Comparison
==   !=   <    >    <=   >=

// Logical
and  or   not  !

// Bitwise
&    |    ^    ~    <<   >>

// Assignment
=    +=   -=   *=   /=   %=   &=   |=   ^=   <<=  >>=

// Generics
$    // Generic type parameter prefix

// Builtins
@    // Builtin function prefix (for example `@type_set`)

// Other
::   :    ;    ,    ()   []   {}   ..
```

`...` has no token: the tokenizer rejects it with an unsupported-operator
error, so `0...5` never lexes. Use `..` for slice bounds and variadic
parameters (§6.6). `?` likewise has no token and is rejected as an
unexpected character.

Write ASCII after `@` and `$`. Their continuation checks accept Unicode
alphanumerics (for example, `@café` lexes as one builtin token), unlike
identifier starts, which require ASCII. Non-ASCII spellings there have no
defined meaning.

Float `%` is remainder with a quotient truncated toward zero. Its nonzero result
has the dividend's sign. Constant folding follows the same rule as generated
Zig: `-5.5 % 2.0` is `-1.5`, and exact negative division preserves negative zero.
This does not relax the existing nonzero-divisor proof requirement.

Typed integer `/` truncates toward zero (backend `@divTrunc`). Typed
integer and float `%` take the dividend's sign (backend `@rem`; float `%`
uses `math.fmod`). The integer edges are defined in every build profile:
`MIN / -1` wraps to `MIN`, `MIN % -1` is 0, unary `-MIN` wraps to `MIN`,
and `math.abs(MIN)` is `MIN`. A shift by a run-time count that is negative
or at least the operand's bit width panics with "shift count out of
range" in every profile.

Constant arithmetic has one evaluator (`a7/exact_constants.py`) and one
rule, stated in §4.2.1: values are exact, and the result must fit its
destination. Nothing wraps and nothing rounds per operation. A constant
that does not fit its destination exits 6. Arithmetic on typed run-time
values is separate and keeps the wrapping rule above. A constant integer
division or remainder by zero stays for the divisor proof, which rejects
it; a constant float division or remainder by zero is a constant error.

Build profiles (`ZIG_OPTIMIZE_MODE` in `a7/backends/zig.py`): `debug`
compiles Zig with `-O Debug`, `release` with `-O ReleaseSafe`, and `fast`
with `-O ReleaseFast`. In `release` and `fast` the backend drops the
wrapping operator suffix only where the safety pass discharged a
`_nonwrap` proof, and `--no-nonwrap` keeps wrapping in every profile.
`release` keeps Zig's runtime checks. `fast` removes them, so an
operation whose proof is wrong is undefined behavior there.

### 2.6 Literals

#### Integer Literals
```a7
42        // Decimal
0x2A      // Hexadecimal
0o52      // Octal
0b101010  // Binary
1_000_000 // With separators
```

**Numeric Literal Limits:**
- Maximum numeric literal length: 100 characters (including separators)
- Underscores can be used as separators for readability. Placement is
  validated by the number conversion itself: `1__2` is rejected as an
  invalid numeric literal
- Prefixes are lowercase only: `0x`, `0o`, `0b`. `0X2A` lexes as `0`
  followed by the identifier `X2A`
- `0x` digits are `0-9 a-f A-F`; `0o` digits are `0-7`; `0b` digits are
  `0-1`. Each prefixed literal needs at least one digit after the prefix

#### Floating-Point Literals
```a7
3.14159
2.71e10
.5
1.
```

A float exponent (`e` or `E` with an optional sign) needs at least one
digit: `1e` is rejected, `1e+10` is a float. A `.` followed by another
`.` is not a decimal point: `1..5` lexes as `1`, `..`, `5`, while a
trailing `1.` before anything else is the float `1.`.

#### Character Literals
```a7
'a'
'\n'      // Newline
'\t'      // Tab
'\\'      // Backslash
'\''      // Single quote
'\x41'    // Byte escape for A
```

#### String Literals
```a7
"Hello, World!" // single line string
"Line 1\nLine 2"
"Quote: \"Hello\""
"Plain string"
```

Accepted escapes in character and string literals are `\n`, `\t`,
`\r`, `\\`, `\'`, `\"`, `\0`, and `\xHH`. Any other backslash escape
(including `\b`, `\f`, `\v`, and `\a`) is a lexical error. `\xHH`
needs exactly two hex digits (`\x4` is rejected). The tokenizer accepts
any two hex digits. A character literal holds one code point from 0 through
255; a larger code point is a lexical error. This byte range is checked by
[`test_char_literal_errors.py`](../test/test_char_literal_errors.py).

String literals hold at most 32,767 characters including both quote
characters. Longer literals are a lexical error.

#### Boolean Literals
```a7
true
false
```

#### Nil Literal
```a7
nil
```

**Usage**: `nil` can **only** be used with reference/pointer types (`ref T`). It represents a null pointer.

**Invalid**: Arrays, structs, primitives, and other value types cannot be assigned `nil`.

```a7
// Valid: nil with reference types
ptr: ref i32 = nil
fn_ptr: ref fn() = nil
if ptr == nil { }

// Invalid: nil with value types
arr: [5]i32 = nil      // ERROR: arrays cannot be nil
x: i32 = nil           // ERROR: primitives cannot be nil
s: MyStruct = nil      // ERROR: value structs cannot be nil
```

**Array Initialization**: Arrays must be initialized with:
- No initializer (zero-initialized, like every declaration without one): `arr: [5]i32`
- Single value (all elements): `arr: [5]i32 = 0`
- Array literal: `arr: [5]i32 = [1, 2, 3, 4, 5]`

Array literals must match the declared array length when a target type is
present. Each element is checked against the declared element type, including
nested array literals and literal arms selected by `if` or `match`. Generic
initializers and bound callback arguments apply those checks at each concrete
instantiation. Typed array values still require compatible element types;
a typed `[2]i32` does not narrow implicitly to `[2]i8`. In an `if` or `match`,
a concrete typed numeric array arm supplies the element type for literal arms
of the same shape.

---

## 3. Type System

### 3.1 Type Categories

A7's type system consists of:
1. **Value types**: Copied by value
2. **Reference types**: Point to memory locations
3. **Generic types**: Parameterized types

### 3.2 Primitive Types

| Type     | Size (bytes) | Range/Description |
|----------|--------------|-------------------|
| `bool`   | 1           | `true` or `false` |
| `i8`     | 1           | -128 to 127 |
| `i16`    | 2           | -32,768 to 32,767 |
| `i32`    | 4           | -2^31 to 2^31-1 |
| `i64`    | 8           | -2^63 to 2^63-1 |
| `isize`  | platform    | Signed pointer-sized integer |
| `u8`     | 1           | 0 to 255 |
| `u16`    | 2           | 0 to 65,535 |
| `u32`    | 4           | 0 to 2^32-1 |
| `u64`    | 8           | 0 to 2^64-1 |
| `usize`  | platform    | Unsigned pointer-sized integer |
| `f32`    | 4           | IEEE 754 single |
| `f64`    | 8           | IEEE 754 double |
| `char`   | 1           | Byte character (0-255) |

**Note**: `isize` and `usize` are platform-dependent types:
- On 32-bit platforms: 4 bytes (same as i32/u32)
- On 64-bit platforms: 8 bytes (same as i64/u64)

Use `usize` for sizes, lengths, capacities, allocation byte counts, and array/slice/string indices. It is the memory-shape integer and maps directly to Zig `usize`.

Use `isize` only for signed pointer-sized offsets or differences between positions. It exists for pointer-adjacent signed math, not as the default signed integer type.

Use fixed-width integers such as `i32`, `i64`, `u32`, or `u64` when the data itself has that width or range. Small arithmetic examples may use `i32`; counters and indexes should usually use `usize`.

### 3.3 Composite Types

#### Arrays
```a7
// Fixed-size array
arr: [10]i32
matrix: [3][3]f64

// Element-wise addition for same-shape numeric fixed arrays
a: [4]f64 = [1.0, 2.0, 3.0, 4.0]
b: [4]f64 = [5.0, 6.0, 7.0, 8.0]
c: [4]f64
c = a + b
```

`T.len` and `T.element` are proposed type introspection, not implemented
array properties. Create a slice to read its `.len`; the checker currently
provides `.len` and `.ptr` on slice values, not fixed-array values.

#### Slices
```a7
// Dynamic view into array
slice: []i32

// Slice properties
slice.ptr      // Pointer to first element
slice.len      // Number of elements (usize)
```

#### Strings
```a7
// UTF-8 source string literal
name: string = "Hello"

// String slicing produces a []char byte slice
part := name[1..4]

// Historical representation sketch, not a current user-defined type alias
string :: struct {
    ptr: ref u8
    len: usize
}
```

#### References (Pointers)
```a7
// Single indirection
ptr: ref i32

// Multiple indirection
ptr_ptr: ref ref i32

// Function pointer
fn_ptr: ref fn(i32, i32) i32

// Ref parameters can modify caller storage through typed lowering
x := 42
set_to_100 :: fn(value: ref i32) {
    value = 100
}
set_to_100(x)
```

#### Structs
```a7
Person :: struct {
    name: string
    age: u32
    height: f32
}

// Nested structs
Employee :: struct {
    person: Person
    id: u64
    salary: f64
}
```

#### Unions
```a7
Number :: union {
    i: i32
    f: f32
    u: u32
}

value := Number{i: 42}
same_value: i32 = value.i

// Tagged union (discriminated)
Result :: union(tag) {
    ok: i32
    err: string
}
```

Untagged unions use `Type{field: value}` literals with exactly one named field.
The named field must exist and its value must be assignable to that field type.
Field access type-checks against the declared union fields. Tagged unions
match through leading-dot arms: `case .tag:` tests the tag and
`case .tag(name):` binds a copy of the payload (see §5.2). Only
copyable payloads bind.

#### Enums
```a7
// Simple enumeration
Color :: enum {
    Red,    // 0
    Green,  // 1
    Blue    // 2
}

// With explicit values
StatusCode :: enum {
    Ok = 200,
    NotFound = 404,
    Error = 500
}
```

An enum with explicit values uses the first Zig tag type in `i32`, `u32`,
`i64`, `u64` that holds every variant. An omitted value is the previous value
plus one. For example, `Big :: enum { A = 4294967295, B }` needs `i64` because
`B` is 4294967296. Values up to 18446744073709551615 use `u64` when the whole
enum fits that unsigned range. If no single supported tag type fits all
variants, code generation rejects the enum. Enums without explicit values let
Zig choose the tag width. See
[`test_enum_tag_types.py`](../test/test_enum_tag_types.py) for compiler/native
cases and the separate backend-only rejection check.

### 3.4 Type Aliases

```a7
// Simple alias
Handle :: u64

// Generic alias
Vector :: [3]f32
Matrix :: [4][4]f32
```

An alias whose right side is a bare user-defined name (for example
`Handle :: MyInt`) is a constant value alias, not a type alias. Only
primitive, `ref`, generic-parameter, and bracket type spellings form
type aliases.

### 3.5 Reference Semantics

```a7
// Ref parameters use ordinary lvalue arguments
x := 42
set_to_100 :: fn(value: ref i32) {
    value = 100  // OK: modifies the caller's storage
}
set_to_100(x)

Counter :: struct {
    value: i32
}

increment :: fn(counter: ref Counter) {
    counter.value += 1  // OK: checked field access through ref
}
```

Public address-of and dereference operators are not part of A7. The compiler
inserts internal reference operations only where a typed construct requires
them, then proves the operation safe before Zig codegen.

---

## 4. Declarations and Expressions

### 4.1 Variable Declarations

```a7
// Immutable binding (constant) - use ::
PI :: 3.14159

// Mutable bindings (variables) - use := or name: T
count := 0
age: i32 = 25    // Explicit type, initialized
name := "John"   // Inferred as string
buffer: [1024]u8 // Explicit type, no initializer: all zeros

// Multiple declaration/destructuring syntax is planned, not current:
// a, b, c: i32 = 1, 2, 3
// x, y := 10, 20
```

### 4.2 Declaration Rules

**One rule: `::` is immutable; `:=` and `name: T` are mutable:**

- `::` - Creates immutable bindings (constants)
- `:=` - Creates mutable bindings with inferred type
- `name: T [= value]` - Creates mutable bindings with explicit type

```a7
// Constants (immutable) - use ::
PI :: 3.14159
MAX_BUFFER :: 1024
VERSION :: "1.0.0"
DOUBLE_PI :: PI * 2

// Variables (mutable) - use := or name: T
count := 0
name := "John"
buffer: [1024]u8

// Explicit typing is always mutable
MAX_SIZE: i32 = 1000    // Mutable with explicit type
counter: i32 = 0        // Mutable with explicit type

// Variables can be reassigned
counter = counter + 1   // OK
// PI = 3.0             // ERROR: cannot reassign constant

// Example using logical operators
valid := count > 0 and count < 100
should_process := valid or force_mode
can_exit := !running and cleanup_done
```

### 4.2.1 Untyped numeric constants

This section describes implemented exact arithmetic and destination fitting.
See [the packet](plan/packets/P-TYP-forward-globals.md) for the approved contract
and Appendix C for resource requirements whose enforcement remains incomplete.

Numeric literals and numeric `::` bindings made entirely from supported constant
expressions retain their exact value until a use needs a concrete type. A use
does not choose a type for other uses of the same constant. Global dependencies
resolve before function bodies, so declaration order does not change fitting.
Local declarations keep their existing visibility rules.

```a7
RATE :: 2.0
small: u8 = RATE
wide: i64 = RATE
runtime := RATE       // Concrete f64
```

An integer destination accepts a constant only when its value is integral and
within range. `2.0` fits `i32`; `2.5`, `256` into `u8`, and `-1` into `usize`
reject. Implicit fitting never truncates or wraps. `usize` and `isize` use the
compilation target's pointer width.

Runtime float-to-integer conversion still requires an explicit checked
cast, and the range proof is literal-only: the safety pass accepts a
`FLOAT`-literal operand that is finite, integral, and within the target
range (`a7/passes/safety.py:1036-1043`, enforced at lines 903-904) and
rejects anything else with "float-to-int cast requires finite integral
range proof". The backend lowers an approved cast to `@intFromFloat`
(`zig.py:2047`). Non-literal float-to-int proofs are future work; no
program relying on them is accepted today.

A float destination rounds the exact value directly to `f32` or `f64`, nearest
with ties to even. It preserves signed zero and permits subnormal values and
underflow to zero. A finite value that would round to infinity rejects. Ordinary
typed math calls can still produce infinity or NaN. For example,
`INF :: math.exp(1000.0)` retains the call's concrete result type after importing
`std/math` as `math`.

Wholly untyped arithmetic uses exact values. `+`, `-` and `*` do not wrap or round.
With integer-category operands, `/` truncates toward zero. A floating-category
operand makes `/` exact rational division. Thus `5 / 2` is 2 even when assigned
to `f64`, while `5.0 / 2` is 2.5. Remainder is `a - trunc(a / b) * b`. Division
and remainder by zero reject: the float case as a constant error, the
integer case through the divisor proof. A floating zero result keeps the
IEEE sign: `0.0 * -1.0` is negative zero. Comparisons use exact values, so
`0.1 + 0.2 == 0.3` is true. `1e400 == 1e400` can be true without fitting either
operand to `f64`.

Untyped bitwise operations require integer-category operands. A spelling such
as `2.0` remains in the floating category even though its value is integral.
Untyped shifts require a nonnegative integer-category count. Left shift
multiplies exactly by a power of two; right shift preserves the sign, so
`-3 >> 1` is -2. Bitwise `~` is a typed operator and is not folded as an
untyped constant. Compiler resource limits still apply: a float literal
exponent above 4,096 or a constant wider than 131,072 bits exits 6.

An inferred runtime value defaults to `i32` for the integer category or `f64`
for the floating category. Formatting and generic inference without a concrete
numeric expectation use those same defaults. A large integer needs an explicit
destination, such as `value: i64 = 9007199254740993`, before formatting.
Annotated variables, fields, parameters, returns and aggregate elements fit
directly to their declared type. Array lengths and indices require an integral
value fitting `usize`. Numeric patterns fit to the subject type.

Typed values remain typed. At a mixed numeric operation, fit the untyped operand
to its concrete peer before applying the existing typed operation. This keeps
typed floating arithmetic and typed integer wrapping distinct from exact
constant arithmetic. Runtime float-to-integer conversion still requires an
explicit checked cast. `cast(T, value)` first gives an untyped operand its
category default, then applies the existing cast rules.

### 4.3 Expression Categories

#### Primary Expressions
- Identifiers: `x`, `foo`
- Literals: `42`, `"hello"`, `true`
- Parenthesized: `(x + y)`

#### Postfix Expressions
- Array subscript: `arr[i]`
- Slice: `arr[1..5]`, `arr[..3]`, `arr[2..]`
- Field access: `point.x`
- Function call: `max(a, b)`

Method-call sugar such as `vec.length()` is planned syntax, not current
semantic support. Use explicit functions such as `length(vec)`.

#### Unary Expressions
- Negation: `-x`
- Logical NOT: `!flag`
- Bitwise NOT: `~bits`

**Note**: Logical operators use keywords:
- `and` for logical AND (not `&&`)
- `or` for logical OR (not `||`)
- `!` for logical NOT

#### Binary Expressions
Precedence (highest to lowest):
1. `*`, `/`, `%`
2. `+`, `-`
3. `<<`, `>>`
4. `<`, `>`, `<=`, `>=`
5. `==`, `!=`
6. `&`
7. `^`
8. `|`
9. `and`
10. `or`

#### Cast Expressions
```a7
// Explicit cast
x := cast(f64, 42)

// Generic cast
y := cast(T, value)
```

---

## 5. Control Flow

### 5.1 Conditional Statements

```a7
// Simple if
if condition {
    // code
}

// If-else chain
if x < 0 {
    print("negative")
} else if x > 0 {
    print("positive")
} else {
    print("zero")
}

// Conditional expression
result := if x > 0 { x } else { -x }

// Complex conditions with and/or
if age >= 18 and age <= 65 {
    print("Working age")
}

if name == "admin" or permissions.admin {
    allow_access()
}

// Nested logical operators
if (x > 0 and x < 100) or (y > 0 and y < 100) {
    print("In bounds")
}
```

Struct literals are not parsed in `if`/`while` conditions, even nested inside
call arguments: bind the value first (`p := Pt{x: 1}`) and test the variable.
See STATUS Known Gaps.

### 5.2 Pattern Matching

```a7
// Match on enum values
match color {
    case Color.Red: {
        print("Red")
    }
    case Color.Green: {
        print("Green")
        fall  // Continue into the next case body; must be final in a non-final case
    }
    case Color.Blue: {
        print("Green or Blue")
    }
}

// Match on literal values
match x {
    case 0: print("zero")
    case 1, 2, 3: print("small")
    case 4..10: print("medium")
    else: print("large")
}

// Match on tagged-union tags with leading-dot arms
r := Result{ok: 1}
out := match r {
    case .ok(v): v + 1    // binds a copy of the payload
    case .err(e): e
}

// A bare tag tests without binding; else opts out of exhaustiveness
match r {
    case .ok(v): print(v)
    case .err(e): print(e)
    else: print("other")
}

// Identifier capture patterns
score :: fn(x: i32) i32 {
    ret match x {
        case value: value + 1  // value is branch-local and has type i32
    }
}
```

An identifier pattern refers to an existing visible symbol when one exists,
which preserves constant/value-pattern matching. If no visible symbol with that
name exists, the identifier is a capture pattern: it matches the scrutinee,
binds an immutable branch-local value with the scrutinee type, and covers all
remaining values like `_`. A capture pattern must be the only pattern in its
case.

A leading-dot arm names a tag of the scrutinee's tagged union type.
`case .tag:` tests the tag without binding. `case .tag(name):` binds
a copy of the payload to a branch-local immutable. There is no
`.tag(_)` form. A bare `case tag:` over a tagged union is an exit-6
error; write the dot. A match with uncovered tags and no `else`
reports one exit-6 error listing each missing tag. Only copyable
payloads bind: binding a `string` payload exits 6. Test-only arms over
owning payloads stay allowed. Untagged unions and non-union
scrutinees keep the prior rules.

A statement `match` stores its `else` body as a statement list (`else_case`);
an expression `match` stores one expression (`else_expr`). JSON output exposes
both field names. See STATUS Known Gaps.

### 5.3 Loops

```a7
// Infinite loop
for {
    if should_stop() { break }
}

// While loop
while condition {
    // code
}

// C-style for loop
for i := 0; i < 10; i += 1 {
    print(i)
}

// Range loop
for value in array {
    print(value)
}

// Range with index
for i, value in array {
    printf("[{}] = {}\n", i, value)
}
// The index variable `i` has type `usize`.

// Range over slice
for char in string[2..5] {
    print(char)
}
// string[2..5] has type []char.

// Complex conditions using and/or
while running and not should_exit() {
    process_events()
}

for i := 0; i < 100 and valid; i += 1 {
    if check_condition(i) or force_exit {
        break
    }
}
```

### 5.4 Jump Statements

```a7
// Return from function
ret value

// Break from loop
break

// Continue to next iteration
continue

// Break/continue with loop label
@outer for i := 0; i < 10; i += 1 {
    for j := 0; j < 10; j += 1 {
        if condition {
            break outer
        }
    }
}
```

Loop labels use `@name` directly before a loop statement. The old
`name: for ...` spelling is rejected because `name:` is reserved for typed
bindings, fields, and case-like syntax.

Semantic validation reports unreachable statements that appear later in the same block after `ret`, a valid `break` or `continue`, `fall`, or an `if`/`match` statement whose branches all terminate.

---

## 6. Functions

### 6.1 Function Declarations

```a7
// Basic function
add :: fn(x: i32, y: i32) i32 {
    ret x + y
}

// Void function
print_number :: fn(n: i32) {
    printf("{}\n", n)
}

// Return struct for multiple values
DivModResult :: struct {
    quotient: i32
    remainder: i32
}

divmod :: fn(a: i32, b: i32) DivModResult {
    ret DivModResult{a / b, a % b}
}

// Named fields in return struct
sincos :: fn(angle: f64) struct { sin: f64, cos: f64 } {
    ret struct { sin: f64, cos: f64 }{
        sin: math.sin(angle),
        cos: math.cos(angle)
    }
}

// Current generic value function
identity :: fn(value: $T) $T {
    ret value
}

// Current minimal form: conjunction of set memberships
add :: fn(a: $T, b: $T) $T where T: Numeric {
    ret a + b
}

// Current: several bounds, comma-separated
first :: fn(a: $T, b: $U) $T where T: Numeric, U: Numeric {
    ret a
}

// Current: inline type set as a bound
f :: fn(a: $T) $T where T: @type_set(i32, i64) {
    ret a
}

// Rejected with exit 6: richer predicates (`where T == i32`,
// `where true`), unknown names, `$T` in the bound, bounds on value
// params, non-set bounds, and `where` on enums.
```

#### Nested functions

A function may declare and call a nested function that captures no enclosing
locals or parameters. Each nested body receives type and control-flow checks.
The Zig backend emits these functions at file scope under distinct names.
Reading an enclosing local or parameter currently fails during code generation
with exit 7 and advice to pass it as a parameter. A nested function's own
parameter may reuse an enclosing name.

```a7
outer :: fn(k: i32) i32 {
    helper :: fn(v: i32) i32 { ret v + 1 }
    ret helper(k)
}
```

Returning a capture-free nested function as a function value is also supported.
See [`test_nested_functions.py`](../test/test_nested_functions.py) and
[`test_nested_function_codegen.py`](../test/test_nested_function_codegen.py).

### 6.2 Recursion

Recursion is not part of A7. A function may not call itself directly, and
groups of functions may not call each other in a cycle. Semantic validation
also rejects common indirect cycles through local function-pointer aliases and
higher-order callback trampolines before backend code generation.

Use loops, explicit stacks, or index-based worklists for repeated work.

```a7
// ERROR: direct recursion is rejected
factorial :: fn(n: i32) i32 {
    if n <= 1 {
        ret 1
    }
    ret n * factorial(n - 1)
}

// ERROR: callback trampolines cannot hide recursion
call_it :: fn(f: fn(i32) i32, n: i32) i32 {
    ret f(n)
}

countdown :: fn(n: i32) i32 {
    if n <= 0 {
        ret 0
    }
    ret call_it(countdown, n - 1)
}

// OK: iterative rewrite
factorial_iter :: fn(n: i32) i32 {
    result := 1
    for i := 2; i <= n; i += 1 {
        result *= i
    }
    ret result
}
```

### 6.3 Function Parameter Immutability

**All value function parameters in A7 are immutable by design.** `ref`
parameters can mutate the caller's storage, but the reference binding itself is
compiler-managed and not exposed as an assignable pointer value. The Zig
backend lowers a `ref T` parameter to `*T` with one null check at the
function boundary; nullable locals unwrap once at the same boundary,
and the body uses the pointer directly with no per-use unwrap.

```a7
// Parameters cannot be reassigned
bad_function :: fn(x: i32) i32 {
    x += 1  // ERROR: cannot modify parameter
    ret x
}

// Ref parameters can modify caller storage
increment :: fn(x: ref i32) {
    x += 1
}

// To work with a mutable copy, create a local variable
good_function :: fn(x: i32) i32 {
    local_x := x      // Create mutable local copy using :=
    local_x += 1      // OK: modifying local variable
    ret local_x
}

// Usage example
main :: fn() {
    value := 10
    increment(value)  // Passes value by checked reference
    printf("Value: {}\n", value)  // Prints: Value: 11
}
```

### 6.4 Function Types

```a7
// Function pointer type
BinaryOp :: fn(i32, i32) i32

// Using function pointers
apply :: fn(op: BinaryOp, x: i32, y: i32) i32 {
    ret op(x, y)
}

result := apply(add, 10, 20)
```

### 6.5 Methods

Current implementation is limited. The examples in this section describe the
intended receiver model, not a fully runnable set. Use ordinary functions and
consult the language reference for verified reference-parameter forms.

```a7
// Methods are functions with receiver
Vec2 :: struct {
    x: f32
    y: f32
}

// Method declaration - receiver is immutable parameter
length :: fn(self: ref Vec2) f32 {
    ret sqrt(self.x * self.x + self.y * self.y)
}

// Method that modifies the receiver
normalize :: fn(self: ref Vec2) {
    len := sqrt(self.x * self.x + self.y * self.y)
    self.x /= len  // OK: modifying through checked reference field access
    self.y /= len
}

// Explicit receiver call
v := Vec2{3.0, 4.0}
len := length(v)
normalize(v)      // Modifies v through checked reference
```

### 6.6 Variadic Functions

> **Implementation Status**: Variadic parameter syntax is parsed and partially
> type-checked for declarations, but runtime iteration and ABI lowering are not
> implemented. Codegen modes reject variadic parameters before backend emission;
> do not treat variadic functions as runnable current syntax.

```a7
// Planned shape: variadic parameters must be last
sum :: fn(values: ..i32) i32 {
    total := 0
    for val in values {
        total += val
    }
    ret total
}

// Type-safe printf
printf :: fn(format: string, args: ..)
```

---

## 7. Generics

### 7.1 Generic System Design

A7 uses a simple generic system where type parameters are compile-time constants with **inline declaration syntax**.

**Core Principles:**
- `$T` is used **inline** within type expressions to declare and reference generic types
- The same `$T` syntax is used everywhere - no separate declaration vs reference syntax
- Generic types are inferred from usage context at compile time
- Constraints are a semantic analysis feature for declared generic functions

**Generic Type Parameter Syntax Rules:**
- Must start with `$` followed immediately by a letter (a-z, A-Z)
- Digits and underscores are accepted after the initial letter: `$T1` and
  `$MY_TYPE` are valid; `$123` is invalid
- The tokenizer uses Unicode-aware letter and alphanumeric checks after `$`;
  use ASCII spellings for the documented language forms
- Standalone `$` is invalid and produces a compilation error

```a7
// Generic ref swap is not currently supported. Reading/reassigning ref
// parameters does not provide general value-copy swap semantics.

// Generic function with return type
identity :: fn(x: $T) $T {
    ret x
}

// Generic function - type inferred from first argument
abs :: fn(x: $T) $T {
    ret if x < 0 { -x } else { x }
}

// Multiple generic type parameters
pair :: fn(first: $T, second: $U) {
    x := first
    y := second
}

// Planned broader composite propagation; not backend-complete yet.
first :: fn(arr: []$T) $T {
    ret arr[0]
}
```

Generic local initializers must fit each concrete instantiation. This includes
literal arrays and scalar `if`/`match` results. Branches containing array
literals do not yet receive every nested contextual fit. For example, `z: $T = 0` cannot be
instantiated as `string`, and a branch producing 300 cannot fit an i8 destination.
A typed integer value does not gain an implicit narrowing conversion merely
because another branch is an untyped constant.

A function-valued parameter has the concrete signature selected by its enclosing
instantiation. Calls through its local aliases, assignments and `if`/`match`
selections keep that signature. They do not infer a fresh type parameter at each
callback call. Generic function declarations remain separate: aliasing one does
not bind its otherwise unresolved type parameters. Callback provenance through
record fields and array elements remains incomplete; see [Status](STATUS.md).

### 7.2 Generic Types

Generic structs and unions use inline `$T` syntax in their field types:

```a7
// Generic struct - $T used inline in field types
Pair :: struct {
    first: $T,
    second: $U,
}

// Usage - specify concrete types at instantiation
p := Pair(i32, string){first: 42, second: "answer"}

// Generic box
Box :: struct {
    value: $T,
}

// Nested generic instantiation
nested: Box(Box(i32))

// Generic union
Result :: union {
    ok: $T,
    err: $E,
}

// Generic tagged union - specializes positionally like a struct
TResult :: union(tag) {
    ok: $T,
    err: $E,
}
r := TResult(i32, string){ok: 1}
```

A generic `union(tag)` takes its concrete types positionally, in field
order: `TResult(i32, string)` binds `$T` to `i32` and `$E` to
`string`. Field access on the instance resolves to the bound type. A
wrong field type or an unknown field exits 6. Conflicting `$T`
bindings at one call site exit 6 (`GENERIC_PARAM_MISMATCH`). Generic
enums are out of scope: enum variants have no payload types to specialize.
Use a tagged union for payload-bearing alternatives.

`$N` value parameters accept their declared scalar kind, including `usize`,
`bool`, and small integer types. Structs and unions instantiate from named
constants, such as `Buf(SIZE)` with `SIZE :: 4`. The backend emits value
parameters with their declared Zig type, such as `comptime N: usize`.
[`test_generics_value_param_codegen.py`](../test/test_generics_value_param_codegen.py)
covers named constants, local constants, struct literals, and reference
parameter types. Literal value arguments do not parse, and function calls
cannot infer `$N`; see
[`test_generics_value_params.py`](../test/test_generics_value_params.py).

### 7.3 Type Sets and Constraints

> **Implementation Status**: Type-set syntax is implemented for predefined sets,
> local `@type_set(...)` aliases, and inline constraints on declared generic
> functions. Inferred call arguments are checked against declared type sets.

Type sets are defined using the `@type_set()` builtin function:

```a7
// Built-in type sets (will be defined in standard library)
Numeric :: @type_set(i8, i16, i32, i64, isize, u8, u16, u32, u64, usize, f32, f64)
Integer :: @type_set(i8, i16, i32, i64, isize, u8, u16, u32, u64, usize)
Float :: @type_set(f32, f64)
Signed :: @type_set(i8, i16, i32, i64, isize, f32, f64)
Unsigned :: @type_set(u8, u16, u32, u64, usize)

// Custom type sets
SmallInts :: @type_set(i8, u8, i16, u16)
BigInts :: @type_set(i64, u64)
```

**Current Constraint Syntax**:
```a7
abs($T: Numeric) :: fn(x: $T) $T {
    ret if x < 0 { -x } else { x }
}

min($T: Numeric) :: fn(a: $T, b: $T) $T {
    ret if a < b { a } else { b }
}
```

A `where` clause states the same bounds after the signature, as a
conjunction of set memberships. It works on generic fns, structs, and
unions:

```a7
add :: fn(a: $T, b: $T) $T where T: Numeric {
    ret a + b
}

P($T) :: struct {
    x: $T,
} where T: Numeric
```

Each bound resolves like a declared `$T: Set` constraint (predefined
sets, inline `@type_set(...)`, local aliases). Richer predicates,
unknown names, duplicate bounds, bounds on value params, non-set
bounds, and `where` on enums exit 6.

### 7.4 Generic Specialization

```a7
identity($T) :: fn(value: $T) $T {
    ret value
}

main :: fn() {
    a := identity(7)
    b := identity("ok")
}
```

Generic functions are specialized from concrete call sites in Zig output.
Broader composite generic specialization and deeper propagation through
method-style call chains remain implementation work.

Two functions with the same name exit 6 (`ALREADY_DEFINED`), whatever
their signatures. A7 has no function overloading.

---

## 8. Memory Management

### 8.1 Stack Allocation

All local variables are stack-allocated by default:
```a7
example :: fn() {
    x := 42            // Stack
    arr: [100]f32      // Stack
    person: Person     // Stack
}  // All automatically freed
```

### 8.2 Heap Allocation

```a7
Box :: struct {
    value: i32
}

// Allocate a heap struct
box := new Box
if box == nil {
    ret
}
box.value = 42
del box

// Heap fixed arrays are not current syntax. Use stack arrays or slices.
buffer: [1024]u8
slice := buffer[0..1024]

// Initialize fields through the returned reference
point := new Point
if point == nil {
    ret
}
point.x = 10
point.y = 20
del point

// `new T(args...)` and `new T{...}` initializer forms are not current syntax.

// Check allocation
large := new Point
if large == nil {
    // Handle allocation failure
}
```

Release builds allocate through `std.heap.smp_allocator`. Debug builds allocate
through `std.heap.page_allocator`. Allocation failure behavior is unchanged.

### 8.3 Defer Statement

```a7
// Defer executes at scope exit
{
    file := open("data.txt")
    defer close(file)

    point := new Point
    defer del point

    // Use file and buffer
    // Both cleaned up automatically
}

// Defer order is LIFO
{
    defer print("3")
    defer print("2")
    defer print("1")
    // Prints: 1 2 3
}
```

### 8.4 Memory Safety Status

Current implementation:

1. `new` and `del` parse, type-check, and lower for the implemented backends.
2. `del` is validated for reference-like values. Direct reference aliases share
   allocation deletion state; repeated deletion and reads after deletion fail
   until reassignment to a fresh allocation.
3. `defer del value` can express manual cleanup at scope exit.
4. Reference fields require a non-nil proof. A user field named `ptr` receives
   the same check. Field guards follow assignments and known call effects.

Not yet implemented:

1. Ownership, borrowing, or lifetime analysis that proves absence of dangling pointers.
2. Complete alias tracking through array elements and fields reached through
   joined allocation sets. These gaps prevent a general double-free or
   use-after-free safety claim.
3. General array/slice bounds-check insertion by the A7 compiler.

---

## 9. Planned Array Programming for AI

Tensor APIs, broadcasting, automatic differentiation, GPU movement, and
performance annotations remain proposals. Their historical examples now live
in the [array programming proposal](design/array-programming.md). They are not
accepted A7 syntax. Current fixed-array behavior is described in §3.3.

---

## 10. Modules and Visibility

### 10.1 File-Based Module Model

Every A7 source file is a module. There is no explicit `module` keyword. The
current backend lowers supported file-backed imports into the same generated
Zig file; A7 multi-file support is a frontend/module feature, not separate
object linking.

```a7
// File: vector.a7
// This file is automatically the "vector" module

// Public export
pub Vec3 :: struct {
    x: f32
    y: f32
    z: f32
}

// Public function
pub dot :: fn(a: Vec3, b: Vec3) f32 {
    ret a.x * b.x + a.y * b.y + a.z * b.z
}

// Approved private-name spelling; enforcement is incomplete, see §10.4
_value :: 7
```

### 10.2 Import Statements

```a7
// Current backend-lowered virtual stdlib imports
math :: import "std/math"
io :: import "std/io"

// Aliases are supported for virtual stdlib imports
console :: import "std/io"

// Resolver-only selected import metadata; not backend-runnable yet
import "vector" { Vec3, dot }

// Planned syntax; the parser accepts it but `using` is currently dropped,
// so it has no using semantics yet (see STATUS Known Gaps)
// using import "vector"

// Local aliases lower into the same generated Zig output for simple calls
sibling :: import "./sibling"
subfolder :: import "subfolder/helper"

// From a nested importer, allowed if utils remains inside the entry folder
parent :: import "../utils"
```

- Importing the same file twice in one file is a compile error, even through
  alternate spellings or symlinks. Different files may import the same file.
- An import alias conflicting with an existing definition in the same scope
  fails name resolution. Under L28, a local binding cannot reuse an import
  alias from its own file, including a stdlib alias. This check covers
  parameters, loop bindings and match captures. Record fields and aliases in
  other files do not reserve local names. Full per-file scopes remain unfinished.
- `using import` and selected imports are parser/resolver metadata. Their
  presence in the AST does not establish runnable backend support.

### 10.2.1 Module identity and resolution

The resolver first recognizes virtual stdlib spellings, including `io`,
`std/io`, `math`, and `std/math`. Other imports resolve relative to the
importing file, first as `<path>.a7`, then through the retained
`<path>/mod.a7` directory fallback. A nested file's `import "helper"` does
not fall back to the entry directory.

Resolved file paths must stay inside the entry file's folder. Parent segments
such as `../shared` are allowed within that boundary. Symlinks and parent paths
that escape it are rejected, as are absolute paths, backslashes, null bytes,
and empty paths. Canonical real paths identify loaded files, duplicate imports,
and cycles. A diamond import shares one loaded dependency even when its two
importers use different relative spellings.

The mechanisms are in [`a7/module_resolver.py`](../a7/module_resolver.py).
[`test_module_path_identity.py`](../test/test_module_path_identity.py) covers
relative bases, containment, alternate spellings, cache reuse, and cycle retry.
Hardlink identity is not specified by this realpath rule.

### 10.2.2 Cycles and entry

- Import cycles are distinct from call recursion. An import cycle
  (`A -> B -> A` at load time) is a compile error raised during module
  loading by the canonical-identity active set in `ModuleResolver.load_module`.
  A7 source recursion (a function calling itself, directly or through a
  cycle of calls) is a separate, banned construct rejected by semantic
  validation, not by the module loader.
- Entry-point rule: only the entry file is gated. An executable entry
  must define `main :: fn()` with no parameters and no return value; a
  missing or misshaped `main` exits 6 at the Entry Point stage
  in `A7Compiler.compile_file_detailed`. Imported modules never need their own
  `main`. `a7 check --lib` checks a library file without an entry
  point; `build` and `run` still require one.
- Known gaps (unchanged behavior, stated so callers stop guessing): a
  bare entry-file call to a module function is rejected with exit 6
  naming the qualified spelling; module-qualified struct literals are
  follow-up work, as are selected imports and `using import` lowering
  (STATUS Known Gaps; `compile.py` `_annotate_file_module_calls` only
  marks alias-qualified `X.f(...)` and in-module bare sibling calls).

### 10.3 Standard Library Status

Current implementation:

- `std/io` and `io` are virtual modules backed by compiler/backend mappings.
- `std/math` and `math` are virtual modules backed by compiler/backend mappings.
- Virtual stdlib modules are registered through the module resolver and may be
  imported with arbitrary local aliases, for example
  `console :: import "std/io"`.
- Local file imports such as `./vector` can resolve from on-disk `.a7` files
  and simple alias-qualified function calls lower into the same generated Zig
  output file.

Planned, not implemented as public stdlib modules yet:

- `std/string`
- `std/mem`
- `std/collections`

### 10.4 Visibility Rules (staged intent)

L25-L31 and L69 approve these rules: each file has its own namespace,
`alias.name` accesses another file, top-level `_name` is private, and `__name`
is reserved for the compiler. Other top-level names are public. Struct fields
remain visible to importers under L29. `pub` on a field does not hide or expose
it differently.

The compiler still combines imported declarations for semantic analysis and
uses call annotations for supported file-module calls. It does not yet enforce
complete per-file isolation or underscore visibility. `pub` is accepted and
recorded, but current access checks do not implement the approved visibility
rule. Removing `pub`, selecting all-site `__` rejection, and changing import
forms require their separate compatibility dispositions in
[P-MOD](plan/packets/P-MOD-modules.md). L69 authorizes the per-file scope work;
these implementation gaps are not a request for another approval of L25-L31.

---

## 11. Built-in Functions and Operators

### 11.1 Builtin Functions

These functions are handled specially by the compiler and use the `@` prefix:

```a7
// Type sets
@type_set :: fn(types: ..type) TypeSet     // Create type set
```

The tokenizer/parser reserve additional intrinsic spellings, but they are not
semantically resolved or backend-lowered yet:

```a7
// Memory intrinsics
@size_of :: fn($T: type) usize             // Size in bytes
@align_of :: fn($T: type) usize            // Alignment requirement
@type_id :: fn($T: type) usize             // Unique type identifier
@type_name :: fn($T: type) string          // Type name as string

// Compiler intrinsics
@unreachable :: fn()                       // Mark unreachable code
@likely :: fn(cond: bool) bool             // Branch prediction hint
@unlikely :: fn(cond: bool) bool           // Branch prediction hint
```

### 11.2 Standard Library Functions

Generation 1 (current, virtual, backend-lowered): `io.print`,
`io.println`, `io.eprintln` lower to `__a7_stdout_print` /
`__a7_stderr_print` with the persistent-writer preamble in
`a7/backends/zig.py`. Recoverable I/O emission and its checker gap are
described below. `std/io` and `io` (likewise
`std/math` and `math`) are alternate public spellings of the same
virtual module (`a7/stdlib/__init__.py:11-16`). Current virtual
modules also provide math calls such as `math.sqrt`, `math.abs`,
`math.floor`, `math.ceil`, `math.sin`, `math.cos`, `math.tan`,
`math.log`, `math.exp`, `math.min`, and `math.max`. Typed math
spellings such as `sqrt_f32` and `sqrt_f64` are not callable; the
list below is a planned API shape.

Recoverable I/O (current emission, checker typing deferred):
`io.println_ok` prints like `io.println` as a statement
(`io.println_ok("n={}", 42)` prints `n=42`), and the backend builds a
`__a7_IoResult` union value (`ok: usize` byte count,
`err: __a7_IoErr`) that the statement discards. `io.read_line` takes a
byte slice (`io.read_line(buf[0..])`) and its backend helper reads
stdin bytes into it, returning the count the same way. The checker
still types every `std.io.*` call as void and still demands a format
string as the first argument, so matching on a `println_ok` call or
passing a buffer through the CLI exits 6 until the checker follow-up
types them as `Result`. `Option`/`Result` themselves are ordinary
user-declared generic unions with no builtin sugar: `Option(i32)` and
`Result(i32, i32)` instantiate positionally, and errors propagate
through explicit `match` only. There is no `?` operator. Library
`get`/`pop` and `or{}`/`use` sugar are deferred.

Generation 2 (planned API shape, not callable): the per-type print
family `print_i32`, `print_f64`, `printf`, `eprint`, `eprintln` listed
below. Note the deliberate `eprint` vs `eprintln` distinction: the
current backend provides `eprintln` only (stderr, newline); bare
`eprint` (stderr, no newline) exists solely in the planned list and is
not implemented. Likewise the current `io.print` is the virtual
single entry point, while `print :: fn(s: string)` in the list below
is the planned unqualified shape — the two generations must not be
conflated when reading the signatures that follow.

The Zig backend lowers current `std/io` calls to generated stdout/stderr print
helpers. Stdout helpers buffer through one persistent writer and flush at
program exit, before each stderr write, before a panic, and before a stdin
read. When stdout is a terminal they also flush at each newline. Stderr
helpers flush after each call. A write to a closed pipe ends the program
with exit status 0 and no message; any other formatting or write failure
panics instead of silently dropping output. Stdout and stderr remain separate streams, and stdout content
always precedes stderr content written after it.

The broader string, ASCII, memory, assertion, and allocation function list below
is planned API shape, not current implementation:

```a7
// Math functions (specific signatures, no generics)
abs_i32 :: fn(x: i32) i32
abs_i64 :: fn(x: i64) i64
abs_f32 :: fn(x: f32) f32
abs_f64 :: fn(x: f64) f64

min_i32 :: fn(a: i32, b: i32) i32
min_i64 :: fn(a: i64, b: i64) i64
min_f32 :: fn(a: f32, b: f32) f32
min_f64 :: fn(a: f64, b: f64) f64

max_i32 :: fn(a: i32, b: i32) i32
max_i64 :: fn(a: i64, b: i64) i64
max_f32 :: fn(a: f32, b: f32) f32
max_f64 :: fn(a: f64, b: f64) f64

// Float math functions
sqrt_f32 :: fn(x: f32) f32
sqrt_f64 :: fn(x: f64) f64
pow_f32 :: fn(x: f32, y: f32) f32
pow_f64 :: fn(x: f64, y: f64) f64
sin_f64 :: fn(x: f64) f64
cos_f64 :: fn(x: f64) f64
tan_f64 :: fn(x: f64) f64

// I/O functions
print :: fn(s: string)
print_i32 :: fn(x: i32)
print_f64 :: fn(x: f64)
printf :: fn(fmt: string, args: ..)
eprint :: fn(s: string)
eprintln :: fn(s: string)

// Assertions (separate functions, no overloading)
assert :: fn(cond: bool)
assert_msg :: fn(cond: bool, msg: string)
panic :: fn(msg: string)

// String functions
str_len :: fn(s: string) usize
str_copy :: fn(dst: []u8, src: string) usize
str_compare :: fn(a: string, b: string) i32
str_find :: fn(haystack: string, needle: string) isize
str_contains :: fn(haystack: string, needle: string) bool
str_starts_with :: fn(s: string, prefix: string) bool
str_ends_with :: fn(s: string, suffix: string) bool

// ASCII character functions
char_is_alpha :: fn(c: char) bool
char_is_digit :: fn(c: char) bool
char_is_upper :: fn(c: char) bool
char_is_lower :: fn(c: char) bool
char_to_upper :: fn(c: char) char
char_to_lower :: fn(c: char) char

// Memory functions
mem_copy :: fn(dst: []u8, src: []u8) usize
mem_move :: fn(dst: []u8, src: []u8) usize
mem_set :: fn(dst: []u8, val: u8) usize
mem_zero :: fn(dst: []u8) usize
mem_compare :: fn(a: []u8, b: []u8) i32
mem_alloc :: fn(size: usize) ref u8
mem_free :: fn(ptr: ref u8)
mem_realloc :: fn(ptr: ref u8, old_size: usize, new_size: usize) ref u8
```

---

## 12. Tokens and AST Components

### 12.1 Token Types

The authoritative token list is the `TokenType` enum in `a7/tokens.py`.
The enumeration below mirrors it exactly (member name, then source
spelling). Words with no keyword entry lex as `IDENTIFIER` (see §2.4);
`cast`, `const`, `self`, `size_of`, `type`, `using`, and `var` have no
token type of their own.

```a7
// Literals
INTEGER_LITERAL       // 42, 0x2A, 0b101010
FLOAT_LITERAL         // 3.14, 2.71e10
STRING_LITERAL        // "hello"
CHAR_LITERAL          // 'a', '\n', '\x41'
TRUE_LITERAL          // true
FALSE_LITERAL         // false
NIL_LITERAL           // nil

// Identifiers, builtins, and generics
IDENTIFIER            // user-defined names
BUILTIN_ID            // @name
GENERIC_TYPE          // $T

// Keywords (each keyword spells itself)
AND AS BOOL BREAK CASE CHAR CONTINUE DEL DEFER ELSE ENUM
F32 F64 FALL FALSE FLOAT FN FOR IF IMPORT IN INT
I8 I16 I32 I64 ISIZE LET MATCH NEW NIL NOT OR
PUB REF RET STRING STRUCT TRUE UNION
U8 U16 U32 U64 UINT USIZE WHERE WHILE

// Operators
PLUS                  // +
MINUS                 // -
MULTIPLY              // *
DIVIDE                // /
MODULO                // %
ASSIGN                // =
PLUS_ASSIGN           // +=
MINUS_ASSIGN          // -=
MULTIPLY_ASSIGN       // *=
DIVIDE_ASSIGN         // /=
MODULO_ASSIGN         // %=
EQUAL                 // ==
NOT_EQUAL             // !=
LESS_THAN             // <
LESS_EQUAL            // <=
GREATER_THAN          // >
GREATER_EQUAL         // >=
BITWISE_AND           // &
BITWISE_OR            // |
BITWISE_XOR           // ^
BITWISE_NOT           // ~
LEFT_SHIFT            // <<
RIGHT_SHIFT           // >>
BITWISE_AND_ASSIGN    // &=
BITWISE_OR_ASSIGN     // |=
BITWISE_XOR_ASSIGN    // ^=
LEFT_SHIFT_ASSIGN     // <<=
RIGHT_SHIFT_ASSIGN    // >>=
LOGICAL_NOT           // !

// Punctuation and declarations
DECLARE_CONST         // ::
DECLARE_VAR           // :=
COLON                 // :
COMMA                 // ,
DOT                   // .
DOT_DOT               // ..
LEFT_PAREN            // (
RIGHT_PAREN           // )
LEFT_BRACKET          // [
RIGHT_BRACKET         // ]
LEFT_BRACE            // {
RIGHT_BRACE           // }

// Statement termination and end of file
TERMINATOR            // newline or ; (consecutive terminators collapse)
EOF                   // end of file
```

Notes:

- `and`, `or`, and `not` are keyword tokens; only `!` is `LOGICAL_NOT`.
- `...` and `?` have no token: `...` is rejected with an
  unsupported-operator error and `?` with an unexpected-character error.
- The enum also declares `SEMICOLON`, `ADDRESS_OF`, `DEREFERENCE`, and
  `COMMENT`, which the tokenizer never emits: `;` produces `TERMINATOR`,
  `&` produces `BITWISE_AND`, and comments are discarded without a token.

### 12.2 AST Node Types

The following names are a historical design sketch, not the Python AST API.
Current node kinds are `NodeKind` members in
[`a7/ast_nodes.py`](../a7/ast_nodes.py), such as `PROGRAM`, `FUNCTION`, and
`TYPE_POINTER`. The sketch includes proposed nodes absent from that enum.

```a7
// Top-level nodes
AST_PROGRAM             // Root of the entire program
AST_IMPORT_DECL         // Import declarations
AST_FUNCTION_DECL       // Function declarations
AST_STRUCT_DECL         // Struct type declarations
AST_UNION_DECL          // Union type declarations
AST_ENUM_DECL           // Enum type declarations
AST_TYPE_ALIAS          // Type alias declarations
AST_CONST_DECL          // Constant declarations
AST_VAR_DECL            // Variable declarations

// Type nodes
AST_TYPE_PRIMITIVE      // Built-in types (i32, f64, etc.)
AST_TYPE_IDENTIFIER     // User-defined type names
AST_TYPE_POINTER        // ref T
AST_TYPE_ARRAY          // [N]T
AST_TYPE_SLICE          // []T
AST_TYPE_FUNCTION       // fn(T, U) V
AST_TYPE_GENERIC        // T with generic parameters
AST_TYPE_STRUCT         // Anonymous struct types
AST_TYPE_UNION          // Anonymous union types

// Expression nodes
AST_EXPR_LITERAL        // Literal values
AST_EXPR_IDENTIFIER     // Variable/function names
AST_EXPR_BINARY         // Binary operations (a + b)
AST_EXPR_UNARY          // Unary operations (-a, !b)
AST_EXPR_CALL           // Function calls
AST_EXPR_INDEX          // Array/slice indexing
AST_EXPR_SLICE          // Slice expressions [start..end]
AST_EXPR_FIELD          // Struct field access (a.field)
AST_EXPR_DEREF          // Internal dereference inserted by typed lowering
AST_EXPR_CAST           // Type casting
AST_EXPR_IF             // Conditional expressions
AST_EXPR_MATCH          // Match expressions
AST_EXPR_STRUCT_INIT    // Struct initialization
AST_EXPR_ARRAY_INIT     // Array initialization

// Statement nodes
AST_STMT_EXPRESSION     // Expression statements
AST_STMT_BLOCK          // Block statements { ... }
AST_STMT_IF             // If statements
AST_STMT_WHILE          // While loops
AST_STMT_FOR            // For loops
AST_STMT_MATCH          // Match statements
AST_STMT_BREAK          // Break statements
AST_STMT_CONTINUE       // Continue statements
AST_STMT_RETURN         // Return statements
AST_STMT_DEFER          // Defer statements
AST_STMT_ASSIGNMENT     // Assignment statements

// Pattern nodes (for match statements)
AST_PATTERN_LITERAL     // Literal patterns (42, "hello")
AST_PATTERN_IDENTIFIER  // Existing identifier patterns or branch-local captures
AST_PATTERN_ENUM        // Enum variant patterns
AST_PATTERN_RANGE       // Range patterns (1..10)
AST_PATTERN_WILDCARD    // Wildcard pattern (_)

// Generic nodes
AST_GENERIC_PARAM       // Generic type parameters ($T, $T: Numeric)
AST_GENERIC_CONSTRAINT  // Type set constraints (Numeric or @type_set(...))
AST_GENERIC_INSTANCE    // Generic instantiation
AST_TYPE_SET            // Type set definitions (@type_set(...))

// Utility nodes
AST_PARAMETER           // Function parameters
AST_FIELD               // Struct/union fields
AST_ENUM_VARIANT        // Enum variants
AST_CASE_BRANCH         // Match case branches
AST_IDENTIFIER_LIST     // List of identifiers
AST_EXPRESSION_LIST     // List of expressions
AST_TYPE_LIST           // List of types
```

### 12.3 AST Node Structure

The following A7 structs are historical design sketches. The current compiler
uses a Python `ASTNode` dataclass with optional fields and `SourceSpan`; it does
not use this tagged-data layout or a generic `children` array.

```a7
ASTNode :: struct {
    kind: ASTNodeKind          // Type of the node
    location: SourceLocation   // Position in source file
    data: union {              // Node-specific data
        literal: LiteralData
        binary: BinaryExprData
        function: FunctionData
        // ... other node types
    }
    children: []ref ASTNode    // Child nodes
}

SourceLocation :: struct {
    file: string
    line: i32
    column: i32
    offset: i32
}

LiteralData :: struct {
    type: LiteralType
    value: union {
        int_val: i64
        float_val: f64
        char_val: char
        string_val: string
        bool_val: bool
    }
}

BinaryExprData :: struct {
    operator: TokenType
    left: ref ASTNode
    right: ref ASTNode
}

FunctionData :: struct {
    name: string
    params: []ref ASTNode
    return_type: ref ASTNode
    body: ref ASTNode
    is_generic: bool
    generic_params: []ref ASTNode  // List of AST_GENERIC_PARAM nodes
}

GenericParamData :: struct {
    name: string              // Parameter name (T without $)
    constraint: ref ASTNode   // Optional type set constraint (Numeric or @type_set(...))
}

TypeSetData :: struct {
    name: string              // Type set name
    types: []ref ASTNode      // List of types in the set
}
```

### 12.4 Parsing Precedence

Operator precedence (highest to lowest):
1. Primary expressions (literals, identifiers, parentheses)
2. Postfix (function calls, array access, field access)
3. Unary prefix (-, !, ~, cast)
4. Multiplicative (*, /, %)
5. Additive (+, -)
6. Shift (<<, >>)
7. Relational (<, >, <=, >=)
8. Equality (==, !=)
9. Bitwise AND (&)
10. Bitwise XOR (^)
11. Bitwise OR (|)
12. Logical AND (and)
13. Logical OR (or)
14. Assignment (=, +=, -=, etc.)

---

## 13. Grammar Summary

This abbreviated grammar retains some design-only alternatives. It is not an
acceptance grammar. The parser and the qualifications in each section determine
current syntax. In particular, import metadata does not imply backend support,
and generic declaration examples in §6 and §7 give the accepted spelling.

### 13.1 Top-Level Grammar

```ebnf
program = (import_decl | declaration)*

import_decl =
    | "import" string_lit
    | identifier "::" "import" string_lit
    | "import" string_lit "{" identifier_list "}"
    | "using" "import" string_lit

declaration =
    | function_decl
    | type_decl
    | const_decl
    | var_decl

function_decl =
    | identifier "::" "fn" "(" param_list? ")" type? block
    | identifier "::" "fn" generic_params "(" param_list? ")" type? block

generic_params =
    | generic_param ("," generic_param)*

generic_param =
    | "$" identifier
    | "$" identifier ":" type_set
    | "$" identifier ":" "@type_set" "(" type_list ")"

where_clause = "where" identifier ":" type_set ("," identifier ":" type_set)*
```

A `where_clause` follows the header of a generic function, struct, or
union declaration. Only set-membership bounds are accepted; anything
richer is rejected (see §7.3).

### 13.2 Type Grammar

```ebnf
type =
    | primitive_type
    | identifier type_args?
    | "[" expr? "]" type
    | "ref" type
    | "fn" generic_params? "(" type_list? ")" type?
    | struct_type
    | union_type

type_args = "(" type ("," type)* ")"

type_set = identifier  // References to type sets like Numeric, Integer

struct_type = "struct" generic_params? "{" field_list? "}"
union_type = "union" generic_params? "(" "tag" ")" "{" variant_list "}"

field_list = field ("," field)*
field = "pub"? identifier ":" type

variant_list = variant ("," variant)*
variant = identifier ":" type
```

The `(tag)` marker is optional in the parser (`union()` is also accepted),
and there is no rule for an anonymous inline union type even though §12.2
lists `AST_TYPE_UNION`. See STATUS Known Gaps.

### 13.3 Expression Grammar

```ebnf
expr = logical_or_expr

logical_or_expr = logical_and_expr ("or" logical_and_expr)*
logical_and_expr = bitwise_or_expr ("and" bitwise_or_expr)*
bitwise_or_expr = bitwise_xor_expr ("|" bitwise_xor_expr)*
bitwise_xor_expr = bitwise_and_expr ("^" bitwise_and_expr)*
bitwise_and_expr = equality_expr ("&" equality_expr)*
equality_expr = relational_expr (("==" | "!=") relational_expr)*
relational_expr = shift_expr (("<" | ">" | "<=" | ">=") shift_expr)*
shift_expr = additive_expr (("<<" | ">>") additive_expr)*
additive_expr = multiplicative_expr (("+" | "-") multiplicative_expr)*
multiplicative_expr = unary_expr (("*" | "/" | "%") unary_expr)*

unary_expr =
    | postfix_expr
    | unary_op unary_expr
    | "cast" "(" type "," expr ")"

postfix_expr =
    | primary_expr
    | postfix_expr "[" expr "]"
    | postfix_expr "[" expr? ".." expr? "]"
    | postfix_expr "." identifier
    | postfix_expr "(" expr_list? ")"

primary_expr =
    | identifier
    | literal
    | "(" expr ")"
    | "if" expr block "else" block_or_if
```

Assignment is statement-only in the parser. `a = b = 3` is rejected; it is
not a right-associative expression. See
[`test_statement_forms_codegen.py`](../test/test_statement_forms_codegen.py).

### 13.4 Statement Grammar

```ebnf
statement =
    | assignment_stmt
    | expr_stmt
    | block_stmt
    | if_stmt
    | match_stmt
    | loop_label loop_stmt
    | for_stmt
    | while_stmt
    | jump_stmt
    | defer_stmt
    | var_decl

loop_label = "@" identifier
loop_stmt = for_stmt | while_stmt

jump_stmt =
    | "ret" expr?
    | "break" identifier?
    | "continue" identifier?

assignment_stmt = postfix_expr assign_op expr

defer_stmt = "defer" statement
```

---

## Appendix A: Language Semantics

### A.1 Evaluation Order

1. Function arguments: left-to-right
2. Binary operators: left-to-right
3. Assignment is statement-only; chained assignment is rejected
4. Field initialization: declaration order

### A.2 Type Conversions

Current checked conversions include:

- Safe numeric widening according to the implemented scalar compatibility rules.
- `T` lvalues to `ref T` in function calls.
- Integer literals to an integer destination when the value fits, including
  arguments and return values. A literal branch can take the other branch's type.

Implicit array-to-slice argument conversion is not implemented. Use explicit
slicing to create a view. Mixed-width arithmetic records the compatible wider
result type; a narrower result binding requires an explicit checked cast.
Integer `+`, `-`, and `*`, including compound assignments, use wrapping lowering.
Release builds lower a proven-range integer `+`, `-`, `*`, or compound form to
a non-wrapping operator when the safety pass proves the result fits the operand
type. Debug builds and unproven forms keep wrapping. `--no-nonwrap` forces
wrapping in both profiles.
Unsigned negation is rejected. Constant shift counts must be non-negative and
less than the operand width. Other numeric edge cases still require qualification.

### A.3 Name Resolution

1. Current scope
2. Enclosing scopes (outward)
3. File scope
4. Imported names
5. Built-in names

### A.4 Lifetime Rules

These are intended lifetime requirements, not established compiler guarantees.
The current proof limits are in [the safety contract](SAFETY_CONTRACT.md).

1. Stack values live until scope exit
2. Heap values live until explicit `del`
3. References must not outlive referent
4. Slices must not outlive backing array

---

## Appendix B: Standard Compiler Diagnostics

### B.1 Error Categories

The E-number families below are historical design labels. Current diagnostics
use the codes and exit stages in [the error catalog](ERROR_CATALOG.md).

- **E0xxx**: Syntax errors
- **E1xxx**: Type errors
- **E2xxx**: Lifetime errors
- **E3xxx**: Generic instantiation errors
- **E4xxx**: Module/import errors

### B.2 Common Lexer Error Messages

The A7 compiler provides specific error messages for lexical analysis failures:

- `"Unexpected character: 'X'"` - Invalid character found in source code
- `"The string is not closed"` - Unterminated string literal
- `"The char is not closed"` - Unterminated character literal
- `"Tabs '\\t' are unsupported"` - Tab character found (not supported)
- `"Invalid string escape sequence"` - Unknown escape or malformed `\xHH` escape in a string literal
- `"Identifier is too long"` - Identifier exceeds 100 characters
- `"Number is too long"` - Numeric literal exceeds 100 characters

**Error Format:**
```
error: <message>, line: <line>, col: <column>
help: <helpful advice>
   <line_number> │ <source_code_line>
                 │ <error_pointer>
```

### B.3 Warning Categories

These W-number families are proposed categories, not a current warning API.

- **W0xxx**: Unused code
- **W1xxx**: Deprecated features
- **W2xxx**: Performance issues
- **W3xxx**: Potential bugs

---

## Appendix C: Implementation Limits

The tokenizer enforces the first three limits below. The remaining rows are
historical proposed limits, not implemented minimum capacities or enforced caps.
The parser instead has `MAX_NESTING_DEPTH = 256` for tracked nested constructs;
this is not a promise that every 256-deep program completes every compiler pass.
See [`a7/tokens.py`](../a7/tokens.py) and [`a7/parser.py`](../a7/parser.py).

| Feature | Limit or historical proposal |
|---------|---------------|
| Identifier length | 100 characters |
| Numeric literal length | 100 characters |
| String literal length | 32,767 characters, including both quotes |
| Function parameters | 255 |
| Generic parameters | 32 |
| Nested blocks | 127 |
| Array dimensions | 8 |
| Struct fields | 1,023 |
| Union variants | 255 |
| Enum values | 65,535 |
| Import depth | 32 (planned) |
| Defer statements per scope | 255 |
| Match cases | 1,023 |

Import depth 32 is an unapproved proposal. L69 does not authorize that cap.
The loader uses an explicit stack; the low-recursion regression loads 1,100
modules in [`test_iterative_module_loading.py`](../test/test_iterative_module_loading.py).

The approved exact-constant policy specifies the following caps.
`a7/exact_constants.py` enforces decimal-exponent and integer-component limits.
The credit budgets, retained-payload budget, dependency-depth cap, and diagnostic
caps below remain policy requirements; this table does not claim their full
enforcement. See [P-TYP](plan/packets/P-TYP-forward-globals.md).

| Exact evaluation limit | Cap |
| --- | --- |
| Absolute decimal exponent in a numeric token | 4,096 |
| Reduced numerator or denominator | 131,072 bits each |
| Transient arithmetic component | 262,144 bits |
| Work per evaluated initializer or fitting context | 2^24 limb-operation credits |
| Work per compilation | 2^32 limb-operation credits |
| Retained bindings and exact-value cache | 16 MiB of logical payload |
| Constant dependency-chain depth | 65,536 bindings |
| Rendered diagnostic value | 256 characters |
| Whole exact-evaluation diagnostic | 2,048 characters |
| Rendered dependency chain | At most 32 links |

Credits measure deterministic work under the
[resource policy](plan/research/untyped-constant-resource-policy-2026-09-20.md).
They do not measure elapsed time. Logical payload counts integer-component bytes
and an entry allowance; it does not measure process memory. The policy requires
conservative growth checks before operations, so a
computation may exceed a limit even when its final reduced value would fit.
Enforced limit errors do not substitute an approximate value. Target emission
uses the destination's bounded encoding.

---

## Appendix D: ASCII Character Set Support

A7 identifiers, keywords, and numeric literals use ASCII only (see §2.1,
§2.3, and §2.6). For the accepted escape spellings in character and
string literals, see §2.6: `\n`, `\t`, `\r`, `\\`, `\'`, `\"`, `\0`,
and `\xHH` with exactly two hex digits.

The tokenizer rejects `\b`, `\f`, `\v`, and `\a`. Earlier drafts of this
appendix listed them as supported escapes; they are not accepted.

---

## Appendix E: Implementation Status (a7-py)

Current implementation gaps live in [Status](STATUS.md). The compiler/package
gate is [`run_all_tests.sh`](../run_all_tests.sh); the full release gate is
[`run_release_checks.sh`](../run_release_checks.sh). A historical test count or
feature list does not establish that the current tree passes these checks.

`a7-py` is not a sandbox. Compile and execute only A7 source you trust.

### E.1 Current Constraints and Open Gaps

1. **Supported `fall` scope restrictions**
   - `fall` is supported in match statements and lowers in Zig.
   - `fall` must be the final direct statement of a non-final match case.
   - `fall` is invalid outside match cases, in `else` branches, in final cases,
     or nested inside other control-flow statements.

2. **Advanced match diagnostics**
   - Exhaustiveness for bool/enum is implemented.
   - Exact duplicate bool, enum, and scalar literal patterns are diagnosed.
   - Wildcard-first and fully covered bool/enum cases make later cases and else branches unreachable.
   - Literal and compile-time constant numeric/char range overlaps are diagnosed.
   - Conservative non-constant symbolic interval overlaps are diagnosed when
     inclusive ranges share an endpoint symbol.
   - Identifier capture patterns bind the scrutinee in branch-local scope when
     no existing symbol with that name is visible.

3. **Memory/lifetime model depth**
   - Basic `new`/`del` validation and direct use-after-`del` rejection exist;
     full ownership/lifetime and aliasing analysis is not complete.

4. **Backend hardening**
   - Zig is the only supported code generation target.
   - The retired C backend no longer defines release readiness or public support status.
   - Backend regression coverage should continue expanding for every new language feature.

5. **Release packaging activation**
   - Python packaging and installed CLI are present.
   - Tag-triggered draft GitHub releases attach package, docs, and native
     example artifacts.
   - Package-registry publishing is not part of the current release workflow.

### E.2 Source Of Truth

- [Status](STATUS.md) tracks language gaps, priorities, and roadmap notes.
- [Release checklist](RELEASE.md) tracks local build and release gates.
