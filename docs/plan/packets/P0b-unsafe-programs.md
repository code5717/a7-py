# Packet P0b: reject unsafe programs that build today

Status: proposed, 2026-09-16, revision 2 after an independent review. Each item
changes the result of a program that A7 accepts and Zig builds today, so each needs
your approval. Partial approval is expected. Decisions are recorded in the
[ledger](../decisions.md).

Today's behavior contradicts two documents. `docs/SAFETY_CONTRACT.md:47-49` says
"If a fact is invalidated or unknown, the compiler rejects the dependent operation",
and SPEC A.4 says "Slices must not outlive backing array" (`docs/SPEC.md:2088`).
Whatever you decide, those documents are corrected to match.

## How the evidence was gathered

- Every example below was compiled: A7 accepted it and `zig build-obj` accepted the
  emitted Zig (`tmp/packets/check/`). None was built into a program or run, because
  running them would divide by zero, index out of bounds, use freed memory or free
  memory twice.
- Reproduction IDs in brackets refer to the two ledgers linked from the
  [inventory reproduction](../audit/2026-09-16-inventory-repro.md).
- **Programs affected** was measured over 2440 programs: the 2105 A7 sources that
  pytest passes to the compiler, the 43 examples, and the code blocks in `docs/SPEC.md`,
  `site/public/docs/`, `site/public/llms-full.txt` and `docs/lang-safety/`. Code blocks
  that do not parse today never reach the check.
- Items P0b.1 to P0b.4 were measured by running a changed copy of the safety pass
  beside the real one and comparing results. Items P0b.5 to P0b.7 and P0b.9 were
  measured by searching the parsed programs for the pattern. P0b.8 was not scanned.

## Summary

| Item | Change | Programs affected |
| --- | --- | --- |
| P0b.1 | A value assigned inside a block or branch is remembered after it, as the range of all paths | 0 |
| P0b.2 | Loops: values assigned inside a loop are accounted for | Depends on the option: 2 or 6 examples |
| P0b.3 | A call that may change a variable through a reference forgets what was known about it | 0 |
| P0b.4 | Compound assignment (`-=`, `+=`, ...) computes the new value | 0 |
| P0b.5 | Returning a slice of a local array is rejected | 0 |
| P0b.6 | Deleting the same storage twice through two names is rejected | 0 |
| P0b.7 | `del` through a `ref` parameter is rejected | 0 |
| P0b.8 | `defer del a` followed by `del a` is rejected | not scanned |
| P0b.9 | `==` between two string locals that hold literals is rejected | 0 |

P0b.1, P0b.3 and P0b.4 together were also measured: 0 programs.

## P0b.1 Values assigned inside a block or branch

```a7
// Current A7: accepted. The safety pass restores what it knew before the block,
// so it still believes x is 5 and approves the division.
main :: fn() {
    x := 5
    {
        x = 0
    }
    y := 10 / x
}
// Proposed: rejected with the existing message "divisor may be zero".
```

Where two branches rejoin, each variable keeps the range covering both paths: after
`if c { top -= 1 }` with `top` at 1, `top` is known to be 0 or 1.

Impact: 0 programs.

## P0b.2 Loops

```a7
// Current A7: accepted. The loop body is checked once, with the facts from before
// the loop, so the division is approved although x is 0 on the second pass.
main :: fn() {
    x := 5
    i := 0
    while i < 3 {
        y := 10 / x
        x = 0
        i += 1
    }
}
// Proposed: rejected with the existing message "divisor may be zero".
```

The same flaw approves out-of-bounds indexing today. A `while i < 10` loop that
indexes a 5-element array with `i` is accepted and builds.

Three options:

| Option | What happens | Examples affected | Cost |
| --- | --- | --- | --- |
| (a) Wait for Wave 3 | Loops stay unsound until the new fact engine lands (packet P7) | None now | Out-of-bounds and divide-by-zero in loops keep passing for Waves 1 and 2; new examples written in that time get no loop proof checking |
| (b) Simple rule now | Facts about anything a loop assigns are dropped at the loop's start | 6: `026_binary_tree`, `029_sorting`, `030_calculator`, `032_prime_numbers`, `041_route_simulation`, `042_gradebook`; also `docs/lang-safety/edge-cases/03-definite-assignment.md:206` | Today's safety pass has no way to prove an upper bound from a guard (`a7/safety.py:688-702` learns only lower bounds, `!= 0` and non-nil), so these examples cannot be fixed by adding guards. They would have to be restructured, and the ordinary `while i < N { arr[i]; i += 1 }` pattern would stop compiling |
| (c) Proper loop rule now | The loop is analyzed until its facts stop changing, with bounds taken from conditions such as `i < N` | 2: `026_binary_tree.a7:49, 56, 62` and `030_calculator.a7:62` | More work in the current safety pass, which Wave 3 replaces (the logic carries over). `026_binary_tree` needs an explicit capacity check before indexing its stack. `030_calculator` divides by a float that cannot be proven non-zero; it needs a guard, or packet P4's float rule |

Probes confirmed option (c) accepts `for i := cast(usize, 0); i < 5; i += 1 { arr[i] }`
and the nested `j < limit` loop in `029_sorting`, and rejects the `while i < 10`
overrun, a zero divisor reaching the loop start through `continue`, and one reaching
the loop exit through `break`.

The five examples besides `026_binary_tree` are correct programs that today are
approved for the wrong reason. For example, after `j += 1` the safety pass records
`j` as 1, whatever it was before.

**Recommendation:** (c). It closes a real out-of-bounds hole now, at the cost of two
small example edits, which would be shown to you before they are made.

**Decision requested:** choose (a), (b) or (c).

## P0b.3 Calls that change a variable through a reference

```a7
// Current A7: accepted. zero() sets x to 0 through the ref parameter, but the
// safety pass keeps believing x is 5.
zero :: fn(v: ref i32) {
    v = 0
}

main :: fn() {
    x := 5
    zero(x)
    y := 10 / x
}
// Proposed: rejected with the existing message "divisor may be zero".
```

A function can store a reference it receives and change the variable during a later
call. So after a local has been passed to a `ref` parameter, the proposed rule forgets
what it knows about that local at every later call in the same function, including
calls such as `io.println` that cannot change it. Dividing by such a local after a
call then needs a fresh check (`if x != 0`).

Impact: 0 programs.

## P0b.4 Compound assignment

```a7
// Current A7: accepted. After `x -= 5` the safety pass records x as 5 (the
// right-hand value), not 0.
main :: fn() {
    x := 5
    x -= 5
    y := 10 / x
}
// Proposed: rejected with the existing message "divisor may be zero".
// `x += 1` from 5 stays accepted, because the new value is computed as 6.
```

Impact: 0 programs, including when combined with P0b.1 and P0b.3. If you choose P0b.2
option (b), this item also affects `026_binary_tree` through that option.

## P0b.5 Returning a slice of a local array

```a7
// Current A7: accepted. The returned slice points into get()'s stack frame, which
// no longer exists when main reads it. SPEC A.4 forbids this.
io :: import "std/io"

get :: fn() []i32 {
    buf: [4]i32 = [1, 2, 3, 4]
    buf[0] = 5
    ret buf[0..2]
}

main :: fn() {
    s := get()
    io.println("{}", s.len)
}
// Proposed: rejected; message wording not yet written.
```

Impact: 0 programs. The general rule for slices is memory gate M13.

## P0b.6 Deleting the same storage twice through two names

```a7
// Current A7: accepted, and emits two destroy calls for one allocation.
Pt :: struct { x: i32 }

main :: fn() {
    a := new Pt
    b := a
    del a
    del b
}
// Proposed: rejected; message wording not yet written.
```

A second `del` of the same name inside a loop is rejected the same way. Not covered:
reading through the other name after a `del` (`b := a; del a; x := b.x`) still
compiles; that belongs to memory gates M3 and M4, which propose removing `del`.

Impact: 0 programs. `test/test_cast_safety_matrix.py:280` (delete, reassign, delete)
stays accepted.

## P0b.7 `del` through a `ref` parameter

```a7
// Current A7: accepted. v refers to the caller's stack variable x, and del frees
// that stack address.
release :: fn(v: ref i32) {
    del v
}

main :: fn() {
    x: i32 = 1
    release(x)
}
// Proposed: rejected; message wording not yet written.
```

The rule cannot tell whether the caller passed stack or heap storage, so it also
rejects a correct helper that deletes heap memory passed to it. Not covered: deleting
through a `ref` stored in a struct field. Both belong to gates M3 and M4.

Impact: 0 programs.

## P0b.8 `defer del` followed by `del`

```a7
// Current A7: accepted. The deferred delete is not tracked, so both run.
Pt :: struct { x: i32 }

main :: fn() {
    a := new Pt
    defer del a
    del a
}
// Proposed: rejected; message wording not yet written.
```

Reading `a` after `defer del a` and before the scope ends stays accepted. Impact: not
scanned; no example or test was found that uses both forms on one variable by name.

The examples in P0b.6 to P0b.8 avoid a variable named `p`: today `del p` collides with
the `|p|` capture the compiler emits, and Zig rejects that for a separate reason
(P0.1 list item 8).

## P0b.9 `==` between two string locals holding literals

```a7
// Current A7: accepted. The two locals hold literals of the same length, which
// Zig emits as pointers, so == compares their addresses, not their text.
main :: fn() {
    a := "x"
    b := "y"
    same := a == b
}
// Proposed: rejected; message wording not yet written.
```

This is the only string `==` form that builds today. Literals of different lengths,
a local compared with a literal, typed `string` locals, and parameters are already
rejected by Zig; comparing two literals directly keeps working because the compiler
folds it (`test/test_ast_preprocessor.py:386`). Comparing text is part of packet P10.

Impact: 0 programs.
