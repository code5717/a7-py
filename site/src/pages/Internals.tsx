import CodeBlock from '../components/CodeBlock'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const stages = [
  { label: 'Tokenizer', file: 'tokens.py' },
  { label: 'Parser', file: 'parser.py' },
  { label: 'Semantic', file: 'passes/' },
  { label: 'Preprocessor', file: 'ast_preprocessor.py' },
  { label: 'Codegen', file: 'backends/' },
]

const dataLabels = ['tokens', 'AST', 'symbols + types', 'annotated AST', 'Zig / C']

const subPasses = [
  { num: 1, name: '.adr/.val lowering' },
  { num: 2, name: 'Stdlib resolution' },
  { num: 3, name: 'Struct init normalization' },
  { num: 4, name: 'Mutation analysis' },
  { num: 5, name: 'Usage analysis' },
  { num: 6, name: 'Type inference' },
  { num: 7, name: 'Shadowing resolution' },
  { num: 8, name: 'Function hoisting' },
  { num: 9, name: 'Constant folding' },
]

const annotationList = [
  { name: 'is_mutable', desc: 'var vs const emission' },
  { name: 'is_used', desc: 'dead code elimination' },
  { name: 'emit_name', desc: 'shadow-safe names' },
  { name: 'resolved_type', desc: 'backend type mapping' },
  { name: 'hoisted', desc: 'nested fn → module level' },
  { name: 'stdlib_canonical', desc: 'builtin mapping' },
]

const testLayers = [
  ['Tokenizer', 'test/test_tokenizer.py', 'Token generation, literals, keywords, operators, error cases.'],
  ['Parser', 'test/test_parser_*.py', 'AST generation for language constructs.'],
  ['Semantic', 'test/test_semantic_*.py', 'Name resolution, type checking, validations.'],
  ['Codegen', 'test/test_codegen_zig.py, test/test_codegen_c.py', 'Zig/C emission and build checks.'],
  ['End-to-end', 'test/test_examples_e2e*.py', 'Compile, build, run, compare golden output.'],
  ['Release gate', 'run_all_tests.sh', 'Full local gate, artifact builds, docs style, error matrix.'],
]

export default function Internals() {
  return (
    <div className="page">
      <PageHeader
        title="Internals"
        summary="Compiler structure by file."
      />

      {/* ── Pipeline flow ── */}
      <SectionPanel title="Pipeline" id="pipeline">
        <div className="flow-strip">
          {stages.map((s, i) => (
            <div key={s.label} className="flow-strip-item">
              <div className="flow-strip-node">
                <span className="flow-strip-label">{s.label}</span>
                <code className="flow-strip-file">a7/{s.file}</code>
              </div>
              {i < dataLabels.length && (
                <span className="flow-strip-edge">{dataLabels[i]}</span>
              )}
            </div>
          ))}
        </div>
        <p className="text-tertiary text-tiny mt-2">
          All traversals are iterative. The full pipeline works at <code className="doc-inline-code">sys.setrecursionlimit(100)</code>.
        </p>
      </SectionPanel>

      {/* ── Core modules ── */}
      <SectionPanel title="Modules">
        <DataTable
          headers={['File', 'Role']}
          rows={[
            [<code className="doc-inline-code" key="t">a7/tokens.py</code>, 'Tokenizer — generics ($T), nested comments, all number formats'],
            [<code className="doc-inline-code" key="p">a7/parser.py</code>, 'Recursive descent with precedence climbing'],
            [<code className="doc-inline-code" key="a">a7/ast_nodes.py</code>, 'ASTNode dataclass + NodeKind enum (60 kinds)'],
            [<code className="doc-inline-code" key="c">a7/compile.py</code>, 'Pipeline driver, stage sequencing, exit codes'],
            [<code className="doc-inline-code" key="e">a7/errors.py</code>, '82 error codes, SourceSpan, Rich formatting'],
            [<code className="doc-inline-code" key="ty">a7/types.py</code>, '14 type kinds, all frozen/hashable'],
            [<code className="doc-inline-code" key="pp">a7/ast_preprocessor.py</code>, '9 iterative sub-passes annotating AST for backend'],
            [<code className="doc-inline-code" key="st">a7/symbol_table.py</code>, 'Symbol + Scope + ModuleTable (hierarchical lookup)'],
            [<code className="doc-inline-code" key="bb">a7/backends/base.py</code>, 'Abstract backend contract (generate + visit)'],
            [<code className="doc-inline-code" key="bz">a7/backends/zig.py</code>, 'Zig code generator, reads all annotations'],
            [<code className="doc-inline-code" key="bc">a7/backends/c.py</code>, 'C11 code generator, labeled loops via goto, slice structs'],
          ]}
        />
      </SectionPanel>

      {/* ── Semantic analysis ── */}
      <SectionPanel title="Semantic analysis">
        <p className="text-secondary mb-2">
          Three sequential passes. Each is gated — downstream only runs if upstream succeeds.
          Errors within a pass are collected, not thrown.
        </p>
        <div className="pass-cards">
          <div className="pass-card">
            <span className="pass-card-num">1</span>
            <div>
              <strong>Name resolution</strong>
              <p className="text-tertiary pass-card-copy">Builds SymbolTable with hierarchical scopes</p>
              <code className="flow-strip-file">a7/passes/name_resolution.py</code>
            </div>
          </div>
          <div className="pass-card">
            <span className="pass-card-num">2</span>
            <div>
              <strong>Type checking</strong>
              <p className="text-tertiary pass-card-copy">Inference, checking, produces node_types map</p>
              <code className="flow-strip-file">a7/passes/type_checker.py</code>
            </div>
          </div>
          <div className="pass-card">
            <span className="pass-card-num">3</span>
            <div>
              <strong>Semantic validation</strong>
              <p className="text-tertiary pass-card-copy">Control flow, memory, defer, match exhaustiveness</p>
              <code className="flow-strip-file">a7/passes/semantic_validator.py</code>
            </div>
          </div>
        </div>
      </SectionPanel>

      {/* ── Preprocessor ── */}
      <SectionPanel title="Preprocessor">
        <p className="text-secondary mb-2">
          Runs after semantic analysis. Nine sub-passes, all iterative.
          Passes 1-3 run bottom-up on the whole tree. Passes 4-9 run per function.
        </p>
        <div className="subpass-grid">
          {subPasses.map((sp) => (
            <div key={sp.num} className="subpass-item">
              <span className="subpass-num">{sp.num}</span>
              <span className="subpass-name">{sp.name}</span>
            </div>
          ))}
        </div>
      </SectionPanel>

      {/* ── Annotations ── */}
      <SectionPanel title="Annotations">
        <p className="text-secondary mb-2">
          Set by the preprocessor, consumed by the backend. This is how stages talk without recomputation.
        </p>
        <div className="annotation-grid">
          {annotationList.map((a) => (
            <div key={a.name} className="annotation-card">
              <code className="doc-inline-code">{a.name}</code>
              <span className="text-tertiary text-micro">{a.desc}</span>
            </div>
          ))}
        </div>
      </SectionPanel>

      {/* ── AST design ── */}
      <SectionPanel title="AST design">
        <p className="text-secondary mb-2">
          Flat union pattern: one <code className="doc-inline-code">ASTNode</code> dataclass, optional fields,
          discriminated by <code className="doc-inline-code">NodeKind</code> enum (60 kinds).
        </p>
        <DataTable
          headers={['Group', 'Kinds']}
          rows={[
            [<strong key="tl">Top-level</strong>, 'PROGRAM, IMPORT, FUNCTION, STRUCT, UNION, ENUM, TYPE_ALIAS, CONST, VAR'],
            [<strong key="ty">Types</strong>, 'TYPE_PRIMITIVE, TYPE_IDENTIFIER, TYPE_GENERIC, TYPE_POINTER, TYPE_ARRAY, TYPE_SLICE, TYPE_FUNCTION'],
            [<strong key="ex">Expressions</strong>, 'LITERAL, IDENTIFIER, BINARY, UNARY, CALL, INDEX, FIELD_ACCESS, DEREF, CAST, IF_EXPR, NEW_EXPR'],
            [<strong key="st">Statements</strong>, 'BLOCK, IF_STMT, WHILE, FOR, FOR_IN, MATCH, BREAK, CONTINUE, RETURN, DEFER, DEL, ASSIGNMENT'],
          ]}
        />
        <div className="mt-2">
          <h3 className="section-subtitle mb-1">Critical attribute names</h3>
          <DataTable
            headers={['Correct', 'Wrong', 'Nodes']}
            rows={[
              [<code className="doc-inline-code" key="op">node.operator</code>, <code className="doc-inline-code" key="opw">node.op</code>, 'Binary, Unary, Assignment'],
              [<code className="doc-inline-code" key="lv">node.literal_value</code>, <code className="doc-inline-code" key="lvw">node.value</code>, 'Literal nodes'],
              [<code className="doc-inline-code" key="pt">node.parameter_types</code>, <code className="doc-inline-code" key="ptw">node.param_types</code>, 'Function type nodes'],
              [<code className="doc-inline-code" key="tt">node.target_type</code>, <span className="text-muted" key="ttw">n/a</span>, 'NEW_EXPR, TYPE_POINTER, CAST'],
            ]}
          />
        </div>
      </SectionPanel>

      {/* ── Type system ── */}
      <SectionPanel title="Type system">
        <p className="text-secondary mb-2">
          Frozen dataclasses — immutable and hashable. Used as dict keys in type maps.
        </p>
        <DataTable
          headers={['Class', 'What it represents']}
          rows={[
            [<code className="doc-inline-code" key="pr">PrimitiveType</code>, 'i8..i64, u8..u64, f32, f64, bool, char, string'],
            [<code className="doc-inline-code" key="ar">ArrayType</code>, '[N]T — fixed-size'],
            [<code className="doc-inline-code" key="sl">SliceType</code>, '[]T — dynamic view'],
            [<code className="doc-inline-code" key="po">PointerType / ReferenceType</code>, 'ptr T and ref T (only ref allows nil)'],
            [<code className="doc-inline-code" key="fn">FunctionType</code>, 'fn(params) return, optional variadic'],
            [<code className="doc-inline-code" key="sr">StructType / EnumType / UnionType</code>, 'Named composite types with fields/variants'],
            [<code className="doc-inline-code" key="gp">GenericParamType</code>, '$T with optional TypeSet constraint'],
            [<code className="doc-inline-code" key="gi">GenericInstanceType</code>, 'Monomorphized generic — List(i32)'],
          ]}
        />
      </SectionPanel>

      {/* ── Backend + errors + symbols ── */}
      <SectionPanel title="Backend lifecycle" id="backend-notes">
        <CodeBlock code={`# 1. reset()  — clear state
# 2. scan     — iterative walk to detect new/del/io usage
# 3. preamble — emit imports + allocator setup
# 4. walk     — visit() dispatches on NodeKind
# 5. output   — return accumulated Zig source

# Both backends read preprocessor annotations AND
# re-analyze mutations/usage locally (dual analysis)
# --backend c selects C11 output (validated with zig cc)`} />
      </SectionPanel>

      <SectionPanel title="Testing" id="testing">
        <div id="scripts" />
        <CodeBlock
          lang="bash"
          code={`PYTHONPATH=. uv run pytest --tb=no -q
uv run python scripts/verify_examples_e2e.py
uv run python scripts/verify_examples_e2e_c.py
uv run python scripts/verify_backend_parity.py
./run_all_tests.sh`}
        />
        <DataTable
          caption="Verification layers by scope."
          headers={['Layer', 'Files', 'Scope']}
          rows={testLayers.map(([name, file, desc]) => [
            name,
            <code className="doc-inline-code" key={`${name}-file`}>{file}</code>,
            desc,
          ])}
        />
      </SectionPanel>

      <SectionPanel title="Errors and symbols">
        <div className="stack-2">
          <div>
            <h3 className="section-subtitle">Error system</h3>
            <p className="text-secondary">
              82 error codes across 3 enums: <code className="doc-inline-code">TokenizerErrorType</code> (20),{' '}
              <code className="doc-inline-code">SemanticErrorType</code> (32),{' '}
              <code className="doc-inline-code">TypeErrorType</code> (30).
              Every error carries a <code className="doc-inline-code">SourceSpan</code> with line/column for precise underlines.
            </p>
          </div>
          <div>
            <h3 className="section-subtitle">Symbol table</h3>
            <p className="text-secondary">
              Hierarchical scopes with parent lookup. 10 symbol kinds.{' '}
              <code className="doc-inline-code">ModuleTable</code> tracks aliases, file-backed modules, and selected import metadata.
            </p>
          </div>
        </div>
      </SectionPanel>
    </div>
  )
}
