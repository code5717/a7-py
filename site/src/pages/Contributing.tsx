import CodeBlock from '../components/CodeBlock'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const pitfalls = [
  ['and, or, not', '&&, ||, !', 'Keywords, not symbols'],
  ['x.adr', '&x', 'Property syntax for address-of'],
  ['p.val', '*p', 'Property syntax for dereference'],
  ['$T', 'T', 'Generic params need $ prefix'],
  ['PI :: 3.14', 'const PI = 3.14', ':: for constants'],
  ['x := 0', 'let x = 0', ':= for variables'],
  ['arr: [5]i32', 'arr = nil', 'Arrays can\'t be nil'],
]

export default function Contributing() {
  return (
    <div className="page">
      <PageHeader
        title="Contributing"
        summary="Setup, workflow, checks."
      />

      <SectionPanel title="Setup">
        <CodeBlock
          lang="bash"
          code={`git clone https://github.com/Airbus5717/a7-py.git
cd a7-py
uv sync
PYTHONPATH=. uv run pytest --tb=no -q`}
        />
      </SectionPanel>

      <SectionPanel title="Rules">
        <ul className="doc-list">
          <li>No recursion in AST traversal. Use explicit stacks. Pipeline must work at recursion limit 100.</li>
          <li>Use exact attribute names: <code className="doc-inline-code">node.operator</code>, <code className="doc-inline-code">node.literal_value</code>, <code className="doc-inline-code">node.parameter_types</code>.</li>
          <li>Semantic errors are collected, not thrown. The pipeline keeps going.</li>
          <li>Preprocessor annotations bridge stages. Set once, consumed by backend.</li>
        </ul>
      </SectionPanel>

      <SectionPanel title="Workflow">
        <ol className="doc-list">
          <li>Read the code near your change before editing.</li>
          <li>Run tests before and after.</li>
          <li>One concern per commit.</li>
          <li>Update <code className="doc-inline-code">CHANGELOG.md</code>, <code className="doc-inline-code">MISSING_FEATURES.md</code>, and <code className="doc-inline-code">AGENTS.md</code> when relevant.</li>
        </ol>
      </SectionPanel>

      <SectionPanel title="Tests">
        <CodeBlock
          lang="bash"
          code={`PYTHONPATH=. uv run pytest --tb=no -q            # all tests
PYTHONPATH=. uv run pytest -k "generic" -v        # filter by name
PYTHONPATH=. uv run pytest test/test_tokenizer.py  # one file`}
        />
        <ul className="doc-list mt-2">
          <li>All existing tests must pass.</li>
          <li>New features need tests. Bug fixes need regression tests.</li>
        </ul>
      </SectionPanel>

      <SectionPanel title="Common mistakes">
        <DataTable
          caption="Common A7 syntax mistakes and their corrected forms."
          headers={['Right', 'Wrong', 'Why']}
          rows={pitfalls.map(([right, wrong, note]) => [
            <code className="doc-inline-code" key={`${right}-r`}>{right}</code>,
            <code className="doc-inline-code" key={`${wrong}-w`}>{wrong}</code>,
            note,
          ])}
        />
      </SectionPanel>

      <SectionPanel title="File layout">
        <CodeBlock
          code={`a7-py/
  main.py
  src/
    tokens.py            # tokenizer
    parser.py            # parser
    ast_nodes.py         # AST types
    compile.py           # pipeline driver
    errors.py            # error types
    types.py             # type system
    ast_preprocessor.py  # 9-pass annotator
    passes/              # semantic analysis
    backends/            # code generation
    stdlib/              # standard library
  test/
  examples/`}
        />
      </SectionPanel>
    </div>
  )
}
