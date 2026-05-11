**SOUNDNESS**

The headline contract is stronger than the design can currently support. [05-for-a7.md](/home/air/Projects/pl/a7-py/docs/lang-safety/05-for-a7.md:13) says every safety hazard is compile-time caught and emitted Zig is safe under `ReleaseFast`; [07-language-review.md](/home/air/Projects/pl/a7-py/docs/lang-safety/07-language-review.md:27) then lists current critical gaps: nullable refs, unrestricted int-pointer casts, bare indexing, bare arithmetic, unchecked division. So today the contract is aspirational, not a design invariant.

The biggest unsoundness hole is D.003: arbitrary-precision `int`/`uint` arithmetic “never overflows” and transparently bignum-promotes [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:141). That promotion allocates. Allocation failure is data-dependent. But arithmetic returns direct `int`, not `?int` or `Result`. Under the zero-runtime-error contract, every bignum promotion must either be statically impossible, return fallibility, or have a proved non-failing allocator. The docs do not solve this.

`number` as “real number with infinite precision” [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:76) is worse. General exact real arithmetic makes equality, ordering, formatting, floor, and `to_int_exact()` semantically expensive and sometimes undecidable depending on representation. If `number` is rational/decimal/bigfloat, say so. If it is mathematical real, the compiler is promising magic.

Flow-sensitive narrowing is not enough for the claimed proof burden. The design admits v1 will not track cross-variable correlations or SMT predicates [compile-time-knowledge.md](/home/air/Projects/pl/a7-py/docs/lang-safety/compile-time-knowledge.md:320), while indexing/division/conversions rely on those proofs before codegen [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:1313). This means many safe programs fail, and any implementation bug becomes UB because codegen emits bare operations.

`borrow` preserving narrowings is only sound if “read-only” means deep immutable and no hidden mutation through aliases, globals, callbacks, FFI, async effects, or interior mutable cells. Crystal’s refusal to narrow repeated method calls after a nil check is exactly the warning sign: the value can change between calls unless captured locally. TypeScript’s narrowing is useful, but TypeScript explicitly documents unsound tradeoffs in its type system. Sources: TypeScript narrowing docs, TypeScript compatibility soundness note, Crystal narrowing limitation discussion.

FFI is treated as an exception, but the contract still says “zero runtime errors.” A corrupt FFI call can invalidate all alias/range/null proofs. The realistic contract is “zero A7-originated runtime errors outside trusted extern boundaries,” not unconditional zero runtime errors.

**ERGONOMICS**

D.025/D.039 turn common code into proof-shaping code. Users must write guards not because the program needs runtime behavior, but because the compiler needs a syntactic proof. That is SPARK-style programming, not Python/JS-feel. SPARK makes this work with explicit contracts, subtypes, loop invariants, and a verifier; A7 wants the same safety while hiding all proof terms. That is the worst ergonomics point: users get SPARK rejection without SPARK’s explicit proof vocabulary.

Removing `unwrap()` is consistent with the contract, but then also making many naturally fallible things compile errors instead of `?T` removes recovery composition. Example: slice-to-array conversion with opaque length is forced into a guard, while a `?[N]T` form would be the ergonomic total API. D.025’s bias against `?T` will make APIs brittle.

Parameter-mode inference from function body is a code-review trap. If a private edit changes a helper from read-only to mutating, every caller’s aliasing/move obligations can change. Without caller-side sigils, `foo(x)` gives no visible clue whether it borrows, mutates, or consumes. If modes are inferred but exported in the compiled interface, public APIs become body-dependent. If they are not exported, separate compilation is impossible.

No storable references blocks observer patterns, graph structures, arenas with direct links, callback state, intrusive collections, views into buffers, and many parsers. The docs admit users must rewrite with indices [parameter-modes.md](/home/air/Projects/pl/a7-py/docs/lang-safety/parameter-modes.md:249). That is fine for a safety language, but it is not Python/JS ergonomics.

**PERFORMANCE**

Arbitrary precision by default is not “typical case no cost.” V8’s BigInt docs explicitly warn that arbitrary precision is a separate domain and that polyfilling operator behavior would require replacing every operator with type-checking calls at unacceptable runtime/file-size cost. Python integers are heap objects of arbitrary size; CPython even documents `PyLongObject` as the representation for all ints. Sources: V8 BigInt, V8 implementation notes, Python C API integer docs.

Range-tracked specialization is JIT-shaped, but A7 is an ahead-of-time compiler emitting Zig. LuaJIT/V8 can deopt when speculation fails. A7 cannot cheaply deopt unless it emits tagged numeric values and slow paths everywhere. That means either pervasive branches/tags or many compile errors. The design handwaves the hardest part: stable representation and calling convention for values that may be machine int in one path and bignum in another.

`number` is a performance cliff. Infinite precision real math plus string formatting and comparisons will drag big rational/decimal libraries into ordinary code. If `f"..."` implicitly formats arbitrary precision values [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:281), formatting can allocate and fail too.

Channels plus isolated heaps copy or move ownership. Large immutable snapshots cannot be shared across tasks in v1; the docs admit Pony’s `val` capability is lost [parameter-modes.md](/home/air/Projects/pl/a7-py/docs/lang-safety/parameter-modes.md:330). That is a predictable throughput cliff for config tables, ASTs, bytecode, intern pools, and caches.

**IMPLEMENTATION**

“One pass, few hundred lines” is not credible [compile-time-knowledge.md](/home/air/Projects/pl/a7-py/docs/lang-safety/compile-time-knowledge.md:330). This pass becomes: CFG construction, path-sensitive narrowing, loop induction, disjunctive intervals, invalidation, alias analysis, move/partial move analysis, destructor insertion, generic instantiation, diagnostics, and codegen proof markers. Rust’s NLL/Polonius history shows even mature teams still hit false positives in borrow analysis. Source: Rust NLL/Polonius blog.

Stack safety is underspecified. Banning recursion does not prove no stack overflow: large stack arrays, nested generic expansion, backend helper calls, spawned task stack sizes, and bignum/library frames all need accounting. The docs list stack-budget proof [05-for-a7.md](/home/air/Projects/pl/a7-py/docs/lang-safety/05-for-a7.md:97) but do not define a computable stack model.

Auto-drop plus partial moves is compiler engineering, not sugar. You need precise drop flags at CFG joins, reverse drop order, explicit `del` precedence, moved-field handling, panic-free destructors, and interaction with `return`, loops, and channels. Since runtime traps are forbidden, destructor failure must also be impossible or typed.

**INCONSISTENCIES**

D.024 says `cast(T, x)` is the universal conversion operator and is accepted [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:760). D.038 says `cast(T, x)` is removed and is accepted [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:1290). Both cannot be true. Many later examples still use `cast()` after D.038.

The cluster index says CB is accepted [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:43), but the CB section ends with “PROPOSED” [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:1451). The document is not internally authoritative.

D.025 classifies `EnumT::from_discriminant(i)` where `i` is runtime as data-dependent returning `?T` [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:804). D.032 later says it returns `EnumT` directly and compile-errors unless range-proved. Pick one.

D.025 mentions `[N]T::try_from(s)` as statically resolvable; D.031 rejects `try_from` and uses direct `[N]T::from(s)`. This is not naming drift; it changes whether opaque runtime length can be handled as data.

D.003 arbitrary-precision arithmetic contradicts the original [05-for-a7.md](/home/air/Projects/pl/a7-py/docs/lang-safety/05-for-a7.md:91) contract table that bare arithmetic on opaque integers must be checked/wrapped/saturated/proved. The new design removed user-visible arithmetic choices but did not replace the failure story for allocation.

The newest direction says parameter modes should be inferred from the body. The docs still propose explicit modes in signatures [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:1545). Body-inferred modes also contradict D.042’s claim that the function signature is the source of truth [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:1578).

**PRECEDENT-BASED RED FLAGS**

SPARK proves absence of runtime errors, but it does so with flow analysis, proof, preconditions, postconditions, subtype constraints, and loop invariants. AdaCore says 95-98% of runtime checks are typically automatic, with remaining checks manually proved or justified. That is the realistic bar. A7 currently claims SPARK-tier results without SPARK-tier annotations. Sources: SPARK user guide, proof manual, loop invariant rationale.

Swift did not rely on purely static exclusivity. Swift 5 enabled runtime exclusivity checks in Release builds. That is a direct warning against A7’s “static only, no checks” `inout` story. Source: Swift exclusivity enforcement.

Pony needed six reference capabilities plus `recover` to support safe actor sharing without locks. A7 intentionally drops shared immutable cross-task values. That simplifies the type system but cuts expressiveness and forces copying. Sources: Pony reference capabilities, Pony passing/sharing.

Inko’s isolated-process model still needs ownership categories, borrows, unique references, `recover`, and sendability rules. It even documents a runtime panic case when an owned value is dropped while borrows exist. A7’s “channels + isolated heaps” needs the same depth or it will either be unsound or unusable. Sources: Inko memory management, Inko concurrency/recovery.

Rust’s cast history is a warning for `cast()`: Clippy has lints for `as` because it silently performs lossy and dangerous conversions, and recommends `try_from()` for truncation-sensitive cases. A universal `cast(T, x)` is review-hostile unless every conversion family is visibly distinct. Sources: Rust Clippy `as_conversions`, `cast_possible_truncation`.

Hylo and Mojo do not validate the inference fantasy. Hylo has explicit `let`, `inout`, `sink`, `set` conventions and complex lifetime/projection rules. Mojo documents ownership and argument conventions explicitly. They reduced lifetime annotation burden; they did not make public mutation/consumption modes disappear into body inference. Sources: Hylo spec/language tour, Mojo ownership docs.

**WHAT THIS DESIGN LIKELY GETS WRONG**

A7 is trying to combine Python/JS surface ergonomics, SPARK absence-of-runtime-errors, Rust/Hylo ownership, Pony/Inko concurrency, and V8/LuaJIT numeric performance. Those systems pay visible costs: annotations, runtime checks, JIT/deopt machinery, capability types, recovery blocks, or explicit failure values. A7 currently hides the costs in “the compiler knows.”

The likely correction is harsh: either add visible proof/API surface (`NonZero`, bounded indices, pre/postconditions, sendable/unique types, explicit parameter modes), or weaken the guarantee to “no unchecked A7-originated traps for accepted proven patterns; otherwise typed runtime checks.” The current version promises too much invisibility. That is where it will break.
tokens used
163,141
**SOUNDNESS**

The headline contract is stronger than the design can currently support. [05-for-a7.md](/home/air/Projects/pl/a7-py/docs/lang-safety/05-for-a7.md:13) says every safety hazard is compile-time caught and emitted Zig is safe under `ReleaseFast`; [07-language-review.md](/home/air/Projects/pl/a7-py/docs/lang-safety/07-language-review.md:27) then lists current critical gaps: nullable refs, unrestricted int-pointer casts, bare indexing, bare arithmetic, unchecked division. So today the contract is aspirational, not a design invariant.

The biggest unsoundness hole is D.003: arbitrary-precision `int`/`uint` arithmetic “never overflows” and transparently bignum-promotes [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:141). That promotion allocates. Allocation failure is data-dependent. But arithmetic returns direct `int`, not `?int` or `Result`. Under the zero-runtime-error contract, every bignum promotion must either be statically impossible, return fallibility, or have a proved non-failing allocator. The docs do not solve this.

`number` as “real number with infinite precision” [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:76) is worse. General exact real arithmetic makes equality, ordering, formatting, floor, and `to_int_exact()` semantically expensive and sometimes undecidable depending on representation. If `number` is rational/decimal/bigfloat, say so. If it is mathematical real, the compiler is promising magic.

Flow-sensitive narrowing is not enough for the claimed proof burden. The design admits v1 will not track cross-variable correlations or SMT predicates [compile-time-knowledge.md](/home/air/Projects/pl/a7-py/docs/lang-safety/compile-time-knowledge.md:320), while indexing/division/conversions rely on those proofs before codegen [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:1313). This means many safe programs fail, and any implementation bug becomes UB because codegen emits bare operations.

`borrow` preserving narrowings is only sound if “read-only” means deep immutable and no hidden mutation through aliases, globals, callbacks, FFI, async effects, or interior mutable cells. Crystal’s refusal to narrow repeated method calls after a nil check is exactly the warning sign: the value can change between calls unless captured locally. TypeScript’s narrowing is useful, but TypeScript explicitly documents unsound tradeoffs in its type system. Sources: TypeScript narrowing docs, TypeScript compatibility soundness note, Crystal narrowing limitation discussion.

FFI is treated as an exception, but the contract still says “zero runtime errors.” A corrupt FFI call can invalidate all alias/range/null proofs. The realistic contract is “zero A7-originated runtime errors outside trusted extern boundaries,” not unconditional zero runtime errors.

**ERGONOMICS**

D.025/D.039 turn common code into proof-shaping code. Users must write guards not because the program needs runtime behavior, but because the compiler needs a syntactic proof. That is SPARK-style programming, not Python/JS-feel. SPARK makes this work with explicit contracts, subtypes, loop invariants, and a verifier; A7 wants the same safety while hiding all proof terms. That is the worst ergonomics point: users get SPARK rejection without SPARK’s explicit proof vocabulary.

Removing `unwrap()` is consistent with the contract, but then also making many naturally fallible things compile errors instead of `?T` removes recovery composition. Example: slice-to-array conversion with opaque length is forced into a guard, while a `?[N]T` form would be the ergonomic total API. D.025’s bias against `?T` will make APIs brittle.

Parameter-mode inference from function body is a code-review trap. If a private edit changes a helper from read-only to mutating, every caller’s aliasing/move obligations can change. Without caller-side sigils, `foo(x)` gives no visible clue whether it borrows, mutates, or consumes. If modes are inferred but exported in the compiled interface, public APIs become body-dependent. If they are not exported, separate compilation is impossible.

No storable references blocks observer patterns, graph structures, arenas with direct links, callback state, intrusive collections, views into buffers, and many parsers. The docs admit users must rewrite with indices [parameter-modes.md](/home/air/Projects/pl/a7-py/docs/lang-safety/parameter-modes.md:249). That is fine for a safety language, but it is not Python/JS ergonomics.

**PERFORMANCE**

Arbitrary precision by default is not “typical case no cost.” V8’s BigInt docs explicitly warn that arbitrary precision is a separate domain and that polyfilling operator behavior would require replacing every operator with type-checking calls at unacceptable runtime/file-size cost. Python integers are heap objects of arbitrary size; CPython even documents `PyLongObject` as the representation for all ints. Sources: V8 BigInt, V8 implementation notes, Python C API integer docs.

Range-tracked specialization is JIT-shaped, but A7 is an ahead-of-time compiler emitting Zig. LuaJIT/V8 can deopt when speculation fails. A7 cannot cheaply deopt unless it emits tagged numeric values and slow paths everywhere. That means either pervasive branches/tags or many compile errors. The design handwaves the hardest part: stable representation and calling convention for values that may be machine int in one path and bignum in another.

`number` is a performance cliff. Infinite precision real math plus string formatting and comparisons will drag big rational/decimal libraries into ordinary code. If `f"..."` implicitly formats arbitrary precision values [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:281), formatting can allocate and fail too.

Channels plus isolated heaps copy or move ownership. Large immutable snapshots cannot be shared across tasks in v1; the docs admit Pony’s `val` capability is lost [parameter-modes.md](/home/air/Projects/pl/a7-py/docs/lang-safety/parameter-modes.md:330). That is a predictable throughput cliff for config tables, ASTs, bytecode, intern pools, and caches.

**IMPLEMENTATION**

“One pass, few hundred lines” is not credible [compile-time-knowledge.md](/home/air/Projects/pl/a7-py/docs/lang-safety/compile-time-knowledge.md:330). This pass becomes: CFG construction, path-sensitive narrowing, loop induction, disjunctive intervals, invalidation, alias analysis, move/partial move analysis, destructor insertion, generic instantiation, diagnostics, and codegen proof markers. Rust’s NLL/Polonius history shows even mature teams still hit false positives in borrow analysis. Source: Rust NLL/Polonius blog.

Stack safety is underspecified. Banning recursion does not prove no stack overflow: large stack arrays, nested generic expansion, backend helper calls, spawned task stack sizes, and bignum/library frames all need accounting. The docs list stack-budget proof [05-for-a7.md](/home/air/Projects/pl/a7-py/docs/lang-safety/05-for-a7.md:97) but do not define a computable stack model.

Auto-drop plus partial moves is compiler engineering, not sugar. You need precise drop flags at CFG joins, reverse drop order, explicit `del` precedence, moved-field handling, panic-free destructors, and interaction with `return`, loops, and channels. Since runtime traps are forbidden, destructor failure must also be impossible or typed.

**INCONSISTENCIES**

D.024 says `cast(T, x)` is the universal conversion operator and is accepted [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:760). D.038 says `cast(T, x)` is removed and is accepted [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:1290). Both cannot be true. Many later examples still use `cast()` after D.038.

The cluster index says CB is accepted [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:43), but the CB section ends with “PROPOSED” [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:1451). The document is not internally authoritative.

D.025 classifies `EnumT::from_discriminant(i)` where `i` is runtime as data-dependent returning `?T` [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:804). D.032 later says it returns `EnumT` directly and compile-errors unless range-proved. Pick one.

D.025 mentions `[N]T::try_from(s)` as statically resolvable; D.031 rejects `try_from` and uses direct `[N]T::from(s)`. This is not naming drift; it changes whether opaque runtime length can be handled as data.

D.003 arbitrary-precision arithmetic contradicts the original [05-for-a7.md](/home/air/Projects/pl/a7-py/docs/lang-safety/05-for-a7.md:91) contract table that bare arithmetic on opaque integers must be checked/wrapped/saturated/proved. The new design removed user-visible arithmetic choices but did not replace the failure story for allocation.

The newest direction says parameter modes should be inferred from the body. The docs still propose explicit modes in signatures [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:1545). Body-inferred modes also contradict D.042’s claim that the function signature is the source of truth [08-decisions.md](/home/air/Projects/pl/a7-py/docs/lang-safety/08-decisions.md:1578).

**PRECEDENT-BASED RED FLAGS**

SPARK proves absence of runtime errors, but it does so with flow analysis, proof, preconditions, postconditions, subtype constraints, and loop invariants. AdaCore says 95-98% of runtime checks are typically automatic, with remaining checks manually proved or justified. That is the realistic bar. A7 currently claims SPARK-tier results without SPARK-tier annotations. Sources: SPARK user guide, proof manual, loop invariant rationale.

Swift did not rely on purely static exclusivity. Swift 5 enabled runtime exclusivity checks in Release builds. That is a direct warning against A7’s “static only, no checks” `inout` story. Source: Swift exclusivity enforcement.

Pony needed six reference capabilities plus `recover` to support safe actor sharing without locks. A7 intentionally drops shared immutable cross-task values. That simplifies the type system but cuts expressiveness and forces copying. Sources: Pony reference capabilities, Pony passing/sharing.

Inko’s isolated-process model still needs ownership categories, borrows, unique references, `recover`, and sendability rules. It even documents a runtime panic case when an owned value is dropped while borrows exist. A7’s “channels + isolated heaps” needs the same depth or it will either be unsound or unusable. Sources: Inko memory management, Inko concurrency/recovery.

Rust’s cast history is a warning for `cast()`: Clippy has lints for `as` because it silently performs lossy and dangerous conversions, and recommends `try_from()` for truncation-sensitive cases. A universal `cast(T, x)` is review-hostile unless every conversion family is visibly distinct. Sources: Rust Clippy `as_conversions`, `cast_possible_truncation`.

Hylo and Mojo do not validate the inference fantasy. Hylo has explicit `let`, `inout`, `sink`, `set` conventions and complex lifetime/projection rules. Mojo documents ownership and argument conventions explicitly. They reduced lifetime annotation burden; they did not make public mutation/consumption modes disappear into body inference. Sources: Hylo spec/language tour, Mojo ownership docs.

**WHAT THIS DESIGN LIKELY GETS WRONG**

A7 is trying to combine Python/JS surface ergonomics, SPARK absence-of-runtime-errors, Rust/Hylo ownership, Pony/Inko concurrency, and V8/LuaJIT numeric performance. Those systems pay visible costs: annotations, runtime checks, JIT/deopt machinery, capability types, recovery blocks, or explicit failure values. A7 currently hides the costs in “the compiler knows.”

The likely correction is harsh: either add visible proof/API surface (`NonZero`, bounded indices, pre/postconditions, sendable/unique types, explicit parameter modes), or weaken the guarantee to “no unchecked A7-originated traps for accepted proven patterns; otherwise typed runtime checks.” The current version promises too much invisibility. That is where it will break.
