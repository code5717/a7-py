# A7 Programming Language Specification

> **Implementation Status (2026-05-08)**: This specification describes the A7 language design. The current Python implementation (`a7-py`) provides:
> - ✅ **Tokenizer/Lexer**: implemented
> - ✅ **Parser**: implemented
> - ✅ **AST generation**: implemented
> - ✅ **Semantic pipeline**: implemented (name resolution, type checking, semantic validation), including match expressions, pattern type checks, and bool/enum exhaustiveness checks
> - ✅ **Zig code generation**: implemented
> - ✅ **C code generation**: implemented (C11, validated with `zig cc`)
> - ✅ **Debug/release example artifact builds**: available through `scripts/build_examples.py`
> - 📊 **Current tests**: check with `PYTHONPATH=. uv run pytest --tb=no -q`
>
> See `MISSING_FEATURES.md`, `TODO.md`, and `RELEASE.md` for detailed feature, verification, and release status.

## Table of Contents

1. [Introduction](#introduction)
2. [Lexical Structure](#lexical-structure)
3. [Type System](#type-system)
4. [Declarations and Expressions](#declarations-and-expressions)
5. [Control Flow](#control-flow)
6. [Functions](#functions)
7. [Generics](#generics)
8. [Memory Management](#memory-management)
9. [Planned Array Programming for AI](#planned-array-programming-for-ai)
10. [Modules and Visibility](#modules-and-visibility)
11. [Built-in Functions and Operators](#built-in-functions-and-operators)
12. [Tokens and AST Components](#tokens-and-ast-components)
13. [Grammar Summary](#grammar-summary)

---

## 1. Introduction

### 1.1 Language Overview

A7 is a statically-typed, procedural programming language that compiles to Zig and C, with plans for native machine code targets.
It features:
- **Static typing** with type inference
- **Compile-time generics** via monomorphization
- **Manual memory management** with safety features
- **Planned array programming for AI** with broadcasting, vectorized operations, and multidimensional tensors
- **File-based module system** with controlled visibility
- **Zero-cost abstractions**
- **Platform-aware integer types** (isize/usize)

### 1.2 Design Philosophy

1. **Simplicity over features**: Every feature must justify its complexity
2. **Explicit over implicit**: No hidden allocations or conversions
3. **Performance**: Zero-cost abstractions, predictable performance
4. **Safety**: Prevent common errors at compile time
5. **Interoperability**: Clean C ABI compatibility

---

## 2. Lexical Structure

### 2.1 Source Encoding

A7 source files must be ASCII encoded. The standard file extension is `.a7`.

**Whitespace Rules:**
- Spaces (U+0020) and carriage returns (U+000D) are allowed
- Tab characters (U+0009) are **not supported** and will cause a compilation error
- Newlines (U+000A) serve as statement terminators

### 2.2 Comments

```a7
// Single-line comment extends to end of line

/* 
   Multi-line comment
   /* Can be nested */
*/
```

### 2.3 Identifiers

```ebnf
identifier = letter (letter | digit | "_")*
letter     = "a"..."z" | "A"..."Z"  ; ASCII letters only
digit      = "0"..."9"              ; ASCII digits only
```

**Identifier Rules:**
- Identifiers are case-sensitive
- Must start with an ASCII letter (a-z, A-Z) or underscore
- Can contain ASCII letters, digits (0-9), and underscores
- **Unicode characters are not supported** in identifiers
- Leading underscores are reserved for compiler-generated names
- Maximum length: 100 characters

### 2.4 Keywords

```
and        as         bool       break      case       cast       char
const      continue   defer      del        else       enum       f32
f64        fall       false      fn         for        i8         i16
i32        i64        if         import     in         isize      match
new        nil        or         pub        struct     ref        ret
self       size_of    string     true       type       u8         u16
u32        u64        union      using      usize      var        where
while
```

### 2.5 Operators and Punctuation

```
// Arithmetic
+    -    *    /    %    

// Comparison
==   !=   <    >    <=   >=

// Logical
and  or   !    

// Bitwise
&    |    ^    ~    <<   >>

// Assignment
=    +=   -=   *=   /=   %=   &=   |=   ^=   <<=  >>=

// Memory
.adr .val .    

// Generics  
$    // Generic type parameter prefix

// Other
::   :    ;    ,    ()   []   {}   ..   ...   @
```

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
- Underscores can be used as separators for readability
- Hex literals use `0x` prefix, octal use `0o`, binary use `0b`

#### Floating-Point Literals
```a7
3.14159
2.71e10
.5
1.
```

#### Character Literals
```a7
'a'
'\n'      // Newline
'\t'      // Tab
'\\'      // Backslash
'\''      // Single quote
'\x41'    // Hex escape (A) - ASCII only
```

#### String Literals
```a7
"Hello, World!" // single line string
"Line 1\nLine 2"
"Quote: \"Hello\"" 
"Plain string"
```

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
// ✅ Valid - nil with reference types
ptr: ref i32 = nil
fn_ptr: ref fn() void = nil
if ptr == nil { }

// ❌ Invalid - nil with value types
arr: [5]i32 = nil      // ERROR: arrays cannot be nil
x: i32 = nil           // ERROR: primitives cannot be nil
s: MyStruct = nil      // ERROR: value structs cannot be nil
```

**Array Initialization**: Arrays must be initialized with:
- No initializer (zero-initialized): `arr: [5]i32`
- Single value (all elements): `arr: [5]i32 = 0`
- Array literal: `arr: [5]i32 = [1, 2, 3, 4, 5]`

Array literals must match the declared array length when a target type is
present. Each element is checked against the declared element type, including
nested array literals.

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
| `char`   | 1           | ASCII character (0-127) |

**Note**: `isize` and `usize` are platform-dependent types:
- On 32-bit platforms: 4 bytes (same as i32/u32)
- On 64-bit platforms: 8 bytes (same as i64/u64)

Use `usize` for sizes, lengths, capacities, allocation byte counts, and array/slice/string indices. It is the memory-shape integer and maps to `usize` in Zig and `size_t` in C.

Use `isize` only for signed pointer-sized offsets or differences between positions. It exists for pointer-adjacent signed math, not as the default signed integer type.

Use fixed-width integers such as `i32`, `i64`, `u32`, or `u64` when the data itself has that width or range. Small arithmetic examples may use `i32`; counters and indexes should usually use `usize`.

### 3.3 Composite Types

#### Arrays
```a7
// Fixed-size array
arr: [10]i32
matrix: [3][3]f64

// Array type properties
T.len       // Number of elements (compile-time constant)
T.element   // Element type
```

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
// ASCII encoded string
name: string = "Hello"

// String slicing produces a []char byte slice
part := name[1..4]

// String is equivalent to
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

// All pointers can be modified through dereferencing
x := 42
ptr := x.adr
ptr.val = 100  // Modifies the value x points to (using . syntax)
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
Field access type-checks against the declared union fields. Tagged union tag
inspection is reserved syntax and is not implemented yet.

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

### 3.4 Type Aliases

```a7
// Simple alias
Handle :: u64

// Generic alias
Vector :: [3]f32
Matrix :: [4][4]f32
```

### 3.5 Pointer Semantics

```a7
// All pointers allow modification through dereferencing
x := 42
ptr := x.adr
ptr.val = 100  // OK: modifies the value x points to

// Pointer reassignment
y := 50
ptr = y.adr    // OK: pointer now points to y

// Function parameters are immutable (including pointers)
modify_value :: fn(p: ref i32) {
    p.val = 200    // OK: modifying through dereference
    // p = other_var.adr  // ERROR: cannot reassign parameter
}

// To reassign a pointer in a function, use ref ref
reassign_pointer :: fn(p: ref ref i32, new_target: ref i32) {
    p.val = new_target  // OK: changes what the original pointer points to
}
```

---

## 4. Declarations and Expressions

### 4.1 Variable Declarations

```a7
// Immutable binding (constant)
x: i32 = 42
PI :: 3.14159

// Mutable binding (variable)
count := 0
buffer: [1024]u8

// Type can be explicit or inferred
age: i32 = 25    // Explicit type
name := "John"   // Inferred as string

// Multiple declaration/destructuring syntax is planned, not current:
// a, b, c: i32 = 1, 2, 3
// x, y := 10, 20
```

### 4.2 Declaration Rules

**A7 uses two declaration operators:**

- `::` - Creates immutable bindings (constants)
- `:=` - Creates mutable bindings (variables)

```a7
// Constants (immutable) - use ::
PI :: 3.14159
MAX_BUFFER :: 1024
VERSION :: "1.0.0"
DOUBLE_PI :: PI * 2

// Variables (mutable) - use :=
count := 0
name := "John"
buffer: [1024]u8

// Explicit typing works with both
MAX_SIZE: i32 = 1000    // Immutable with explicit type
counter: i32 = 0        // Mutable with explicit type (uses = not :=)

// Variables can be reassigned
counter = counter + 1   // OK
// PI = 3.0             // ERROR: cannot reassign constant

// Example using logical operators
valid := count > 0 and count < 100
should_process := valid or force_mode
can_exit := !running and cleanup_done
```

### 4.3 Expression Categories

#### Primary Expressions
- Identifiers: `x`, `foo`
- Literals: `42`, `"hello"`, `true`
- Parenthesized: `(x + y)`

#### Postfix Expressions
- Array subscript: `arr[i]`
- Slice: `arr[1..5]`, `arr[..3]`, `arr[2..]`
- Field access: `point.x`
- Address access: `variable.adr`
- Pointer dereference: `ptr.val`
- Function call: `max(a, b)`

Method-call sugar such as `vec.length()` is planned syntax, not current
semantic support. Use explicit functions such as `length(vec.adr)`.

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

// Generic function examples
swap :: fn($T, a: ref T, b: ref T) {
    temp := a.val
    a.val = b.val
    b.val = temp
}

// Generic function with type constraint
add :: fn($T, a: T, b: T) T where T: Numeric {
    ret a + b
}

// Multiple generic parameters
convert :: fn($T, $U, value: T) U
where
    T: Numeric,
    U: Numeric
{
    ret cast(U, value)
}
```

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

**All function parameters in A7 are immutable by design.** This includes both value parameters and pointer parameters - the parameters themselves cannot be reassigned, though data can be modified through pointer dereferencing.

```a7
// Parameters cannot be reassigned
bad_function :: fn(x: i32) i32 {
    x += 1  // ERROR: cannot modify parameter
    ret x
}

// Pointers can be dereferenced to modify data
increment :: fn(x: ref i32) {
    x.val += 1  // OK: modifying through pointer dereference
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
    increment(value.adr)  // Pass pointer to modify original
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
    self.x /= len  // OK: modifying through pointer dereference
    self.y /= len
}

// Explicit receiver call
v := Vec2{3.0, 4.0}
len := length(v.adr)
normalize(v.adr)      // Modifies v through pointer
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
- Can contain only letters and underscores after the initial letter
- No digits allowed: `$T`, `$MY_TYPE` ✅ but `$T1`, `$123` ❌
- Standalone `$` is invalid and produces a compilation error

```a7
// Simple generic function - $T used inline in parameter and return types
swap :: fn(a: ref $T, b: ref $T) {
    //           ^^       ^^
    //      $T used inline in type expressions
    temp := a.val
    a.val = b.val
    b.val = temp
}

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

### 7.2 Generic Types

Generic structs, enums, and unions use inline `$T` syntax in their field types:

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

// Generic enum
Option :: enum {
    Some: $T,
    None,
}

// Generic union
Result :: union {
    ok: $T,
    err: $E,
}
```

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

Generic functions are specialized from concrete call sites. Backends that do
not have native generic functions, such as the C backend, lower simple top-level
generic function calls into generated concrete functions such as
`identity__i32` and `identity__string`. Used generic struct instances also
lower to concrete backend types such as `Box__i32`. Broader composite generic
specialization and deeper propagation through method-style call chains remain
implementation work.

---

## 8. Memory Management

### 8.1 Stack Allocation

All local variables are stack-allocated by default:
```a7
fn example() {
    x := 42            // Stack
    arr: [100]f32      // Stack  
    person: Person     // Stack
}  // All automatically freed
```

### 8.2 Heap Allocation

```a7
// Allocate single value
ptr := new i32
ptr.val = 42
del ptr

// Heap fixed arrays are not current syntax. Use stack arrays or slices.
buffer: [1024]u8
slice := buffer[0..1024]

// Initialize through the returned reference
point := new Point
point.val = Point{x: 10, y: 20}
del point

// `new T(args...)` and `new T{...}` initializer forms are not current syntax.

// Check allocation
large := new Point
if large == nil {
    // Handle allocation failure
}
```

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
2. `del` is validated for reference-like values.
3. `defer del value` can express manual cleanup at scope exit.

Not yet implemented:

1. Ownership, borrowing, or lifetime analysis that proves absence of dangling pointers.
2. Static double-free or use-after-free prevention beyond the current basic shape checks.
3. General array/slice bounds-check insertion by the A7 compiler.

---

## 9. Planned Array Programming for AI

### 9.1 Multidimensional Arrays

This section is a design target, not current implementation status. Tensor
types, broadcasting, vectorized tensor operators, AI primitives, GPU movement,
and performance annotations are not implemented yet. Current release status is
tracked in `MISSING_FEATURES.md` and `TODO.md`.

#### Tensor Types
```a7
// N-dimensional tensors (up to 8 dimensions)
Tensor :: struct($T: Numeric, $N: u8) {
    data: ref T              // Flat data storage
    shape: [N]usize         // Dimensions
    strides: [N]usize       // Memory strides
}

// Type aliases for common tensor shapes
Vector :: [N]$T             // 1D vector
Matrix :: [M][N]$T          // 2D matrix  
Tensor3D :: [D][H][W]$T     // 3D tensor
Tensor4D :: [B][C][H][W]$T  // 4D tensor (batch, channels, height, width)

// Dynamic tensors with runtime shape
DynTensor :: struct($T: Numeric) {
    data: ref T
    shape: []usize
    strides: []usize
    ndim: u8
}
```

#### Array Literals and Initialization
```a7
// Multi-dimensional array literals
matrix := [[1, 2, 3],
           [4, 5, 6],
           [7, 8, 9]]

// Tensor initialization with shape inference
tensor := [[[1, 2], [3, 4]],
           [[5, 6], [7, 8]]]  // Shape: [2, 2, 2]

// Explicit tensor creation
zeros := tensor_zeros([3, 4, 5], f32)     // All zeros
ones := tensor_ones([2, 3], i32)          // All ones  
range := tensor_range(0, 100, [10, 10])   // Sequential values
random := tensor_random([5, 5], f32)      // Random values [0, 1)

// Tensor from data with explicit shape
data := [1, 2, 3, 4, 5, 6]
reshaped := tensor_from_data(data, [2, 3])
```

### 9.2 Broadcasting and Vectorized Operations

#### Automatic Broadcasting
```a7
// Broadcasting follows NumPy-compatible rules
a := [[1, 2, 3],        // Shape: [2, 3]
      [4, 5, 6]]
      
b := [10, 20, 30]       // Shape: [3] -> broadcasts to [1, 3]

result := a + b         // Element-wise addition with broadcasting
// result = [[11, 22, 33],
//           [14, 25, 36]]

// Scalar broadcasting
scaled := a * 2.0       // Multiply all elements by 2

// Complex broadcasting
x := tensor_ones([3, 1, 4])    // Shape: [3, 1, 4]
y := tensor_ones([2, 5, 1])    // Shape: [2, 5, 1] 
z := x + y                     // Result shape: [3, 2, 5, 4]
```

#### Vectorized Operations
```a7
// Element-wise operations (all support broadcasting)
sum := a + b           // Addition
diff := a - b          // Subtraction  
prod := a * b          // Multiplication
quot := a / b          // Division
power := a ^ b         // Power
mod := a % b           // Modulo

// Mathematical functions (vectorized)
roots := sqrt(a)       // Square root of each element
logs := log(a)         // Natural logarithm
exps := exp(a)         // Exponential
sins := sin(a)         // Sine function
tans := tanh(a)        // Hyperbolic tangent

// Comparison operations (return boolean tensors)
gt := a > b            // Greater than
eq := a == b           // Equality
mask := a >= 0.5       // Create boolean mask

// Boolean operations on tensors
result := tensor_where(mask, a, b)  // Select elements based on condition
```

### 9.3 Tensor Manipulation and Reshaping

#### Shape Operations
```a7
// Get tensor properties
dims := tensor_shape(a)        // Returns [usize] of dimensions
ndim := tensor_ndim(a)         // Number of dimensions
size := tensor_size(a)         // Total number of elements
dtype := tensor_dtype(a)       // Element type

// Reshaping (must preserve total size)
reshaped := tensor_reshape(a, [6])        // Flatten to 1D
matrix := tensor_reshape(a, [2, 3])       // 2x3 matrix
tensor3d := tensor_reshape(a, [1, 2, 3])  // Add batch dimension

// View operations (share memory)
flattened := tensor_flatten(a)            // 1D view
view := tensor_view(a, [start..end])      // Slice view
```

#### Axis Operations  
```a7
// Reorder dimensions
transposed := tensor_transpose(matrix)              // 2D transpose
swapped := tensor_transpose(tensor, [2, 0, 1])     // Reorder axes

// Add/remove dimensions
expanded := tensor_expand_dims(a, axis: 1)         // Add dimension at axis 1
squeezed := tensor_squeeze(a)                      // Remove size-1 dimensions
unsqueezed := tensor_unsqueeze(a, axis: 0)         // Add dimension at axis 0

// Concatenation and splitting
concat := tensor_concat([a, b, c], axis: 0)        // Join along axis
chunks := tensor_split(a, sections: 3, axis: 1)    // Split into 3 parts
stacked := tensor_stack([a, b, c], axis: 2)        // Stack along new axis
```

### 9.4 Reduction Operations

```a7
// Aggregation along axes
sum_all := tensor_sum(a)                    // Sum all elements
sum_axis := tensor_sum(a, axis: 1)          // Sum along axis 1
mean_val := tensor_mean(a, axis: [0, 1])    // Mean along multiple axes

// Statistical operations
max_val := tensor_max(a)                    // Maximum value
min_val := tensor_min(a)                    // Minimum value
std_dev := tensor_std(a, axis: 0)           // Standard deviation
variance := tensor_var(a)                   // Variance

// Find operations
argmax := tensor_argmax(a, axis: 1)         // Indices of maximum values
argmin := tensor_argmin(a)                  // Index of global minimum
```

### 9.5 Linear Algebra Operations

```a7
// Matrix operations
product := tensor_matmul(A, B)              // Matrix multiplication
dot_prod := tensor_dot(x, y)                // Vector dot product
cross := tensor_cross(u, v)                 // Cross product (3D vectors)

// Decompositions and factorizations
eigenvals, eigenvecs := tensor_eig(A)       // Eigendecomposition
U, S, Vt := tensor_svd(A)                  // Singular value decomposition
Q, R := tensor_qr(A)                       // QR decomposition
L, U := tensor_lu(A)                       // LU decomposition

// Matrix properties
det := tensor_det(A)                        // Determinant
trace := tensor_trace(A)                    // Trace
inv := tensor_inv(A)                        // Matrix inverse
norm := tensor_norm(x, p: 2)                // L2 norm
```

### 9.6 AI-Specific Operations

#### Neural Network Primitives
```a7
// Convolution operations
conv_out := tensor_conv2d(input, kernel,    // 2D convolution
                         stride: [1, 1], 
                         padding: [0, 0])

pool_out := tensor_maxpool2d(input,         // Max pooling
                            kernel_size: [2, 2],
                            stride: [2, 2])

// Activation functions (vectorized)
relu := tensor_relu(x)                      // ReLU activation
sigmoid := tensor_sigmoid(x)                // Sigmoid activation
softmax := tensor_softmax(x, axis: -1)      // Softmax normalization
gelu := tensor_gelu(x)                      // GELU activation

// Normalization
batch_norm := tensor_batch_norm(x, gamma, beta, mean, var)
layer_norm := tensor_layer_norm(x, axis: -1)
```

#### Gradient Operations
```a7
// Automatic differentiation support
grad_fn := tensor_grad_enable(x)            // Enable gradient tracking
grad := tensor_backward(loss)               // Compute gradients
no_grad := tensor_no_grad { ... }           // Disable gradient computation

// Gradient clipping
clipped := tensor_clip_grad_norm(params, max_norm: 1.0)
```

### 9.7 Memory Layout and Performance

#### Memory Layout Control
```a7
// Specify memory layout
row_major := tensor_c_layout(data, shape)   // C-style (row-major)
col_major := tensor_f_layout(data, shape)   // Fortran-style (column-major)
strided := tensor_strided(data, shape, strides)

// Memory management
contiguous := tensor_contiguous(a)          // Ensure contiguous memory
copied := tensor_copy(a)                    // Deep copy
cloned := tensor_clone(a)                   // Clone with same layout
```

#### Performance Annotations
```a7
// Compiler hints for optimization
@vectorize                                  // Enable SIMD vectorization
tensor_operation :: fn(a: Tensor, b: Tensor) Tensor {
    ret a + b
}

@parallel                                   // Enable parallel execution
matrix_multiply :: fn(A: Matrix, B: Matrix) Matrix {
    ret tensor_matmul(A, B)
}

// Memory prefetch hints
@prefetch(a.data, size_of(f32) * tensor_size(a))
result := expensive_computation(a)
```

### 9.8 Indexing and Slicing

#### Advanced Indexing
```a7
// Multi-dimensional indexing
element := tensor[i, j, k]                  // Direct element access
row := tensor[i, ..]                        // Entire row
col := tensor[.., j]                        // Entire column
block := tensor[i..i+3, j..j+3]             // 3x3 block

// Boolean indexing
mask := tensor > 0.5                        // Boolean mask
filtered := tensor[mask]                    // Elements where mask is true

// Integer array indexing
indices := [0, 2, 4, 6]
selected := tensor[indices]                 // Select specific indices

// Fancy indexing with multiple arrays
row_idx := [0, 1, 2]
col_idx := [1, 2, 0]
elements := tensor[row_idx, col_idx]        // Select (0,1), (1,2), (2,0)
```

### 9.9 Built-in Tensor Functions

```a7
// Creation functions
tensor_zeros :: fn(shape: []usize, $T: Numeric) Tensor(T)
tensor_ones :: fn(shape: []usize, $T: Numeric) Tensor(T)
tensor_eye :: fn(n: usize, $T: Numeric) Tensor(T)           // Identity matrix
tensor_arange :: fn(start: $T, stop: $T, step: $T) Tensor(T)
tensor_linspace :: fn(start: $T, stop: $T, num: usize) Tensor(T)

// Type conversion
tensor_cast :: fn($T, $U: Numeric, tensor: Tensor(T)) Tensor(U)
tensor_to_f32 :: fn(tensor: Tensor) Tensor(f32)
tensor_to_i32 :: fn(tensor: Tensor) Tensor(i32)

// I/O operations  
tensor_save :: fn(tensor: Tensor, filename: string) bool
tensor_load :: fn(filename: string, $T: Numeric) Tensor(T)
tensor_print :: fn(tensor: Tensor, precision: u8)

// Device operations (for GPU/accelerator support)
tensor_to_gpu :: fn(tensor: Tensor) Tensor
tensor_to_cpu :: fn(tensor: Tensor) Tensor
tensor_device :: fn(tensor: Tensor) Device
```

### 9.10 Array Programming Examples

#### Machine Learning Example
```a7
// Simple neural network layer
Layer :: struct {
    weights: Matrix(f32)
    bias: Vector(f32)
}

forward :: fn(layer: Layer, input: Matrix(f32)) Matrix(f32) {
    // Matrix multiplication + bias + activation
    linear := tensor_matmul(input, layer.weights) + layer.bias
    ret tensor_relu(linear)
}

// Batch processing
process_batch :: fn(data: Tensor4D(f32)) Tensor4D(f32) {
    // Normalize batch
    normalized := tensor_batch_norm(data)
    
    // Apply convolution
    conv_out := tensor_conv2d(normalized, kernel)
    
    // Pooling
    ret tensor_maxpool2d(conv_out, kernel_size: [2, 2])
}
```

#### Scientific Computing Example  
```a7
// Solve linear system Ax = b using tensor operations
solve_linear :: fn(A: Matrix(f64), b: Vector(f64)) Vector(f64) {
    // LU decomposition
    L, U, P := tensor_lu_pivot(A)
    
    // Forward substitution: Ly = Pb
    Pb := tensor_matmul(P, b)
    y := tensor_forward_solve(L, Pb)
    
    // Backward substitution: Ux = y
    ret tensor_backward_solve(U, y)
}

// Numerical integration using broadcasting
integrate_2d :: fn(f: fn(f64, f64) f64, bounds: [4]f64, steps: [2]usize) f64 {
    x := tensor_linspace(bounds[0], bounds[1], steps[0])
    y := tensor_linspace(bounds[2], bounds[3], steps[1])
    
    // Create meshgrid using broadcasting
    X := tensor_expand_dims(x, axis: 1)     // [n, 1]
    Y := tensor_expand_dims(y, axis: 0)     // [1, m]
    
    // Evaluate function on grid (broadcasts to [n, m])
    Z := f(X, Y)
    
    // Numerical integration using trapezoidal rule
    dx := (bounds[1] - bounds[0]) / cast(f64, steps[0] - 1)
    dy := (bounds[3] - bounds[2]) / cast(f64, steps[1] - 1)
    
    ret tensor_sum(Z) * dx * dy
}
```

---

## 10. Modules and Visibility

### 10.1 File-Based Module Model

Every A7 source file is a module. There is no explicit `module` keyword.
Current backend codegen does not link multiple `.a7` files yet; file-backed
imports resolve during semantic validation but are rejected before Zig/C
emission.

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

// Private helper (not exported)
normalize :: fn(v: ref Vec3) {
    len := length(v)
    v.x /= len
    v.y /= len
    v.z /= len
}
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

// Planned syntax; not a current parser form
// using import "vector"

// Resolver-validated local aliases; codegen modes reject before backend output
sibling :: import "./sibling"
subfolder :: import "subfolder/helper"

// Parent traversal imports are rejected by the resolver
parent :: import "../utils"  // error
```

### 10.3 Standard Library Status

Current implementation:

- `std/io` and `io` are virtual modules backed by compiler/backend mappings.
- `std/math` and `math` are virtual modules backed by compiler/backend mappings.
- Virtual stdlib modules are registered through the module resolver and may be
  imported with arbitrary local aliases, for example
  `console :: import "std/io"`.
- Local file imports such as `./vector` can resolve from on-disk `.a7` files
  during semantic validation, but backend lowering/linking for file-backed
  modules is not implemented yet. Compile/pipeline/doc modes reject them before
  codegen instead of emitting invalid Zig/C.

Planned, not implemented as public stdlib modules yet:

- `std/string`
- `std/mem`
- `std/collections`

### 10.4 Visibility Rules

- `pub` modifier only applies to **global/top-level declarations**:
  - Global functions
  - Global variables and constants
  - Type declarations (struct, enum, union)
- `pub` items are exported from the file/module
- Non-`pub` items are file-private
- No protected/internal visibility
- **Struct fields are always file-private** (cannot be marked `pub`)
- Function parameters and local variables cannot be marked `pub`

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

Current virtual modules provide `io.print`, `io.println`, `io.eprintln`, and
math calls such as `math.sqrt`, `math.abs`, `math.floor`, `math.ceil`,
`math.sin`, `math.cos`, `math.tan`, `math.log`, `math.exp`, `math.min`, and
`math.max`. Some typed math builtin spellings such as `sqrt_f32` and `sqrt_f64`
also map through the stdlib registry.

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

```a7
// Literals
TOKEN_INT_LITERAL       // 42, 0x2A, 0b101010
TOKEN_FLOAT_LITERAL     // 3.14, 2.71e10
TOKEN_CHAR_LITERAL      // 'a', '\n', '\x41'
TOKEN_STRING_LITERAL    // "hello", "multi\nline"
TOKEN_BOOL_LITERAL      // true, false
TOKEN_NIL_LITERAL       // nil

// Identifiers and Keywords
TOKEN_IDENTIFIER        // user_defined_names
TOKEN_AND               // and
TOKEN_AS                // as
TOKEN_BOOL              // bool
TOKEN_BREAK             // break
TOKEN_CASE              // case
TOKEN_CAST              // cast
TOKEN_CHAR              // char
TOKEN_CONST             // const
TOKEN_CONTINUE          // continue
TOKEN_DEFER             // defer
TOKEN_DEL               // del
TOKEN_ELSE              // else
TOKEN_ENUM              // enum
TOKEN_F32               // f32
TOKEN_F64               // f64
TOKEN_FALL              // fall
TOKEN_FALSE             // false
TOKEN_FN                // fn
TOKEN_FOR               // for
TOKEN_I8                // i8
TOKEN_I16               // i16
TOKEN_I32               // i32
TOKEN_I64               // i64
TOKEN_IF                // if
TOKEN_IMPORT            // import
TOKEN_IN                // in
TOKEN_ISIZE             // isize
TOKEN_MATCH             // match
TOKEN_NEW               // new
TOKEN_NIL               // nil
TOKEN_OR                // or
TOKEN_PUB               // pub
TOKEN_REF               // ref
TOKEN_RET               // ret
TOKEN_SELF              // self
TOKEN_SIZE_OF           // size_of
TOKEN_STRING            // string
TOKEN_STRUCT            // struct
TOKEN_TRUE              // true
TOKEN_TYPE              // type
TOKEN_U8                // u8
TOKEN_U16               // u16
TOKEN_U32               // u32
TOKEN_U64               // u64
TOKEN_UNION             // union
TOKEN_USING             // using
TOKEN_USIZE             // usize
TOKEN_VAR               // var
TOKEN_WHERE             // where
TOKEN_WHILE             // while

// Operators
TOKEN_PLUS              // +
TOKEN_MINUS             // -
TOKEN_STAR              // *
TOKEN_SLASH             // /
TOKEN_PERCENT           // %
TOKEN_EQUAL_EQUAL       // ==
TOKEN_NOT_EQUAL         // !=
TOKEN_LESS              // <
TOKEN_GREATER           // >
TOKEN_LESS_EQUAL        // <=
TOKEN_GREATER_EQUAL     // >=
TOKEN_AND_AND           // and
TOKEN_OR_OR             // or
TOKEN_BANG              // !
TOKEN_AMPERSAND         // &
TOKEN_PIPE              // |
TOKEN_CARET             // ^
TOKEN_TILDE             // ~
TOKEN_LEFT_SHIFT        // <<
TOKEN_RIGHT_SHIFT       // >>
TOKEN_EQUAL             // =
TOKEN_PLUS_EQUAL        // +=
TOKEN_MINUS_EQUAL       // -=
TOKEN_STAR_EQUAL        // *=
TOKEN_SLASH_EQUAL       // /=
TOKEN_PERCENT_EQUAL     // %=
TOKEN_AND_EQUAL         // &=
TOKEN_OR_EQUAL          // |=
TOKEN_CARET_EQUAL       // ^=
TOKEN_LEFT_SHIFT_EQUAL  // <<=
TOKEN_RIGHT_SHIFT_EQUAL // >>=

// Punctuation
TOKEN_COLON_COLON       // ::
TOKEN_COLON             // :
TOKEN_SEMICOLON         // ;
TOKEN_COMMA             // ,
TOKEN_LEFT_PAREN        // (
TOKEN_RIGHT_PAREN       // )
TOKEN_LEFT_BRACKET      // [
TOKEN_RIGHT_BRACKET     // ]
TOKEN_LEFT_BRACE        // {
TOKEN_RIGHT_BRACE       // }
TOKEN_DOT               // .
TOKEN_DOT_DOT           // ..
TOKEN_DOT_DOT_DOT       // ...
TOKEN_AT                // @
TOKEN_DOLLAR            // $ (for generic type parameters)
TOKEN_QUESTION          // ?

// Special
TOKEN_EOF               // End of file
TOKEN_NEWLINE           // \n (for layout-sensitive parsing)
TOKEN_COMMENT           // Comments (usually discarded)
TOKEN_ERROR             // Lexer error token
```

### 12.2 AST Node Types

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
AST_EXPR_DEREF          // Pointer dereference (ptr.val)
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

Each AST node contains:

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
2. Postfix (function calls, array access, field access, deref)
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
```

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

### 13.3 Expression Grammar

```ebnf
expr = assignment_expr

assignment_expr = 
    | logical_or_expr
    | logical_or_expr assign_op assignment_expr

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
    | postfix_expr "." "val"
    | postfix_expr "(" expr_list? ")"

primary_expr = 
    | identifier
    | literal
    | "(" expr ")"
    | "if" expr block "else" block_or_if
```

### 13.4 Statement Grammar

```ebnf
statement = 
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

defer_stmt = "defer" statement
```

---

## Appendix A: Language Semantics

### A.1 Evaluation Order

1. Function arguments: left-to-right
2. Binary operators: left-to-right
3. Assignment: right-to-left
4. Field initialization: declaration order

### A.2 Type Conversions

No implicit conversions except:
- Array to slice (safe widening)
- `T` to `ref T` in function calls
- Integer literals to any integer type if in range

### A.3 Name Resolution

1. Current scope
2. Enclosing scopes (outward)
3. File scope
4. Imported names
5. Built-in names

### A.4 Lifetime Rules

1. Stack values live until scope exit
2. Heap values live until explicit `del`
3. References must not outlive referent
4. Slices must not outlive backing array

---

## Appendix B: Standard Compiler Diagnostics

### B.1 Error Categories

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

- **W0xxx**: Unused code
- **W1xxx**: Deprecated features
- **W2xxx**: Performance issues
- **W3xxx**: Potential bugs

---

## Appendix C: Implementation Limits

| Feature | Minimum Limit |
|---------|---------------|
| Identifier length | 100 characters |
| Numeric literal length | 100 characters |
| String literal length | 65,535 bytes |
| Function parameters | 255 |
| Generic parameters | 32 |
| Nested blocks | 127 |
| Array dimensions | 8 |
| Struct fields | 1,023 |
| Union variants | 255 |
| Enum values | 65,535 |
| Import depth | 32 |
| Defer statements per scope | 255 |
| Match cases | 1,023 |

---

## Appendix D: ASCII Character Set Support

A7 supports the full ASCII character set (0-127) only. Characters outside this range are not supported in string literals, character literals, or identifiers.

### D.1 Escape Sequences

| Escape | ASCII Value | Description |
|--------|-------------|-------------|
| `\n`   | 10          | Line feed (newline) |
| `\r`   | 13          | Carriage return |
| `\t`   | 9           | Horizontal tab |
| `\b`   | 8           | Backspace |
| `\f`   | 12          | Form feed |
| `\v`   | 11          | Vertical tab |
| `\a`   | 7           | Alert (bell) |
| `\\`   | 92          | Backslash |
| `\'`   | 39          | Single quote |
| `\"`   | 34          | Double quote |
| `\0`   | 0           | Null character |
| `\xHH` | 0-127       | Hex escape (2 digits, ASCII only) |

---

## Appendix E: Implementation Status (a7-py)

Status snapshot (2026-05-08):

- ✅ Full compiler pipeline exists (tokenizer, parser, semantic passes, AST preprocessing, Zig backend, C backend).
- ✅ Examples have end-to-end verification for both Zig and C backends.
- ✅ Debug and release example artifact builds are available through `scripts/build_examples.py`.
- 📊 Test status: run `PYTHONPATH=. uv run pytest --tb=no -q` for the current branch.
- 🚫 Security status: `a7-py` is not a sandbox. Do not compile and execute untrusted A7 source.

### E.1 Current Open Gaps

1. **`fall` scope restrictions**
   - `fall` is supported in match statements and lowers in both Zig and C.
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
   - Basic `new`/`del` validation exists; full ownership/lifetime analysis is not complete.

4. **Backend semantic parity hardening**
   - Differential parity checks across backends should continue expanding for new language features.
   - C lowers side-effectful `match` expression scrutinees through generated single-evaluation locals in variable initializers, return values, assignments, function arguments, and I/O arguments.
   - C lowers raw `fn(...)` parameter and variable declarations as function pointers.
   - Function-type aliases resolve in semantic analysis and lower as C typedefs.

5. **Release packaging activation**
   - Python packaging and installed CLI are present.
   - Tag-triggered draft GitHub releases attach package, docs, and native
     example artifacts.
   - Package-registry publishing is not part of the current release workflow.

### E.2 Source Of Truth

- `MISSING_FEATURES.md` tracks language gaps with implementation notes.
- `TODO.md` tracks engineering and verification backlog.
- `RELEASE.md` tracks local release/debug build gates.
