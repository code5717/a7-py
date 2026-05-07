import { Link, useLocation } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'
import { CURL_DOC_BY_ROUTE, CURL_DOC_GROUPS } from '../content/curlDocs'

function publicDocsPath(path: string) {
  return `${import.meta.env.BASE_URL.replace(/\/$/, '')}${path}`
}

function DocDirectory() {
  return (
    <>
      <PageHeader
        eyebrow="curl.md"
        title="Markdown docs"
        summary="Fetchable pages for agents, terminals, and editor tools."
      />

      {CURL_DOC_GROUPS.map((group) => (
        <SectionPanel key={group.label} title={group.label}>
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

  return (
    <div className="page">
      <PageHeader eyebrow={doc.group} title={doc.label} summary={doc.note} />

      <SectionPanel title="Open Markdown">
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
      </SectionPanel>

      <SectionPanel title="Browse">
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
