import { describe, expect, test } from 'bun:test'
import { readRegistry, renderMarkdown, exportsFor, BASE, ORIGIN } from './content'

describe('Markdown publication requirements', () => {
  test('literal code survives HTML escaping and raw HTML never becomes executable markup', () => {
    const source = '# Escaping\n\n<script>alert("unsafe")</script>\n\n```a7\nif a < b && b > 0 { io.println("<tag>") }\n```\n\n[x](javascript:alert%281%29)\n'
    const { html } = renderMarkdown(source)
    expect(html).not.toContain('<script>')
    expect(html).not.toContain('href="javascript:')
    expect(html).toContain('&lt;script&gt;')
    const literalCode = html.match(/<code[^>]*>([\s\S]*?)<\/code>/)?.[1]
    expect(literalCode?.replace(/&quot;/g, '"').replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&amp;/g, '&').trimEnd())
      .toBe('if a < b && b > 0 { io.println("<tag>") }')
  })

  test('nested instructions, blockquotes and tables retain their document structure', () => {
    const { html } = renderMarkdown('# Structures\n\n1. Install\n   - Get Python\n   - Get Zig\n2. Compile\n\n> Compile trusted source only.\n\n| Input | Output |\n| --- | --- |\n| `.a7` | native binary |\n')
    expect(html).toMatch(/<ol>[\s\S]*<li>[\s\S]*<ul>[\s\S]*Get Python[\s\S]*<\/ul>[\s\S]*<\/li>[\s\S]*<\/ol>/)
    expect(html).toContain('<blockquote>')
    expect(html).toContain('<thead>')
    expect(html).toContain('<tbody>')
    expect(html).toContain('<code>.a7</code>')
  })

  test('repeated headings receive unique stable link targets', () => {
    const markdown = '# Reference\n\n## Functions\n\nFirst.\n\n## Functions\n\nSecond.\n\n## Functions 1\n\nNamed suffix.\n'
    const first = renderMarkdown(markdown)
    const second = renderMarkdown(markdown)
    expect(first.headings).toEqual(second.headings)
    expect(new Set(first.headings.map(heading => heading.id)).size).toBe(first.headings.length)
    for (const heading of first.headings) expect(first.html).toContain(`id="${heading.id}"`)
  })
})

test('registry preserves old routes and covers all twelve approved reference topics', async () => {
  const docs = await readRegistry()
  const slugs = new Set(docs.map(doc => doc.slug))
  for (const slug of ['index', 'start', 'language', 'stdlib', 'compiler', 'status', 'release', 'agent-usage', 'project', 'tour', 'examples']) expect(slugs.has(slug)).toBe(true)
  for (const topic of ['syntax', 'declarations', 'types', 'operators', 'control-flow', 'functions', 'arrays-strings', 'aggregate-types', 'generics', 'memory', 'modules', 'builtins']) expect(slugs.has(`language/${topic}`)).toBe(true)
  expect(slugs.size).toBe(docs.length)
  expect(BASE).toBe('/a7-py')
  for (const doc of docs) {
    expect(doc.html.match(/<h1(?:\s|>)/g)?.length).toBe(1)
    expect(doc.title.trim().length).toBeGreaterThan(0)
    expect(doc.summary.trim().length).toBeGreaterThan(0)
    const ids = Array.from(doc.html.matchAll(/\bid="([^"]+)"/g), match => match[1])
    expect(new Set(ids).size).toBe(ids.length)
  }
})


test('each published document has matching discovery, manifest and sitemap records', async () => {
  const docs = await readRegistry()
  const exports = exportsFor(docs)
  const manifest = JSON.parse(exports['docs/manifest.json'])
  expect(manifest.schemaVersion).toBe(1)
  expect(manifest.pages.length).toBe(docs.length)
  expect(exportsFor(docs)).toEqual(exports)
  for (const doc of docs) {
    const page = manifest.pages.find((page: { id: string }) => page.id === doc.slug)
    expect(page?.title).toBe(doc.title)
    expect(page?.sections).toEqual(doc.headings)
    expect(exports['llms.txt']).toContain(`](${ORIGIN}/docs/${doc.slug}.md)`)
    expect(exports['llms-full.txt'].split(`Source: ${ORIGIN}/docs/${doc.slug}.md`).length - 1).toBe(1)
    expect(exports['sitemap.xml']).toContain(`<loc>${page.url}</loc>`)
    expect(page.sources.length).toBeGreaterThan(0)
    for (const feature of doc.features) {
      const entry = manifest.features.find((entry: { id: string }) => entry.id === feature.id)
      expect(entry.documentationUrl).toBe(page.url)
      expect(entry.markdownUrl).toBe(page.markdown)
      expect(feature.qualification.length).toBeGreaterThan(0)
      expect(feature.evidence.length).toBeGreaterThan(0)
    }
  }
  expect(new Set(manifest.features.map((feature: { id: string }) => feature.id)).size).toBe(manifest.features.length)
})

test('Markdown topic links resolve to HTML topics and preserve fragment targets', () => {
  const { html } = renderMarkdown('# Links\n\n[Functions](/a7-py/docs/language/functions.md#parameters)\n\n[Types](types.md#numeric-types)\n', 'language/functions')
  expect(html).toContain('href="/a7-py/language/functions/#parameters"')
  expect(html).toContain('href="/a7-py/language/types/#numeric-types"')
})

test('local article links resolve to a documented route and section', async () => {
  const docs = await readRegistry()
  for (const doc of docs) {
    for (const match of doc.html.matchAll(/href="([^"\s]+)"/g)) {
      const url = new URL(match[1].replace(/&amp;/g, '&'), `${ORIGIN}/${doc.slug === 'index' ? '' : doc.slug + '/'}`)
      if (url.origin !== new URL(ORIGIN).origin || !url.pathname.startsWith(BASE + '/')) continue
      if (/\.[a-z0-9]+$/.test(url.pathname)) continue
      const slug = url.pathname.slice(BASE.length).replace(/^\/|\/$/g, '') || 'index'
      const target = docs.find(page => page.slug === slug)
      expect(target, `${doc.slug}: missing topic ${url.href}`).toBeDefined()
      if (url.hash) {
        const id = decodeURIComponent(url.hash.slice(1))
        expect(target!.headings.some(heading => heading.id === id) || target!.aliases.includes(id), `${doc.slug}: missing anchor ${url.href}`).toBe(true)
      }
    }
  }
})

test('full corpus leaves fenced examples untouched while converting prose links', async () => {
  const [sample] = await readRegistry()
  const fenced = '````markdown\n```text\n[Literal URL](/a7-py/language/)\n```\n````'
  const docs = [{ ...sample, markdown: '# Fixture\n\n[Reference](/a7-py/language/)\n\n' + fenced }]
  const full = exportsFor(docs)['llms-full.txt']
  expect(full).toContain('[Reference](/a7-py/docs/language.md)')
  expect(full).toContain(fenced)
})

test('full corpus resolves nested relative Markdown links from each source document', async () => {
  const [sample] = await readRegistry()
  const full = exportsFor([{...sample,slug:'language/functions',markdown:'# Functions\n\n[Types](types.md#primitive-types) and [status](../status.md) and [local](#functions).'}])['llms-full.txt']
  expect(full).toContain('](/a7-py/docs/language/types.md#primitive-types)')
  expect(full).toContain('](/a7-py/docs/status.md)')
  expect(full).toContain('](/a7-py/docs/language/functions.md#functions)')
})

test('search excerpts preserve identifiers and ignore Markdown links and fenced headings', async () => {
  const { searchEntries } = await import('./search')
  const [sample] = await readRegistry()
  const markdown = '# Guide\n\nRead [the types](types.md).\n\n## Code\n\n```a7\n# not a heading\nvalue := thing.len\n```\n\nText after code.'
  const rendered = renderMarkdown(markdown)
  const entries = searchEntries([{...sample,...rendered,markdown}])
  expect(entries.map(entry => entry.section)).toEqual(['Guide','Code'])
  expect(entries[0].text).toContain('Read the types.')
  expect(entries[0].text).not.toContain('types.md')
  expect(entries[1].text).toContain('thing.len')
  expect(entries[1].text).toContain('Text after code.')
  expect(entries[1].href).toEndWith('#code')
})

test('agent export preserves inline and indented code that looks like links', async () => {
  const [sample] = await readRegistry()
  const inline = '`[literal](/a7-py/start/)`'
  const nested = '``[literal ` tick](/a7-py/start/)``'
  const indented = '    [literal](/a7-py/start/)'
  const markdown = `# Fixture\n\n${inline}\n\n${nested}\n\n${indented}\n\n[Real link](/a7-py/start/)`
  const full = exportsFor([{...sample,markdown}])['llms-full.txt']
  expect(full).toContain(inline)
  expect(full).toContain(nested)
  expect(full).toContain(indented)
  expect(full).toContain('[Real link](/a7-py/docs/start.md)')
})
