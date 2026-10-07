---
title: Functions and callbacks
nav: Functions
group: Reference
summary: Declarations, parameters, returns, callbacks, and recursion restrictions.
order: 15
---

# Functions and callbacks

Declare a named function with `name :: fn(parameters) ReturnType { ... }`. Omit the return type for a function with no returned value. `ret expression` returns a value; `ret` exits a void function.

```a7
add :: fn(x: i32, y: i32) i32 {
    ret x + y
}
```

## Parameters and returned values

Value parameters are immutable. To update a local working value, copy a parameter into a `:=` variable. A `ref T` parameter modifies caller storage and receives an ordinary lvalue argument. Do not add address-of syntax at a call.

A function returns one value. Return a named struct when several results belong together. Multiple return values and destructuring are unavailable in the current backend.

## Nested functions

A function can declare a nested function that uses its own parameters and locals.
Capture-free nested functions can be called or returned as function values. The
backend gives them distinct file-scope Zig names, so separate enclosing functions
can each declare `helper`.

```a7
outer :: fn(k: i32) i32 {
    helper :: fn(v: i32) i32 { ret v + 1 }
    ret helper(k)
}
```

Reading an enclosing local or parameter currently fails during code generation
with exit 7. Pass that value as an argument instead. Nested bodies receive type,
return-path, and control-flow checks. See the
[native regression cases](https://github.com/code5717/a7-py/blob/master/test/test_nested_function_codegen.py).

## Function types and callbacks

A function type uses `fn(i32, i32) i32`. A named alias can describe a callback, and a parameter of that type can be called inside the function. See the complete [function pointer example](https://github.com/code5717/a7-py/blob/master/examples/022_function_pointers.a7) and [callback example](https://github.com/code5717/a7-py/blob/master/examples/027_callbacks.a7).

This complete program shows both a raw function type and an alias. It prints
`11 11` followed by a newline:

```a7
io :: import "std/io"

BinaryOp :: fn(i32, i32) i32

add :: fn(a: i32, b: i32) i32 {
    ret a + b
}

apply :: fn(op: BinaryOp, a: i32, b: i32) i32 {
    ret op(a, b)
}

main :: fn() {
    raw: fn(i32, i32) i32 = add
    callback: BinaryOp = add
    io.println("{} {}", raw(8, 3), apply(callback, 8, 3))
}
```

`apply` calls the supplied function. These function values do not imply closure
capture or recursive callbacks. For an event-dispatch example with a no-argument
`fn()` callback, see `027_callbacks.a7`.

Function references and nullable heap references are not interchangeable. A declared `ref fn(...) ...` can represent a nullable function reference; ordinary function values have their declared function type.

## Receiver-style functions

A function can take a struct or `ref` struct as its first parameter. Call it explicitly as `increment(counter)`. Method-call sugar such as `counter.increment()` is planned, not current semantic support.

```a7
Counter :: struct {
    value: i32
}
increment :: fn(counter: ref Counter) {
    counter.value += 1
}
```

## Recursion and variadics

Recursion is unavailable. The compiler rejects direct calls back to the same function, mutual call cycles, and known cycles through local aliases and callback trampolines. Use loops, explicit stacks, or index-based worklists, as in the linked-list and binary-tree examples.

Variadic declaration syntax such as `values: ..i32` is limited to parsing and partial declaration checks. Codegen rejects user variadic parameters before backend emission. The compiler's special handling of `io.println` does not make general variadic functions runnable.

## Status and restrictions

Status: supported for ordinary functions and example-backed callbacks. Generic specialization, variadic lowering, and broader method-style call chains have separate limits. See [generics](generics.md) and [memory](memory.md).

## Evidence

- [examples/004_func.a7](https://github.com/code5717/a7-py/blob/master/examples/004_func.a7)
- [examples/017_methods.a7](https://github.com/code5717/a7-py/blob/master/examples/017_methods.a7)
- [examples/022_function_pointers.a7](https://github.com/code5717/a7-py/blob/master/examples/022_function_pointers.a7)
- [examples/027_callbacks.a7](https://github.com/code5717/a7-py/blob/master/examples/027_callbacks.a7)
- [docs/STATUS.md](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
