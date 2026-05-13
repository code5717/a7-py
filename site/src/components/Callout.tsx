import type { ReactNode } from 'react'
import styles from './Callout.module.css'

export type CalloutKind = 'note' | 'warn' | 'danger' | 'tip' | 'agent'

const KIND_GLYPH: Record<CalloutKind, string> = {
  note: '[?]',
  tip: '[+]',
  warn: '[!]',
  danger: '[x]',
  agent: '[agent]',
}

const KIND_LABEL: Record<CalloutKind, string> = {
  note: 'NOTE',
  tip: 'TIP',
  warn: 'WARN',
  danger: 'DANGER',
  agent: 'AGENT NOTE',
}

export default function Callout({ kind = 'note', label, children }: {
  kind?: CalloutKind
  label?: string
  children: ReactNode
}) {
  return (
    <aside className={`${styles.callout} ${styles[kind]}`} role="note">
      <div className={styles.rail} aria-hidden />
      <div className={styles.body}>
        <div className={styles.label}>
          <span className={styles.glyph}>{KIND_GLYPH[kind]}</span>
          <span>{label ?? KIND_LABEL[kind]}</span>
        </div>
        <div className={styles.content}>{children}</div>
      </div>
    </aside>
  )
}
