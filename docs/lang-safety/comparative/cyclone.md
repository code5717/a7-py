# Comparative: Cyclone

Status: Phase B study written before 2026-09-14; dated notes mark superseded A7 points, and current decisions are in [decisions.md](../../plan/decisions.md) and the [memory plan](../../plan/memory.md).

## Summary

Cyclone (2002–2008) was the first serious attempt to add memory safety to C
while keeping C's surface syntax. It introduced region-based memory management,
fat pointers, non-null pointer types and tagged unions. Many of these ideas now
appear in safer C dialects, such as Apple's `-fbounds-safety`, and in SPARK
access types.

Cyclone matters to A7 for three reasons:

1. Porting legacy C to Cyclone changed about 8% of lines. This is the closest
   empirical data for A7's adoption story.
2. Cyclone's region inference is prior art for A7's region scopes (the Gap 10
   fallback).
3. Its design shows which Ada and Rust mechanisms safety needs, and which add
   complexity for little safety gain.

## Per-gap findings

| Gap | Cyclone |
| --- | --- |
| 03 Definite assignment | Enforced by flow analysis. The 2002 paper reports a handful of false positives that forced rewrites; most code was unaffected. |
| 04 `NonZero` division | No refinement types. Division by zero is a runtime trap. |
| 05 Stack budget | Not addressed. Recursion is allowed. |
| 06 Typed arithmetic | No ranged subtypes. C integer semantics are kept. |
| 09 Refinement-lite | None beyond the `@notnull` and `@numelts` pointer annotations. |
| 11 Finite floats | Not addressed. Floats follow IEEE 754 as in C. |

### Gap 01 — Cast

Cyclone kept C casts but restricted them:

- Pointer-to-int casts are allowed, but the type system marks the result as
  "tainted". Access through a tainted pointer fails at compile time.
- Unsafe reinterpretation needs the explicit form `_unsafe_cast<T>(x)`.
- Numeric casts behave as in C.

A7 can adopt the discipline of naming the dangerous operation. A7 takes a
stricter line and has no escape at all.

> Note (2026-09-16): A7's cast design is open under gate G3; see
> [decisions.md](../../plan/decisions.md).

### Gap 02 — Nullable pointers

Cyclone has three pointer kinds:

- `T *@nullable`: may be null (C's default behavior).
- `T *@notnull`: never null, so dereference needs no check.
- `T ?`: a fat pointer for arrays and strings; it carries the length with the
  address.

`T *@notnull` and the inverse default are an early form of the idea behind
Ada's `not null` access types and A7's `ref T`.

A7 can adopt the three-kind design: non-null, nullable, and fat pointer for
arrays. A7's `ref T`, `?ref T` and `[]T` map to it directly.

> Note (2026-09-16): The memory plan removes stored `ref` values and `nil`
> (gates M4 and M13). Absence uses optionals, `ref` remains only as a parameter,
> and slices become temporary views. See [memory.md](../../plan/memory.md)
> section 3.

### Gap 07 — Bounded indexing: fat pointers

Fat pointers are Cyclone's main array feature. `T ?` carries `(ptr, size)`, and
each index is checked at run time against the size. `T @numelts(n)` expresses a
compile-time-known size, but was rare in practice.

The 2002 paper reports about 5–10% runtime overhead for fat pointers, with
acceptable ergonomics.

A7 already uses the fat-pointer model by default through `[]T`.

### Gap 08 — `Option<T>` / `Result<T, E>`

Cyclone added tagged unions: C unions whose tag the type system enforces. This
brings the sum types of ML-family languages to C, the same idea as Rust's
`enum`, Ada's discriminated records and the `enum` of Swift and Hylo.

```cyclone
tagged union Result_t {
    int Ok;
    char *Err;
};
```

Accessing `.Ok` when the tag is `Err` is a compile-time or runtime error.

A7 already has tagged unions. Cyclone's experience confirms that the model
works.

### Gap 10 — Affine ownership: regions

Regions are Cyclone's main contribution. A region is lexically scoped:

```cyclone
{
    region r;                       // declare a region
    int *@region(r) p = rnew(r, 0);  // allocate in r
    // ...
}                                    // region r is freed; p is invalid past this scope
```

Region annotations are inferred by default. Users write them only on function
signatures that pass references across regions. The paper reports:

> "Porting legacy C to Cyclone has required altering about 8 % of the code; of
> the changes, only 6 % (of the 8 %) were region annotations."

Most allocations need no annotation because inference picks the right region.

A7 can adopt lexically scoped regions as the fallback for allocations that do
not fit affine ownership (Gap 10). Stack-shaped scopes also give predictable
stack budgets (Gap 05). The Phase B sketch of A7 region scopes was:

```a7
region tokens
    first := new Token{...}     ; allocated in `tokens`
    ; ...
end                              ; everything in `tokens` is freed here
```

Cyclone's experience suggests that this is ergonomic when combined with
inference.

A7 should not adopt Cyclone's full region polymorphism
(`fn f<r>(p: T *@region(r))`). It adds much type-system complexity, and most
code does not need it. Ship the lexical form first; add polymorphism only if
real use cases demand it.

> Note (2026-09-16): The region sketch above is historical. The memory plan makes
> extents compiler-inferred and invisible: no `region` block, no `new`, no `del`,
> and no memory vocabulary in source (L15, L17, L19; memory plan contract item 9
> and gates M3, M11). The Cyclone lesson that inference carries the common case
> still applies, now to the whole program. See
> [memory.md](../../plan/memory.md).

### Gap 12 — FFI

Cyclone is itself a C-compatible dialect, so its FFI surface is all of C. Calls
into unmodified C libraries need careful pointer-kind annotations at the
boundary.

A7 can take the empirical lesson that boundary annotations are tractable. Most
foreign signatures can be annotated by hand or with a small tool.

## What A7 should adopt

1. Lexically scoped regions with inference, as the Gap 10 fallback. Combined
   with the recursion ban, they give a bounded region tree.
2. The three pointer kinds (non-null, nullable, fat), already in A7 as `ref T`,
   `?ref T` and `[]T`.
3. Tagged unions, already in A7.
4. The 8% migration cost as the benchmark for A7's migration story.
5. Region inference by default, with region annotations only at function
   signatures.

> Note (2026-09-16): Items 1, 2 and 5 are superseded by the memory plan: extents
> are inferred with no source syntax, and stored `ref` and `nil` are removed
> (M4). Tagged-union tag inspection is still reserved syntax in the current
> compiler ([SPEC](../../SPEC.md) section 3.3).

## What to avoid

1. Full region polymorphism (explicit region variables, similar to Rust's `'a`
   lifetimes). Too complex for the marginal benefit; the lexical form covers the
   common case.
2. `_unsafe_cast`. A7 has no escape.
3. Runtime bounds checks on fat pointers. A7 proves the bound statically and
   emits the unchecked access.

## Lessons for A7

Inference makes safety ergonomic. Cyclone's region annotations are a small
fraction of the code (about 0.5% of lines, 6% of the 8% changed) because the
inferencer handles the common case. A7 region scopes, if added, should need no
annotation in the typical case.

The boundary between safe and unsafe code is the function signature. Cyclone
annotates pointer kinds at signatures and infers the rest in bodies. The Phase B
recommendation was for A7 to do the same for parameter modes (Hylo's approach)
and region annotations.

> Note (2026-09-16): L6 approves immutable argument bindings but no
> parameter-mode syntax; `ref` stays the working form. The memory plan infers
> placement without region annotations. See
> [decisions.md](../../plan/decisions.md).

## Sources

- [Cyclone project page](https://cyclone.thelanguage.org/)
- [Cyclone region paper (Grossman et al., PLDI 2002)](https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf)
- ["Safe Manual Memory Management in Cyclone" (Swamy et al.)](https://www.cs.umd.edu/projects/PL/cyclone/scp.pdf)
- ["Cyclone: A safe dialect of C" (Jim et al., USENIX 2002)](http://www.cs.umd.edu/projects/cyclone/papers/cyclone-safety.pdf)
- [Grossman's thesis on safe programming at the C level](https://homes.cs.washington.edu/~djg/papers/grossman_thesis.pdf)
