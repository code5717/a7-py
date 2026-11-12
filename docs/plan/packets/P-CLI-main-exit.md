# Main return codes

Status: proposed, awaiting a user decision. No compiler behavior has changed.
This packet addresses P2-72 and the open `main` exit-status item in the roadmap.

## Current behavior

```a7
main::fn(){}
```

This passes checking and emits Zig. Both of these signatures fail with semantic
exit 6, including when checked with `--lib`:

```a7
main::fn()u8{ret 7}
```

```a7
main::fn()i32{ret 7}
```

The error is `Executable entry point main must have no parameters and no return
value`. An imported file's `main` does not satisfy the entry-file requirement.
The [current probes](../../../tmp/v1-completion-2026-10-07/main-exit-proposal-evidence/REPORT.md)
record twenty compiler invocations and one import-origin check on frozen source
`de578138`. They establish checking and emission behavior, not native exit codes.

## Recommended contract

Keep `main::fn()` and add `main::fn()u8`. Both take no parameters. A normal return
from void main yields status 0; a normal return from u8 main yields its value,
from 0 through 255. Keep other entry signatures rejected, including `i32`,
`usize`, `bool` and parameterized main. This packet adds the explicit `u8`
spelling only; it does not add new generic-entry or return-type-alias behavior.

```a7
// demo.a7
io::import "std/io"
main::fn()u8{
    defer io.println("cleanup")
    io.println("done")
    ret 7
}
```

Proposed results after implementation:

```text
a7 check demo.a7             -> compiler exit 0
a7 build demo.a7 -o demo     -> compiler exit 0
./demo                      -> prints done, then cleanup; process exit 7
a7 run demo.a7               -> same output; command exit 7
```

The returned expression is evaluated once. Ordinary function defers run before
return completes, and the existing stdout wrapper flushes before normal process
termination. Preserve existing I/O failure and panic behavior; a failed flush
does not count as a normal return of the requested code. No immediate-exit API
that skips cleanup is introduced.
Existing broken-pipe handling may terminate with status 0; other stdout errors
retain their panic behavior. Those failure paths do not acquire a cleanup or
requested-status guarantee from this proposal.

Compiler failures retain their existing exit stages. A program may itself return
one of those numbers, so the exit number alone does not distinguish a compiler
failure from a program result; the command's diagnostics provide that context.

## Entry selection and library mode

The entry file's own main remains the selected executable entry. Imported or
nested functions named main do not replace it. The entry checks that protect
ordinary void main must also apply to the newly accepted u8 entry.

`--lib` continues to omit an implicit executable root for analysis and does not
require main. If the library root declares main, permit the same parameterless
void/u8 signatures. Retain current rejection of its other main signatures.
Preserve current library emission: an explicitly declared root main can still
emit as unprefixed main; imported mains keep their module prefixes. This packet
does not redesign library exports or permit `build`/`run` without an entry.

## Compatibility and alternatives

Existing accepted void-main programs keep their output and normal exit status.
The explicit u8 form becomes accepted where it currently fails, in executable
and library checking. `ret 256`, `ret -1` and incompatible runtime return values
must follow existing u8 fitting/type rules. There is no truncation or implicit
signed-to-unsigned conversion for exit codes.

- Keep void main only. All current outcomes remain; users still cannot return
  a process status from main.
- Design a wider signed status or an exit function. This needs separate choices
  about range conversion, cleanup and target behavior before implementation.

The local Zig 0.16.0 source has a matching implementation route: `std/start.zig`
lines 750–755 maps void main to 0 and returns u8 main's value. The inspected file
hash is `2839e5ca2d125604bff88adeadf463e6d42bdb37058bc02896cd9220cf27dc5b`.
That is source evidence from the pinned toolchain, not a native test. A7's I/O
wrapper currently has void return type and discards the user-main result, so
relaxing entry validation alone would be insufficient.

## Acceptance checks after approval

- Verify both old void and new u8 entries with and without I/O in Debug,
  ReleaseSafe and ReleaseFast. Observe stdout, stderr and actual process status
  for 0, 7 and 255 through a saved binary and `a7 run`.
- Verify deferred output and cleanup precede process completion. Check return
  expression evaluation once and preservation of its value when a defer changes
  the local from which it was returned. Keep existing flush-failure behavior.
- Check successful `check`, emission and `build` return 0 regardless of the
  future program status. Preserve all compiler-failure stage codes.
- Check invalid signatures and out-of-range returns, imported main selection,
  library-root variants and entry-specific proof requirements. Require located
  diagnostics and no emitted artifact for semantic failures.
- Start with the existing local Linux x86_64 toolchain. Record other targets as
  unqualified until their native process behavior is tested; source inspection
  and cross-compilation alone do not establish it.
- Run the permitted frozen compiler/package gate and update README, SPEC,
  STATUS, CHANGELOG, CLI guidance and affected site exports. Cyber scans remain
  excluded. A passing gate does not establish full V1 completion.

Approval is required by AGENTS.md's language-change rule because this accepts a
new entry signature and defines observable process behavior.
