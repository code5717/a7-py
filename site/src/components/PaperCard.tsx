import type { ReactNode } from 'react'
import styles from './PaperCard.module.css'

interface Props {
  /** Mono caption shown in the top-left hairline tab, e.g. "docs/language.md" */
  filePath: string
  /** Optional version/status label shown in the top-right tab */
  rightLabel?: string
  children: ReactNode
}

/**
 * Editorial reading card — warm cream paper inside the industrial chrome.
 * The 1px top hairline + file-path tab is the bridge between the two worlds.
 */
export default function PaperCard({ filePath, rightLabel, children }: Props) {
  return (
    <article className={styles.card}>
      <header className={styles.tab}>
        <span className={styles.path}>{filePath}</span>
        {rightLabel && <span className={styles.right}>{rightLabel}</span>}
      </header>
      <div className={styles.body}>{children}</div>
    </article>
  )
}
