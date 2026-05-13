import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ENTRIES_BY_PATH,
  dataUrl,
  githubEditUrl,
  neighbours,
  sourceMarkdownUrl,
  type ManifestEntry,
} from '../content/manifest'
import PaperCard from '../components/PaperCard'
import TocRail from '../components/TocRail'
import PageFooter from '../components/PageFooter'
import { enhanceCodeBlocks, mountMermaidBlocks } from '../utils/enhanceDom'
import styles from './DocPage.module.css'

interface DocJson {
  slug: string
  sourcePath: string
  frontmatter: Record<string, unknown>
  html: string
  headings: Array<{ level: 1 | 2 | 3; id: string; text: string }>
  firstParagraph: string
}

export default function DocPage({ path }: { path: string }) {
  const entry = ENTRIES_BY_PATH.get(path) as ManifestEntry | undefined
  const [loadState, setLoadState] = useState<{
    path: string
    doc: DocJson | null
    error: string | null
  }>({ path: '', doc: null, error: null })
  const proseRef = useRef<HTMLDivElement | null>(null)
  const np = useMemo(() => (entry ? neighbours(entry.path) : { prev: undefined, next: undefined }), [entry])
  const doc = loadState.path === path ? loadState.doc : null
  const error = loadState.path === path ? loadState.error : null

  useEffect(() => {
    if (!entry) return
    let cancelled = false
    void (async () => {
      try {
        const res = await fetch(dataUrl(entry))
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        const json = (await res.json()) as DocJson
        if (!cancelled) setLoadState({ path: entry.path, doc: json, error: null })
      } catch (err) {
        if (!cancelled) setLoadState({ path: entry.path, doc: null, error: (err as Error).message })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [entry])

  useEffect(() => {
    if (!doc || !proseRef.current) return
    enhanceCodeBlocks(proseRef.current)
    const dispose = mountMermaidBlocks(proseRef.current)
    return dispose
  }, [doc])

  useEffect(() => {
    if (!entry) return
    document.title = `${entry.title} — A7 Docs`
    const link = document.querySelector('link[rel="alternate"][type="text/markdown"]')
    const href = sourceMarkdownUrl(entry)
    if (link) link.setAttribute('href', href)
    else {
      const el = document.createElement('link')
      el.rel = 'alternate'
      el.type = 'text/markdown'
      el.href = href
      document.head.appendChild(el)
    }
  }, [entry])

  if (!entry) return null

  return (
    <div className={styles.layout}>
      <div className={styles.center}>
        <PaperCard filePath={`docs/${entry.source}.md`} rightLabel={entry.eyebrow}>
          <div className={styles.eyebrow}>{entry.eyebrow}</div>
          {!doc && !error && <p className={styles.loading}>Loading…</p>}
          {error && <p className={styles.error}>Could not load: {error}</p>}
          {doc && (
            <div
              ref={proseRef}
              className="prose"
              dangerouslySetInnerHTML={{ __html: doc.html }}
            />
          )}
        </PaperCard>
        <div className={styles.footer}>
          <PageFooter
            prev={np.prev}
            next={np.next}
            sourceUrl={sourceMarkdownUrl(entry)}
            editUrl={githubEditUrl(entry)}
          />
        </div>
      </div>
      {doc && doc.headings.length > 0 && (
        <TocRail headings={doc.headings} />
      )}
    </div>
  )
}
