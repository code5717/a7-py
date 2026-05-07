import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

interface SectionPanelProps {
  title?: string
  subtitle?: string
  children: ReactNode
  className?: string
  id?: string
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

export default function SectionPanel({ title, subtitle, children, className = '', id }: SectionPanelProps) {
  const { pathname } = useLocation()
  const sectionId = id ?? (title ? slugify(title) : undefined)

  return (
    <section id={sectionId} className={`section-panel ${className}`.trim()} data-reveal>
      {title && (
        <h2 className="section-title">
          <span>{title}</span>
          {sectionId && (
            <Link className="section-anchor-link" to={`${pathname}#${sectionId}`} aria-label={`Link to ${title}`}>
              #
            </Link>
          )}
        </h2>
      )}
      {subtitle && <p className="section-subtitle">{subtitle}</p>}
      {children}
    </section>
  )
}
