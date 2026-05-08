import { CURL_DOC_GROUPS, CURL_DOC_ITEMS } from './curlDocs'

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
  { kind: 'route', to: '/docs', label: 'Docs' },
  { kind: 'route', to: '/start', label: 'Start' },
  { kind: 'route', to: '/features', label: 'Guide' },
  { kind: 'route', to: '/plugins', label: 'Plugins' },
  { kind: 'route', to: '/skills', label: 'LLM' },
  { kind: 'route', to: '/develop', label: 'Contribute' },
  { kind: 'link', href: 'https://github.com/code5717/a7-py', label: 'GitHub ↗' },
]

export const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  ...CURL_DOC_GROUPS.map((group) => ({
    label: group.label,
    items: group.items.map((item) => ({
      to: item.route,
      label: item.label,
      note: item.note,
    })),
  })),
]

const CURL_PAGE_META = Object.fromEntries(CURL_DOC_ITEMS.map((item) => [
  item.route,
  {
    title: item.label,
    description: item.note,
    markdownPath: item.markdownPath,
  },
]))

export const PAGE_META: Record<string, { title: string; description: string; markdownPath?: string }> = {
  '/': {
    title: 'A7 Docs',
    description: 'Documentation for the A7 compiler, runnable examples, CLI, language reference, and current status.',
    markdownPath: '/docs/index.md',
  },
  '/docs': {
    title: 'Markdown Docs',
    description: 'curl.md-friendly Markdown documentation index for agents, terminals, and editor tools.',
    markdownPath: '/docs/index.md',
  },
  '/start': {
    title: 'Getting Started',
    description: 'Install the A7 compiler repository and run the first example with uv.',
    markdownPath: '/docs/getting-started.md',
  },
  '/installation': {
    title: 'Installation',
    description: 'Install Python, uv, Zig, and local docs dependencies.',
    markdownPath: '/docs/install.md',
  },
  '/language': {
    title: 'Language Reference',
    description: 'A7 syntax, types, control flow, memory, modules, generics, and implementation notes.',
    markdownPath: '/docs/language.md',
  },
  '/cli': {
    title: 'CLI',
    description: 'A7 compiler modes, flags, output formats, and exit codes.',
    markdownPath: '/docs/cli.md',
  },
  '/pipeline': {
    title: 'Compiler Pipeline',
    description: 'Tokenizer, parser, semantic validation, preprocessing, and backend code generation.',
    markdownPath: '/docs/compiler.md',
  },
  '/stdlib': {
    title: 'Standard Library',
    description: 'A7 standard library modules, math builtins, IO calls, and compiler intrinsics.',
    markdownPath: '/docs/language.md',
  },
  '/examples': {
    title: 'Examples',
    description: 'Addressable runnable A7 example programs with local run commands.',
    markdownPath: '/docs/examples.md',
  },
  '/internals': {
    title: 'Internals',
    description: 'A7 compiler architecture and source-map overview.',
    markdownPath: '/docs/compiler.md',
  },
  '/testing': {
    title: 'Testing',
    description: 'Repository test commands, example verifier, and docs quality gates.',
    markdownPath: '/docs/compiler.md',
  },
  '/status': {
    title: 'Status',
    description: 'Current A7 implementation status, completed work, and open language gaps.',
    markdownPath: '/docs/status.md',
  },
  '/contributing': {
    title: 'Contributing',
    description: 'A7 contribution workflow, local checks, and project standards.',
    markdownPath: '/docs/contributing.md',
  },
  '/changelog': {
    title: 'Changelog',
    description: 'Current and historical A7 compiler and docs changes.',
    markdownPath: '/docs/changelog.md',
  },
  ...CURL_PAGE_META,
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
