# 07 — Modules, visibility, tooling

Current state: file is the module (L25). `alias :: import "path"` + `alias.name`
is the only backend-lowered form. Resolver: `a7/module_resolver.py:33-60`
(worklist load, `loading_stack` cycle check at 177-179), path resolve at
132-159 (`{path}.a7` or `{path}/mod.a7`), merge into one Zig file at
`a7/compile.py:894-927` with `module_emit_prefix` (704-706). `pub` is parsed
(`a7/parser.py:236-252`) and stored on decls but never enforced: no
`is_public` check exists in `a7/passes/`. SPEC 10.4 still says `pub` exports
top-level names. L27 supersedes it: `_name` private, rest public, `__` reserved.

## 1. pub enforcement design
Current: `pub value :: fn()` and plain `value :: fn()` both importable;
`h._value()` also accepted (P-MOD probe `private_qualified` prints 7).
Zig: `pub` per-file, erased by single-file lowering — A7 must enforce.
Odin: public-by-default + `@(private)`; Go: uppercase exports; Rust: private by
default, `pub`/`pub(crate)` opens; Python: `_` convention only.
Proposal: enforce L27. Underscore wins over `pub`: `pub _x` stays private.
Access `h._x` rejects at use site with decl + use spans.
```a7
// helper.a7
value :: fn() i32 { ret 7 }
_hidden :: fn() i32 { ret 8 }
// main.a7
h :: import "helper"
main :: fn() { io.println("{}", h.value()) } // ok; h._hidden() rejects
```
Keep `pub` accepted as redundant marker through V1 (P-MOD M-PUB). Needs P-MOD
decision (M-PUB, M-RESERVED, M-BOUNDARY). G6 gate.

## 2. Struct-field / enum-variant visibility
Current: L29 locks all struct fields visible across files. SPEC 10.4 says
fields always file-private — contradicts L29 and breaks `g.Point{x: 7}`.
Enum variants have no visibility rule at all.
Zig/Odin/Rust: fields of a public type are usable (Rust needs `pub` per field;
Zig/Odin expose all fields of a reachable type). Python: no enforcement.
Proposal: keep L29. Delete SPEC 10.4 private-field sentence. Variants follow
the enum: public enum exposes all variants; `_Enum` is private.
```a7
// geometry.a7
Point :: struct { x: i32, y: i32 }
Color :: enum { Red, Green }
```
No per-field `pub` (parser accepts it today without effect — reject or ignore
by decision). Needs P-MOD decision (L29 scope limit notes fields need packet
cover). G6.

## 3. Import cycles
Current: rejected via `loading_stack` (`module_resolver.py:177-179`,
`topological_sort` at 431-471). Message names chain but spans are thin.
Zig allows cycles (lazy analysis); Odin/Go/Rust reject (Odin: chain diagnostic;
Go: illegal; Rust: E0391 with note).
Proposal: keep rejection. Report full chain with one span per edge:
`main.a7 -> cyc_a.a7:1 -> cyc_b.a7:1 -> cyc_a.a7`. Self-import is a 1-edge
cycle. No re-export: `a.b.x` never resolves through `a`'s imports. Depth cap
(M-DEPTH, 32) is separate and undecided.
```a7
// cyc_a.a7: b :: import "cyc_b"
// cyc_b.a7: a :: import "cyc_a"  // error, chain above
```
Needs P-MOD decision (cycle rule + span format). G6.

## 4. mod.a7 directories
Current: `resolve_module_path` tries `{path}.a7` then `{path}/mod.a7`
(`module_resolver.py:150-153`). If both exist, first wins silently.
Odin/Go: directory is the package. Zig/Jai: file-based. Research
(`docs/plan/research/modules-odin-zig-go.md` R1) recommends dropping fallback.
Proposal (P-MOD M-DIRECTORY): remove implicit fallback; `h :: import "pkg/mod"`
is the explicit spelling. Bare `"pkg"` with only `pkg/mod.a7` on disk rejects
with a did-you-mean hint. Alternative (keep + precedence rule) keeps ambiguity.
Needs P-MOD decision. G6.

## 5. fmt / test / doc CLI
Current: `check`, `build`, `run`, `doctor` exist (`a7/cli.py:187-192`).
`--doc-out`/`doc` mode emits markdown; no `fmt`, no `test` runner.
Zig: `zig fmt` + `zig test`; Go: `gofmt`/`go test`; Rust: `rustfmt`/`cargo test`;
Odin: `odin test`; Python: external (black/pytest).
Proposal: `a7 fmt` (canonical layout; no semantic change; idempotent check via
`--check`), `a7 test` (discovers `*_test.a7` or `test_` entry files, runs each
`main :: fn()`, reports pass/fail per file), keep `doc` as-is. All three reuse
the pipeline result object so module graph and spans match `check`.
```sh
a7 fmt main.a7 helper.a7
a7 test ./tests/
```
Needs G6 decision (G6 names `test`/`fmt` explicitly). P-MOD does not cover it.

## 6. Entry-point rule
Current: entry file must define `main :: fn()` with no params/result
(`a7/compile.py:284-301`); `--lib` suppresses for `check` (L54). Imported
modules exempt. `build`/`run` always require `main`.
Go/Rust: `main` package/fn required for binaries, libraries exempt. Zig: root
needs `main` only for executables. Python: no rule.
Proposal: keep. No change requested. `check --lib` stays the library spelling;
`build`/`run` never accept `--lib`. Document that non-entry `main` is an
ordinary function (lowered under its module prefix, not as program entry).
Needs no new decision (L54 locked). Note in P-MOD acceptance only.

## Decision map
| Item | Needs P-MOD | Needs G6 |
| --- | --- | --- |
| pub enforcement (M-PUB, M-RESERVED, M-BOUNDARY) | yes | yes |
| Field/variant visibility (L29/SPEC fix) | yes | yes |
| Cycle format, no re-export | yes | yes |
| mod.a7 fallback (M-DIRECTORY) | yes | yes |
| Import forms: bare/named/using (M-FORMS) | yes | yes |
| Depth cap (M-DEPTH) | yes | yes |
| fmt/test/doc commands | no | yes |
| Entry-point rule | no (L54) | no |
