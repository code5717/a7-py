> **Source:** Claude Code reading subagent, group D, full read of saved repository research.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../decisions.md).

# Brainstorm notes D — conversions, narrowing, edge-cases 01–12

Scope: `docs/lang-safety/conversions.md` (626 lines), `docs/lang-safety/narrowing.md`
(657 lines), `docs/lang-safety/edge-cases/01..12` (all read in full). Status is judged
against `docs/plan/decisions.md` (locked L1–L16, "Superseded material" lines 70–90),
not only what each file says about itself. Paths below are relative to
`docs/lang-safety/` unless stated. "(inference)" marks my own reasoning.

Headline: this corpus is about **safety** (use-after-free, double free, null,
out-of-bounds, overflow, NaN). It does **not** cover **reclamation**, meaning
automatic freeing. It assumes an explicit `del` (10:7–9, 10:AO-06, Q10e 10:175–178
"no destructor; `del` is explicit"), rules out `Rc`/`Arc` (10:81), and never proposes
freeing memory automatically. None of the 14 files mentions garbage collection,
tensors or autodiff. The L15 memory model therefore has to be built from nearby
mechanisms, listed in section 2.

---

## 1. Per-file summaries and status

### conversions.md — research for Cluster CB; now largely historical
- Proposes method-style conversions (`x.to_int()`, `s.parse_int()`) over constructor
  style (`int(x)`) and operator style (`cast`/`@as`) (201–217). Its two-category rule
  (8–18) says statically resolvable conversions return `T` and fail to compile when
  the proof is missing, while data-dependent ones return `?T`/`Result`.
- Central claim (250–326): narrowing makes the `?T` contract free, because the
  compiler emits a bare cast when the proof holds.
- The whole surface uses `int`/`uint`/`number` with "arbitrary precision" (27–30,
  223–235). decisions.md:83 supersedes D.025–D.027 and D.033–D.039 for L4, and
  decisions.md:85 sends the `cast` keep-or-remove question to gate G3.
- It contradicts itself. It says "`cast` keyword removed entirely (D.038)" (597), yet
  its worked examples still use `cast(uint, i)` (269, 304). It says opaque
  `x.to_uint()` is a "Runtime branch" (534) but also "does not compile" (349–350).
  Its code mixes brace syntax with `fn … end` syntax (462–474).
- **Status:** research, historical where it depends on `int`/`uint`/`number`. The
  method-style principle and check elision remain open under G3.

### narrowing.md — research for Cluster CD; the mechanism is still live
- Flow-sensitive narrowing acts as a hidden subtype lattice, for example
  "`int with non-zero`" (58–96). The user never writes these subtypes (93–96, 470–476).
- It covers 12 patterns (N1–N12, 119–301) and an invalidation table (311–321). It
  weighs four precision levels (336–380) and recommends Level 2, disjunctive
  intervals, plus fixed patterns (382–399).
- It recommends no `assert` in v1 (543–545) and says a runtime assert is "Forbidden
  by the contract" (517–518).
- It depends on unaccepted material. It uses `inout`/`borrow` modes (265–276, 316–320),
  though L6 approves no syntax (decisions.md:55–56) and D.040/041/049 were not
  accepted (decisions.md:87). It also relies on D.020 range tracking over `int`,
  which decisions.md:84 supersedes.
- **Status:** research. The idea stands, but the examples and numeric types are stale.

### edge-cases/01-cast.md — Phase A enumeration (research)
- Lists 30 casts (C-01..C-30) in the classes lossless, truncating, sign-change,
  bit-cast, forbidden, implicit upcast and FFI-only. The critical hole is C-13
  `cast(ref T, usize)`, which "Compiles — the critical hole" (33).
- Requires that cast classification be closed under composition (119–123) and
  re-checked for each generic instantiation (124–126).
- Open questions Q01a–h cover the strict vs lenient `cast`, `?T` vs `Result`, whether
  `bit_cast` exists, enum casts and migration.
- **Status:** research, feeding G3. The code citations (type_checker.py:1800,
  zig.py:1690) describe the tree the author examined.

### edge-cases/02-nullable-pointers.md — Phase A (research)
- Splits non-null `ref T` (lowered to `*T`, bare `p.*`) from `?ref T` (lowered to
  `?*T`, usable only after match/narrowing). The 22 sites N-01..N-22 cover locals,
  parameters, fields, arrays, generics, cycles, builders and `defer`.
- Cycles store `?ref T` "at exactly the cycle-closing link" (N-12, 29; 100–102).
- Questions: `?ref T` as its own type vs `Option<ref T>` (Q02a), how to initialise
  arrays of non-null refs (Q02d), and builders via `MaybeUninit` vs staged types (Q02e).
- **Status:** research.

### edge-cases/03-definite-assignment.md — Phase A (research)
- Reading before writing becomes a compile error on every path (DA-01..DA-20). Hard
  cases are loops (DA-06/07/08), element-wise array fill (DA-13), `new`-then-fill
  (DA-14), `set` out-params (DA-15) and `defer` (DA-10).
- Definite assignment and move analysis share one CFG and lattice (61–64).
- Dropping the silent zero-init "may actually speed up generated code" (111–113).
- **Status:** research. The file itself says "This entire feature is greenfield" (147).

### edge-cases/04-nonzero-division.md — Phase A (research)
- Proposes a `NonZero<T>` divisor refinement, a fallible `NonZero::new`, a
  `SafeDivisor<T>` excluding `-1` for signed types (NZ-06, Q04e), and a shift-amount
  bound (NZ-16, Q04g).
- L5 explicitly leaves division, remainder, `MIN / -1` and shifts undecided
  (decisions.md:52–54), so this file is still live.
- **Status:** research. NZ-17 depends on Gap 11, which L16 replaces (see section 3).

### edge-cases/05-stack-budget.md — Phase A (research)
- The recursion ban makes the call graph a DAG, so maximum stack depth is computable
  at compile time (7–11). The budget is the frame-size sum on the worst path, with a
  maximum over diamonds and match arms (SB-01/02/07).
- Default budget of 1 MiB (Q05a). Also covers spill estimation (Q05b), indirect calls
  as a maximum over matching signatures (SB-16/Q05d), per-thread budgets (SB-10/19)
  and large-struct returns via a `set` out-param (Q05f).
- **Status:** research (greenfield, 138). SB-05 cites "`CLAUDE.md:114-116`", a stale
  line pointer (inference: CLAUDE.md has since been rewritten).

### edge-cases/06-typed-arithmetic.md — Phase A (research); partly superseded
- Unproved `+ - *` is a compile error (TA-03, TA-05), with a
  `checked_`/`wrap_`/`sat_` family (TA-14..16), range tracking, widening questions
  (TA-23, Q06b) and a strict mixed-sign policy (TA-10/26).
- L5 (Odin-style defined wrapping) supersedes the overflow proof for `+ - *`
  (decisions.md:86). Negation, shifts and `abs` are not covered by L5 and stay open.
- **Status:** research, partly superseded by L5.

### edge-cases/07-bounded-indexing.md — Phase A (research)
- `s[i]` must be proved in bounds and then emits `s.ptr[i]`, or else go through
  `try_get(i) -> ?T`. A four-pattern catalog (Q07a) covers `for 0..len`, foreach,
  indexed foreach and a guard, plus the typed index `Index<n>` (BI-17).
- Slices are treated as immutable, so stale lengths "n/a" (BI-14, 31; 90–93).
- Option Q07d(c), "`s[i]` (proved, panic otherwise)" (128), conflicts with the no-trap
  contract.
- **Status:** research.

### edge-cases/08-option-result.md — Phase A (research)
- Proposes `Option`/`Result`, `?T` sugar, no `unwrap`/`expect` (OR-11/12, forbidden
  as traps), a `?` propagation operator (Q08c), niche optimisation of `Option<ref T>`
  to `?*T` (OR-20), and `Result<T,()>` → `?T` (98–100).
- Borrowing-style match (`case some(borrow v)`, Q08e) depends on Gap 10.
- **Status:** research. conversions.md:448–452 says CA D.010/D.017–D.019 accepted
  parts of it in 08-decisions.md. I did not verify which of those survive (D.010 is
  superseded in part, decisions.md:84).

### edge-cases/09-refinement-lite.md — Phase A (research)
- A closed or template refinement kit modelled on Ada `subtype`: `Bounded`, `Index`,
  `NonZero`, `Positive`, `Natural`, `Fin`, `SafeDivisor`, `Length`, `NonEmpty`
  (RF-01..09).
- Refinements are zero-cost `struct { value: T }` (108–110). An optional packed
  storage form (RF-20) would store `Bounded<i32,0,255>` as a `u8`.
- Uses the SPARK static-predicate model: "predicates without runtime input" (159–161).
- **Status:** research. RF-06 `Fin` is undermined by L16.

### edge-cases/10-affine-ownership.md — Phase A (research); key file for L15
- Direction: "mutable value semantics (Hylo's approach): references exist only as
  parameter-passing modes, not as storable values" (11–14).
- Covers move analysis (AO-01..10), modes `T`/`borrow`/`inout`/`consume`/`set`
  (AO-11..16), call-site exclusivity (AO-17..24), partial moves and drop order
  (AO-25..30), and refused Rust features (lifetimes, `Pin`, `Rc`/`Arc`) (AO-31..36).
- The mode vocabulary is **not accepted** (decisions.md:87; L6 scope limit :55–56),
  and the ownership syntax is open decision O2 / gate G2 (decisions.md:66).
- **Status:** research, the most relevant file for L15. Its manual `del` assumption
  now conflicts with L15's "something like garbage collection".

### edge-cases/11-finite-floats.md — Phase A (research); superseded in substance by L16
- Proposes `Fin<F>` for finite floats: non-finite values are "allowed but tracked"
  (FF-01..04), float→int is a compile error unless the input is `Fin` (FF-05), and
  literals are refined to `Fin` (FF-15). Q11a includes a "Strict: bare `f64` reserved"
  option.
- O1 ("IEEE values or finite-only") is resolved by L16 in favour of IEEE
  (decisions.md:65).
- **Status:** historical as a float policy. A few pieces could survive as optional
  library refinements (inference).

### edge-cases/12-ffi-boundary.md — Phase A (research); deferred by design
- FFI is "the **single** boundary at which the language stops enforcing safety"
  (8–9). Every `extern fn` must return `Result`/`Option` (FFI-02), or `()` when it
  cannot fail (FFI-03).
- Proposes `OpaqueRef<Tag>` for foreign pointers (FFI-22) and says A7 owns its
  allocator, with foreign allocations crossing only as opaque references (Q12h).
  Callbacks are open and should be restricted (FFI-27, Q12e).
- "This gap is mostly *deferred*" (161).
- **Status:** research, a deferred design note.

---

## 2. Memory-management ideas relevant to L15

L15 asks for automatic memory management with no runtime collector, designed for
data-oriented programs and resolved at compile time. Each idea below gives its
location, how it works, what happens at compile time vs runtime, its cost, and its
limits.

### 2.1 Non-storable references: mutable value semantics (Hylo) — 10:11–14, AO-31..35, Q10a (10:158–166)
- **Mechanism.** References exist only as parameter modes and cannot be struct fields
  or array elements. That removes lifetimes: "Hylo demonstrates lifetimes aren't
  needed if refs aren't storable" (AO-31, 76).
- **Compile time:** all of it. Modes lower to `*const T` / `*T` (AO-12/13).
  **Runtime:** nothing.
- **Cost:** "None at runtime … move analysis is the same complexity as DA (linear in
  CFG size)" (151–154).
- **Limits.** Shared mutable state (caches, observers) and parent/child links are
  false positives (125–132). Q10a lists a middle option, "storable but only in
  specific shapes (e.g., closures, generators)" (165–166).
- **L15 relevance (inference).** Hylo-style value semantics is the most direct way to
  get GC-like behaviour without GC. Values own their storage and the compiler inserts
  frees at scope exit. The file never says freeing is automatic, though; it keeps `del`.

### 2.2 Affine move analysis on the definite-assignment lattice — 10 AO-01..10, 10:91–95, 03:61–64, 02:59–62
- **Mechanism.** A binding is owned, moved, or consumed by `del`. Using it after a
  move or `del` is a compile error (AO-07/08), and moves on only some branches are
  errors (AO-09). "A moved `ref T` slot becomes effectively `?ref T = none` (the same
  'uninitialised after move' state DA tracks)" (10:88–90).
- **Compile time:** a forward CFG dataflow shared with definite assignment, "same CFG,
  same lattice operations, separate flags" (10:93–94). **Runtime:** none.
- **Limits.** Address-of is open (Q10c). Generic ownership must be re-checked for each
  instantiation (138–139). FFI is not covered (136).
- **L15 relevance (inference).** The same liveness lattice could decide the last use
  or scope exit where the compiler inserts a free, as in Rust drop elaboration or ASAP
  destruction. AO-29 already fixes "Reverse declaration order; deterministic" drop
  order (69). Q10e recommends against destructors, so L15 would reverse or reframe Q10e.

### 2.3 Parameter modes `borrow`/`inout`/`consume`/`set` — 10 AO-11..16; 03 DA-15; 05 Q05f
- **Mechanism.** The default passes by value (copy if `Copy`, otherwise move).
  `borrow` is read-only and cannot escape. `inout` is exclusive and cannot escape.
  `set` is write-only for uninitialised output (AO-15, "`*T` (Zig out-param)").
- **Compile time:** the mode checks and escape ban. **Runtime:** pointer passing.
- Large structs above N bytes (say 256) are returned through a `set` out-param
  (05:123–125).
- **Limits.** The syntax is not approved (decisions.md:55–56, 87). narrowing.md:319
  assumes borrow parameters cannot alias, "which they do" (assumed, not accepted).
- **Data-oriented relevance (inference).** `set` plus definite assignment lets callers
  pass uninitialised bulk buffers to be filled, which is the pattern tensor kernels need.

### 2.4 Call-site exclusivity, with range-proved distinct indices — 10 AO-17..24, Q10f; 06:94–96
- **Mechanism.** Two `inout`s on the same value are an error (AO-18). Distinct field
  paths are fine (AO-19). `arr[i]`, `arr[j]` with opaque indices are an error (AO-20),
  but "`f(inout arr[i], inout arr[i+1])` … OK (range proof: `i ≠ i+1`)" (AO-21).
- **Compile time:** the whole check, reusing the range tracker. **Runtime:** none.
- **Limits.** Aliasing through dereferenced pointers is open (AO-24).
- **Data-oriented relevance.** In-place updates over struct-of-arrays columns and
  element pairs (swap, stencils) depend on AO-19/AO-21 precision.

### 2.5 Arena plus indices instead of pointers (Cyclone-style) — 10:130–132, AO-35 (10:80), AO-36 (10:81), cite 10:212–213
- **Quotes.** "Linked data structures where parent and child both reference each
  other. Mitigation: use indices into a parent-owned arena (Cyclone style)."
  "Self-referential structs … Forbidden; user works around via indices." "`Rc`/`Arc`
  shared ownership | Out of scope; consider regions (Gap A reduction)."
- **Compile time:** the arena owns its elements, so ordinary ownership suffices.
  **Runtime:** index validity is only as good as bounds proofs (07) or a `try_get`
  branch. There is no generation check.
- **Limits.** Stale indices after removal or reuse are not discussed (inference: this
  is the ABA / generational-handle problem). BI-14 declares stale length "n/a (slices
  are immutable refs)" (07:31), which stops holding once arenas grow.
- **L15 relevance (inference).** This is the idiomatic Zig/Odin/Jai data-oriented
  answer and the best fit for "data oriented design". Regions are named but never
  designed.

### 2.6 Typed indices as handles: `Index<n>`, `OpaqueRef<Tag>` — 07 BI-17, Q07b; 09 RF-02, RF-08; 12 FFI-22, Q12f
- **Mechanism.** `i: Index<n>` "carries proof `i < n`" (07:34). `OpaqueRef<Tag>` is
  "named tag for type hygiene" (12:51).
- **Compile time:** the proof or tag. **Runtime:** a bare integer or pointer.
- **Limits.** "`Index<s.length>` but generics over slice lengths is a heavy feature"
  (07:81–84). Q07b chooses between a comptime `$n` and a refinement over the slice
  variable.
- **L15 relevance (inference).** A tagged, typed handle (`Handle<Pool>`) plus a proof
  of liveness would make arena access check-free. Nothing here covers liveness, only
  range.

### 2.7 Non-null / nullable split and cycles — 02 N-01..N-12, N-19; 08 OR-20
- **Mechanism.** `ref T` is non-null and emits bare `p.*`. `?ref T` "niche-optimises
  to `?*U`" (08:98–99). "end-of-chain stored as `?ref T` (literal `none`);
  intermediate is `ref T`" (N-12, 02:29).
- **Compile time:** nullness. **Runtime:** "Non-null deref is strictly faster (no
  `.?`)" (02:108).
- **Limits.** Arrays of non-null refs need full initialisation (N-08, Q02d). Builders
  need `MaybeUninit` or staged types (Q02e). A storable `ref T` field (N-06) conflicts
  with the non-storable model in 10 (inference: 02 assumes storable refs, 10 forbids them).
- **L15 relevance.** N-19, "for `ref T` the defer always frees" (02:36), is the closest
  this corpus comes to deterministic automatic freeing.

### 2.8 Definite assignment for uninitialised bulk storage — 03 DA-12..14, Q03a, Q03h, 03:111–113
- **Mechanism.** Arrays may be declared and filled progressively only if the analysis
  proves every index in `0..N` was written (DA-13). Alternatives are an explicit
  initialiser or `[N]MaybeUninit<T>` + `assume_init()` (Q03a, 03:117–123).
- **Compile time:** the proof. **Runtime:** "Zig can use `undefined` for the slot
  until the user's explicit assignment lands" (03:111–113), so there is no zeroing cost.
- **Limits.** "DA gives up when an address-of is taken (sound but conservative), or it
  tracks through pointers (precise but expensive)" (03:93–96). Loop-coverage proofs
  may only work for the literal `for i in 0..N` (Q03c).
- **Data-oriented relevance (inference).** Large tensor or column buffers need uninit
  allocation. `new`-then-fill (DA-14) is the heap version and is left open.

### 2.9 Proof-driven check elision — conversions.md:250–326; narrowing.md:50–54; 07:105–110
- **Mechanism.** The fallible signature is the contract, and the emitted code skips
  the check when narrowing discharges it. Example: "emission: bare `s.ptr[idx]`"
  (conversions.md:273–274).
- **Compile time:** range and nullness proofs. **Runtime:** only what the prover
  cannot discharge.
- **Cost.** Proved indexing is "*faster* than today" (07:107–108). `try_get` costs
  one `if` (07:109–110).
- **Limits.** Level 2 intervals lose cross-variable relations (narrowing.md:343–344).
  Level 3/4 costs more (361–380). Floats break it under IEEE (section 3).
- **L15 relevance (inference).** The same lattice could prove handle and arena liveness
  or "no escape", letting frees and region pops be placed statically.

### 2.10 Static stack budget over the recursion-free call DAG — 05 SB-01..20, Q05a–h
- **Mechanism.** The frame-size sum along the worst path is compared with a budget.
  Diamonds take the max (SB-02). Generics are sized per instantiation (SB-15).
  Indirect calls take the max over matching signatures (SB-16). Threads get their own
  budget (SB-10/19). FFI frames get a fixed allowance (SB-09).
- **Compile time:** the whole analysis, "O(call-graph-edges)" (05:97). **Runtime:** the
  stack size set at thread creation, "same cost as today" (98–99).
- **Limits.** "Recursion ban. **Required prerequisite.**" (58–59). Spill estimation is
  conservative (69–73). Inlining can make the estimate wrong (80–82). Multi-file
  programs need whole-program info (62–63). SB-05 (runtime-sized stack arrays) is
  rejected.
- **L15 relevance (inference).** The most "resolved at compile time" memory analysis
  in the corpus. The same DAG-plus-instantiation analysis could bound per-call
  temporary arena or scratch usage and size scratch allocators at compile time, much
  like Jai's temporary storage but proven. The file only covers stack frames.

### 2.11 Allocation failure as a value — conversions.md:15–16; 02 N-05, N-13
- **Mechanism.** `new T{...}` is data-dependent and returns `?T`/`Result`
  (conversions.md:15–18). "allocation failure surfaces as `-> ?ref T`" (02:22).
- **Compile time:** the type forces handling. **Runtime:** a branch on the allocator result.
- **Limits.** Ergonomics: every allocation gets a match (inference).

### 2.12 FFI allocator ownership and borrow retention — 12 Q12h, FFI-19, FFI-23, FFI-27, Q12e; 10:111–114
- **Mechanism.** "A7 owns its allocator; foreign allocations cross only as opaque
  references" (12:143–145). Foreign parameters default to `borrow` and foreign
  reference returns come back as `?ref T` (10:112–114).
- **Compile time:** the type shape at the boundary. **Runtime:** trusted, not checked.
- **Limits.** "Foreign code reads from a `borrow []u8` after the call returns |
  Documented hazard; the language cannot prevent" (FFI-23). Callbacks retained by C
  would need a `'static`-equivalent, which 10 AO-33 refuses (see 3.6).
- **L15 relevance (inference).** Any compile-time freeing scheme must treat an FFI call
  as an escape sink. Native kernel libraries for L9 tensors cross this boundary, so
  tensor buffers handed to BLAS-style kernels need a "borrowed for the call only" rule.

### 2.13 Layout compaction — 09 RF-20, Q09h; 08 OR-20, 08:98–100; 05:50–51
- **Mechanism.** Refinements could be packed into smaller storage; `Option<ref>` uses
  the null niche; `Result<T,()>` becomes `?T`.
- **Compile time:** layout choice. **Runtime:** smaller memory, better cache behaviour
  (inference).
- **Limits.** "Optional optimisation". Packing a `Bounded` changes the ABI at FFI,
  where 12 FFI-16 strips refinements (inference: packed storage and stripping need a
  defined rule).

### 2.14 Narrowing invalidation as an aliasing model — narrowing.md:311–327, N10/N11
- **Mechanism.** Calls that take `inout` reset narrowing, `borrow` calls do not, and
  "Mutation through `*ptr` where the pointer is derived from `x` | Resets (heap
  mutation invalidates)" (320).
- **L15 relevance (inference).** Whatever memory model L15 picks decides how precise
  facts about heap data can be. Automatic memory management with shared handles would
  make heap narrowing weaker.

---

## 3. Conflicts with L15, L16 and other locked decisions

### 3.1 L16 (IEEE floats; NaN and inf are ordinary values)
- **11-finite-floats.md:8–11** — "The contract requires either (a) `Fin<F>` refined
  type … or (b) explicit handling at each operation that may produce a non-finite." L16
  makes NaN and inf ordinary values, with no required tracking.
- **11 FF-05 (23)** — float→int cast "**Compile error** unless `x: Fin<f64>`".
- **11 FF-15 (33)** — "Float literal `1.5` … Refined to `Fin<f64>`".
- **11 FF-16 (34)** — NaN/inf literals "**never** assigned to `Fin<F>`" (fine as a
  library type, but it assumes `Fin` is central).
- **11 Q11a (111–117)** — includes "Strict: bare `f64` reserved; user must always wrap."
  Directly against L16.
- **11:99–102** — "The contract requires that bare `f64` *cannot* slip into a context
  where NaN propagation is unsafe".
- **04 NZ-17 (32)** — "Allowed, but result is non-finite; Gap 11 catches downstream".
- **09 RF-06 (24)** — `Fin<$F>` as a core refinement.
- **01 Gap-11 interaction (83–85)** — "`cast(int, x: Fin<f64>)` is a *lossless
  float→int* path". Also wrong on its face: a finite float can still exceed the integer
  range (inference).
- **conversions.md:223–246 and 312–313** — claims `number` has no NaN, and
  "The emission is a bare `@intFromFloat(usize, @floor(f))` — no NaN check".
  **Counterexample (inference, from IEEE semantics).** The guard at 300,
  `if f < 0 or f >= cast(number, n) { ret nil }`, lets NaN through, because both
  comparisons are false for NaN. `@intFromFloat` on NaN is then illegal behaviour in
  Zig and unchecked under ReleaseFast. Under L16 this elision is unsound.
- **narrowing.md:106 and 444–448** — "Float bound narrowing — same operators on
  `number`", together with "Negation: `if not p` narrows the else" and De Morgan. Under
  IEEE, `not (f < 0)` does not imply `f >= 0`. Float narrowing needs NaN as its own
  lattice element (inference).

### 3.2 L5 (Odin-style wrapping `+ - *`)
- **06 TA-03 (22)** "`i + 1` where `i: usize` with no range info … **Compile error**";
  **TA-05 (24)** "`a - b` … opaque `u32` … **Compile error**"; **TA-06 (25)**
  "auto-promote to `u16` or **compile error**"; **Q06b (126–132)** widening options.
  All superseded for `+ - *` (decisions.md:86).
- **06:7–10** "Under `-O ReleaseFast` these wrap silently — UB." Under L5 wrapping is
  defined behaviour and no longer UB, provided the emitted code uses `+%` (inference).
- **conversions.md:324–326** relies on "CA's bare arithmetic specialisation (D.003)".
  D.003 is superseded (decisions.md:81).
- **narrowing.md:51–54** lists "no overflow" among the obligations narrowing
  discharges, and **584–585** cites D.003.
- **09 RF-18 (36)** "refinement preservation through arithmetic … (modulo overflow)".
  Under wrapping, a `Bounded` sum may wrap, so preservation needs a no-wrap proof
  (inference).
- Not a conflict: 06 TA-15 `wrap_add` and TA-07/TA-08 negation and shifts are outside
  L5's scope (decisions.md:52–54).

### 3.3 L3/L4 (no `number`; explicit-width integers)
- **conversions.md:27–30** "`int`/`uint`/`number` as primary types; bit-width types as
  FFI-only". **36–48** numeric table. **76–80** "Bit-width types are warned in non-FFI
  code (CA D.002)". **233–235** "With `number` being arbitrary precision, every output
  that *would* fit in `int` does fit". All superseded (decisions.md:79–83).
- **narrowing.md** examples use `int`/`uint`/`number` throughout (e.g. 18–31, 104–106,
  264). **N6 (193–194)** "`total: int` … `i: uint`".
- **conversions.md:462–474** `parse_uint() -> ?uint`, `parts.length` as `uint`, which
  conflicts with the `usize` for lengths rule (CLAUDE.md, decisions.md:84).

### 3.4 No public address-of or dereference operators
- **03:93** "`var x: int; var p = &x; *p = 1; print x`"; **03:97** "`fill(&x)`";
  **03 DA-15 (32)** "`fill(&x)`".
- **01 C-27 (47)** "permitted only via explicit `&x as []u8` if at all".
- **10 Q10c (171–172)** "Address-of (`x.adr`) — does it produce a temporary borrow …";
  **10:137** "Address-of expressions (`&x`) — open question".
- **narrowing.md:320** "Mutation through `*ptr`".
- **02 N-19 (36)** "`defer if (p) |q| del q`" (Zig capture syntax in an A7 context,
  presented as the current form). **02:7–8, 18** describe today's `.?.*` deref, which is
  Zig output, not A7 syntax.

### 3.5 L6 (immutable argument bindings; no mode syntax approved)
- **narrowing.md:265, 270** `x: inout ?int`, `helper(inout x)`; **316–319** the
  borrow/inout table and "which they do". This assumes Cluster CC modes are adopted
  (decisions.md:87 says they are not).
- **10 AO-11..16** treat `borrow`/`inout`/`consume`/`set` as the decision target, but
  L6 approves only the principle (decisions.md:55–56).
- **narrowing.md:254–255** reassigns `b = nil`, where `b` is a function argument. Under
  L6 argument bindings are immutable, so the example is invalid.

### 3.6 L15 (automatic, compile-time, data-oriented memory)
- **10:7–9, AO-06 (30)** "`del p` … Consumes `p`" and **Q10e (175–178)**
  "**Recommendation**: no destructor; `del` is explicit and the type tracks it." This is
  manual freeing and conflicts with "something like garbage collection".
- **10 AO-36 (81)** "`Rc`/`Arc` shared ownership | Out of scope; consider regions".
  Consistent with "no runtime GC", but the regions it points to are never designed,
  so L15 has nothing to build on there.
- **10:125–127** "Algorithms that legitimately need shared mutable state (caches,
  observers). Mitigation: region-style scopes (out-of-scope for this gap; future work)".
- **02 N-06 (23)** / **N-09 (26)** assume storable `ref T` fields and slices of refs.
  This conflicts internally with 10's non-storable references (10:11–14), and would
  also conflict with a value-semantics L15 design (inference).
- **07 BI-14 (31)** stale length is "n/a (slices are immutable refs)". Growable,
  arena-backed data-oriented containers would break that invariant (inference).
- **Internal tension:** **12 FFI-27 (60)** wants callbacks to be "explicitly modeled
  with a `'static`-equivalent (open)", while **10 AO-33 (78)** refuses "`'static` and
  friends".

### 3.7 No-trap contract and no-unsafe claims vs trust points
- **README.md:20–26** "The language has no `unsafe` escape hatch" vs **12:8–9** FFI is
  "the **single** boundary at which the language stops enforcing safety", and **FFI-07**
  "foreign code promises non-null; documented as trust".
- **07 Q07d (128)** "`s[i]` (proved, panic otherwise)" vs narrowing.md:517–518, where a
  runtime assert is "**Forbidden by the contract**".
- **conversions.md:115** "All fallible cases use `?T`" vs its own revision note at
  15–18, which also allows `Result<T, E>`.

---

## 4. Hard cases and counterexamples mentioned

**Lifetimes and escapes**
- Refs cannot escape `borrow`/`inout` (10 AO-12/13).
- FFI retains a borrow after the call returns (12 FFI-23).
- Callbacks stored by foreign code (12 FFI-27, Q12e: "the borrow extends through the
  call").
- `defer` needs a value that was moved (10 AO-30).
- Closures capturing uninitialised or moved variables (03 DA-16; 10:115–117; 05 SB-14).

**Aliasing**
- `swap(inout x, inout x)` (AO-18). `arr[i]`/`arr[j]` with opaque indices (AO-20).
  `borrow x, borrow y` through pointers (AO-24).
- Address-taken locals defeating definite assignment (03:93–96).
- Two `inout`s of the same `i32` interleaving arithmetic (06:94–96).
- `f(borrow other)` where `other` aliases `x` (narrowing.md:319).
- Cast chains laundering a pointer: `cast(u32, cast(f32, x: ref T))` (01:119–123).
- Values re-emerging as a different pointer type through `extern fn` or dispatch (01:127–128).

**Cycles**
- Linked list and tree end-of-chain `?ref` (02 N-12).
- Parent/child mutual references pushed to an arena (10:130–132).
- Self-referential structs forbidden (AO-35).
- `examples/025_linked_list.a7` and `026_binary_tree.a7` flagged as the biggest
  refactors (10:143–145).

**Arenas, handles, regions**
- Parent-owned arena of indices (10:131–132). Regions deferred (10:81, 126–127). Cyclone
  regions paper (10:212–213). Handles appear only as `Index<n>` (07 BI-17) and
  `OpaqueRef<Tag>` (12 FFI-22).
- No generational or liveness handling for indices (inference: a gap).

**Partial initialisation and moves**
- Builders with half-built structs (02 N-22, Q02e; 03:103).
- Arrays of non-null refs (02 N-08, Q02d).
- Partial field move, then a whole move (10 AO-26..28).
- `new`-then-fill (03 DA-14).
- Moves on some branches only (AO-09) and in match arms (AO-10).

**Numeric and float**
- `INT_MIN / -1` (04 NZ-06). `-INT_MIN` (06 TA-07, 04 NZ-19). `INT_MIN.abs()` (06 TA-09).
- Shift at or above the bit width (04 NZ-16, 06 TA-08).
- `i64→f64` above 2^53 (01 C-09). Enum from an invalid integer (01 C-24). Slice →
  `[N]T` length (01 C-26).
- NaN passes a `<`/`>=` guard (conversions.md:300–313). Inference counterexample; see 3.1.
- Subnormals (11 FF-13) and rounding error (11:90–92). `tan` near π/2 (11 Q11f).

**Stack**
- Indirect calls forcing a worst-case budget (05 SB-16). Inlining changing frames
  (05:80–82). FFI frames (SB-09, 12 FFI-24). Signal handlers and `sigaltstack` (SB-11).

**Concurrency**
- Only peripheral: per-thread stack budgets (05 SB-10, SB-19, Q05e), signal-handler FFI
  (12 FFI-26), and "Threading / signal interaction — out of language scope" (12 Q12i).
- README.md:43 points to parameter-modes.md for "channels + isolated owned data". That
  file is outside this read set.

**Tensors and AI**
- **Not mentioned anywhere in the 14 files.** The only ergonomic note is that
  "Float-heavy code (DSP, graphics, ML) becomes wordy with `Fin<F>` wrappers" (11:96–98).

**Generics**
- Casts, ownership, definite assignment and stack frames must be re-checked for each
  instantiation (01:89–93; 10:138–139; 03 Q03f; 05 SB-15).
- Nullability default for `$T` (02 N-15, Q02c).

---

## 5. Open questions for the brainstorm

1. **What does "like GC" mean?** Jai, Odin and Zig are manual or arena languages with
   no automatic freeing. Which model should the compiler implement?
   - (a) Scope-based automatic frees on moves and last use (Rust drop elaboration /
     ASAP style), reversing 10 Q10e.
   - (b) Inferred regions or arenas (Tofte–Talpin / Cyclone / MLKit style).
   - (c) Explicit arenas or allocators with compile-time proof that nothing escapes
     (Odin/Zig plus a checker).
   - (d) Value semantics (Hylo) where heap data is owned by values and freed at scope exit.
   - (e) Generational handles, where use-after-free is detected at runtime (Vale-style).
     This would conflict with "resolved at compile time".
2. **Are references ever storable?** This is 10 Q10a. The choice decides whether
   lifetimes or regions must be inferred, and whether 02 N-06/N-09 (ref fields, ref
   slices) survive.
3. **What replaces pointers for data-oriented graphs** (trees, meshes, entity
   systems): arena plus typed index (`Handle<Pool>`)? If so, must stale-handle safety be
   proved at compile time? That needs remove/reuse rules the corpus lacks, since
   BI-14 is "n/a".
4. **Tensors (L7/L9).** Who owns the buffers? Does the autodiff tape use an arena
   scoped to one step? Can views and slices of a tensor exist without storable refs?
   How are buffers passed to native kernels under the FFI trust rules (12 FFI-19/23)?
5. **Does the stack-budget analysis (05) extend to scratch or temporary arenas?** A
   compile-time maximum scratch size per call DAG would be a proven version of Jai's
   temporary storage.
6. **Concurrency (L1).** Is data shared across threads only by move (isolated
   ownership), or do read-only borrows cross threads? How do per-thread arenas interact
   with automatic frees?
7. **Float→int under L16.** Should conversion return `?T` and check NaN, inf and range
   at runtime, or require a proof that includes a NaN check? Should narrowing model NaN
   explicitly so that `not (f < 0)` stops implying `f >= 0`?
8. **Is `Fin<F>` kept at all** (as an optional stdlib refinement), or dropped with 11?
9. **What proof obligations remain once `+ - *` wrap (L5)?** Division, shifts,
   negation and allocation-size arithmetic are still open. Should allocation-size
   multiplication (`n * size_of(T)`) be proved not to wrap, given that wrapping sizes are
   a classic memory bug?
10. **Destructors.** Does L15 need user-defined cleanup for resources that are not
    memory (files, GPU handles)? Or is cleanup memory-only while other resources use
    explicit `defer`?
11. **FFI allocator.** Q12h says "A7 owns its allocator". Must automatically managed A7
    memory ever be handed to C and retained? If so, what escape annotation is needed?
12. **Should G3 revive method-style conversions** now that types are explicit-width?
    Should `cast` stay for lossless widening only, given the D.024/D.038 contradiction?

---

## 6. External references worth following up

Cited in the files:
- **Hylo mutable value semantics**, <https://hylo-lang.org/introduction/>, and the
  **Hylo spec**, <https://hylo-lang.org/docs/reference/specification/> (10:207–208).
- **Rust NLL RFC 2094**, <https://rust-lang.github.io/rfcs/2094-nll.html> (10:209).
- **Swift SE-0176, exclusive access to memory**,
  <https://github.com/apple/swift-evolution/blob/main/proposals/0176-enforce-exclusive-access-to-memory.md>
  (10:210–211).
- **Cyclone regions paper**,
  <https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf> (10:212–213).
  The most direct L15 lead in this set.
- **Ada strongly typed subtypes**,
  <https://learn.adacore.com/courses/intro-to-ada/chapters/strongly_typed_language.html>
  (09:157–158).
- **SPARK declarations and types (static predicates)**,
  <https://docs.adacore.com/spark2014-docs/html/lrm/declarations-and-types.html> (09:159–161).
- **Ada `'Valid`**, `learn.adacore.com/courses/advanced-ada/parts/data_types/types.html`
  (11:144–148).
- **Ada interfacing with C**,
  `learn.adacore.com/courses/intro-to-ada/chapters/interfacing_with_c.html` (12:153–155).
- **Zig** `extern fn` and `@cImport` (12:156–157), and the `@intCast` / `@bitCast` /
  `@floatFromInt` family (conversions.md:183–184, 555).
- **Abstract interpretation tools and libraries:** CompCert, Polyspace, PIPS, PPL, Apron
  (narrowing.md:369–370). **SMT-backed verifiers:** SPARK/gnatprove, F\*, Dafny, Liquid
  Haskell, Z3, CVC5 (narrowing.md:374–380, 412–414).
- **Languages compared for conversions:** Kotlin, Rust, Python, JavaScript, Swift, Mojo
  (conversions.md:123–184, 545–556). **For narrowing:** Kotlin smart casts, TypeScript
  control-flow narrowing, C# NRT (narrowing.md:404–414).
- **Rust** `core::num::NonZeroI32` (04:126–127) and `MaybeUninit` (02 Q02e; 03 Q03h).
- **LLVM register-pressure heuristic** for spill estimation (05 SB-08, Q05b).

Suggested for L15, not cited in these files (inference):
- Tofte–Talpin region inference and the MLKit.
- Vale generational references.
- Lobster compile-time reference-count elision.
- Koka/Perceus reuse analysis.
- ASAP (Proust) static deallocation.
- Odin/Jai context allocator and temporary storage.
- Zig allocator interface.
