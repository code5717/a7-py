# Comparative: Cyclone

> Phase B artifact in the `docs/lang-safety/` research process.

Cyclone (2002–2008) was the **first serious attempt to add memory
safety to C without abandoning C's surface syntax**. It introduced
**region-based memory management**, **fat pointers**, **non-null
access types**, and **tagged unions** — many of which are now
standard in safer-C dialects (`-fbounds-safety` for Apple,
SPARK access types, etc.).

Cyclone is **directly relevant to A7** because:

1. Cyclone reports **8 % of legacy-C lines needed changing** to
   port to Cyclone — the closest empirical data we have to A7's
   adoption story.
2. Cyclone's **region inference** is the prior art for A7's
   region scopes (Gap 10's fallback).
3. Cyclone's design choices show **which Ada/Rust mechanisms are
   needed for safety and which add complexity for less safety
   gain**.

Primary sources:

- [Cyclone project page](https://cyclone.thelanguage.org/)
- [Cyclone region paper (Grossman et al., PLDI 2002)](https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf)
- ["Safe Manual Memory Management in Cyclone" (Swamy et al.)](https://www.cs.umd.edu/projects/PL/cyclone/scp.pdf)
- ["Cyclone: A safe dialect of C" (Jim et al., USENIX 2002)](http://www.cs.umd.edu/projects/cyclone/papers/cyclone-safety.pdf)
- [Grossman's thesis on safe programming at the C level](https://homes.cs.washington.edu/~djg/papers/grossman_thesis.pdf)

---

## How Cyclone handles each gap

### Gap 01 — Cast

Cyclone retained C casts but **restricted them**:

- Pointer↔int casts: still allowed but flagged by the type system
  as "tainted" — accessing through a tainted pointer fails at
  compile time.
- Unsafe reinterpretation: requires explicit
  `_unsafe_cast<T>(x)` form.
- Numeric casts: same as C.

**What A7 can steal:** the **named `_unsafe_cast` form** as the
single escape. A7 takes a stricter line (no escape at all), but
the discipline of naming the dangerous operation is clear.

---

### Gap 02 — Nullable pointers

Cyclone introduced **three** pointer flavours:

- `T *@nullable` — may be null (the C default behaviour).
- `T *@notnull` — never null; deref doesn't need a check.
- `T ?` — **fat pointer** for arrays / strings (carries length
  alongside the address).

The `T *@notnull` syntax (and the inverse default) is the
ancestor of Ada's `not null` access types and A7's `ref T`.

**What A7 can steal:** the **three-flavour design** —
non-null, nullable, fat-pointer-for-arrays. A7's `ref T`,
`?ref T`, and `[]T` (slice) map directly.

---

### Gap 03 — Definite assignment

Cyclone enforced definite-assignment via a flow analysis. The
2002 paper documents the cost: a handful of false positives
forced rewrites; most code was unaffected.

---

### Gap 04 — `NonZero` division

Cyclone did not have refinement types. Division by zero remains
a runtime trap.

---

### Gap 05 — Stack budget

Not addressed. Cyclone allowed recursion.

---

### Gap 06 — Typed arithmetic

Cyclone did not have ranged subtypes. C's integer arithmetic
semantics were preserved.

---

### Gap 07 — Bounded indexing — **fat pointers**

The headline Cyclone feature for arrays. The fat pointer `T ?`
carries `(ptr, size)`; indexing is checked at runtime against
the size. Cyclone also provided `T @numelts(n)` for compile-time-
known sizes (rare in practice).

The 2002 paper reports that fat pointers cost ~5–10 % runtime
overhead and were ergonomically acceptable.

**What A7 can steal:** the **fat-pointer-by-default** model for
arrays / slices. A7 already does this via `[]T`.

---

### Gap 08 — `Option<T>` / `Result<T, E>`

Cyclone introduced **tagged unions** (C's discriminated unions
with a type-system-enforced tag). The Cyclone tagged union is
the direct ancestor of Rust's `enum`, Ada's discriminated
records, and Swift/Hylo's `enum`.

```cyclone
tagged union Result_t {
    int Ok;
    char *Err;
};
```

The compiler enforces tag access — accessing `.Ok` when the tag
is `Err` is a compile or runtime error.

**What A7 can steal:** A7 already has tagged unions. The
Cyclone validation confirms the model works.

---

### Gap 09 — Refinement-lite

Cyclone did not have refinement types beyond the `@notnull` /
`@numelts` annotations on pointers.

---

### Gap 10 — Affine ownership — **regions**

**This is Cyclone's headline contribution.**

Cyclone introduced **lexically-scoped regions**:

```cyclone
{
    region r;                       // declare a region
    int *@region(r) p = rnew(r, 0);  // allocate in r
    // ...
}                                    // region r is freed; p is invalid past this scope
```

Region annotations are **inferred by default**; the user only
writes them at function signatures with cross-region references.

The paper reports:

> "Porting legacy C to Cyclone has required altering about 8 %
> of the code; of the changes, only 6 % (of the 8 %) were region
> annotations."

Most allocations don't need explicit annotations; the inference
picks the right region.

**What A7 can steal:** the **lexically-scoped region** pattern as
the **fallback for allocations that don't fit affine ownership**
(Gap 10 §3.6, also Gap 05 — stack-shaped scopes give
predictable stack budgets).

A7's region scopes would look like:

```a7
region tokens
    first := new Token{...}     ; allocated in `tokens`
    ; ...
end                              ; everything in `tokens` is freed here
```

The Cyclone experience suggests this is **highly ergonomic**
when combined with inference.

**What A7 should not steal:** Cyclone's full **region
polymorphism** (`fn f<r>(p: T *@region(r))`). It adds significant
type-system complexity and most code doesn't need it. A7 should
ship the lexical form first and consider polymorphism only if
real use cases demand it.

---

### Gap 11 — Finite floats

Not addressed. Floats follow IEEE 754 as in C.

---

### Gap 12 — FFI

Cyclone is itself a C-compatible dialect, so the FFI surface
is "everything." Specific calls into unmodified C libraries
require careful pointer-flavour annotation at the boundary.

**What A7 can steal:** **the empirical observation that
boundary annotations are tractable**. Most foreign signatures
can be annotated by hand or with a small tool.

---

## Primary sources

- [Cyclone region paper](https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf)
- ["Safe Manual Memory Management in Cyclone"](https://www.cs.umd.edu/projects/PL/cyclone/scp.pdf)
- ["Cyclone: A safe dialect of C"](http://www.cs.umd.edu/projects/cyclone/papers/cyclone-safety.pdf)
- [Grossman's thesis](https://homes.cs.washington.edu/~djg/papers/grossman_thesis.pdf)

---

## What A7 can steal — consolidated

1. **Lexically-scoped regions** with inference (Gap 10
   fallback). Combine with the recursion ban to get a bounded
   region tree.
2. **The three-flavour pointer design** (non-null, nullable,
   fat) — already in A7 as `ref T`, `?ref T`, `[]T`.
3. **Tagged unions** — already in A7.
4. **The empirical 8 % migration cost** as the benchmark for A7's
   migration story.
5. **Region inference + region annotation at function signatures**
   — defaulting strategy.

## What A7 should not steal

1. **Full region polymorphism** (`'a` lifetimes) — too complex
   for the marginal benefit. The lexical form covers the
   common case.
2. **`_unsafe_cast`** — A7 has no escape.
3. **Runtime bounds checks on fat pointers** — A7 proves the
   bound statically and emits the unchecked access.

## Cyclone's lessons for A7

The single biggest insight: **inference is what makes safety
ergonomic.** Cyclone's region annotations are a small fraction
of total code (~0.5 % of lines) because the inferencer handles
the common case. A7's region scopes (when added) should follow
the same pattern: lexical declaration with no annotation needed
for the typical case.

The second insight: **the boundary between safe and unsafe code
is at the function signature.** Cyclone annotates pointer
flavour at signatures; the body's inference fills in the rest.
A7 should do the same for parameter modes (Hylo's approach) and
region annotations.
