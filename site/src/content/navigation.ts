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
  { kind: 'route', to: '/start', label: 'Start' },
  { kind: 'route', to: '/language', label: 'Language' },
  { kind: 'route', to: '/examples', label: 'Examples' },
  { kind: 'route', to: '/internals', label: 'Compiler' },
  { kind: 'route', to: '/status', label: 'Status' },
  { kind: 'link', href: 'https://github.com/code5717/a7-py', label: 'GitHub ↗' },
]

export const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: 'Overview',
    items: [
      { to: '/', label: 'Home', note: 'Project map and quick commands' },
      { to: '/start', label: 'Getting Started', note: 'Install and first compile run' },
      { to: '/start#cli', label: 'CLI', note: 'Modes, flags, exit codes' },
    ],
  },
  {
    label: 'Reference',
    items: [
      { to: '/language', label: 'Language', note: 'Types, control flow, generics' },
      { to: '/language#standard-library', label: 'Standard Library', note: 'stdlib, io, math, intrinsics' },
      { to: '/examples', label: 'Examples', note: 'Runnable A7 programs' },
    ],
  },
  {
    label: 'Compiler',
    items: [
      { to: '/internals', label: 'Compiler', note: 'Pipeline, architecture, testing' },
      { to: '/internals#pipeline', label: 'Pipeline', note: 'Compiler stage flow' },
      { to: '/internals#testing', label: 'Testing', note: 'Quality gates and scripts' },
      { to: '/status', label: 'Status', note: 'Current completeness and gaps' },
    ],
  },
  {
    label: 'Project',
    items: [
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
    description: 'A7 standard library modules, math builtins, IO calls, and compiler intrinsics.',
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
  { to: '/start#cli', label: 'CLI Modes and Flags', group: 'CLI', detail: 'compile, tokens, ast, semantic, pipeline, doc, flags, exit codes' },
  { to: '/internals#pipeline', label: 'Pipeline Stages', group: 'Compiler pipeline', detail: 'Tokenizer, parser, semantic validation, preprocessing, codegen' },
  { to: '/language#standard-library', label: 'Standard Library', group: 'Stdlib', detail: 'stdlib, io, math, planned stub modules, compiler intrinsics' },
  { to: '/status#open-gaps', label: 'Open gaps', group: 'Status section', detail: 'fall semantics, match diagnostics, memory model, generic constraints' },
  { to: '/internals#testing', label: 'Golden output verifier', group: 'Testing', detail: 'Example compile, build, run, and output checks' },
]
