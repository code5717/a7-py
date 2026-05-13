import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import Shell from './components/Shell'
import Home from './pages/Home'
import DocPage from './pages/DocPage'
import NotFound from './pages/NotFound'
import { MANIFEST, LEGACY_REDIRECTS, EXTERNAL_REDIRECTS } from './content/manifest'

function ExternalRedirect({ to }: { to: string }) {
  useEffect(() => {
    window.location.replace(to)
  }, [to])
  return null
}

function ScrollManager() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    if (hash) {
      const id = decodeURIComponent(hash.slice(1))
      const el = document.getElementById(id)
      if (el) {
        el.scrollIntoView({ behavior: 'auto', block: 'start' })
        return
      }
    }
    window.scrollTo(0, 0)
  }, [pathname, hash])
  return null
}

export default function App() {
  return (
    <Shell>
      <ScrollManager />
      <Routes>
        <Route path="/" element={<Home />} />

        {MANIFEST.map((entry) => (
          <Route key={entry.path} path={entry.path} element={<DocPage path={entry.path} />} />
        ))}

        {LEGACY_REDIRECTS.map(({ from, to }) => (
          <Route key={from} path={from} element={<Navigate to={to} replace />} />
        ))}

        {EXTERNAL_REDIRECTS.map(({ from, to }) => (
          <Route key={from} path={from} element={<ExternalRedirect to={to} />} />
        ))}

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Shell>
  )
}
