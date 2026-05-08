import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import { useTheme } from '../hooks/useTheme'
import { EXAMPLES } from '../content/examples'
import { NAV_GROUPS, PAGE_META, PRIMARY_NAV, SECTION_SEARCH_ITEMS } from '../content/navigation'
import { lockBodyScroll } from '../utils/scrollLock'

const SEARCH_ITEMS = [
  ...NAV_GROUPS.flatMap((group) =>
    group.items.map((item) => ({
      to: item.to,
      label: item.label,
      group: group.label,
      detail: item.note,
    })),
  ),
  ...SECTION_SEARCH_ITEMS,
  ...EXAMPLES.map((example) => ({
    to: `/examples?example=${example.id}`,
    label: example.title,
    group: 'Example',
    detail: `${example.file} · ${example.desc}`,
  })),
]

function getRouteAnchor(routeHash: string) {
  if (routeHash) {
    return routeHash.slice(1)
  }

  const rawHash = window.location.hash
  const anchorIndex = rawHash.indexOf('#', 1)
  const routeAliasAnchors: Record<string, string> = {
    '#/cli': 'cli',
    '#/pipeline': 'pipeline',
    '#/stdlib': 'standard-library',
    '#/testing': 'testing',
  }

  return anchorIndex >= 0 ? rawHash.slice(anchorIndex + 1) : (routeAliasAnchors[rawHash] ?? '')
}

function scrollAnchorIntoView(anchor: string) {
  const element = document.getElementById(anchor)

  if (!element) {
    return
  }

  const stickyOffset = 86
  const top = Math.max(0, element.getBoundingClientRect().top + window.scrollY - stickyOffset)

  window.scrollTo({ top, left: 0 })
}

function scrollToRouteAnchor(routeHash: string) {
  const anchor = getRouteAnchor(routeHash)

  if (!anchor) {
    window.scrollTo({ top: 0, left: 0 })
    return
  }

  window.setTimeout(() => scrollAnchorIntoView(anchor), 0)
  window.setTimeout(() => scrollAnchorIntoView(anchor), 80)
  window.setTimeout(() => scrollAnchorIntoView(anchor), 240)
  window.setTimeout(() => scrollAnchorIntoView(anchor), 750)
  window.setTimeout(() => scrollAnchorIntoView(anchor), 1500)
}

function publicDocsPath(path: string) {
  return `${import.meta.env.BASE_URL.replace(/\/$/, '')}${path}`
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const searchInputRef = useRef<HTMLInputElement>(null)
  const searchPanelRef = useRef<HTMLElement>(null)
  const sidebarRef = useRef<HTMLElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const previousSearchFocusRef = useRef<HTMLElement | null>(null)
  const previousSidebarFocusRef = useRef<HTMLElement | null>(null)
  const { pathname, hash } = useLocation()
  const { preference, resolvedTheme, darkExtensionActive, cycleTheme } = useTheme()
  const pageMeta = PAGE_META[pathname] ?? PAGE_META['/']
  const markdownHref = pageMeta.markdownPath ? publicDocsPath(pageMeta.markdownPath) : publicDocsPath('/docs/index.md')

  const searchResults = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()

    if (!query) {
      return SEARCH_ITEMS.slice(0, 8)
    }

    return SEARCH_ITEMS.filter((item) =>
      `${item.label} ${item.group} ${item.detail}`.toLowerCase().includes(query),
    ).slice(0, 10)
  }, [searchQuery])

  useEffect(() => {
    document.title = `${pageMeta.title} | A7`

    const description = document.querySelector<HTMLMetaElement>('meta[name="description"]')
    if (description) {
      description.content = pageMeta.description
    }

    let alternate = document.querySelector<HTMLLinkElement>('link[data-a7-markdown-alternate]')
    if (!alternate) {
      alternate = document.createElement('link')
      alternate.dataset.a7MarkdownAlternate = 'true'
      alternate.rel = 'alternate'
      alternate.type = 'text/markdown'
      document.head.appendChild(alternate)
    }
    alternate.href = new URL(markdownHref, window.location.origin).toString()
  }, [markdownHref, pageMeta.description, pageMeta.title])

  useEffect(() => {
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual'
    }

    scrollToRouteAnchor(hash)
  }, [hash, pathname])

  useEffect(() => {
    const handleHashChange = () => scrollToRouteAnchor('')
    let lastHash = window.location.hash
    let correctUntil = 0

    const hashWatcher = window.setInterval(() => {
      if (window.location.hash !== lastHash) {
        lastHash = window.location.hash
        correctUntil = Date.now() + 2500
      }

      if (Date.now() > correctUntil) {
        return
      }

      const anchor = getRouteAnchor('')

      if (anchor) {
        scrollAnchorIntoView(anchor)
      }
    }, 100)

    window.addEventListener('hashchange', handleHashChange)
    return () => {
      window.clearInterval(hashWatcher)
      window.removeEventListener('hashchange', handleHashChange)
    }
  }, [])

  useEffect(() => {
    if (!sidebarOpen) {
      return
    }

    const releaseScrollLock = lockBodyScroll()
    previousSidebarFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    const fallbackFocus = menuButtonRef.current
    window.setTimeout(() => {
      const firstFocusable = sidebarRef.current?.querySelector<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      firstFocusable?.focus()
    }, 0)

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSidebarOpen(false)
        return
      }

      if (event.key !== 'Tab' || !sidebarRef.current) {
        return
      }

      const focusables = sidebarRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )

      if (focusables.length === 0) {
        event.preventDefault()
        return
      }

      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const active = document.activeElement

      if (event.shiftKey && active === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      releaseScrollLock()
      document.removeEventListener('keydown', handleKeyDown)
      ;(previousSidebarFocusRef.current ?? fallbackFocus)?.focus()
    }
  }, [sidebarOpen])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target
      const isTypingTarget =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        (target instanceof HTMLElement && target.isContentEditable)

      if (
        (event.key === '/' || event.code === 'Slash') &&
        !isTypingTarget &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey
      ) {
        event.preventDefault()
        setSearchOpen(true)
        return
      }

      if (event.key === 'Escape') {
        setSearchOpen(false)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  useEffect(() => {
    if (!searchOpen) {
      return
    }

    const releaseScrollLock = lockBodyScroll()
    previousSearchFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    window.setTimeout(() => searchInputRef.current?.focus(), 0)

    return () => {
      releaseScrollLock()
      previousSearchFocusRef.current?.focus()
    }
  }, [searchOpen])

  useEffect(() => {
    if (!searchOpen) {
      return
    }

    const handleSearchKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !searchPanelRef.current) {
        return
      }

      const focusables = searchPanelRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )

      if (focusables.length === 0) {
        event.preventDefault()
        return
      }

      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const active = document.activeElement

      if (event.shiftKey && active === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleSearchKeyDown)
    return () => document.removeEventListener('keydown', handleSearchKeyDown)
  }, [searchOpen])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      {sidebarOpen && <div className="mobile-overlay" onClick={() => setSidebarOpen(false)} />}

      <aside
        ref={sidebarRef}
        className={`app-sidebar${sidebarOpen ? ' open' : ''}`}
        aria-label="Mobile documentation navigation"
        aria-modal={sidebarOpen ? 'true' : undefined}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </aside>

      <div className="app-main">
        <header className="site-header">
          <div className="site-header-inner">
            <NavLink to="/" className="site-brand">
              <span className="site-brand-mark">A7</span>
            </NavLink>

            <nav className="site-nav" aria-label="Primary">
              {PRIMARY_NAV.map((item) => (
                item.kind === 'route' ? (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) => `site-nav-link${isActive ? ' active' : ''}`}
                  >
                    {item.label}
                  </NavLink>
                ) : (
                  <a
                    key={item.href}
                    className="site-nav-link"
                    href={item.href}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {item.label}
                  </a>
                )
              ))}
            </nav>

            <div className="site-header-tools">
              <a className="markdown-link" href={markdownHref}>
                Markdown
              </a>

              <button
                type="button"
                className="site-search"
                aria-label="Search documentation"
                onClick={() => setSearchOpen(true)}
              >
                <span className="site-search-label">
                  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                    <circle cx="11" cy="11" r="6.5" />
                    <path strokeLinecap="round" d="M16 16l4 4" />
                  </svg>
                  Search docs
                </span>
                <span className="site-search-kbd">/</span>
              </button>

              <button
                type="button"
                onClick={cycleTheme}
                className="theme-toggle"
                aria-label={`Theme: ${preference}. Click to cycle theme mode.`}
                title={darkExtensionActive ? 'Dark extension detected. Site theme will avoid double-dark styling.' : undefined}
              >
                <span className="theme-toggle-icon" aria-hidden="true">
                  {resolvedTheme === 'dark' ? (
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
                    </svg>
                  ) : preference === 'system' ? (
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                      <rect x="3.5" y="4.5" width="17" height="12" rx="2" />
                      <path strokeLinecap="round" d="M8 19.5h8M12 16.5v3" />
                    </svg>
                  ) : (
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                      <circle cx="12" cy="12" r="4.5" />
                      <path strokeLinecap="round" d="M12 2.5v2.5M12 19v2.5M21.5 12H19M5 12H2.5M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8M18.7 18.7l-1.8-1.8M7.1 7.1L5.3 5.3" />
                    </svg>
                  )}
                </span>
                <span className="theme-toggle-label">{preference}</span>
                {darkExtensionActive ? <span className="theme-toggle-badge">ext</span> : null}
              </button>

              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                ref={menuButtonRef}
                className="site-menu-button"
                aria-label="Open site navigation"
              >
                <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M4 12h16M4 17h16" />
                </svg>
                <span className="site-menu-button-text">Menu</span>
              </button>
            </div>
          </div>
        </header>

        <main id="main-content" className="app-main-inner" tabIndex={-1}>
          <Outlet />
        </main>

        <footer className="app-footer">
          <div className="app-footer-inner site-footer-grid">
            <div className="site-footer-brand">
              <div className="site-footer-title">A7</div>
              <div>The A7 Project</div>
              <div>MIT License</div>
            </div>

            <div className="site-footer-column">
              <h3>Language</h3>
              <div className="site-footer-links">
                <Link to="/start">Getting Started</Link>
                <Link to="/language">Language Reference</Link>
                <Link to="/examples">Examples</Link>
                <Link to="/cli">CLI</Link>
              </div>
            </div>

            <div className="site-footer-column">
              <h3>Project</h3>
              <div className="site-footer-links">
                <Link to="/internals">Compiler</Link>
                <Link to="/status">Status</Link>
                <Link to="/release">Release</Link>
                <Link to="/contributing">Contributing</Link>
              </div>
            </div>

            <div className="site-footer-column">
              <h3>Resources</h3>
              <div className="site-footer-links">
                <a href={publicDocsPath('/llms.txt')}>llms.txt</a>
                <a href={publicDocsPath('/llms-full.txt')}>llms-full.txt</a>
                <a href={publicDocsPath('/docs/index.md')}>Markdown docs</a>
                <a href={markdownHref}>This page as Markdown</a>
              </div>
            </div>
          </div>
        </footer>
      </div>

      {searchOpen ? (
        <div className="search-overlay" role="presentation" onMouseDown={() => setSearchOpen(false)}>
          <section
            ref={searchPanelRef}
            className="search-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="search-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="search-panel-head">
              <div>
                <p className="search-panel-kicker">Docs search</p>
                <h2 id="search-title" className="search-panel-title">Find a page or example</h2>
              </div>
              <button type="button" className="icon-button" onClick={() => setSearchOpen(false)} aria-label="Close search">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <label className="search-input-wrap">
              <span className="search-input-icon" aria-hidden="true">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <circle cx="11" cy="11" r="6.5" />
                  <path strokeLinecap="round" d="M16 16l4 4" />
                </svg>
              </span>
              <input
                type="search"
                ref={searchInputRef}
                className="search-input"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search docs, plugins, CLI..."
                aria-label="Search documentation"
              />
            </label>
            <div className="search-result-status" role="status" aria-live="polite">
              {searchResults.length} {searchResults.length === 1 ? 'result' : 'results'}
              {searchQuery.trim() ? ` for "${searchQuery.trim()}"` : ''}
            </div>

            <div className="search-results" aria-label="Search results">
              {searchResults.length > 0 ? (
                <ul className="search-result-list">
                  {searchResults.map((item) => (
                    <li key={`${item.group}-${item.label}`}>
                      <NavLink
                        to={item.to}
                        className="search-result"
                        onClick={() => setSearchOpen(false)}
                      >
                        <span className="search-result-group">{item.group}</span>
                        <span className="search-result-label">{item.label}</span>
                        <span className="search-result-detail">{item.detail}</span>
                      </NavLink>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="search-empty" role="status">
                  <span>No matching docs.</span>
                  <span>Try language, CLI, pipeline, testing, or an example name.</span>
                </div>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}
