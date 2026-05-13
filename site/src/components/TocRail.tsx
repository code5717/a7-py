import { useEffect, useState } from 'react'
import styles from './TocRail.module.css'

export interface TocHeading {
  level: 1 | 2 | 3
  id: string
  text: string
}

interface Props {
  headings: TocHeading[]
}

export default function TocRail({ headings }: Props) {
  const items = headings.filter((h) => h.level === 2 || h.level === 3)
  const [activeId, setActiveId] = useState<string | null>(items[0]?.id ?? null)

  useEffect(() => {
    if (items.length === 0) return
    const elements = items
      .map((h) => document.getElementById(h.id))
      .filter((el): el is HTMLElement => Boolean(el))
    if (elements.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.target.getBoundingClientRect().top - b.target.getBoundingClientRect().top)
        if (visible.length > 0) {
          setActiveId(visible[0].target.id)
        }
      },
      { rootMargin: '-80px 0px -65% 0px', threshold: [0, 1] },
    )
    elements.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [items])

  if (items.length === 0) return null

  return (
    <nav className={styles.rail} aria-label="On this page">
      <h2 className={styles.title}>[ ON THIS PAGE ]</h2>
      <ul className={styles.list}>
        {items.map((h) => (
          <li key={h.id} className={h.level === 3 ? styles.lvl3 : styles.lvl2}>
            <a
              href={`#${h.id}`}
              className={`${styles.link} ${activeId === h.id ? styles.active : ''}`}
            >
              {activeId === h.id && <span className={styles.dot} aria-hidden />}
              <span>{h.text}</span>
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
