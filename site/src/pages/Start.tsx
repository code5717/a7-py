import { Link } from 'react-router-dom'
import CodeBlock from '../components/CodeBlock'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const HELLO = `io :: import "std/io"

main :: fn() {
    io.println("Hello, World!")
}`

const modeRows = [
  ['compile', 'Full pipeline and code generation (default)'],
  ['tokens', 'Tokenize only'],
  ['ast', 'Tokenize and parse'],
  ['semantic', 'Tokenize, parse, and check'],
  ['pipeline', 'Full pipeline with intermediate output'],
  ['doc', 'Generate a markdown report'],
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

const flagRows = [
  ['--verbose', 'Show intermediate results'],
  ['--mode MODE', 'Set pipeline stage'],
  ['--format json', 'Structured JSON output'],
  ['--backend zig', 'Select the Zig backend'],
  ['--doc-out PATH', 'Write markdown report'],
]

export default function Start() {
  return (
    <div className="page">
      <PageHeader
        title="Getting Started"
        summary="Install. Write. Run."
      />

      <SectionPanel title="Requirements">
        <ul className="doc-list">
          <li>Python 3.13+</li>
          <li><a href="https://docs.astral.sh/uv/" target="_blank" rel="noopener noreferrer">uv</a> package manager</li>
          <li>Zig 0.16.0 compiler (to run generated output)</li>
        </ul>
      </SectionPanel>

      <SectionPanel title="Install">
        <CodeBlock
          lang="bash"
          code={`git clone https://github.com/code5717/a7-py.git
cd a7-py
uv sync`}
        />
      </SectionPanel>

      <SectionPanel title="Write a program">
        <CodeBlock code={HELLO} lang="a7" title="hello.a7" />
      </SectionPanel>

      <SectionPanel title="Compile and run">
        <CodeBlock
          lang="bash"
          code={`# Compile to Zig
uv run python main.py examples/001_hello.a7

# Run generated output if you wrote hello.zig locally
zig run hello.zig

# Other modes
uv run python main.py --mode tokens examples/001_hello.a7
uv run python main.py --mode ast examples/001_hello.a7
uv run python main.py --format json examples/001_hello.a7`}
        />
      </SectionPanel>

      <SectionPanel title="CLI" id="cli" subtitle="Daily commands, modes, and stable exit codes.">
        <CodeBlock lang="bash" code={`uv run a7 [OPTIONS] <file.a7>
uv run python main.py [OPTIONS] <file.a7>   # repository compatibility wrapper`} />
        <div id="modes" />
        <DataTable
          caption="Compiler execution modes."
          headers={['Mode', 'What it does']}
          rows={modeRows.map(([mode, desc]) => [
            <code className="doc-inline-code" key={mode}>{mode}</code>,
            desc,
          ])}
        />
        <div id="flags" />
        <DataTable
          caption="Common CLI flags."
          headers={['Flag', 'Effect']}
          rows={flagRows.map(([flag, effect]) => [
            <code className="doc-inline-code" key={flag}>{flag}</code>,
            effect,
          ])}
        />
        <DataTable
          caption="Process exit codes returned by the CLI."
          headers={['Code', 'Meaning']}
          rows={exitRows.map(([code, meaning]) => [
            <code className="doc-inline-code" key={code}>{code}</code>,
            meaning,
          ])}
        />
      </SectionPanel>

      <SectionPanel title="Next">
        <ul className="doc-list">
          <li><Link to="/language">Language Reference</Link> — full syntax</li>
          <li><Link to="/examples">Examples</Link> — runnable programs to read</li>
          <li><Link to="/internals">Internals</Link> — pipeline and tests</li>
        </ul>
      </SectionPanel>
    </div>
  )
}
