import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Start from './pages/Start'
import Language from './pages/Language'
import Examples from './pages/Examples'
import Internals from './pages/Internals'
import Status from './pages/Status'
import Contributing from './pages/Contributing'
import Changelog from './pages/Changelog'
import NotFound from './pages/NotFound'
import CurlDocsPage from './pages/CurlDocsPage'

const CLI_ANCHORS = { modes: 'modes', flags: 'flags' }
const PIPELINE_ANCHORS = { 'pipeline-stages': 'pipeline', 'backend-notes': 'backend-notes' }
const STDLIB_ANCHORS = { io: 'io', math: 'math', 'stub-modules': 'stub-modules' }
const TESTING_ANCHORS = { scripts: 'scripts' }

function scrollToAnchor(anchor: string) {
  const element = document.getElementById(anchor)

  if (!element) {
    return
  }

  const stickyOffset = 86
  const top = Math.max(0, element.getBoundingClientRect().top + window.scrollY - stickyOffset)

  window.scrollTo({ top, left: 0 })
}

function LegacySectionAlias({
  anchor,
  anchorMap = {},
  children,
}: {
  anchor: string
  anchorMap?: Record<string, string>
  children: ReactNode
}) {
  const { hash } = useLocation()

  useEffect(() => {
    const targetAnchor = anchorMap[hash.slice(1)] ?? anchor

    window.setTimeout(() => scrollToAnchor(targetAnchor), 0)
    window.setTimeout(() => scrollToAnchor(targetAnchor), 80)
    window.setTimeout(() => scrollToAnchor(targetAnchor), 240)
    window.setTimeout(() => scrollToAnchor(targetAnchor), 750)
    window.setTimeout(() => scrollToAnchor(targetAnchor), 1500)
  }, [anchor, anchorMap, hash])

  return children
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="start" element={<Start />} />
        <Route path="installation" element={<CurlDocsPage />} />
        <Route path="why" element={<CurlDocsPage />} />
        <Route path="faq" element={<CurlDocsPage />} />
        <Route path="language" element={<Language />} />
        <Route path="features" element={<CurlDocsPage />} />
        <Route path="agent-usage" element={<CurlDocsPage />} />
        <Route
          path="cli"
          element={<LegacySectionAlias anchor="cli" anchorMap={CLI_ANCHORS}><Start /></LegacySectionAlias>}
        />
        <Route path="api" element={<CurlDocsPage />} />
        <Route path="plugins" element={<CurlDocsPage />} />
        <Route path="plugins/:plugin" element={<CurlDocsPage />} />
        <Route path="skills" element={<CurlDocsPage />} />
        <Route path="llms" element={<CurlDocsPage />} />
        <Route path="llms-full" element={<CurlDocsPage />} />
        <Route
          path="pipeline"
          element={<LegacySectionAlias anchor="pipeline" anchorMap={PIPELINE_ANCHORS}><Internals /></LegacySectionAlias>}
        />
        <Route path="examples" element={<Examples />} />
        <Route
          path="stdlib"
          element={<LegacySectionAlias anchor="standard-library" anchorMap={STDLIB_ANCHORS}><Language /></LegacySectionAlias>}
        />
        <Route path="internals" element={<Internals />} />
        <Route
          path="testing"
          element={<LegacySectionAlias anchor="testing" anchorMap={TESTING_ANCHORS}><Internals /></LegacySectionAlias>}
        />
        <Route path="status" element={<Status />} />
        <Route path="contributing" element={<Contributing />} />
        <Route path="develop" element={<CurlDocsPage />} />
        <Route path="deploy" element={<CurlDocsPage />} />
        <Route path="kitchen-sink" element={<CurlDocsPage />} />
        <Route path="changelog" element={<Changelog />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
