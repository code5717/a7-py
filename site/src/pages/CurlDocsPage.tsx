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
  const docsIndexHref = publicDocsPath('/docs/index.md')
  const llmsHref = publicDocsPath('/llms.txt')
  const llmsFullHref = publicDocsPath('/llms-full.txt')
  const docsIndexUrl = publicDocsUrl('/docs/index.md')
  const llmsUrl = publicDocsUrl('/llms.txt')
  const llmsFullUrl = publicDocsUrl('/llms-full.txt')
  const llmsCommand = `curl -fsS ${llmsUrl}`
  const docsIndexCommand = `curl -fsS ${docsIndexUrl}`
  const llmsFullCommand = `curl -fsS ${llmsFullUrl}`

  return (
    <>
      <PageHeader
        eyebrow="curl.md"
        title="Fetchable docs"
        summary="Stable Markdown files for curl.md, agents, terminals, and editor tools."
      />

      <SectionPanel className="curl-docs-start">
        <div className="curl-docs-start-copy">
          <p className="section-label">Start here</p>
          <h2 className="section-title">A small index, then exact files.</h2>
          <p className="text-secondary">
            Fetch `llms.txt` to route. Fetch `docs/index.md` for the full navigation tree.
            Use `llms-full.txt` only when one combined context file is easier.
          </p>
        </div>
        <div className="curl-docs-commands">
          <FetchCommandRow href={llmsHref} label="Compact index" command={llmsCommand} />
          <FetchCommandRow href={docsIndexHref} label="Docs index" command={docsIndexCommand} />
          <FetchCommandRow href={llmsFullHref} label="Full context" command={llmsFullCommand} />
        </div>
      </SectionPanel>

      {CURL_DOC_GROUPS.map((group) => (
        <SectionPanel key={group.label} title={group.label} className="curl-docs-group">
          <div className="doc-link-list">
            {group.items.map((item) => (
              <Link key={item.route} to={item.route} className="doc-link-row">
                <span>
                  <span className="doc-link-title">{item.label}</span>
                  <span className="doc-link-desc">{item.note}</span>
                </span>
                <code className="doc-inline-code">{item.markdownPath}</code>
              </Link>
            ))}
          </div>
        </SectionPanel>
      ))}
    </>
  )
}

function MarkdownArticle({ markdownPath }: { markdownPath: string }) {
  const [html, setHtml] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [blocks, setBlocks] = useState<string[]>([])
  const containerRef = useRef<HTMLElement | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    setHtml(null)
    setError(null)
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
        setBlocks(mermaidBlocks)
        setHtml(clean)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : String(err)
        setError(message)
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

      <SectionPanel title="Open Markdown" className="curl-docs-open">
        <div className="markdown-landing">
          <a className="primary-action" href={markdownHref}>
            Open raw Markdown <span aria-hidden="true">→</span>
          </a>
          <a className="secondary-action" href={publicDocsPath('/llms.txt')}>
            llms.txt <span aria-hidden="true">→</span>
          </a>
          <a className="secondary-action" href={publicDocsPath('/llms-full.txt')}>
            full context <span aria-hidden="true">→</span>
          </a>
        </div>
        <FetchCommandRow href={markdownHref} label="Direct fetch" command={markdownCommand} className="single" />
      </SectionPanel>

      <MarkdownArticle markdownPath={doc.markdownPath} />

      <SectionPanel title="Browse" className="curl-docs-group">
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
    </div>
  )
}
