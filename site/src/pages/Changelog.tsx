import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const releases = [
  {
    version: 'Unreleased',
    date: '',
    groups: {
      Added: [
        'C backend support has been retired from the public compiler; Zig is now the only supported code generation target.',
        'Higher-order callback trampoline recursion is rejected during semantic validation.',
        'Generic struct literals retain concrete instance types, and used generic struct instances compile through Zig codegen.',
        'Release workflow hardening now includes split permissions, pinned audit tooling, artifact checksums, archive verification, and attestations.',
        'Public Markdown docs, llms.txt, and the docs site now distinguish current features from parsed-only or reserved syntax.',
      ],
      Changed: [
        'Zig stdio lowering now uses shared buffered stdout/stderr writers and generated print helpers.',
        'Normal example verification fails closed when a golden output fixture is missing.',
        'Low-recursion documentation now scopes the claim to the compiler stages that are actually stack-based today.',
        'File-backed imports fail closed before backend codegen until multi-file linking is implemented.',
      ],
      Fixed: [
        'JSON diagnostics serialize selected import item lists without tracebacking.',
        'Variadic parameters fail closed before backend codegen instead of emitting invalid target signatures.',
        'Examples now better exercise their documented branches in the Zig backend.',
        'Formatter symbol collection now surfaces traversal failures instead of swallowing broad exceptions.',
      ],
    },
  },
  {
    version: '0.3.0',
    date: '2026-05-07',
    groups: {
      Added: [
        'Labeled loops for while, for, and for-in with labeled break/continue in Zig.',
        'Match expression type checking, bool/enum exhaustiveness, wildcard patterns, and return-path validation.',
        'Error stage verifier and matrix tests for mode/format contracts.',
        'Examples end-to-end verifier with golden output fixtures.',
        'CLI v2 mode/format contract with stable exit codes.',
        'Standard library registry with io and math mappings.',
        'AST node annotations consumed by backend emission.',
        'Unskipped previously deferred semantic tests to surface concrete implementation gaps.',
      ],
      Changed: [
        'Docs site refresh with corrected quickstart commands, route labels, examples, and status wording.',
        'AST-wide analysis, preprocessing, formatter/reporting walks, and backend binary-expression emission moved to explicit stack-based traversal.',
        'Semantic errors are collected without hard-stop.',
        'Backend reads preprocessor annotations instead of recomputing.',
        'Semantic backlog is tracked by active tests. Run pytest for current counts.',
      ],
      Fixed: [
        'Match/switch Zig codegen trailing comma edge cases.',
        'Character literal escaping and operator keyword usage.',
        'Struct initialization and nil handling in examples.',
        'Status/docs/changelog list exact missing features uncovered by the unskipped semantic tests.',
      ],
    },
  },
  {
    version: '0.2.0',
    date: '2025-11-03',
    groups: {
      Added: [
        'Function type parsing.',
        'Generic type instantiation in type expressions.',
        'Uninitialized variable declarations.',
      ],
      Changed: ['Parser completeness and struct-literal disambiguation.'],
      Fixed: ['Generic parameter parsing and return-without-value for void functions.'],
    },
  },
  {
    version: '0.1.0',
    date: '2025-11-02',
    groups: {
      Added: [
        'Tokenizer, parser, and baseline language support.',
        '22 example programs and 352 tests.',
        'Rich error messages, pointer property syntax, full spec draft.',
      ],
    },
  },
]

export default function Changelog() {
  return (
    <div className="page">
      <PageHeader
        title="Changelog"
        summary="What changed, by release."
      />

      {releases.map((release) => (
        <SectionPanel key={release.version} title={release.version} subtitle={release.date || 'In progress'}>
          <div className="stack-2">
            {Object.entries(release.groups).map(([groupName, changes]) => (
              <section key={groupName}>
                <h3 className="section-subtitle mb-2">
                  <span className={`doc-chip ${chipTone(groupName)}`}>{groupName}</span>
                </h3>
                <ul className="doc-list">
                  {(changes as string[]).map((change: string) => (
                    <li key={change}>{change}</li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </SectionPanel>
      ))}
    </div>
  )
}

function chipTone(groupName: string): string {
  if (groupName === 'Added') return 'success'
  if (groupName === 'Changed') return 'warning'
  return 'accent'
}
