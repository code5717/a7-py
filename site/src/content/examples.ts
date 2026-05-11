export const exampleModules = import.meta.glob<string>('../../../examples/*.a7', {
  query: '?raw',
  import: 'default',
})

const EXAMPLE_META = {
  '000_empty.a7': { title: 'Empty Program', category: 'Basics', desc: 'Minimal valid A7 program' },
  '001_hello.a7': { title: 'Hello World', category: 'Basics', desc: 'Print to stdout with io module' },
  '002_var.a7': { title: 'Variables', category: 'Basics', desc: 'Variable and constant declarations' },
  '003_comments.a7': { title: 'Comments', category: 'Basics', desc: 'Single-line and block comments' },
  '004_func.a7': { title: 'Functions', category: 'Basics', desc: 'Function declarations and calls' },
  '005_for_loop.a7': { title: 'For Loops', category: 'Control Flow', desc: 'C-style and range-based loops' },
  '006_if.a7': { title: 'Conditionals', category: 'Control Flow', desc: 'If-else statements and expressions' },
  '007_while.a7': { title: 'While Loops', category: 'Control Flow', desc: 'While loop patterns' },
  '008_switch.a7': { title: 'Match', category: 'Control Flow', desc: 'Pattern matching with literal cases' },
  '009_struct.a7': { title: 'Structs', category: 'Types', desc: 'Struct declarations and initialization' },
  '010_enum.a7': { title: 'Enums', category: 'Types', desc: 'Enumeration declarations and matching' },
  '011_memory.a7': { title: 'Memory', category: 'Memory', desc: 'Heap allocation with new/del' },
  '012_arrays.a7': { title: 'Arrays', category: 'Types', desc: 'Fixed-size arrays and slices' },
  '013_pointers.a7': { title: 'References', category: 'Memory', desc: 'Implicit ref-argument passing' },
  '014_generics.a7': { title: 'Generics', category: 'Types', desc: 'Generic functions and generic struct instances' },
  '015_types.a7': { title: 'Type System', category: 'Types', desc: 'Type aliases and composite types' },
  '016_unions.a7': { title: 'Unions', category: 'Types', desc: 'Untagged union field literals and access' },
  '017_methods.a7': { title: 'Receiver Functions', category: 'Types', desc: 'Method-style mutation through explicit ref receivers' },
  '018_modules.a7': { title: 'Modules', category: 'Basics', desc: 'Virtual stdlib imports with aliases' },
  '019_literals.a7': { title: 'Literals', category: 'Basics', desc: 'All literal formats: hex, octal, binary, escapes' },
  '020_operators.a7': { title: 'Operators', category: 'Basics', desc: 'Arithmetic, logical, bitwise, assignment' },
  '021_control_flow.a7': { title: 'Control Flow', category: 'Control Flow', desc: 'Combined control flow patterns' },
  '022_function_pointers.a7': { title: 'Function Pointers', category: 'Functions', desc: 'Raw function types, aliases, higher-order calls' },
  '023_inline_structs.a7': { title: 'Inline Structs', category: 'Types', desc: 'Anonymous struct return values' },
  '024_defer.a7': { title: 'Defer', category: 'Memory', desc: 'Resource management with defer' },
  '025_linked_list.a7': { title: 'Linked List', category: 'Data Structures', desc: 'Explicit next-index linked-list traversal' },
  '026_binary_tree.a7': { title: 'Binary Tree', category: 'Data Structures', desc: 'Stack-based binary tree traversal without recursion' },
  '027_callbacks.a7': { title: 'Callbacks', category: 'Functions', desc: 'Event dispatch through function pointers' },
  '028_state_machine.a7': { title: 'State Machine', category: 'Patterns', desc: 'State transitions through enum matching' },
  '029_sorting.a7': { title: 'Sorting', category: 'Algorithms', desc: 'Sorting with custom comparators' },
  '030_calculator.a7': { title: 'Calculator', category: 'Applications', desc: 'Math operations including sqrt, power' },
  '031_number_guessing.a7': { title: 'Number Guessing', category: 'Applications', desc: 'Deterministic number-guessing control-flow example' },
  '032_prime_numbers.a7': { title: 'Primes', category: 'Algorithms', desc: 'Trial-division prime checks and GCD' },
  '033_fibonacci.a7': { title: 'Fibonacci', category: 'Algorithms', desc: 'Iterative sequence generation with usize indexes' },
  '034_string_utils.a7': { title: 'String Utils', category: 'Applications', desc: 'Length, slicing, iteration, and char search' },
  '035_matrix.a7': { title: 'Matrix Ops', category: 'Applications', desc: '2x2 matrix addition with array +' },
  '036_control_flow_edges.a7': { title: 'Control Flow Edges', category: 'Control Flow', desc: 'Labeled loops, slices, and match-case defer scope' },
  '037_language_tour.a7': { title: 'Language Tour', category: 'Basics', desc: 'One-file tour of declarations, types, control flow, refs, heap values, and function pointers' },
} as const

function titleFromFile(file: string) {
  return file
    .replace(/^\d+_/, '')
    .replace(/\.a7$/, '')
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function exampleIdFromFile(file: string) {
  return file.replace(/\.a7$/, '')
}

export const EXAMPLES = Object.keys(exampleModules)
  .map((path) => {
    const file = path.split('/').pop() ?? path
    const meta = EXAMPLE_META[file as keyof typeof EXAMPLE_META]

    return {
      id: exampleIdFromFile(file),
      file,
      title: meta?.title ?? titleFromFile(file),
      category: meta?.category ?? 'Examples',
      desc: meta?.desc ?? 'Runnable A7 example',
    }
  })
  .sort((left, right) => left.file.localeCompare(right.file))

export type Example = (typeof EXAMPLES)[number]
