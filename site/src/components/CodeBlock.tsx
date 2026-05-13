import { useEffect, useRef, useState } from 'react'
import styles from './CodeBlock.module.css'

interface Props {
  /** Pre-highlighted HTML from Shiki (build-time). Already inside the codeblock body. */
  highlightedHtml?: string
  /** Plain text (used for copy and as a fallback when highlightedHtml is absent) */
  source: string
  language: string
  filename?: string
}

export default function CodeBlock({ highlightedHtml, source, language, filename }: Props) {
  const [copied, setCopied] = useState(false)
  const timeoutRef = useRef<number | null>(null)

  useEffect(() => () => {
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current)
  }, [])

  function onCopy() {
    void navigator.clipboard.writeText(source).then(() => {
      setCopied(true)
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current)
      timeoutRef.current = window.setTimeout(() => setCopied(false), 1400)
    })
  }

  return (
    <figure className={styles.block}>
      <header className={styles.strip}>
        <span className={styles.left}>
          <span className={styles.lang}>{filename ?? language ?? 'text'}</span>
        </span>
        <button type="button" className={styles.copy} onClick={onCopy} aria-label="Copy code">
          {copied ? '[ copied ]' : '[ copy ]'}
        </button>
      </header>
      {highlightedHtml ? (
        <div className={styles.body} dangerouslySetInnerHTML={{ __html: highlightedHtml }} />
      ) : (
        <pre className={styles.body}>
          <code>{source}</code>
        </pre>
      )}
    </figure>
  )
}
