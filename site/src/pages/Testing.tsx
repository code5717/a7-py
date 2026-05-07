import CodeBlock from '../components/CodeBlock'
import DataTable from '../components/DataTable'
import MetricTile from '../components/MetricTile'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const layers = [
  ['Tokenizer', 'test/test_tokenizer.py', 'Token generation, literals, keywords, operators, error cases.'],
  ['Parser', 'test/test_parser_*.py', 'AST generation for all language constructs.'],
  ['Semantic', 'test/test_semantic_*.py', 'Name resolution, type checking, validations.'],
  ['Codegen', 'test/test_codegen_zig.py', 'A7 to Zig emission and build checks.'],
  ['End-to-end', 'test/test_examples_e2e.py', 'Compile, build, run, compare output with golden fixtures.'],
  ['Error stages', 'test/test_error_stage_matrix.py', 'Exit code stability across modes and formats.'],
]

export default function Testing() {
  return (
    <div className="page">
      <PageHeader
        title="Testing"
        summary="Commands and coverage."
      />

      <section className="metric-grid">
        <MetricTile label="Tests" value="Run pytest" note="status depends on your branch state" />
        <MetricTile label="Examples E2E" value="Run verifier" note="scripts/verify_examples_e2e.py" />
        <MetricTile label="Error checks" value="stage matrix" note="modes + output formats" />
      </section>

      <SectionPanel title="Running tests">
        <CodeBlock
          lang="bash"
          code={`PYTHONPATH=. uv run pytest                        # everything
PYTHONPATH=. uv run pytest --tb=no -q              # summary only
PYTHONPATH=. uv run pytest test/test_tokenizer.py   # one file
PYTHONPATH=. uv run pytest -k "generic" -v          # filter`}
        />
      </SectionPanel>

      <SectionPanel title="Layers">
        <DataTable
          caption="Compiler test layers by scope and primary test files."
          headers={['Layer', 'Files', 'Scope']}
          rows={layers.map(([name, file, desc]) => [
            name,
            <code className="doc-inline-code" key={`${name}-file`}>{file}</code>,
            desc,
          ])}
        />
      </SectionPanel>

      <SectionPanel title="Scripts">
        <DataTable
          caption="Repository scripts for broader verification passes."
          headers={['Script', 'What it does']}
          rows={[
            [<code className="doc-inline-code" key="err">scripts/verify_error_stages.py</code>, 'Check error reporting across all modes and formats'],
            [<code className="doc-inline-code" key="e2e">scripts/verify_examples_e2e.py</code>, 'Compile, build, run, verify outputs for all examples'],
            [<code className="doc-inline-code" key="all">run_all_tests.sh</code>, 'Run test groups with summary'],
          ]}
        />
      </SectionPanel>

      <SectionPanel title="Guarantees">
        <ul className="doc-list">
          <li>All AST traversals are iterative. No recursion.</li>
          <li>Example behavior is validated by <code className="doc-inline-code">scripts/verify_examples_e2e.py</code>.</li>
          <li>Exit-code contracts are validated by <code className="doc-inline-code">test/test_error_stage_matrix.py</code>.</li>
        </ul>
      </SectionPanel>
    </div>
  )
}
