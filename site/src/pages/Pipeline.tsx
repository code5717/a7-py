import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const stages = [
  {
    num: '1',
    name: 'Tokenizer',
    file: 'src/tokens.py',
    desc: 'Source text to tokens. Handles generics ($T), nested comments, all number formats.',
    input: 'Source code',
    output: 'Token list',
  },
  {
    num: '2',
    name: 'Parser',
    file: 'src/parser.py',
    desc: 'Recursive-descent with precedence climbing. Produces the full AST.',
    input: 'Token list',
    output: 'AST',
  },
  {
    num: '3',
    name: 'Semantic Analysis',
    file: 'src/passes/',
    desc: 'Three passes: name resolution, type checking, semantic validation. Errors are collected, not thrown.',
    input: 'AST',
    output: 'Symbol table + types + diagnostics',
  },
  {
    num: '4',
    name: 'Preprocessing',
    file: 'src/ast_preprocessor.py',
    desc: 'Nine sub-passes annotate the AST for the backend: pointer lowering, shadowing, mutation analysis, hoisting.',
    input: 'AST + semantic context',
    output: 'Annotated AST',
  },
  {
    num: '5',
    name: 'Codegen',
    file: 'src/backends/',
    desc: 'Pluggable backends read annotations to emit target code. Zig (zig.py) and C11 (c.py) are both supported.',
    input: 'Annotated AST',
    output: 'Zig or C source',
  },
]

export default function Pipeline() {
  return (
    <div className="page">
      <PageHeader
        title="Pipeline"
        summary="Five iterative stages from source to output."
      />

      <SectionPanel title="Pipeline stages">
        <p className="text-secondary">
          <code className="doc-inline-code">Source</code> &rarr; <code className="doc-inline-code">Tokens</code> &rarr;{' '}
          <code className="doc-inline-code">AST</code> &rarr; <code className="doc-inline-code">Annotated AST</code> &rarr;{' '}
          <code className="doc-inline-code">Zig / C</code>
        </p>
      </SectionPanel>

      <section className="stack-2">
        {stages.map((stage) => (
          <article key={stage.num} className="section-panel">
            <div className="pipeline-stage-head">
              <span className="pipeline-stage-num">{stage.num}</span>
              <div>
                <h2 className="section-title mb-1">
                  {stage.name}
                </h2>
                <code className="doc-inline-code">{stage.file}</code>
              </div>
            </div>
            <p className="text-secondary mt-2">{stage.desc}</p>
            <p className="text-tertiary text-tiny">
              {stage.input} &rarr; {stage.output}
            </p>
          </article>
        ))}
      </section>

      <SectionPanel title="Design notes">
        <ul className="doc-list">
          <li>No recursive AST walks anywhere. Everything uses explicit stacks.</li>
          <li>Preprocessor annotations (<code className="doc-inline-code">emit_name</code>, <code className="doc-inline-code">is_mutable</code>, <code className="doc-inline-code">resolved_type</code>) bridge stages so the backend doesn't recompute.</li>
          <li>Backend is pluggable. <code className="doc-inline-code">src/backends/base.py</code> defines the contract.</li>
        </ul>
      </SectionPanel>

      <SectionPanel title="Backend notes">
        <ul className="doc-list">
          <li>Zig and C backends both emit source from the annotated AST.</li>
          <li>C output is validated with <code className="doc-inline-code">zig cc</code> for current examples.</li>
          <li>New match forms and backend parity checks should be verified before relying on newly added forms.</li>
        </ul>
      </SectionPanel>
    </div>
  )
}
