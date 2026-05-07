import CodeBlock from '../components/CodeBlock'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const ioFunctions = [
  ['io.println(s: string)', 'Print with newline'],
  ['io.print(s: string)', 'Print without newline'],
  ['io.eprintln(s: string)', 'Print to stderr'],
]

const mathFunctions = [
  ['sqrt_f32(x: f32) f32', 'Square root'],
  ['sqrt_f64(x: f64) f64', 'Square root'],
  ['abs_f32(x: f32) f32', 'Absolute value'],
  ['abs_f64(x: f64) f64', 'Absolute value'],
  ['floor_f32(x: f32) f32', 'Floor'],
  ['floor_f64(x: f64) f64', 'Floor'],
  ['ceil_f32(x: f32) f32', 'Ceiling'],
  ['ceil_f64(x: f64) f64', 'Ceiling'],
  ['sin_f32(x: f32) f32', 'Sine'],
  ['sin_f64(x: f64) f64', 'Sine'],
  ['cos_f32(x: f32) f32', 'Cosine'],
  ['cos_f64(x: f64) f64', 'Cosine'],
  ['tan_f32(x: f32) f32', 'Tangent'],
  ['tan_f64(x: f64) f64', 'Tangent'],
  ['log_f32(x: f32) f32', 'Natural log'],
  ['log_f64(x: f64) f64', 'Natural log'],
  ['exp_f32(x: f32) f32', 'Exponential'],
  ['exp_f64(x: f64) f64', 'Exponential'],
  ['min_f32(a: f32, b: f32) f32', 'Minimum'],
  ['min_f64(a: f64, b: f64) f64', 'Minimum'],
  ['max_f32(a: f32, b: f32) f32', 'Maximum'],
  ['max_f64(a: f64, b: f64) f64', 'Maximum'],
]

const intrinsics = [
  ['@size_of(T)', 'Size of type in bytes'],
  ['@align_of(T)', 'Alignment of type'],
  ['@type_id(T)', 'Unique numeric type identifier'],
  ['@type_name(T)', 'Type name as string'],
  ['@type_set(...)', 'Define type set constraints'],
  ['@unreachable()', 'Mark code as unreachable'],
  ['@likely(cond)', 'Branch hint'],
  ['@unlikely(cond)', 'Branch hint'],
]

export default function Stdlib() {
  return (
    <div className="page">
      <PageHeader
        title="Standard Library"
        summary="Built-in modules and compiler intrinsics."
      />

      <SectionPanel title="io">
        <DataTable
          caption="Standard io module functions."
          headers={['Function', 'Description']}
          rows={ioFunctions.map(([sig, desc]) => [
            <code className="doc-inline-code" key={sig}>{sig}</code>,
            desc,
          ])}
        />
        <CodeBlock
          lang="a7"
          code={`io :: import "std/io"

main :: fn() {
    io.println("Hello, World!")
    io.print("no newline")
}`}
        />
      </SectionPanel>

      <SectionPanel title="math">
        <DataTable
          caption="Standard math module functions."
          headers={['Function', 'Description']}
          rows={mathFunctions.map(([sig, desc]) => [
            <code className="doc-inline-code" key={sig}>{sig}</code>,
            desc,
          ])}
        />
        <CodeBlock
          lang="a7"
          code={`math :: import "std/math"

main :: fn() {
    x := sqrt_f32(16.0)
    y := abs_f64(-42.0)
    z := max_f32(2.0, 10.0)
}`}
        />
      </SectionPanel>

      <SectionPanel title="Stub modules" subtitle="These files exist in the source tree but are not registered as available stdlib modules yet.">
        <ul className="doc-list">
          <li><strong>mem</strong> — source stub only; byte-copy/fill/alloc APIs are not documented as available.</li>
          <li><strong>string</strong> — source stub only; string utility APIs are not documented as available.</li>
        </ul>
      </SectionPanel>

      <SectionPanel title="Intrinsics">
        <DataTable
          caption="Compiler intrinsics available in A7."
          headers={['Intrinsic', 'Description']}
          rows={intrinsics.map(([name, desc]) => [
            <code className="doc-inline-code" key={name}>{name}</code>,
            desc,
          ])}
        />
      </SectionPanel>
    </div>
  )
}
