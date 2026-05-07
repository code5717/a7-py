export type PrimaryNavItem =
  | { kind: 'route'; to: string; label: string; end?: boolean }
  | { kind: 'link'; href: string; label: string }

export type NavItem = {
  to: string
  label: string
  note: string
}

export type SectionSearchItem = {
  to: string
  label: string
  group: string
  detail: string
}

export const PRIMARY_NAV: PrimaryNavItem[] = [
  { kind: 'route', to: '/', label: 'Docs', end: true },
  { kind: 'route', to: '/start', label: 'Getting Started' },
  { kind: 'route', to: '/language', label: 'Language' },
  { kind: 'route', to: '/cli', label: 'CLI' },
  { kind: 'route', to: '/stdlib', label: 'Stdlib' },
  { kind: 'route', to: '/examples', label: 'Examples' },
  { kind: 'route', to: '/testing', label: 'Testing' },
  { kind: 'route', to: '/changelog', label: 'Changelog' },
  { kind: 'link', href: 'https://github.com/code5717/a7-py', label: 'GitHub ↗' },
]

export const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: 'Overview',
    items: [
      { to: '/', label: 'Home', note: 'Project map and quick commands' },
      { to: '/start', label: 'Getting Started', note: 'Install and first compile run' },
    ],
  },
  {
    label: 'Reference',
    items: [
      { to: '/language', label: 'Language', note: 'Types, control flow, generics' },
      { to: '/cli', label: 'CLI', note: 'Modes, flags, exit codes' },
      { to: '/pipeline', label: 'Pipeline', note: 'Compiler stage flow' },
      { to: '/stdlib', label: 'Standard Library', note: 'Builtins and modules' },
    ],
  },
  {
    label: 'Learn',
    items: [
      { to: '/examples', label: 'Examples', note: 'Runnable A7 programs' },
      { to: '/internals', label: 'Internals', note: 'File-by-file architecture' },
      { to: '/testing', label: 'Testing', note: 'Quality gates and scripts' },
    ],
  },
  {
    label: 'Project',
    items: [
      { to: '/status', label: 'Status', note: 'Current completeness and gaps' },
      { to: '/contributing', label: 'Contributing', note: 'Workflow and standards' },
      { to: '/changelog', label: 'Changelog', note: 'Release history' },
    ],
  },
]

export const PAGE_META: Record<string, { title: string; description: string }> = {
  '/': {
    title: 'A7 Docs',
    description: 'Documentation for the A7 compiler, runnable examples, CLI, language reference, and current status.',
  },
  '/start': {
    title: 'Getting Started',
    description: 'Install the A7 compiler repository and run the first example with uv.',
  },
  '/language': {
    title: 'Language Reference',
    description: 'A7 syntax, types, control flow, memory, modules, generics, and implementation notes.',
  },
  '/cli': {
    title: 'CLI',
    description: 'A7 compiler modes, flags, output formats, and exit codes.',
  },
  '/pipeline': {
    title: 'Compiler Pipeline',
    description: 'Tokenizer, parser, semantic validation, preprocessing, and backend code generation.',
  },
  '/stdlib': {
    title: 'Standard Library',
    description: 'Implemented A7 standard library modules, math builtins, IO calls, and compiler intrinsics.',
  },
  '/examples': {
    title: 'Examples',
    description: 'Addressable runnable A7 example programs with local run commands.',
  },
  '/internals': {
    title: 'Internals',
    description: 'A7 compiler architecture and source-map overview.',
  },
  '/testing': {
    title: 'Testing',
    description: 'Repository test commands, example verifier, and docs quality gates.',
  },
  '/status': {
    title: 'Status',
    description: 'Current A7 implementation status, completed work, and open language gaps.',
  },
  '/contributing': {
    title: 'Contributing',
    description: 'A7 contribution workflow, local checks, and project standards.',
  },
  '/changelog': {
    title: 'Changelog',
    description: 'Current and historical A7 compiler and docs changes.',
  },
}

export const SECTION_SEARCH_ITEMS: SectionSearchItem[] = [
  { to: '/language#lexical-structure', label: 'Lexical Structure', group: 'Language section', detail: 'Tokens, comments, keywords, @ builtins, and $ generic IDs' },
  { to: '/language#type-system', label: 'Type System', group: 'Language section', detail: 'Primitive types, arrays, slices, references, aliases' },
  { to: '/language#control-flow-and-statements', label: 'Control Flow and Statements', group: 'Language section', detail: 'if, while, for, match, fall status, labeled loops' },
  { to: '/language#generics', label: 'Generics', group: 'Language section', detail: 'Generic parameters, @type_set constraints, current gaps' },
  { to: '/language#memory-and-pointers', label: 'Memory and Pointers', group: 'Language section', detail: 'new, del, defer, .adr, .val, nil' },
  { to: '/language#builtins-and-intrinsics', label: 'Builtins and Intrinsics', group: 'Language section', detail: '@size_of, @align_of, @type_name, @type_set' },
  { to: '/cli#modes', label: 'CLI Modes', group: 'CLI section', detail: 'compile, tokens, ast, semantic, pipeline, doc' },
  { to: '/cli#flags', label: 'CLI Flags', group: 'CLI section', detail: '--mode, --format, --verbose, --doc-out' },
  { to: '/pipeline#pipeline-stages', label: 'Pipeline Stages', group: 'Pipeline section', detail: 'Tokenizer, parser, semantic validation, preprocessing, codegen' },
  { to: '/pipeline#backend-notes', label: 'Backend Notes', group: 'Pipeline section', detail: 'Zig and C backend behavior and limitations' },
  { to: '/stdlib#io', label: 'io module', group: 'Stdlib section', detail: 'print, println, eprintln' },
  { to: '/stdlib#math', label: 'math module', group: 'Stdlib section', detail: 'sqrt, abs, floor, ceil, sin, cos, tan, log, exp, min, max f32/f64 builtins' },
  { to: '/stdlib#stub-modules', label: 'Stub modules', group: 'Stdlib section', detail: 'Source stubs are not available stdlib modules yet' },
  { to: '/status#open-gaps', label: 'Open gaps', group: 'Status section', detail: 'fall semantics, match diagnostics, memory model, generic constraints' },
  { to: '/testing#scripts', label: 'Golden output verifier', group: 'Testing section', detail: 'Example compile, build, run, and output checks' },
]
