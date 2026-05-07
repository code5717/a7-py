import MetricTile from '../components/MetricTile'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const done = [
  { name: 'Parser', desc: 'All constructs: functions, structs, enums, unions, generics, match, imports, labeled loops.' },
  { name: 'Semantic analysis', desc: 'Name resolution, type checking with inference, control flow and memory checks, slice/index validation.' },
  { name: 'Preprocessing', desc: 'Nine sub-passes: lowering, resolution, mutation, usage, shadowing, hoisting, folding.' },
  { name: 'Zig backend', desc: 'Full translation with type mapping, pointer handling, hoisting, annotations, labeled loops.' },
  { name: 'C backend', desc: 'C11 output validated with zig cc for current examples. Labeled loops, slices, defer, raw and aliased function pointers, range and identifier match patterns, and core match expressions are present; backend parity checks should keep expanding.' },
  { name: 'Release tooling', desc: 'Installed CLI entrypoint plus debug/release artifact verification for Zig and C example builds.' },
]

const missing = [
  { name: 'fall statement semantics', desc: 'fall is parsed but not yet validated or lowered in semantic/codegen passes.' },
  { name: 'Advanced match diagnostics', desc: 'Exact duplicate, wildcard-first, full bool/enum coverage, and literal range overlaps are diagnosed. Symbolic range overlap and true capture patterns remain open.' },
  { name: 'Generic constraint internals', desc: 'Inline type-set constraint resolution in generics.py is still placeholder-level.' },
  { name: 'Memory/lifetime model', desc: 'Only basic del reference checks. No ownership/borrow-style lifetime analysis.' },
  { name: 'Backend semantic parity hardening', desc: 'Core conformance is green, but differential backend checks should expand. Side-effectful match scrutinees are supported in variable initializers; inline expression contexts remain open.' },
  { name: 'Automated publishing', desc: 'Local package builds are available, but tag-based package publishing is not wired yet.' },
]

export default function Status() {
  return (
    <div className="page">
      <PageHeader
        title="Status"
        summary="Done, open, next."
      />

      <section className="metric-grid">
        <MetricTile label="Pipeline" value="Working with open gaps" />
        <MetricTile label="Tests" value="Use live test run" note="PYTHONPATH=. uv run pytest --tb=no -q" />
        <MetricTile label="Examples" value="Zig + C verifiers" note="run_all_tests.sh includes both" />
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
          <li>Implement fall statement validation and backend lowering.</li>
          <li>Add symbolic/computed range-overlap match diagnostics.</li>
          <li>Improve type checker: control-flow narrowing, return consistency, dead code detection.</li>
          <li>Expand differential/backend-equivalence checks for new language features.</li>
          <li>Wire tag-based package publishing once release hosting is chosen.</li>
        </ol>
      </SectionPanel>
    </div>
  )
}
