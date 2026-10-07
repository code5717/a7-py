# Networking and system stdlib needs

Scope: TCP/UDP sockets, DNS, TLS, HTTP client/server, plus supporting
surface: files/paths, process, time, random. Sources: `a7/stdlib/`
(`io.py`, `math.py`), `docs/SPEC.md` §10.3, `docs/plan/README.md`
gates G5/G7, standing direction L1 (fuller standard library).

Standing direction: small compiler core, fat standard library. Sockets,
TLS, and HTTP are library code over OS calls, not syntax. The compiler
grows no network primitives; `std/net`, `std/http`, `std/tls`,
`std/fs`, `std/path`, `std/process`, `std/time`, `std/rand` carry the
weight.

## 1. What A7 has today

Nothing beyond console output and math. Verified in `a7/stdlib/`:

- `io`: `print`, `println`, `eprintln` only. All panic on failure; no
  recoverable I/O (plan README G5 notes this).
- `math`: `sqrt/abs/floor/ceil/sin/cos/tan/log/exp/min/max` only.
- No files, paths, process, time, random, sockets, DNS, TLS, or HTTP.
- SPEC §10.3 names `std/string`, `std/mem`, `std/collections` as planned
  only; no `std/net` or `std/http` section exists yet.

## 2. What others provide

- Zig std: `std.net` (TCP/UDP, `Address`, `StreamServer`, DNS via
  `std.net` address parsing + `std.dns` client), `std.tls` (client only,
  no cert verification helpers), `std.http` (client + low-level server),
  `std.fs` (files/dirs/paths), `std.process` (args/env/child),
  `std.time` (timestamp/sleep), `std.Random` (xoshiro/SplitMix).
  Pattern: explicit allocator on every call; A7 must not copy that
  (compiler-managed extents per L15/L17 instead).
- Odin core: `net` (TCP/UDP, DNS dial, TLS via `crypto/tls`), `net/http`
  (client + server handlers), `os` (files/env/process), `time`,
  `rand`, `path/filepath`. Builtin `map`/`dynamic` keep the common case
  small; same lesson applies: one default socket/TLS path, no option maze.
- Nim stdlib: `net` (sockets + SSL wrap), `httpclient`/`asynchttpserver`,
  `os`/`osproc`, `times`, `random`, `asyncdispatch` for nonblocking I/O.
  Warning: sync and async APIs duplicated everything; A7 should pick one
  model (structured tasks, G7) and not fork the surface.
- Python: `socket`, `ssl`, `http.client`/`http.server`, `urllib`,
  `pathlib`, `subprocess`, `time`/`datetime`, `random`, `os`. Broadest
  bar for API breadth, but blocking-by-default plus threads is not the
  model; A7 blocking-inside-tasks is closer to Go.
- Go stdlib: `net` (TCP/UDP/DNS, one `Dial`/`Listen`), `crypto/tls`,
  `net/http` (client + server, the reference server API), `os`,
  `path/filepath`, `os/exec`, `time`, `math/rand`, `crypto/rand`. Closest
  target shape: small verbs, timeouts on client, handler function on
  server, goroutines hidden underneath (A7: tasks, G7).

Lesson: one `dial`/`listen` pair (Go), one server handler shape (Go),
TLS as a wrapper not a parallel stack (Nim/Python), no allocator or
async-sync duplication (Zig/Nim warnings).

## 3. Minimal API proposal (A7 spellings)

```a7
net :: import "std/net"
http :: import "std/http"
fs :: import "std/fs"

serve :: fn() {
    s := net.listen_tcp("127.0.0.1", 8080)?
    c := s.accept()?
    msg: [256]u8
    n := c.read(msg[..])?
    c.write("ok"[..])?
    c.close()
}
fetch :: fn() void {
    r := http.get("https://example.com")?
    io.println(r.status)
}
```

- `std/net`: `TcpStream{read, write, close}`,
  `TcpListener{accept, close}`, `listen_tcp(host, port)`,
  `dial_tcp(host, port)`, `UdpSocket{send_to, recv_from}`,
  `resolve(host)` for DNS. All return `Result(_, NetErr)`.
- `std/tls`: `tls.wrap(stream, host)` upgrades a TCP stream; no raw
  socket duplication. Cert verify on by default, opt-out flag explicit.
- `std/http`: `get(url)`, `post(url, body)`, `Client{get, post,
  timeout}`, `serve(addr, handler)` with `Handler :: fn(req: Request,
  res: Response)`. Request/response own their buffers.
- `std/fs`: `read_file(path)`, `write_file(path, data)`,
  `File{open, read, write, close}`. `std/path`: `join`, `base`,
  `ext`, `is_abs`. `std/process`: `args()`, `env_get(name)`,
  `run(cmd)` returning exit code + output. `std/time`: `now()`,
  `sleep(ms)`, `instant` diff. `std/rand`: seeded `gen()`,
  `gen_range(lo, hi)`; `std/crypto_rand` for keys/TLS nonces.

## 4. Ordering and dependencies

- After collections (report 03) and G5 error propagation. Every call
  above returns `Result`; without `?` and `Result` matching decided,
  network code cannot report refused/timeout/reset distinctly.
- After or with G7 structured tasks. Blocking sockets are only usable
  with tasks; `serve` above blocks in `accept`. Server + tests need
  task groups, cancellation (client disconnect), and join outcomes.
- Files/paths/process/time/random first: they need no concurrency,
  unblock CLI programs and tests, and HTTP/TLS need `time` (timeouts,
  cert expiry) and `rand` (nonces) anyway. Order: fs/path/process/time/
  rand, then net/DNS, then TLS, then HTTP client, then HTTP server.

## 5. Test plan

- Loopback TCP echo and UDP send/recv on 127.0.0.1, ephemeral ports; no
  external network in unit tests.
- DNS: local resolver against a seeded hosts entry, plus timeout test
  against an unroutable address.
- TLS: handshake against a local self-signed fixture server; verify
  failure on wrong host and success with fixture cert pinned.
- HTTP: client GET/POST against a local `serve` fixture; status, header,
  and body assertions; server test drives N sequential connections then
  a concurrent burst once G7 tasks land.
- System: file round-trip, path join/base/ext vectors, `run("echo")`
  exit-code check, seeded rand determinism, sleep lower-bound timing.
- Error matrix: refused connection, reset mid-read, timeout, DNS
  not-found — each maps to a distinct `NetErr` variant, asserted per case.
