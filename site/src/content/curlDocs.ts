export type CurlDocItem = {
  route: string
  markdownPath: string
  label: string
  note: string
}

export type CurlDocGroup = {
  label: string
  items: CurlDocItem[]
}

export const CURL_DOC_GROUPS: CurlDocGroup[] = [
  {
    label: 'Introduction',
    items: [
      { route: '/start', markdownPath: '/docs/getting-started.md', label: 'Getting Started', note: 'Fast path from checkout to first run' },
      { route: '/install', markdownPath: '/docs/install.md', label: 'Installation', note: 'Python, uv, Zig, and site setup' },
      { route: '/why', markdownPath: '/docs/why.md', label: 'Why A7', note: 'Project goals, fit, and non-goals' },
      { route: '/faq', markdownPath: '/docs/faq.md', label: 'FAQ', note: 'Short answers for agent workflows' },
    ],
  },
  {
    label: 'Guide',
    items: [
      { route: '/features', markdownPath: '/docs/guide/features.md', label: 'Features', note: 'Implemented language and compiler surface' },
      { route: '/agent-usage', markdownPath: '/docs/guide/agent-usage.md', label: 'Agent Usage', note: 'Fetch order, checks, and trust boundaries' },
      { route: '/cli', markdownPath: '/docs/guide/cli.md', label: 'CLI', note: 'Commands, modes, flags, and exit codes' },
      { route: '/api', markdownPath: '/docs/guide/api.md', label: 'API & SDK', note: 'Automation entry points and current limits' },
      { route: '/plugins', markdownPath: '/docs/guide/plugins.md', label: 'Plugins', note: 'Agent and editor integration map' },
    ],
  },
  {
    label: 'Plugins',
    items: [
      { route: '/plugins/amp', markdownPath: '/docs/plugins/amp.md', label: 'Amp', note: 'Use A7 docs from Amp' },
      { route: '/plugins/claude', markdownPath: '/docs/plugins/claude.md', label: 'Claude Code', note: 'Use A7 docs from Claude Code' },
      { route: '/plugins/codex', markdownPath: '/docs/plugins/codex.md', label: 'Codex', note: 'Use A7 docs from Codex' },
      { route: '/plugins/cursor', markdownPath: '/docs/plugins/cursor.md', label: 'Cursor', note: 'Use A7 docs from Cursor' },
      { route: '/plugins/opencode', markdownPath: '/docs/plugins/opencode.md', label: 'OpenCode', note: 'Use A7 docs from OpenCode' },
      { route: '/plugins/pi', markdownPath: '/docs/plugins/pi.md', label: 'Pi', note: 'Use A7 docs from Pi' },
    ],
  },
  {
    label: 'LLM Resources',
    items: [
      { route: '/skills', markdownPath: '/docs/skills.md', label: 'Skills', note: 'Agent skill guidance and repo rules' },
      { route: '/llms', markdownPath: '/llms.txt', label: 'llms.txt', note: 'Compact markdown entry point' },
      { route: '/llms-full', markdownPath: '/llms-full.txt', label: 'llms-full.txt', note: 'Single fetch context file' },
    ],
  },
  {
    label: 'Contributing',
    items: [
      { route: '/develop', markdownPath: '/docs/dev/develop.md', label: 'Contributing', note: 'Local development workflow' },
      { route: '/deploy', markdownPath: '/docs/dev/deploy.md', label: 'Deploy', note: 'Docs deploy and release notes' },
      { route: '/kitchen-sink', markdownPath: '/docs/dev/kitchen-sink.md', label: 'Kitchen Sink', note: 'Markdown component coverage' },
      { route: '/changelog', markdownPath: '/docs/changelog.md', label: 'Changelog', note: 'Current release notes' },
    ],
  },
  {
    label: 'A7 References',
    items: [
      { route: '/language', markdownPath: '/docs/language.md', label: 'Language and Library', note: 'Syntax, integer guidance, stdlib, and no-recursion rule' },
      { route: '/internals', markdownPath: '/docs/compiler.md', label: 'Compiler and Tests', note: 'Pipeline, Zig verification, and release gate' },
      { route: '/safety', markdownPath: '/docs/safety.md', label: 'Safety Contract', note: 'Facts, obligations, proofs, and backend-plan invariants' },
      { route: '/examples', markdownPath: '/docs/examples.md', label: 'Examples', note: 'Runnable programs and verification commands' },
      { route: '/release', markdownPath: '/docs/release.md', label: 'Release', note: 'Artifacts, package build, audits, and draft release status' },
      { route: '/status', markdownPath: '/docs/status.md', label: 'Status', note: 'Implementation status and known gaps' },
      { route: '/pipeline', markdownPath: '/docs/pipeline.md', label: 'Pipeline', note: 'Compiler pipeline alias' },
      { route: '/testing', markdownPath: '/docs/testing.md', label: 'Testing', note: 'Verification command alias' },
      { route: '/stdlib', markdownPath: '/docs/stdlib.md', label: 'Standard Library', note: 'Current stdlib alias' },
    ],
  },
]

export const CURL_DOC_ITEMS = CURL_DOC_GROUPS.flatMap((group) =>
  group.items.map((item) => ({ ...item, group: group.label })),
)

export const CURL_DOC_BY_ROUTE = new Map(CURL_DOC_ITEMS.map((item) => [item.route, item]))

const installationDoc = CURL_DOC_BY_ROUTE.get('/install')
if (installationDoc) {
  CURL_DOC_BY_ROUTE.set('/installation', installationDoc)
}
