import { Link, useLocation } from 'react-router-dom'
import { ENTRIES_BY_PATH } from '../content/manifest'
import styles from './Header.module.css'

interface Props {
  theme: 'light' | 'dark'
  onToggleTheme: () => void
  onOpenSearch: () => void
  onToggleSidebar: () => void
  sidebarOpen: boolean
}

export default function Header({ theme, onToggleTheme, onOpenSearch, onToggleSidebar, sidebarOpen }: Props) {
  const { pathname } = useLocation()
  const entry = ENTRIES_BY_PATH.get(pathname)
  const breadcrumb = entry ? entry.eyebrow : pathname === '/' ? 'HOME' : 'NOT FOUND'

  return (
    <header className={styles.header}>
      <button
        type="button"
        className={styles.menuBtn}
        aria-label="Toggle sidebar"
        aria-expanded={sidebarOpen}
        onClick={onToggleSidebar}
      >
        <span aria-hidden>[≡]</span>
      </button>
      <Link to="/" className={styles.wordmark} aria-label="A7 home">
        [A7//DOCS]
      </Link>
      <div className={styles.breadcrumb} aria-live="polite">
        {breadcrumb}
      </div>
      <div className={styles.right}>
        <button
          type="button"
          className={styles.searchBtn}
          onClick={onOpenSearch}
          aria-label="Open search"
        >
          <span className={styles.searchLabel}>SEARCH</span>
          <kbd className={styles.kbd}>⌘K</kbd>
        </button>
        <button
          type="button"
          className={styles.themeBtn}
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
        >
          [{theme === 'light' ? 'LIGHT' : 'DARK'}]
        </button>
        <a
          className={styles.ghLink}
          href="https://github.com/Airbus5717/a7-py"
          target="_blank"
          rel="noopener"
        >
          [GH]
        </a>
      </div>
    </header>
  )
}
