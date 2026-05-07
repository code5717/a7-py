import { useEffect, useId, useRef, useState } from 'react'
import { useHighlight } from '../hooks/useHighlight'
import { lockBodyScroll } from '../utils/scrollLock'

interface CodeModalProps {
  title: string
  code: string
  onClose: () => void
  runCommand?: string
  lineCount?: number
}

export default function CodeModal({ title, code, onClose, runCommand, lineCount }: CodeModalProps) {
  const html = useHighlight(code, 'a7')
  const titleId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const [copied, setCopied] = useState<'source' | 'command' | null>(null)
  const copyResetRef = useRef<number | null>(null)

  useEffect(() => {
    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }

      if (e.key !== 'Tab' || !panelRef.current) {
        return
      }

      const focusables = panelRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )

      if (focusables.length === 0) {
        e.preventDefault()
        return
      }

      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const active = document.activeElement

      if (e.shiftKey && active === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKey)
    const releaseScrollLock = lockBodyScroll()
    closeButtonRef.current?.focus()

    return () => {
      document.removeEventListener('keydown', handleKey)
      releaseScrollLock()
      previousFocusRef.current?.focus()
      if (copyResetRef.current !== null) {
        window.clearTimeout(copyResetRef.current)
      }
    }
  }, [onClose])

  const copyText = async (kind: 'source' | 'command', value: string) => {
    if (!navigator.clipboard) {
      return
    }

    await navigator.clipboard.writeText(value)
    setCopied(kind)
    if (copyResetRef.current !== null) {
      window.clearTimeout(copyResetRef.current)
    }
    copyResetRef.current = window.setTimeout(() => {
      setCopied(null)
      copyResetRef.current = null
    }, 1400)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        ref={panelRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <div className="modal-title-group">
            <h2 id={titleId} className="modal-title">
              <code className="doc-inline-code">{title}</code>
            </h2>
            {lineCount ? <p className="modal-meta">{lineCount} {lineCount === 1 ? 'line' : 'lines'}</p> : null}
          </div>
          <div className="modal-actions">
            <button
              type="button"
              className="code-action-button"
              onClick={() => void copyText('source', code)}
            >
              {copied === 'source' ? 'Copied source' : 'Copy source'}
            </button>
            {runCommand ? (
              <button
                type="button"
                className="code-action-button"
                onClick={() => void copyText('command', runCommand)}
              >
                {copied === 'command' ? 'Copied command' : 'Copy run command'}
              </button>
            ) : null}
          </div>
          <button
            type="button"
            ref={closeButtonRef}
            className="icon-button"
            onClick={onClose}
            aria-label="Close modal"
          >
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        {html ? (
          <div className="modal-code code-highlighted" dangerouslySetInnerHTML={{ __html: html }} />
        ) : (
          <pre className="modal-code">
            <code>{code}</code>
          </pre>
        )}
      </div>
    </div>
  )
}
