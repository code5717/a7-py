import { Link } from 'react-router-dom'
import type { ManifestEntry } from '../content/manifest'
import styles from './PageFooter.module.css'

interface Props {
  prev?: ManifestEntry
  next?: ManifestEntry
  sourceUrl: string
  editUrl: string
}

export default function PageFooter({ prev, next, sourceUrl, editUrl }: Props) {
  return (
    <footer className={styles.footer}>
      <div className={styles.nav}>
        {prev ? (
          <Link to={prev.path} className={`${styles.navLink} ${styles.prev}`}>
            <span className={styles.dir}>← PREV</span>
            <span className={styles.title}>{prev.title}</span>
          </Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link to={next.path} className={`${styles.navLink} ${styles.next}`}>
            <span className={styles.dir}>NEXT →</span>
            <span className={styles.title}>{next.title}</span>
          </Link>
        ) : (
          <span />
        )}
      </div>
      <div className={styles.meta}>
        <a className={styles.metaLink} href={sourceUrl} target="_blank" rel="noopener">
          [ view as markdown ]
        </a>
        <a className={styles.metaLink} href={editUrl} target="_blank" rel="noopener">
          [ edit on github ]
        </a>
      </div>
    </footer>
  )
}
