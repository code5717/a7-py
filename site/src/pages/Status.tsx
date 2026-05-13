import MetricTile from '../components/MetricTile'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const done = [
  { name: 'Parser', desc: 'All constructs: functions, structs, enums, unions, generics, match, imports, labeled loops.' },
  { name: 'Semantic analysis', desc: 'Name resolution, type checking with inference, control flow and memory checks, slice/index validation, and invalid fall placement diagnostics.' },
  { name: 'Preprocessing', desc: 'Nine sub-passes: lowering, resolution, mutation, usage, shadowing, hoisting, folding.' },
  { name: 'Zig backend', desc: 'Full translation with type mapping, pointer handling, hoisting, annotations, labeled loops, and fallthrough lowering.' },
  { name: 'Zig-only generation', desc: 'C support has been retired from the active compiler. CI, release artifacts, and examples now focus on Zig output.' },
  { name: 'Generic constraints', desc: 'Predefined, aliased, and inline type-set constraints resolve for declared generic functions and are checked at inferred call sites.' },
  { name: 'Release tooling', desc: 'Installed CLI entrypoint, debug/release artifact verification, package artifact builds, checksums, and draft GitHub releases.' },
]

const missing = [
  { name: 'Advanced match diagnostics', desc: 'Exact duplicate, wildcard-first, full bool/enum coverage, literal plus compile-time constant ranges, shared-endpoint symbolic ranges, and identifier captures are diagnosed. Arbitrary symbolic inequalities remain open.' },
  { name: 'Memory/lifetime model', desc: 'Direct use after del is rejected until reassignment. Full ownership, borrowing, aliasing, and lifetime analysis remain open.' },
  { name: 'Module lowering', desc: 'File-backed modules and selected imports are resolver-validated, but multi-file backend linking, direct selected-import names, and using imports are not runnable current syntax.' },
  { name: 'Backend semantic parity hardening', desc: 'Core conformance is green, but differential backend checks should expand for every new language feature.' },
  { name: 'Package-registry publishing', desc: 'The current release workflow deliberately stops at package artifacts attached to draft GitHub releases. Registry publishing should be a separate reviewed change if it is added later.' },
]

export default function Status() {
  return (
    <div className="page">
      <PageHeader
        title="Status"
        summary="Done, open, next."
      />

      <section className="metric-grid">
        <MetricTile label="Pipeline" value="Working" state="Open gaps tracked below" />
        <MetricTile label="Tests" value="Run locally" state="pytest and artifact gates" note="PYTHONPATH=. uv run pytest --tb=no -q" />
        <MetricTile label="Examples" value="43/43" state="Zig verifier suite" />
      </section>

      <SectionPanel title="Done">
        <div className="stack-2">
          {done.map((item) => (
            <article key={item.name} className="doc-callout success">
              <p className="m-0"><strong>{item.name}</strong></p>
              <p className="text-secondary item-copy">{item.desc}</p>
            </article>
          ))}
        </div>
      </SectionPanel>

      <SectionPanel title="Open gaps">
        <div className="stack-2">
          {missing.map((item) => (
            <article key={item.name} className="doc-callout warning">
              <p className="m-0"><strong>{item.name}</strong></p>
              <p className="text-secondary item-copy">{item.desc}</p>
            </article>
          ))}
        </div>
      </SectionPanel>

      <SectionPanel title="Next priorities">
        <ol className="doc-list">
          <li>Improve type checker: control-flow narrowing, arbitrary symbolic range reasoning, and deeper assignment compatibility.</li>
          <li>Expand differential/backend-equivalence checks for new language features.</li>
          <li>Decide whether package-registry publishing belongs in the release workflow; keep it out until that design is explicit.</li>
        </ol>
      </SectionPanel>
    </div>
  )
}
