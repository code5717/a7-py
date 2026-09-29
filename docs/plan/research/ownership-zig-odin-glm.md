> **Source:** OpenCode zai-coding-plan/glm-5.3, immutable arguments and ownership direction compared with Zig and Odin.  
> **Session:** `opencode session ses_f5e8d4575ffeZ28gnTCHhUeUuP`  
> **Date:** 2026-09-14. Recovered 2026-09-15 with opencode export after Plan Mode blocked the original write.  
> **Status:** Advisory. Report and follow-up turn preserved verbatim; earlier progress messages omitted. User decisions are in the [ledger](../decisions.md).

# Advisory Review: Immutable Function Arguments & Ownership Direction for A7 v1

**Role:** external reviewer (advisory only). Read-only: no files were edited or created; no compiler probes were run. Sources read first-hand: `docs/lang-safety/HANDOFF.md`, `docs/lang-safety/08-decisions.md` (Cluster CC, D.040–D.053), `docs/lang-safety/parameter-modes.md`, `docs/SAFETY_CONTRACT.md`, `docs/audits/2026-09-14/memory-safety-glm-review.md`, `docs/SPEC.md` (ref/swap surface), `examples/013_pointers.a7`, official Zig language reference (ziglang.org, master) and official Odin overview (odin-lang.org).

---

## 1. What Zig and Odin actually do (official-doc findings)

The claim "function parameters are immutable, Zig/Odin style" is being used in the A7 docs to mean something **neither language implements**.

**Zig** (official langref):
- Parameters are immutable *bindings*: "This is made possible, in part, by the fact that parameters are immutable" (Pass-by-value Parameters).
- "`const` applies to all of the bytes that the identifier immediately addresses. Pointers have their own const-ness."
- Consequence: `fn f(s: []u8) void { s[0] = 0; }` is **legal** — the binding `s` can't be reassigned, but the pointee is fully mutable through it, and the caller's storage changes invisibly. Read-only pointee must be requested *in the type*: `[]const u8`, `*const T`. There is no aliasing or exclusivity check anywhere.

**Odin** (official overview):
- "all parameters are immutable in Odin" — immutable *bindings*; "To mutate the procedure parameter (like in C), an explicit copy is required … `x := x`" (shadowing).
- "Passing a pointer value makes a copy of the pointer, not the data it points to. Slices, dynamic arrays, and maps … are normal structures with pointer fields … Their elements will not be copied." So mutating `s[0]` through a slice parameter mutates the caller's data. Odin has no `const` at all (strings are the one immutable type) and no exclusivity checking.

**Finding:** Zig/Odin give you (a) no binding reassignment, and (b) **zero restriction on pointee mutation, zero aliasing safety**. Their parameter immutability exists for calling-convention efficiency (lets the compiler pass big values by reference), not memory safety. D.040's example `s[0] = 0 // compile error: s is borrow` (08-decisions.md:1508) is **read-only-borrow semantics (Rust `&T` / Hylo `let` / Mojo `borrowed`)**, mislabeled as Odin/Zig. The rationale text ("Matches Odin's model", 08-decisions.md:1531) is factually wrong about Odin.

**A7-specific wrinkle that forces a choice:** A7's public surface has no address-of/deref operators and ref parameters use implicit deref (SAFETY_CONTRACT.md:64-68; `examples/013_pointers.a7` — `p += 1` on `p: ref i32` means *pointee* += 1). So unlike Zig (`p.* = 1` vs `p = other`), A7 **cannot syntactically distinguish binding-write from pointee-write**. "Immutable bindings only" cannot be inherited from Zig; A7 must pick a semantic.

---

## 2. The three precise choices

| | A. Immutable bindings only (literal Zig/Odin) | B. Read-only borrowed default (D.040 as written; Hylo/Mojo) | C. Deep immutability even for owning resources |
|---|---|---|---|
| `x = 10` on value param | error | error | error |
| `s[0] = 0` through `s: []u8` param | **allowed** | error | error |
| `p.x = 1` through `p: ref T` param | **allowed** | error | error |
| mutate through a `consume`d/owned param | allowed | allowed | **error** |
| new keywords needed | none | mutation surface needed (not necessarily a keyword) | mutation surface needed |
| memory-safety leverage | **none** (no exclusivity, no fact preservation) | high (see §3) | not more than B for memory safety |
| rejects safe programs | few | moderate (mutating helpers must opt in) | many (builder/init helpers die) |

**A** is not a memory-safety mechanism at all. It leaves every mutation-through-parameter hazard in the 2026-09-14 review expressible: callee writes through `ref` params invalidating caller proofs (MS-2), `del` through a `ref` param freeing caller storage (MS-5), invisible slice aliasing. It also cannot deliver the already-committed concurrency model (D.050 channels + isolated owned data): a slice handed to `go work(s)` under A shares mutable memory across tasks — a data race the contract forbids. **Channels+isolation without ownership/move tracking is incoherent; A alone contradicts user direction #11.**

**C** adds no memory-safety gain over B (UAF/double-free come from `del`/free paths, not from benign mutation) and costs heavily: freshly allocated objects couldn't be initialized/filled by helpers, builder patterns die. Over-rejection was already codex's critique of the design's proof surface (HANDOFF §4.2).

**B is the only choice that is both safety-bearing and consistent with the existing drafted decisions** — D.040's example text, D.041b's lattice, D.044 exclusivity, D.047 non-Copy slices, and narrowing.md's "borrow doesn't reset facts" invalidation rule (narrowing.md:315-323) all presuppose read-only defaults.

---

## 3. Impacts by feature (choice B assumed, deltas noted)

- **Slices:** default `s: []u8` is a read-only view; writing needs the mutation surface. Avoids introducing Zig-style `[]const u8` type-level const (mode carries constness; keeps the type surface small). D.047 (slices not `Copy`) already prevents slice-header aliasing duplication; keep it. Under A, two aliases + writes through both are unchecked in-task corruption.
- **Owning heap refs (`ref T` from `new`):** default param = read-only view of the object. `del` on *any* parameter becomes a compile error (it consumes caller-owned storage) — structurally closes the MS-5 shape (`del` through ref param) and half of MS-4's risk class. Ownership transfer stays a separate concern (§5).
- **Return values:** the rule "returned values are owned or copies" stays; returning slices of locals remains rejected (MS-8 unchanged). Read-only defaults make returning a *view* of a param conceptually safe for reads but A7 has no storable refs (D.049), so v1 should still reject returning slices of parameters — cheap and conservative.
- **Consumption/drop:** `del`/consume applies only to owning bindings at the owner, plus channel/task moves. Auto-drop (D.046) composes unchanged. Under A, "consume" has no distinguishable meaning — everything is a mutable alias.
- **I/O handles:** immutability must be **shallow**: kernel/OS state is not A7 pointee state. An immutable `f: File` binding may still `f.write(...)`. Frame handles as non-Copy opaque values whose stdlib methods are compiler-known-effectful; binding immutability is all that applies. Under C this needs an explicit exemption; under B it falls out naturally.
- **Channels:** same shallow rule — `ch.send(v)` mutates channel internals but not the binding. The send *operand* must be owned (move) for non-Copy: `ch.send(s)` where `s: []u8` is a local view must be rejected or require an owned value (D.052 needs ownership anyway).
- **Task transfers:** `go work(s)` with read-only-default `work` still shares memory across tasks — isolation requires the *argument* to be moved/copied at spawn for non-Copy types. So the minimal ownership core (move-on-spawn, move-on-send) is needed **regardless** of the immutability choice; B is what makes the spawn boundary checkable.
- **Fact-engine soundness (from prior review):** under B, calls whose relevant arguments are default-mode provably don't write through them, so caller nil/interval/length facts survive *those* arguments — the conservative call-effect invalidation (review design decision 2) shrinks to mutating calls and globals. Under A, every call invalidates everything ref-passed, or the proofs stay unsound.

---

## 4. Before / after examples (explicit widths only, per approved numeric vocabulary)

**Before (today's A7, `examples/013_pointers.a7`):**
```a7
increment :: fn(p: ref i32) {
    p += 1                    // mutates caller's x, invisibly; no keyword anywhere
}
main :: fn() {
    x: i32 = 10
    increment(x)              // x == 11 now
}
```

**After — choice A (binding-only; pointee mutation silent, NOT recommended):**
```a7
increment :: fn(p: ref i32) {
    p += 1                    // still OK: implicit deref = pointee write, binding untouched
}
fill :: fn(b: []u8) {
    b[0] = 0                  // still OK: caller's bytes change, signature says nothing
}
```

**After — choice B (read-only default) with mutation surface = explicit keyword (NOT approved, shown for contrast only):**
```a7
increment :: fn(p: inout i32) { p += 1 }        // mutation visible in signature
fill :: fn(b: inout []u8)      { b[0] = 0 }
```

**After — choice B with a keyword-free mutation surface (option 2 in §5):**
```a7
bump :: fn(v: i32) i32 { ret v + 1 }            // pure, no keywords

main :: fn() {
    x: i32 = 10
    x = bump(x)                                 // functional update; compiler lowers in place
    buf: [4]u8 = [0, 0, 0, 0]
    buf = buf_fill(buf, 0)                      // or method form: buf.fill(0)
}
```
(Same program shape under either surface; the difference is only where mutation is declared.)

**After — choice C (deep immutability, NOT recommended):**
```a7
init :: fn(p: ref Point) { p.x = 0 }            // compile error even for fresh objects
main :: fn() {
    p := new Point
    p.x = 0                                     // only the owner may mutate; helpers can't
}
```

---

## 5. Recommended minimal coherent ownership direction (for user discussion)

1. **Adopt immutable bindings, Zig/Odin-literal** — no parameter reassignment ever, in any mode. Cheap, uncontroversial. (Note: `docs/SPEC.md:698-702`'s own `swap` example reassigns `ref` params and conflicts with even this; it must be updated under any choice.)
2. **Adopt read-only pointee for default (no-keyword) parameters** — D.040's actual example semantics. Fix D.040's rationale to cite Hylo/Mojo/Rust `&T`, not Odin/Zig. This is the safety-bearing decision and the one needing explicit user approval.
3. **Keep ownership tracking confined to the owning spine:** `new`/`del` bindings, move-on-channel-send, move-on-task-spawn, auto-drop (D.043/D.045/D.046/D.047/D.052 as drafted). No storable refs (D.049). This much ownership is already forced by the committed concurrency model — it is not optional complexity.
4. **`del` on a parameter is always a compile error** (structural fix for MS-4/MS-5 shapes, independent of provenance analysis).
5. **Shallow immutability for stdlib handles/channels** (binding immutable; effectful operations allowed; kernel/runtime state is out of scope). User-defined mutating methods deferred with the mutation surface.
6. **The one genuinely open decision — the mutation surface** (since explicit `inout` is not approved), as a menu:
   - **(a)** inferred modes on private functions per D.041 (zero keywords; public functions still need *some* declared surface);
   - **(b)** functional-update convention (`x = f(x)`, `buf.fill(0)` sugar), compiler-verified in-place lowering via linearity — zero new keywords anywhere, mutation never crosses a signature;
   - **(c)** explicit keyword(s), Swift/Hylo style — requires separate approval.

   My advisory preference for v1 discussion: **(b)**, with (a) as the ergonomic fallback; both are consistent with directions #5/#6 (no mode keywords, small language). Note D.041/D.041b/D.042 currently presuppose a keyword surface at public boundaries — under (b) those three decisions need rework; under (a) they stand.

---

## 6. Memory/cyber consequences (scope note, not full security claims)

- Choice A leaves argument-passing as an **invisible mutation channel**: signatures cannot be audited for write behavior, enabling write-after-check corruption patterns through aliases (the classic in-memory TOCTOU/confused-deputy shape) in ReleaseFast artifacts where no runtime backstop exists. The prior review's critical holes (MS-1/MS-2) would remain unfixable at this layer.
- Choice B makes mutation **signature-auditable** (grep-able API surface for reviewers) and shrinks the fact-invalidation problem to mutating calls plus globals; globals remain a residual invalidation surface under any choice.
- No choice alone fixes MS-1 (join soundness), MS-3 (alias double-del), MS-6 (unions), MS-7 (recursion bypasses), MS-8 (escape), MS-9 (init), MS-10 (overflow); B is an enabling layer, not a repair.

## 7. Drift flags found in passing

- `08-decisions.md`/`parameter-modes.md`/`HANDOFF.md` still assume `int`/`uint`/`number` (HANDOFF Q1–Q3) — superseded by the user's approved explicit-widths-only vocabulary (i8..i64, u8..u64, isize, usize, f32, f64); docs examples need the sweep before CC is re-presented.
- D.040 rationale mis-cites Odin/Zig (§1 above).
- `SPEC.md:698-702` `swap` example reassigns `ref` params — incompatible with immutable bindings.

---

*Follow-up turn in the same session, preserved verbatim.*

# Corrected Advisory: "All Function Arguments Are Immutable" — Reconciled Review

Advisory only; read-only (no files touched; one fetch of the provided Jai source). This supersedes my prior report where corrected below.

---

## 1. Withdrawals and corrections

1. **Withdrawn: "choice A (binding-only immutability) makes safety unfixable."** Immutable bindings with mutable referents can coexist with ownership, exclusivity, effect tracking, and isolated tasks — the checking lives in compiler analysis (A7's passes), not in the parameter surface. Zig/Odin/Jai merely *choose* not to provide that analysis; nothing about binding immutability prevents it.
2. **Withdrawn: "consume is impossible under A" and "B is uniquely coherent."** Ownership transfer is an orthogonal axis (affine bindings over `new`/`del`/channel/task moves) and composes with mutable referents. Both designs are coherent; they differ in where mutation is *visible* (inferred effects vs. parameter surface) and in migration cost.
3. **Corrected: read-only parameters do not prevent writes via globals or independently obtained aliases.** Even with fully immutable arguments, a callee may write a global or mutate storage reached another way. Conservative call-effect invalidation (globals, escaped aliases, receiver-mutating stdlib operations) is required **regardless** of the immutability semantics chosen. Jai's own docs-in-practice concede the same: args are treated `const & restrict`, but "the data might be aliased by an evil global or a pointer… the Jai philosophy is don't do that, and maybe try to detect it in debug mode."
4. **Corrected: `p += 1` through `ref i32` is referent mutation, not parameter rebinding.** Implicit deref means the existing blessed idiom (`examples/013_pointers.a7`) and SPEC's `swap` (`a = b` on `ref T` params = pointee write) are **legal under binding immutability** — no migration needed. Binding immutability bites only value-typed parameter reassignment (`x: i32; x = 5`). My earlier claim that SPEC `swap` conflicts with immutable bindings was wrong.
5. **Corrected: blanket `del`-on-parameter ban is policy, not safety necessity.** The safety requirement is **ownership provenance**: `del` is legal only on a binding owned at that point. `del` on an explicitly transferred owned parameter (take-ownership-then-free) is a legitimate pattern if/when a transfer surface exists. A blanket parameter ban is merely one conservative interim shape.
6. **Corrected: I/O and channel state is not "out of scope."** Channel buffers and file state are mutable runtime memory; `ch.send(v)` is a write. The principled framing: stdlib receiver-mutating operations carry **declared effects** in the compiler's stdlib registry and participate in the same invalidation as globals. No hand-waving.
7. **Corrected: functional-update in-place lowering is conditional.** `x = f(x)` may lower in place only when uniqueness (no outstanding aliases) and value semantics are proven; otherwise it copies (or is rejected). It is a value-semantic convention with opportunistic performance, not a universal no-copy guarantee.
8. **New input incorporated: user approved Odin-style defined wrapping `+ - *`.** See §5.

---

## 2. Evidence base (Zig/Odin official; Jai qualified)

| | Binding reassign | Write through argument | Mutation surface | Aliasing/effect check | Ownership |
|---|---|---|---|---|---|
| **Zig** (official langref) | forbidden ("parameters are immutable") | legal unless type says `const` (`[]u8` vs `[]const u8`, `*T` vs `*const T`) | type-level `const` | none | manual |
| **Odin** (official overview) | forbidden ("all parameters are immutable in Odin"; mutate via shadow copy `x := x`) | always legal for pointee (slices/pointers "normal structures with pointer fields… elements will not be copied"); no `const` exists | explicit pointer param | none | manual |
| **Jai** (Feb 2023 closed-beta practitioner report — **not official, not current; Jai has no public authoritative docs**) | forbidden; deep: `s.count = 0` → "Can't assign to an immutable argument" | forbidden through arguments ("written as if `const &`"); mutation only via explicit pointer arg | explicit `*T` param | assumes `restrict` (no alias) **unproven**; "maybe detect in debug mode"; no const, no references, no ownership, explicitly "NOT memory safe" | manual |

Jai is the useful third point: it shows "all arguments immutable" in the **deep** sense is a shipping design (with maybe-by-reference passing as the payoff), and it shows the honest cost — the no-alias assumption is a philosophy, not a check. Qualification: single 2023 beta source; semantics may have changed; nothing about Jai numerics/floats is authoritative (consistent with the coordinator not finding an official float contract).

---

## 3. Precise meaning of "all function arguments are immutable" — keyword-free

Recommended formulation (for user confirmation, layered so the uncontroversial part is separable):

**R1 — Binding immutability (unconditional, matches Zig/Odin/Jai):** a parameter name may not be rebound. With A7's implicit deref, the precise syntactic rule is: assignment whose target is the bare parameter name denotes *binding* mutation for value-typed parameters (→ compile error) and denotes the *referent* for `ref`/slice-typed parameters (existing semantics unchanged).

**R2 — Deep immutability of by-value arguments (recommended; enables Zig/Jai "maybe by reference"):** a by-value argument's bytes are read-only in the callee; the compiler may pass large ones by pointer. Zero new syntax; enables `const&restrict`-style optimization and keeps value semantics observable.

**R3 — Referent-write policy for parameter-passed storage (`ref T` params, slice element writes): the one genuine fork (Decision 1 below).** Either writes remain legal (today's semantics; visibility via inferred effects + tooling + serialized cross-module signatures), or they are restricted to an explicitly mutable parameter *type* — note `ref T` already is such a type in today's keyword-free surface; the open sub-question is slice interiors, which have no `ref`-flavored form today.

Under R1+R2 alone, **all existing examples and SPEC idioms compile unchanged**; the language gets strictly one new rejection rule (value-param rebinding) plus one optimization freedom.

---

## 4. Interaction notes (corrected)

- **Effects/invalidation:** under any R3 choice, calls still invalidate facts for globals and escaped aliases; stdlib mutating ops (`ch.send`, file writes) must be effect-declared. R3(b) narrows per-argument invalidation to mutating parameters; R3(a) achieves the same per-argument precision through inferred effects, at the cost of syntax-level auditability.
- **`del`:** provenance rule as in §1.5. Blanket interim ban is one option, now labeled as such.
- **Consume/moves:** orthogonal spine (`new`/`del`, move-on-send, move-on-spawn per D.050–D.052) — compatible with every R3 choice.
- **Return values:** unchanged from prior report (owned-or-copy rule; MS-8 slice-of-local rejection stands; read-only views of params remain rejected in v1 for conservatism — storable refs are banned anyway).

---

## 5. Overflow reflection (user already decided: Odin-style defined wrapping `+ - *`)

- `+ - *` on fixed-width ints: defined wrap (unsigned mod 2^n; signed two's-complement, deterministic; compiler may not assume no-overflow — per official Odin overview). The "overflow proof obligation" for these operators **dissolves**; MS-10 in the prior review is superseded by policy, not by implementation.
- Remaining numeric obligations: division/modulo (zero divisor), casts (range), float→int; Odin also defines shifts (unbounded count, shift-as-n-single-shifts) — mirror or restrict is a minor doc choice.
- Concrete codegen consequence: Zig plain `+` is illegal-behavior on overflow in ReleaseFast, so A7 **must emit `+%` / `-%` / `*%`** (and `<<|`-equivalent care for shifts) to deliver defined wrap.
- Doc sync when decisions land: SAFETY_CONTRACT risk-table arithmetic row, SPEC arithmetic section, 08-decisions CE text, STATUS/MS-10 note.

---

## 6. Necessary user decisions (only these; no decisions made here)

1. **R3 — referent-write policy for parameter-passed storage.**
   (a) legal with inferred effects (zero migration; mutation not in syntax; visible via tooling/serialized signatures), or
   (b) legal only through explicitly mutable parameter types (`ref T` qualifies today; slice interiors then need: forbid in v1 / stdlib wrapper / future surface — sub-decision).
2. **`del` legality shape.** Ownership-provenance rule (general; permits `del` on explicitly transferred owned params once transfer exists) vs. conservative interim blanket parameter ban. Safety requires only provenance.
3. **Effects & invalidation contract.** Accept that globals/aliases/stdlib-mutating-ops require conservative invalidation under any choice, and pick the visibility mechanism for cross-module/public mutation contracts without new keywords (inferred-and-serialized per D.041's private-inference compromise, tooling-only, or defer). D.041/D.041b/D.042 need rework under the no-keywords direction either way.

Doc-drift flags (carry-over, still valid): D.040's rationale mis-cites Odin/Zig for read-only pointee (Odin/Zig allow referent writes; Jai-style deep-const is the real precedent if R3(b) is chosen); the parameter-modes comparison table should add Jai (qualified); docs still use `int`/`uint`/`number` vs. the approved explicit-width vocabulary.