import { NavLink, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { ENTRIES_BY_SECTION } from '../content/manifest'
import styles from './Sidebar.module.css'

interface Props {
  open: boolean
  onClose: () => void
}

export default function Sidebar({ open, onClose }: Props) {
  const { pathname } = useLocation()

  useEffect(() => {
    onClose()
    // intentionally only react to path change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname])

  return (
    <>
      <aside className={`${styles.sidebar} ${open ? styles.open : ''}`} aria-label="Documentation navigation">
        <nav className={styles.nav}>
          <NavLink to="/docs" className={({ isActive }) => `${styles.overview} ${isActive ? styles.active : ''}`}>
            <span className={styles.idx}>00</span>
            <span>Overview</span>
          </NavLink>
          {ENTRIES_BY_SECTION
            .filter((sec) => sec.entries.length > 0)
            .map((sec) => (
              <section key={sec.key} className={styles.section}>
                <header className={styles.sectionHeader}>
                  <span className={styles.sectionIdx}>{sec.index}</span>
                  <span className={styles.sectionLabel}>[ {sec.label} ]</span>
                </header>
                <ul className={styles.list}>
                  {sec.entries.map((entry) => (
                    <li key={entry.path}>
                      <NavLink
                        to={entry.path}
                        className={({ isActive }) =>
                          `${styles.item} ${isActive ? styles.active : ''}`
                        }
                      >
                        <span className={styles.rail} aria-hidden />
                        <span className={styles.itemLabel}>{entry.navLabel ?? entry.title}</span>
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
        </nav>
      </aside>
      {open && <div className={styles.scrim} onClick={onClose} aria-hidden />}
    </>
  )
}
