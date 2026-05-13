import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'
import { CURL_DOC_BY_ROUTE, CURL_DOC_GROUPS, CURL_DOC_ITEMS } from '../content/curlDocs'

let mermaidInitialized = false
async function ensureMermaid() {
  if (typeof window === 'undefined') return null
  const mod = await import('mermaid')
  const mermaid = mod.default
  if (!mermaidInitialized) {
    mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'strict' })
    mermaidInitialized = true
  }
  return mermaid
}

marked.setOptions({ gfm: true, breaks: false })

const EMPTY_MERMAID_BLOCKS: string[] = []

function publicDocsPath(path: string) {
  return `${import.meta.env.BASE_URL.replace(/\/$/, '')}${path}`
}

function publicDocsUrl(path: string) {
  if (typeof window === 'undefined') {
    return publicDocsPath(path)
  }
  return new URL(publicDocsPath(path), window.location.origin).toString()
}

type ExtractResult = { source: string; mermaidBlocks: string[] }

function extractMermaidBlocks(source: string): ExtractResult {
  const blocks: string[] = []
  const out = source.replace(
    /```mermaid\s*\n([\s\S]*?)```/g,
    (_match, body: string) => {
      const id = blocks.length
      blocks.push(body)
      return `<div class="mermaid-placeholder" data-mermaid-id="${id}"></div>`
    },
  )
  return { source: out, mermaidBlocks: blocks }
}

function wrapMarkdownTables(html: string) {
  return html
    .replace(/<table>/g, '<div class="markdown-table-wrap"><table>')
    .replace(/<\/table>/g, '</table></div>')
}

function FetchCommandRow({
  href,
  label,
  command,
  className = '',
}: {
  href: string
  label: string
  command: string
  className?: string
}) {
  const [copied, setCopied] = useState(false)
  const resetTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (resetTimerRef.current !== null) {
        window.clearTimeout(resetTimerRef.current)
      }
    }
  }, [])

  const copyCommand = async () => {
    if (!navigator.clipboard) return
    await navigator.clipboard.writeText(command)
    setCopied(true)
    if (resetTimerRef.current !== null) {
      window.clearTimeout(resetTimerRef.current)
    }
    resetTimerRef.current = window.setTimeout(() => {
      setCopied(false)
      resetTimerRef.current = null
    }, 1400)
  }

  return (
    <div className={`doc-fetch-row ${className}`.trim()}>
      <a className="doc-fetch-target" href={href}>
        <span className="doc-fetch-label">{label}</span>
        <code>{command}</code>
      </a>
      <button
        type="button"
        className={`doc-copy-button${copied ? ' copied' : ''}`}
        onClick={copyCommand}
        aria-label={`Copy ${label.toLowerCase()} fetch command`}
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}

function DocDirectory() {
  return (
    <>
      <PageHeader
        eyebrow="Documentation"
        title="A7 docs"
        summary="Start with the language, examples, compiler pipeline, and current implementation status."
      />

      <SectionPanel title="Start here" className="docs-start-grid">
        <div className="link-card-grid">
          <Link to="/start" className="link-card">
            <span className="link-card-title">Getting Started</span>
            <span className="link-card-desc">Install the repo, compile a program, and run the generated Zig.</span>
          </Link>
          <Link to="/language" className="link-card">
            <span className="link-card-title">Language Reference</span>
            <span className="link-card-desc">Syntax, types, control flow, refs, generics, stdlib, and current limits.</span>
          </Link>
          <Link to="/examples" className="link-card">
            <span className="link-card-title">Examples</span>
            <span className="link-card-desc">Browse verified A7 programs and inspect their source.</span>
          </Link>
          <Link to="/internals" className="link-card">
            <span className="link-card-title">Compiler</span>
            <span className="link-card-desc">Tokenizer, parser, semantic checks, preprocessing, and Zig backend notes.</span>
          </Link>
          <Link to="/status" className="link-card">
            <span className="link-card-title">Status</span>
            <span className="link-card-desc">Implemented surface, open gaps, and next priorities.</span>
          </Link>
          <Link to="/release" className="link-card">
            <span className="link-card-title">Release</span>
            <span className="link-card-desc">Artifact builds, package checks, and release verification.</span>
          </Link>
        </div>
      </SectionPanel>

      <SectionPanel title="Reference map" className="curl-docs-group">
        <div className="doc-link-list">
          {[
            '/install',
            '/cli',
            '/language',
            '/internals',
            '/safety',
            '/examples',
            '/status',
            '/release',
            '/contributing',
            '/changelog',
          ].map((route) => {
            const item = CURL_DOC_BY_ROUTE.get(route)
            if (!item) return null
            return (
              <Link key={route} to={item.route} className="doc-link-row">
                <span>
                  <span className="doc-link-title">{item.label}</span>
                  <span className="doc-link-desc">{item.note}</span>
                </span>
              </Link>
            )
          })}
        </div>
      </SectionPanel>
    </>
  )
}

function MarkdownArticle({ markdownPath }: { markdownPath: string }) {
  const [article, setArticle] = useState<{
    markdownPath: string
    html: string | null
    error: string | null
    blocks: string[]
  }>({ markdownPath, html: null, error: null, blocks: [] })
  const containerRef = useRef<HTMLElement | null>(null)
  const navigate = useNavigate()
  const html = article.markdownPath === markdownPath ? article.html : null
  const error = article.markdownPath === markdownPath ? article.error : null
  const blocks = article.markdownPath === markdownPath ? article.blocks : EMPTY_MERMAID_BLOCKS

  useEffect(() => {
    let cancelled = false
    const url = publicDocsPath(markdownPath)
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`fetch ${res.status}`)
        return res.text()
      })
      .then((text) => {
        if (cancelled) return
        const { source, mermaidBlocks } = extractMermaidBlocks(text)
        const rendered = marked.parse(source) as string
        const clean = DOMPurify.sanitize(rendered, {
          ADD_TAGS: ['div'],
          ADD_ATTR: ['data-mermaid-id', 'class'],
        })
        setArticle({
          markdownPath,
          html: wrapMarkdownTables(clean),
          error: null,
          blocks: mermaidBlocks,
        })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : String(err)
        setArticle({ markdownPath, html: null, error: message, blocks: [] })
      })
    return () => {
      cancelled = true
    }
  }, [markdownPath])

  useEffect(() => {
    if (!html || !containerRef.current) return
    const container = containerRef.current
    const base = import.meta.env.BASE_URL
    const docsPrefix = `${base.replace(/\/$/, '')}/docs/`

    const anchors = container.querySelectorAll<HTMLAnchorElement>('a[href]')
    anchors.forEach((a) => {
      const href = a.getAttribute('href') || ''
      if (href.startsWith(docsPrefix) && href.endsWith('.md')) {
        const relMd = href.slice(docsPrefix.length).replace(/\.md$/, '')
        const item = CURL_DOC_ITEMS.find((d) => d.markdownPath === `/docs/${relMd}.md`)
        if (item) {
          a.onclick = (ev) => {
            ev.preventDefault()
            navigate(item.route)
          }
        }
      }
    })

    const placeholders = container.querySelectorAll<HTMLElement>('.mermaid-placeholder')
    if (placeholders.length === 0) return
    let cancelled = false
    ensureMermaid().then(async (mermaid) => {
      if (!mermaid || cancelled) return
      for (const el of Array.from(placeholders)) {
        const idAttr = el.getAttribute('data-mermaid-id')
        const idx = idAttr ? parseInt(idAttr, 10) : -1
        const code = blocks[idx]
        if (!code) continue
        try {
          const renderId = `mermaid-${Math.random().toString(36).slice(2, 9)}`
          const { svg } = await mermaid.render(renderId, code)
          if (cancelled) return
          el.innerHTML = svg
          el.classList.add('mermaid-rendered')
        } catch (err) {
          el.innerHTML = `<pre class="mermaid-error">Mermaid render failed: ${
            err instanceof Error ? err.message : String(err)
          }</pre>`
        }
      }
    })
    return () => {
      cancelled = true
    }
  }, [html, blocks, navigate])

  if (error) {
    return (
      <SectionPanel className="markdown-panel">
        <p className="text-secondary">Failed to load Markdown: {error}</p>
      </SectionPanel>
    )
  }

  if (html === null) {
    return (
      <SectionPanel className="markdown-panel">
        <p className="text-secondary">Loading...</p>
      </SectionPanel>
    )
  }

  return (
    <SectionPanel className="markdown-panel">
      <article
        ref={containerRef}
        className="markdown-body"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </SectionPanel>
  )
}

export default function CurlDocsPage() {
  const { pathname } = useLocation()
  const doc = CURL_DOC_BY_ROUTE.get(pathname)

  if (!doc) {
    return <div className="page"><DocDirectory /></div>
  }

  const markdownHref = publicDocsPath(doc.markdownPath)
  const markdownFetchUrl = publicDocsUrl(doc.markdownPath)
  const markdownCommand = `curl -fsS ${markdownFetchUrl}`

  return (
    <div className="page">
      <PageHeader eyebrow={doc.group} title={doc.label} summary={doc.note} />

      <MarkdownArticle markdownPath={doc.markdownPath} />

      <SectionPanel title="Browse related docs" className="curl-docs-group">
        <div className="doc-link-list">
          {CURL_DOC_GROUPS.find((group) => group.label === doc.group)?.items.map((item) => (
            <Link key={item.route} to={item.route} className="doc-link-row">
              <span>
                <span className="doc-link-title">{item.label}</span>
                <span className="doc-link-desc">{item.note}</span>
              </span>
            </Link>
          ))}
        </div>
      </SectionPanel>

      <SectionPanel title="Source Markdown" className="curl-docs-open">
        <div className="markdown-landing">
          <a className="secondary-action" href={markdownHref}>
            Open raw Markdown <span aria-hidden="true">→</span>
          </a>
        </div>
        <FetchCommandRow href={markdownHref} label="Direct fetch" command={markdownCommand} className="single" />
      </SectionPanel>
    </div>
  )
}
