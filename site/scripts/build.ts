import { mkdir, readdir, readFile, rm, writeFile, copyFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'

const ROOT = path.resolve(import.meta.dir, '..')
const PUBLIC = path.join(ROOT, 'public')
const DOCS = path.join(PUBLIC, 'docs')
const DIST = path.join(ROOT, 'dist')
const BASE = '/a7-py'
const ORIGIN = 'https://code5717.github.io/a7-py'

type Doc = {
  slug: string
  title: string
  nav: string
  group: string
  summary: string
  order: number
  markdown: string
  html: string
  headings: Array<{ level: number; id: string; text: string }>
}

const DOC_ORDER = [
  'index',
  'start',
  'language',
  'stdlib',
  'compiler',
  'status',
  'release',
  'agent-usage',
  'project',
]

const DOC_KIND: Record<string, string> = {
  start: 'guide',
  language: 'reference',
  stdlib: 'reference',
  compiler: 'reference',
  status: 'status',
  release: 'status',
  'agent-usage': 'guide',
  project: 'manual',
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/`([^`]+)`/g, '$1')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 72) || 'section'
}

function parseFrontmatter(raw: string): { data: Record<string, string>; body: string } {
  if (!raw.startsWith('---\n')) return { data: {}, body: raw }
  const end = raw.indexOf('\n---\n', 4)
  if (end === -1) return { data: {}, body: raw }
  const head = raw.slice(4, end).trim()
  const data: Record<string, string> = {}
  for (const line of head.split('\n')) {
    const idx = line.indexOf(':')
    if (idx === -1) continue
    data[line.slice(0, idx).trim()] = line.slice(idx + 1).trim().replace(/^["']|["']$/g, '')
  }
  return { data, body: raw.slice(end + 5) }
}

function inlineMarkdown(value: string): string {
  let out = escapeHtml(value)
  out = out.replace(/`([^`]+)`/g, '<code>$1</code>')
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, label: string, href: string) => {
    const safeHref = escapeHtml(href)
    const external = /^https?:\/\//.test(href)
    return `<a href="${safeHref}"${external ? ' target="_blank" rel="noopener"' : ''}>${label}</a>`
  })
  return out
}

function renderMarkdown(markdown: string): { html: string; headings: Doc['headings'] } {
  const lines = markdown.split('\n')
  const html: string[] = []
  const headings: Doc['headings'] = []
  const idCounts = new Map<string, number>()
  let paragraph: string[] = []
  let list: string[] = []
  let inFence = false
  let fenceLang = ''
  let fence: string[] = []
  let table: string[] = []

  function closeParagraph() {
    if (paragraph.length === 0) return
    html.push(`<p>${inlineMarkdown(paragraph.join(' '))}</p>`)
    paragraph = []
  }

  function closeList() {
    if (list.length === 0) return
    html.push(`<ul>${list.map((item) => `<li>${inlineMarkdown(item)}</li>`).join('')}</ul>`)
    list = []
  }

  function closeTable() {
    if (table.length < 2) {
      table = []
      return
    }
    const rows = table
      .filter((line, idx) => idx !== 1)
      .map((line) => line.replace(/^\||\|$/g, '').split('|').map((cell) => inlineMarkdown(cell.trim())))
    const [head, ...body] = rows
    html.push(
      `<table><thead><tr>${head.map((cell) => `<th>${cell}</th>`).join('')}</tr></thead>` +
      `<tbody>${body.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table>`,
    )
    table = []
  }

  for (const line of lines) {
    if (line.startsWith('```')) {
      if (!inFence) {
        closeParagraph()
        closeList()
        closeTable()
        inFence = true
        fenceLang = line.slice(3).trim() || 'text'
        fence = []
      } else {
        html.push(`<pre data-lang="${escapeHtml(fenceLang)}"><code>${escapeHtml(fence.join('\n'))}</code></pre>`)
        inFence = false
        fenceLang = ''
        fence = []
      }
      continue
    }

    if (inFence) {
      fence.push(line)
      continue
    }

    if (/^\|.+\|$/.test(line.trim())) {
      closeParagraph()
      closeList()
      table.push(line.trim())
      continue
    }

    closeTable()

    const heading = /^(#{1,3})\s+(.+)$/.exec(line)
    if (heading) {
      closeParagraph()
      closeList()
      const level = heading[1].length
      const text = heading[2].trim()
      const base = slugify(text)
      const seen = idCounts.get(base) ?? 0
      idCounts.set(base, seen + 1)
      const id = seen === 0 ? base : `${base}-${seen}`
      headings.push({ level, id, text: text.replace(/`/g, '') })
      html.push(`<h${level} id="${id}"><a href="#${id}">${inlineMarkdown(text)}</a></h${level}>`)
      continue
    }

    const item = /^[-*]\s+(.+)$/.exec(line)
    if (item) {
      closeParagraph()
      list.push(item[1].trim())
      continue
    }

    if (list.length > 0 && /^\s{2,}\S/.test(line)) {
      list[list.length - 1] += ` ${line.trim()}`
      continue
    }

    if (line.trim() === '') {
      closeParagraph()
      closeList()
      continue
    }

    paragraph.push(line.trim())
  }

  closeParagraph()
  closeList()
  closeTable()
  return { html: html.join('\n'), headings }
}

async function listDocFiles(): Promise<string[]> {
  const names = await readdir(DOCS)
  return names.filter((name) => name.endsWith('.md')).sort((a, b) => {
    const as = a.replace(/\.md$/, '')
    const bs = b.replace(/\.md$/, '')
    return DOC_ORDER.indexOf(as) - DOC_ORDER.indexOf(bs)
  })
}

async function readDocs(): Promise<Doc[]> {
  const files = await listDocFiles()
  const docs: Doc[] = []
  for (const file of files) {
    const slug = file.replace(/\.md$/, '')
    const raw = await readFile(path.join(DOCS, file), 'utf8')
    const { data, body } = parseFrontmatter(raw)
    const rendered = renderMarkdown(body)
    docs.push({
      slug,
      title: data.title ?? slug,
      nav: data.nav ?? data.title ?? slug,
      group: data.group ?? 'Docs',
      summary: data.summary ?? '',
      order: Number(data.order ?? DOC_ORDER.indexOf(slug)),
      markdown: body.trim(),
      html: rendered.html,
      headings: rendered.headings,
    })
  }
  return docs.sort((a, b) => a.order - b.order)
}

async function copyPublic(src: string, dest: string) {
  if (!existsSync(src)) return
  const entries = await readdir(src, { withFileTypes: true })
  await mkdir(dest, { recursive: true })
  for (const entry of entries) {
    const from = path.join(src, entry.name)
    const to = path.join(dest, entry.name)
    if (entry.isDirectory()) {
      await copyPublic(from, to)
    } else if (entry.isFile()) {
      await copyFile(from, to)
    }
  }
}

function docHref(slug: string): string {
  return slug === 'index' ? `${BASE}/` : `${BASE}/${slug}/`
}

function navHtml(docs: Doc[], activeSlug: string): string {
  return docs
    .map((doc) => {
      const href = docHref(doc.slug)
      return `<a class="nav-link${doc.slug === activeSlug ? ' active' : ''}" href="${href}">
        <span>${String(doc.order).padStart(2, '0')}</span>${escapeHtml(doc.nav)}
      </a>`
    })
    .join('')
}

function modalsHtml(): string {
  return `
  <div class="chord-toast" role="status" aria-live="polite">
    chord: <em data-chord-key>g</em>
  </div>
  <div class="modal" data-modal="search" role="dialog" aria-modal="true" aria-labelledby="search-title">
    <div class="modal-card" role="document">
      <header>
        <span id="search-title">Search docs</span>
        <button type="button" data-modal-close aria-label="Close search">esc</button>
      </header>
      <label class="search-input-row">
        <input type="search" placeholder="search docs and headings…" autocomplete="off" spellcheck="false" data-autofocus aria-label="Search">
      </label>
      <div class="search-results" role="listbox" data-search-list></div>
      <div class="search-empty" data-search-empty style="display:none">no matches</div>
      <div class="search-footer">
        <span><kbd>↑</kbd><kbd>↓</kbd> move</span>
        <span><kbd>↵</kbd> open</span>
        <span><kbd>esc</kbd> close</span>
      </div>
    </div>
  </div>
  <div class="modal" data-modal="shortcuts" role="dialog" aria-modal="true" aria-labelledby="shortcuts-title">
    <div class="modal-card" role="document">
      <header>
        <span id="shortcuts-title">Keyboard shortcuts</span>
        <button type="button" data-modal-close aria-label="Close shortcuts">esc</button>
      </header>
      <div class="shortcuts-grid">
        <div class="shortcuts-group">
          <h3>General</h3>
          <dl>
            <div><dt>Search</dt><dd><kbd>⌘</kbd><kbd>K</kbd></dd></div>
            <div><dt>Search (alt)</dt><dd><kbd>/</kbd></dd></div>
            <div><dt>Show shortcuts</dt><dd><kbd>?</kbd></dd></div>
            <div><dt>Close overlay</dt><dd><kbd>esc</kbd></dd></div>
            <div><dt>Scroll to top</dt><dd><kbd>t</kbd></dd></div>
          </dl>
        </div>
        <div class="shortcuts-group">
          <h3>Navigation</h3>
          <dl>
            <div><dt>Previous page</dt><dd><kbd>[</kbd></dd></div>
            <div><dt>Next page</dt><dd><kbd>]</kbd></dd></div>
            <div><dt>Home</dt><dd><kbd>g</kbd> <kbd>h</kbd></dd></div>
            <div><dt>Start</dt><dd><kbd>g</kbd> <kbd>s</kbd></dd></div>
            <div><dt>Language</dt><dd><kbd>g</kbd> <kbd>l</kbd></dd></div>
            <div><dt>Stdlib</dt><dd><kbd>g</kbd> <kbd>b</kbd></dd></div>
            <div><dt>Compiler</dt><dd><kbd>g</kbd> <kbd>c</kbd></dd></div>
            <div><dt>Status</dt><dd><kbd>g</kbd> <kbd>t</kbd></dd></div>
            <div><dt>Release</dt><dd><kbd>g</kbd> <kbd>r</kbd></dd></div>
            <div><dt>Agents</dt><dd><kbd>g</kbd> <kbd>a</kbd></dd></div>
            <div><dt>Project</dt><dd><kbd>g</kbd> <kbd>p</kbd></dd></div>
          </dl>
        </div>
      </div>
    </div>
  </div>`
}

function pageMetaScript(doc: Doc, docs: Doc[]): string {
  const ordered = docs.filter((d) => d.slug !== 'index')
  const idx = ordered.findIndex((d) => d.slug === doc.slug)
  const prev = idx > 0 ? ordered[idx - 1] : null
  const next = idx >= 0 && idx < ordered.length - 1 ? ordered[idx + 1] : null
  const data = {
    slug: doc.slug,
    prev: prev ? { slug: prev.slug, title: prev.nav, href: docHref(prev.slug) } : null,
    next: next ? { slug: next.slug, title: next.nav, href: docHref(next.slug) } : null,
  }
  return `<script>window.__A7_PAGE__=${JSON.stringify(data)}</script>`
}

function pageHtml(doc: Doc, docs: Doc[]): string {
  const title = doc.slug === 'index' ? 'A7' : `${doc.title} - A7`
  const canonical = doc.slug === 'index' ? `${ORIGIN}/` : `${ORIGIN}/${doc.slug}/`
  const main = doc.slug === 'index' ? homeHtml(doc, docs) : docHtml(doc, docs)

  return `<!doctype html>
<html lang="en" data-slug="${escapeHtml(doc.slug)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
  <meta name="description" content="${escapeHtml(doc.summary || 'A7 compiler documentation')}">
  <meta name="theme-color" content="#11110e">
  <link rel="canonical" href="${canonical}">
  <link rel="icon" href="${BASE}/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT@9..144,300..900,0..100&family=JetBrains+Mono:wght@300..700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="${BASE}/assets/site.css">
</head>
<body>
  <div class="read-progress" aria-hidden="true"></div>
  <header class="topbar">
    <a class="brand" href="${BASE}/" aria-label="A7 home"><span>A7</span><small>compiler docs</small><em class="version-pill">v0.16</em></a>
    <nav class="quick">
      <a href="${BASE}/start/" data-key="S">Start</a>
      <a href="${BASE}/language/" data-key="L">Language</a>
      <a href="${BASE}/stdlib/" data-key="B">Stdlib</a>
      <a href="${BASE}/llms.txt" data-key="A">llms.txt</a>
      <button type="button" class="shortcut-trigger" data-search-open aria-label="Open search" title="Search (⌘K)">⌕</button>
      <button type="button" class="shortcut-trigger" data-shortcuts-open aria-label="Show keyboard shortcuts" title="Shortcuts (?)">?</button>
    </nav>
  </header>
  ${main}
  ${modalsHtml()}
  ${pageMetaScript(doc, docs)}
  <script src="${BASE}/assets/site.js"></script>
</body>
</html>`
}

function pagerHtml(doc: Doc, docs: Doc[]): string {
  const ordered = docs.filter((d) => d.slug !== 'index')
  const idx = ordered.findIndex((d) => d.slug === doc.slug)
  if (idx === -1) return ''
  const prev = idx > 0 ? ordered[idx - 1] : null
  const next = idx < ordered.length - 1 ? ordered[idx + 1] : null
  if (!prev && !next) return ''
  const prevHtml = prev
    ? `<a href="${docHref(prev.slug)}" data-pager-prev><small>previous · [</small><strong>${escapeHtml(prev.nav)}</strong></a>`
    : `<span></span>`
  const nextHtml = next
    ? `<a href="${docHref(next.slug)}" data-pager-next><small>next · ]</small><strong>${escapeHtml(next.nav)}</strong></a>`
    : `<span></span>`
  return `<nav class="doc-pager" aria-label="Document navigation">${prevHtml}${nextHtml}</nav>`
}

function docHtml(doc: Doc, docs: Doc[]): string {
  const toc = doc.headings
    .filter((h) => h.level > 1)
    .map((h) => `<a href="#${h.id}">${escapeHtml(h.text)}</a>`)
    .join('')
  const related = docs
    .filter((d) => d.slug !== doc.slug)
    .slice(0, 4)
    .map((d) => `<a href="${BASE}/${d.slug === 'index' ? '' : `${d.slug}/`}">${escapeHtml(d.nav)}</a>`)
    .join('')

  return `<main class="shell">
    <aside class="sidebar" aria-label="Documentation">${navHtml(docs, doc.slug)}</aside>
    <article class="paper" data-running="A7 FIELD MANUAL / ${escapeHtml(doc.nav)}">
      <p class="eyebrow">${escapeHtml(doc.group)}</p>
      <h1>${escapeHtml(doc.title)}</h1>
      ${doc.summary ? `<p class="summary">${escapeHtml(doc.summary)}</p>` : ''}
      <div class="prose">${doc.html}</div>
      ${pagerHtml(doc, docs)}
      <footer class="doc-footer">
        <a href="${BASE}/docs/${doc.slug}.md">Raw markdown</a>
        <a href="https://github.com/code5717/a7-py">GitHub</a>
        <span style="margin-left:auto;opacity:.7">press <kbd>?</kbd> for shortcuts</span>
      </footer>
    </article>
    <aside class="toc" aria-label="On this page">
      <strong>On this page</strong>
      ${toc || related}
    </aside>
  </main>`
}

function homeHtml(doc: Doc, docs: Doc[]): string {
  const routes = docs
    .filter((d) => d.slug !== 'index')
    .map((d) => {
      const kind = DOC_KIND[d.slug] ?? 'doc'
      return `<a class="route-row" href="${BASE}/${d.slug}/" data-kind="${kind}">
      <span class="route-num">${String(d.order).padStart(2, '0')}</span>
      <span class="route-title">
        <strong>${escapeHtml(d.nav)}</strong>
        <i class="route-kind" aria-hidden="true">${kind}</i>
      </span>
      <em>${escapeHtml(d.summary)}</em>
    </a>`
    })
    .join('')

  return `<main class="home">
    <section class="poster">
      <span class="reg-mark" data-pos="tl" aria-hidden="true"></span>
      <span class="reg-mark" data-pos="tr" aria-hidden="true"></span>
      <span class="reg-mark" data-pos="bl" aria-hidden="true"></span>
      <span class="reg-mark" data-pos="br" aria-hidden="true"></span>
      <div class="poster-meta" aria-hidden="true">
        <span>SHEET 01 / 09</span>
        <span>v0.16.0</span>
        <span>STAMP · A7-COMPILER</span>
      </div>
      <div class="poster-copy">
        <div class="poster-head">
          <p class="plate">AOT / ZIG 0.16 / SINGLE-FILE OUTPUT</p>
          <p class="poster-pipeline" aria-label="A7 pipeline">
            <em>.a7</em>
            <span>→</span>
            <em>parse</em>
            <span>→</span>
            <em>check</em>
            <span>→</span>
            <em>zig</em>
            <span>→</span>
            <em>binary</em>
          </p>
        </div>
        <h1>A7</h1>
        <p class="poster-tag">Docs for the A7 programming language.</p>
        <p class="poster-sub">.a7 → Zig 0.16 → native binary. AOT, no recursion, single-file output.</p>
        <div class="hero-actions">
          <a href="${BASE}/start/" data-primary>Start using A7 →</a>
          <a href="${BASE}/llms-full.txt">Fetch agent corpus</a>
          <a href="https://github.com/code5717/a7-py" target="_blank" rel="noopener">GitHub</a>
        </div>
        <dl class="poster-stats" aria-label="At a glance">
          <div><dt>Docs</dt><dd>${docs.length}</dd></div>
          <div><dt>Targets</dt><dd>Zig 0.16</dd></div>
          <div><dt>Output</dt><dd>1 file</dd></div>
          <div><dt>Recursion</dt><dd>banned</dd></div>
        </dl>
        <p class="poster-scroll" aria-hidden="true">↓ scroll for routes</p>
      </div>
      <figure class="system-plate">
        <img src="${BASE}/a7-system-map.svg" alt="A7 compiler system map">
        <figcaption>FIG.01 · COMPILER PIPELINE</figcaption>
      </figure>
      <div class="spec-spine" aria-label="System facts">
        <span>NO SOURCE RECURSION</span>
        <span>MULTI-FILE INPUT</span>
        <span>SINGLE ZIG OUTPUT</span>
        <span>RAW DOCS FOR AGENTS</span>
      </div>
    </section>
    <section class="route-board" aria-label="Documentation routes">
      <div class="route-intro">
        <p class="eyebrow">§02 · Field Manual</p>
        <h2>Small corpus.<br>Heavy signal.</h2>
        <p>Eight pages. Each one is a single markdown file, served raw to agents and rendered for humans.</p>
        <p class="route-intro-meta">
          <span><kbd>g</kbd> <kbd>s</kbd> jumps to Start</span>
          <span><kbd>g</kbd> <kbd>l</kbd> jumps to Language</span>
        </p>
        <a class="route-intro-link" href="${BASE}/llms.txt">View raw index ↗</a>
      </div>
      <div class="routes">${routes}</div>
    </section>
    <section class="preview" aria-label="Language preview">
      <div class="preview-copy">
        <p class="eyebrow">§03 · At a glance</p>
        <h2>Read the language<br>in one glance.</h2>
        <p>Module imports, typed functions, structs, iterative loops. No source recursion. No hidden allocations.</p>
        <ul class="preview-features">
          <li><strong>::</strong> module &amp; const binding</li>
          <li><strong>fn</strong> typed functions, named returns</li>
          <li><strong>for</strong> indexed loop, the only loop form</li>
          <li><strong>ret</strong> explicit return, no expression bodies</li>
        </ul>
        <a class="route-intro-link" href="${BASE}/language/">Open the language reference ↗</a>
      </div>
      <figure class="preview-code">
        <figcaption>EXAMPLES / 004_func.a7</figcaption>
        <pre data-lang="a7"><code><span class="hl-c">// Functions in A7</span>

io <span class="hl-op">::</span> <span class="hl-k">import</span> <span class="hl-s">&quot;std/io&quot;</span>

<span class="hl-c">// Typed function with a single return value</span>
add <span class="hl-op">::</span> <span class="hl-k">fn</span>(x: <span class="hl-t">i32</span>, y: <span class="hl-t">i32</span>) <span class="hl-t">i32</span> {
    <span class="hl-k">ret</span> x + y
}

<span class="hl-c">// Iterative — A7 source recursion is banned</span>
factorial <span class="hl-op">::</span> <span class="hl-k">fn</span>(n: <span class="hl-t">i32</span>) <span class="hl-t">i32</span> {
    result := <span class="hl-n">1</span>
    <span class="hl-k">for</span> i := <span class="hl-n">2</span>; i &lt;= n; i += <span class="hl-n">1</span> {
        result *= i
    }
    <span class="hl-k">ret</span> result
}

main <span class="hl-op">::</span> <span class="hl-k">fn</span>() {
    io.println(<span class="hl-s">&quot;5 + 7 = {}&quot;</span>, add(<span class="hl-n">5</span>, <span class="hl-n">7</span>))
    io.println(<span class="hl-s">&quot;6! = {}&quot;</span>, factorial(<span class="hl-n">6</span>))
}</code></pre>
      </figure>
    </section>
    <section class="terminal-strip" data-tabs>
      <div class="terminal-intro">
        <p class="eyebrow">§04 · Terminal Contract</p>
        <h2>Every visual page<br>has a raw text twin.</h2>
        <p>Agents and humans share one canonical source. Fetch the same Markdown the renderer ships from.</p>
      </div>
      <div class="terminal">
        <header class="terminal-bar">
          <span class="terminal-light"></span>
          <span class="terminal-light"></span>
          <span class="terminal-light"></span>
          <span class="terminal-title">~/a7</span>
          <nav class="terminal-tabs" role="tablist">
            <button type="button" role="tab" data-tab="agents" aria-selected="true">agents</button>
            <button type="button" role="tab" data-tab="compile" aria-selected="false">compile</button>
            <button type="button" role="tab" data-tab="release" aria-selected="false">release</button>
          </nav>
        </header>
        <div class="terminal-panel" data-tab-panel="agents">
<pre><span class="t-prompt">$</span> <span class="t-cmd">curl -fsSL https://code5717.github.io/a7-py/llms.txt</span>
<span class="t-out"># A7 Docs</span>
<span class="t-out">- A7 Documentation: .../docs/index.md</span>
<span class="t-out">- Start: .../docs/start.md</span>
<span class="t-out">- Language: .../docs/language.md</span>
<span class="t-out">- Stdlib: .../docs/stdlib.md</span>
<span class="t-out">- Compiler: .../docs/compiler.md</span>
<span class="t-out">...</span>
<span class="t-prompt">$</span> <span class="t-cmd">curl -fsSL https://code5717.github.io/a7-py/docs/language.md</span>
<span class="t-out"><span class="t-dim">---</span></span>
<span class="t-out"><span class="t-dim">title: Language</span></span>
<span class="t-out"><span class="t-dim">---</span></span>
<span class="t-out"># Language</span>
<span class="t-out">The implemented A7 language surface and the rules examples must follow today.</span><span class="terminal-cursor" aria-hidden="true"></span></pre>
        </div>
        <div class="terminal-panel" data-tab-panel="compile" hidden>
<pre><span class="t-prompt">$</span> <span class="t-cmd">uv run a7 examples/001_hello.a7 --mode compile</span>
<span class="t-out">[compile] tokenize     ok</span>
<span class="t-out">[compile] parse        ok</span>
<span class="t-out">[compile] name-resolve ok</span>
<span class="t-out">[compile] type-check   ok</span>
<span class="t-out">[compile] safety       ok</span>
<span class="t-out">[compile] emit zig     ok  -> dist/001_hello.zig</span>
<span class="t-prompt">$</span> <span class="t-cmd">zig build-exe dist/001_hello.zig -O ReleaseSmall</span>
<span class="t-out">[zig]     <span class="t-ok">done</span>           -> 001_hello (148K)</span>
<span class="t-prompt">$</span> <span class="t-cmd">./001_hello</span>
<span class="t-out">Hello, World!</span><span class="terminal-cursor" aria-hidden="true"></span></pre>
        </div>
        <div class="terminal-panel" data-tab-panel="release" hidden>
<pre><span class="t-prompt">$</span> <span class="t-cmd">./run_all_tests.sh</span>
<span class="t-out">[pytest]               <span class="t-ok">412 passed</span></span>
<span class="t-out">[examples e2e]         <span class="t-ok">31 / 31</span></span>
<span class="t-out">[error stage matrix]   <span class="t-ok">ok</span></span>
<span class="t-out">[docs style]           <span class="t-ok">ok</span></span>
<span class="t-out">[secrets check]        <span class="t-ok">ok</span></span>
<span class="t-out">[wheel smoke test]     <span class="t-ok">ok</span></span>
<span class="t-out">release gate: <span class="t-ok">green</span></span><span class="terminal-cursor" aria-hidden="true"></span></pre>
        </div>
      </div>
    </section>
    <footer class="site-footer" aria-label="Site footer">
      <div class="site-footer-row">
        <div class="site-footer-brand">
          <span class="footer-mark">A7</span>
          <p>Compiler docs · Open source · Zig 0.16</p>
        </div>
        <nav class="site-footer-nav" aria-label="Footer navigation">
          <div>
            <h4>Docs</h4>
            <a href="${BASE}/start/">Start</a>
            <a href="${BASE}/language/">Language</a>
            <a href="${BASE}/stdlib/">Stdlib</a>
            <a href="${BASE}/compiler/">Compiler</a>
          </div>
          <div>
            <h4>Operate</h4>
            <a href="${BASE}/status/">Status</a>
            <a href="${BASE}/release/">Release</a>
            <a href="${BASE}/agent-usage/">Agents</a>
            <a href="${BASE}/project/">Project</a>
          </div>
          <div>
            <h4>Raw</h4>
            <a href="${BASE}/llms.txt">llms.txt</a>
            <a href="${BASE}/llms-full.txt">llms-full.txt</a>
            <a href="${BASE}/sitemap.xml">sitemap.xml</a>
          </div>
          <div>
            <h4>Project</h4>
            <a href="https://github.com/code5717/a7-py" target="_blank" rel="noopener">GitHub ↗</a>
            <a href="https://github.com/code5717/a7-py/issues" target="_blank" rel="noopener">Issues ↗</a>
            <a href="https://github.com/code5717/a7-py/blob/master/LICENSE" target="_blank" rel="noopener">License ↗</a>
          </div>
        </nav>
      </div>
      <div class="site-footer-ticker" aria-hidden="true">
        <span>v0.16.0</span>
        <span>·</span>
        <span>built ${new Date().toISOString().slice(0, 10)}</span>
        <span>·</span>
        <span>no source recursion</span>
        <span>·</span>
        <span>single zig output</span>
        <span>·</span>
        <span>raw docs for agents</span>
        <span>·</span>
        <span>press <kbd>?</kbd> for shortcuts</span>
      </div>
    </footer>
  </main>`
}

function llmsTxt(docs: Doc[]): string {
  const lines = [
    '# A7 Docs',
    '',
    'A7 lowers .a7 source to Zig 0.16 and then to a native binary.',
    'Use this file as a compact index. Fetch llms-full.txt for the whole corpus.',
    '',
  ]
  for (const doc of docs) {
    lines.push(`- ${doc.title}: ${ORIGIN}/docs/${doc.slug}.md`)
    if (doc.summary) lines.push(`  ${doc.summary}`)
  }
  lines.push('', 'Canonical site: ' + ORIGIN + '/')
  return lines.join('\n')
}

function llmsFull(docs: Doc[]): string {
  return [
    '# A7 Full Docs Corpus',
    '',
    'Generated from site/public/docs/*.md.',
    '',
    ...docs.flatMap((doc) => [
      `# ${doc.title}`,
      '',
      `Source: ${ORIGIN}/docs/${doc.slug}.md`,
      '',
      doc.markdown,
      '',
    ]),
  ].join('\n')
}

function sitemap(docs: Doc[]): string {
  const urls = docs.map((doc) => {
    const loc = doc.slug === 'index' ? `${ORIGIN}/` : `${ORIGIN}/${doc.slug}/`
    return `  <url><loc>${loc}</loc></url>`
  })
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`
}

type SearchEntry = {
  kind: string
  title: string
  section?: string
  summary?: string
  href: string
}

function searchIndex(docs: Doc[]): SearchEntry[] {
  const entries: SearchEntry[] = []
  for (const doc of docs) {
    const hrefBase = docHref(doc.slug)
    entries.push({
      kind: 'page',
      title: doc.title,
      section: doc.group,
      summary: doc.summary,
      href: hrefBase,
    })
    for (const h of doc.headings) {
      if (h.level < 2) continue
      entries.push({
        kind: `§${h.level}`,
        title: h.text,
        section: `${doc.nav} · ${doc.group}`,
        href: `${hrefBase}#${h.id}`,
      })
    }
  }
  return entries
}

async function writePage(doc: Doc, docs: Doc[]) {
  const outDir = doc.slug === 'index' ? DIST : path.join(DIST, doc.slug)
  await mkdir(outDir, { recursive: true })
  await writeFile(path.join(outDir, 'index.html'), pageHtml(doc, docs))
}

async function main() {
  const docs = await readDocs()
  await rm(DIST, { recursive: true, force: true })
  await mkdir(DIST, { recursive: true })
  await copyPublic(PUBLIC, DIST)
  await mkdir(path.join(DIST, 'assets'), { recursive: true })
  await copyFile(path.join(ROOT, 'src', 'site.js'), path.join(DIST, 'assets', 'site.js'))
  for (const doc of docs) await writePage(doc, docs)
  await writeFile(path.join(DIST, 'assets', 'search.json'), JSON.stringify(searchIndex(docs)))
  await writeFile(path.join(DIST, 'llms.txt'), llmsTxt(docs))
  await writeFile(path.join(DIST, 'llms-full.txt'), llmsFull(docs))
  await writeFile(path.join(DIST, 'sitemap.xml'), sitemap(docs))
  await writeFile(path.join(PUBLIC, 'llms.txt'), llmsTxt(docs))
  await writeFile(path.join(PUBLIC, 'llms-full.txt'), llmsFull(docs))
  await writeFile(path.join(PUBLIC, 'sitemap.xml'), sitemap(docs))
  console.log(`built ${docs.length} docs into ${path.relative(ROOT, DIST)}`)
}

await main()
