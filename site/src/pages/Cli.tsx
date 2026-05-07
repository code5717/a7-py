import CodeBlock from '../components/CodeBlock'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const modeRows = [
  ['compile', 'Full pipeline: tokenize, parse, check, codegen (default)'],
  ['tokens', 'Tokenize only'],
  ['ast', 'Tokenize + parse'],
  ['semantic', 'Tokenize + parse + type check'],
  ['pipeline', 'Full pipeline with intermediate output'],
  ['doc', 'Generate markdown report'],
]

const exitRows = [
  ['0', 'Success'],
  ['2', 'Bad arguments'],
  ['3', 'File not found'],
  ['4', 'Tokenizer error'],
  ['5', 'Parse error'],
  ['6', 'Semantic error'],
  ['7', 'Codegen error'],
  ['8', 'Internal bug'],
]

export default function Cli() {
  return (
    <div className="page">
      <PageHeader
        title="CLI"
        summary="How to invoke the compiler."
      />

      <SectionPanel title="Usage">
        <CodeBlock lang="bash" code={`uv run python main.py [OPTIONS] <file.a7>`} />
      </SectionPanel>

      <SectionPanel title="Modes">
        <DataTable
          caption="Compiler execution modes and stage coverage."
          headers={['Mode', 'What it does']}
          rows={modeRows.map(([mode, desc]) => [<code className="doc-inline-code" key={mode}>{mode}</code>, desc])}
        />
        <CodeBlock
          lang="bash"
          code={`uv run python main.py --mode tokens examples/001_hello.a7
uv run python main.py --mode ast examples/004_func.a7
uv run python main.py --verbose examples/009_struct.a7`}
        />
      </SectionPanel>

      <SectionPanel title="Flags">
        <DataTable
          caption="Common CLI flags."
          headers={['Flag', 'Effect']}
          rows={[
            [<code className="doc-inline-code" key="verbose">--verbose</code>, 'Show intermediate results'],
            [<code className="doc-inline-code" key="mode">--mode MODE</code>, 'Set pipeline stage'],
            [<code className="doc-inline-code" key="format">--format json</code>, 'Structured JSON output'],
            [<code className="doc-inline-code" key="docout">--doc-out PATH</code>, 'Write markdown report'],
          ]}
        />
      </SectionPanel>

      <SectionPanel title="Exit codes">
        <DataTable
          caption="Process exit codes returned by the CLI."
          headers={['Code', 'Meaning']}
          rows={exitRows.map(([code, meaning]) => [
            <code className="doc-inline-code" key={code}>{code}</code>,
            meaning,
          ])}
        />
        <p className="text-tertiary text-small mt-1">
          Stable across versions. Safe to use in CI scripts.
        </p>
      </SectionPanel>
    </div>
  )
}
