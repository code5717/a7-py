# A7 Memory-Safety Review — Z.AI GLM-5.3 Dedicated Reviewer

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it, in particular the manual `del` remediation direction (see the [memory plan](../../plan/memory.md)). Findings MS-1…MS-12 and their evidence stand as recorded.

- **Date:** 2026-09-14
- **Reviewer:** Z.AI GLM-5.3, external memory-safety reviewer invoked by the controlling
  Codex session. Advisory output; not the primary coordinator.
- **Repository state audited:** `701c67936c70ad2b0608326e23e56cc5d38c9fdb`
  (`701c679 Bump anthropics/claude-code-action from 0.0.63 to 1.0.148 (#22)`).
- **Working-tree state at audit start:** uncommitted documentation-cleanup edits in
  `README.md`, `docs/SPEC.md` (ToC anchor style only), `docs/lang-safety/README.md`
  (new "Reading status" disclaimer that research acceptance does not establish
  implementation), `site/public/docs/index.md`, `site/public/llms-full.txt`, plus new
  `AGENTS.md` "Test quality" section, untracked `docs/README.md`, and untracked
  `docs/audits/`. Full diff snapshot preserved at `/tmp/opencode/pre-audit-docs-diff.txt`
  (125 lines). No compiler-source modifications were present or made.
- **Scope:** memory safety only, traced from public syntax and
  `docs/SAFETY_CONTRACT.md` / `docs/lang-safety/` / `docs/SPEC.md` / `docs/STATUS.md`
  promises through parser, name/type/semantic validation, safety facts, AST
  transformations, generic and module lowering, and Zig emission.
- **Method:** full first-hand read of `a7/safety.py`; targeted first-hand reads of the
  load-bearing regions of `a7/backends/zig.py`, `a7/passes/type_checker.py`,
  `a7/passes/semantic_validator.py`, `a7/compile.py`; five read-only sub-agent
  deep-dives (type checker; semantic front-end; Zig backend; pipeline/transforms;
  test inventory); compile-only fixtures run through the real CLI
  (`.venv/bin/python main.py … --output …`) with emitted-Zig inspection and native
  qualification via `zig build-exe -fno-emit-bin` (compile-only, full semantic
  analysis from the reachable `main`; Zig 0.16.0 at
  `/tmp/a7-audit-20260914/zig/zig`). Initial `ast-check`/`build-obj` screening was
  superseded by `build-exe -fno-emit-bin` re-qualification because of Zig's lazy
  analysis (see correction note). **No A7 program that exhibits memory corruption
  was compiled to an executable or executed.** Every defect demonstration stops at
  A7 accepted/rejected, emitted Zig, and external Zig compile-only semantic
  analysis. Runtime limits are stated once under Limitations.
- **Independence:** sibling reports under `docs/audits/2026-09-14/`
  (`compiler-review.md`, `language-contract-review.md`, `audit-matrix.md`,
  `docs-cleanup-report.md`, `website-codex-review.md`) were **not** read. Pre-existing
  repro fixtures were listed for name-collision avoidance only; this report's fixtures
  use the unique `glm-memsafe-` prefix under `docs/audits/2026-09-14/repros/`.
- **Gate context:** see correction note item 6. This report does not assert,
  confirm or refute gate status.
- **Capability notes (required disclosure):** three initial sub-agent dispatches failed
  with `Rate limit reached for requests` (provider-side limit); all three were retried
  successfully and completed. No authentication failures otherwise; no network access
  was needed; no nested model CLIs were launched.

## Correction note — 2026-09-14, second pass (coordinator reconciliation)

This report was corrected in place after reconciliation against coordinator
findings. Changes:

1. **Native-lowering evidence re-qualified.** Zig's lazy analysis means
   `ast-check`/`build-obj` without a reachable entrypoint may not analyze all
   function bodies; the first pass's `build-obj` passes were therefore weaker
   evidence than presented (observed errors were real, passes were not conclusive).
   Every headline fixture has now been re-qualified with compile-only
   `zig build-exe -fno-emit-bin` (Zig 0.16.0), which semantically analyzes `main`
   and everything reachable from it: all ten defect fixtures pass full semantic
   analysis, and the `del p` fixture fails at the Zig stage (its A7 acceptance and
   Zig-stage failure are distinguished under MS-11). No binary was emitted or
   executed at any point.
2. **Explicit epistemics:** no proof of runtime memory safety follows from compiled
   fixture acceptance, emitted-Zig text inspection, or the absence of
   panic/trap strings in emitted code. That shortcut is rejected throughout this
   report; compile evidence demonstrates only (a) A7 acceptance/rejection and
   (b) accepted native lowering shape. Runtime behavior of every defect program
   remains unobserved and unclaimed.
3. **Test-strategy correction:** the earlier suggestion to mark known-defect
   regression tests `xfail` is withdrawn — it violates the repository
   `AGENTS.md` "Test quality" rule. For agreed current requirements the regression
   tests must fail visibly (red) until fixed.
4. **Remediation corrections:** the "ever-assigned-from-`new`" heap-provenance
   suggestion is withdrawn as unsound (a binding can later hold different
   storage); replaced with a conservative path-valid provenance rule framed as a
   design question. The "defer-del marks moved immediately" suggestion is withdrawn
   (it would reject legitimate reads before scope exit, e.g. the blessed
   `examples/011_memory.a7` idiom); replaced with scheduled-cleanup semantics and
   conflict tracking, policy left as a design question.
5. **Classification review:** known-gap vs defect classifications re-reviewed with
   confidence levels (Section 4.1), distinguishing broken promises (defects) from
   acknowledged incomplete work (gaps) and from defects-by-silence.
6. **Gate context:** the coordinator's current full gate stands at 11/12 with
   pytest at 12 failed / 2515 passed / no skips on the configured toolchain. This
   review's findings are advisory and were derived independently of the gate;
   incidental failures observed in other environments are not treated as evidence
   of regressions, and nothing here asserts gate status.

---

## 1. Executive summary

A7's safety architecture is real and partially effective: the pipeline ordering is
correct (safety proofs gate codegen, `a7/compile.py:346-382`), the `BackendPlan`
approval mechanism fails closed in codegen (`a7/backends/zig.py:1786-1795`), literal
out-of-bounds indexing, use-after-`del` on the same binding, unknown-length slice
indexing, and unguarded ref field access are all rejected, and the direct/mutual/local
function-pointer-alias recursion ban works as documented.

However, the **fact-flow engine that discharges the obligations the safety contract
claims (`index`, `slice`, `deref`, `div/mod`, `cast`) has two confirmed soundness
holes that let memory-unsafe programs pass every gate and emit fully-compiling Zig**:

1. **Unsound joins (MS-1):** facts for variables mutated inside
   branches/loops/blocks are silently restored to stale pre-block knowledge at block
   exit (`a7/safety.py:301-306`), so an index proven in-bounds using stale facts is
   emitted as an unchecked access (`arr[y]` raw; OOB write under ReleaseFast).
2. **No call effects (MS-2):** calls never invalidate facts
   (`a7/safety.py:444-447`); a callee that `del`s through a `ref` parameter leaves
   the caller's non-nil proof intact, and emitted code writes through a destroyed
   pointer (`kill(q); q.?.x = 1;`).

Around these sit confirmed acceptance of: alias double-`del`, `defer del` + explicit
`del` double deletion, `del` on a `ref` parameter aliasing a caller stack lvalue
(`allocator.destroy(&stack_var)`), unchecked untagged-union active-field reads,
returning slices of stack arrays, uninitialized struct/slice bindings emitted as Zig
`undefined`, and two recursion-ban bypasses (struct-field function pointers and
module-qualified cross-module calls). Release artifacts build with
`-OReleaseFast` (`scripts/build_examples.py:25`), which removes every Zig runtime
backstop the current lowering leans on; the `docs/lang-safety/` aspiration
("emitted Zig is memory-safe under `-O ReleaseFast`") is not met today, while the
narrower `docs/SAFETY_CONTRACT.md` claims are met only up to the MS-1/MS-2 holes.

Most of the individual gaps are individually acknowledged somewhere in
`STATUS.md`/`SAFETY_CONTRACT.md` ("full ref/del alias behavior, and
ownership/lifetime guarantees are incomplete"), but the two fact-engine soundness
holes and the recursion-ban bypasses are **not** acknowledged anywhere and contradict
the contract's enforced rows. Section 4 separates confirmed defects from documented
gaps and hypotheses, with a classification/confidence review in Section 4.1;
Section 7 lists design decisions requiring agreement; Section 8
gives regression-test specifications; Section 9 gives the ordered qualification
roadmap. All native-lowering evidence is compile-only
(`zig build-exe -fno-emit-bin` from a reachable `main`); no runtime memory-safety
conclusion is drawn anywhere in this report — compiled acceptance, emitted-text
scans, and absence of trap strings do not prove runtime safety, and that inference
is rejected (see correction note and Limitations).

---

## 2. Promise surface audited (what the compiler claims)

| Source | Claim | Status in this audit |
| --- | --- | --- |
| `docs/SAFETY_CONTRACT.md:3-6` | Compiler must fail closed; risky operations without proof are rejected before Zig emission | Pipeline gate confirmed (`compile.py:346-382`, `zig.py:1786-1795`), but proofs themselves are unsound (MS-1, MS-2) |
| `docs/SAFETY_CONTRACT.md:45-58` (risk table) | cast, div/mod, index, slice, deref, use-after-del enforced; arithmetic, union discriminants, ownership "active work" | Enforced rows verified working on their positive/negative controls, **except** that index/slice/deref proofs can be discharged from stale facts (MS-1/MS-2). Overflow row confirmed disabled (`safety.py:631-636`). Union row confirmed dead (`ObligationKind.UNION_FIELD` never constructed, `safety.py:184`) |
| `docs/SAFETY_CONTRACT.md:64-78` | No public address-of/deref; `ref T` nullable today; `new`/`nil` maybe-nil until proven | Matches implementation (`.adr`/`.val` rejected, `type_checker.py:1784-1791`; auto-`&` inserted only at ref call sites, `zig.py:1661-1666`) |
| `docs/SAFETY_CONTRACT.md:82-91` | del cleanup required, use-after-del rejected, reassignment reinitializes; affine refs + alias rejection are future work | Same-binding semantics confirmed; alias/defer-double variants confirmed unenforced (MS-3, MS-4, MS-5) |
| `docs/STATUS.md:33-34` | "full ref/del alias behavior, and ownership/lifetime guarantees are incomplete" | Accurate; confirms these are known gaps (but see MS-8: no escape analysis exists at all) |
| `docs/lang-safety/README.md:20-26` (research contract) | Statically rejects **every** memory-safety-violating program; emitted Zig safe under `-O ReleaseFast`; no unsafe escape hatch | Aspirational; not met (MS-1..MS-9 all produce ReleaseFast-unsafe or trapping programs). The working-tree "Reading status" disclaimer added to this file correctly frames research ≠ implementation |
| `docs/SPEC.md §8.4` | "Static double-free or use-after-free prevention beyond the current basic shape checks" not implemented; no bounds-check insertion by A7 | Accurate. SPEC also documents surface that does not compile (see MS-12 spec drift) |
| `AGENTS.md:49-51` | Recursion ban covers direct, mutual, and local function-pointer alias cycles | Direct/mutual/local-alias confirmed enforced and tested; struct-field/global function pointers and module-qualified calls bypass it (MS-7) |

---

## 3. Architecture facts established (with evidence)

- **Pipeline order** (`compile.py`): tokenize → parse → module load+inline into one
  program (`:235-261`) → name resolution (`:269-271`) → type check (`:313-327`) →
  semantic validation (`:329-344`) → `SafetyProofPass` (`:346-359`) → semantic gate
  (`:374-382`) → `ASTPreprocessor` (`:388-395`) → Zig codegen with `BackendPlan`
  (`:397-404`). No path emits Zig with safety errors outstanding; no error swallowing
  reaches codegen.
- **Approvals** are keyed `(id(node), operation)` (`safety.py:208-222`); codegen
  re-checks and fails closed (`zig.py:1786-1795`). Post-safety AST preprocessing
  replaces only UNARY/BINARY nodes with LITERALs (constant folding) and never creates
  gated node kinds, so approvals survive transformations today. This safety is
  **incidental** (no liveness/versioning guard on `id()` reuse); flagged as latent
  hazard LH-1.
- **Generic lowering is Zig `comptime`**, not Python-side monomorphization
  (`zig.py:432-436`, `:518-546`). The `GenericMonomorphizer` in `a7/generics.py`
  (deep-copy + substitution, `:134-182`) is dead code; if ever wired in post-safety it
  would bypass proofs by construction (LH-2). Generic bodies are safety-checked once
  on generic types and fail closed for length-dependent proofs (verified:
  `first :: fn(a: []$T) $T { ret a[0] }` is rejected, "index bounds are not proven").
- **Module lowering** inlines imported file modules into one combined program with raw
  names; only function *emission* is prefixed (`compile.py:613-627`,
  `zig.py:1625-1629`). The combined program is fully safety-analyzed in codegen modes.
- **Lowering shapes**: `ref T` → `?*T` (`zig.py:2100-2104`); ref-arg lvalues get auto
  `&` (`:1661-1666`); approved field access/assignment through refs emit `.?`/`.?.*`
  (`:1713-1749`); indexing emits raw `obj[i]` (`:1670-1686`); `new T` →
  `allocator.create(T) catch null` with `page_allocator` (`:1903-1914`, `:159`);
  `del` → `if (expr) |p| allocator.destroy(p)` with **no nulling**
  (`:1300-1306`); defer maps 1:1 to Zig `defer` (`:1272-1298`); untagged unions emit
  plain Zig `union` (`:607-626`); declarations without initializers get
  `_default_value` — zero for numerics, `null` for pointers, **`undefined` for
  structs, unions, slices, and anything unrecognized** (`:2115-2141`).
- **Profiles**: the Python package only emits Zig; builds happen in
  `scripts/build_examples.py` (`:20-27`: debug `-ODebug`, release `-OReleaseFast`)
  and `test/test_pipeline_native.py` (`:36-46`). In ReleaseFast, Zig's bounds,
  overflow, null-unwrap, `@intCast`, and union-active-field checks are all disabled —
  i.e., **every current backstop for the lowered risky operations disappears in the
  release profile**.

---

## 4. Findings

Classification key: **[DEFECT]** confirmed by compile-only repro with emitted-Zig
evidence; **[GAP]** acknowledged in docs but confirmed unenforced, with teeth;
**[HYP]** hypothesis from code reading, not reproduced. Severity reflects worst-case
impact of an *accepted* program: memory corruption (critical/high), crash-only,
contract violation, or tooling.

### MS-1 [DEFECT, critical] — Unsound fact join: stale facts after block-scoped mutation

- **Where:** `a7/safety.py:301-306` (BLOCK: `saved = copy_symbols(); …;
  restore_symbols(saved)`), `:335-344` (IF), `:345-363` (WHILE/FOR). Fact map is
  name-keyed (`:152`, `:167-168`).
- **Mechanism:** assignments inside any nested block update `facts.by_symbol`, but
  block exit restores the *snapshot* taken at entry. Guard-narrowing refinements
  should indeed be rolled back — but so are legitimate updates to outer variables.
  After the block the compiler believes pre-block knowledge (e.g. `y ∈ [0,0]`) while
  the runtime value may be anything assigned in the branch. There is no join/widen
  and no invalidation for assigned-in-block symbols; loop bodies are visited once
  with the same restore semantics.
- **Repro:** `docs/audits/2026-09-14/repros/glm-memsafe-join-stale-index.a7`

  Current A7 (compile-only probe):
  ```a7
  main :: fn() {
      arr: [2]i32 = [1, 2]
      y: usize = 0
      c := true
      if c { y = 5 }
      arr[y] = 1
  }
  ```
  A7 accepts (exit 0). Emitted Zig (verified):
  ```zig
  pub fn main() void {
      var arr: [2]i32 = .{ 1, 2 };
      var y: usize = 0;
      const c = true;
      if (c) { y = 5; }
      arr[y] = 1;
  }
  ```
  `zig build-exe -fno-emit-bin` (full semantic analysis from `main`) succeeds. The
  `index` obligation was discharged from the stale
  interval `[0,0]` (`_prove_index`, `safety.py:567-574`). At runtime `y == 5`:
  Debug/ReleaseSafe → guaranteed trap; **ReleaseFast → out-of-bounds write**. The
  same staleness defeats `slice`, `cast` (PROVABLE_NARROWING via `_range_fits`,
  `safety.py:537-544`), and nonzero-divisor proofs.
- **Runtime behavior not executed** (per audit constraints); the compile-time
  mis-discharge and unchecked emission are the confirmed facts.

### MS-2 [DEFECT, critical] — Calls have no effects: stale nil/interval facts across calls; callee `del` through `ref` param

- **Where:** `a7/safety.py:444-447` (CALL visits callee and args only — no fact
  invalidation for ref-passed arguments or anything else); `zig.py:1300-1306`
  (`del` destroys through the param pointer); `type_checker.py:1378-1405`
  (lvalue args to `ref` params marked for auto-`&`).
- **Repro:** `repros/glm-memsafe-call-del-stale-nil.a7`

  Current A7 (compile-only probe):
  ```a7
  kill :: fn(p: ref Pt) { del p }
  main :: fn() {
      q := new Pt
      if q == nil { ret }
      kill(q)
      q.x = 1
  }
  ```
  A7 accepts. Emitted Zig (verified):
  ```zig
  fn kill(p: ?*Pt) void { if (p) |p| allocator.destroy(p); }
  pub fn main() void {
      var q = allocator.create(Pt) catch null;
      if ((q == null)) { return; }
      kill(q);
      q.?.x = 1;
  }
  ```
  `kill` destroys the allocation; the caller's `non_nil` fact (learned by the
  `== nil` early-return guard, `safety.py:698-702` via `_learn_after_stmt:663-668`)
  survives the call, so `q.x = 1` is *approved* and emitted as a use-after-free
  write. `zig build-exe -fno-emit-bin` succeeds. Value-domain variant: any `ref`-parameter write
  invalidates caller interval facts used by index/slice/cast proofs (not separately
  reproduced; same code path, `safety.py:444-447`).
- Related: `del` emits no nulling store, so even without aliases the binding keeps a
  dangling pointer value (`zig.py:1306`).

### MS-3 [DOCUMENTED GAP — confirmed silent acceptance, high] — Alias-blind `del`: name-keyed moved set, double deletion accepted

- **Where:** `a7/safety.py:724-726` (`_mark_deleted` records only the syntactic
  identifier name); moved-set logic `:397-399`, `:326-328`. No alias/points-to facts
  exist anywhere (`ValueFact`, `safety.py:137-146`).
- **Repro:** `repros/glm-memsafe-alias-double-del.a7`: `pp := new Pt; qq := pp;
  del pp; del qq` — accepted; emitted Zig destroys through both `pp` and `qq`
  (verified, `zig build-exe -fno-emit-bin` OK). Double free with `page_allocator` (no
  double-free detection in any Zig mode). STATUS.md admits "full ref/del alias
  behavior … incomplete", so this is a **documented gap with confirmed silent
  acceptance** (see Section 4.1) rather than an undisclosed defect; that it is
  accepted with no diagnostic and no warning at the `del`/`defer del` usage sites in
  SPEC §8 keeps it a live hazard.

### MS-4 [DEFECT, high] — `defer del p` + explicit `del p` compiles to double deletion

- **Where:** `a7/safety.py:379-386` — the DEFER branch deliberately visits a
  deferred DEL's operand **without** marking it moved (contrast `:387-389`); no
  pass anywhere relates a deferred del to a later explicit del. `del` does not null
  the binding (`zig.py:1306`), so the deferred destroy always re-fires.
- **Repro:** `repros/glm-memsafe-defer-del-double.a7`: `p := new Pt; defer del p;
  del p` — accepted; emitted Zig (verified):
  ```zig
  const p = allocator.create(Pt) catch null;
  defer if (p) |p| allocator.destroy(p);
  if (p) |p| allocator.destroy(p);
  ```
  Double free at scope exit. Note the docs-blessed idiom (`examples/011_memory.a7`)
  uses `defer del` alone and is fine; the conflict combination is simply unchecked.

### MS-5 [DEFECT, high] — `del` on a `ref` parameter destroys caller stack storage

- **Where:** `a7/passes/semantic_validator.py:384-396` — the only `del` validation
  is "operand has ReferenceType". `type_checker.py:1392-1395` lets any lvalue be
  passed to a `ref` param; `zig.py:1661-1666` emits `&arg`; `zig.py:1300-1306`
  destroys through it.
- **Repro:** `repros/glm-memsafe-del-ref-param.a7`: `bad :: fn(x: ref i32) { del x };
  main { v := 3; bad(v) }` — accepted; emitted Zig (verified):
  ```zig
  fn bad(x: ?*i32) void { if (x) |p| allocator.destroy(p); }
  pub fn main() void { var v: i32 = 3; bad(&v); }
  ```
  `allocator.destroy` on a stack address — invalid free. There is no heap-ness
  distinction for `del` anywhere in the compiler.

### MS-6 [GAP, high] — Untagged-union active-field access is entirely unchecked

- **Where:** reads type-check against any declared field (`type_checker.py:1776-1782`,
  `:1812-1817`); `ObligationKind.UNION_FIELD` is declared (`safety.py:184`) but
  **never constructed** anywhere; no approval is required for union field access in
  codegen (`zig.py:1713-1721` plain path); untagged unions lower to plain Zig
  `union` (`zig.py:607-626`).
- **Repro (runtime-active variant):** `repros/glm-memsafe-union-inactive-field.a7`
  (`u := U{a: n}; ret u.b` with runtime `n`) — accepted, `zig build-exe
  -fno-emit-bin` succeeds (full semantic analysis from `main`).
  Comptime-known variant additionally shows Zig itself rejects it at compile time
  (`error: access of union field 'b' while field 'a' is active`), but with runtime
  values the mismatch becomes a runtime check: panic in Debug/ReleaseSafe,
  **type confusion (UB) in ReleaseFast**. Not executed, per constraints.
- **Docs status:** SAFETY_CONTRACT lists union discriminant proofs as "active
  compiler-safety work" — acknowledged gap. SPEC §3.3 does not warn that inactive
  reads are unchecked; SPEC drift worth fixing regardless of the language decision.

### MS-7 [DEFECT, high] — Recursion-ban bypasses: struct-field/global function pointers and module-qualified calls

(Cited as `memory-safety-glm-review.md:343-368` for MS-7a/7b in docs/plan/research/memory/review/qwen.md. The v1 plan tracks this as gate G4.)

The ban (`AGENTS.md:49-51`, SPEC §6.2) is enforced via a name-keyed call graph over
top-level functions whose callee extraction requires a bare `IDENTIFIER`
(`semantic_validator.py:501-544`, `_direct_callee_name:803-818`).

- **7a. Struct-field function pointer:** `_collect_function_aliases` only tracks
  IDENTIFIER←IDENTIFIER assignments (`:1091-1104`); `s.f(...)` callees are invisible
  (`:812-813`). Repro `repros/glm-memsafe-recursion-struct-fnptr.a7`
  (`s := Cb{f: spin}; … ret s.f(n - 1)`) — accepted, emitted Zig is directly
  recursive (verified, `zig build-exe -fno-emit-bin` OK). Unbounded recursion at
  runtime → stack exhaustion (a memory-safety event). Not executed.
- **7b. Module-qualified calls:** `_annotate_file_module_calls`
  (`compile.py:574-595`) tags `helper.work()` for codegen emission but leaves the
  callee a FIELD_ACCESS, so no graph edge is created, while the imported body sits in
  the graph under its raw name. Repro `repros/glm-memsafe-recursion-module/`
  (`task` → `helper.work` → `task`) — accepted; emitted Zig (verified,
  `zig build-exe -fno-emit-bin` OK):
  ```zig
  fn module___helper__work(n: i32) i32 { return task(n); }
  fn task(n: i32) i32 { … return module___helper__work((n - 1)); }
  ```
  Undetected mutual recursion across modules.
- **7c [HYP, medium].** Alias chains (`g := f; h := g; h()`) break alias tracking
  (`semantic_validator.py:1098-1104`); nested-function bodies are excluded from the
  graph but are today accidentally gated by an unrelated `UNDEFINED_TYPE` at the call
  site; higher-order forwarding is modeled one level deep. All from code reading;
  7a/7b were the reproduced representatives.

### MS-8 [GAP (broadly documented) / DEFECT-BY-SILENCE (specific), high] — No escape/lifetime analysis: returning slices of stack storage accepted

- **Where:** no escape analysis exists (no lifetime/dangling tracking in any pass);
  slicing lowers to Zig slicing on locals (`zig.py:1688-1694`); functions may return
  slice types (`[]T`), and Zig's "local escapes" error does not fire for slices
  returned through a pointer-typed context.
- **Repro:** `repros/glm-memsafe-slice-stack-escape.a7`

  Current A7 (compile-only probe):
  ```a7
  make :: fn(n: i32) []i32 {
      buf: [4]i32 = [0, 0, 0, 0]
      buf[0] = n
      ret buf[0..4]
  }
  ```
  Accepted; emitted Zig (verified) is `var buf: [4]i32 …; return buf[0..4];` —
  `zig build-exe -fno-emit-bin` succeeds. The returned slice dangles after `make`
  returns, in Debug and ReleaseFast alike. Storing `&arg` ref-params into heap objects
  (auto-`&` at `zig.py:1664`) is the pointer analogue — **[HYP]**, not reproduced.
  SPEC §8.4 acknowledges missing ownership/lifetime analysis; returning-slices is
  nevertheless accepted silently.

### MS-9 [DEFECT-BY-SILENCE, high] — Uninitialized struct/slice bindings emit Zig `undefined`; no definite assignment

- **Where:** `type_checker.py:725-729` accepts `var x: T;` for any annotated `T`;
  the safety pass's `initialized` fact is never read (`safety.py:144`, `:307-310`);
  `_default_value` returns `undefined` for structs, unions, slices, and unrecognized
  types (`zig.py:2115-2141`).
- **Repro:** `repros/glm-memsafe-uninit-struct-slice.a7` (`p: Point; v := p.x;
  s: []i32`) — accepted; emitted Zig contains `undefined` declarations (verified,
  `zig build-exe -fno-emit-bin` OK). Reading Zig `undefined` is illegal behavior in
  **all** build modes. Numerics get `0` and pointers `null` (defined), so the
  exposure is specifically struct/union/slice (and any type falling through
  `:2141`).

### MS-10 [GAP, high] — Fixed-width arithmetic overflow proofs are disabled

- **Where:** `_prove_integer_overflow` begins with an unconditional `return`
  (`safety.py:631-636`; the obligation code `:637-646` is unreachable), while
  emitted arithmetic is plain Zig ops (`zig.py:1586-1609`). Debug: overflow panics;
  ReleaseFast: wrap/UB. Acknowledged in SAFETY_CONTRACT/STATUS. No repro needed
  (documented); tests confirm it is untested (Section 6).
- Note (2026-09-16): ledger L5 decides that integer `+`, `-` and `*` wrap, so the
  required semantics for those operators change from proof to wrapping. Division,
  shifts and casts remain open under gate G3.

### MS-11 [DEFECT, medium] — `del` of a variable named `p` emits invalid Zig (capture shadow)

- **Where:** `zig.py:1306` (and the inline defer variant `:2386-2390`) uses the
  fixed capture name `|p|`: `if (p) |p| allocator.destroy(p);`.
- **Repro:** `repros/glm-memsafe-del-var-named-p.a7` — A7 accepts (exit 0);
  the Zig stage fails on the emitted text: `zig ast-check` and
  `zig build-exe -fno-emit-bin` both report
  `error: capture 'p' shadows local constant from outer scope`. Evidence
  distinction: **A7 acceptance is demonstrated; native lowering is demonstrated to
  fail at the external Zig compile step** (the defect). Not memory-unsafe (build-time
  failure), but a confirmed codegen defect on a trivially common identifier.

### MS-12 [DEFECT, low] — SPEC drift on accepted syntax (compile-verified)

- SPEC §2.6 documents single-value array initialization `arr: [5]i32 = 0` as valid;
  the type checker rejects it (`Type mismatch: expected '[3]i32', got 'i32'` —
  reproduced with `arr: [3]i32 = 0`). SPEC §7.1's `first :: fn(arr: []$T) $T …
  arr[0]` shape is rejected by the safety pass (verified; SPEC flags it
  "planned/not backend-complete" but still shows it as example code). Writing a
  literal through a `ref usize` parameter (`v = 5`) is rejected because the
  implicit-deref trigger uses plain assignability without literal-fit logic
  (`type_checker.py:834-838`) — the SPEC §3.5 idiom only works when literal type
  matches the referent exactly (e.g. `ref i32`).
- Also observed: A7 array literals emit Zig tuples (`.{ … }`, `zig.py:1897-1901`),
  so runtime-indexed assignment/slicing of an *inferred*-type array literal fails to
  compile in Zig (`unable to resolve comptime value` / `slice of non-array type`) —
  accepted A7 programs that die at the external build step (robustness, not safety).

### Latent hazards [HYP] (recorded for the roadmap, no live path today)

- **LH-1:** `BackendPlan` keys are raw `id()` with no liveness guard
  (`safety.py:208-222`); preprocessor folding orphans nodes whose ids CPython may
  recycle. No current post-safety node creation is codegen-gated, so not currently
  exploitable — the invariant is accidental.
- **LH-2:** dead `GenericMonomorphizer` (`generics.py:121-243`) deep-copies ASTs and
  would carry no approvals/node types if wired in post-safety.
- **LH-3:** name-resolution ↔ type-checker scope pairing is positional
  (`type_checker.py:142-157`) with fallback define-into-current-scope masking
  mismatches (`:745-754`) — fragile under future traversal changes.
- **LH-4:** per-module name-resolution errors are discarded during module load
  (`module_resolver.py:162-166`); `--mode semantic` doesn't build the combined
  program, so imported bodies are unanalyzed in that mode (no Zig is emitted there).

### 4.1 Classification review — known gap vs defect (advisory confidence)

(Cited as §4.1 in docs/plan/research/memory-security-glm.md.)

Re-reviewed on coordinator request. Advisory confidence reflects the strength of
the compile-verified evidence plus whether a documented promise is actually broken.
"Incidental failures in other environments" play no role in these classifications,
and none of them depends on gate status.

| Finding | Class | Confidence | Basis |
| --- | --- | --- | --- |
| MS-1 stale-fact joins | **Undisclosed defect** | High | Breaks the SAFETY_CONTRACT *enforced* rows (index/slice/cast/div); compile-verified mis-discharge; no doc admits fact-join unsoundness |
| MS-2 call effects (nil staleness) | **Undisclosed defect** | High | Breaks the enforced "ref non-nil proof" row; compile-verified approved UAF-write lowering |
| MS-2 `del` through `ref` param | Defect with documented-gap overlap | Medium-high | Freeing caller storage is nowhere disclosed; overlaps STATUS.md's vague "full ref/del alias behavior … incomplete" |
| MS-3 alias double-`del` | **Documented gap** (confirmed silent acceptance) | High | STATUS.md explicitly defers full ref/del alias behavior; severity unchanged (double free), disclosure adequate, silence at usage sites is not |
| MS-4 `defer del` + explicit `del` | **Defect by silence** | Medium-high | No doc promises or denies the conflict; accepted program lowers to double destroy |
| MS-5 `del` on stack-aliasing ref param | **Defect by silence** (partial gap overlap) | High impact / medium-high class confidence | SPEC §8.4 says `del` is "validated for reference-like values"; nothing discloses that this can free stack storage |
| MS-6 union active-field | **Documented gap** (with SPEC-drift component) | High | SAFETY_CONTRACT marks it "active work"; SPEC §3.3 still shows unchecked reads without warning |
| MS-7 recursion bypasses (7a/7b) | **Undisclosed defect** | High | Breaks the explicit AGENTS.md/SPEC §6.2 ban promise; both emit recursive Zig |
| MS-8 stack-slice escape | Documented gap (broad) + silence (specific) | Medium-high | SPEC §8.4/STATUS defer lifetime analysis generally; returning stack slices specifically is accepted with no warning |
| MS-9 `undefined` defaults | **Defect by silence** (no promise broken) | Medium | No doc claims definite assignment; accepted programs emitting `undefined` is a language-quality defect |
| MS-10 overflow disabled | **Documented gap** | High | Explicitly disabled in code and documented |
| MS-11 `del p` capture shadow | **Defect** (codegen correctness) | High | A7 accepts; Zig stage rejects emitted text |
| MS-12 spec drift | **Verified drift** | High | Both directions compile-verified |

Advisory note: "documented gap" does not mean "acceptable" — it means the
repository's own status documents already acknowledge the missing enforcement, so
the finding's force is prioritization rather than disclosure failure.

### Positive controls — checks that do fire closed (compile-verified)

| Check | Evidence |
| --- | --- |
| Literal OOB index rejected | `repros/glm-memsafe-neg-index-oob.a7` → "index bounds are not proven" |
| Unknown-length slice indexing rejected (fail-closed) | `repros/glm-memsafe-neg-slice-index.a7` |
| Use-after-del (same binding) rejected | `repros/glm-memsafe-neg-use-after-del.a7` → USE_AFTER_MOVE |
| Compound `and` nil-guard fails closed | `repros/glm-memsafe-neg-compound-nil-guard.a7` |
| Guard-then-use nil idiom works (blessed path) | `examples/011_memory.a7` pattern; emitted `q.?.x` |
| Generic slice indexing rejected pre-codegen | `repros/glm-memsafe-generic-slice-index-rejected.a7` |
| `new [N]T` rejected | `type_checker.py:3005-3017` (code-verified; matches AGENTS.md) |
| Direct/mutual/local fn-ptr-alias recursion rejected | `test_semantic_functions.py` TestRecursionBan (strong suite) |
| Codegen fails closed without approval | `zig.py:1786-1795`; generic index rejected at semantic stage |

---

## 5. Compile-time guarantee vs Zig runtime check vs debug/release

(This table is cited as lines 502-517, 509 and 512 in docs/plan/research/memory/notes-h-audits-pdfs-current-memory.md. That file also cites lines 149, 187-192, 253, 319-320, 388-389, 579-587 and 753 of this report, by original numbering.)

| Operation | A7 compile-time proof | Emitted Zig | Debug/ReleaseSafe backstop | ReleaseFast reality |
| --- | --- | --- | --- | --- |
| Index `arr[i]` | interval ⊆ [0,len-1] (unsound under MS-1/MS-2) | raw `arr[i]` (`zig.py:1670-1686`) | bounds panic | **unchecked** |
| Slice `a[s..e]` | interval relation proof (unsound under MS-1/MS-2) | raw `a[s..e]` (`:1688-1694`) | bounds panic | **unchecked** |
| Ref field access / write-through | `non_nil` fact (stale across calls, MS-2) | `.?` / `.?.*` (`:1713-1749`) | null panic | **unchecked null deref** |
| Integer `+ - * <<` | none (MS-10 disabled) | plain ops (`:1586-1609`) | overflow panic | wrap/UB |
| `/` `%` | divisor nonzero (unsound under MS-1) | `@divTrunc`/`@rem` (`:1576-1585`) | div-by-zero panic | **unchecked** |
| `cast` | classification + range proof (unsound under MS-1) | `@intCast`/`@floatCast`/`@intFromFloat` (`:1751-1775`) | range panic | **unchecked truncation; `@intFromFloat` UB** |
| Union field read | none (MS-6) | plain `.field` | active-field panic | **type confusion UB** |
| `new` failure | maybe-nil; must be guarded before use | `catch null` (`:1903-1914`) | n/a | silent nil if proof stale |
| `del` | reference-typed operand only | `if (x) |p| destroy(p)` (`:1300-1306`) | page_allocator has no double-free/UAF detection in any mode | **invalid/double free** |
| Uninit struct/slice | none (MS-9) | `undefined` (`:2115-2141`) | UB on read in all modes | UB on read |

Bottom line: under the current lowering, **ReleaseFast correctness rests entirely on
the A7 static proofs**, and the two critical holes (MS-1, MS-2) mean release binaries
can perform unchecked OOB accesses and UAF writes that the compiler certified.

---

## 6. Test-suite assessment (false confidence)

Verified by test-inventory sub-agent with spot-checks; highlights:

- **Working well:** recursion-ban tests (direct/mutual/alias/higher-order, negative
  controls), error-stage matrix (pytest + script parity, 61/61), example e2e golden
  pipeline in Debug, tokenizer/parser volume.
- **Tautological tests (assert nothing):** `test/test_semantic_control_flow.py:1272`
  (`test_simple_defer`), `:1298` (`test_defer_outside_function_error`),
  `test/test_semantic_errors.py:302`, `:314` — `expect_error` results are only
  checked to be `bool`.
- **Diagnostics-only safety testing:** the semantic suites
  (`test_semantic_comprehensive|control_flow|errors|analysis.py`) do **not** run
  `SafetyProofPass`; "success" there says nothing about proof discharge. Emitted Zig
  for accepted safety-relevant programs is inspected in only ~3 places, one of which
  (`test_nil_to_null`) asserts merely `'null' in zig`.
- **No tests at all for:** `REF_NON_NIL` rejection (the message "reference may be
  nil" appears in no test), index/slice bounds-proof negative cases, double-del,
  del-on-ref-param, defer+del double deletion, union inactive-field reads, arithmetic
  overflow rejection, fact joins/loops/call invalidation. ReleaseFast is exercised by
  only two arithmetic pytest tests; memory-safety behavior under ReleaseFast has zero
  pytest coverage (full-suite release runs exist only in `run_all_tests.sh`).
- **Count inflation:** 445 of 1162 test functions (38%) are parser tests across 17
  overlapping files; `break`/`continue`-outside-loop is tested in four files; several
  parser tests still assert acceptance of banned legacy `.adr`/`.val` syntax
  (e.g. `test_parser_combinatorical.py:867-896`) — parsing-only acceptance that can
  drift from the documented public language.
- **Hidden skip:** `test/test_release_tooling.py:79-80` returns silently (counts as
  pass) when `zig` is absent.

---

## 7. Design decisions requiring agreement

Note (2026-09-16): decisions 3, 4 and 7 assume users keep manual `del`, `defer del`
and ref aliasing. Ledger L15, L17–L19 and L21 replace that direction with automatic
compile-time memory management; see the [memory plan](../../plan/memory.md). The
findings they respond to still stand. Decisions 6 and 9 remain open as gates G4
and G9 in the [v1 plan](../../plan/README.md).

1. **Fact-merge policy (blocks MS-1):** replace snapshot-restore with a real join —
   for every symbol assigned anywhere in a block/branch/loop body, the post-merge
   fact must be the union/widening of entry and exit facts (or top/unknown).
   Decide: statement-level fixpoint over the existing tree walk (minimal), or the
   CFG/fact/obligation split already prioritized in `docs/STATUS.md` item 4
   (architectural). Recommendation: tree-walk join now, CFG later.
2. **Call-effect model (blocks MS-2):** minimum conservative rule — any call
   invalidates facts (nil, interval, length) for every argument passed to a `ref`
   parameter and for every global. Decide whether to also model `del`-through-ref as
   a hard error (see 3) and whether interprocedural summaries are in scope for v1.
3. **`del` semantics** (cited as `memory-safety-glm-review.md:565-588` in
   docs/plan/research/memory/notes-h-audits-pdfs-current-memory.md; direction
   superseded, see the note above): (a) heap provenance — `del` must be legal only where the
   value *at that program point* provably flows from a `new`. A flow-insensitive
   "ever assigned from `new`" rule is **unsound** (the binding can later hold
   different storage — an alias copy, a `ref`-param source, a field read) and is
   explicitly not recommended. The conservative, path-valid shape: track
   per-binding provenance facts in the safety pass — `prov_new` immediately after a
   direct `new` assignment; dropped to *unknown* on any other assignment, on
   copy-in from another ref-typed expression, and merged by union at joins
   (`prov_new` survives a merge only if it holds on all paths, which in practice
   means it rarely survives and `del` becomes restricted to straight-line
   post-`new` uses unless the join rule is refined); `del` on *unknown* or
   param/field/index operands is a hard error. Whether to relax this with
   alias-set tracking is part of decision 4. (b) Emitted `del` should null the
   binding so post-`del` storage cannot be re-destroyed through the same name.
   (c) `defer del` should be modeled as **scheduled cleanup, not an immediate
   move**: reads of the binding before scope exit remain legal (the blessed
   `examples/011_memory.a7` idiom depends on this), and the compiler instead tracks
   pending scheduled deletions per binding and diagnoses conflicts — an explicit
   `del` of a binding with a pending scheduled deletion (MS-4), duplicate
   scheduled deletions of the same binding, and reads after the deletion point
   (which, being scope exit, are not textually reachable). The exact conflict
   granularity (per binding vs per allocation) is a design question tied to
   decision 4. These are consistent with SAFETY_CONTRACT's stated next ownership
   phase; the question is whether they land before or after the CFG work.
4. **Alias policy for refs (blocks MS-3)** (cited as
   `memory-safety-glm-review.md:589-594` in
   docs/plan/research/memory/notes-h-audits-pdfs-current-memory.md; direction
   superseded, see the note above): SAFETY_CONTRACT defers affine refs.
   Decide the interim rule: reject `q := p` copies of ref-typed values (breaking
   change), or diagnose only conflicting `del`s via a name-independent "allocation
   state" tracked per `new` site (needs the alias work), or document the hazard and
   gate `del` on provenance only (3a catches the double-destroy-through-two-names
   case only if the second `del` is on a non-`new`-sourced name).
5. **Union policy (blocks MS-6):** choose between (a) emit `union(enum)` tagged
   lowerings and require discriminant proofs (matches `edge-cases/01`/`02` research
   direction), (b) reject inactive-field reads at compile time via active-field
   facts, or (c) interim: hard error on *any* untagged union field read until (a)/(b)
   land. Also fix SPEC §3.3 to state current behavior.
6. **Recursion-ban scope (blocks MS-7):** agree that FIELD_ACCESS/INDEX callees
   resolved to function-typed values must create call-graph edges (requires type
   information in the validator or a post-typecheck pass), and that module-qualified
   calls count. Decide whether storable function pointers remain in the language at
   all given the ban (simplest sound option: function values may only be passed
   directly as arguments, never stored).
7. **Escape policy (blocks MS-8):** minimum viable rule — reject returning any
   slice/ref whose operand chain originates from a local of the returning function;
   reject storing auto-`&`-created refs into heap objects. Decide the real model
   per `lang-safety/parameter-modes.md` (regions vs borrow vs value semantics).
8. **Initialization policy (blocks MS-9):** decide which types have defined zero
   values (numerics/bool/string/pointers today) and require explicit
   initialization for all others (struct/union/slice/array-of-struct); emit no
   `undefined` from defaults ever.
9. **Release profile posture:** keep `-OReleaseFast` as the release profile with the
   lang-safety "safe by shape" test as the gate (honest but distant), or switch
   release artifacts to `-OReleaseSafe` until MS-1..MS-9 are closed (pragmatic;
   changes `scripts/build_examples.py:25` and archive names per AGENTS.md). This is
   a product-level decision the coordinator should put to the owner.
10. **Fix-in-passing agreements:** MS-11 capture-name fix (emit a fresh
    non-colliding capture or use the operand expression directly); SPEC drift items
    (MS-12); removal or quarantining of dead machinery (`GenericMonomorphizer`,
    `UNION_FIELD`, `initialized` fact, type-checker `_nonnegative_vars` dead system)
    so future work cannot mistake them for enforcement.

---

## 8. Regression-test specifications

(Sections 8 and 9 are cited as §8–§9 in docs/plan/research/memory/review/qwen.md.)

All specs are compile-only (no corruption payloads executed). "Rejection" means the
semantic stage fails with the quoted fragment; "acceptance" additionally inspects
emitted Zig. Suggested home: a new `test/test_memory_safety_proofs.py` wired like
`test_semantic_types.py` (includes `SafetyProofPass`) plus emitted-Zig assertions
like `test_codegen_zig.py`.

| ID | Source fixture (basis) | Expected result |
| --- | --- | --- |
| R-MS-1a | `glm-memsafe-join-stale-index.a7` | **Rejection** at Safety Proof: index bounds not provable (stale `[0,0]` must not discharge). Per the repository `AGENTS.md` "Test quality" rule this must land as a **visible red regression** for the agreed current requirement (SAFETY_CONTRACT's enforced index row) — no `xfail`/skip masking — and stay red until the join fix lands |
| R-MS-1b | same with `while` body mutation and with `match` arms | same |
| R-MS-2a | `glm-memsafe-call-del-stale-nil.a7` | **Rejection**: `del` through `ref` param (per decision 3a) or call invalidates `non_nil` so `q.x` errors "reference may be nil" |
| R-MS-2b | `wr(i)` writes through `ref usize`; then `arr[i]` | **Rejection**: index bounds not proven after call |
| R-MS-3 | `glm-memsafe-alias-double-del.a7` | **Rejection** (per chosen alias policy) — at minimum a diagnostic, never silent acceptance |
| R-MS-4 | `glm-memsafe-defer-del-double.a7` | **Rejection**: "binding is already deleted by a deferred del" (or emitted Zig contains exactly one destroy for the allocation) |
| R-MS-5 | `glm-memsafe-del-ref-param.a7` | **Rejection**: `del` requires a heap allocation from `new` |
| R-MS-6 | `glm-memsafe-union-inactive-field.a7` | **Rejection** or explicit per-policy diagnostic; today it must not pass silently |
| R-MS-7a | `glm-memsafe-recursion-struct-fnptr.a7` | **Rejection**: RECURSION_NOT_ALLOWED |
| R-MS-7b | `glm-memsafe-recursion-module/` (two files) | **Rejection**: cross-module mutual recursion detected |
| R-MS-7c | alias chain `g := f; h := g; h()` inside `f` | **Rejection** |
| R-MS-8 | `glm-memsafe-slice-stack-escape.a7` | **Rejection**: returning slice of local — or per interim decision a hard error on any local-sourced slice in return position |
| R-MS-9 | `glm-memsafe-uninit-struct-slice.a7` | **Rejection**: uninitialized struct/slice binding; emitted Zig contains no `undefined` from defaults |
| R-MS-11 | `glm-memsafe-del-var-named-p.a7` | Acceptance **and** `zig build-exe -fno-emit-bin` passes on emitted Zig (currently fails: capture shadow) |
| R-MS-12 | `arr: [3]i32 = 0` | Either implementation matches SPEC (accept) or SPEC fixed (reject documented) — one truth, asserted either way |
| Positive guards (keep green) | `glm-memsafe-neg-*` fixtures | current rejections stay rejections (anti-regression for fail-closed paths) |

Suite hygiene (decision-adjacent, recommended): delete or rewrite the four
tautological tests (Section 6); wire the semantic suites through `SafetyProofPass`;
add one ReleaseFast pytest that builds (does not run) each safety-relevant accepted
fixture with `-OReleaseFast` so lowering changes stay visible; un-hide the
`test_release_tooling.py` skip.

---

## 9. Ordered memory-safety qualification roadmap

Phase numbering is dependency-ordered, not calendar-ordered. Each phase is
independently shippable and ends with its R-tests green.

Note (2026-09-16): the `del` and alias remediation in Phases 1c and 2 is
superseded in direction by ledger L15, L17–L19 and L21 (see the
[memory plan](../../plan/memory.md)). Phase 6 is affected by L5 (integer `+`, `-`,
`*` wrap). The proof-soundness work in Phases 1a/1b, 3, 5 and 7 corresponds to
tracks 1 and 5 of the [v1 plan](../../plan/README.md).

- **Phase 0 — Hygiene and honesty (no semantics change).**
  Fix MS-11 (`del` capture shadow). Fix the four tautological tests; wire semantic
  suites through `SafetyProofPass`. Reconcile SPEC §2.6/§3.5/§7.1 with behavior
  (MS-12). Add the "positive guards" R-tests so existing fail-closed paths are
  pinned. Remove or quarantine dead machinery (LH-2, `UNION_FIELD`, `initialized`,
  `_nonnegative_vars`). Record MS-1..MS-9 as known issues in STATUS.md until fixed
  (currently only some are implied).
- **Phase 1 — Make the advertised proofs sound (stops the bleeding).**
  (a) Fact joins: statement-level merge/widen for symbols assigned in blocks,
  branches, loop bodies (MS-1). (b) Call effects: conservative invalidation for
  ref-passed args and globals (MS-2). (c) `del` discipline (cited as
  `memory-safety-glm-review.md:679-684` in
  docs/plan/research/memory/notes-h-audits-pdfs-current-memory.md): path-valid
  heap-provenance requirement (decision 3a), null-after-del emission, and
  scheduled-cleanup conflict tracking for `defer del` (decision 3c — reads before
  scope exit stay legal; only conflicts are diagnosed) (MS-4, MS-5).
  Deliverable: R-MS-1a/1b, R-MS-2a/2b, R-MS-4, R-MS-5 green as visible red-to-green
  regressions (no `xfail`); existing example
  suite still passes (no blessed idiom regresses — verify via
  `scripts/build_examples.py` debug+release).
- **Phase 2 — Deletion and alias closure.**
  Per new-ref-copy policy or allocation-state tracking, close alias double-del
  (MS-3, R-MS-3). Add `del` stage-matrix rows. This is the first slice of the
  SAFETY_CONTRACT "next ownership phase"; keep it minimal and documented.
- **Phase 3 — Recursion-ban completeness.**
  Type-informed call-graph edges for FIELD_ACCESS/INDEX callees, module-qualified
  calls, alias chains; decide storable-function-pointer policy (decision 6).
  R-MS-7a/7b/7c green; extend `TestRecursionBan`.
- **Phase 4 — Unions and escapes.**
  Tagged-union lowering or active-field facts (MS-6); slice-of-local return/store
  rejection (MS-8); auto-`&` escape rules. Update SPEC §3.3/§8 honestly at each
  step.
- **Phase 5 — Initialization and defaults.**
  Definite-assignment minimum per decision 8; eliminate `undefined` defaults
  (MS-9).
- **Phase 6 — Arithmetic.**
  Enable interval-based overflow proving behind the existing obligation plumbing
  (MS-10) or typed wrapping operators per `edge-cases/06`; until then keep the
  disabled state documented as a contract row, not a footnote.
- **Phase 7 — Qualification gate (ongoing).**
  (a) Contract-table test: one rejection + one accepted-and-emitted-Zig test per
  SAFETY_CONTRACT row. (b) Differential Debug/ReleaseFast corpus over all examples
  (extend `run_all_tests.sh`), zero-behavior-difference requirement. (c) The
  lang-safety §4.8.13 no-trap walk (`@panic`/`@trap`/`unreachable` scan of emitted
  Zig) as a script. (d) Small adversarial corpus (the `glm-memsafe-*` fixtures plus
  successors) compiled in both profiles. (e) Only then revisit the ReleaseFast
  posture (decision 9) and the lang-safety "safe by shape" claim.

---

## 10. Coverage matrix and reviewed-file inventory

### Coverage matrix (what this review examined, per area)

| Area | First-hand | Sub-agent | Fixture-verified | Not covered |
| --- | --- | --- | --- | --- |
| Safety facts & obligations (`safety.py`) | full read | cross-refs | joins (MS-1), calls (MS-2), del paths, guards, index/slice/cast rejections | exhaustive interval-arithmetic audit of `IntegerInterval` ops (read, not proven) |
| Type checker | targeted (assignment 827-901, var-decl 658-754, index rules 1677-1735, new 3005-3017) | full | ref-literal gap, uninit acceptance, array-init drift | full 3082-line line-by-line read |
| Semantic validator / name resolution / symbols | targeted (del 384-396) | full | recursion bypasses 7a/7b (via A7 compile) | none material |
| Zig backend | targeted (del/defer/assign 1250-1389, exprs/approvals 1650-1809, unions/vars 595-744, new 1895-1914, types/defaults 2075-2149) | full | emitted Zig for all MS repros; `zig build-exe -fno-emit-bin` re-qualification (initial ast-check/build-obj screening superseded) | full 2395-line read; io-helper internals; match/capture lowering details |
| Pipeline / preprocessor / generics / modules | gate region 340-409 | full | generic rejection, module recursion | none material |
| stdlib (`a7/stdlib/*`) | skimmed via agents | registry only | n/a | per-builtin Zig mapping audit (test_stdlib_registry covers shape) |
| Tests | spot | full inventory | n/a | execution of the suite (delegated to coordinator's gate) |
| Runtime behavior of defect programs | — | — | intentionally **not executed** | all runtime outcomes are inferred, not observed |

### Reviewed-file inventory

First-hand full read: `a7/safety.py` (737), `docs/SAFETY_CONTRACT.md`, `docs/SPEC.md`
(through §13), `docs/STATUS.md`, `docs/lang-safety/README.md`, `AGENTS.md`,
pre-audit diff. First-hand targeted reads: `a7/backends/zig.py` (regions above),
`a7/passes/type_checker.py`, `a7/passes/semantic_validator.py`, `a7/compile.py`,
`examples/011_memory.a7`, `examples/013_pointers.a7`. Sub-agent-read (reported with
line evidence, spot-checked against source where load-bearing):
`a7/passes/type_checker.py` (full), `a7/types.py`, `a7/cast_classifier.py`,
`a7/passes/semantic_validator.py`, `a7/passes/name_resolution.py`,
`a7/symbol_table.py`, `a7/semantic_context.py`, `a7/backends/zig.py` (full),
`a7/backends/base.py`, `a7/compile.py` (full), `a7/ast_preprocessor.py`,
`a7/generics.py`, `a7/module_resolver.py`, `a7/ast_nodes.py`, `scripts/build_examples.py`,
`test/` (42 files inventoried).

**This is not a claim of exhaustive verification.** The matrix above bounds what was
checked and how; sub-agent line references were trusted only where they aligned with
first-hand reads or compile-verified behavior.

### Artifacts produced

- This report: `docs/audits/2026-09-14/memory-safety-glm-review.md` (only file
  written outside `repros/`).
- 16 uniquely-named harmless fixtures under
  `docs/audits/2026-09-14/repros/glm-memsafe-*` (compile-only demonstrants and
  negative controls; none executed as binaries).
- Scratch fixtures and emitted Zig preserved under `/tmp/opencode/a7fix/`
  (temporary, outside the repository).

### Limitations

- **No runtime-safety claims.** No defect program was compiled to an executable or
  run (per instructions). Runtime outcomes (panics, silent corruption) are nowhere
  claimed as observed; where mentioned they are explicitly labeled as inferences
  from emitted-Zig semantics and Zig's documented Debug/ReleaseFast behavior.
  Compile-only evidence in this report — A7 acceptance, `build-exe -fno-emit-bin`
  semantic acceptance, emitted-text inspection, and absence of panic/trap strings —
  demonstrates only compiler acceptance and lowering shape. **No proof of runtime
  memory safety follows from any of those, and that shortcut is explicitly
  rejected.**
- Evidence-quality episode (recorded per protocol): the first pass qualified native
  lowering with `ast-check`/`build-obj`, which Zig's lazy analysis may not extend
  to unreferenced bodies; all headline fixtures were re-qualified with
  `build-exe -fno-emit-bin`. Observed Zig-stage *errors* from the first pass were
  real (AstGen/Sema errors surfaced from reachable code); only the *passes* were
  weaker than presented. The three initial sub-agent rate-limit failures were
  retried and completed; no evidence remains incomplete for that reason.
- The full test suite and release gate were not run (audit-only constraint); the
  coordinator runs them (current coordinator status: gate 11/12; pytest 12 failed /
  2515 passed / no skips on the configured toolchain — reported for context only;
  this review neither relies on nor disputes it).
- `IntegerInterval` arithmetic and the match/capture lowering were reviewed but not
  formally verified; additional lower-precision issues may exist there.
- Sibling audit reports were deliberately unread; overlapping findings with them are
  coincidental and unbeknownst to this reviewer.
