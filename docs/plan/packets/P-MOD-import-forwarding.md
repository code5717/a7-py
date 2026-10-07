# Import forwarding decision

Approved as L76 on 2026-10-07: "Keep imports local (Recommended)".
This decision covers access through another file's import alias. It is implemented
and qualified in full source manifest `27c4c26e`, including direct-import and
public-wrapper native controls. The alternative below is not selected. See
[Status](../../STATUS.md) for the qualification boundary.

## Behavior before the decision

```a7
// b.a7
value::fn()i32{ret 42}
```

```a7
// a.a7
b::import "./b"
```

```a7
// main.a7
a::import "./a"
main::fn(){x:=a.b.value()}
```

The combined module candidate emits Zig with exit 0. Native build exits 7:
`error: use of undeclared identifier 'a'`. The existing compiler has the same
emission gap. No successful native behavior was found for this example.

The current probe uses frozen stage 10, checker `2a2e6f60` and safety `607f1fde`.
Sources, commands and diagnostics are retained in
`tmp/v1-completion-2026-10-07/module-reexport-decision/results.json`.
An initial incorrect CLI invocation exited 2; the corrected `--mode compile`
invocation supplies the exit-0 evidence. No generated program was executed.

## Approved behavior

An import alias belongs to its declaring file and is not automatically exposed
through that file. Reject `a.b.value()` at semantic checking with exit 6 and a
message that `b` is an import alias of `a`, followed by a direct-import example.
Ordinary exported declarations, including a public function that calls its own
imports, remain accessible.

The entry file can import the dependency directly:

```a7
b::import "./b"
main::fn(){x:=b.value()}
```

Or `a` can expose an ordinary function:

```a7
// a.a7
b::import "./b"
value::fn()i32{ret b.value()}
```

```a7
// main.a7
a::import "./a"
main::fn(){x:=a.value()}
```

This adds no syntax. A presently accepted emission-only program receives an
earlier, located error. Direct imports and ordinary public wrappers keep their
existing behavior. The rule must cover value, call, type and constant paths,
including longer chains; it must preserve underscore privacy and local shadows.
It does not change directory fallback, bare imports, `pub`, local `__` names,
file identity, initialization order or struct-field access.

The parser already rejects multi-dot type annotations such as `x:a.b.Box`
and literals such as `a.b.Box{}` with exit 5. That grammar remains unchanged.
The semantic exit-6 rule applies to parsed constructs, including `a.b` used as
a type or literal name and longer expression chains such as `a.b.value()`.

## Alternative

Expose non-private import aliases as namespace members. Then `a.b.value()`
would build and run, and nested type/constant paths would resolve through the
same chain. Each module boundary would still enforce underscore privacy.
This requires a defined forwarding rule and matching resolver, checker and
lowering behavior. It makes `a`'s imports part of `a`'s public interface.

## Acceptance checks

- The chosen rule applies consistently to calls, types, constants and chains.
- Direct-import and wrapper controls build and print `42` in all profiles.
- Private names remain inaccessible through every path.
- A normal struct field named `b` remains a field, including `a.value.b`.
- Local shadows and same-name declarations in separate files keep their identity.
- Parsed forwarded-import forms receive exit 6 before Zig compilation.
  Unsupported multi-dot type/literal syntax keeps parser exit 5. Successful
  Zig emission alone does not qualify the accepted controls.
