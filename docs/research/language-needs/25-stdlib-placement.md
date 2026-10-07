# Stdlib placement audit: compiler vs library vs never

Scope: place every pending stdlib item in exactly one bucket. Rule: small
compiler, fat stdlib. Default is LIBRARY unless syntax or codegen is
required. Sources: reports 10 (networking/system), 16 (ecosystem), 03
(collections/stdlib). See `docs/SPEC.md` §10.3, `a7/stdlib/`.

Buckets: COMPILER = new syntax or codegen in `a7/`. LIBRARY = A7 or
lowered Zig code over OS calls, no grammar change. NEVER = refused,
with reason.

## 1. C / C++ interop

C-only interop is enough. A `cextern` block plus a C-header import maps
1:1 to Zig `extern fn` + `@cImport` (report 16 §3). No name mangling,
no header translation beyond what Zig already does.

C++ namespaces are NEVER. Zig, Odin, Rust, and Go all draw the same
line: C++ binds through a flat `extern "C"` shim written on the C++
side. Reasons: namespaces, classes, templates, overloads, and
exceptions each need their own lowering; the compiler would grow a
second type system. A7 refuses the same way. C++ users write the shim.

Placement: C interop = LIBRARY (later, thin lowering to Zig extern).
C++ namespaces/classes/templates/exceptions = NEVER.

## 2. Regex

No language syntax. No regex literal, no match operator. Every
comparison language either keeps regex out of the core (Zig ships
none, deliberately; Rust keeps `regex` an external crate) or ships it
as an ordinary library (Go `regexp` RE2, Odin `core:text/regex,
Python `re`).

A7 follows the library side if it ships one at all: a `std/regex`
module with one linear-time engine (RE2-style, Go/Rust model), never
backtracking syntax in the compiler. Glob and prefix matching in
`std/string` cover tooling uses today.

Placement: LIBRARY (later, only on a qualified use case). Report 16
says never-until-proven; this audit keeps that gate and names the
bucket it would land in.

## 3. Crypto

No compiler intrinsic. No `hash` keyword, no constant-folded cipher.
Side-channel risk is the reason crypto stays a thin wrapper, not new
code: constant-time loops, secret zeroing, and nonce handling are
easy to break in a hand-written stdlib and hard to test.

Comparison: Zig `std.crypto` and Go `crypto/*` ship primitives in
stdlib (large audit surface their teams carry). Rust refuses: `ring`
and `rustcrypto` are audited third-party crates, not std. Python
`hashlib` wraps OpenSSL instead of implementing ciphers.

A7 takes the Python/Rust shape: never implement primitives in A7
stdlib. When TLS or hashing needs primitives, call OS/Zig-provided
ones through C interop. Document "A7 does not ship crypto" as a
standing rule (report 16 §6).

Placement: LIBRARY (later, wrapper over OS/Zig primitives only).
New primitives = NEVER.

## 4. Serialization and formats

JSON: LIBRARY (later). `std/json` with `stringify(T)` / `parse(T)`
lowered to Zig `std.json`, struct-field driven. Same shape as Zig
`std.json`, Odin `core:encoding/json`, Go `encoding/json`. Rust
`serde_json` is external; A7 keeps it in std because report 10 needs
it for HTTP work.

YAML/TOML: NEVER in std. No binary formats (gob, bincode) in std
either. YAML's spec is large and its parsers carry a history of
alias/billion-laughs bugs; TOML believers can vendor a package once
C interop or a registry exists. JSON plus A7 struct literals cover
config. Revisit only with a qualified use case.

## 5. System surface

Files/paths/process: LIBRARY (now). `std/fs` (`read_file`,
`write_file`, `File{open, read, write, close}`), `std/path` (`join`,
`base`, `ext`, `is_abs`), `std/process` (`args`, `env_get`, `run`).
No concurrency needed; unblocks CLI programs and tests. Reports 03
and 10 agree this ships first.

Time/date: LIBRARY (now, minimal). `now`, `sleep`, duration
arithmetic on `i64` timestamps. No timezone database, no calendar
formatting in V1 (Go `time` is the reference; Zig `std.time` shows
the minimal viable shape; Odin `core:time` shows what to defer).

Args: LIBRARY (now). Runtime accessor only: count plus indexed
access as `string` (~10 lines of backend, report 16 §8). A
Go-`flag`-style declarative parser is later; parsing loops are
ordinary A7 code.

Logging: LIBRARY (later, small). `std/log` with debug/info/warn/error
levels on Zig `std.log`, stderr sink reuses `std/io`. Structured
key-value logging deferred (Go `log/slog` is the model to copy later;
Rust `tracing` stays out).

Random: LIBRARY (later). Seeded PRNG (`gen`, `gen_range`) lowering to
Zig `std.Random`; deterministic default seed for tests, OS seed
opt-in. No stdlib CSPRNG claim; keys and TLS nonces use
`std/crypto_rand` over the OS source.

Subprocess: LIBRARY (later). `std/process.run(cmd)` returning exit
code plus output, after files/paths and error propagation (`?` +
`Result`) land. One verb, not a job-control framework.

SIMD: NEVER (explicit intrinsics in std). No `std/simd` vector types,
no compiler auto-vectorizer promise. Zig exposes SIMD through vector
types; A7 gets scalar codegen right first. Revisit as LIBRARY only
when a backend vector lowering exists.

## 6. Network surface

Sockets: LIBRARY (later). One `dial_tcp` / `listen_tcp` pair (Go
model), `TcpStream{read, write, close}`, `UdpSocket{send_to,
recv_from}`, all returning `Result(_, NetErr)`. Needs G5 error
propagation and G7 tasks first; blocking sockets without tasks are
unusable.

DNS: LIBRARY (later, with sockets). `resolve(host)` next to dial, not
a separate package. Local-resolver tests only.

TLS: LIBRARY (later, after sockets). `tls.wrap(stream, host)` upgrades
a TCP stream; no parallel raw-socket stack. Cert verify on by default.
Primitives come from the OS per §3, never fresh A7 cipher code.

HTTP client: LIBRARY (later, after TLS). `get(url)`, `post(url,
body)`, `Client{get, post, timeout}`.

HTTP server: LIBRARY (later, last). `serve(addr, handler)` with one
handler shape `fn(req, res)`. Needs task groups and cancellation
(client disconnect) from G7.

## 7. Final lists

COMPILER (none of these items). No new syntax or codegen in this
audit; `cextern` block when it comes is the only grammar-adjacent
work and it lowers 1:1 to Zig extern.

LIBRARY now: files/paths, time (minimal), args accessor, process
basics — each needs no concurrency and unblocks CLI programs.

LIBRARY later (order): owning String/List/Map + `std/string`,
`std/mem` → subprocess/run → seeded random → logging (levels) →
sockets/DNS → TLS wrapper → JSON → HTTP client → HTTP server.

NEVER: C++ namespaces/classes/templates/exceptions (shim rule);
regex syntax or backtracking engine; fresh crypto primitives;
YAML/TOML/binary formats in std; SIMD intrinsics in std — each
would grow compiler or audit surface for no V1 need.
