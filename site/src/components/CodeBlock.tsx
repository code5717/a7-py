import { useEffect, useRef, useState } from 'react'
import { useHighlight } from '../hooks/useHighlight'

interface CodeBlockProps {
  code: string
  lang?: string
  title?: string
}

export default function CodeBlock({ code, lang, title }: CodeBlockProps) {
  const html = useHighlight(code, lang)
  const [copied, setCopied] = useState(false)
  const resetTimerRef = useRef<number | null>(null)
  const codeLabel = title || lang || 'code'

  useEffect(() => {
    return () => {
      if (resetTimerRef.current !== null) {
        window.clearTimeout(resetTimerRef.current)
      }
    }
  }, [])

  const copyCode = async () => {
    if (!navigator.clipboard) {
      setCopied(false)
      return
    }

    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)

      if (resetTimerRef.current !== null) {
        window.clearTimeout(resetTimerRef.current)
      }

      resetTimerRef.current = window.setTimeout(() => {
        setCopied(false)
        resetTimerRef.current = null
      }, 1400)
    } catch {
      setCopied(false)
    }
  }

  return (
    <figure className={`code-shell${lang ? ` code-lang-${lang}` : ''}`} data-reveal>
      {(title || lang) && (
        <figcaption className="code-head">
          <span className="code-head-title">{codeLabel}</span>
          <span className="code-head-tools">
            {lang ? <span className="code-head-meta">{lang}</span> : null}
            <button
              type="button"
              className={`code-copy-button${copied ? ' copied' : ''}`}
              onClick={copyCode}
              aria-label={`Copy ${codeLabel} block`}
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
          </span>
        </figcaption>
      )}
      {html ? (
        <div
          className="code-pre code-highlighted"
          role="region"
          aria-label={`${codeLabel} source`}
          tabIndex={0}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre className="code-pre" role="region" aria-label={`${codeLabel} source`} tabIndex={0}>
          <code>{code}</code>
        </pre>
      )}
    </figure>
  )
}
