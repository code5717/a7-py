import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MANIFEST } from '../content/manifest'
import styles from './SearchModal.module.css'

interface IndexEntry {
  slug: string
  title: string
  firstParagraph: string
  headings: Array<{ level: 1 | 2 | 3; id: string; text: string }>
}

interface SearchResult {
  path: string
  title: string
  context: string
  hash?: string
  score: number
}

const INDEX_URL = '/a7-py/docs-data/search-index.json'

function score(query: string, text: string, weight: number): number {
  const q = query.toLowerCase()
  const t = text.toLowerCase()
  if (!t.includes(q)) return 0
  if (t === q) return 100 * weight
  if (t.startsWith(q)) return 60 * weight
  return 30 * weight
}

const SLUG_TO_PATH = new Map(MANIFEST.map((e) => [e.source, e.path]))

export default function SearchModal({ onClose }: { onClose: () => void }) {
  const [index, setIndex] = useState<IndexEntry[] | null>(null)
  const [query, setQuery] = useState('')
  const [activeIdx, setActiveIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const res = await fetch(INDEX_URL)
        const json = (await res.json()) as IndexEntry[]
        if (!cancelled) setIndex(json)
      } catch {
        /* ignore */
      }
    })()
    inputRef.current?.focus()
    return () => {
      cancelled = true
    }
  }, [])

  const results = useMemo<SearchResult[]>(() => {
    if (!index || !query.trim()) return []
    const out: SearchResult[] = []
    for (const entry of index) {
      const route = SLUG_TO_PATH.get(entry.slug)
      if (!route) continue
      const titleScore = score(query, entry.title, 3)
      const paraScore = score(query, entry.firstParagraph, 1)
      let best = titleScore + paraScore
      let hash: string | undefined
      let context = entry.firstParagraph
      for (const h of entry.headings) {
        const s = score(query, h.text, 2)
        if (s > 0) {
          best += s
          if (!hash || s > 30) {
            hash = h.id
            context = h.text
          }
        }
      }
      if (best > 0) {
        out.push({ path: route, title: entry.title, context, hash, score: best })
      }
    }
    return out.sort((a, b) => b.score - a.score).slice(0, 12)
  }, [index, query])

  useEffect(() => {
    setActiveIdx(0)
  }, [query])

  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      const r = results[activeIdx]
      if (r) {
        e.preventDefault()
        navigate(r.path + (r.hash ? `#${r.hash}` : ''))
        onClose()
      }
    } else if (e.key === 'Escape') {
      onClose()
    }
  }

  return (
    <div className={styles.scrim} role="dialog" aria-modal="true" aria-label="Search docs" onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()} onKeyDown={onKeyDown}>
        <header className={styles.header}>
          <span className={styles.tag}>[ SEARCH ]</span>
          <input
            ref={inputRef}
            className={styles.input}
            type="search"
            placeholder="Search docs…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
          <button type="button" className={styles.close} onClick={onClose} aria-label="Close search">
            [ esc ]
          </button>
        </header>
        <ul className={styles.results}>
          {query && results.length === 0 && (
            <li className={styles.empty}>no results</li>
          )}
          {results.map((r, i) => (
            <li key={`${r.path}#${r.hash ?? ''}`}>
              <button
                type="button"
                className={`${styles.result} ${i === activeIdx ? styles.active : ''}`}
                onClick={() => {
                  navigate(r.path + (r.hash ? `#${r.hash}` : ''))
                  onClose()
                }}
                onMouseEnter={() => setActiveIdx(i)}
              >
                <span className={styles.resultTitle}>{r.title}</span>
                <span className={styles.resultPath}>{r.path}{r.hash ? `#${r.hash}` : ''}</span>
                <span className={styles.resultCtx}>{r.context}</span>
              </button>
            </li>
          ))}
        </ul>
        <footer className={styles.footer}>
          <span>↑↓ navigate</span>
          <span>↵ open</span>
          <span>esc close</span>
        </footer>
      </div>
    </div>
  )
}
