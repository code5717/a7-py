import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'
import { CURL_DOC_BY_ROUTE, CURL_DOC_GROUPS } from '../content/curlDocs'

function publicDocsPath(path: string) {
  return `${import.meta.env.BASE_URL.replace(/\/$/, '')}${path}`
}

function publicDocsUrl(path: string) {
  if (typeof window === 'undefined') {
    return publicDocsPath(path)
  }

  return new URL(publicDocsPath(path), window.location.origin).toString()
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
    if (!navigator.clipboard) {
      return
    }

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
            Open {doc.label} <span aria-hidden="true">→</span>
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
