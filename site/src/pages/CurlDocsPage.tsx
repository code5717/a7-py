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

function DocDirectory() {
  const docsIndexHref = publicDocsPath('/docs/index.md')
  const llmsHref = publicDocsPath('/llms.txt')
  const llmsFullHref = publicDocsPath('/llms-full.txt')
  const docsIndexUrl = publicDocsUrl('/docs/index.md')
  const llmsUrl = publicDocsUrl('/llms.txt')
  const llmsFullUrl = publicDocsUrl('/llms-full.txt')

  return (
    <>
      <PageHeader
        eyebrow="curl.md"
        title="Fetchable docs"
        summary="Stable Markdown entry points for agents, terminals, and editor tools."
      />

      <SectionPanel className="curl-docs-start">
        <div className="curl-docs-start-copy">
          <p className="section-label">Start here</p>
          <h2 className="section-title">One index, one full context file.</h2>
          <p className="text-secondary">
            Use the index for routing. Use the full context file when a single fetch is easier.
          </p>
        </div>
        <div className="curl-docs-commands">
          <a className="doc-fetch-row" href={llmsHref}>
            <span className="doc-fetch-label">Compact index</span>
            <code>curl -fsS {llmsUrl}</code>
          </a>
          <a className="doc-fetch-row" href={docsIndexHref}>
            <span className="doc-fetch-label">Docs index</span>
            <code>curl -fsS {docsIndexUrl}</code>
          </a>
          <a className="doc-fetch-row" href={llmsFullHref}>
            <span className="doc-fetch-label">Full context</span>
            <code>curl -fsS {llmsFullUrl}</code>
          </a>
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
        <a className="doc-fetch-row single" href={markdownHref}>
          <span className="doc-fetch-label">Direct fetch</span>
          <code>curl -fsS {markdownFetchUrl}</code>
        </a>
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
