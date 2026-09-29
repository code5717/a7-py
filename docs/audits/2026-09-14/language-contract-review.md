# Language contract and developer workflow review

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it.

Reviewed on 2026-09-14 against baseline commit
`701c67936c70ad2b0608326e23e56cc5d38c9fdb` and the working checkout. Each
compiler finding was reproduced twice with disposable files. No compiler files
changed. Documentation observations describe the state before the concurrent
documentation cleanup. Reconcile them with that cleanup before treating them as
open defects.

## Scope and evidence

The review covered `AGENTS.md`, `README.md`, `docs/SPEC.md`, `docs/STATUS.md`,
`docs/RELEASE.md`, `docs/SAFETY_CONTRACT.md`, CLI artifact handling, the module
resolver, release scripts, the release workflow, and public agent status docs.
This is a bounded contract and workflow review. It does not qualify all compiler
semantics, prove the published implementation limits, or establish release
readiness.

Run the saved reproduction from the repository root:

```sh
uv run python docs/audits/2026-09-14/repros/language_contract.py
```

The script creates its own temporary directory and removes it on exit. It does
not compile repository examples in place. The captured result is
[language-contract-observed.json](repros/language-contract-observed.json).
The source is [language_contract.py](repros/language_contract.py).

On this host the initial `uv` shim failed because Mise had no selected version.
The successful run used the installed binary directly:

```sh
/home/cx89/.local/share/mise/installs/uv/0.12.6/uv-x86_64-unknown-linux-musl/uv run python docs/audits/2026-09-14/repros/language_contract.py
```

No external model CLI was used for this review.

## LC-01. P1. Explicit output paths can destroy A7 input

`a7 demo.a7 -o demo.a7 --format json` exits 0 and replaces the source with Zig.
`a7 demo.a7 --doc-out demo.a7 --format json` also exits 0 and replaces the source
with a Markdown compilation report. The reproduction uses `main :: fn() {}`.

The source is read before output generation. `a7/compile.py:441` subsequently
opens the requested output for writing, and `a7/compile.py:471` does the same for
documentation. Neither path rejects a destination that identifies the source.
This can lose the user's only copy of a program after an accidental path choice.

Completion criteria:

- Reject source/output and source/documentation collisions before any write.
- Apply the check to resolved paths and existing file identity, including
  symlinks and hardlinks.
- Include loaded module sources in the protected input set.
- Reject output/documentation collisions so a report cannot replace emitted Zig.
- Preserve every affected file on rejection and return a documented CLI error.

Only the two direct same-path overwrites were reproduced in this audit. The
additional cases are required coverage for a complete correction.

## LC-02. P2. Failed JSON compilation advertises an old artifact

With a pre-existing `demo.zig` containing `old artifact`, compiling the malformed
source `main :: fn( {` exits 5. The JSON still includes
`artifacts.output_path` for `demo.zig`, although this invocation never wrote it.

`a7/compile.py:779-780` includes the artifact when its path exists on disk.
It does not check whether the current invocation produced it. Consumers that use
the artifact list independently from the exit code can select a previous build.
The observation concerns misleading provenance. Retaining an old file after a
failed compilation is not itself the defect.

Completion criteria:

- Track which artifacts this invocation successfully wrote.
- Exclude stale and unwritten destinations from the JSON artifact list.
- Specify how partial success is represented when Zig output succeeds and the
  later documentation write fails.
- Test failures before code generation and during artifact writes with existing
  destination files.

## LC-03. P2. The import loader bypasses its own cycle guard

The reproduction consists of three files.

Current A7:

```a7
// main.a7
a :: import "a"
main :: fn() { a.work() }
```

Current A7:

```a7
// a.a7
b :: import "b"
pub work :: fn() {}
```

Current A7:

```a7
// b.a7
a :: import "a"
pub other :: fn() {}
```

The CLI exits 0. Calling `ModuleResolver.load_module("a")` also succeeds and
caches both modules. Calling `topological_sort()` on that same resolver then
raises `Circular dependency detected in module graph`.

The implementation evidence is specific:

- `a7/module_resolver.py:40` lists circular dependency detection as a resolver
  responsibility.
- Lines 123-125 return cached modules before lines 130-135 inspect the active
  loading stack.
- Lines 186-191 cache a module before loading its dependencies. A dependency
  back-edge therefore returns through the cache and never reaches the guard.
- Lines 344-348 reject cycles during topological sorting, but the CLI dependency
  loading path does not invoke that check.

This is a broken existing guard and inconsistent behavior between resolver
operations. A search of README, SPEC, STATUS, SAFETY_CONTRACT and public agent
docs found no explicit public policy banning cyclic modules. The documented
function-recursion ban is a separate rule and is not evidence that module cycles
must be illegal. Do not describe this as a demonstrated violation of a published
module-cycle rule.

Completion criteria:

- Decide and document whether source modules may form import cycles.
- If cycles are rejected, enforce the rule on the actual CLI loading path and
  report the participating modules.
- If cycles are supported, define their initialization and resolution behavior
  and replace contradictory rejection paths.
- Resolve graph identity through canonical files so alternate import spellings
  cannot evade or fabricate a cycle.

Note (2026-09-16): the module-cycle policy is still open under gate G6 in the
[v1 plan](../../plan/README.md).

## Pre-cleanup documentation observations

These references preserve the original audit evidence. Concurrent documentation
cleanup may already have changed the quoted statements or line numbers.

(LC-D01 is cited as "line 144" in
docs/plan/research/memory/notes-h-audits-pdfs-current-memory.md.)

| ID | Baseline evidence | Assessment and required reconciliation |
| --- | --- | --- |
| LC-D01 | `docs/SAFETY_CONTRACT.md:3-6` requires rejecting every unproved risky operation, while lines 57-60 acknowledge incomplete arithmetic, union, and ownership checks. `docs/SPEC.md:2083-2089` states reference and slice lifetime rules without an adjacent implementation qualification. | Distinguish the intended safety contract from currently enforced guarantees. These statements alone do not prove that an individual unsafe program is accepted. Use compiler reproductions from the full audit to establish those defects. |
| LC-D02 | `site/public/docs/status.md:31` and `site/public/llms-full.txt:403` describe file-backed imports as follow-up work. README's What Works section and `docs/STATUS.md:30-32` describe limited current support. | Align the public status summaries with the narrow supported form and named limitations. |
| LC-D03 | README Quick Start contains `git clone <repository-url>`, while `site/public/docs/start.md` supplies the actual GitHub clone command. | Replace the placeholder and run the documented installation journey. |
| LC-D04 | `docs/SPEC.md:2131-2148` publishes minimum limits, including 127 nested blocks, 255 parameters, and 65,535-byte strings. | Treat these as unqualified claims until boundary tests establish them. This audit did not demonstrate a failing boundary and does not label a specific limit broken. |

## Completion criteria for the roadmap

A useful completion milestone is a qualified version of the current language.
The release claim should identify its supported behavior and prove it through
programs that exercise interactions between features.

1. Every construct described as current either compiles and executes correctly
   in debug and release or receives an A7 diagnostic before Zig emission.
2. (Cited as "line 157-159" in
   docs/plan/research/memory/notes-h-audits-pdfs-current-memory.md.)
   Safety qualification covers arithmetic overflow, shifts, union access, alias
   invalidation, lifetime escape, and indirect recursion alongside casts,
   division, and bounds proofs. Every claim points to accepted positive cases
   and rejected unsafe cases.
   Note (2026-09-16): for integer `+`, `-` and `*`, overflow checks are
   superseded by ledger L5 (wrapping). Division, shifts and casts remain open
   under gate G3.
3. Module qualification covers canonical identities, visibility, nested relative
   imports, the chosen cycle policy, namespace collisions, exported types, and
   generic propagation. The output remains one combined Zig file as specified.
4. The installation journey reaches a running program through documented
   commands. Toolchain diagnosis, version reporting, exit codes, and JSON
   artifacts make failures actionable.
5. README, SPEC, STATUS, the rendered site, and the agent corpus agree about
   supported and deferred behavior.
6. The full repository release gate, docs build, clean-wheel smoke workflow, and
   separately documented dependency and security checks pass. A passing example
   suite alone does not establish all language guarantees.

`docs/STATUS.md:19-39` names unfinished modules, generic specialization, workflow
commands, numeric and ownership guarantees, and standard library work. Those are
roadmap inputs, not grounds for inventing new syntax during an audit.

Tensor, AI, GPU, performance annotations, the package registry, and concurrency
are explicitly deferred in `docs/STATUS.md:41-44`. New numeric types require a
design brief. Optional references and affine ownership are future designs in
`docs/SAFETY_CONTRACT.md`. Keep those decisions as separate roadmap milestones.
Their absence is not a defect in a narrower, accurately documented release.

Note (2026-09-16): the v1 boundary in this paragraph is superseded by ledger L1
and L7 (concurrency, AI and a fuller language are in v1). New numeric types are
settled by L3 and L4, with remaining rules under gate G3. Reference and ownership
direction is superseded by L15, L17–L19 and L21; see the
[memory plan](../../plan/memory.md). The package registry stays out of scope.
