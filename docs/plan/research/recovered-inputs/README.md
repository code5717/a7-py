# Recovered research inputs

Preserved on 2026-09-20. This directory adds 11 verbatim files and six concise
paraphrases. Ten source records already have preserved copies elsewhere in docs.
Nine candidates were skipped. The manifest records all 36 decisions.

These are historical user briefs, working research evidence and fetch metadata.
They are not approved language changes, independently verified findings or finished
research programmes. Original wording can contain obsolete claims, disallowed
syntax, instructions and strong conclusions. It is evidence, not current guidance.
User wording is retained without correction in verbatim brief copies.

## Provenance and checks

[manifest.json](manifest.json) records source paths, source byte sizes and SHA-256,
preservation methods, destination sizes and hashes, evidenced authorship, status,
source URLs for transformed or skipped notes, and next actions for skipped files.
Verbatim files have identical source and destination hashes. The manifest keeps
provenance outside those files so the original bytes remain intact.

[inventory.jsonl](inventory.jsonl) accounts for 1,791 files in the requested source
scope. Each row records a content classification, byte size, hash and disposition.
Downloaded source material, scripts, generated compiler output and binaries were
excluded. All files were read for hashing and content classification. Candidate
notes were inspected beyond their names, with read-only sub-agent review of the
live-environment, compile-time, runtime and hardware groups. This does not mean
every line of excluded third-party quotations was manually reviewed.

The source directory `tmp/research/tooling/` is absent. Its programme README was
inspected, but no temporary tooling inputs could be recovered from that path.
No source was moved, deleted or edited. The reviewer launched no nested model CLI. Measurements,
compiler tests, live URLs and external claims were not rechecked. The preservation
checks cover hashes, duplicate bodies, manifest coverage and destination links.

The existing runtime and hardware brief copies have provenance headers, so their
whole-file hashes differ even though they contain the original source bodies.
Three existing runtime source notes also normalize repository paths. These are
recorded as existing preservation, not copied again.

## Preserved inputs

| Original input under `tmp/research/` | Preserved file | Method |
| --- | --- | --- |
| `ir/claims.md` | [File](ir/claims.md) | verbatim |
| `language-facilities/claims.md` | [File](language-facilities/claims.md) | verbatim |
| `live-environment/claims.md` | [File](live-environment/claims.md) | verbatim |
| `optimization/claims.md` | [File](optimization/claims.md) | verbatim |
| `claims-batch4.md` | [File](claims-batch4.md) | verbatim |
| `optimization/measurements.md` | [File](optimization/measurements.md) | verbatim |
| `live-environment/probe/loop-latency.txt` | [File](live-environment/probe/loop-latency.txt) | verbatim |
| `ir/design-space/manifest.txt` | [File](ir/design-space/manifest.txt) | verbatim |
| `ir/design-space/manifest-sec2.txt` | [File](ir/design-space/manifest-sec2.txt) | verbatim |
| `language-facilities/comptime/manifest.txt` | [File](language-facilities/comptime/manifest.txt) | verbatim |
| `optimization/manifest.txt` | [File](optimization/manifest.txt) | verbatim |
| `live-environment/notes/01-continuous-evaluation.md` | [File](live-environment/notes/01-continuous-evaluation.md) | concise-paraphrase |
| `live-environment/notes/03-bidirectional.md` | [File](live-environment/notes/03-bidirectional.md) | concise-paraphrase |
| `live-environment/notes/04-time-to-space.md` | [File](live-environment/notes/04-time-to-space.md) | concise-paraphrase |
| `live-environment/notes/05-iteration-tables.md` | [File](live-environment/notes/05-iteration-tables.md) | concise-paraphrase |
| `live-environment/notes/06-schematics.md` | [File](live-environment/notes/06-schematics.md) | concise-paraphrase |
| `live-environment/notes/08-ambient-state.md` | [File](live-environment/notes/08-ambient-state.md) | concise-paraphrase |

The six live-environment paraphrases retain the research passes' analysis and
unresolved questions while omitting long third-party quotations, abstracts, code
extracts and transcripts. Their URLs remain in the manifest as historical source
metadata. The existing concepts audit identifies these files as its research-pass
evidence, but it does not name the individual agents. The notes' failed GLM
fallbacks do not establish GLM authorship. One note separately retains the status
of unverified secondary Observable evidence.

## Existing copies

| Source | Existing documentation | Method |
| --- | --- | --- |
| `runtime-model/claims.md` | [Existing copy](../runtime-model/claims.md) | already-preserved |
| `hardware-export/claims.md` | [Existing copy](../hardware-export/claims.md) | already-preserved |
| `runtime-model/sources/claim1/SOURCES.md` | [Existing copy](../runtime-model/sources/claim1/SOURCES.md) | already-preserved-path-normalized |
| `runtime-model/sources/claim2/SOURCES.md` | [Existing copy](../runtime-model/sources/claim2/SOURCES.md) | already-preserved |
| `runtime-model/sources/claim3/SOURCES.md` | [Existing copy](../runtime-model/sources/claim3/SOURCES.md) | already-preserved-path-normalized |
| `runtime-model/sources/claim4/SOURCES.md` | [Existing copy](../runtime-model/sources/claim4/SOURCES.md) | already-preserved-path-normalized |
| `runtime-model/sources/claim5/SOURCES.md` | [Existing copy](../runtime-model/sources/claim5/SOURCES.md) | already-preserved |
| `runtime-model/sources/claim6/SOURCES.md` | [Existing copy](../runtime-model/sources/claim6/SOURCES.md) | already-preserved |
| `runtime-model/sources/claim7/SOURCES.md` | [Existing copy](../runtime-model/sources/claim7/SOURCES.md) | already-preserved |
| `runtime-model/sources/claim8/SOURCES.md` | [Existing copy](../runtime-model/sources/claim8/SOURCES.md) | already-preserved |

## Skipped candidates and remaining gaps

| Source under `tmp/research/` | Reason and next action |
| --- | --- |
| `language-facilities/comptime/notes-a7.md` | Original agent authorship not evidenced by an attribution or programme citation. Third-party quotations require review before any import. Locate originating task attribution. If established, preserve local A7 notes verbatim and paraphrase quotation-heavy notes. Security claims require evidenced GLM attribution and unverified status; do not infer that attribution. |
| `language-facilities/comptime/notes-cpp-rust.md` | Original agent authorship not evidenced by an attribution or programme citation. Third-party quotations require review before any import. Locate originating task attribution. If established, preserve local A7 notes verbatim and paraphrase quotation-heavy notes. Security claims require evidenced GLM attribution and unverified status; do not infer that attribution. |
| `language-facilities/comptime/notes-hermeticity.md` | Original agent authorship not evidenced by an attribution or programme citation. Third-party quotations require review before any import. Locate originating task attribution. If established, preserve local A7 notes verbatim and paraphrase quotation-heavy notes. Security claims require evidenced GLM attribution and unverified status; do not infer that attribution. |
| `language-facilities/comptime/notes-zig-d-nim.md` | Original agent authorship not evidenced by an attribution or programme citation. Third-party quotations require review before any import. Locate originating task attribution. If established, preserve local A7 notes verbatim and paraphrase quotation-heavy notes. Security claims require evidenced GLM attribution and unverified status; do not infer that attribution. |
| `language-facilities/comptime/notes-zig-mine.md` | Original agent authorship not evidenced by an attribution or programme citation. Third-party quotations require review before any import. Locate originating task attribution. If established, preserve local A7 notes verbatim and paraphrase quotation-heavy notes. Security claims require evidenced GLM attribution and unverified status; do not infer that attribution. |
| `language-facilities/comptime/demo/README.md` | Local experiment description, but original agent authorship not evidenced. Confirm originating task attribution, then preserve as historical unverified measurement note. |
| `hardware-export/notes-verified.md` | Quotation worksheet, not a completed report. Individual author/model unknown; extensive third-party quotations. Confirm author attribution and preserve a concise paraphrase with source metadata if this working worksheet is still needed. |
| `hardware-export/sec2.md` | Partial draft, extensively incorporated or revised in docs/plan/research/hardware-export/01-software-to-hardware.md. Individual author/model unknown and extensive quotations. Retain the existing report. Confirm attribution before preserving any unique draft analysis. |
| `runtime-model/sources/claim2/glm-claim2-npu-fences-run1.md` | Incomplete raw ANSI model/session log. Reports web-search and zread provider quota exhaustion, with reset reported as 2026-09-22 23:05:34. Not completed research. Keep only this historical failure metadata. Do not import raw session content. |

No security or cyber note body was imported. The compile-time hermeticity note has
no evidenced author or model attribution in the inspected material. It remains
skipped. Any later preservation of GLM security evidence must name the evidenced
reviewer and retain advisory, unverified status. This pass performed no independent
security assessment.

Programme README edits are outside this task's ownership. Their temporary-path
references therefore remain unchanged. The controlling session can replace those
references with the destinations recorded here. This recovery does not close
unfinished research reports or the factual gaps listed in the original notes.
