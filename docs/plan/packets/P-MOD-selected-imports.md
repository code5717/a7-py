# Selected import lists

Status: proposed, awaiting a user decision. No compiler change is implemented.
This packet concerns P2-68. L76's file-local import rule remains approved and
does not decide selected-name bindings.

## Current behavior

Given this file:

```a7
// helper.a7
value::fn()i32{ret 7}
other::fn()i32{ret 9}
```

Both unused lists below pass semantic checking and emit Zig, including the
name that does not exist:

```a7
// missing_selected.a7
import "helper" { Nope }
main::fn(){}
```

```a7
// existing_selected_unused.a7
import "helper" { value }
main::fn(){}
```

Using the selected function fails with semantic exit 6, `Undefined identifier`:

```a7
import "helper" { value }
main::fn(){x:=value()}
```

Ordinary alias access passes checking and emits Zig:

```a7
h::import "helper"
main::fn(){x:=h.other()}
```

An alias followed by a list, `h::import "helper" { value }`, fails parsing with
exit 5. These are compiler-only observations on source manifest `de578138`.
No generated program was built or executed for this packet. The
[probe report](../../../tmp/v1-completion-2026-10-07/phase2-selected-import-evidence/REPORT.md)
and [raw evidence](../../../tmp/v1-completion-2026-10-07/phase2-selected-import-evidence/evidence.json)
record eleven commands, twenty-two streams, six inputs and three Zig artifacts.

## Recommended behavior

Reject a parsed selected import list with semantic exit 6 until a usable
selected-binding contract is approved and implemented. The error points to
the import and explains: `Selected import lists are not supported; use an
import alias and qualified access.` Provide a concrete alias example in the
hint. Recognize the presence of a list, including `{}`, rather than testing
whether the list contains any names.

The two currently accepted unused-list examples would fail. The selected-call
example would report the unsupported import before checking the call. The
replacement is:

```a7
h::import "helper"
main::fn(){x:=h.value()}
```

Keep ordinary aliases, module visibility, duplicate-import rules and L76's
file-local imports unchanged. Keep parser-only AST reporting of selected lists.
Existing path-resolution errors retain their earlier exit 3; malformed lists
and alias-plus-list syntax retain parse exit 5. This proposal does not define
`using import` or alter bare imports without a list.

This is a compatibility change: a program containing an unused list can emit
Zig today and would stop at semantic checking. Approval is required under
AGENTS.md's language-change rule. There is no automatic source rewrite.

## Alternatives

- Keep metadata-only behavior. The current outcomes remain, including silently
  accepting unused nonexistent names. The documented limitation stays open.
- Implement usable selected bindings. The existing `value()` example would
  resolve to the exported function; `Nope` would fail at the import. This needs
  a separate complete contract for type/value bindings, visibility, collisions,
  generic declarations and module ownership before implementation. Choosing
  that direction does not approve unspecified details or alias-plus-list syntax.

## Acceptance checks after approval

- Semantic and compile modes reject empty, valid-name, missing-name and
  private-name lists with exit 6, a located import diagnostic and no artifact.
  Include an imported file that itself contains a selected list.
- Parser-only mode still reports the list. Malformed lists remain parse errors,
  and unresolved file paths retain resolution errors.
- Ordinary aliases can access public functions, constants, types and generic
  declarations. Missing/private members and forwarded aliases retain their
  existing rejection rules. A direct call control prints `7` in all profiles.
- Inspect existing selected-list tests and examples for compatibility impact.
  Run focused module tests, then the permitted frozen compiler/package gate.
  Keep cyber scans excluded and record the source identity and native limits.
- Update SPEC, STATUS, CHANGELOG and affected README/site guidance to describe
  the selected rule. Preserve this packet's pre-change observations.
