# Self-hosting parity proposal

Proposed acceptance contract, not approved or implemented. L73 requires an
A7-written compiler and bootstrap parity before V1 publication. The Python
compiler remains the bootstrap compiler. Zig provides native builds and runtime
support under L41. This packet defines evidence for replacement; it does not
select memory management, add syntax, or waive unfinished compiler requirements.

## Current and proposed behavior

Today `uv run a7 program.a7` invokes Python and emits Zig. There is no qualified
A7-written compiler or successor generation. The proposed chain uses one frozen
A7 compiler source tree, called `S`, and one pinned Zig toolchain:

| Step | Producer | Input | Result |
| --- | --- | --- | --- |
| 1 | Qualified Python compiler P | S | Zig Z1, built into native compiler C1 |
| 2 | C1 | The same S | Zig Z2, built into native compiler C2 |
| 3 | C2 | The same S | Zig Z3 |

These are acceptance roles, not new executable names or runnable commands today.
C1 and C2 must perform the compiler work themselves. Calling Python to parse,
check or generate a program does not establish self-hosting. Test orchestration
may use Python; Zig remains the permitted native build tool. Preserve source,
toolchain, command, environment, process-launch and artifact records so this
boundary can be checked.

For example, all three compilers must accept this program:

```a7
io :: import "std/io"
main :: fn() { io.println("{}", 7) }
```

Its native stdout must be exactly `7\n`, with successful exit and empty stderr.
All three must reject the following at semantic exit 6, with matching diagnostic
code, message, file and source span:

```a7
main :: fn() { x: i32 = "text" }
```

The contract covers the full approved language and CLI at the frozen acceptance
revision. These two examples illustrate the comparison; they are not its corpus.
Existing unresolved behavior, including the scalar-read expected failure, must
be settled before freezing acceptance. Agreement on a known defect is not a pass.

## Recommended comparison

Require public behavior parity and byte-identical Zig from P, C1 and C2.
In particular, Z1 = Z2 = Z3 byte for byte. All three must also emit identical
Zig for every successful corpus case. Compare native behavior from P, C1 and C2
against independently specified expected results, not merely against each other.

This requires the A7 port to preserve Python's emitter formatting and naming
choices. An alternative permits reviewed differences between P and the A7 port,
while requiring exact C1/C2 output equality, including Z2 = Z3. Every P/C1
emission difference would need a recorded explanation and review against the
expected behavior. No mismatch would be automatically accepted because programs
happen to print the same value. Both alternatives retain the same language,
diagnostic, runtime and complete-corpus requirements. Neither permits a compiler
that only builds its own source.

## Corpus and comparison rules

Freeze and hash the complete input inventory before running any generation.
Inventory every current language regression, example, module fixture, diagnostic
case, package check and deep-input requirement. Python API tests need explicit
equivalent language cases or an identified compiler-internal check. Document that
mapping; silently dropping API-only tests or failed cases is not permitted.
Include the complete A7 compiler source and its imported dependencies.

Compare acceptance/rejection, failure stage and exit code; diagnostic codes,
ordered messages, hints and spans; documented CLI modes and report schema; and
required output artifacts. Preserve exact byte output for deterministic native
cases, and explicit numerical tolerances only where an approved feature contract
already defines them. Run required native profiles and installed-package controls.
Include deep inputs and iterative algorithms. Python's recursion-limit checks
remain checks of P, not substitutes for exercising C1 and C2.

Prefer identical source and output paths for sequential generation runs. Archive
each result before the next run. If different roots are necessary, permit only a
declared one-to-one root mapping in schema-identified path fields. Preserve
relative filenames and every source coordinate. Never replace path-like text in
source literals, generated code, arbitrary messages or unrelated strings.

Ignore `timing_ms` only for parity equality, while retaining its raw value for
measurements. Preserve raw reports. JSON object-key order is immaterial; array
order, types and values remain significant. Native build command reports contain
temporary paths; compare their declared argument roles using the recorded path
map. Do not erase failed-command details or broadly remove fields. An unclassified
report difference fails until reviewed and explicitly resolved.

Compiler binary hashes are retained as identities. Binary byte equality is a
separate reproducible-build claim, because native metadata may differ. It cannot
replace the Zig fixed-point comparison or native behavior checks.

The current `doctor` command reports Python's version and executable and requires
Python 3.13 on the target platform. An A7 implementation must not fabricate those
values. Its replacement metadata and support checks need a separate compatibility
disposition before implementation. Approving the parity rule does not waive this
CLI requirement or approve removing Python fields from the current command.
Likewise, an exposed Python-specific diagnostic representation must receive an
explicit disposition; it cannot be silently excluded from the corpus.

## Acceptance and compatibility

Approval selects a comparison contract only. Implementation still follows the
roadmap: finish correctness, qualify compiler-building workloads and approved
memory/stdlib facilities, then port the compiler. Existing recursion bans,
resource limits and L38 workload requirements remain unchanged. No Python CLI
entry point, package or fallback is removed by this proposal.

Acceptance requires every corpus row to pass for P, C1 and C2 on the identified
revision, the selected emission comparison to pass, installed artifacts to work,
and independent reviews to reconcile the evidence. Keep the Python bootstrap
available until this is established. Publishing V1 still waits for every other
L73 track, including deferred GPU execution.

The [proposal evidence](../../audits/2026-10-07/bootstrap-parity-proposal.json)
records current source references and four Python-only report probes. Those
probes establish neither a second compiler nor bootstrap parity.
