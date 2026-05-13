import styles from './StatusChip.module.css'

export type ChipTone = 'neutral' | 'ok' | 'todo' | 'ni' | 'accent'

interface Props {
  tone?: ChipTone
  children: string
}

const TONE_CLASS: Record<ChipTone, string> = {
  neutral: styles.neutral,
  ok: styles.ok,
  todo: styles.todo,
  ni: styles.ni,
  accent: styles.accent,
}

export default function StatusChip({ tone = 'neutral', children }: Props) {
  return <span className={`${styles.chip} ${TONE_CLASS[tone]}`}>[ {children} ]</span>
}
