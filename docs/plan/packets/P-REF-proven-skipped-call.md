# Proven skipped reference use at a call

Status: proposed, awaiting explicit approval. No production change is approved
by this packet. The existing rejection oracle remains in force pending a reply.

## Current and proposed behavior

The current working compiler rejects both programs below with semantic exit 6.
The rejection comes from the callee field-access requirement even when `f` is
false. Root reproduced both outcomes without native execution on 2026-10-19.

```a7
Box::struct{x:i32}
read::fn(r:ref Box,f:bool){if f{x:=r.x}}
main::fn(){read(nil,false)}
```

Proposed result: exit 0 for semantic checking and emission. The read is never
reached. Changing the last line to the following must still produce exit 6:

```a7
main::fn(){read(nil,true)}
```

The proposal allows a complete call proof to discharge the callee's potential
nil-use requirement when every reachable use is skipped. It must retain the
actual argument values captured in evaluation order. A successful proof for one
invocation cannot authorize another invocation with different arguments.
Unknown guards, incomplete effects and unsupported callable targets receive no
new permission. Reached nil reads and expired-owner reads remain rejected.
An uncalled or externally callable function receives no invented closed caller.

This proposal concerns reference-use proof at calls. It does not select scalar
reference loading syntax, deletion-origin policy, stack expiration, automatic
memory or public callee/argument rebinding order.

## Compatibility and alternatives

This expands acceptance of a currently rejected program. It would replace the
exit-6 expectation in test_existing_direct_callee_error_is_preserved with a
paired skipped/reached requirement. Existing diagnostics remain required when
the proof cannot establish skipped use. Update the specification, safety
contract and public status only after approval and verification.

Alternative 1 preserves the existing conservative rejection and its test.
Alternative 2 accepts only a callee's explicit nil guard; a caller's literal
false argument would still reject. The recommendation is complete call proof,
which gives the same safety rule to direct and supported forwarded calls.

## Acceptance requirements

- The exact false/true pair above yields 0/6 in semantic and emission modes.
- Two calls with false then true still reject the reached true call.
- An argument captured before a later mutation retains its original value.
- Unknown guards and unsupported effects do not silently receive a proof.
- Guarded nullable setters and readonly-abort nil/live controls retain their
  approved outcomes.
- Uncalled/external entries and calls through unresolved targets preserve their
  existing conservative boundary.
- Native execution of accepted controls follows semantic and emission checks;
  no unsafe negative is executed.

These are requirements, not completed tests for an approved language change.

## Evidence

[Current compiler probes](../../../tmp/call-guard-decision-2026-10-19/results.json)
record exact commands, exit codes and diagnostics. The current safety contract
keeps existing fatal diagnostics and describes the readonly analysis as
rejection-only. Isolated candidates accept the false case, which is a
compatibility difference requiring a disposition. It is not a reached unsafe
nil dereference.
