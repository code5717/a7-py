/*
 * Post-mount DOM enhancement of rendered markdown HTML.
 * The a7-docs Vite plugin emits:
 *   <div class="codeblock" data-lang="...">
 *     <div class="codeblock__inner">…Shiki HTML…</div>
 *   </div>
 *   <div class="mermaid-block" data-mermaid="base64-source"></div>
 *
 * We wrap codeblocks with a filename strip + copy button via direct DOM mutation
 * (cheaper than re-rendering through React) and render mermaid SVG into placeholders.
 */

export function enhanceCodeBlocks(root: HTMLElement) {
  const blocks = root.querySelectorAll<HTMLDivElement>('.codeblock')
  blocks.forEach((block) => {
    if (block.dataset.enhanced === '1') return
    block.dataset.enhanced = '1'
    const lang = block.dataset.lang || 'text'
    const inner = block.querySelector<HTMLDivElement>('.codeblock__inner')
    if (!inner) return

    const source = inner.textContent ?? ''

    const strip = document.createElement('header')
    strip.className = 'codeblock__strip'
    strip.setAttribute('role', 'toolbar')

    const left = document.createElement('span')
    left.className = 'codeblock__lang'
    left.textContent = lang.toLowerCase()
    strip.appendChild(left)

    const copy = document.createElement('button')
    copy.type = 'button'
    copy.className = 'codeblock__copy'
    copy.setAttribute('aria-label', 'Copy code')
    copy.textContent = '[ copy ]'
    let timer: number | null = null
    copy.addEventListener('click', () => {
      void navigator.clipboard.writeText(source).then(() => {
        copy.textContent = '[ copied ]'
        if (timer) window.clearTimeout(timer)
        timer = window.setTimeout(() => {
          copy.textContent = '[ copy ]'
        }, 1400)
      })
    })
    strip.appendChild(copy)

    block.insertBefore(strip, inner)
  })
}

let mermaidPromise: Promise<typeof import('mermaid').default> | null = null

async function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then((mod) => {
      const m = mod.default
      m.initialize({
        startOnLoad: false,
        theme: document.documentElement.dataset.theme === 'light' ? 'default' : 'dark',
        securityLevel: 'strict',
        fontFamily: 'Geist Mono, JetBrains Mono, monospace',
      })
      return m
    })
  }
  return mermaidPromise
}

let counter = 0

/**
 * Render <div class="mermaid-block" data-mermaid="…b64…"> placeholders into SVGs.
 * Returns a disposer that aborts in-flight renders.
 */
export function mountMermaidBlocks(root: HTMLElement): () => void {
  const placeholders = Array.from(root.querySelectorAll<HTMLDivElement>('.mermaid-block'))
  let cancelled = false
  if (placeholders.length === 0) return () => undefined

  void (async () => {
    const mermaid = await loadMermaid()
    if (cancelled) return
    for (const ph of placeholders) {
      if (ph.dataset.rendered === '1') continue
      const b64 = ph.dataset.mermaid
      if (!b64) continue
      try {
        const source = atob(b64)
        const id = `mermaid-svg-${++counter}`
        const { svg } = await mermaid.render(id, source)
        if (cancelled) return
        ph.innerHTML = svg
        ph.dataset.rendered = '1'
      } catch (err) {
        ph.innerHTML = `<pre style="color:var(--danger)">${(err as Error).message}</pre>`
      }
    }
  })()

  return () => {
    cancelled = true
  }
}
