import { Link } from 'react-router-dom'
import CodeBlock from '../components/CodeBlock'
import DataTable from '../components/DataTable'
import DocCallout from '../components/DocCallout'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'

const KEYWORD_GROUPS: Array<[string, string]> = [
  ['Control flow', 'if else match case while for in break continue fall ret defer del'],
  ['Declarations and modules', 'fn struct enum union import pub'],
  ['Type and value words', 'bool char string i8 i16 i32 i64 u8 u16 u32 u64 isize usize f32 f64 ref new nil true false'],
  ['Operators and helpers', 'and or not as where'],
]

const LITERAL_FORMS: Array<[string, string, string]> = [
  ['Integer', '123, 1_000_000, 0b1010, 0o755, 0xFF', 'Binary, octal, decimal, and hex with underscores'],
  ['Float', '3.14, .5, 10., 1e9, 1.5e-3', 'Scientific notation supported'],
  ['Char', `'A', '\\n', '\\x41'`, 'Single quoted, one character or valid escape'],
  ['String', `"hello", "line\\nnext"`, 'Double quoted'],
  ['Bool', 'true, false', 'Boolean literals'],
  ['Nil', 'nil', 'Null-like literal for ref types'],
]

const PRIMITIVE_TYPES: Array<[string, string, string]> = [
  ['bool', '1 byte', 'Boolean'],
  ['char', '1 byte', 'ASCII character'],
  ['i8 i16 i32 i64', '1 to 8 bytes', 'Signed integers'],
  ['u8 u16 u32 u64', '1 to 8 bytes', 'Unsigned integers'],
  ['usize', 'Platform-sized', 'Memory sizes, lengths, and indices'],
  ['isize', 'Platform-sized', 'Signed pointer offsets only'],
  ['f32 f64', '4 or 8 bytes', 'IEEE-754 floating-point'],
  ['string', 'Pointer + length', 'Immutable string view'],
]

const TYPE_FORMS: Array<[string, string, string]> = [
  ['Arrays', '[N]T', 'Fixed-size array'],
  ['Slices', '[]T', 'Dynamically sized view'],
  ['References', 'ref T', 'Pointer/reference type'],
  ['Function type', 'fn(T1, T2) Ret', 'Callable type signature'],
  ['Inline struct type', 'struct { x: i32, y: i32 }', 'Anonymous record type'],
  ['Named type alias', 'Vec3 :: [3]f32', 'Alias for any type expression'],
]

const OPERATORS: Array<[string, string]> = [
  ['Arithmetic', '+  -  *  /  %'],
  ['Comparison', '==  !=  <  <=  >  >='],
  ['Logical', 'and  or  not  !'],
  ['Bitwise', '&  |  ^  ~  <<  >>'],
  ['Assignment', '=  +=  -=  *=  /=  %=  &=  |=  ^=  <<=  >>='],
  ['Other syntax operators', '.  ..  :  ::  :='],
]

const OP_PRECEDENCE: Array<[string, string]> = [
  ['Highest', 'Postfix: call (), index [], field .'],
  ['Unary', '-  not  !  ~'],
  ['Multiplicative', '*  /  %'],
  ['Additive', '+  -'],
  ['Shift', '<<  >>'],
  ['Relational', '<  <=  >  >='],
  ['Equality', '==  !='],
  ['Bitwise', '& then ^ then |'],
  ['Logical', 'and then or'],
]

const INTRINSICS: Array<[string, string]> = [
  ['@size_of(T)', 'Size of type in bytes'],
  ['@align_of(T)', 'Alignment requirement of a type'],
  ['@type_id(T)', 'Compiler type identifier'],
  ['@type_name(T)', 'Type name string'],
  ['@type_set(...)', 'Build type sets for generic constraints'],
  ['@unreachable()', 'Mark unreachable code path'],
  ['@likely(cond), @unlikely(cond)', 'Branch prediction hint'],
]

const IO_FUNCTIONS: Array<[string, string]> = [
  ['io.println(s: string)', 'Print with newline'],
  ['io.print(s: string)', 'Print without newline'],
  ['io.eprintln(s: string)', 'Print to stderr'],
]

const MATH_FUNCTIONS: Array<[string, string]> = [
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

export default function Language() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="Reference"
        title="Language Reference"
        summary="Syntax, types, memory, modules, and grammar."
      />

      <SectionPanel title="At a Glance">
        <DataTable
          caption="Core syntax forms used across the language."
          headers={['Construct', 'Syntax', 'Notes']}
          rows={[
            [<code className="doc-inline-code">constant</code>, <code className="doc-inline-code">name :: value</code>, 'Immutable binding'],
            [<code className="doc-inline-code">variable</code>, <code className="doc-inline-code">name := value</code>, 'Mutable binding with inference'],
            [<code className="doc-inline-code">typed variable</code>, <code className="doc-inline-code">name: Type = value</code>, 'Initializer optional inside function bodies'],
            [<code className="doc-inline-code">function</code>, <code className="doc-inline-code">name :: fn(params) Ret {'{...}'}</code>, 'Return type is optional (void if omitted)'],
            [<code className="doc-inline-code">type alias</code>, <code className="doc-inline-code">Name :: TypeExpr</code>, 'Includes function and generic type forms'],
            [<code className="doc-inline-code">terminator</code>, <code className="doc-inline-code">{'\\n'} or ;</code>, 'Newline and semicolon are both statement terminators'],
          ]}
        />
      </SectionPanel>

      <SectionPanel title="Lexical Structure">
        <DataTable
          caption="Tokenizer behavior and token-level rules."
          headers={['Rule', 'Behavior']}
          rows={[
            [<code className="doc-inline-code">Source encoding</code>, 'ASCII-focused; identifiers are ASCII alphanumeric + underscore'],
            [<code className="doc-inline-code">Whitespace</code>, 'Spaces and carriage returns are ignored; tabs are rejected'],
            [<code className="doc-inline-code">Terminators</code>, 'Every newline is a statement terminator token (deduplicated)'],
            [<code className="doc-inline-code">Builtin IDs</code>, 'Names that start with @ are tokenized as builtins (example: @size_of)'],
            [<code className="doc-inline-code">Generic IDs</code>, 'Names that start with $ are generic type tokens (example: $T)'],
          ]}
        />

        <h3 className="section-title subsection-title spaced">Comments</h3>
        <CodeBlock
          lang="a7"
          code={`// Single-line comment
# Alternative single-line comment

/* Multi-line comments are supported.
   Nested multi-line comments are also supported:
   /* inner comment */
*/`}
        />

        <h3 className="section-title subsection-title spaced">Keywords</h3>
        <DataTable
          caption="Reserved keyword groups in the tokenizer."
          headers={['Group', 'Keywords']}
          rows={KEYWORD_GROUPS.map(([group, words]) => [
            group,
            <code className="doc-inline-code" key={group}>{words}</code>,
          ])}
        />
      </SectionPanel>

      <SectionPanel title="Literals">
        <DataTable
          caption="Literal forms accepted by the parser."
          headers={['Kind', 'Examples', 'Notes']}
          rows={LITERAL_FORMS.map(([kind, examples, notes]) => [
            kind,
            <code className="doc-inline-code" key={kind}>{examples}</code>,
            notes,
          ])}
        />
        <CodeBlock
          lang="a7"
          code={`main :: fn() {
    dec := 123
    hex := 0xFF
    bin := 0b1010
    sci := 1.25e3
    ch: char = '\\n'
    text := "hello"
    ok := true
    p: ref i32 = nil
}`}
        />
      </SectionPanel>

      <SectionPanel title="Type System">
        <h3 className="section-title subsection-title">Primitive Types</h3>
        <DataTable
          caption="Primitive value types in A7."
          headers={['Type', 'Size', 'Meaning']}
          rows={PRIMITIVE_TYPES.map(([typeName, size, meaning]) => [
            <code className="doc-inline-code" key={typeName}>{typeName}</code>,
            size,
            meaning,
          ])}
        />

        <h3 className="section-title subsection-title spaced">Composite and Derived Types</h3>
        <DataTable
          caption="Common type expressions."
          headers={['Category', 'Syntax', 'Description']}
          rows={TYPE_FORMS.map(([category, syntax, description]) => [
            category,
            <code className="doc-inline-code" key={category}>{syntax}</code>,
            description,
          ])}
        />

        <CodeBlock
          lang="a7"
          code={`Vec3 :: [3]f32
BinaryOp :: fn(i32, i32) i32

Point :: struct {
    x: f32
    y: f32
}

State :: enum { Idle, Running, Done }

Value :: union {
    i: i32
    f: f32
}

Tagged :: union(tag) {
    ok: i32
    err: string
}`}
        />
      </SectionPanel>

      <SectionPanel title="Declarations">
        <CodeBlock
          lang="a7"
          code={`// Top-level constants and functions
PI :: 3.14159
add :: fn(x: i32, y: i32) i32 { ret x + y }

// Mutable variables
count := 0

// Typed declarations
name: string = "A7"
uninitialized: i32

// Type aliases
Meters :: f64
Mapper :: fn(i32) i32

main :: fn() {
    local := 1
    local_typed: i32 = 2
    local_const :: 42
}`}
        />
        <p className="text-secondary mt-1">
          Use <code className="doc-inline-code">::</code> for immutable declarations and <code className="doc-inline-code">:=</code> for mutable declarations.
        </p>
      </SectionPanel>

      <SectionPanel title="Expressions">
        <DataTable
          caption="Expression categories and representative forms."
          headers={['Category', 'Examples']}
          rows={[
            ['Primary', <code className="doc-inline-code">42, "text", value, (expr)</code>],
            ['Unary', <code className="doc-inline-code">-x, not done, !flag, ~mask</code>],
            ['Binary', <code className="doc-inline-code">a + b, x {'<'} y, p and q, flags {'<<'} 2</code>],
            ['Call', <code className="doc-inline-code">fn_name(arg1, arg2)</code>],
            ['Index and slice', <code className="doc-inline-code">arr[i], arr[start..end], arr[..end]</code>],
            ['Field and pointer ops', <code className="doc-inline-code">obj.field, value.adr, ptr.val</code>],
            ['Constructors', <code className="doc-inline-code">Type{'{...}'}, new Type, new(Type)</code>],
            ['Casts and intrinsics', <code className="doc-inline-code">cast(i32, x), @size_of(i64)</code>],
            ['Expression control flow', <code className="doc-inline-code">if cond {'{'}a{'}'} else {'{'}b{'}'}, match x {'{'} ... {'}'}</code>],
          ]}
        />

        <CodeBlock
          lang="a7"
          code={`result := cast(i32, 4.8)
size := @size_of(i32)

arr: [5]i32 = [10, 20, 30, 40, 50]
mid := arr[1..4]

point := Point{x: 10.0, y: 20.0}
ptr := point.adr
x := ptr.val.x

kind := if x > 0 { "positive" } else { "zero-or-negative" }`}
        />
      </SectionPanel>

      <SectionPanel title="Control Flow and Statements">
        <CodeBlock
          lang="a7"
          code={`if score >= 90 {
    grade := "A"
} else if score >= 80 {
    grade := "B"
} else {
    grade := "C"
}

while running {
    step()
}

for i := 0; i < 10; i += 1 {
    if i == 7 { break }
}

for value in values {
    use(value)
}

for i, value in values {
    io.println("idx={} value={}", i, value)
}

@outer while true {
    continue outer
}

match code {
    case 0: { io.println("ok") }
    case 1, 2: {
        io.println("retry")
        fall
    }
    case 3..10: { io.println("wait") }
    else: { io.println("unknown") }
}`}
        />
        <p className="text-secondary mt-1">
          <code className="doc-inline-code">fall</code> continues into the next match case body. It must be the final direct statement of a non-final case.
        </p>
        <DocCallout tone="warning">
          Backend note: C match expressions support literal, enum, range, wildcard, existing-identifier patterns, and single-evaluation lowering for side-effectful scrutinees. True identifier-capture patterns remain open.
        </DocCallout>
      </SectionPanel>

      <SectionPanel title="Functions">
        <CodeBlock
          lang="a7"
          code={`// Standard function
add :: fn(a: i32, b: i32) i32 {
    ret a + b
}

// Void return when omitted
greet :: fn(name: string) {
    io.println("hello {}", name)
}

// Function type alias
Reducer :: fn(i32, i32) i32

// Variadic parameter
sum :: fn(values: ..i32) i32 {
    total := 0
    for value in values { total += value }
    ret total
}

// Method style is normal function + ref receiver
Counter :: struct { value: i32 }
inc :: fn(counter: ref Counter) {
    counter.val.value += 1
}`}
        />
        <DocCallout tone="info">
          Function declarations must be named. Anonymous function literals are not a declaration form in the current grammar.
        </DocCallout>
      </SectionPanel>

      <SectionPanel title="Memory and Pointers">
        <CodeBlock
          lang="a7"
          code={`x := 42
x_ptr: ref i32 = x.adr
x_ptr.val += 1

heap_value := new i32
heap_value.val = 99
del heap_value

main :: fn() {
    buf: [256]u8
    slice := buf[0..256]

    maybe: ref i32 = nil
    if maybe == nil {
        ret
    }
}`}
        />
        <p className="text-secondary mt-1">
          Address-of and dereference use property syntax: <code className="doc-inline-code">.adr</code> and <code className="doc-inline-code">.val</code>.
        </p>
      </SectionPanel>

      <SectionPanel title="Generics">
        <CodeBlock
          lang="a7"
          code={`identity :: fn(x: $T) $T {
    ret x
}

Pair :: struct {
    first: $T
    second: $U
}

pair := Pair(i32, string){ first: 7, second: "seven" }

Numeric :: @type_set(i8, i16, i32, i64, f32, f64)

abs_generic :: fn(x: $T) $T {
    ret if x < 0 { -x } else { x }
}`}
        />
        <DocCallout tone="warning">
          Some generic semantic paths are still in progress (constraint-aware arithmetic, full substitution in some struct-literal and field-access paths). See <Link to="/status">Status</Link> for current gaps.
        </DocCallout>
      </SectionPanel>

      <SectionPanel title="Modules and Visibility">
        <CodeBlock
          lang="a7"
          code={`// Aliased import
io :: import "std/io"

// Direct module import forms
import "vector" { Vec3, dot }
using import "vector"

pub Vec2 :: struct {
    pub x: f32
    pub y: f32
}

pub length :: fn(v: Vec2) f32 {
    ret sqrt_f32(v.x * v.x + v.y * v.y)
}`}
        />
        <p className="text-secondary mt-1">
          Every <code className="doc-inline-code">.a7</code> file is a module. Use <code className="doc-inline-code">pub</code> to export top-level declarations and struct fields.
        </p>
      </SectionPanel>

      <SectionPanel title="Standard Library" id="standard-library">
        <p className="text-secondary">
          Current virtual stdlib support is intentionally small: <code className="doc-inline-code">std/io</code> and{' '}
          <code className="doc-inline-code">std/math</code>. Source stubs such as <code className="doc-inline-code">mem</code> and{' '}
          <code className="doc-inline-code">string</code> exist in the repository, but are not registered as public modules yet.
        </p>
        <h3 id="io" className="section-title subsection-title spaced">io</h3>
        <DataTable
          caption="Standard io module functions."
          headers={['Function', 'Description']}
          rows={IO_FUNCTIONS.map(([sig, desc]) => [
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
        <h3 id="math" className="section-title subsection-title spaced">math</h3>
        <DataTable
          caption="Standard math module functions."
          headers={['Function', 'Description']}
          rows={MATH_FUNCTIONS.map(([sig, desc]) => [
            <code className="doc-inline-code" key={sig}>{sig}</code>,
            desc,
          ])}
        />
        <h3 id="stub-modules" className="section-title subsection-title spaced">Stub modules</h3>
        <ul className="doc-list">
          <li><strong>mem</strong> — source stub only; byte-copy/fill/alloc APIs are not registered as available modules yet.</li>
          <li><strong>string</strong> — source stub only; string utility APIs are not registered as available modules yet.</li>
        </ul>
      </SectionPanel>

      <SectionPanel title="Builtins and Intrinsics">
        <DataTable
          caption="Builtin intrinsics parsed as @-prefixed call expressions."
          headers={['Intrinsic', 'Purpose']}
          rows={INTRINSICS.map(([name, purpose]) => [
            <code className="doc-inline-code" key={name}>{name}</code>,
            purpose,
          ])}
        />
      </SectionPanel>

      <SectionPanel title="Operators and Precedence">
        <DataTable
          caption="Operator families."
          headers={['Category', 'Operators']}
          rows={OPERATORS.map(([category, ops]) => [category, <code className="doc-inline-code" key={category}>{ops}</code>])}
        />

        <h3 className="section-title subsection-title spaced">Precedence (High to Low)</h3>
        <DataTable
          headers={['Level', 'Operators']}
          rows={OP_PRECEDENCE.map(([level, ops]) => [level, <code className="doc-inline-code" key={level}>{ops}</code>])}
        />
      </SectionPanel>

      <SectionPanel title="Grammar Quick Reference">
        <CodeBlock
          lang="text"
          code={`declaration :=
  identifier "::" (fn_decl | struct_decl | enum_decl | union_decl | import_decl | type_expr | expression)
| identifier ":=" expression
| identifier ":" type_expr ("=" expression)?
| "import" string_literal ("{" identifier ("," identifier)* "}")?
| "using" "import" string_literal

statement :=
  "ret" expression?
| "break" identifier?
| "continue" identifier?
| "fall"
| "if" expression statement ("else" statement)?
| "while" expression statement
| "for" block
| "for" identifier "in" expression block
| "for" identifier "," identifier "in" expression block
| "for" init_stmt terminator expression terminator update_stmt block
| "match" expression "{" case_branch* else_branch? "}"
| "defer" statement
| "del" expression
| block
| expression_or_assignment

type_expr :=
  primitive
| identifier ("(" type_expr ("," type_expr)* ")")?
| "$" identifier
| "ref" type_expr
| "[" expression? "]" type_expr
| "fn" "(" type_expr ("," type_expr)* ")" type_expr?
| "struct" "{" field_list "}"
| "@type_set" "(" type_expr ("," type_expr)* ")"`}
        />
      </SectionPanel>

      <SectionPanel title="Implementation Notes">
        <DocCallout tone="success">
          Parsing coverage is complete for the language surface described here. The compiler runs tokenization, parsing, semantic passes, preprocessing, and code generation (Zig and C backends) end-to-end.
        </DocCallout>
        <DocCallout tone="warning">
          A small set of semantic features are still open: advanced match diagnostics, true match capture patterns, full generic specialization, and lifetime-style memory checks. For exact pass/fail status, see <Link to="/status">Status</Link> and <code className="doc-inline-code">MISSING_FEATURES.md</code>.
        </DocCallout>
      </SectionPanel>
    </div>
  )
}
