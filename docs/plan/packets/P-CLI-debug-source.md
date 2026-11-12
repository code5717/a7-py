# Native build source lifetime

Status: proposed. No implementation is approved by this packet.

`a7 build` leaves debug information pointing at a generated Zig file that it
deletes before returning. Retaining that exact generated source path would fix
this file-lifetime defect. It would not provide A7 source-level debugging.

## Current behavior and evidence

Save this as `demo.a7`:

```a7
early :: fn(b: bool) { if b { ret } }
main :: fn() { early(false) }
```

```sh
uv run a7 build demo.a7 --profile debug -o demo
readelf --debug-dump=decodedline --wide demo
```

The build succeeds. Its debug line table names
`a7-native-<id>/program.zig` beside the executable, but that directory no longer
exists. `a7/cli.py` creates a `TemporaryDirectory`, moves only the binary to the
destination, and removes the directory when leaving the context.

The [CLI observation](../../../tmp/v1-completion-2026-10-07/phase2-debug-source-lifetime/cli-observation.md)
records the actual Debug build on source manifest `de578138`. Six commands and
12 streams were verified; all 1,664 frozen source hashes and modes remained
unchanged. The binary was inspected with `readelf`, not executed. No debugger
stepping or listing was tested. The decoded table contains generated Zig
locations, with no A7 source filename.

Retention is the proposed repair. Source embedding has not been selected or
qualified.

## Proposed contract

Every successful `a7 build`, in debug, release or fast profile, retains the exact
Zig file used to build its executable:

```text
Before:
  demo
  debug information -> deleted a7-native-<id>/program.zig

After:
  demo
  a7-debug-<unique-id>/program.zig
  debug information -> existing a7-debug-<unique-id>/program.zig
```

- Create a fresh, compiler-owned `a7-debug-<unique-id>` directory beside the
  requested output. Its short prefix does not depend on the executable name.
  Use its unique path during compilation, so the debug information names the
  retained file. Copying source to a different path after compilation is insufficient.
- Preserve the existing atomic binary replacement. Until a build succeeds, keep
  the previous executable and all earlier retained source directories intact.
- On compilation or replacement failure, remove only the new directory owned by
  that invocation. Keep current exit stages and diagnostic behavior.
- Successful binary replacement commits the build. Retain its source even if
  printing `Built <path>` later fails; preserve existing reporting exit behavior.
- Retain the generated source after success. Keep earlier successful source
  directories, because copied older executables may still refer to them.
- Preserve existing source-file, directory, symlink and hardlink output-conflict
  checks. Never reuse or overwrite a preexisting source directory.
- Keep the current `Built <path>` output. Do not change A7 syntax, program output,
  the executable destination, or the `a7 run` cleanup behavior.
- Leave compile-only `-o file.zig` behavior unchanged. It already retains the
  caller-selected generated source.

The directory is a build artifact. Users can remove it when they no longer need
source listing for executables that refer to it. Repeated successful builds
therefore retain additional source copies; this proposal adds no automatic
cleanup command or retention limit. Moving the executable alone does not move
its referenced source. Relocatable bundles and A7 source maps remain separate.

## Compatibility and alternatives

Native build commands gain one retained directory per successful invocation.
Scripts that assume the output directory contains only the executable must
account for it. Existing successful A7 program outputs and command exit codes
must remain unchanged. All three profiles need direct artifact verification;
only the Debug defect has been reproduced in this packet.

Alternatives are to keep the current one-file build output and use the existing
compile-to-Zig workflow when source listing is needed, or design an explicit
opt-in retention flag. Both leave the default native build's source-lifetime
problem unchanged. A7 line mapping, DWARF rewriting and source embedding are
larger designs and are not part of this proposal.

## Acceptance checks after approval

1. Build a trusted program in each profile. Inspect the resulting debug line
   table and prove the named generated file exists after the CLI returns, with
   bytes matching the emitted source. Execute the program and check its output.
2. Rebuild at the same output path after changing the source. Prove the new
   executable uses the new source path and the older retained source is intact.
3. Exercise frontend rejection, Zig failure after staging, and binary-replacement
   failure. Prove the previous
   binary and source remain unchanged and only the new staging directory is
   removed. After successful replacement, an output-reporting failure must not
   delete the committed source. Name any mocked OS boundary separately from
   actual native evidence.
4. Check destinations with spaces, a long otherwise-valid basename, and the
   existing entry/import/symlink/hardlink/directory conflict cases. Verify the compiler does not overwrite inputs.
5. Verify `a7 run` still preserves program stdout, arguments, working directory
   and exit status, and cleans its temporary artifacts after completion.
6. Run relevant CLI tests, native examples, permitted compiler/package checks,
   and site checks. Preserve the user's scan exclusions and GPU deferral.

## Decision needed

Approve retained generated-source directories for successful native builds, or
keep the current artifact contract pending a different debugging design.

The [P0.1 repair list](P0-plan-confirmations.md#p01-which-fixes-go-ahead-without-asking-you)
requires a packet for fixes outside its named list. P2-75 retention is absent
from that list, and this proposal changes the files produced by a successful
command. The [decision ledger](../decisions.md) has no disposition for this
artifact contract. No acceptance test or implementation is complete yet.
