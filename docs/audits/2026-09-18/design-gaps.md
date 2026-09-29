# Design gaps: tensors, concurrency, the native boundary

Auditor: independent, 2026-09-18. Scope: the three aspects the
[language audit checklist](../../plan/audit/language-audit-checklist.md) lists as
never audited because no code exists — tensors and array programming (SPEC 9),
concurrency, and the FFI / native boundary. This is a documentation and design
audit. Findings are prefixed `DSG`.

Tree audited: the main working tree with batches C3, PR-00, T0, V1, NOREC-0 and
PL-02 applied as uncommitted changes. The worktrees under
`/home/cx89/Projects/pl-dev/a7-wt/` (C1, C4, C2) were not read. Probes are under
`tmp/audit/2026-09-18/design/probes/`; every probe is compile-only and nothing
was built or run except `zig build-obj -fno-emit-bin`.

## Result

All three aspects are **specified but absent**. No line of `a7/` mentions any of
them: a word-boundary grep for `tensor`, `Tensor`, `concurren`, `thread`,
`spawn`, `Channel`, `gpu`, `vectorize`, `parallel`, `prefetch`, `extern`,
`callconv`, `broadcast`, `matmul`, `task_group`, `autodiff`, `gradient`, `simd`,
`atomic` and `mutex` over `a7/ --include=*.py` returns 0 hits for every term
(`tmp/audit/2026-09-18/design/grep-a7.txt`). No test covers any of them: the only
matches in `test/` are an identifier `tensor_3d`
(`test/test_parser_unicode_and_special.py:411`) and a struct field `channels: 2`
(`test/test_parser_creative_cases.py:481`).

All 16 `a7` code blocks in SPEC 9 fail to compile: at file scope, 8 at parse
and 8 at semantic analysis; wrapped in `main`, 10 at parse and 2 at semantic
(`tmp/audit/2026-09-18/design/asis.txt`, `wrapped.txt`). That much is KNOWN and
recorded (`docs/plan/README.md:298`, "no tensor code compiles today").

What is new is that SPEC 9 is not merely unimplemented — it is **unimplementable
as written against A7's own rules**, and the plan documents that are supposed to
replace it contradict each other and, in one case, contradict the memory gate
they cite. The concrete decision debt is 19 rows in "What is missing".

| Severity | NEW | KNOWN | Total |
| --- | --- | --- | --- |
| CRITICAL | 0 | 0 | 0 |
| HIGH | 4 | 0 | 4 |
| MEDIUM | 12 | 0 | 12 |
| LOW | 5 | 0 | 5 |
| Total | 21 | 0 | 21 |

No finding changes a program that A7 accepts and Zig builds today, because no
program using any of this syntax is accepted. The approval answer for every
finding is therefore **no** for the defect itself. The separate question of
whether *withdrawing a promise* needs approval is answered in
[Recommendation](#recommendation).

## 1. Tensors and array programming (SPEC 9)

### What is promised

SPEC 9 runs 364 lines, `docs/SPEC.md:1083-1446`. It carries one disclaimer, at
`docs/SPEC.md:1087-1090`:

> This section is a design target, not current implementation status. Tensor
> types, broadcasting, vectorized tensor operators, AI primitives, GPU movement,
> and performance annotations are not implemented yet.

After that paragraph come 16 fenced ```` ```a7 ```` blocks containing roughly 120
declarations and statements, rendered identically to every working example
elsewhere in the same file. The section title in the table of contents is
"Planned Array Programming for AI" (`docs/SPEC.md:24`).

A reader who arrives at SPEC 9, reads the disclaimer, and then reads the section
would reasonably conclude: this is the settled design, the spelling is decided,
and only the implementation is missing. That conclusion is wrong on all three
counts. The spelling is not decided (gate G8 at `docs/plan/README.md:292-307`
lists the tensor literal dtype, promotion, mutation and alias syntax as
undecided, and proposes *different* spellings from SPEC 9 for the same
operations). The design is not settled (`docs/plan/research/ai-frameworks-codex.md:44-52`
lists five substantive errors in it). And parts of it cannot be implemented
without changing rules A7 has already locked.

### What exists

`grep -rn -w -i tensor a7/ --include=*.py` → 0 hits. Nothing in the tensor
surface exists.

One adjacent thing does exist and SPEC 9 never mentions it: element-wise
addition of same-shape 1-D fixed numeric arrays, specified at
`docs/SPEC.md:262-266` and lowered to a Zig `@Vector`.

Probe `t01_arrayadd.a7`, `uv run a7 ... --output t01_arrayadd.zig` → **exit 0**:

```zig
c = (@as(@Vector(4, f64), a) + @as(@Vector(4, f64), b));
```

`zig build-obj -fno-emit-bin t01_arrayadd.zig` → **exit 0**
(`tmp/audit/2026-09-18/design/zig_t01.txt`). This is KNOWN and checked-correct at
`docs/audits/2026-09-16/compiler/types.md:599-600`.

### Probe matrix: every code block in SPEC 9

"as-is" is the block compiled unchanged at file scope; "in `main`" is the same
block wrapped in a `main` function (statement blocks only). Full logs:
`tmp/audit/2026-09-18/design/asis.txt` and `wrapped.txt`.

| # | SPEC lines | Subject | as-is | in `main` | First diagnostic |
| --- | --- | --- | --- | --- | --- |
| 1 | 1094-1113 | Tensor types | 5 | — | `Expected LEFT_BRACE, got LEFT_PAREN` at `struct($T: Numeric, $N: u8)` |
| 2 | 1118-1135 | Array literals | 5 | 5 | `Expected expression` (multi-line array literal) |
| 3 | 1142-1158 | Broadcasting | 5 | 5 | `Expected expression` (multi-line array literal) |
| 4 | 1163-1184 | Vectorized ops | 6 | 6 | `Undefined type (Identifier 'a')`, 29 errors |
| 5 | 1191-1204 | Shape ops | 6 | 5 | `Expected RIGHT_BRACKET, got DOT_DOT` at `tensor_view(a, [start..end])` |
| 6 | 1209-1221 | Axis ops | 6 | 5 | `Expected RIGHT_PAREN, got COLON` at `axis: 1` |
| 7 | 1227-1240 | Reductions | 6 | 5 | `Expected RIGHT_PAREN, got COLON` at `axis: 1` |
| 8 | 1246-1261 | Linear algebra | 6 | 5 | `Expected expression` at `eigenvals, eigenvecs := ...` |
| 9 | 1268-1285 | NN primitives | 5 | 5 | `Expected RIGHT_PAREN, got COLON` at `stride: [1, 1]` |
| 10 | 1290-1296 | Gradients | 6 | 5 | `Expected expression` at `tensor_no_grad { ... }` |
| 11 | 1303-1311 | Memory layout | 6 | 6 | `Undefined type (Identifier 'tensor_c_layout')`, 12 errors |
| 12 | 1316-1329 | Annotations | 5 | 5 | `Expected declaration ...` at `@vectorize` |
| 13 | 1336-1353 | Indexing | 5 | 5 | `Expected RIGHT_BRACKET, got COMMA` at `tensor[i, j, k]` |
| 14 | 1359-1379 | Built-in signatures | 5 | — | `Expected parameter name` at `fn(shape: []usize, $T: Numeric)` |
| 15 | 1386-1408 | ML example | 6 | — | `Undefined type (Identifier 'tensor_matmul')`, 5 errors |
| 16 | 1413-1443 | Scientific example | 5 | — | `Expected expression` at `L, U, P := tensor_lu_pivot(A)` |

Eight blocks never reach the type checker. The failures are not "the function is
missing"; they are "this is not A7 syntax".

### Targeted probes

Full log: `tmp/audit/2026-09-18/design/targeted.txt`.

| Probe | Source | Exit | Result |
| --- | --- | --- | --- |
| `t01_arrayadd` | `c = a + b` on `[4]f64` | 0 | Works; `@Vector` lowering; Zig accepts |
| `t02_multiline` | `[1,`⏎`2]` in `main` | 5 | `Expected expression` |
| `t03_nested` | `[[1,2],[3,4]]` one line | 0 | Emits untyped `.{ .{1,2}, .{3,4} }` |
| `t04_destructure` | `a, b := f()` | 0 | Emits `var b = f();`; **`main` is gone** |
| `t05_namedarg` | `g(axis: 1)` | 5 | Not parsed |
| `t06_multiindex` | `m[0, 1]` | 5 | Not parsed |
| `t07_vectorize` | `@vectorize` on a decl | 5 | Not parsed |
| `t08_xor` | `p := a ^ b` | 0 | Emits Zig `(a ^ b)` — XOR, not power |
| `t11_generic_struct_paren` | `struct($T: Numeric)` | 5 | Not parsed |
| `t13_broadcast` | `[3]f64 + [2]f64` | 6 | Correctly rejected |
| `t14_scalarbc` | `a * 2.0` on `[3]f64` | 6 | `Requires numeric type` |
| `t15_matrix2d` | `[2][2]f64 + [2][2]f64` | 6 | Rejected; see DSG-13 |

## 2. Concurrency

### What is promised

There is no SPEC section on concurrency. The promise is spread across four
documents that describe **three different and mutually exclusive surfaces**:

1. An annotation on a function, in the language specification itself —
   `docs/SPEC.md:1322`: `@parallel // Enable parallel execution`.
2. Structured tasks with channels, in gate G7 — `docs/plan/README.md:267-286`:
   `task_group { spawn worker(results, 1) ... }`, `results.close()`, marked
   "Proposed syntax. Every spelling here is undecided."
3. An annotated *call* over work the compiler already proves independent, in
   `docs/plan/research/bend-for-a7.md:119-131` (B4): "the same surface — an
   annotation on a call the compiler already proves independent — is the cheapest
   concurrency A7 could offer, and it needs no thread API, no locks and no
   runtime scheduler beyond a fork-join pool."

Against all three, the published documentation says concurrency is not coming:
`site/public/llms-full.txt:422`, under "Deferred": "Concurrency primitives", with
`:426-427` adding "If a feature is listed here as deferred, do not write public
examples that rely on it as if it is complete." (`:307` — "File IO, network IO,
and concurrency are out of scope for the current stdlib" — is scoped to the
stdlib, so it is weaker evidence.) `docs/STATUS.md:41-44` says the same as `:422`.
And `docs/plan/decisions.md` L1 (`:41`) puts concurrency **in** v1, with the
superseded-material table explicitly retiring `docs/STATUS.md:41-44`.

A reader of the public docs concludes concurrency is deferred indefinitely. A
reader of the plan concludes it is v1 scope with three candidate shapes and no
decision. Both readings are current.

### What exists

0 hits in `a7/` for `concurren`, `thread`, `spawn`, `Channel`, `task_group`,
`atomic`, `mutex`, `parallel`.

Probe `t10_taskgroup.a7` (the G7 block verbatim) → **exit 5**,
`Unexpected token 'spawn' after parsing complete program [line 10: col 9]`.

Probe `t12_bend_parcall.a7` (`y := f!(1)`) → **exit 6**,
`Requires bool type [line 4: col 10]`: the tokenizer splits `f!(1)` into `f`,
`!`, `(1)`, so Bend's call-annotation spelling collides with the existing logical
`!`. That is a fact G7 needs before it picks shape 3.

## 3. FFI and the native boundary

### What is promised

`docs/plan/memory.md:623` (gate M25) is the honest statement:

> Native declaration surface | Open it in Phase A with before and after examples.
> It has no syntax today, and gate M12, phase F and the AI acceptance workloads
> all depend on it

The dependency chain, traced through the plan:

| Step | Where | Depends on the previous |
| --- | --- | --- |
| M25 — declaration surface | `docs/plan/memory.md:623` | — |
| M12 — descriptors (borrowing, retention, returned storage, alignment, completion, callbacks, thread affinity) | `docs/plan/memory.md:594` | M25: a descriptor has nothing to attach to without a declaration form |
| M43 — native supply chain (pinned kernel libraries and hashes) | `docs/plan/memory.md:632` | M25/M12: which libraries are pinned follows from what can be declared |
| Track 10 — native boundary: ABI descriptors, native handle ownership, kernel-library bridge | `docs/plan/README.md:346` | M25, M12, M43; execution plan Wave 6 states it as "M25 decided in Wave 4; after M12 and M43 packets" (`docs/plan/execution.md:436`) |
| AI sequence step 4 — "OpenBLAS or BLIS for `f32` and `f64` matrix work, and optional oneDNN acceleration" | `docs/plan/README.md:505-506` | track 10; and ledger L9 (`docs/plan/decisions.md:44`) makes native kernels the approved implementation route |
| Track 11 — CPU AI | `docs/plan/README.md:347` | "G1, G8, 3b, 6a, 10" — track 10 by name |
| Memory phase F — tasks, tensors, native | `docs/plan/memory.md:669` | "D; v1 gates G7, G8, and gates M25, M43; tracks 9, 10, 11" |
| Track 6b — memory model integration | `docs/plan/README.md:340` | phases F and G |
| Track 13 — release qualification | `docs/plan/README.md:349` | "All" |

The only draft of a declaration surface is
`docs/lang-safety/edge-cases/12-ffi-boundary.md`, 30 numbered subcases
(FFI-01…FFI-30) plus examples. Its own 2026-09-16 notes
(`:24-40`) retire most of its vocabulary: the `borrow`/`inout` framing is
replaced by M12 descriptors, `Result<T,E>` angle-bracket spelling and stored or
returned `ref` are removed by M4, `Bounded`/`Fin<F>` are superseded by D.020 and
L16, D.033's bit-width rule is superseded by L4, and its variadic subcase Q12g
sits on parsed-only syntax. The file states plainly at `:107`: "All examples in
this file are proposals. FFI does not exist in A7."

### What exists

0 hits in `a7/` for `extern` or `callconv`. Probe `t09_extern.a7`
(`libc_read :: extern "C" fn(fd: i32, buf: []u8) usize`) → **exit 5**,
`Unexpected token '"C"' after parsing complete program`.

---

# Findings

## DSG-1 · HIGH · NEW · SPEC 9 uses destructuring as working code, which SPEC 4.1 and CLAUDE.md both call parsed-only

SPEC 9.5 and 9.10 write multiple-binding declarations as ordinary A7:

- `docs/SPEC.md:1252` — `eigenvals, eigenvecs := tensor_eig(A)`
- `docs/SPEC.md:1253` — `U, S, Vt := tensor_svd(A)`
- `docs/SPEC.md:1254` — `Q, R := tensor_qr(A)`
- `docs/SPEC.md:1255` — `L, U := tensor_lu(A)`
- `docs/SPEC.md:1416` — `L, U, P := tensor_lu_pivot(A)`

The same file says at `docs/SPEC.md:422-424`:

> `// Multiple declaration/destructuring syntax is planned, not current:`
> `// a, b, c: i32 = 1, 2, 3`
> `// x, y := 10, 20`

CLAUDE.md's Docs Accuracy rule names "multiple-declaration and destructuring
binding syntax" among the three forms that must be marked parsed-only/reserved,
and states: "Adding examples, snippets, or claims that imply the parsed-only
forms work end-to-end is treated the same as a doc/code drift bug." SPEC 9
contains five such snippets.

The compiler does not reject the form, it miscompiles it. Probe
`tmp/audit/2026-09-18/design/probes/t04_destructure.a7`,
`uv run a7 t04_destructure.a7 --output t04_destructure.zig` → **exit 0**, whole
output:

```zig
fn f() i32 {
    return 1;
}

var b = f();
```

`main` is gone and `a` has vanished. The mechanism is KNOWN (PAR-03 / PAR-06,
`docs/audits/2026-09-16/compiler/parser.md:147`, which records the identical
result for `a, b := 1, 2`). What is new is that the language specification uses
the form as working syntax in two sections.

Secondary: `docs/SPEC.md:1255` rebinds `U`, already bound at `:1253`, inside one
code block.

**Fix direction.** Rewrite 9.5 and 9.10 to the current multiple-value form —
SPEC 6.1 (`docs/SPEC.md:679-694`) says the current form is a return struct — or
mark the whole section under DSG-20's relabelling.
**Approval:** no. No accepted program changes.

## DSG-2 · HIGH · NEW · Three incompatible concurrency shapes are promised, and the public docs deny all three

The four statements, quoted:

- `docs/SPEC.md:1322` (the language specification): `@parallel  // Enable parallel execution`, an annotation on a function declaration.
- `docs/plan/README.md:267-286` (gate G7): `task_group { spawn worker(results, 1) ... }` with `Channel(i32)` — a structured-task API with a runtime.
- `docs/plan/research/bend-for-a7.md:127-131` (B4): "the same surface — an annotation on a call the compiler already proves independent — is the cheapest concurrency A7 could offer, and it needs no thread API, no locks and no runtime scheduler beyond a fork-join pool."
- `site/public/llms-full.txt:422`, generated from `site/public/docs/status.md:44`: "## Deferred … - Concurrency primitives", with `:426-427` adding "If a feature is listed here as deferred, do not write public examples that rely on it as if it is complete."

These are not three descriptions of one feature. The annotation form (1 and 3)
needs no channels, no cancellation, no join outcomes and no close rule; the
structured form (2) needs all four, and G7 itself opens on exactly those
questions (`docs/plan/README.md:269`: "Decide structured task lifetime,
cancellation, join outcomes and channel close"). Choosing shape 3 would retire
gates M26 (cancellation points, `docs/plan/memory.md:595`) and M27 (channel
close, `:596`) as written.

The public denial is also stale in its own right: `docs/STATUS.md:41-44` lists
concurrency under "Deferred Tracks", and `docs/plan/decisions.md` (superseded
material table) records "`docs/STATUS.md:41-44`: tensor, AI, GPU and concurrency
as deferred tracks | L1, L7" — i.e. the ledger already retired that paragraph,
and track 0 has not updated it.

**Fix direction.** G7 must choose a shape before track 9 or any packet. Present
the three as options with the cost line B4 already quotes from Bend
("Parallelism requires balanced calls", `bend-for-a7.md:122-123`). Independently of
the choice, SPEC 9.7's `@parallel` must stop being the only concurrency
construct in the language specification.
**Approval:** no for the docs reconciliation; the shape choice is gate G7.

## DSG-3 · HIGH · NEW · Gate G7's own example violates memory gates M10 and M36

`docs/plan/README.md:276-286`:

```a7
main :: fn() {
    results := Channel(i32){}
    task_group {
        spawn worker(results, 1)
        spawn worker(results, 2)
    }   // both tasks end before this scope ends
    results.close()
}
```

Gate M10 (`docs/plan/memory.md:593`) says tasks are "Structured; scope exit
cancels then joins children; no detach in v1; **values move in**." Under that
rule `results` moves into the first `spawn`, and the second `spawn` and the
later `results.close()` are both uses after move. Gate M36 (`:597`) permits the
alternative — "Read-only sharing with child tasks … for parent values the parent
does not change until children finish" — but `worker` calls `out.send(...)`, a
write, and the parent then calls `results.close()`, another write. Neither gate,
as written, admits this program. Nothing in either gate exempts channels.

The same six lines use three other constructs that do not exist: method-call
syntax `out.send(...)` / `results.close()` (the checklist records at
`docs/plan/audit/language-audit-checklist.md:92` that "there is no `x.m()` call
form" and that SPEC 6.5 defines methods as free functions), a generic struct
literal `Channel(i32){}`, and the `spawn` and `task_group` keywords. Probe
`t10_taskgroup.a7` → exit 5, `Unexpected token 'spawn' after parsing complete
program`.

This matters more than an unimplemented example: G7 is the artifact the owner
will read when deciding concurrency, and it demonstrates a lifetime pattern that
the memory plan rejects.

**Fix direction.** Either add a channel exemption to M10/M36 and say so in the
example, or rewrite the example so the channel is created by `task_group` and
never crosses a move. Decide before G7 is presented.
**Approval:** no (the example compiles nowhere); the underlying rule is M10.

## DSG-4 · HIGH · NEW · The native declaration surface blocks five downstream items and has no usable draft

M25 (`docs/plan/memory.md:623`) states the gap. The chain above shows M12, M43,
track 10, AI sequence step 4, track 11, phase F, track 6b and track 13 all sit
behind it.

What survives a late M25 decision (INFERENCE, from the dependency table):

- AI sequence steps 1-3 — tensor value semantics, portable reference kernels, the
  eager reverse tape (`docs/plan/README.md:499-504`) — depend on G1, G8 and the
  memory model, not on track 10. They can be built against A7's own kernels.
- Track 9 (concurrency) depends on "G7, 6a, 7b" (`docs/plan/README.md:345`), not
  on track 10.

What breaks if M25 is decided late:

- Ledger L9 (`docs/plan/decisions.md:44`) — "A7 owns tensor semantics and
  automatic differentiation over established native kernel libraries" — is
  unimplementable until there is a way to declare a native call. Every matmul in
  the L10 acceptance workloads goes through it.
- Gate M14's performance margins (`docs/plan/memory.md:585`) are measured against
  C and Zig. A pure-A7 reference matmul will not meet a BLAS-derived margin, so
  either the margins are set late or they are set against a path that does not
  exist yet. M14 also requires margins be "fixed … before any baseline runs".
- Phase F exit evidence (`docs/plan/memory.md:669`) names "native descriptors"
  directly; phase F cannot exit.
- M43 (supply chain) and the GLM security review that track 10 requires
  (`docs/plan/README.md:346`, "Native boundary qualification; GLM security
  review") cannot be scoped: what has to be reviewed is defined by what can be
  declared.

`docs/lang-safety/edge-cases/12-ffi-boundary.md` is not a usable draft. Its own
notes at `:24-40` supersede its vocabulary against L4, L6, L16, D.020, M4 and
M12, and `:107` says "FFI does not exist in A7."

**Fix direction.** Open M25 as a packet with before-and-after examples, as the
gate itself instructs. INFERENCE: because the backend already emits Zig, the
cheapest surface to specify and the only one with a working lowering today is a
declaration that maps to a Zig `extern fn` plus a linked library, with the M12
descriptor carried as declaration attributes. That is a starting point, not a
recommendation the owner has approved.
**Approval:** no for writing the packet; the syntax itself is gate M25.

## DSG-5 · MEDIUM · NEW · SPEC 9 uses two generic spellings that no other SPEC section defines and that do not parse

`docs/SPEC.md:1095` declares a generic struct with a parenthesized parameter
list: `Tensor :: struct($T: Numeric, $N: u8) {`. SPEC 7.2
(`docs/SPEC.md:906-916`) defines generic structs with inline `$T` in field types
and no parameter list at all:

```a7
Pair :: struct {
    first: $T,
    second: $U,
}
```

Probe `t11_generic_struct_paren.a7` → **exit 5**, `Expected LEFT_BRACE, got
LEFT_PAREN [line 2: col 13]`; block 1 fails identically at `docs/SPEC.md:1095`.

`docs/SPEC.md:1360-1367` declares generic functions with the generic parameter
inside the ordinary parameter list: `tensor_zeros :: fn(shape: []usize, $T:
Numeric) Tensor(T)`. SPEC 7.3 (`:962-968`) puts constraints in a list before
`::` (`abs($T: Numeric) :: fn(x: $T) $T`) and SPEC 6.1 (`:705`) shows a third
form with a `where` clause (`add :: fn($T, a: T, b: T) T where T: Numeric`).
Block 14 fails at **exit 5**, `Expected parameter name [line 3: col 36]`.

`$N: u8` at `:1095` is a *value* generic parameter constrained by a concrete
type. No SPEC section defines value generics; SPEC 7.3 constrains generic
parameters by type sets only.

Finally, `Tensor(T)` at `:1360` and `:1363` omits the `$` that SPEC 7 requires
and passes one argument to a two-parameter struct.

**Fix direction.** Any surviving SPEC 9 declarations must be respelled in SPEC 7
syntax, or the value-generic form must go to a packet of its own. Note the
underlying spread of three generic spellings across SPEC 6.1, 7.2 and 7.3 is
outside this component and belongs to the generics audit.
**Approval:** no.

## DSG-6 · MEDIUM · NEW · SPEC 9.2 documents `^` as exponentiation; SPEC 2.5 defines it as bitwise XOR and the compiler emits XOR

`docs/SPEC.md:1168`: `power := a ^ b          // Power`.

`docs/SPEC.md:120` lists `^` under "// Bitwise": `&    |    ^    ~    <<   >>`.

Probe `t08_xor.a7` (`a: i32 = 6`, `b: i32 = 3`, `p := a ^ b`) → **exit 0**,
emitting `const p = (a ^ b);` — Zig XOR, value 5, not 216.

A reader who follows SPEC 9.2 writes `a ^ b` for exponentiation, gets a silently
accepted program, and gets XOR.

**Fix direction.** Delete the line or respell it; A7 has no exponent operator.
**Approval:** no — but note this one is the closest thing in SPEC 9 to a live
hazard, because the expression compiles today with the wrong meaning.

## DSG-7 · MEDIUM · NEW · SPEC 9 uses named call arguments about twenty times; the grammar has none, and `axis: -1` contradicts the `usize` index rule

Named arguments appear at `docs/SPEC.md:1214`, `:1216`, `:1219`, `:1220`,
`:1221`, `:1229`, `:1230`, `:1235`, `:1239`, `:1261`, `:1270-1271`,
`:1274-1275`, `:1280`, `:1285`, `:1296`, `:1374` — `axis:`, `stride:`, `padding:`,
`kernel_size:`, `sections:`, `p:`, `max_norm:`, `precision:`.

The SPEC grammar at `docs/SPEC.md:2022` has only
`postfix_expr = ... | postfix_expr "(" expr_list? ")"`. There is no named-argument
production anywhere in section 13.

Probe `t05_namedarg.a7` (`g(axis: 1)`) → **exit 5**.

Two further inconsistencies inside SPEC 9 itself:

- `axis` is a scalar at `:1229` (`tensor_sum(a, axis: 1)`) and a list at `:1230`
  (`tensor_mean(a, axis: [0, 1])`), with no overload rule stated.
- `axis: -1` at `:1280` and `:1285` is a negative axis index. CLAUDE.md's A7
  Source Rules require `usize` for "array/slice/string indices" and reserve
  `isize` for "signed pointer-sized offsets and position differences only".
  `docs/plan/research/ai-frameworks-codex.md:50` already records this: "`axis: -1`
  needs an axis convention distinct from element indices."

**Fix direction.** Named arguments are a language feature with no gate and no
packet; SPEC 9 cannot assume them. Either open a packet or respell SPEC 9
positionally. The axis convention is gate G8.
**Approval:** no.

## DSG-8 · MEDIUM · NEW · Multi-dimensional and partial indexing have no grammar and do not parse

`docs/SPEC.md:1337-1340`:

```a7
element := tensor[i, j, k]
row := tensor[i, ..]
col := tensor[.., j]
block := tensor[i..i+3, j..j+3]
```

The grammar at `docs/SPEC.md:2018-2019` admits exactly two index forms:
`postfix_expr "[" expr "]"` and `postfix_expr "[" expr? ".." expr? "]"` — one
index or one range, never a comma-separated list.

Probe `t06_multiindex.a7` (`m[0, 1]` on a `[2][2]i32`) → **exit 5**,
`Expected RIGHT_BRACKET, got COMMA`. Block 13 fails identically at
`docs/SPEC.md:1337`.

`docs/SPEC.md:1344` (`filtered := tensor[mask]`) and `:1353`
(`elements := tensor[row_idx, col_idx]`) additionally index with a boolean tensor
and with an array of indices, both of which contradict the `usize` index rule.

**Approval:** no.

## DSG-9 · MEDIUM · NEW · SPEC 9's own function inventory is internally inconsistent

`docs/SPEC.md:1356-1380` is headed "9.9 Built-in Tensor Functions" and lists 13
signatures. Functions used as working code elsewhere in section 9 but absent
from that list: `tensor_range` (`:1130`), `tensor_random` (`:1131`),
`tensor_from_data` (`:1135`), `tensor_where` (`:1184`), every function in 9.3,
9.4, 9.5, 9.6 and 9.7, and `tensor_lu_pivot`, `tensor_forward_solve`,
`tensor_backward_solve` (`:1416`, `:1420`, `:1423`).

`tensor_range` at `:1130` and `tensor_arange` at `:1363` name the same operation
twice.

`tensor_batch_norm` takes five arguments at `docs/SPEC.md:1284`
(`tensor_batch_norm(x, gamma, beta, mean, var)`) and one at `:1401`
(`tensor_batch_norm(data)`). One of its argument names is `var`, a Zig keyword
that the backend does not escape (KNOWN B12, `docs/plan/README.md:444-445`).

`docs/SPEC.md:1404` calls `tensor_conv2d(normalized, kernel)` where `kernel` is
never declared — the enclosing function `process_batch` takes only `data`.

`docs/SPEC.md:1372` — `tensor_save :: fn(tensor: Tensor, filename: string) bool`.
`docs/plan/research/ai-frameworks-codex.md:52`: "A tensor save/load API returning
only a boolean cannot express the proposed recovery and compatibility behavior",
which gate M24 (`docs/plan/memory.md:611`) and M46 (`:635`) require.

`docs/plan/research/ai-frameworks-codex.md:51` further records that
"Eigendecomposition, SVD, LU, and inverse are not dependencies of the two
approved ML workloads" (L10) — so the whole of 9.5 specifies work v1 does not
need.

**Approval:** no.

## DSG-10 · MEDIUM · NEW (extends a KNOWN row) · Broadcasting: the stated rule, the example, and A7's numeric rules do not agree

KNOWN, recorded twice: `docs/plan/README.md:395-396` and
`docs/plan/research/ai-frameworks-codex.md:44`. `docs/SPEC.md:1156-1158` claims
shapes `[3, 1, 4]` and `[2, 5, 1]` broadcast to `[3, 2, 5, 4]`; under the NumPy
rules the same section invokes at `:1142` they do not broadcast at all.

New, and not recorded anywhere: two further broadcasting claims in the same
subsection sit on undecided numeric rules.

- `docs/SPEC.md:1143-1147` binds `a` from an integer literal array, then
  `docs/SPEC.md:1153` writes `scaled := a * 2.0` — an integer tensor times a
  float scalar. Promotion between dtypes is explicitly undecided (gate G8,
  `docs/plan/README.md:294`: "Decide the tensor literal default dtype, promotion
  or explicit casts"), and gate G3's recommendation runs the other way
  (`docs/plan/README.md:169-170`: "same-type operands with contextual literals").
- `docs/SPEC.md:1181` writes `mask := a >= 0.5` on the same integer `a`.

Probe `t14_scalarbc.a7` (`a: [3]f64`, `c := a * 2.0`) → **exit 6**,
`Requires numeric type`: scalar broadcast does not exist even for a float array.

**Fix direction.** G8 owns the promotion decision. The example at `:1156-1158`
must be corrected to `[3,1,1,4]` and `[1,2,5,1]` or deleted, whatever else
happens to section 9.
**Approval:** no.

## DSG-11 · MEDIUM · NEW · `@vectorize`, `@parallel` and `@prefetch` are reserved intrinsics presented as working annotations

`docs/SPEC.md:1317`, `:1322`, `:1328`. CLAUDE.md's Docs Accuracy rule requires
"intrinsics other than `@type_set`" to be marked parsed-only/reserved. SPEC 7.3
(`docs/SPEC.md:943-945`) marks type sets as implemented; nothing marks these
three.

They are not merely unimplemented — they are not a grammatical position. Probe
`t07_vectorize.a7` (`@vectorize` on the line before a function declaration) →
**exit 5**, `Expected declaration (constant, variable, or function) [line 2:
col 1]`. Block 12 fails identically. A7 has no declaration-attribute syntax at
all, and adding one is a language change with no gate and no packet.

`docs/SPEC.md:1328` also calls `size_of(f32)`, which is not in SPEC 11's built-in
list and does not resolve.

`@parallel` is additionally the concurrency conflict in DSG-2.

**Approval:** no.

## DSG-12 · MEDIUM · NEW · SPEC 9 promises GPU device movement; L8 and the plan confine accelerators to interface design

`docs/SPEC.md:1377-1379`:

```a7
tensor_to_gpu :: fn(tensor: Tensor) Tensor
tensor_to_cpu :: fn(tensor: Tensor) Tensor
tensor_device :: fn(tensor: Tensor) Device
```

`Device` is used as a return type and never declared anywhere in the SPEC.

Ledger L8 (`docs/plan/decisions.md:43`): "CPU first, with an accelerator interface
for a later GPU backend", and its scope limit (`:79`): "L8 permits accelerator
interface design. It does not qualify any GPU, NPU, TPU or FPGA."
`docs/plan/README.md:514-515`: "Accelerator backend adapters stay at interface
design. The hardware research ordering does not create v1 qualification work."
`docs/plan/research/hardware-providers-codex.md:9`: "Broad research does not
qualify any hardware or expand approved v1 scope."

SPEC 9's own disclaimer does mention "GPU movement" among the unimplemented
items (`:1088`), so this is weaker than DSG-1 — but the three signatures still
present a device API as settled design when the ledger permits only an interface
sketch.

**Approval:** no.

## DSG-13 · MEDIUM · NEW · Element-wise array arithmetic is 1-D and addition-only, and the 2-D diagnostic names two identical types

`docs/SPEC.md:262-266` promises "Element-wise addition for same-shape numeric
fixed arrays" with no rank restriction. `docs/SPEC.md:1164-1169` promises `+`,
`-`, `*`, `/`, `^` and `%`.

`a7/passes/type_checker.py:1223-1233`:

```python
if op == BinaryOp.ADD and isinstance(left_type, ArrayType) and isinstance(right_type, ArrayType):
    if (
        left_type.size == right_type.size
        and left_type.element_type.equals(right_type.element_type)
        and self._is_numeric_compatible(left_type.element_type)
    ):
        return left_type
    self.add_type_error(
        TypeErrorType.OPERATOR_TYPE_MISMATCH,
        node.span,
        context=f"add between {left_type} and {right_type}",
    )
```

Two consequences. First, only `BinaryOp.ADD` is handled, so `-`, `*`, `/` and `%`
on arrays fall through to rejection (`array -` rejected is KNOWN at
`docs/audits/2026-09-16/compiler/types.md:600`, probe `b38`; probe
`t16_arraymul.a7` — `a * b`, `a / b`, `a % b` on two `[3]f64` — → **exit 6**,
three × `Requires numeric type`). Second, for
`[2][2]f64` the element type is `[2]f64`, which is not numeric, so the rank-2
case takes the error path and prints both operand types — which are identical.

Probe `t15_matrix2d.a7` → **exit 6**:
`error: Operator requires compatible types (add between [2][2]f64 and [2][2]f64)`.

The rejection may well be intended. The diagnostic is wrong: it tells the user
two identical types are incompatible.

**Fix direction.** Give the non-numeric-element case its own message ("element-wise
arithmetic applies to one-dimensional arrays of numeric elements"), and correct
`docs/SPEC.md:262` to say one-dimensional and addition-only.
**Approval:** no for the diagnostic. If the fix instead *accepted* rank-2
addition, that accepts more programs and still needs no approval under L24.

## DSG-14 · MEDIUM · NEW (KNOWN mechanism PAR-06) · Every multi-dimensional array literal in SPEC 9 is written multi-line and cannot parse

`docs/SPEC.md:1119-1121`, `:1124-1126`, `:1143-1147` write array literals across
lines. Probe `t02_multiline.a7` (`m := [1,`⏎`          2]`) → **exit 5**,
`Expected expression [line 3: col 12]`. The single-line equivalent
(`t03_nested.a7`, `[[1, 2], [3, 4]]`) → **exit 0**, emitting an untyped Zig
tuple `.{ .{ 1, 2 }, .{ 3, 4 } }`.

The parser cause is KNOWN: `docs/audits/2026-09-16/compiler/parser.md:210`
("`parse_array_literal` (1894-1913) … do not [skip TERMINATORs]") and PAR-06 at
`:46`. What is new is that it makes SPEC 9.1's "Array Literals and
Initialization" unreachable as written, and that the accepted one-line form
produces an untyped anonymous tuple, not an array type — so "tensor
initialization with shape inference" (`docs/SPEC.md:1123`) has no current
analogue either.

**Approval:** no.

## DSG-15 · LOW · NEW · Type/value confusions in SPEC 9

- `docs/SPEC.md:1192` — `dims := tensor_shape(a)  // Returns [usize] of dimensions`. `[usize]` is not an A7 type; SPEC 3.3 spells slices `[]T` (`:269-277`) and arrays `[N]T` (`:252-256`).
- `docs/SPEC.md:1195` — `dtype := tensor_dtype(a)  // Element type` returns a type as a runtime value. A7 has no first-class types; SPEC 7.3 type sets are compile-time only.
- `docs/SPEC.md:1102-1105` — `Vector :: [N]$T`, `Matrix :: [M][N]$T`, `Tensor3D :: [D][H][W]$T`, `Tensor4D :: [B][C][H][W]$T` leave `N`, `M`, `D`, `H`, `W`, `B`, `C` unbound. `[n]u8` with an unbound `n` is a KNOWN track-1 defect that "compiles and emits Zig that references an undefined `n`" (`docs/plan/README.md:377-378`).
- `docs/SPEC.md:1388-1389` — `Matrix(f32)` and `Vector(f32)` pass one argument to aliases with two and one free names respectively; `docs/SPEC.md:1399` applies `Tensor4D(f32)` to a four-free-name alias.

**Approval:** no.

## DSG-16 · LOW · NEW · "Up to 8 dimensions" is asserted and then contradicted by the type that would enforce it

`docs/SPEC.md:1094`: `// N-dimensional tensors (up to 8 dimensions)`.
`docs/SPEC.md:1095`: `$N: u8`, and `docs/SPEC.md:1112`: `ndim: u8` — both admit
0-255. Nothing in the section states where 8 is enforced or what happens at 9.

**Approval:** no.

## DSG-17 · LOW · NEW · The scientific-computing example is ill-typed under every A7 rule it touches

`docs/SPEC.md:1427-1443`, `integrate_2d`:

- `:1427` declares `f: fn(f64, f64) f64`; `:1436` calls `Z := f(X, Y)` where `X` and `Y` are tensors from `tensor_expand_dims`. The comment at `:1435` says "Evaluate function on grid (broadcasts to [n, m])" — implicit lifting of a scalar function over tensors, which nothing in SPEC 9 or gate G8 defines.
- `:1439-1440` — `cast(f64, steps[0] - 1)` where `steps: [2]usize`. Under L5 (`docs/plan/decisions.md:40`) integer `-` wraps, so `steps[0] == 0` gives `usize` max, not `-1`; `cast` itself sits on the open D.024/D.038 contradiction routed to gate G3 (`docs/plan/decisions.md`, superseded table).
- `:1438` — the comment says "Numerical integration using trapezoidal rule"; `tensor_sum(Z) * dx * dy` at `:1442` is a Riemann sum, which weights endpoints wrong.
- `:1416` — `L, U, P := tensor_lu_pivot(A)`: see DSG-1.

**Approval:** no.

## DSG-18 · LOW · NEW · The gradient API in SPEC 9.6 diverges from gate G8's own spelling and omits the tape rules the memory gates impose

`docs/SPEC.md:1290-1296` names `tensor_grad_enable(x)`, `tensor_backward(loss)`,
`tensor_no_grad { ... }`, `tensor_clip_grad_norm(params, max_norm: 1.0)`.

Gate G8 (`docs/plan/README.md:300-307`) proposes a different surface for the same
operations — `loss := sum(x * x)`, `grads := backward(loss)` — and marks it
"Proposed syntax. Every spelling here is undecided."

Neither section mentions gate M17 (`docs/plan/memory.md:604`): "`backward(loss)`
consumes the recorded computation; a second `backward` on the same loss is
rejected", nor M18 (`:605`): changing a saved value is rejected statically, nor
M23 (`:610`). SPEC 9.6 presents an unconstrained PyTorch-shaped API.

`tensor_no_grad { ... }` at `:1293` is a block passed where an expression goes.
A7 has no such form; probe block 10 fails at **exit 5**, `Expected expression
[line 6: col 31]`.

**Approval:** no.

## DSG-19 · LOW · NEW · An undefined value in an expression is reported as an undefined *type*

Probe `w_spec9_b04_L1163-1184.a7`, `sum := a + b` inside `main` → **exit 6**,
`error: Undefined type (Identifier 'a') [line 4: col 12]`. The same wording
appears for `tensor_c_layout` at block 11 and for every unresolved call target in
blocks 5-8 and 10.

`a` is a value, not a type. The site is `a7/passes/type_checker.py:1211`, which raises
`TypeErrorType.UNDEFINED_TYPE` for an unresolved *identifier expression*;
`a7/errors.py:359` renders that code as the fixed string "Undefined type" and
`:419` appends "Ensure the type is defined before use". Every undefined value in
an expression therefore gets a type-flavoured message. This is a diagnostics
defect, outside this component; a grep of
`docs/audits/2026-09-16/compiler/types.md` and `parser.md` for the wording
returned nothing, so it is routed to the diagnostics audit named in
`docs/plan/audit/language-audit-checklist.md:124-127`.

**Approval:** no.

## DSG-20 · MEDIUM · NEW · `docs/STATUS.md:41-44` still defers what ledger L1 and L7 put in v1

`docs/STATUS.md:41-44`:

> ## Deferred Tracks
>
> Tensor, AI, GPU, performance annotations, package registry, and concurrency
> runtime support need separate design documents and prerequisites before code.

`docs/plan/decisions.md` superseded-material table: "`docs/STATUS.md:41-44`:
tensor, AI, GPU and concurrency as deferred tracks | L1, L7". L1 (`:36`) selects
"Finish the broader vision", L7 (`:42`) puts "Tensor operations, inference,
training and an AI-ready language foundation" in v1.

`site/public/llms-full.txt:422` repeats the deferral for concurrency, and
`:426-427` turns it into an instruction: "If a feature is listed here as
deferred, do not write public examples that rely on it as if it is complete."

So the public documentation and the ledger state opposite scopes for the same
three features. Track 0 owns the reconciliation
(`docs/plan/README.md:332`: "Mark superseded entries in `08-decisions.md`,
HANDOFF, STATUS and the safety contract without deleting them"); it has not
happened.

Note the package registry is correctly deferred and stays so — CLAUDE.md puts it
out of scope. Only the tensor/AI/GPU/concurrency half of the sentence is stale.

**Approval:** no.

## DSG-21 · MEDIUM · NEW · SPEC 9 constrains every tensor to `Numeric`, which cannot contain the two dtypes ledger L11 locks

`docs/SPEC.md:1095` and `:1109` constrain tensor element types with
`$T: Numeric`, and every signature in 9.9 repeats it (`:1360-1367`). SPEC 7.3
defines that set at `docs/SPEC.md:951`:

```a7
Numeric :: @type_set(i8, i16, i32, i64, isize, u8, u16, u32, u64, usize, f32, f64)
```

Ledger L11 (`docs/plan/decisions.md:46`) is locked: "Tensor formats `f16` and
`bf16` in addition to `f32` and `f64`". Its scope limit (`docs/plan/decisions.md:107`)
confirms the split: "L11 names tensor formats. Scalar floats remain `f32` and
`f64`."

Neither type exists. `docs/SPEC.md:221-236` (SPEC 3.2, primitive types) lists
`f32` and `f64` and nothing narrower. `grep -rn -w 'f16|bf16' a7/ --include=*.py`
returns 0 hits.

SPEC 9's own type structure therefore cannot express the precision decision the
ledger already made. That is not a wording problem; it forces three choices:
whether `f16` and `bf16` are A7 primitive types or tensor-only element codes;
what `Numeric` means once they exist (a scalar `f16` would become legal
arithmetic, which L11's scope limit appears to exclude); and what their
arithmetic and conversion semantics are under L16 and gate G1.

`docs/plan/README.md:501-502` (AI sequence step 2) already assumes the answer —
"Portable reference kernels for every required operator and dtype, including
defined f16 and bf16 widening where CPUs lack native support" — with the types
absent.

**Approval:** no for recording it. Adding the types is a language change and
needs one.

---

# What is missing

| Item | What exists now | What it needs | Decision owner | Decidable now? | Priority for v1 |
| --- | --- | --- | --- | --- | --- |
| Tensor value model: shape, dtype, strides, views, aliasing | SPEC 9.1 struct sketch that does not parse (DSG-5); nothing in `a7/` | A settled value semantics: default literal dtype, promotion, view vs copy, and how `usize` strides express a transposed or reversed view (`ai-frameworks-codex.md:49`: "`usize` strides cannot represent negative strides") | Gate G8 + M11 | Waits on G1 (float rules) and M11 (extents) | Blocks AI sequence steps 1-8  |
| Tensor dtypes `f16` and `bf16` | Locked by L11; not in SPEC 3.2, not in `Numeric` (SPEC `:951`), 0 hits in `a7/` (DSG-21) | Decide primitive-vs-element-code, what `Numeric` becomes, and their arithmetic under G1 | **none** for the types (needs a packet); G1 for semantics; G8 for the `Numeric` set | **Now** for the primitive-vs-element-code question; the semantics wait on G1 | AI sequence step 2 |
| Tensor type syntax | Two unparseable generic spellings in SPEC 9 | A spelling in SPEC 7 syntax, or a value-generic packet if `[N]T` shapes stay in the type | Gate G8; needs the generics work first | Waits on the generics audit and on the value model | Before any track 11 work  |
| Named call arguments | None; 20 uses in SPEC 9; no grammar | Either a language packet or a positional respelling of SPEC 9 | **none** — no gate, no packet owns this | **Now.** No dependency; it blocks the SPEC rewrite | Decide now; it is cheap and it unblocks the SPEC rewrite  |
| Multi-dimensional indexing `t[i, j]` and axis slicing `t[i, ..]` | None; no grammar; parse error | A packet; it changes the index grammar | **none** | **Now** in principle; better taken with the value model | Before track 11  |
| Declaration attributes (`@vectorize`, `@parallel`, `@prefetch`) | None; no grammatical position | Decide whether A7 has attributes at all. If not, delete them from SPEC 9 | **none** (`@parallel` overlaps G7) | **Now** — the answer can be "A7 has no attributes" | Low; performance hints are last  |
| Axis convention | `axis: -1` in SPEC 9 vs the `usize` index rule | A named convention distinct from element indices (`ai-frameworks-codex.md:50`) | Gate G8 | Waits on the value model | With the tensor value model  |
| Autodiff surface | Two different spellings (SPEC 9.6 and G8) and three memory gates (M17, M18, M23) that neither reflects | One spelling, with the tape-consumption and saved-value rules written into it | Gate G8 + M17/M18/M23 | Waits on G1, M11 and the value model | AI sequence step 3  |
| Broadcasting rule | A stated NumPy rule with an example that violates it (KNOWN) | Correct the example; state whether A7 broadcasts at all, given it rejects `[3]f64 + [2]f64` today | Gate G8 | Waits on G8's promotion decision | Named in the plan's test plan (`docs/plan/README.md:534-535`)  |
| Linear algebra (9.5) | 12 signatures, none needed by L10 | Decide whether v1 ships any of it. `ai-frameworks-codex.md:51` says no | Gate G8 | **Now.** L10 already says these are not v1 dependencies | Cut candidate  |
| Device / GPU API | 3 signatures + an undeclared `Device` type vs L8 interface-only | Delete or mark as interface sketch | Ledger L8 scope limit; no new gate needed | **Now.** L8's scope limit already answers it | Cut candidate  |
| Concurrency shape | Three incompatible surfaces (DSG-2) | Pick one. The B4 annotated-call option (`bend-for-a7.md:119-131`) removes M26 and M27 from v1 scope entirely; the G7 structured-task option keeps both. Note `f!(x)` collides with `!` (probe `t12`, exit 6) | Gate G7 | Waits on G5 and M10 — `docs/plan/README.md:270` makes G7 depend on both | Decide before track 9; the choice resizes the memory plan  |
| Task value lifetime | G7's example contradicts M10 and M36 (DSG-3) | A channel rule: exempt channels from "values move in", or construct them inside `task_group` | Gate M10, with M36 | Waits on the shape choice above | Before G7 is presented  |
| Native declaration surface | Nothing; one superseded draft | Open M25 with before/after examples, as the gate says | Gate M25 | **Now. Nothing blocks it**, and phase A's exit evidence already requires it open (`docs/plan/memory.md:662`) | **Highest of the three.** Five items queue behind it (DSG-4)  |
| Native descriptor attachment | M12 lists seven descriptor properties with no syntax to carry them | A declaration form that carries them | Gate M12, after M25 | Waits on M25 | With track 10  |
| Kernel-library pinning | M43 text only | Which libraries, pinned how — cannot be scoped before M25 | Gate M43 | Waits on M25 | With track 10  |
| Run-time stop contract for tensor and native failure | None (`language-audit-checklist.md:78`, gap 8) | A defined stop and message; M2 makes task/step/session extents recoverable but names no mechanism | Gate M39 / M2 | Waits on M2's recoverability split | Needed by AI acceptance  |
| Tensor reduction order and accumulation dtype | SPEC 9.4 states neither; G1's own open list names "tensor reduction order" (`docs/plan/README.md:100`) | A defined order, or a documented non-guarantee, plus the accumulation dtype (`ai-frameworks-codex.md:167`: "Reduction result — operator-specific") | Gate G1, with G8 | Waits on G1's strictness decision | Needed for reproducible training |
| Float-to-integer conversion failure | `tensor_to_i32` (`docs/SPEC.md:1369`) has no failure mode; G1 lists "float-to-integer conversion failure" as open (`docs/plan/README.md:99`) | A defined result or rejection for out-of-range and non-finite inputs | Gate G1 | Waits on G1 | With the numeric work (track 3b) |

## Checked and correct

- Element-wise `+` on same-shape 1-D numeric fixed arrays works end to end: A7 exit 0, `@Vector` lowering, `zig build-obj` exit 0 (probe `t01`, `zig_t01.txt`). KNOWN `types.md:599-600`.
- Shape-mismatched array addition is correctly rejected: probe `t13_broadcast`, exit 6, `Operator requires compatible types (add between [3]f64 and [2]f64)`.
- SPEC 9 carries a disclaimer at `docs/SPEC.md:1087-1090` and the word "Planned" in its title and table-of-contents entry (`:24`, `:1083`). It is marked — just not per-block, and not per CLAUDE.md's named parsed-only forms.
- `README.md`, `site/public/llms.txt`, `site/public/llms-full.txt` and every file under `site/public/docs/` contain zero occurrences of "tensor" (`grep -rniL tensor` lists all of them as non-matching). The tensor promise lives only in `docs/SPEC.md`. The public site does not leak it.
- No example in SPEC 9 violates the A7 source recursion ban: of the six functions it declares with bodies (`docs/SPEC.md:1318`, `:1323`, `:1392`, `:1399`, `:1414`, `:1427`; the 9.9 signatures at `:1360-1379` have no bodies), none calls itself and none forms a cycle. The ban is the one A7 rule section 9 does not break.
- `docs/lang-safety/edge-cases/12-ffi-boundary.md` states its own status accurately at `:107` ("All examples in this file are proposals. FFI does not exist in A7.") and its 2026-09-16 notes correctly retire its superseded vocabulary.
- Gate G7 and gate G8 both label their code "Proposed syntax. Every spelling here is undecided." (`docs/plan/README.md:273`, `:301`). The plan is honest about its own status; SPEC 9 is the outlier.
- `docs/plan/research/ai-frameworks-codex.md:44-52` had already found five SPEC 9 defects. Four of them (broadcasting, `flatten` views, negative strides, `axis: -1`, the boolean save API) are reproduced above with their citations; none had been carried into an audit ID.

## Test gaps

Everything in this component is untested, which is expected for absent features.
Two gaps are worth recording anyway:

- **No test asserts that any SPEC 9, G7 or FFI syntax is rejected.** If someone adds a `spawn` or `extern` keyword tomorrow, nothing fails. A small rejection corpus — one file per construct, asserting the exit code and the error category — would pin the current surface and give any future packet a before-and-after baseline. There is precedent: the plan's own test plan asks for "rejection of broadcasting `[3,1,4]` with `[2,5,1]`" (`docs/plan/README.md:534-535`).
- **Element-wise array addition has three tests and they cover only the working 1-D path.** `test/test_semantic_expressions.py:106-116` (accept), `:118-` (shape mismatch), `test/test_codegen_zig.py:650`, `:670-671` (the `@Vector` text). No test covers rank ≥ 2, and none covers `-`, `*`, `/` or `%` on arrays, so DSG-13's misleading diagnostic and the addition-only restriction are both unguarded. The codegen tests assert an exact Zig string, which is close to mirroring the implementation; they are justified here only because the `@Vector` coercion is the load-bearing detail Zig has to accept.

## Recommendation

### SPEC 9 — relabel in place and move the design out of the specification

The disclaimer at `docs/SPEC.md:1087-1090` is real but it is one paragraph
governing 356 lines of ```` ```a7 ```` blocks that render exactly like the working
examples in sections 1-8 and 10-13. Three of those lines
(DSG-1 destructuring, DSG-11 non-`@type_set` intrinsics) are on CLAUDE.md's
explicit Docs Accuracy list, which requires them to be marked *as such* wherever
they appear, not covered by a section-level note. And DSG-6 (`^` as power) is a
snippet that compiles today with a different meaning.

SPEC 6.6 sets the in-place precedent, at `docs/SPEC.md:835-839`:

> **Implementation Status**: Variadic parameter syntax is parsed and partially
> type-checked for declarations, but runtime iteration and ABI lowering are not
> implemented. Codegen modes reject variadic parameters before backend emission;
> do not treat variadic functions as runnable current syntax.

The difference is that SPEC 6.6's syntax *parses*. SPEC 9's does not parse and,
on the evidence above, is not a coherent design. So the right move is stronger
than a label.

**Recommended, in order:**

1. **Move the body of section 9 to `docs/plan/design/tensors.md`**, and leave in
   the SPEC a short section 9 that says what is decided (nothing), names the gate
   (G8), names the ledger entries that put AI in v1 (L7-L11), and links to the
   design file and the AI sequence. Renumbering is avoided by keeping the heading, and the
   table-of-contents entry at `docs/SPEC.md:24` keeps its wording.
   Wording for the replacement section:

   > ## 9. Planned Array Programming for AI
   >
   > **Implementation Status**: no tensor, array-programming, autodiff, device or
   > performance-annotation feature exists in A7, and none of the syntax
   > previously shown here parses. Ledger entries L7-L11 put CPU tensor
   > operations, inference and training in v1; gate G8 in `docs/plan/README.md`
   > decides the surface, and nothing has been decided. The design material,
   > including its known defects, is in `docs/plan/design/tensors.md`. Do not
   > treat any of it as A7 syntax.
   >
   > The one array operation A7 supports today is element-wise `+` on two
   > one-dimensional fixed arrays of the same length and numeric element type;
   > it is specified in section 3.3.

2. **In the moved file, fence every block as ```` ```text ```` rather than
   ```` ```a7 ````**, so no snippet renders as A7 source, and prefix each
   subsection with the defect list from this report.

3. **Fix the four errors that must not survive the move regardless**: the
   broadcasting shapes at `docs/SPEC.md:1156-1158`, `^` as power at `:1168`, the
   `tensor_batch_norm` arity clash at `:1284`/`:1401`, and the five destructuring
   lines.

**Approval.** Relabelling, re-fencing and moving the text changes no syntax, no
behavior and no accepted program: **docs-only, no approval needed** under
CLAUDE.md's Docs Accuracy rule, which already requires it. What would need
approval is *withdrawing the promise* — saying A7 will not have tensors — because
that contradicts locked ledger entries L1 and L7-L11. Nothing above proposes
that, and the recommended wording is careful to keep the v1 commitment while
removing the false implication that its spelling is settled.

### Concurrency — remove `@parallel` from the SPEC; make G7 choose a shape

There is no concurrency section to relabel; there is one stray annotation at
`docs/SPEC.md:1322` that is currently the language specification's only statement
about parallel execution, and it goes with section 9 under the move above.

`docs/STATUS.md:41-44` and `site/public/llms-full.txt:422` should be corrected to
say concurrency is **planned for v1 and undesigned** rather than deferred, since
the ledger already retired the deferral (DSG-20). Wording for STATUS.md:

> ## Planned, not designed
>
> Tensor, AI and concurrency support are in v1 scope (ledger L1, L7) and have no
> implementation and no approved syntax. Gates G7 (concurrency) and G8 (AI) in
> `docs/plan/README.md` own the decisions. GPU and accelerator work is interface
> design only (L8). Package-registry publishing stays out of scope.

**Approval.** The STATUS and site correction is docs-only and simply applies a
decision already in the ledger: **no approval needed**. The shape choice — and
the M10/M36 channel rule in DSG-3 — is gate G7 and gate M10, and needs the
owner.

### FFI — no documentation change; open M25 now

The FFI documentation is already honest: `12-ffi-boundary.md` says so at `:107`,
and M25 says so at `docs/plan/memory.md:623`. Nothing needs marking.

What is needed is a decision, and it is the most time-critical of the three: the
chain in DSG-4 puts five plan items behind it, and two of them (M14 performance
margins, the track 10 GLM security review) cannot even be *scoped* until it
lands. The execution plan schedules "M25 decided in Wave 4"
(`docs/plan/execution.md:436`) while phase A's exit evidence already requires
"The native declaration gate (M25) is open" (`docs/plan/memory.md:662`). Opening
it is the phase A task; it is not blocked on the correctness exit, and delaying
it does not buy anything.

**Approval.** Writing the M25 packet is ordinary planning work: **no approval
needed to write it**. The syntax it proposes is a language change and needs the
owner's approval, which is exactly what the packet is for.

## Not verified

- The three in-flight worktrees under `/home/cx89/Projects/pl-dev/a7-wt/` (C1, C4, C2). None of them touches this component on the evidence of the batch descriptions, but this was not checked.
- Whether SPEC 9's `tensor_flatten` (`docs/SPEC.md:1203`) can promise a shared-memory view — `ai-frameworks-codex.md:48` says it cannot for arbitrary strides. Recorded as that report's claim; not independently rechecked.
- The external claims in `ai-frameworks-codex.md` and `hardware-providers-codex.md` about JAX, PyTorch, oneDNN, BLAS and specific hardware. Both reports mark themselves advisory and say their external claims were not rechecked (`docs/plan/README.md:551`); this audit did not recheck them either.
- Whether any KNOWN audit ID already covers DSG-19's "Undefined type (Identifier 'a')" wording. A grep of `docs/audits/2026-09-16/compiler/types.md` and `parser.md` for that phrasing found nothing, but the 2026-09-16 diagnostics coverage was not read in full. The emitting site (`a7/passes/type_checker.py:1211`) was confirmed.
- Nothing else. `docs/plan/design/` does not exist (`ls -d docs/plan/design` → "No such file or directory"); the recommendation's destination `docs/plan/design/tensors.md` therefore needs the directory created, or another path chosen.

claims checked: 131
