// A7 docs — typography, motion, search, shortcuts
const base = '/a7-py'

// ─────────── legacy URL fallbacks ───────────
if (location.hash.startsWith('#/')) {
  location.replace(base + location.hash.slice(1))
}
const from = new URLSearchParams(location.search).get('from')
if (from && location.pathname === base + '/') {
  const clean = from.replace(/^\/+/, '')
  const known = ['start', 'language', 'stdlib', 'compiler', 'status', 'release', 'agent-usage', 'project']
  const first = clean.split('/')[0]
  if (known.includes(first)) location.replace(`${base}/${first}/`)
}

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ─────────── reading progress ───────────
const progress = document.querySelector('.read-progress')
if (progress) {
  let ticking = false
  const update = () => {
    const max = document.documentElement.scrollHeight - innerHeight
    const ratio = max > 0 ? Math.min(1, Math.max(0, scrollY / max)) : 0
    progress.style.transform = `scaleX(${ratio})`
    ticking = false
  }
  update()
  const onScroll = () => {
    if (ticking) return
    requestAnimationFrame(update)
    ticking = true
  }
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onScroll, { passive: true })
}

// ─────────── code copy buttons ───────────
document.querySelectorAll('pre code').forEach((code) => {
  const pre = code.parentElement
  if (!pre || pre.querySelector('.copy')) return
  const button = document.createElement('button')
  button.type = 'button'
  button.className = 'copy'
  button.textContent = 'copy'
  button.setAttribute('aria-label', 'Copy code')
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(code.textContent || '')
      button.textContent = 'copied'
      button.classList.add('is-copied')
    } catch {
      button.textContent = 'failed'
    }
    setTimeout(() => {
      button.textContent = 'copy'
      button.classList.remove('is-copied')
    }, 1200)
  })
  pre.append(button)
})

// ─────────── scroll-reveal ───────────
if (!reduceMotion && 'IntersectionObserver' in window) {
  const reveal = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-revealed')
        reveal.unobserve(entry.target)
      }
    }
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0 })

  // mark home sections and prose blocks
  const candidates = document.querySelectorAll(
    '.route-board, .terminal-strip, .prose > h2, .prose > h3, .prose > p, .prose > ul, .prose > ol, .prose > pre, .prose > table, .doc-pager',
  )
  candidates.forEach((el, i) => {
    el.setAttribute('data-reveal', '')
    el.style.setProperty('--reveal-delay', `${Math.min(i, 4) * 40}ms`)
    reveal.observe(el)
  })
}

// ─────────── TOC scrollspy ───────────
const tocEl = document.querySelector('.toc')
if (tocEl && 'IntersectionObserver' in window) {
  const tocLinks = Array.from(tocEl.querySelectorAll('a[href^="#"]'))
  const map = new Map()
  for (const a of tocLinks) {
    const id = decodeURIComponent(a.getAttribute('href').slice(1))
    const target = document.getElementById(id)
    if (target) map.set(target, a)
  }
  let activeEl = null
  const setActive = (el) => {
    if (activeEl === el) return
    activeEl = el
    tocLinks.forEach((l) => l.classList.remove('active'))
    map.get(el)?.classList.add('active')
  }
  const headings = Array.from(map.keys())
  const spy = new IntersectionObserver((entries) => {
    // pick the topmost intersecting heading
    const visible = entries.filter((e) => e.isIntersecting)
    if (visible.length) {
      const top = visible.reduce((a, b) =>
        a.boundingClientRect.top < b.boundingClientRect.top ? a : b,
      )
      setActive(top.target)
    }
  }, { rootMargin: '-15% 0px -70% 0px', threshold: 0 })
  headings.forEach((h) => spy.observe(h))
}

// ─────────── modals ───────────
function getModal(name) {
  return document.querySelector(`[data-modal="${name}"]`)
}

let lastFocus = null

function openModal(name) {
  const modal = getModal(name)
  if (!modal) return
  closeAllModals(name)
  lastFocus = document.activeElement
  modal.setAttribute('data-open', '')
  document.body.style.overflow = 'hidden'
  const target =
    modal.querySelector('[data-autofocus]') ||
    modal.querySelector('input, textarea, select') ||
    modal.querySelector('button, a')
  if (!target) return
  // Force layout flush so the focus call lands on a now-visible element
  void modal.offsetWidth
  target.focus({ preventScroll: true })
  if (target instanceof HTMLInputElement) target.select?.()
  // Retry once more in case the first attempt was lost during the display change
  requestAnimationFrame(() => {
    if (document.activeElement !== target) target.focus({ preventScroll: true })
  })
}

function closeModal(name) {
  const modal = getModal(name)
  if (!modal || !modal.hasAttribute('data-open')) return
  modal.removeAttribute('data-open')
  document.body.style.overflow = ''
  lastFocus?.focus?.()
}

function closeAllModals(except) {
  document.querySelectorAll('[data-modal][data-open]').forEach((m) => {
    if (m.dataset.modal !== except) {
      m.removeAttribute('data-open')
      document.body.style.overflow = ''
    }
  })
}

document.querySelectorAll('[data-modal]').forEach((modal) => {
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal(modal.dataset.modal)
  })
  modal.querySelectorAll('[data-modal-close]').forEach((btn) => {
    btn.addEventListener('click', () => closeModal(modal.dataset.modal))
  })
})

document.querySelectorAll('[data-shortcuts-open]').forEach((btn) => {
  btn.addEventListener('click', () => openModal('shortcuts'))
})
document.querySelectorAll('[data-search-open]').forEach((btn) => {
  btn.addEventListener('click', () => openModal('search'))
})

// ─────────── search ───────────
const searchModal = getModal('search')
const searchInput = searchModal?.querySelector('input')
const searchList = searchModal?.querySelector('[data-search-list]')
const searchEmpty = searchModal?.querySelector('[data-search-empty]')
let searchIndex = null
let searchIndexPromise = null
let searchSelection = 0

async function loadSearchIndex() {
  if (searchIndex) return searchIndex
  if (!searchIndexPromise) {
    searchIndexPromise = fetch(`${base}/assets/search.json`)
      .then((r) => r.json())
      .catch(() => [])
  }
  searchIndex = await searchIndexPromise
  return searchIndex
}

function rankSearch(items, q) {
  if (!q) return items.slice(0, 12)
  const needle = q.toLowerCase().trim()
  const tokens = needle.split(/\s+/).filter(Boolean)
  const scored = []
  for (const item of items) {
    const hay = `${item.title} ${item.section ?? ''} ${item.summary ?? ''}`.toLowerCase()
    let score = 0
    let allHit = true
    for (const t of tokens) {
      const idx = hay.indexOf(t)
      if (idx === -1) { allHit = false; break }
      score += 100 - Math.min(idx, 80)
      if (item.title.toLowerCase().startsWith(t)) score += 80
      if ((item.section ?? '').toLowerCase().includes(t)) score += 30
    }
    if (allHit) scored.push({ item, score })
  }
  scored.sort((a, b) => b.score - a.score)
  return scored.slice(0, 12).map((s) => s.item)
}

function renderSearch(items) {
  if (!searchList) return
  searchList.innerHTML = ''
  if (!items.length) {
    if (searchEmpty) searchEmpty.style.display = 'block'
    return
  }
  if (searchEmpty) searchEmpty.style.display = 'none'
  items.forEach((item, i) => {
    const a = document.createElement('a')
    a.href = item.href
    a.className = 'search-result'
    a.setAttribute('role', 'option')
    if (i === searchSelection) a.setAttribute('aria-selected', 'true')
    a.innerHTML = `
      <span>${escapeHtml(item.kind || 'doc')}</span>
      <span style="flex:1;width:auto;">
        <strong>${escapeHtml(item.title)}</strong>
        <em>${escapeHtml(item.section || item.summary || '')}</em>
      </span>
    `
    a.addEventListener('mousemove', () => {
      searchSelection = i
      updateSelection()
    })
    searchList.append(a)
  })
}

function updateSelection() {
  const results = searchList?.querySelectorAll('.search-result')
  if (!results) return
  results.forEach((r, i) => {
    if (i === searchSelection) {
      r.setAttribute('aria-selected', 'true')
      r.scrollIntoView({ block: 'nearest' })
    } else {
      r.removeAttribute('aria-selected')
    }
  })
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

async function runSearch() {
  if (!searchInput) return
  const items = await loadSearchIndex()
  searchSelection = 0
  renderSearch(rankSearch(items, searchInput.value))
}

if (searchInput) {
  searchInput.addEventListener('input', runSearch)
  searchInput.addEventListener('keydown', (e) => {
    const results = searchList?.querySelectorAll('.search-result')
    if (!results || !results.length) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      searchSelection = (searchSelection + 1) % results.length
      updateSelection()
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      searchSelection = (searchSelection - 1 + results.length) % results.length
      updateSelection()
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const sel = results[searchSelection]
      if (sel) location.assign(sel.getAttribute('href'))
    }
  })
}

// Preload index eagerly so the first keystroke renders immediately.
// On slower connections we still fall back to fetching on demand.
if ('requestIdleCallback' in window) {
  requestIdleCallback(() => loadSearchIndex().then(() => runSearch()), { timeout: 1500 })
} else {
  setTimeout(() => loadSearchIndex().then(() => runSearch()), 200)
}

// ─────────── keyboard shortcuts ───────────
const pageInfo = window.__A7_PAGE__ || { slug: 'index', prev: null, next: null }

const chordToast = document.querySelector('.chord-toast')
const chordKey = chordToast?.querySelector('[data-chord-key]')

let chord = null
let chordTimer = null
function setChord(k) {
  chord = k
  document.body.classList.toggle('chord-active', !!k)
  if (chordKey) chordKey.textContent = k ?? ''
  clearTimeout(chordTimer)
  if (k) chordTimer = setTimeout(() => setChord(null), 1500)
}

const NAV_KEYS = {
  h: '',
  s: 'start/',
  l: 'language/',
  b: 'stdlib/',
  c: 'compiler/',
  t: 'status/',
  r: 'release/',
  a: 'agent-usage/',
  p: 'project/',
}

const isEditable = (el) => {
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable
}

document.addEventListener('keydown', (e) => {
  // Cmd/Ctrl+K — open search even when typing elsewhere (but not inside the search input itself)
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    openModal('search')
    return
  }

  if (e.key === 'Escape') {
    if (searchInput && document.activeElement === searchInput && searchInput.value) {
      searchInput.value = ''
      runSearch()
      return
    }
    closeAllModals()
    setChord(null)
    return
  }

  if (e.metaKey || e.ctrlKey || e.altKey) return
  if (isEditable(e.target)) return

  const k = e.key.toLowerCase()

  if (chord === 'g') {
    e.preventDefault()
    const dest = NAV_KEYS[k]
    if (dest !== undefined) {
      location.assign(base + '/' + dest)
    } else if (k === 'g') {
      window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' })
    }
    setChord(null)
    return
  }

  if (k === 'g') {
    e.preventDefault()
    setChord('g')
    return
  }

  if (e.key === '?' || (e.shiftKey && k === '/')) {
    e.preventDefault()
    openModal('shortcuts')
    return
  }

  if (k === '/') {
    e.preventDefault()
    openModal('search')
    return
  }

  if (k === '[' && pageInfo.prev) {
    e.preventDefault()
    location.assign(pageInfo.prev.href)
    return
  }
  if (k === ']' && pageInfo.next) {
    e.preventDefault()
    location.assign(pageInfo.next.href)
    return
  }

  if (k === 't') {
    e.preventDefault()
    window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' })
    return
  }

  if (k === 'g') {
    setChord('g')
  }
})

// ─────────── terminal tabs ───────────
document.querySelectorAll('[data-tabs]').forEach((root) => {
  const tabs = root.querySelectorAll('[data-tab]')
  const panels = root.querySelectorAll('[data-tab-panel]')
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const name = tab.dataset.tab
      tabs.forEach((t) => t.setAttribute('aria-selected', t === tab ? 'true' : 'false'))
      panels.forEach((p) => {
        const match = p.dataset.tabPanel === name
        if (match) p.removeAttribute('hidden')
        else p.setAttribute('hidden', '')
      })
    })
  })
})

// ─────────── topbar shadow on scroll ───────────
const topbar = document.querySelector('.topbar')
if (topbar) {
  let scrolled = false
  const onScroll = () => {
    const now = scrollY > 8
    if (now !== scrolled) {
      scrolled = now
      topbar.style.boxShadow = now ? '0 8px 30px rgba(0,0,0,.35)' : ''
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
}
