# 08 — Native boundary + release posture

Date: 2026-10-02. Scope: C-interface ABI descriptors, handle ownership,
kernel-library bridge, platform matrix, ReleaseFast check-stripping vs L39,
artifact naming/provenance.

## 1. Current posture (Zig-only)

- Single backend: `a7/backends/zig.py` emits Zig source; no C/IR backend
  exists. `a7/backends/base.py` + `__init__.py` hold the registry.
- CLI build path (`a7/cli.py:168-171`): `zig build-exe program.zig -O
  Debug|ReleaseFast -femit-bin=...` in a temp dir, atomic `os.replace`
  to destination. `a7 run` executes the binary in place.
- Script path (`scripts/build_examples.py:24-28,98-140`): debug `-ODebug`,
  release `-OReleaseFast`, with `zig ast-check` + `zig fmt --check` gates
  before `build-exe`.
- Arithmetic rule (`a7/backends/zig.py:2074-2083`, SPEC A.2): debug always
  wraps (`+%`); release drops the wrapping suffix only where the safety
  pass proves range fit. `--no-nonwrap` forces wrapping in both profiles
  (`a7/cli.py:249`, `scripts` has no equivalent flag — gap).
- Entry-point rule (`a7/compile.py:293-299`): `main :: fn()` required
  unless `--lib` (`a7/cli.py:111,253`). `--lib` is check-only today; no
  static/shared library emission path exists.
- No FFI surface: grep finds no `extern`, `@cImport`, `linkLibc`, or native
  import in `a7/` except the Zig keyword table (`zig.py:436`). A7 source
  has no `extern` declaration form; SPEC §Interoperability ("Clean C ABI
  compatibility") is aspiration, not implementation.
- V1 qualification target is Linux x86-64, Python 3.13, Zig 0.16.0
  (`a7/cli.py:100-105`). Release workflow pins
  `zig-x86_64-linux-0.16.0` (`.github/workflows/release.yml:19`).

## 2. ReleaseFast check-stripping vs L39

- L39 (decisions.md:118): required runtime checks **remain in release
  builds**. Fail-closed contract; any change needs a migration packet.
- Conflict: `-OReleaseFast` tells Zig to strip all safety: integer
  overflow checks, bounds checks, and `unreachable` become UB. A7's own
  wrapping/nonwrap split is deliberate, but any future A7-level check
  (bounds, nil, cast) emitted as plain Zig indexing/arithmetic would be
  silently stripped in release — violating L39.
- Fix direction: safety-critical checks must be emitted in
  ReleaseFast-proof form — explicit `if` + `unreachable`-free error path
  (return error, panic via `std.debug.panic`, or abort), never bare
  `arr[i]`, `a + b`, or `x.?` where the check matters. Reserve bare
  operators for proof-discharged cases only.
- Backstop options (cheapest first):
  1. Emit checks as explicit branches returning errors (survives any `-O`).
  2. Add a codegen assertion pass: grep emitted Zig for bare indexing /
     nonwrap ops lacking a proof token before `build-exe`.
  3. Downgrade release to `-OReleaseSafe` until the proof pipeline lands;
     keep `ReleaseFast` for explicitly opted-in, proof-clean modules.
  4. `--no-nonwrap`-style flag per check class (`--keep-bounds-checks`)
     for users who want speed with receipts.

## 3. How Zig / Odin / Rust handle FFI + release modes

- Zig: `extern fn` + explicit ABI (`extern`, `callconv(.c)`), `extern struct`
  with C layout, `@cImport`/`translate-c` for headers, `linkLibc` /
  `linkSystemLibrary` in build scripts. Four modes: Debug, ReleaseSafe
  (checks on), ReleaseFast (checks off, fast math), ReleaseSmall.
  The mode/check matrix is explicit — A7 should copy that explicitness.
- Odin: `foreign import` blocks with `cdecl`/`stdcall` calling
  conventions, `foreign fn` declarations, context allocator passed
  implicitly. Bounds/overflow assertions controlled by `-o:none|minimal|
  aggressive` flags, orthogonal to `-debug`/`-o:speed|size`. Lesson:
  separate the check level from the opt level; A7 currently conflates
  them in one `--profile` flag.
- Rust: `extern "C"` blocks are `unsafe` by construction;GYm `repr(C)`
  for layout; Miri + `-C debug-assertions` keep cheap checks in release
  while overflow checks stay debug-only unless `-C overflow-checks=on`.
  Lesson: mark the boundary `unsafe`/explicit, and ship per-check
  toggles rather than one global profile.

## 4. Minimal checked native-interface sketch (L41 direction)

L41 (decisions.md:120): minimal C interface, implemented through Zig;
app code never manages raw native pointers.

```a7
// Proposed, not implemented. All descriptors compile-time literals.
native "libc" {
    fn puts(s: []u8) i32 = "puts"      // symbol name explicit
}

main :: fn() i32 {
    h := native_open("libc", "puts", sig(fn([]u8) i32))  // handle, not pointer
    defer native_close(h)                                 // ownership: open/close pair
    return native_call(h, "hello".bytes())
}
```

Rules: (a) descriptor (library, symbol, signature triple) is a
compile-time constant — no dynamic `dlsym` strings from variables;
(b) handles are opaque linear values: `native_open` returns owned
handle, `native_close` consumes it, use-after-close is a compile
error; (c) only plain-old-data crosses (`i32`, `bool`, byte slices) —
slices are copied or pinned for the call duration, never aliased;
(d) every crossing re-validates: length fits `usize`, enum in range,
handle live — checks emitted as explicit branches per §2, so they
survive ReleaseFast; (e) failures return A7 errors, never unwind
across the boundary.

## 5. Kernel-library bridge

The same handle discipline covers kernel/library services (files,
sockets, GPU buffers): one `resource` type with open/use/close, never
a raw fd or device pointer in app code. Zig's `std.os` / `std.fs`
backs the implementation; A7 exposes only checked constructors
(open path, bind addr) that validate arguments before the syscall.
Deferred: async completion, zero-copy mapping, custom allocators.

## 6. Platform-matrix proposal

| Tier | Target | Gate |
|---|---|---|
| 1 supported | Linux x86-64, Zig 0.16.0 | full gate incl. E2E |
| 2 best-effort | Linux aarch64, macOS arm64 | `build_examples.py` smoke |
| 3 declared-unsupported | Windows, 32-bit | clear diagnostic, no silent UB |

Steps: (1) add `-target` passthrough to `a7 build` (Zig already
cross-compiles; A7 just never exposes it); (2) extend artifact names
with target triple (see §7); (3) per-target `bench/pins/` only for
tier 1; (4) `isize`/`usize` widths (SPEC:277) pinned per target in
layout tests. `a7 doctor` already reports platform — extend it to
state the tier.

## 7. Artifact naming / provenance (current + fix)

- Current: `a7-example-artifacts-linux-x86_64-zig0.16.0-<profile>.tar.gz`
  (release.yml:79) — platform/toolchain/profile encoded. Good.
- Provenance: `scripts/generate_release_manifest.py` → `dist/SHA256SUMS`,
  verified by `verify_release_manifest.py`, plus `gh attestation verify`
  per archive (RELEASE.md:100-143). Package, docs, and native archives
  all covered; archive member lists asserted.
- Gaps: (a) no provenance for ad-hoc `a7 build` binaries (no embedded
  version/profile stamp — consider `--version`-stamped build-id);
  (b) `--no-nonwrap` not reflected in artifact names; (c) Windows
  `.exe` suffix handled in CLI but untested in CI (tier 3 above).
