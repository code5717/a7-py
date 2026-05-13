/*
 * vite-plugin-a7-docs
 *
 * Build-time markdown → JSON pipeline. Replaces runtime fetch+marked+Shiki+DOMPurify.
 *
 * On startup (dev) and buildStart (prod):
 *   - Glob public/docs/**.md
 *   - For each: gray-matter front-matter, marked → HTML, Shiki syntax highlighting
 *   - Extract H1/H2/H3 headings with ids for TOC + search
 *   - Emit public/docs-data/<slug>.json with { slug, sourcePath, frontmatter, html, headings }
 *   - Emit public/docs-data/search-index.json aggregating heading + first paragraph
 *
 * In dev, re-runs when a doc changes (configureServer + watcher).
 * A7 code blocks are aliased to Zig grammar (syntax is close enough; no upstream Shiki support).
 */

import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Plugin, ViteDevServer } from 'vite'
import matter from 'gray-matter'
import { marked, Renderer } from 'marked'
import { createHighlighter } from 'shiki'
import type { Highlighter } from 'shiki'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SITE_ROOT = path.resolve(__dirname, '..')
const DOCS_ROOT = path.join(SITE_ROOT, 'public', 'docs')
const OUT_ROOT = path.join(SITE_ROOT, 'public', 'docs-data')

const LANGS = [
  'zig', 'bash', 'shellscript', 'python', 'json', 'typescript', 'tsx',
  'javascript', 'jsx', 'css', 'html', 'markdown', 'yaml', 'toml',
] as const

const A7_LANG_ALIAS = 'zig' // A7 syntax is Zig-like; no upstream grammar.

type Heading = { level: 1 | 2 | 3; id: string; text: string }
type DocJson = {
  slug: string
  sourcePath: string
  frontmatter: Record<string, unknown>
  html: string
  headings: Heading[]
  firstParagraph: string
}

let highlighterPromise: Promise<Highlighter> | null = null
function getHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: ['github-dark-default'],
      langs: LANGS as unknown as string[],
    })
  }
  return highlighterPromise
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .slice(0, 80)
}

function decodeHtml(s: string): string {
  return s
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&nbsp;/g, ' ')
}

async function walkDocs(root: string): Promise<string[]> {
  const out: string[] = []
  async function walk(dir: string) {
    const entries = await fs.readdir(dir, { withFileTypes: true })
    for (const e of entries) {
      const full = path.join(dir, e.name)
      if (e.isDirectory()) await walk(full)
      else if (e.isFile() && e.name.endsWith('.md')) out.push(full)
    }
  }
  await walk(root)
  return out
}

function buildSlug(absPath: string): string {
  const rel = path.relative(DOCS_ROOT, absPath).replace(/\\/g, '/')
  return rel.replace(/\.md$/, '')
}

async function renderOne(absPath: string, highlighter: Highlighter): Promise<DocJson> {
  const raw = await fs.readFile(absPath, 'utf8')
  const { data: frontmatter, content } = matter(raw)
  const slug = buildSlug(absPath)
  const sourcePath = '/a7-py/docs/' + slug + '.md'

  const headings: Heading[] = []
  const idCounts = new Map<string, number>()
  let firstParagraph = ''

  const renderer = new Renderer()
  renderer.heading = ({ tokens, depth }) => {
    const text = renderer.parser.parseInline(tokens)
    const plain = decodeHtml(text.replace(/<[^>]+>/g, ''))
    let id = slugify(plain)
    const seen = idCounts.get(id) ?? 0
    if (seen > 0) id = `${id}-${seen}`
    idCounts.set(slugify(plain), seen + 1)
    if (depth <= 3) headings.push({ level: depth as 1 | 2 | 3, id, text: plain })
    return `<h${depth} id="${id}"><a class="anchor" href="#${id}">${text}</a></h${depth}>`
  }
  renderer.paragraph = ({ tokens }) => {
    const html = renderer.parser.parseInline(tokens)
    if (!firstParagraph) {
      const plain = decodeHtml(html.replace(/<[^>]+>/g, '')).trim()
      if (plain.length > 20) firstParagraph = plain.slice(0, 240)
    }
    return `<p>${html}</p>\n`
  }
  renderer.code = ({ text, lang }) => {
    const langKey = (lang || '').trim().toLowerCase()
    if (langKey === 'mermaid') {
      // pass through as a placeholder div; runtime mermaid component handles render.
      const encoded = Buffer.from(text, 'utf8').toString('base64')
      return `<div class="mermaid-block" data-mermaid="${encoded}"></div>\n`
    }
    const resolved = langKey === 'a7' ? A7_LANG_ALIAS : langKey
    const useLang = LANGS.includes(resolved as typeof LANGS[number]) ? resolved : 'text'
    let inner: string
    try {
      inner = highlighter.codeToHtml(text, {
        lang: useLang as string,
        theme: 'github-dark-default',
      })
    } catch {
      inner = highlighter.codeToHtml(text, { lang: 'text' as never, theme: 'github-dark-default' })
    }
    const escaped = inner
      .replace(/^<pre[^>]*>/, '')
      .replace(/<\/pre>\s*$/, '')
    return `<div class="codeblock" data-lang="${langKey || 'text'}"><div class="codeblock__inner">${escaped}</div></div>\n`
  }
  renderer.link = ({ href, title, tokens }) => {
    const inner = renderer.parser.parseInline(tokens)
    const attrs: string[] = []
    if (href) attrs.push(`href="${href}"`)
    if (title) attrs.push(`title="${title}"`)
    if (href && /^https?:\/\//.test(href)) {
      attrs.push('rel="noopener"')
      attrs.push('target="_blank"')
    }
    return `<a ${attrs.join(' ')}>${inner}</a>`
  }

  marked.use({ gfm: true, breaks: false })
  const html = await marked.parse(content, { renderer, async: true })

  return {
    slug,
    sourcePath,
    frontmatter: frontmatter as Record<string, unknown>,
    html: String(html),
    headings,
    firstParagraph,
  }
}

async function renderAll(): Promise<DocJson[]> {
  const highlighter = await getHighlighter()
  const files = await walkDocs(DOCS_ROOT)
  return Promise.all(files.map((f) => renderOne(f, highlighter)))
}

const LLMS_PREAMBLE = `# A7 Programming Language

A7 is a small, safe ahead-of-time compiler. It lowers .a7 source to Zig source,
then to a native binary via the host Zig 0.16 toolchain. The compiler is written
in Python; there is no runtime.

## Invariants

- A7 source recursion is rejected at compile time (direct, mutual, and via
  function-pointer alias cycles).
- Compiler internals use iterative AST traversals throughout. Recursion limit
  is set to 100 in CI to enforce this.
- Iteration is the supported control structure; use loops, worklists, or
  explicit stacks.
- usize is the type for sizes, lengths, capacities, and array/slice/string
  indices.  isize is reserved for signed pointer-sized offsets and position
  differences.
- new [N]T (heap fixed arrays) is currently rejected. Use stack arrays
  (buf: [N]T) or slices.
- Address-of and dereference operators are not part of the public A7
  reference syntax. Pass lvalues directly to ref parameters.

## CLI

- Entrypoint: \`uv run a7 <args>\` (installed CLI) or \`uv run python main.py
  <args>\` (repo wrapper).
- Modes (\`--mode\`): compile (default, writes .zig), tokens, ast, semantic,
  pipeline (full run, no file write), doc.
- Format (\`--format\`): human or json.
- Exit codes: 0 success, 2 usage, 3 io, 4 tokenize, 5 parse, 6 semantic,
  7 codegen, 8 internal.

## Fetch order for agents

1. /a7-py/llms.txt — compact index of every page.
2. /a7-py/docs/<slug>.md — raw markdown for any individual page.
3. /a7-py/llms-full.txt — this file. Full corpus, single fetch.

## Out of scope

- Package-registry publishing (a7 package index, registry client, lockfile
  resolution) is not in this repository.
- A7 is not a sandbox. Only compile and run A7 source you trust.

---

`

async function emit(): Promise<DocJson[]> {
  await fs.mkdir(OUT_ROOT, { recursive: true })
  const docs = await renderAll()
  await Promise.all(
    docs.map((d) =>
      fs.mkdir(path.join(OUT_ROOT, path.dirname(d.slug)), { recursive: true }).then(() =>
        fs.writeFile(path.join(OUT_ROOT, d.slug + '.json'), JSON.stringify(d), 'utf8'),
      ),
    ),
  )
  const index = docs.map((d) => ({
    slug: d.slug,
    title: (d.frontmatter.title as string) || d.headings.find((h) => h.level === 1)?.text || d.slug,
    firstParagraph: d.firstParagraph,
    headings: d.headings.map((h) => ({ level: h.level, id: h.id, text: h.text })),
  }))
  await fs.writeFile(path.join(OUT_ROOT, 'search-index.json'), JSON.stringify(index), 'utf8')

  // Auto-emit llms.txt and llms-full.txt driven by the route manifest.
  const manifestMod = (await import('../src/content/manifest.ts')) as {
    MANIFEST: Array<{ path: string; source: string; title: string; eyebrow: string; section: string }>
    SECTIONS: Array<{ key: string; label: string; index: string }>
  }
  await writeLlmsFiles(manifestMod.MANIFEST, manifestMod.SECTIONS, docs)
  return docs
}

async function writeLlmsFiles(
  manifest: Array<{ path: string; source: string; title: string; eyebrow: string; section: string }>,
  sections: Array<{ key: string; label: string; index: string }>,
  docs: DocJson[],
) {
  const docBySource = new Map(docs.map((d) => [d.slug, d]))
  const ORIGIN = 'https://code5717.github.io/a7-py'
  const PUBLIC = path.join(SITE_ROOT, 'public')

  // --- llms.txt (compact index) ---
  const indexLines: string[] = [
    '# A7 — A small, safe compiler for the agent era',
    '',
    'A7 lowers .a7 source to Zig, then to a native binary via the host Zig 0.16 toolchain.',
    'No source recursion. Iterative compiler internals. Deterministic exit codes (0/2-8).',
    '',
    `Site:    ${ORIGIN}/`,
    `Full:    ${ORIGIN}/llms-full.txt`,
    `Source:  https://github.com/Airbus5717/a7-py`,
    '',
    '## Pages',
    '',
  ]
  for (const sec of sections) {
    const secEntries = manifest.filter((e) => e.section === sec.key)
    if (secEntries.length === 0) continue
    indexLines.push(`### ${sec.label}`)
    indexLines.push('')
    for (const e of secEntries) {
      const doc = docBySource.get(e.source)
      const summary = doc?.firstParagraph?.replace(/\s+/g, ' ').trim() ?? ''
      const trimmed = summary.length > 140 ? summary.slice(0, 137) + '…' : summary
      indexLines.push(`- ${e.title} — ${ORIGIN}${e.path}`)
      if (trimmed) indexLines.push(`  ${trimmed}`)
      indexLines.push(`  Source: ${ORIGIN}/docs/${e.source}.md`)
    }
    indexLines.push('')
  }
  await fs.writeFile(path.join(PUBLIC, 'llms.txt'), indexLines.join('\n'), 'utf8')

  // --- llms-full.txt (full corpus) ---
  const parts: string[] = [LLMS_PREAMBLE]
  for (const sec of sections) {
    const secEntries = manifest.filter((e) => e.section === sec.key)
    if (secEntries.length === 0) continue
    parts.push(`# Section: ${sec.label}\n`)
    for (const e of secEntries) {
      const raw = await fs.readFile(path.join(DOCS_ROOT, e.source + '.md'), 'utf8').catch(() => '')
      const { content } = matter(raw)
      parts.push(`---\n`)
      parts.push(`## ${e.title}\n`)
      parts.push(`URL:     ${ORIGIN}${e.path}`)
      parts.push(`Source:  ${ORIGIN}/docs/${e.source}.md`)
      parts.push(`Section: ${e.eyebrow}`)
      parts.push('')
      parts.push(content.trim())
      parts.push('')
    }
  }
  // Also include the docs hub itself (the /docs overview).
  const overview = manifest.find((e) => e.path === '/docs')
  if (overview) {
    const raw = await fs.readFile(path.join(DOCS_ROOT, overview.source + '.md'), 'utf8').catch(() => '')
    const { content } = matter(raw)
    parts.push(`---\n`)
    parts.push(`## ${overview.title}\n`)
    parts.push(`URL:     ${ORIGIN}${overview.path}`)
    parts.push(`Source:  ${ORIGIN}/docs/${overview.source}.md`)
    parts.push('')
    parts.push(content.trim())
    parts.push('')
  }
  await fs.writeFile(path.join(PUBLIC, 'llms-full.txt'), parts.join('\n'), 'utf8')
}

export default function a7DocsPlugin(): Plugin {
  let server: ViteDevServer | undefined
  return {
    name: 'vite-plugin-a7-docs',
    async buildStart() {
      const docs = await emit()
      this.info(`a7-docs: rendered ${docs.length} docs → public/docs-data/`)
    },
    configureServer(viteServer) {
      server = viteServer
      const watcher = viteServer.watcher
      watcher.add(path.join(DOCS_ROOT, '**/*.md'))
      const onChange = async (file: string) => {
        if (!file.startsWith(DOCS_ROOT) || !file.endsWith('.md')) return
        try {
          await emit()
          server?.ws.send({ type: 'full-reload' })
        } catch (err) {
          server?.config.logger.error(`a7-docs hot-rebuild failed: ${(err as Error).message}`)
        }
      }
      watcher.on('change', onChange)
      watcher.on('add', onChange)
      watcher.on('unlink', onChange)
    },
  }
}
