export const exampleModules = import.meta.glob<string>('../../../examples/*.a7', {
  query: '?raw',
  import: 'default',
})

const EXAMPLE_META = {
  '000_empty.a7': { title: 'Empty Program', category: 'Basics', desc: 'Minimal valid A7 program' },
  '001_hello.a7': { title: 'Hello World', category: 'Basics', desc: 'Print to stdout with io module' },
  '002_var.a7': { title: 'Variables', category: 'Basics', desc: 'Variable and constant declarations' },
  '003_comments.a7': { title: 'Comments', category: 'Basics', desc: 'Single-line and nested block comments' },
  '004_func.a7': { title: 'Functions', category: 'Basics', desc: 'Function declarations and calls' },
  '005_for_loop.a7': { title: 'For Loops', category: 'Control Flow', desc: 'C-style and range-based loops' },
  '006_if.a7': { title: 'Conditionals', category: 'Control Flow', desc: 'If-else statements and expressions' },
  '007_while.a7': { title: 'While Loops', category: 'Control Flow', desc: 'While loop patterns' },
  '008_switch.a7': { title: 'Match', category: 'Control Flow', desc: 'Pattern matching with ranges and fallthrough' },
  '009_struct.a7': { title: 'Structs', category: 'Types', desc: 'Struct declarations and initialization' },
  '010_enum.a7': { title: 'Enums', category: 'Types', desc: 'Enumerations with explicit values' },
  '011_memory.a7': { title: 'Memory', category: 'Memory', desc: 'Heap allocation with new/del' },
  '012_arrays.a7': { title: 'Arrays', category: 'Types', desc: 'Fixed-size arrays and slices' },
  '013_pointers.a7': { title: 'Pointers', category: 'Memory', desc: 'Pointer operations with .adr/.val' },
  '014_generics.a7': { title: 'Generics', category: 'Types', desc: 'Minimal runnable placeholder; richer generics coverage lives in tests' },
  '015_types.a7': { title: 'Type System', category: 'Types', desc: 'Type aliases and composite types' },
  '016_unions.a7': { title: 'Unions', category: 'Types', desc: 'Union and tagged union types' },
  '017_methods.a7': { title: 'Methods', category: 'Types', desc: 'Methods with self receiver' },
  '018_modules.a7': { title: 'Modules', category: 'Basics', desc: 'Import system and visibility' },
  '019_literals.a7': { title: 'Literals', category: 'Basics', desc: 'All literal formats: hex, octal, binary, escapes' },
  '020_operators.a7': { title: 'Operators', category: 'Basics', desc: 'Arithmetic, logical, bitwise, assignment' },
  '021_control_flow.a7': { title: 'Control Flow', category: 'Control Flow', desc: 'Combined control flow patterns' },
  '022_function_pointers.a7': { title: 'Function Pointers', category: 'Functions', desc: 'Higher-order functions and callbacks' },
  '023_inline_structs.a7': { title: 'Inline Structs', category: 'Types', desc: 'Anonymous struct types' },
  '024_defer.a7': { title: 'Defer', category: 'Memory', desc: 'Resource management with defer' },
  '025_linked_list.a7': { title: 'Linked List', category: 'Data Structures', desc: 'Linked-list themed array traversal sample' },
  '026_binary_tree.a7': { title: 'Binary Tree', category: 'Data Structures', desc: 'Binary search tree with traversal' },
  '027_callbacks.a7': { title: 'Callbacks', category: 'Functions', desc: 'Event handling and dispatcher pattern' },
  '028_state_machine.a7': { title: 'State Machine', category: 'Patterns', desc: 'State machines with function pointers' },
  '029_sorting.a7': { title: 'Sorting', category: 'Algorithms', desc: 'Sorting with custom comparators' },
  '030_calculator.a7': { title: 'Calculator', category: 'Applications', desc: 'Math operations including sqrt, power' },
  '031_number_guessing.a7': { title: 'Number Guessing', category: 'Applications', desc: 'Deterministic number-guessing control-flow example' },
  '032_prime_numbers.a7': { title: 'Primes', category: 'Algorithms', desc: 'Sieve of Eratosthenes, factorization' },
  '033_fibonacci.a7': { title: 'Fibonacci', category: 'Algorithms', desc: 'Multiple implementations with memoization' },
  '034_string_utils.a7': { title: 'String Utils', category: 'Applications', desc: 'Text processing utilities' },
  '035_matrix.a7': { title: 'Matrix Ops', category: 'Applications', desc: 'Matrix operations and linear algebra' },
  '036_control_flow_edges.a7': { title: 'Control Flow Edges', category: 'Control Flow', desc: 'Labeled loops, slices, and match-case defer scope' },
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
