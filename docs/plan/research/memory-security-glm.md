> **Source:** OpenCode zai-coding-plan/glm-5.3, whole-language memory safety and security advisory. Nine lines of progress narration preceding the report heading were removed.  
> **Session:** `opencode session ses_f5e72fdbdffe69uM5qrarD64we`  
> **Date:** 2026-09-14. Recovered 2026-09-15 from temporary output after Plan Mode blocked the original write.  
> **Status:** Advisory. Body preserved verbatim except removal of pre-report narration where noted. User decisions are in the [ledger](../decisions.md).

# A7 Full-v1 Memory-Safety & Security Advisory — Whole-Language Review (GLM)

- **Reviewer:** Z.AI GLM, dedicated memory-safety and cybersecurity reviewer, independent reviewer of all language-feature design implications. Advisory only; the controlling Codex session is the primary coordinator.
- **Date:** 2026-09-14. **Mode:** read-only research; no repository files were modified, no vulnerability probing of external systems, no compiled memory-corruption payload executed.
- **Repository state audited:** commit `701c67936c70ad2b0608326e23e56cc5d38c9fdb` (identical to the 2026-09-14 audit baseline; verified via `git rev-parse HEAD`). Working tree carries only the previously-recorded docs/test additions.
- **Standing boundary:** A7 is **not a sandbox** (`docs/SECURITY.md`). Compiled programs run with host privileges; this report neither invents nor implies a sandbox promise. "Security" here means: soundness of what the compiler *certifies*, robustness of the compiler process and its artifacts, and honesty of the trust boundary.
- **Superseded-research handling:** current user directions override stale accepted research wherever they disagree. In particular, this report treats `docs/lang-safety/08-decisions.md` D.001–D.003 (arbitrary-precision `int`/`uint`/`number`), D.004, and the bignum-specialisation machinery as **superseded** by the explicit-width-integer direction; Cluster CC's mode keywords (`borrow`/`inout`/`consume`) as **not approved**; and D.049 (no storable references) as **not approved** (it conflicts with the accepted `ref`-struct-field surface). Nothing in this report silently resolves an unapproved language decision; each such point is an explicit approval question (§11).

---

## 1. Scope and method

Whole language and compiler, per mandate: spatial/temporal safety, initialization, object/provenance/alias model, ownership/moves/`del`/`defer`/allocation-failure cleanup, arenas/pools/containers and iteration invalidation, escaping refs/slices/closures/callbacks, exclusivity/effect inference, indirect recursion and native stack limits, mutable aliases across calls/branches/loops and optimization, tagged-union validity, checked size arithmetic despite defined ordinary wrapping, generics/comptime resource exhaustion, compiler malformed-input handling, concurrency (race freedom, ownership transfer, cancellation/join/channel closure/deadlock, partial failures), native ABI and resource handles, module/path resolution, output artifact safety, and build/dependency trust boundaries. Hardware/device/autograd lifetime concerns are stated as **design requirements**, never as implemented support. A sibling GLM run owns AI-tensor-specific boundaries; tensor topics appear here only where they impose whole-language requirements.

Method: first-hand reads of `README.md`, `docs/SPEC.md` (through §13), `docs/SAFETY_CONTRACT.md`, `docs/SECURITY.md`, `docs/STATUS.md`, `docs/lang-safety/08-decisions.md`; first-hand spot verification of the load-bearing safety/backend code paths (§3); two read-only sub-agents (13-point claim verification at HEAD including previously-uncovered formatter/stdlib/doc-generation surfaces; full digest of the `docs/lang-safety/` research base and HANDOFF); external research from primary sources (ledger in §12). Findings marked **[verified]** were confirmed by me at this HEAD (mine or prior-audit line references re-confirmed); **[attributed]** items rest on coordinator-recorded evidence I did not rerun.

---

## 2. Current-direction reconciliation (what v1 is being planned against)

Locked user directions relevant here:

1. **Explicit-width integer primitives** (`i8..i64`, `u8..u64`, `isize`, `usize`) with `usize` for sizes/lengths/capacities/indices. No arbitrary-precision `int`/`uint`/`number`.
2. **Defined wrapping** for ordinary integer `+`, `-`, `*`. (Wrapping is *defined*, not UB, not panic — this matches Zig's `+%`-family semantics as the emission target and is *stricter* than Rust release-mode behavior, which the Rust Reference documents as panic-in-debug with two's-complement wrapping conventions otherwise.)
3. **Scalar floats `f32`/`f64`; AI tensor dtypes `f16`/`bf16`/`f32`/`f64`.** IEEE-754 vs finite-only semantics are **not approved** — treated as open (§11 Q4).
4. **Argument bindings immutable; explicitly permitted referent mutation approved** (matches SPEC §6.3 today). **Mode syntax not approved.**
5. **Source recursion banned**; no public address-of/dereference operators (matches SPEC §3.5, SAFETY_CONTRACT "Reference Surface").
6. **Broad v1 scope:** ownership, concurrency, fuller stdlib, CPU AI training/inference with A7-owned tensor/autodiff and native numerical kernels. GPU/hardware research is separate and does not expand CPU v1 qualification.
7. Every syntax/behavior change needs before/after concrete A7 examples, compatibility impact, and user approval (§10/§11 follow this).

Consequences for the safety contract that follow from these directions and are *not* open questions: division/modulo and truncating casts remain proof-obligated (wrapping does not rescue `/ 0` or `@intFromFloat` UB); the bignum-promotion machinery and `uint - uint → int` widening (D.004) are void; narrowing (D.020) remains the discharge mechanism for obligations but now tracks explicit-width ranges only, which is materially simpler than the arbitrary-precision design it was written for.

---

## 3. Current evidence — verified state of the implementation

### 3.1 Confirmed soundness holes in the advertised proofs (highest priority)

These are the two defects that make the *currently enforced* SAFETY_CONTRACT rows unsound. I re-verified both at HEAD; line references are current.

- **MS-1 — unsound fact joins [verified].** `a7/safety.py:301-306`: block scopes do `saved = copy_symbols(); …; restore_symbols(saved)`; `restore_symbols` is a plain `by_symbol = saved` replacement (`a7/safety.py:170-174`). Any outer variable assigned inside a block/branch/loop body reverts to stale pre-block facts at exit; loop bodies are visited once with the same restore semantics (`:335-363`). Result: `arr[y]` after `if c { y = 5 }` is *proven* in-bounds from the stale `[0,0]` interval and emitted as raw `arr[y]` — an OOB write under `-OReleaseFast` (the release profile, `scripts/build_examples.py:25`). Same staleness defeats `slice`, `cast`-range, and nonzero-divisor proofs.
- **MS-2 — calls have no effects [verified].** `a7/safety.py:444-447`: CALL visits callee and args, invalidating nothing. A callee that `del`s through a `ref` parameter leaves the caller's `non_nil` proof intact, so `q.x = 1` after `kill(q)` is approved and emitted as a use-after-free write. Value-domain variant: any write through a `ref usize` argument invalidates no interval facts. Related: `del` emits no nulling store (`a7/backends/zig.py:1300-1306`).

### 3.2 Confirmed acceptance of memory-unsafe programs (documented-gap or defect-by-silence)

All re-confirmed at HEAD; classification per the corrected memory-safety review (`docs/audits/2026-09-14/memory-safety-glm-review.md` §4.1):

| ID | Hazard | Enforcement today | Key evidence |
| --- | --- | --- | --- |
| MS-3 | Alias double-`del` (`pp := new Pt; qq := pp; del pp; del qq`) | accepted silently | name-keyed moved set, `safety.py:724-726`; no points-to facts |
| MS-4 | `defer del p` + explicit `del p` → double destroy | accepted silently | defer branch deliberately skips move-marking, `safety.py:379-386`; no nulling, `zig.py:1306` |
| MS-5 | `del` on a `ref` param aliasing caller stack lvalue → `allocator.destroy(&stack_var)` | accepted silently | only check is reference-typedness, `semantic_validator.py:384-396`; auto-`&` at `zig.py:1661-1666` |
| MS-6 | Untagged-union inactive-field read → type confusion under ReleaseFast | accepted; `UNION_FIELD` obligation never constructed (`safety.py:184`); plain Zig `union` lowering (`zig.py:607-626`) |
| MS-7 | Recursion-ban bypasses: struct-field fn pointers, module-qualified calls, alias chains | ban enforced only for bare-IDENTIFIER callees (`semantic_validator.py:803-818`); emitted Zig is recursive for 7a/7b | breaks AGENTS.md/SPEC §6.2 promise |
| MS-8 | Returning slices of stack arrays | accepted; no escape analysis exists | `make :: fn() []i32 { ret buf[0..4] }` compiles, dangles in Debug and ReleaseFast |
| MS-9 | Uninitialized struct/slice bindings emit Zig `undefined` | accepted; `initialized` fact never read; `_default_value` returns `undefined` for struct/union/slice/unknown (`zig.py:2115-2141`) | UB on read in **all** Zig modes |
| MS-10 | Fixed-width overflow obligations disabled | `safety.py:631-636` unconditional `return` | **superseded direction:** defined wrapping for `+ - *` removes this hole for those operators; shifts, casts, div remain obligated (§6) |
| MS-11 | `del` of a variable named `p` emits capture-shadowing invalid Zig | A7 accepts; Zig stage fails | `zig.py:1306` fixed capture `\|p\|` |

### 3.3 What does work (positive controls — do not regress)

Pipeline fail-closed ordering gates codegen on the safety pass (`compile.py:346-382`, re-verified); `BackendPlan.require` fails closed in codegen (`zig.py:1786-1795`, re-verified); literal OOB index, unknown-length slice indexing, same-binding use-after-`del`, unguarded ref field access, compound-condition nil-guards, and generic-slice-indexing are rejected; `new [N]T` is rejected; direct/mutual/local-fn-ptr-alias recursion is rejected and well tested; cast classification with range proofs works; error-stage exit-code taxonomy (4/5/6/7/8) is real and subprocess-tested; `_convert_format_string` doubles every non-placeholder brace and `_quote_zig_string` escapes all control bytes, so user text cannot inject format directives into the generated `std.fmt` calls, and placeholder/arg arity mismatch fails closed at the Zig build (sub-agent-verified, `zig.py:2251-2303`, `type_checker.py:1437-1465`).

### 3.4 Findings new in this review (not in prior audits)

- **NEW-1 (P2) — `file_module_call` bypasses type checking entirely [verified].** `a7/passes/type_checker.py:1318-1321` returns `UNKNOWN` for cross-file module-qualified calls after visiting only the arguments — no name resolution, arity, or type validation — and `zig.py:1625-1629` emits `{prefix}{field}({args})` directly. Consequences: (a) typos and wrong arities in module APIs surface as Zig errors, not A7 diagnostics; (b) this is also how the MS-7b recursion bypass slips through; (c) any future memory-safety obligation inside such call arguments is unanalyzed. This is a *safe-API vs implementation-trust* hole: the module API is trusted, not checked.
- **NEW-2 (P3) — generated docs (--doc-out) are a content-injection sink [verified].** `a7/formatters/markdown_formatter.py` escapes only pipe characters in the token table (`:71`). Raw source lines sit in plain ``` fences (`:57-59`) that a source line containing ``` breaks; symbol names/types enter table cells unescaped (`:126`); error messages enter as raw list items (`:138`); `input_path` enters headers (`:28,51`). Malicious A7 source can inject arbitrary markdown/HTML into generated docs, which are then read as trusted repo artifacts. Same class as the site-build findings SEC-5 but in the compiler's own artifact path.
- **NEW-3 (P3) — console formatter interpolates source-derived error text into rich markup-parsed `console.print` without `rich.markup.escape` [verified].** Identifiers are ASCII-safe (tokenizer charset), but string-literal contents inside error messages can carry `[...]` sequences that rich mis-renders or raises on (`console_formatter.py:142-146` and passim). Terminal-output integrity issue only.
- **NEW-4 (Info) — JSON output is structurally safe.** All JSON emission goes through stdlib `json.dumps` (`compile.py:503,508,715`); no manual JSON string assembly exists anywhere in the package (exhaustive sub-agent sweep), so no source-controlled JSON-injection path exists. The only stdout pollution is the parser's 1000-declaration warning (H-3, prior pipeline review).
- **NEW-5 (Info) — process/exec/write surface is minimal and intended.** Whole-package sweep: zero `subprocess`/`os.system`/`eval`/`exec`; the only writes are the two intended artifact paths (`compile.py:441,471`) and their `makedirs` (`:440,470`), both inside IO-failure handling. No unexpected write or process surface exists in `a7/`.

### 3.5 Carried pipeline/security defects that remain open at HEAD

From the sibling reviews, all still true at this commit: parser match-statement live-lock (RB-1, `parser.py:2235-2261` — re-verified, needs a non-terminator stuck token); `--output`/`--doc-out` equal to input silently destroys source (RB-2, `compile.py:434-482`); output-path derivation `replace(".a7", ext)` rewriting directory components (SEC-7, `compile.py:850,457` — re-verified); parser recovery silently dropping `main` and reporting success (R5/F1); exact-integer folding precision loss through float division (R1, `ast_preprocessor.py:620-625`); exponential recursion-cycle search (RB-3, `semantic_validator.py:534-544`); dead circular-import detection with cache-before-guard (H-9/F4, `module_resolver.py:124-197` — re-verified, `topological_sort` has no caller); imported-diagnostic file attribution (H-8); semantic-vs-compile mode disagreement on module calls (H-8b); site preview traversal + non-loopback bind (SEC-1); pip-audit auditing the wrong environment (SEC-2); `setup-bun@v2` mutable tag and unpinned `uv` (SEC-3/4); secrets-scan gaps (SEC-12). Twelve deliberate red regression tests document the compiler-side items (`test_pipeline_*.py`).

### 3.6 Test-suite posture (no coverage illusion)

The semantic test suites do not run `SafetyProofPass`; emitted Zig for safety-relevant programs is inspected in ~3 places; there are zero tests for `REF_NON_NIL` rejection messages, bounds-proof negatives, double-`del`, `del`-on-ref-param, defer+`del` conflicts, union inactive reads, fact joins, or call invalidation; ReleaseFast memory behavior has zero pytest coverage; four tautological tests assert only `bool`; one Zig-gated test lacks a skip guard and another environment silently returns (prior reviews, §6). Passing the gate today is **observed-tests evidence, not logical-soundness evidence** — MS-1/MS-2 pass precisely because the proof engine's outputs are checked only on their face.

---

## 4. Threat model

**Assets:** (1) the validity of the compiler's certification (a compiled A7 program is as safe as its proofs are sound); (2) developer/host integrity during compilation (filesystem, subprocesses, terminal); (3) artifact integrity (generated Zig, generated docs, release archives, site); (4) future concurrent-program integrity (race freedom, resource cleanup on partial failure).

**Adversary classes and surfaces:**

| Surface | Adversary | Representative attack (evidence) | Class |
| --- | --- | --- | --- |
| A7 source authored to defeat proofs | trusted-ish author writing buggy/adversarial code accepted by the compiler | MS-1/MS-2 stale-fact discharges; MS-3..MS-9 acceptances; MS-7 recursion bypasses | soundness |
| Compiler process robustness (malformed input) | hostile source file | match live-lock (RB-1); 80k-deep parens → clean exit 8; superscript digit → exit-8 INTERNAL; unicode digits silently accepted; 1000-decl cap + stdout pollution | availability/diagnostics |
| Output/artifact paths | user mistake or hostile project layout | `-o` overwrites source (RB-2); `.a7` in directory names redirects output (SEC-7); failed compile advertises stale output; directory-as-artifact | data integrity |
| Generated-artifact consumers | reader of generated docs/HTML | NEW-2 markdown injection; site-build sinks (SEC-5/6) | injection |
| Terminal/automation | source-controlled error text | NEW-3 rich markup; H-3 stdout pollution breaking `--format json` | automation integrity |
| Import/module resolution | hostile checked-out module | traversal/`..`/absolute rejected [verified]; symlink escape rejected; but module identity is the import *string* (dual-spelling double-merge), visibility (`pub`) unenforced (F6), module calls untypechecked (NEW-1), cycle semantics accidental | trust boundary |
| Build/dependency pipeline | upstream compromise | SEC-2 pip-audit wrong target; SEC-3/4 unpinned action/tool; otherwise: pinned Zig URL+SHA, least-privilege permissions, attested two-job release [verified prior] | supply chain |
| Compiled program vs host | anyone running a compiled binary | **out of scope by design**: not a sandbox; programs run with host privileges | accepted model |
| Future concurrency | buggy concurrent program | data races through shared refs; leaks on task cancellation; use-after-close on channels; unbounded task stacks | design (§6.9) |

Explicitly *not* treated as attacks: compiled-program escape (documented model), and anything requiring us to claim rejection of every runtime failure — see feasibility table in §7.

---

## 5. Object/provenance/alias model — what the language currently is

Established facts that any v1 ownership design must start from (all verified): `ref T` lowers to Zig `?*T` (nullable by default, `zig.py:2100-2104`); `ref` arguments accept arbitrary lvalues with compiler-inserted `&` (`zig.py:1661-1666`) — so `ref` params conflate *heap references* and *borrowed stack slots*; `ref` struct fields exist in the accepted surface (SPEC §3.3/§3.5); `new` returns a maybe-nil ref that must be guarded; `del` requires only reference-typedness; copies of ref-typed values are unrestricted (`qq := pp`); no points-to, alias, or escape analysis exists anywhere; there is no address-of/deref syntax, no pointer arithmetic, no `int→ptr` cast path in the *enforced* cast classifier (but see the D.024/D.038 contradiction, §11 Q2 — the audit's `cast(ref T, integer)` hole must be re-checked once the cast surface is decided).

**The core unresolved design question** (approval-gated, §11 Q1): is `ref` (a) an *owning* heap reference (affine, `del`-able), (b) a *borrowed* view of arbitrary storage (never `del`-able), or (c) both, conflated as today? MS-5 is the direct product of (c): `del` on a `ref` param destroys caller *stack* storage. The provenance invariant in §6.2 resolves this without new syntax.

---

## 6. Proposed invariants (v1 target state)

Each invariant states: requirement, enforcement point, and what it deliberately does *not* claim. Numbering is stable for cross-reference.

### Spatial safety
- **I-1 (Index/slice bounds).** Every `a[i]`/`a[s..e]` either has a compile-time proof `0 ≤ i < len` (resp. `0 ≤ s ≤ e ≤ len`) from a *sound* fact lattice, or does not compile; the fallback is a typed `get(i) -> ?T`. Enforcement: obligation discharge in the proof pass; **soundness prerequisites:** I-10 (joins) and I-11 (call effects). Does not claim: rejection is impossible to bypass by FFI memory corruption (environmental).
- **I-2 (Pointer arithmetic).** No public pointer arithmetic exists (current surface). Keep as invariant; any future offset op becomes a proof-obligated operation returning a typed value on failure.

### Temporal safety
- **I-3 (`del` heap provenance).** `del x` compiles only when the value at that program point provably flows from `new` on every path (path-sensitive provenance fact: `prov_new` right after `new`; degraded to *unknown* on any other assignment, copy-in, or merge-by-union at joins; `del` on *unknown*, params, fields, or index results is a hard error). Emitted `del` nulls the binding. This closes MS-5 and halves MS-3 without new syntax. Tradeoff: `del` becomes restricted to straight-line post-`new` code unless alias work lands (acceptable; auto-drop I-5 covers the common path). A flow-insensitive "ever assigned from `new`" rule is unsound and must not ship (withdrawn suggestion, prior review correction note).
- **I-4 (No use-after-`del`, no double-`del`).** Same-binding enforcement exists today; extend to scheduled deletions: `defer del` records a *pending scheduled deletion* (reads before scope exit stay legal — the blessed `examples/011_memory.a7` idiom), and an explicit `del` of a binding with a pending deletion, or duplicate scheduled deletions, are compile errors. Closes MS-4.
- **I-5 (Affine heap refs + auto-drop).** Heap refs (post-I-3 definition) are affine: passing to a consuming position, `del`, or move-out marks the binding consumed; re-use is a compile error; scope exit auto-emits `del` for live non-`Copy` bindings in reverse declaration order; explicit `defer del` suppresses the auto-drop for that binding. This is the SAFETY_CONTRACT "next ownership phase" expressed without new syntax. **Aliasing policy remains the hard part** — see Q1: minimal sound option for v1 is *reject ref-typed copies* (`qq := pp` where `pp: ref T` is a compile error; share via `ref` params instead), which closes MS-3 statically. This is a breaking change to currently-accepted code (compatibility impact in §10).
- **I-6 (No stack-escape).** Reject returning any slice/ref whose operand chain originates from a local (or `ref` parameter) of the returning function; reject storing auto-`&`-created param refs into heap objects. Minimum viable escape rule (prior review decision 7). Long-term model per Q1 (regions vs modes vs value semantics).

### Initialization
- **I-7 (Definite assignment; no `undefined` defaults ever).** Numerics/bool/`string`/pointers keep defined zero values (documented); struct/union/slice/array-of-struct bindings require explicit initialization or full assignment before any read; the backend never emits `undefined` from default-value synthesis (`zig.py:2115-2141` fall-through removed). Closes MS-9.

### Union validity
- **I-8 (Tagged unions for public surface).** Public sum types lower to Zig tagged unions (`union(enum)`); inactive-payload access requires a proven discriminant (match-arm or guard narrowing); untagged unions are either removed from the public surface (breaking; SPEC §3.3 rewrite) or restricted to FFI scope with `bit_cast`-style named helpers only. Interim: hard error on any untagged-union field read until the decision lands. Closes MS-6.

### Arithmetic
- **I-9 (Defined wrapping ordinary arithmetic + checked size-critical arithmetic).** Ordinary `+ - *` on explicit-width ints wrap (defined semantics; emit Zig wrapping ops `%+ %- %*` so the definedness is real, not accidental); `<< >>` widening shifts remain proof-obligated (shift-amount UB in Zig); division/modulo keep the nonzero-divisor proof; narrowing casts keep range proofs; **size-critical contexts** — allocation byte counts, slice/array lengths, offsets, capacities — must be computed with proven-in-range or explicitly checked/saturating operations even though ordinary arithmetic wraps, and must be `usize` per the locked direction. Float→int casts are always range-checked (Zig `@intFromFloat` is UB out of range); int→float is total. NaN policy is open (Q4) but any narrowing-fact machinery must treat float comparisons as non-facts until semantics are decided.

### Proof-engine soundness (compiler)
- **I-10 (Real joins).** Replace snapshot-restore with union/widen (or ⊤) for every symbol assigned anywhere in a block/branch/loop body; loop bodies checked under the join of pre/post facts. Tree-walk join now; CFG architecture later (matches STATUS priority 4 and HANDOFF §8's pass split).
- **I-11 (Call effects).** Minimum conservative rule: any call invalidates nil/interval/length facts for every argument passed to a `ref` parameter and for every global. Optional later: interprocedural summaries (only as *refinement*, never as *relaxation*, of the conservative rule). Closes MS-2.
- **I-12 (Proof preservation under transformation).** Approvals stay keyed to nodes; but the incidental safety of "post-safety passes only replace UNARY/BINARY with LITERALs" must become a structural invariant: no pass after the proof stage may create nodes of gated kinds; approval keys gain a pass-version guard so `id()` reuse can never grant a fabricated approval (LH-1). The dead `GenericMonomorphizer` (`generics.py:121`, no importer — re-verified) and broken `generic_visit` (`backends/base.py:44-47`, nonexistent `node.children` — re-verified) are quarantined/removed so they cannot bypass proofs by construction (LH-2).
- **I-13 (Recursion-ban completeness).** Call-graph edges are built with type information: FIELD_ACCESS/INDEX callees resolving to function-typed values create edges; module-qualified calls create edges (requires NEW-1 fix so those calls are resolved at all); alias chains are modeled to fixed point. Policy decision (Q5): whether storable function values remain — simplest sound option is function values only as direct call arguments, never stored in fields/globals. Recursion-cycle detection itself must be SCC-based (RB-3: current DFS is ~4× growth per +2 functions).
- **I-14 (Stack budget).** With recursion banned and the call graph a DAG (after I-13), compile-time maximum stack depth is computable. v1 requirement: compute it, assert a configured budget at compile time, and set the main/task stack accordingly (`RLIMIT_STACK`/thread attr per the research base, 05-for-a7 §4.8.11). Honest limit: this bounds *A7-emitted* frames, not environment-imposed limits (thread stack caps, guard-page granularity) — those are environmental impossibilities (§7).
- **I-15 (Compiler input robustness).** Every malformed-input class terminates with a classified, spanned diagnostic: match-statement else-raise (RB-1), expression-depth limit with clean error (H-2), ASCII-digit gating (H-10), enforced-or-deleted `MAX_STRING_LENGTH` (M-3), declaration cap as real error with stderr/structured warning (H-3), imported ParseError as parse-category with origin span (R2), parser recovery that drops declarations fails compilation (R5). Resource-exhaustion posture: bounded-cost claims must come from bounded algorithms (SCC, linear scans), not from observed fast exits.

### Exclusivity / aliasing during optimization
- **I-16 (Exclusivity contract).** Whatever surface is approved (Q1), the invariant is: *while a referent is being mutated through one path, no other path may access it*, enforced **compile-time only** (this is deliberately stronger than Swift's production model, which falls back to dynamic checks — SE-0176; the A7 contract has no runtime fallback slot). Today's compiler both (a) permits mutable aliases silently and (b) emits raw `arr[i]`/`.?`/plain ops that Zig's optimizer may treat as noalias — an aliasing-model mismatch that is *itself* a miscompilation risk once LLVM/Zig reason about it. Two consistent options: (a') approve call-site exclusivity (two mutating refs to overlapping storage at one call = error; mutable+shared overlap = error; proved-distinct indices allowed), Hylo-style; or (b') forbid storing/forwarding mutable refs entirely outside parameter position. Both need Q1 first.
- **I-17 (Immutable ≠ noalias — explicit).** Parameter-binding immutability (locked direction) means the *binding* cannot be reassigned; it says nothing about aliasing: an immutable `[]T` param may alias a mutable one, and Odin's ability to pass big params by immutable reference relies on exactly this discipline (Odin FAQ: "procedure parameters are immutable values… allows Odin to optimize how procedure values are passed"). The compiler must not lower immutable params as `noalias` unless an approved exclusivity model holds, and must not treat referent immutability as a fact narrower than the binding rule. This distinction must also be stated in SPEC so users don't infer Rust-`&T`-style aliasing guarantees that A7 does not provide.

### Concurrency (v1 design target — channels + isolated owned data per the research base; all approval-gated surface)
- **I-18 (Race freedom by construction).** Cross-task data crosses by move only (ownership transfer on `send`); no borrow/mutate through task boundaries; no shared mutable state; with I-5, the type system must make it impossible to form a cross-task alias (this is why ref-copy rejection matters before concurrency ships). Does not claim: race freedom against FFI-shared memory or environmental shared mappings (impossibility class).
- **I-19 (Channel lifecycle).** `recv` on closed/empty channel is a *typed* result (`?T` / terminated iteration), never a trap; `send` on closed channel is a typed failure; double-`close` is a compile error via the same affine treatment as `del` (channel handles are owning resources). Un-buffered/`select` semantics are v2 (research base defers `select`).
- **I-20 (Task lifecycle & partial failure).** Spawn requires a callee whose stack budget is computed (I-14 per task); join is the only default way to observe task completion; leaked tasks without join are diagnosed like leaked heap refs at scope exit where statically detectable. Cancellation is **deferred to v2** (research base) — v1 must *document* that an unjoined task outliving its spawner's arena/region is a compile error under the region/move model, not a runtime cleanup promise.
- **I-21 (Deadlock honesty).** Deadlock freedom is **not** claimed for v1 (needs session types or equivalent); the contract documents deadlock as an unhandled hazard of channel cycles, with a join-structure discipline recommended. Promising deadlock freedom would violate the no-overclaim rule.

### ABI / resource handles / FFI (design requirements)
- **I-22 (FFI boundary shape).** `extern fn` declarations use explicit-width types (locked direction); return values are declared `?T`/`Result<T,E>` per the foreign contract; extern memory is never freed by A7 `del` (provenance I-3 forbids it); extern-acquired handles are opaque move-only types. Hardware/device buffers and accelerator streams are, from the CPU v1 language's perspective, exactly this class: **design requirement** — tensors owning device memory must be affine with explicit sync/copy points, and autograd graph nodes must be heap objects under I-5's drop discipline, with per-step scratch allocated from arenas (I-23). None of this is implemented; it constrains the ownership model now so the AI stack cannot build on borrowed-stack escapes.

### Containers/arenas
- **I-23 (Arenas/pools as stdlib ownership types).** Arena and pool allocators enter as explicit stdlib resource types (Odin-style context allocators are the comparison point): arena-reset invalidates everything allocated from it, so the type system must tie slice/ref *provenance* to the arena lifetime — minimum v1 shape: arena-allocated storage may not escape the arena's scope (extends I-6), and iteration invalidation is rejected by exclusivity: while a mutable iteration borrows a container, no mutation call on the same container typechecks (I-16 applied to receiver positions). Fuller stdlib containers (dynamic arrays, maps, `Channel<T>`) are owning types: mutation invalidates outstanding borrows per the same rule.

### Modules / artifacts / pipeline trust
- **I-24 (Module identity and checking).** Canonical file identity (not import string) keys module dedup (closes dual-spelling double-merge, F8); cycle policy is *decided* (reject or support) rather than accidental (dead guard removed or fixed, H-9); `pub` enforced at the reference boundary while retaining internally-referenced private declarations; module-qualified calls are fully type-checked (closes NEW-1, prerequisite of I-13); imported diagnostics carry origin file/spans (H-8) and semantic mode performs the same module combining as codegen.
- **I-25 (Output artifact safety).** Output/doc-output paths are rejected when they resolve to the input (RB-2); output derivation uses suffix-only replacement (SEC-7); failed compiles never advertise artifacts, and directories are never reported as artifacts; generated markdown escapes source-derived text or renders it in non-fence-escaping form (NEW-2); warnings go to stderr and are structured in JSON mode (H-3); console rendering escapes rich markup in source-derived text (NEW-3).
- **I-26 (Supply chain).** pip-audit targets the locked project resolution with a CI inventory assertion (SEC-2); `setup-bun` and `uv` pinned to immutable refs (SEC-3/4); `.env*` gitignored (SEC-12). These remain release-gate blockers per the roadmap.

---

## 7. Compile-time rejection vs runtime error vs environmental impossibility (feasibility table)

The mandate forbids claiming every runtime failure is rejectable. Classification of every hazard A7 v1 faces:

| Hazard | Disposition | Rationale / precedent |
| --- | --- | --- |
| Index/slice OOB | compile-time proof or typed `?T` | SPARK-tier discipline; enforced today (unsoundly — I-10/I-11 fix the engine) |
| Division by zero, `INT_MIN / -1` | compile-time proof or typed checked op | Rust: always panics (Reference: checks occur even with overflow-checks off); A7 raises to compile-time instead |
| Integer overflow `+ - *` | **defined wrapping** (locked direction); checked/widening ops available | removes the failure mode rather than rejecting it |
| Null deref | compile-time via non-null proof / guard narrowing | current `non_nil` facts, post-I-11 sound |
| Use-after-free / double-free / leak | compile-time via affine ownership + provenance + auto-drop | Rust `Drop`; Hylo modes; I-3..I-6 |
| Uninitialized read | compile-time definite assignment | Zig requires initializers; A7 must stop emitting `undefined` (I-7) |
| Union wrong-variant read | compile-time discriminant proof or tagged lowering | Zig tagged `switch` exhaustiveness |
| Cast truncation / float→int range | compile-time range proof or typed checked op | `@intFromFloat` UB makes this mandatory |
| Stack exhaustion via recursion | **compile-time**: recursion banned + DAG stack budget (I-13/I-14) | unique to A7's no-recursion design |
| Allocation failure (`new`) | **runtime, typed**: `?ref T` (already the surface) | cannot be prevented; must be handled; cleanup-on-failure via defer/auto-drop ordering |
| OOM-kill, environment memory exhaustion | **environmental impossibility** | only bounded/mitigated, never prevented |
| I/O errors, parse-of-external-input failures | runtime, typed `?T`/`Result` | data-dependent by nature (compile-time-knowledge tier 3, research base) |
| Deadlock (channel cycles) | **not prevented in v1** (I-21) | would need session types; documented hazard |
| Data race through FFI/shared foreign memory | **environmental impossibility** for A7's type system | documented boundary |
| Host compromise by a compiled program | **accepted model** (not a sandbox) | docs/SECURITY.md |
| Task cancellation cleanup | deferred v2 (documented) | research base defers async cancellation |

The **logical-soundness vs observed-tests** distinction: nothing in the left column is delivered by the current test suite; MS-1/MS-2 demonstrate that green gates plus well-formed obligation *plumbing* still constitute an unsound prover. Soundness arguments must rest on the fact-lattice semantics (joins, invalidation, provenance merges) being specified and adversarially tested, not on example throughput.

---

## 8. Comparative contracts (authoritative sources)

| Language | Compile-time contract | Runtime-checked | Unchecked / explicit-unsafe | Notably absent | Lesson for A7 |
| --- | --- | --- | --- | --- | --- |
| **Rust** (Reference, "Operator expressions": shared borrow freezes the place; `&mut` exclusive; overflow panics in debug, two's-complement wrap otherwise; `INT_MIN/-1` and shift-overflow checked even with overflow-checks off; `as` truncates silently) | affine ownership + aliasing exclusivity (`&T` freeze / `&mut T` exclusivity), `Send`/`Sync`, definite assignment, non-null references | index panic, div panic, debug overflow; release wrap | `unsafe`, `as` truncation/ptr↔int | stack budget (recursion allowed), refinement ranges | the aliasing-exclusivity *invariant* (I-16/I-17) is the load-bearing idea; Rust's lifetime annotations are the cost A7's parameter-mode alternative tries to avoid |
| **Swift** (SE-0176 "Enforce Exclusive Access to Memory"; Swift 5 exclusivity blog 2019; SE-0458 strict-memory-safety draft) | definite assignment; parameter conventions (`borrowing`/`consuming`/`inout`); noncopyable types (SE-0390) | **Law of Exclusivity enforced statically *where possible, dynamically otherwise*** — traps on overlap; arithmetic/subscript/force-unwrap traps | `unsafe` pointer APIs; SE-0458 proposes *opt-in strictness* rather than an always-on guarantee | stack budget; ranges | the largest production deployment of exclusivity-without-lifetimes still needed a runtime fallback; A7's compile-time-only stance (I-16) is more aggressive and must therefore be more conservative about what programs it accepts |
| **Zig 0.16** (Language Reference: `undefined` = "using this value would be a bug"; Illegal Behavior catalog; Build Modes) | `!T` error unions mandatory at every fallible op; no implicit numeric conversions; `comptime` | Illegal Behavior (OOB, overflow, div, `.?`, `@intCast`, wrong union field, alignment) panics in Debug/ReleaseSafe, **is UB in ReleaseFast/ReleaseSmall** | manual allocator aliasing discipline; `undefined` opt-in | any ownership/aliasing analysis; stack budget | A7's backend: every A7 proof gap becomes UB exactly in the release profile; the emission discipline (wrapping ops, tagged unions, no `undefined`, no `.?` without proof) is the entire safety story under ReleaseFast |
| **Odin** (FAQ: "procedure parameters are immutable values", enabling by-value/by-immutable-ref lowering choice; zero-value initialization default with `---` opt-out; no ownership semantics; no pointer arithmetic; custom allocators/arenas via context) | parameter immutability; explicit conversions; zero-init | bounds checks toggleable per statement (`#no_bounds_check`) | raw pointers freely storable; aliasing unchecked | aliasing/exclusivity analysis; lifetime tracking | the ergonomic template for A7's *locked* immutable-bindings direction — and the demonstration that immutability alone buys noalias nothing without a stated aliasing model (I-17) |
| **Go** (race detector docs; memory model) | nothing about aliasing/mutability; nil-map/slice-op behaviors defined | data race = undefined per memory model; race detector is dynamic, test-time only | everything shared; `unsafe` package | any static exclusivity | the anti-model: channels exist but shared memory races remain defined-undefined; A7's move-only channels (I-18) are the deliberate counter-design |
| **C++** (Core Guidelines; Clang lifetime-profile implementation work; "Why Safety Profiles Failed" retrospective) | profiles (type/bounds/lifetime) are advisory lint layers over an unsafe core; lifetime profile needs annotations (`_Owner`, `_Ptr`) and remains incomplete for real codebases | UBSan/ASan families as debug instruments (research base doc 02) | everything | a sound default | the cautionary tale: retrofitting lifetime safety onto a permissive aliasing core stalled; A7 must fix the alias model *before* the ecosystem grows |
| **Research: regions/affine/effects** | Cyclone (Grossman et al. POPL 2002; Swamy et al. SCP 2006): region type-and-effect system, safe manual memory without GC — the proven ancestor of I-23's arena-tied provenance; Tofte/Talpin region inference (POPL 1994); Crary et al. capability calculus (ICFP 1999) | | | | regions are the highest-leverage *optional* phase-2 add-on if parameter-mode discipline leaves gaps (exactly Cyclone's history: added on top of an existing safe core) |
| **Pony** (ponylang.io: "capabilities-secure, actor-model") | reference-capability lattice (`iso`/`val`/`ref`/`box`/`tag`/`trn`) proves data-race freedom compile-time; ORCA GC for cycles | | | | ref-caps are the maximal version of I-18; A7's channel-moves model deliberately takes the simpler Inko/Hylo subset and pays with no shared-immutable across tasks |
| **Koka/Perceus** (Reinking et al., PLDI 2021) | precise RC with reuse analysis; functional; borrowing elision | | | | evidence that "ownership without borrow checker" is implementable; Perceus-style drop-timing analysis is the eventual optimization for I-5's auto-drop |
| **Verona / Hylo / Inko / Dala / Tree Borrows / Dynamic Region Ownership (Stoldt et al., PACMPL 2025)** | Verona: regions as concurrent-ownership units; Hylo: references-as-parameter-modes + call-site exclusivity (A7's primary template per research base); Inko: isolated per-thread heaps + channels; Dala (arXiv:2109.07541): core-local heap areas/capabilities for a dynamic language; Tree Borrows (PLDI 2025): the current frontier formalizing Rust's aliasing semantics; Dynamic Region Ownership (2025): runtime-checked region discipline for concurrency | | | | confirms A7's chosen design point (modes + channels + optional regions) is well inside the established space, and that aliasing models need *some* enforcement point — static (A7 goal), dynamic (Swift/DRO), or capability-structural (Pony) |

**The four distinctions the mandate requires, stated once, sharply:**

1. **Immutability vs noalias.** An immutable binding may still alias mutable storage; only an exclusivity model (or capability lattice) makes aliasing guarantees. Odin exploits immutability for *calling-convention* freedom, not for aliasing soundness. A7 SPEC text must never imply `&T`-Rust-style freeze semantics unless I-16 is approved.
2. **Ownership vs readonly.** Ownership is the right and duty to destroy (affine use, auto-drop, `del`); readonly is an access restriction that can coexist with many aliases. `ref T` today is readonly-ish with accidental destroy rights (MS-5); I-3/I-5 separate them.
3. **Safe APIs vs implementation trust.** A safe API is one whose *contract* is enforced at a boundary the compiler controls (`BackendPlan.require`, typed channel ops); implementation trust is assuming the callee/module behaves (NEW-1's untypechecked module calls, stdlib surface). The file-module hole shows how quickly API safety degrades into trust when a resolution path skips checking.
4. **Logical soundness vs observed tests.** Soundness is a property of the proof rules (join semilattice, invalidation monotonicity, provenance merge); tests sample it. MS-1/MS-2 passed every gate. The v1 qualification must include adversarial proof-engine tests (§9) and, ideally, a written fact-lattice semantics note that the tests are derived from.

---

## 9. Security-focused test and recovery scenarios

All tests verify independently stated observable requirements; no mocks at any compiler boundary; known-defect regressions stay visibly red until fixed (AGENTS.md rule; `xfail` withdrawn per prior correction). Suggested home: extend `test/test_memory_safety_proofs.py` (SafetyProofPass-inclusive, like `test_semantic_types.py`) plus emitted-Zig assertions like `test_codegen_zig.py`, plus real-CLI/real-file tests like `test_pipeline_*.py`.

**Proof-engine adversarial suite (derives from fact-lattice semantics, not implementation mirror):**
- T1 join-widening: `y` reassigned in `if`/`while`/`match` arm; `arr[y]` after → rejection "bounds not provable" (positive control: bounded reassignment proven when join is expressible).
- T2 call-effects: `wr(i)` through `ref usize` then `arr[i]` → rejection; `kill(q)` then `q.x` → rejection (or `del`-provenance error per I-3).
- T3 provenance: `del` on `ref` param → rejection; `del` after non-`new` assignment → rejection; `del` on all-`new` paths → acceptance with nulling emitted.
- T4 defer conflicts: `defer del p; del p` → rejection; `defer del p` + read → acceptance (blessed idiom regression).
- T5 alias policy per approved option: ref-copy rejection (or allocation-state diagnostics).
- T6 escape: return of local-sourced slice/ref → rejection; `for v in container { container.push(..) }`-shaped iteration invalidation → rejection once containers exist.
- T7 untagged unions: inactive-field read → rejection or tagged lowering with exhaustiveness.
- T8 definite assignment: uninit struct/slice read → rejection; emitted Zig contains no `undefined` from defaults (textual scan is *permitted* here because it asserts an independently stated emission property).
- T9 wrapping vs checked: `u8` `255 + 1` wraps to 0 (native run, both profiles, golden value); `usize` allocation-size overflow → rejection or typed checked-op result; `@intFromFloat` range check tested at both profile extremes.
- T10 recursion completeness: struct-field fn-pointer cycle, module-qualified mutual recursion, alias chains → RECURSION_NOT_ALLOWED; fan-in DAG of 60 functions completes in bounded time (kills RB-3 class).
- T11 proof preservation: constant-folding and any new post-safety pass leave approvals intact (structural: gated-node creation post-safety fails a debug assertion).

**Concurrency suite (post-approval, native):** move-on-send (sender's binding unusable), recv-on-closed = typed nil iteration, send-on-closed = typed error, double-close = compile error, spawn-of-over-budget-stack = compile error, unjoined owning-task diagnostic; differential Debug/ReleaseFast output equality on all channel programs; documented-not-prevented: deadlock corpus compiles and is expected to hang in CI only under an explicit timeout-marked acknowledgment test (or is excluded with the hazard documented — a policy choice, not a silent omission).

**Recovery scenarios (partial failure paths, native):** allocation failure mid-initialization (`new` returns nil after partial struct init → no leak under auto-drop ordering); error propagation with `defer` cleanup ordering (LIFO with pending scheduled deletions); module import failure mid-program (no partial Zig written, no stale artifact advertised); failed compile leaves source bytes untouched (RB-2 regression, already red); stack-budget violation rejected at compile time rather than trapping at runtime.

**Pipeline/artifact suite (extends the red tests):** output-derivation with `.a7` directory components (SEC-7); `--doc-out` content-injection canary (docs from a fixture containing ``` fences, pipe-laden identifiers, and markdown-in-string-literals must render inert — asserts escaping, not implementation); JSON mode purity under parser warnings; rich-markup canary in console errors; module identity via canonical path (same file imported two ways merges once); `pub` enforcement with private-internal retention; module-call arity/type errors surface as A7 diagnostics (NEW-1).

---

## 10. Design alternatives and tradeoffs (approval-gated, with before/after)

**Q1 — Reference/ownership surface (blocks MS-3/MS-5/MS-8 and gates I-3..I-6, I-16..I-18).** Options:

- **(a) Minimal, syntax-free (recommended first step):** keep today's surface; add provenance (I-3), scheduled-del conflicts (I-4), affine `ref` + auto-drop (I-5), escape rule (I-6), and *reject ref-typed copies*. Before/after:

```a7
# Before (accepted today; double free at runtime)
p := new Pt
q := p
del p
del q

# After (option a): compile error on `q := p` — "ref values cannot be copied;
# pass p to a ref parameter instead"
```
Compatibility: breaks currently-accepted aliasing patterns; no syntax added; SPEC §8 gains the ownership rules. This is the smallest change that makes the enforced contract rows sound.
- **(b) Parameter-mode keywords (Cluster CC D.040-D.049): mode syntax NOT approved — requires user decision with examples before any implementation.** Before/after (illustrative only):

```a7
# Today: ref params mutate referents; binding immutable (approved, stays)
bump :: fn(x: ref i32) { x = x + 1 }

# CC proposal (NOT approved): explicit/inferred borrow/inout/consume modes
fill :: fn(b: inout []u8) { ... }        # explicit at public boundaries
release :: fn(p: consume ref Buf) { del p }
```
Gain: call-site exclusivity checks, mode-encoded API contracts. Cost: new keywords, inference pass, public/private signature split, and D.049's no-storable-refs rule — which **contradicts the accepted `ref`-struct-field surface** (SPEC §3.3) and would break linked-structure idioms; that contradiction is itself an approval question.
- **(c) Regions (Cyclone/Verona-style) as phase-2:** arena-scoped storage with region-tied provenance for the AI scratch/workload patterns; only if (a)/(b) leave real ergonomic gaps (research base's own recommendation).

**Q2 — Cast surface (HANDOFF S3: D.024 and D.038 are both marked ACCEPTED and contradict each other).** With explicit-width integers, the recommended resolution is the staged hybrid from HANDOFF §7: `cast(T, x)` restricted to primitive numeric conversions with compile-time range discharge; everything else via named methods/constructors; `int↔ptr` never. Before/after:

```a7
# Before (audit hole, 07-language-review §1.2): compiles today
p: ref i32 = cast(ref i32, some_usize)   # must become: hard error "irrecoverable"

# After (hybrid): numeric narrowing keeps proof discipline
n: i32 = read()
u: u8 = cast(u8, n)      # compile error unless n proved in [0,255]
                        # help: guard `if n >= 0 and n <= 255 { ... }` or use checked form
```
Compatibility: examples currently using legal numeric `cast` keep working; any int↔ptr shape must be re-audited for acceptance today (the audit found it compiled; re-verify at the decided surface).

**Q3 — Storable function values (recursion-ban completeness vs feature).** Simplest sound option: function values only as direct arguments, never stored in fields/globals/arrays. Before/after:

```a7
# Before (accepted today; emits recursive Zig — MS-7a)
s := Cb{f: spin}
ret s.f(n - 1)

# After (option: no storable function values): compile error on `f: spin`
# struct fields cannot hold function values; pass callbacks directly:
apply :: fn(g: fn(i32) i32, n: i32) i32 { ret g(n) }
```
Compatibility: minor (callback-table idioms); buys a genuinely acyclic call graph and with it the stack budget (I-14). Alternative: type-informed call-graph edges (I-13) without the storage restriction — more compiler work, keeps the idiom.

**Q4 — Float semantics (not approved either way).** Decision required: IEEE-754 (NaN/inf as values, comparisons non-total — narrowing must treat float guards as non-facts, `Fin<T>` unavailable) vs finite-only (needs `?f64`-style partiality for overflow-producing ops, closer to the original "no NaN, no inf" text, but then division `1.0/x` at `x==0.0` and float-literal overflow need typed outcomes). Tensor dtypes f16/bf16 inherit the scalar decision. No recommendation is imposed; both are stateable, but the choice changes proof obligations for float→int casts and comparison-based narrowing, and it must be recorded before the tensor kernel API freezes.

**Q5 — Release profile posture.** Stay `-OReleaseFast` with the no-trap/shape gate once proofs are sound, or interim `-OReleaseSafe` until I-3..I-11 land. Coordinator/owner product decision (prior review decision 9); changing the profile alone repairs nothing (roadmap decision 7).

---

## 11. Dependencies and approval questions

**Approval questions for the user (blocking, in order):**
1. Q1 reference/ownership surface — option (a) syntax-free now, (b) mode keywords (needs examples above), or (c) defer all aliasing work (leaves MS-3/MS-5/MS-8 accepted-unsafe in v1 — not recommended given "broad v1 includes ownership").
2. Q2 cast hybrid vs removal (resolves the accepted D.024/D.038 contradiction; note both stale decisions must be re-marked once resolved).
3. Q3 storable function values vs type-informed edges (recursion ban completeness).
4. Q4 float semantics (IEEE vs finite-only) — required before narrowing-over-floats and tensor cast obligations freeze.
5. Q5 release profile (ReleaseFast posture).
6. Untagged-union fate (I-8 options; SPEC §3.3 rewrite either way).
7. Module cycle policy: reject or support (current behavior is accidental — F4); visibility enforcement scope (F6); with NEW-1 fix scheduling.
8. Superseded-doc cleanup: mark D.001-D.004/D.021-adjacent CA items and CC cluster as superseded/proposed in `08-decisions.md` and HANDOFF once approved directions land, so the decisions ledger stops asserting bignum/mode-syntax as accepted.

**Dependency ordering (implementation):** I-10/I-11 (proof engine) precede everything; I-3/I-4/I-5 follow immediately (they need no new syntax); I-7/I-8/I-15 are independent; I-13→I-14 (then concurrency I-18..I-21, which also require Q1); NEW-1/`file_module_call` fix precedes I-13's module-edge work; I-25 artifact safety is parallelizable now; I-26 supply-chain items are release-blocking per roadmap independent of language work. Tensor/autograd (I-22 design requirements) depend on I-5's affine/drop discipline existing first; GPU concerns remain out of scope for CPU v1 qualification.

---

## 12. Source and version ledger

**Repository (all at commit `701c67936c70ad2b0608326e23e56cc5d38c9fdb`, read 2026-09-14):** `README.md`; `AGENTS.md`; `docs/SPEC.md` (implementation-status header dated 2026-05-08); `docs/SAFETY_CONTRACT.md`; `docs/SECURITY.md` (actions-pinning date 2026-05-08); `docs/STATUS.md`; `docs/lang-safety/08-decisions.md` (clusters CA/CB ACCEPTED, CC PROPOSED; internal D.024/D.038 contradiction); `docs/lang-safety/HANDOFF.md`; research base digested from `05-for-a7.md`, `01-invisicaps.md`, `02-sanitizers.md`, `03-hardware.md`, `narrowing.md`, `parameter-modes.md`, `compile-time-knowledge.md`, `07-language-review.md`, `comparative/{rust,zig,swift,hylo,mojo,inko-koka-verona,pony,cyclone,...}.md`; audits under `docs/audits/2026-09-14/` (README, root-review, completion-roadmap, memory-safety-glm-review [corrected pass], security-glm-review [corrected pass], pipeline-glm-review, contract-release-glm-review, audit-matrix). **Code re-verified first-hand at HEAD:** `a7/safety.py` (joins 301-306, helpers 170-174; calls 444-447; overflow 631-646; moved-set 724-726), `a7/backends/zig.py` (del 1300-1306; approvals 1786-1795; defaults 2115-2141; format-string/quoting 2251-2303), `a7/passes/semantic_validator.py` (del 384-396; call graph 501-544; callee extraction 803-818), `a7/passes/type_checker.py` (file_module_call 1318-1321; io validation 1437-1465), `a7/module_resolver.py` (124-197, 310), `a7/parser.py` (153, 201-206, 2235-2261), `a7/compile.py` (346-382, 440-471, 850), `a7/formatters/{json,console,markdown}_formatter.py`, `a7/generics.py` (121), `a7/backends/base.py` (44-47). Sub-agent verified: stdlib registry surfaces, package-wide exec/write sweep.

**External (accessed 2026-09-14):** Rust Reference, *Operator expressions* (doc.rust-lang.org/reference; borrow/aliasing rules, overflow semantics, `as` cast table). Swift: SE-0176 *Enforce Exclusive Access to Memory* (swift-evolution); swift.org blog *Swift 5 Exclusivity Enforcement* (2019); SE-0458 *Strict Memory Safety* (draft). Zig Language Reference 0.16.0/master (ziglang.org/documentation: `undefined`, Illegal Behavior, Build Mode, Memory). Odin FAQ (odin-lang.org/docs/faq: parameter immutability, zero-init/`---`, no ownership semantics, no pointer arithmetic, allocators/arena, no closures). Go race detector article (go.dev/doc/articles/race_detector) and Go memory model (happens-before). C++: Core Guidelines (isocpp.github.io); Horváth & Gehre, *Implementing the C++ Core Guidelines' Lifetime Safety Profile in Clang* (LLVM DevMeeting 2019); Baxter, *Why Safety Profiles Failed* (circle-lang.org/draft-profiles.html). Research: Grossman et al., *Region-Based Memory Management in Cyclone* (POPL 2002); Swamy et al., *Safe Manual Memory Management in Cyclone* (SCP 2006); Crary et al., *Typed Memory Management in a Calculus of Capabilities* (ICFP 1999); Tofte & Talpin region inference (POPL 1994, per citation trails); Reinking et al., *Perceus: Garbage Free Reference Counting with Reuse* (PLDI 2021); ponylang.io (*capabilities-secure, actor-model*; ORCA runtime per Pony documentation); *Dala: A Simple Capability-Based Dynamic Language* (arXiv:2109.07541, 2021); *Tree Borrows* (PLDI 2025); Stoldt et al., *Dynamic Region Ownership for Concurrency Safety* (PACMPL/OOPSLA 2025, doi 10.1145/3729313).

---

## 13. Limitations

1. **Compile-only evidence for memory behavior.** Consistent with the audit's constraints, no memory-corruption payload was compiled to an executable or run; runtime outcomes (OOB write, UAF write, double free) are inferences from verified compile-time acceptance and emitted-Zig shape, under Zig 0.16.0's documented Illegal-Behavior semantics. No runtime-safety conclusion is drawn from compile acceptance, text scans, or absence of trap strings.
2. **Verification depth.** First-hand reads covered the cited load-bearing regions and all previously-uncovered formatter/stdlib/artifact surfaces; a full line-by-line read of every pass was not repeated (the sibling pipeline review performed one at the same commit, and its claims I spot-checked all held). Sub-agent line references were trusted only where aligned with my own spot checks.
3. **Attributed items.** Preview-server runtime behavior, site-build injection reachability, and coordinator gate counts are coordinator-attributed (root-review.md) and marked as such; the preview server was not running and was not probed by me.
4. **Design status.** All of §6 beyond the current enforced checks is *proposed invariants*, not implemented behavior; concurrency, arenas, tensors, FFI, and stack budgets do not exist in the implementation, and their treatment here is requirement-setting under the locked user directions. No unapproved syntax is assumed anywhere; §10's mode-keyword and cast examples are decision aids only.
5. **Superseded-decisions risk.** `08-decisions.md` contains accepted decisions (bignum numerics, `number`) that the current directions void, plus a live internal contradiction (D.024/D.038); until that ledger is reconciled (§11 Q8), any doc-level claim of "accepted design" must be checked against the current directions first.
6. **No sandbox, no completeness.** This review does not enumerate every possible compiler bug, does not qualify remote CI or published artifacts, does not audit the deployed site, and makes no claim that rejecting every runtime failure is feasible — §7's impossibility classes are part of the contract, not a disclaimer appended to it.

— End of advisory report. Advisory only; no repository files were modified.
