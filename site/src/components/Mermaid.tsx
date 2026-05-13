import { useEffect, useRef, useState } from 'react'
import styles from './Mermaid.module.css'

let mermaidPromise: Promise<typeof import('mermaid').default> | null = null

async function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then((mod) => {
      const m = mod.default
      m.initialize({
        startOnLoad: false,
        theme: 'dark',
        securityLevel: 'strict',
        fontFamily: 'Geist Mono, JetBrains Mono, monospace',
      })
      return m
    })
  }
  return mermaidPromise
}

let counter = 0

export default function Mermaid({ source }: { source: string }) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const mermaid = await loadMermaid()
        if (cancelled || !hostRef.current) return
        const id = `mermaid-${++counter}`
        const { svg } = await mermaid.render(id, source)
        if (!cancelled && hostRef.current) hostRef.current.innerHTML = svg
      } catch (err) {
        if (!cancelled) setError((err as Error).message)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [source])

  if (error) return <pre className={styles.error}>{error}</pre>
  return <figure className={styles.figure} ref={hostRef} aria-label="Diagram" />
}
