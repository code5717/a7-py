# Scalar declaration stores

On October 17, the compiler integrated a declaration-only safety optimization
from frozen source `3982d76caf4b322fa3cf3bd3d99f8eebe51c6b1fe598f7ed263c1d0af70deba4`.
A resolved local with a concrete numeric, bool or char type and a concrete scalar
initializer cannot have aggregate descendants. Its fact store now avoids
scanning the fact map for those descendants. Reference, aggregate, unknown-type
and assignment paths retain the existing store behavior.

The candidate removes the 1,056, 4,160 and 16,512 descendant entry visits measured
for 32, 64 and 128 scalar-copy declarations. These are instrumented operation
counts, not runtime speedups or a whole-compiler complexity result. P2-81 remains
open for other growing work.

Full pytest passed 5,132 tests with one known strict expected failure in 911.67
seconds. That failure still prints an address instead of the heap scalar value.
Exactly four scanner tests were excluded under the user's instruction. Owner
73162 exited 0. Independent review verified all 1,719 source hashes and modes,
master and eight worker origins, matching collections, unique outcomes and raw
streams. No other test skip or expected failure occurred.

Earlier focused evidence includes 135 nonnative passes and paired generated
output and diagnostics. Supplemental borrowed-mutation controls reach safety
analysis: unsafe bounds reject, guarded bounds pass and copied scalar facts
survive unrelated mutation. Positive generated outputs match the baseline.

The live destination matched the frozen baseline before transfer. The installed
`safety.py` hash is
`ba64371f68f5b5f26f7f4373935340652697d5cb7a78c774c46651216f2f3c9e`.
Local raw evidence remains in
`tmp/v1-completion-2026-10-16/scalar-store-full-qualification/`; the reviewed
candidate and supplemental controls are in `scalar-store-scaling-review/`
beside it. Transfer evidence and the previous file are in
`tmp/v1-completion-2026-10-17/scalar-store-integration/`.

The later numeric-reference write candidate and documentation edits are outside
this full test result. The complete release wrapper was not run for this change;
it includes scans excluded by the user. Benchmark pins, site preview capability,
expanded V1 requirements and publication remain unresolved. Scalar-reference
reads and automatic memory receive no new behavior from this optimization.

## Combined numeric-reference write qualification

The numeric-reference write repair was then integrated. It lets existing exact
numeric fitting check a concrete referent destination, preserving range and
integrality rules. Incompatible typed numeric values still reject, now with an
assignment-type diagnostic. Reference rebinding and scalar reads are unchanged.

The isolated repair passed 21 focused and 180 related nonnative checks, then
six exact native outputs for candidate and typed baseline. Each source was
emitted once with default-debug A7 lowering and built in three Zig modes.
The earlier unsupported CLI flag failure remains preserved. Live combined
focused checks passed 201 tests with nine deselections.

Full pytest on combined frozen source
`9d2384c40bc21e54381e3a50e1ceea907f084c88a51e51b4b045b3bc8b89f4de` passed
5,153 tests with one known strict scalar-printing expected failure in 818.22
seconds. Owner 80409 terminated with exit 0. All nine observers exited 0;
exactly four scanner tests were excluded. Root verified 1,721 source hashes
and modes, command streams and observer records. Independent review confirmed
all unique collections and outcomes, plus 334 live compiler/test identities.
This snapshot includes both
compiler changes and their tests. Later Goose research and handoff edits are
outside it. No complete release-wrapper, performance or publication result
is implied.

The installed type_checker.py SHA is
`35d17550e3407aa2392cd567e60f9118e946fcd72ac47752460c7169a5ad5cb0`.
Combined raw evidence is under
`tmp/v1-completion-2026-10-17/scalar-store-write-full-qualification/`.
Transfer and focused-check evidence are under `ref-scalar-write-integration/`
beside it.
