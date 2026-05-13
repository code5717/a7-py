/*
 * Single source of truth for the A7 docs IA.
 *
 * Flat 5 sections + an overview hub at /docs.
 * Each entry maps a route slug → source markdown (under public/docs/) which the
 * a7-docs Vite plugin renders to /docs-data/<sourceDoc>.json at build time.
 */

export type SectionKey = 'learn' | 'ref' | 'compiler' | 'project' | 'agents'

export interface ManifestEntry {
  /** URL path relative to BrowserRouter basename, e.g. "/learn/start" */
  path: string
  /** Markdown source path under public/docs/, without .md, e.g. "getting-started" or "plugins/claude" */
  source: string
  /** Display title shown in nav and breadcrumb (also overrides H1 if set) */
  title: string
  /** Eyebrow above the H1 in the reading card, e.g. "REFERENCE / LANGUAGE" */
  eyebrow: string
  /** Which top section this belongs to (null for top-level /docs hub) */
  section: SectionKey | 'overview'
  /** Show in sidebar */
  navLabel?: string
}

export interface SectionDef {
  key: SectionKey
  /** Label rendered in sidebar header as `[ LABEL ]` */
  label: string
  /** Schematic number 01-05 */
  index: string
}

export const SECTIONS: SectionDef[] = [
  { key: 'learn', label: 'LEARN', index: '01' },
  { key: 'ref', label: 'REFERENCE', index: '02' },
  { key: 'compiler', label: 'COMPILER', index: '03' },
  { key: 'project', label: 'PROJECT', index: '04' },
  { key: 'agents', label: 'AGENTS', index: '05' },
]

export const MANIFEST: ManifestEntry[] = [
  // overview hub
  {
    path: '/docs',
    source: 'index',
    title: 'A7 Docs',
    eyebrow: 'DOCS / INDEX',
    section: 'overview',
    navLabel: 'Overview',
  },

  // -- learn --
  {
    path: '/learn/start',
    source: 'getting-started',
    title: 'Getting Started',
    eyebrow: 'LEARN / START',
    section: 'learn',
    navLabel: 'Getting Started',
  },
  {
    path: '/learn/why',
    source: 'why',
    title: 'Why A7',
    eyebrow: 'LEARN / WHY',
    section: 'learn',
    navLabel: 'Why A7',
  },
  {
    path: '/learn/faq',
    source: 'faq',
    title: 'FAQ',
    eyebrow: 'LEARN / FAQ',
    section: 'learn',
    navLabel: 'FAQ',
  },
  {
    path: '/learn/examples',
    source: 'examples',
    title: 'Examples',
    eyebrow: 'LEARN / EXAMPLES',
    section: 'learn',
    navLabel: 'Examples',
  },

  // -- reference --
  {
    path: '/ref/language',
    source: 'language',
    title: 'Language Reference',
    eyebrow: 'REFERENCE / LANGUAGE',
    section: 'ref',
    navLabel: 'Language',
  },
  {
    path: '/ref/cli',
    source: 'cli',
    title: 'CLI',
    eyebrow: 'REFERENCE / CLI',
    section: 'ref',
    navLabel: 'CLI',
  },
  {
    path: '/ref/api',
    source: 'api',
    title: 'API',
    eyebrow: 'REFERENCE / API',
    section: 'ref',
    navLabel: 'API',
  },
  {
    path: '/ref/stdlib',
    source: 'stdlib',
    title: 'Standard Library',
    eyebrow: 'REFERENCE / STDLIB',
    section: 'ref',
    navLabel: 'Standard Library',
  },
  {
    path: '/ref/features',
    source: 'features',
    title: 'Features',
    eyebrow: 'REFERENCE / FEATURES',
    section: 'ref',
    navLabel: 'Features',
  },

  // -- compiler --
  {
    path: '/compiler/internals',
    source: 'compiler',
    title: 'Compiler Internals',
    eyebrow: 'COMPILER / INTERNALS',
    section: 'compiler',
    navLabel: 'Internals',
  },
  {
    path: '/compiler/pipeline',
    source: 'pipeline',
    title: 'Pipeline',
    eyebrow: 'COMPILER / PIPELINE',
    section: 'compiler',
    navLabel: 'Pipeline',
  },
  {
    path: '/compiler/safety',
    source: 'safety',
    title: 'Safety',
    eyebrow: 'COMPILER / SAFETY',
    section: 'compiler',
    navLabel: 'Safety',
  },
  {
    path: '/compiler/testing',
    source: 'testing',
    title: 'Testing',
    eyebrow: 'COMPILER / TESTING',
    section: 'compiler',
    navLabel: 'Testing',
  },
  {
    path: '/compiler/status',
    source: 'status',
    title: 'Implementation Status',
    eyebrow: 'COMPILER / STATUS',
    section: 'compiler',
    navLabel: 'Status',
  },
  {
    path: '/compiler/release',
    source: 'release',
    title: 'Release',
    eyebrow: 'COMPILER / RELEASE',
    section: 'compiler',
    navLabel: 'Release',
  },

  // -- project --
  {
    path: '/project/contributing',
    source: 'contributing',
    title: 'Contributing',
    eyebrow: 'PROJECT / CONTRIBUTING',
    section: 'project',
    navLabel: 'Contributing',
  },
  {
    path: '/project/deploy',
    source: 'dev/deploy',
    title: 'Deploy',
    eyebrow: 'PROJECT / DEPLOY',
    section: 'project',
    navLabel: 'Deploy',
  },
  {
    path: '/project/changelog',
    source: 'changelog',
    title: 'Changelog',
    eyebrow: 'PROJECT / CHANGELOG',
    section: 'project',
    navLabel: 'Changelog',
  },

  // -- agents --
  {
    path: '/agents',
    source: 'plugins',
    title: 'Agents Overview',
    eyebrow: 'AGENTS / OVERVIEW',
    section: 'agents',
    navLabel: 'Overview',
  },
  {
    path: '/agents/usage',
    source: 'guide/agent-usage',
    title: 'Agent Usage',
    eyebrow: 'AGENTS / USAGE',
    section: 'agents',
    navLabel: 'Usage',
  },
  {
    path: '/agents/skills',
    source: 'skills',
    title: 'Skills',
    eyebrow: 'AGENTS / SKILLS',
    section: 'agents',
    navLabel: 'Skills',
  },
  {
    path: '/agents/claude',
    source: 'plugins/claude',
    title: 'Claude',
    eyebrow: 'AGENTS / CLAUDE',
    section: 'agents',
    navLabel: 'Claude',
  },
  {
    path: '/agents/codex',
    source: 'plugins/codex',
    title: 'Codex',
    eyebrow: 'AGENTS / CODEX',
    section: 'agents',
    navLabel: 'Codex',
  },
  {
    path: '/agents/cursor',
    source: 'plugins/cursor',
    title: 'Cursor',
    eyebrow: 'AGENTS / CURSOR',
    section: 'agents',
    navLabel: 'Cursor',
  },
  {
    path: '/agents/amp',
    source: 'plugins/amp',
    title: 'Amp',
    eyebrow: 'AGENTS / AMP',
    section: 'agents',
    navLabel: 'Amp',
  },
  {
    path: '/agents/opencode',
    source: 'plugins/opencode',
    title: 'OpenCode',
    eyebrow: 'AGENTS / OPENCODE',
    section: 'agents',
    navLabel: 'OpenCode',
  },
  {
    path: '/agents/pi',
    source: 'plugins/pi',
    title: 'Pi',
    eyebrow: 'AGENTS / PI',
    section: 'agents',
    navLabel: 'Pi',
  },
]

/** Legacy URL → new URL (with optional #anchor). Mounted as <Navigate replace> in App. */
export const LEGACY_REDIRECTS: Array<{ from: string; to: string }> = [
  { from: '/start', to: '/learn/start' },
  { from: '/install', to: '/learn/start#install' },
  { from: '/installation', to: '/learn/start#install' },
  { from: '/why', to: '/learn/why' },
  { from: '/faq', to: '/learn/faq' },
  { from: '/examples', to: '/learn/examples' },

  { from: '/language', to: '/ref/language' },
  { from: '/cli', to: '/ref/cli' },
  { from: '/api', to: '/ref/api' },
  { from: '/stdlib', to: '/ref/stdlib' },
  { from: '/features', to: '/ref/features' },

  { from: '/internals', to: '/compiler/internals' },
  { from: '/pipeline', to: '/compiler/pipeline' },
  { from: '/testing', to: '/compiler/testing' },
  { from: '/status', to: '/compiler/status' },
  { from: '/release', to: '/compiler/release' },

  { from: '/contributing', to: '/project/contributing' },
  { from: '/develop', to: '/project/contributing' },
  { from: '/deploy', to: '/project/deploy' },
  { from: '/changelog', to: '/project/changelog' },

  { from: '/plugins', to: '/agents' },
  { from: '/plugins/claude', to: '/agents/claude' },
  { from: '/plugins/codex', to: '/agents/codex' },
  { from: '/plugins/cursor', to: '/agents/cursor' },
  { from: '/plugins/amp', to: '/agents/amp' },
  { from: '/plugins/opencode', to: '/agents/opencode' },
  { from: '/plugins/pi', to: '/agents/pi' },
  { from: '/agent-usage', to: '/agents/usage' },
  { from: '/skills', to: '/agents/skills' },

  // legacy guide/* surfaces that were aliased in the old curlDocs map
  { from: '/guide/cli', to: '/ref/cli' },
  { from: '/guide/api', to: '/ref/api' },
  { from: '/guide/features', to: '/ref/features' },
  { from: '/guide/plugins', to: '/agents' },
  { from: '/guide/agent-usage', to: '/agents/usage' },
]

/** External URLs (served as raw assets, not React routes). */
export const EXTERNAL_REDIRECTS: Array<{ from: string; to: string }> = [
  { from: '/llms', to: '/a7-py/llms.txt' },
  { from: '/llms-full', to: '/a7-py/llms-full.txt' },
  { from: '/kitchen-sink', to: '/docs' }, // dropped — bounce to hub
]

export const ENTRIES_BY_PATH = new Map(MANIFEST.map((e) => [e.path, e]))
export const ENTRIES_BY_SECTION = SECTIONS.map((s) => ({
  ...s,
  entries: MANIFEST.filter((e) => e.section === s.key),
}))

/** Linear order over the manifest for prev/next. Skips the overview hub. */
const LINEAR = MANIFEST.filter((e) => e.section !== 'overview')

export function neighbours(path: string): { prev?: ManifestEntry; next?: ManifestEntry } {
  const idx = LINEAR.findIndex((e) => e.path === path)
  if (idx === -1) return {}
  return {
    prev: idx > 0 ? LINEAR[idx - 1] : undefined,
    next: idx < LINEAR.length - 1 ? LINEAR[idx + 1] : undefined,
  }
}

/** GitHub source URL for an entry's markdown source. */
export function sourceMarkdownUrl(entry: ManifestEntry): string {
  return `/a7-py/docs/${entry.source}.md`
}

export function githubEditUrl(entry: ManifestEntry): string {
  return `https://github.com/Airbus5717/a7-py/edit/master/site/public/docs/${entry.source}.md`
}

export function dataUrl(entry: ManifestEntry): string {
  return `/a7-py/docs-data/${entry.source}.json`
}
