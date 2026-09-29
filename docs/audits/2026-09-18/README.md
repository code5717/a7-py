# Audits, 2026-09-18

Round two of the audit program: everything the 2026-09-16 compiler audits did
not cover, plus what the language is missing to be usable in production. Asked
for by the user on 2026-09-18 ("audit full everything that wasn't audited on and
everything that is missing", "also everything that makes this language a
finished production language"). Coverage is tracked in
[the language audit checklist](../../plan/audit/language-audit-checklist.md).

Shared brief: `tmp/audit/2026-09-18/PROMPT-COMMON.md`. Every report ends with a
`claims checked: N` line, marks each finding NEW or KNOWN, and answers for each
defect whether fixing it would change a program that A7 accepts and Zig builds
today (which decides whether the fix needs the owner's approval).

| Report | Scope | State |
| --- | --- | --- |
| `methods.md` | Receiver functions, field access, the implicit `ref` argument path, `v.m()` | done: 16 findings (2 CRITICAL, 4 HIGH, 8 MEDIUM, 2 LOW), 7 NEW. A7 has no methods, and neither SPEC 6.5 example compiles |
| `stdlib.md` | The stdlib registry, `io`/`math`/`mem`/`string`, builtins and intrinsics, `Option`/`Result` | done: 18 findings, 8 NEW. The callable stdlib is 14 functions; 5 missing pieces have no owner |
| `production-readiness.md` | Workflow commands, diagnostics as a product, editor and debugger support, release/CI/packaging, versioning, docs, compiler limits | done: 38 findings (2 CRITICAL, 16 HIGH, 16 MEDIUM, 4 LOW), 25 NEW. None of the five promised workflow commands exists; all twelve 2026-09-14 security findings are still live |
| `visibility-modules.md` | `pub`, the underscore rule, the module merge, type aliases | done: 14 findings, all NEW. Imports leak in both directions; cycle detection is unreachable |
| `design-gaps.md` | Tensors (SPEC 9), concurrency, the FFI and native boundary: specified or promised, nothing implemented | done: 21 findings, all NEW, none changing a program that builds. All 16 SPEC 9 code blocks fail to compile; gate G7's own example violates two memory gates |
| `examples-tests.md` | The examples corpus and goldens; the test suite against the Test quality rule | done: 36 findings. Mutation testing shows 47% of the suite asserts nothing that could fail; all 43 goldens are current |
| `language-features.md` | Feature completeness: generics, multiple returns, destructuring, optionals and errors, comptime, an abstraction seam, bit operations | done: 29 findings (6 CRITICAL, 10 HIGH), 13 NEW. A 193-line text tool needed three rewrites to compile, and splitting it across files broke it |

Nothing in these reports changes behavior. Fixes they propose enter the waves
and packets in `docs/plan/execution.md`.
