# Gemini comparison of reuse-oriented memory strategies

Source: produced by Gemini and supplied by the user on 2026-09-15. The table is
preserved exactly. The annotations were first written from general knowledge. On
2026-09-16 the Koka, Lean 4, Roc and Carp annotations were rewritten from the
[storage reuse study](reuse-languages.md). The MLKit annotation is unchecked.

## Supplied table

| Language | Paradigm | Primary strategy | In-place mutation allowed? |
| --- | --- | --- | --- |
| Koka | Strongly typed, effect-based | Perceus RC + Reuse Analysis | Yes, if rc == 1 |
| Lean 4 | Dependently typed, pure | Optimized Ref Counting | Yes, if unshared |
| Roc | Pure functional, app-focused | Optimized RC + Borrowing | Yes (mutable updates) |
| ML Kit | Standard ML dialect | Static Region Inference | No (pure allocation) |
| Carp | Lisp / Functional syntax | Borrow checking & lifetimes | Yes (imperative core) |

## Annotations

- **Koka, Lean 4 and Roc** place reuse at compile time and decide uniqueness
  with a runtime count test. The study found no static removal of that test in
  Lean 4. Koka keeps it in the shipped compiler, including for `fip` functions.
  Roc proves some values unique statically; the mechanism that then skips the
  test is reported only by DeepWiki. The runtime test conflicts with L15 unless
  A7 proves uniqueness statically.
- **Koka** uses Perceus (Reinking, Xie, de Moura and Leijen, PLDI 2021). The
  later FP² paper (ICFP 2023) checks in-place execution of a function definition
  statically and leaves call sites to uniqueness types or runtime checks.
- **Lean 4** uses "Counting Immutable Beans" (Ullrich and de Moura, IFL 2019),
  not Perceus. It infers borrowed parameters, which avoid count updates.
- **Roc** counts atomically by default. Its current Zig compiler keeps only
  narrow reuse rewrites; the general reuse pass of its earlier Rust compiler was
  not found. Roc has reassignable `var` bindings, so "pure functional" needs a
  qualifier: values are immutable, local bindings are not.
- **MLKit** regions are inferred statically. Standard ML still has mutable `ref`
  cells and arrays, so "No" likely means region inference itself does not reuse
  storage in place. MLKit can also combine regions with a garbage collector.
  Unchecked.
- **Carp** frees at the end of lexical scope with no runtime counts, except a
  `delete` function pointer carried by each closure. No compiler-inserted reuse
  was found in the two compiler files checked. In 2017 its author said Carp did
  not yet separate mutable and immutable references. The earlier claim that Carp
  is the closest of the five to a statically resolved model is withdrawn,
  because MLKit was not checked.
- **A7 relevance:** Koka, Lean 4 and Roc get in-place update from static
  placement plus a runtime uniqueness test. Carp places frees statically; no
  compiler-inserted reuse was found in the files checked. L15 and L18 ask for
  reuse without the runtime test. GLM's advice proposes deriving uniqueness from
  affine ownership (`advice-glm.md`, layer 5). In the memory plan, layer 6,
  "Proven-unobservable copy removal, in-place update", depends on layer 2,
  internal ownership. The plan does not name a uniqueness analysis.
