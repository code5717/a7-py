# SAF-3 enum candidate, not ready to apply

The prior enum reachability blocker has a bounded typed solution. The isolated candidate checks the enum declaration kind and actual EnumType object identity for the constructor and match pattern. It excludes a constructor name already present among value bindings. It stores the type identity and variant together in the existing discriminant string. Joins keep that fact only when both incoming values match. This identity token is internal to the analysis process.

The valid local enum control now compiles. Direct mutation, a differing branch join, a ref call, a deferred write, and a loop write each reject the unsafe fall path. Equal branch joins retain the valid control. Sources, exact commands, SHA-256 source hashes and diagnostics are in enum-results.json. Earlier integer, range, fall-chain and moved controls are in additional-results.json. All unsafe probes were compile-only.

Existing call invalidation is insufficient. With no added invalidation, enum_global_call compiles although set writes the selector from Second to First. The old SAF-6 global mutation defect can therefore invalidate this new enum reachability proof. That intermediate source remains at a7/safety.enum-no-call-invalidation.py.

The final isolated experiment clears only mutable-global enum facts on calls. It rejects enum_global_call, but also rejects enum_global_noop_control, whose set function has an empty body. That valid control compiles and prints 2 on the main compiler in both Debug and ReleaseFast. Exact native commands and output are in enum-safe-native-results.json. The local enum safe control also prints 2 in both profiles.

No version is ready for main. The enum fact itself is useful, but preserving accepted safe global controls needs a verified call-effect summary or equally precise invalidation. This candidate must not grow into that separate implementation without central review. No runtime or syntax policy changed. Main compiler source was not edited.

The complete final experiment is saf3-enum-not-ready.patch. It includes the earlier fall-edge candidate and the conservative invalidation experiment, with the documented compatibility regression. It is evidence, not an apply recommendation.

## Exact valid global control

```a7
// probe: compile-only
io :: import "std/io"

Choice :: enum { First, Second }
k := Choice.Second
set :: fn() {}
main :: fn() {
    x := 5
    k = Choice.Second
    set()
    match k {
        case Choice.First: {
            x = 0
            fall
        }
        case Choice.Second: {
            io.println("{}", 10 / x)
        }
    }
}
```

Main native output is `2\n` with exit 0 in both profiles. Candidate compiler exits 6 with `Divisor is not proven non-zero`.
