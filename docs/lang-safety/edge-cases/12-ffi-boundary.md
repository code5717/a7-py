# Gap 12 — FFI boundary discipline

Status: Phase A research from before 2026-09-14; a deferred design note. Not
approved. Current decisions are in the [v1 decision ledger](../../plan/decisions.md).

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.12](../07-language-review.md#112-ffi--explicitly-absent).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

## Summary

A7 has no `extern` keyword. The contract in `05-for-a7.md` §4.7 makes FFI the
single boundary where the language stops enforcing safety. Foreign returns are
typed `Result<T, ForeignError>`, so the user must match. The shim is a small Zig
wrapper, trusted as an external promise. This gap collects design considerations
for when FFI is added.

Ada has mature FFI (`pragma Import`, `pragma Export`, `pragma Convention`), and
SPARK adds stricter import discipline. A7 should learn from both.

## Audit notes (2026-09-16)

- Note (2026-09-16): still accurate that FFI does not exist. `a7/tokens.py` has no
  `extern` keyword, and `STATUS.md` does not list FFI.
- Note (2026-09-16): Q12a ("roadmap defers") is in tension with the ledger. L1 puts
  a fuller v1 in scope, and L9 says established native libraries provide AI
  kernels, so some native boundary is needed for v1.
- Note (2026-09-16): the [memory plan](../../plan/memory.md) (proposed) replaces the
  `borrow` / `inout` framing with native descriptors (gate M12). A descriptor
  declares borrowing, retention, returned storage, alignment, completion, callbacks
  and thread affinity. Native code that retains storage without a declared owner is
  a compile error. This affects FFI-04, FFI-19, FFI-23, FFI-27, Q12e and Q12h.
- Note (2026-09-16): the memory plan removes stored and returned `ref` (M4) and
  says programs never name allocators. FFI-07 (returning `ref T`) and Q12h
  ("A7 owns its allocator") need restating under that plan.
- Note (2026-09-16): FFI-16 (`Bounded`) and FFI-18 (`Fin<f64>` fields) refer to
  user-visible refinements. `08-decisions.md` D.020 keeps refinements internal, and
  ledger L16 supersedes `Fin<F>`.
- Note (2026-09-16): `08-decisions.md` D.033 (FFI bit-width conversions inside
  extern shims) is superseded by ledger L4, which makes explicit-width integers
  ordinary types.
- Note (2026-09-16): Q12g concerns variadic C functions. A7 variadic parameters
  are parsed-only (CLAUDE.md "Docs Accuracy").

## Subcases

### Declaration form

| # | Pattern | Decision target |
| --- | --- | --- |
| FFI-01 | `extern fn libc_read(fd: i32, buf: inout []u8) -> Result<usize, Errno>` | Standard declaration |
| FFI-02 | `extern fn` without a `Result` return type | Compile error: foreign returns must be `Result` or `Option` |
| FFI-03 | `extern fn ... -> ()` (cannot fail) | Allowed: infallible foreign call |
| FFI-04 | `extern fn` taking `borrow []u8` | Allowed: foreign code promises not to retain |
| FFI-05 | `extern fn` taking `ref T` | Allowed: foreign code promises non-null |
| FFI-06 | `extern fn` taking `?ref T` | Allowed: foreign code may pass null |
| FFI-07 | `extern fn` returning `ref T` | Suspect: foreign code promises non-null; documented as trust |
| FFI-08 | Calling convention: `extern "C" fn ...` | Standard syntax; `"C"`, `"system"`, `"naked"` (Zig conventions) |
| FFI-09 | Linker name: `extern "C" fn alloc as "malloc"` | Sets the symbol name (analog of Ada `pragma Import(C, alloc, "malloc")`) |

### Type discipline

| # | Pattern | Decision target |
| --- | --- | --- |
| FFI-10 | Pass a `[]u8` slice | Lowered to a C-ABI `(ptr, len)` pair; foreign side sees `(*const u8, size_t)` |
| FFI-11 | Pass `string` | Same as `[]u8` if strings are slices; otherwise null-terminated conversion |
| FFI-12 | Pass `ref T` to a C `T*` | Lossless; non-null inferred |
| FFI-13 | Pass `?ref T` to a C `T*` that may be null | Lossless |
| FFI-14 | Pass `Option<T>` (non-pointer) | Forbidden; user unpacks and passes the inner value, with a sentinel for `none` |
| FFI-15 | Pass `Result<T, E>` | Forbidden; user matches and passes the inner value |
| FFI-16 | Pass `Bounded<T, lo, hi>` | Stripped to the base type at the boundary |
| FFI-17 | Pass a tagged union | Layout-incompatible with C; forbidden; user marshals by hand |
| FFI-18 | Pass a struct with a non-trivial field type (for example `Fin<f64>`) | Allowed if the layout matches C; user verifies |
| FFI-19 | Pass an `inout` argument | Lowered to `*T`; foreign code must respect its lifetime |
| FFI-20 | Pass a closure (when supported) | Foreign code gets a raw function pointer and an opaque data pointer; a separate documented hazard |
| FFI-21 | Pass `usize` to `size_t` | Lossless (A7 `usize` ≈ C `size_t`) |
| FFI-22 | Receive an opaque pointer (`void *` from C) | Represented as `OpaqueRef<Tag>`, with a named tag for type hygiene |

### Trust and isolation

| # | Pattern | Decision target |
| --- | --- | --- |
| FFI-23 | Foreign code reads a `borrow []u8` after the call returns | Documented hazard; the language cannot prevent it |
| FFI-24 | Foreign code overflows the stack | Outside language control; the stack-budget proof excludes FFI shim frames (Gap 05 SB-09) |
| FFI-25 | Foreign code corrupts memory | Outside language control; documented |
| FFI-26 | A7 calls foreign code from a signal handler | Outside language control; signal safety is the user's responsibility |
| FFI-27 | Foreign code stores a callback into A7 and calls it later | Forbidden at the type level unless modeled with a `'static`-like marker (open) |

### Build/link

| # | Pattern | Decision target |
| --- | --- | --- |
| FFI-28 | Naming a library to link: `@link("ssl")`? | Open: in source or in a build script |
| FFI-29 | Keeping headers and declarations in sync | Open: generated bindings or hand-written |
| FFI-30 | C layout, alignment and padding of A7 structs | Open: a `@repr(C)` attribute? |

## Examples

All examples in this file are proposals. FFI does not exist in A7.

FFI-01, FFI-08, FFI-09 and FFI-21, declarations:

```a7
// Proposed (no extern keyword exists; not implemented)
libc_read :: extern "C" fn(fd: i32, buf: []u8) Result(usize, Errno)   // FFI-01
c_alloc :: extern "C" fn(size: usize) ?OpaqueRef(CBlock) as "malloc"  // FFI-09, FFI-21, FFI-22
```

FFI-10, FFI-14 and FFI-15, marshalling at the call site:

```a7
// Proposed (not implemented)
buf: [256]u8
n := libc_read(fd, buf[0..256])?  // FFI-10: passes (ptr, len)

timeout: ?u32 = nil
raw: u32 = timeout.unwrap_or(0)   // FFI-14: sentinel 0 stands for "none"
set_timeout(raw)
```

The `getchar` false positive, wrapped as a typed optional:

```a7
// Proposed (not implemented)
c_getchar :: extern "C" fn() i32 as "getchar"

read_byte :: fn() ?u8 {
    c := c_getchar()
    if c < 0 {
        ret nil                   // EOF sentinel becomes nil
    }
    ret cast(u8, c)
}
```

FFI-27, FFI-28 and FFI-30, callbacks, linking and layout:

```a7
// Proposed (attributes other than @type_set are parsed-only or reserved)
@link("ssl")                      // FFI-28
@repr(C)                          // FFI-30
Header :: struct {
    tag: u32
    length: u32
}

on_done :: fn(code: i32) { io.println("done {}", code) }
run_async :: extern "C" fn(cb: fn(i32)) Result((), Errno)
run_async(on_done)?               // FFI-27: legal only if C drops cb before returning (Q12e)
```

## Interactions

| Gap | Interaction |
| --- | --- |
| 01 cast | FFI is the one place pointer casts may be needed (for example to opaque C pointers). The cast classifier has a special path for `extern` declaration types. |
| 02 nullable pointers | Declarations choose nullness per parameter and return; the language trusts them (FFI-07). |
| 03 definite assignment | FFI calls satisfy DA at the caller for `inout` / `set` parameters, as native calls do. |
| 04 NonZero division | FFI returns base types; the user promotes. |
| 05 stack budget | SB-09: each `extern fn` contributes a fixed budget, configurable per shim. |
| 06 typed arithmetic | FFI arguments and returns are base types; range info does not cross. |
| 07 bounded indexing | Slices crossing FFI lose bound proofs; the foreign side gets `(ptr, len)`. |
| 08 `Option<T>` / `Result<T, E>` | Required return shape for fallible FFI calls. |
| 09 refinement-lite | Refinements are stripped at the boundary. |
| 10 affine ownership | `inout` and `borrow` lower to raw pointers; foreign compliance is trust. |
| 11 finite floats | Bare floats cross; the user wraps afterward. |

## Failure modes

### False positives

- C APIs that do not fit the `Result` return rule, such as `getchar()` returning
  -1 at EOF as an ordinary value. Mitigation: wrap the extern in a thin A7 function
  that converts the sentinel into `Option<u8>` (see Examples).
- C functions with two outputs (set `errno` and return a value). Mitigation: a shim
  that returns one `Result<T, Errno>`.

### False negatives

- Foreign code that violates its declared contract. The language cannot detect
  this. It is the documented sole hazard.

### Ergonomic costs

- Every C function needs a wrapper. A real cost, matching the SPARK experience.
- Slice and string marshalling need care.

### Performance costs

- No per-call cost beyond the standard ABI shim.

## Open questions

- **Q12a.** When does FFI ship? The Phase A roadmap defers it; this gap is design
  only. (See audit note on L1 and L9.)
- **Q12b.** Bindings generation:
  - Hand-written `extern fn` declarations.
  - Generated from C headers, like Rust's `bindgen`.
  - Both.
- **Q12c.** `@link`: in source or in a build manifest?
- **Q12d.** `@repr(C)` for C-compatible struct layout: required for FFI? Always?
- **Q12e.** Callback pointers (FFI-27): supported, restricted or forbidden?
  Restricted looks right: foreign code may keep a callback only for the duration
  of one call (the borrow lasts through the call). Long-lived callbacks need a
  separate registration mechanism.
- **Q12f.** Opaque types (FFI-22): `OpaqueRef<Tag>` with a named tag, or anonymous
  `void *`? The named tag is more type-safe.
- **Q12g.** Variadic C functions (`printf` style): how? Probably a typed shim per
  call site.
- **Q12h.** Allocator interop: foreign code calls `malloc` and `free`, and A7's
  allocator is separate. Decision: A7 owns its allocator; foreign allocations cross
  only as opaque references.
- **Q12i.** Threads and signals: outside language scope; documented.

## Source citations

- No FFI exists.
- `docs/STATUS.md` does not list FFI; it should. Note (2026-09-16): still true.
- Ada: `pragma Import`, `pragma Export` and `pragma Convention` in
  `learn.adacore.com/courses/intro-to-ada/chapters/interfacing_with_c.html`.
- Zig: `extern fn` and `@cImport()`. A7 would reuse Zig's mechanism and add the
  `Result` return rule.

## Phase C decision-input summary

This gap is mostly deferred. Phase C records these decisions as design notes;
implementation is out of scope for that phase.

1. Q12b — bindings generation strategy.
2. Q12d — `@repr(C)` requirement.
3. Q12e — callback pointer discipline.
4. Q12f — opaque type representation.
5. Q12h — allocator interop policy.

FFI is the final implementation phase in
[`05-for-a7.md` §5](../05-for-a7.md#5-phased-plan-zero-runtime-error-ordering).
