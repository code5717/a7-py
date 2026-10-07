# Function-value initialization proposal

Proposed decision, not approved or implemented: keep bare function values non-nullable and require a value before consumption. Declarations may reserve unused storage without an initializer. There is no callable zero value.

Today this compiles with exit 0 and emits an undefined Zig function pointer:

```a7
main :: fn() {
    f: fn(i32) i32
    x := f(3)
}
```

Under the proposed rule, the call exits 6 with a diagnostic such as “Function value 'f' may be used before assignment.” Calls, copies, arguments, returns and other reads consume a function value. Assigning to its storage does not read the previous value.

This stays accepted:

```a7
inc :: fn(x: i32) i32 { ret x + 1 }
main :: fn() {
    f: fn(i32) i32
    f = inc
    x := f(3)
}
```

Required valid controls include an initializer, straight-line assignment, assignment in both branches, and a branch that returns before an otherwise unassigned use. The following repeated guard must also stay accepted:

```a7
run :: fn(flag: bool) {
    f: fn(i32) i32
    if flag { f = inc }
    if flag { x := f(3) }
}
```

Changing the second guard to `not flag` must reject. Both forms currently pass semantic analysis and Zig emission; the source and results are preserved in this packet. The initialized declaration `inc` above is shared by these examples. No unsafe source was executed.

## Choice and compatibility

The recommended contract is **prove assignment before consumption**. It preserves the named valid controls above. When the compiler cannot establish assignment, it reports semantic exit 6. This can reject some safe programs whose reasoning the compiler cannot prove. It does not promise to preserve every valid program. The exact proof model still needs a concrete design and compatibility review; approving the contract must not silently waive the named controls or approve arbitrary limits.

An alternative is **reject only proved uninitialized consumption**. That changes fewer accepted programs, but uncertain paths remain accepted and the initialization gap stays open. This is a narrower partial repair, not equivalent safety.

Making function values nullable or supplying an automatic panic stub are broader alternatives. Nullable functions would change the existing rule that only `ref T` accepts nil, including assignment, comparison and calls. A stub would choose new runtime behavior. Neither is included in the recommended contract.

Unused storage remains allowed under both initialization-check choices. Requiring an initializer at every declaration would reject existing assign-before-call controls and is not proposed. Ordinary zero initialization for numbers, references, slices and other supported fields remains unchanged.

Full closure requires aggregate fields, array elements, globals, aliases, copied aggregates, heap objects and indirect writes, with correct branch, loop and defer order. A first local-only implementation must be labeled partial. It cannot establish whole-language closure. Existing struct-field assignment before a call in `test/test_zero_initialization.py` must remain accepted. The A7 source-recursion ban is unchanged.

## Authority and verification boundary

L63 in `docs/plan/decisions.md` selects zero initialization and says no program is rejected. It does not define a callable zero value. SPEC section 6.4 describes function values; the nil rules permit only reference types. These sources do not settle the proposed proof-versus-uncertainty choice. STATUS and roadmap R4 already list the gap.

The original packet has 23 paired semantic/Zig-emission cases. This supplement adds the two correlated/complementary cases with exact compiler and Rich identities. None are native verification claims. After a decision, acceptance requires semantic error/span controls, the preserved valid programs, meaningful alias/aggregate tests for every claimed scope, safe observable native controls in all profiles, independent review and the release gate.

The [investigation record](../../audits/2026-10-07/function-initialization-investigation.json) identifies the source and probe evidence.
