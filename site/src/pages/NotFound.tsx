import { Link, useLocation } from 'react-router-dom'
import PaperCard from '../components/PaperCard'
import styles from './NotFound.module.css'

export default function NotFound() {
  const { pathname } = useLocation()
  return (
    <div className={styles.wrap}>
      <PaperCard filePath="error/404" rightLabel="EXIT 1">
        <div className={styles.eyebrow}>SIGNAL / 404</div>
        <h1 className={styles.heading}>Route not resolved.</h1>
        <p className={styles.body}>
          The path <code>{pathname}</code> doesn't map to any A7 document. Try the{' '}
          <Link to="/docs">overview hub</Link> or the{' '}
          <Link to="/learn/start">getting started guide</Link>.
        </p>
      </PaperCard>
    </div>
  )
}
