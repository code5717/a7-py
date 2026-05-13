# Gap 12 — FFI boundary discipline

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.12](../07-language-review.md#112-ffi--explicitly-absent).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

A7 has no `extern` keyword today. The contract documented in
`05-for-a7.md` §4.7 reserves FFI as the **single** boundary at which
the language stops enforcing safety. Foreign returns are typed
`Result<T, ForeignError>` so the user matches; the shim is a small
Zig wrapper trusted as an external promise. This gap collects the
design considerations for *when FFI is eventually added*.

Ada has well-developed FFI: `pragma Import`, `pragma Export`,
`pragma Convention`. SPARK extends with stricter import discipline.
A7 should learn from both.

## Subcases

### Declaration form

| # | Pattern | Decision target |
| --- | --- | --- |
| FFI-01 | `extern fn libc_read(fd: i32, buf: inout []u8) -> Result<usize, Errno>` | Standard declaration |
| FFI-02 | `extern fn` without `Result` return type | **Compile error**: foreign returns must be `Result` or `Option` |
| FFI-03 | `extern fn` with `void` (returns no error) | Allowed: `extern fn ... -> ()` (infallible foreign call) |
| FFI-04 | `extern fn` taking `borrow []u8` | Allowed: foreign code promises not to retain |
| FFI-05 | `extern fn` taking `ref T` | Allowed: foreign code promises non-null |
| FFI-06 | `extern fn` taking `?ref T` | Allowed: foreign code may pass null |
| FFI-07 | `extern fn` returning `ref T` | **Suspect** — foreign code promises non-null; documented as trust |
| FFI-08 | Calling-convention annotation: `extern "C" fn ...` | Standard syntax; `"C"`, `"system"`, `"naked"` (Zig conventions) |
| FFI-09 | Linker name: `extern "C" fn alloc as "malloc"` | Specify the symbol name (Ada `pragma Import(C, alloc, "malloc")` analog) |

### Type discipline

| # | Pattern | Decision target |
| --- | --- | --- |
| FFI-10 | Pass `[]u8` slice | Lowered to `(ptr, len)` C-ABI tuple; foreign side sees `(*const u8, size_t)` |
| FFI-11 | Pass `string` | Same as `[]u8` if A7 strings are slices; otherwise null-terminated conversion |
| FFI-12 | Pass `ref T` to a C function expecting `T*` | Lossless; non-null inferred |
| FFI-13 | Pass `?ref T` to a C function expecting `T*` (may be null) | Lossless |
| FFI-14 | Pass `Option<T>` (non-pointer) | Forbidden directly; user destructures and passes inner value (with a sentinel for `none`) |
| FFI-15 | Pass `Result<T, E>` | Forbidden directly; user pattern-matches and passes inner value |
| FFI-16 | Pass `Bounded<T, lo, hi>` refinement | Stripped to base type at the boundary |
| FFI-17 | Pass tagged union | Layout-incompatible with C; forbidden directly; user marshals manually |
| FFI-18 | Pass struct with non-trivial layout (e.g., `Fin<f64>`-typed field) | Allowed if the underlying layout matches C; user verifies |
| FFI-19 | Pass `inout` arg | Lowered to `*T`; foreign code must respect lifetime |
| FFI-20 | Pass closure (when supported) | Foreign code receives raw function pointer + opaque data pointer; documented as separate FFI hazard |
| FFI-21 | Pass `usize` arg expecting `size_t` | Lossless (A7 `usize` ≈ C `size_t`) |
| FFI-22 | Receive opaque pointer (`*void` from C) | Represented as `OpaqueRef<Tag>` (named tag for type hygiene) |

### Trust and isolation

| # | Pattern | Decision target |
| --- | --- | --- |
| FFI-23 | Foreign code reads from a `borrow []u8` after the call returns | Documented hazard; the language cannot prevent |
| FFI-24 | Foreign code stack-overflows | Out of language control; stack-budget proof excludes FFI shim frames (per Gap 05 SB-09) |
| FFI-25 | Foreign code corrupts memory | Out of language control; documented |
| FFI-26 | A7 program calls foreign code from inside a signal handler | Out of language control; signal-safe FFI is the user's responsibility |
| FFI-27 | Foreign code stores a callback pointer to A7 code, calls back at undefined time | Forbidden at the type level unless explicitly modeled with a `'static`-equivalent (open) |

### Build/link

| # | Pattern | Decision target |
| --- | --- | --- |
| FFI-28 | Specifying a library to link: `@link("ssl")` attribute? | Open: declarative or via build script |
| FFI-29 | Header / interface synchronisation | Open: machine-generated bindings vs hand-written |
| FFI-30 | C compatibility: layout, alignment, padding of A7 structs | Open: `@repr(C)` attribute? |

## Interactions

- **Gap 01 cast.** FFI is the one site where pointer casts may be
  necessary (e.g., to opaque-typed C pointers). Cast classifier
  has a special path for `extern`-decl types.
- **Gap 02 nullable pointers.** FFI declarations choose nullness
  per parameter / return; the language trusts the declaration
  (FFI-07).
- **Gap 03 definite assignment.** FFI calls satisfy DA at the
  caller for `inout`/`set` parameters; same as native calls.
- **Gap 04 NonZero division.** FFI returns base types; user
  promotes.
- **Gap 05 stack budget.** SB-09: each `extern fn` contributes a
  fixed budget (configurable per shim).
- **Gap 06 typed arithmetic.** FFI args/returns are base types;
  range info doesn't cross.
- **Gap 07 bounded indexing.** Slices passed across FFI lose
  bound proofs; the foreign side gets `(ptr, len)`.
- **Gap 08 `Option<T>` / `Result<T, E>`.** Mandatory return shape
  for fallible FFI calls.
- **Gap 09 refinement-lite.** Refinements stripped at the boundary.
- **Gap 10 affine ownership.** `inout` / `borrow` modes lower to
  raw pointers; foreign code's compliance is trust.
- **Gap 11 finite floats.** Bare floats cross; user wraps after.

## Failure modes

### False positives

- Legitimate C APIs that don't fit the `Result`-return discipline
  (e.g., `getchar()` returning -1 on EOF as a regular value).
  Mitigation: wrap the bare extern in a thin user-written A7
  function that converts the sentinel to a typed `Option<u8>`.
- Multi-return C functions (set errno + return value). Mitigation:
  shim into a single `Result<T, Errno>`.

### False negatives

- Foreign code that violates its declared contract. The language
  cannot detect this; this is the **documented** sole hazard.

### Ergonomic costs

- Every C function needs a wrapper. Real cost; matches the SPARK
  experience.
- Slice / string marshalling requires care.

### Performance costs

- Zero per-call beyond the standard ABI shim.

## Open questions

- **Q12a.** When does FFI ship? Roadmap defers; this gap exists
  for design only.
- **Q12b.** Bindings generation. Three options:
  - Hand-written `extern fn` declarations.
  - Tool-generated from C headers (analogous to `bindgen` for
    Rust).
  - Both.
- **Q12c.** `@link` directive: declarative in source vs in a build
  manifest.
- **Q12d.** `@repr(C)` for laying out A7 structs to C-ABI-compatible
  shape. Required for FFI? Always?
- **Q12e.** Callback pointers (FFI-27) — supported, restricted, or
  forbidden? Restricted seems right: foreign code may only retain
  callbacks during a specific call's duration (the borrow extends
  through the call). Long-lived callbacks need a separate
  registration mechanism.
- **Q12f.** Opaque types (FFI-22) — `OpaqueRef<Tag>` with named tag
  for type hygiene, vs anonymous `*void`. Named tag is more typesafe.
- **Q12g.** Variadic C functions (`printf`-style) — supported how?
  Probably wrap each call site in a typed shim.
- **Q12h.** Allocator interop — foreign code calls `malloc`/`free`;
  A7's allocator is separate. Decision: A7 owns its allocator;
  foreign allocations cross only as opaque references.
- **Q12i.** Threading / signal interaction — out of language scope;
  documented.

## Source citations

- No FFI exists today.
- `docs/STATUS.md` doesn't currently list FFI; should add.
- Ada reference: `pragma Import` / `pragma Export` /
  `pragma Convention` discussions in
  `learn.adacore.com/courses/intro-to-ada/chapters/interfacing_with_c.html`.
- Zig reference: `extern fn` and `@cImport()` — A7 inherits Zig's
  underlying mechanism, plus the `Result`-return discipline on top.

## Phase C decision-input summary

This gap is mostly *deferred*. Phase C records the decisions
below as **design notes** for future implementation, but the
implementation phase is out of scope.

1. Q12b — bindings generation strategy.
2. Q12d — `@repr(C)` requirement.
3. Q12e — callback pointer discipline.
4. Q12f — opaque type representation.
5. Q12h — allocator interop policy.

The roadmap phase for FFI is the final implementation phase per
[`05-for-a7.md` §5](../05-for-a7.md#5-phased-plan-zero-runtime-error-ordering).
