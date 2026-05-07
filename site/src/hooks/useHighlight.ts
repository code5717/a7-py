import { useEffect, useState } from 'react'
import { createHighlighterCore, type HighlighterCore } from 'shiki/core'
import { createOnigurumaEngine } from 'shiki/engine/oniguruma'

let highlighterPromise: Promise<HighlighterCore> | null = null

function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighterCore({
      engine: createOnigurumaEngine(import('shiki/wasm')),
      themes: [
        import('shiki/themes/github-light-high-contrast.mjs'),
        import('shiki/themes/github-dark-high-contrast.mjs'),
      ],
      langs: [
        import('shiki/langs/odin.mjs'),
        import('shiki/langs/shellscript.mjs'),
      ],
    })
  }
  return highlighterPromise
}

const langMap: Record<string, string> = {
  a7: 'odin',
  bash: 'bash',
  sh: 'bash',
}

export function useHighlight(code: string, lang?: string) {
  const [html, setHtml] = useState('')
  const mapped = lang ? langMap[lang] : undefined

  useEffect(() => {
    if (!mapped) {
      return
    }

    let cancelled = false
    getHighlighter().then((h) => {
      if (cancelled) return
      const result = h.codeToHtml(code, {
        lang: mapped,
        themes: { light: 'github-light-high-contrast', dark: 'github-dark-high-contrast' },
      })
      setHtml(result)
    })
    return () => { cancelled = true }
  }, [code, mapped])

  return mapped ? html : ''
}
