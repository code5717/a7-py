import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Start from './pages/Start'
import Language from './pages/Language'
import Cli from './pages/Cli'
import Pipeline from './pages/Pipeline'
import Examples from './pages/Examples'
import Stdlib from './pages/Stdlib'
import Internals from './pages/Internals'
import Testing from './pages/Testing'
import Status from './pages/Status'
import Contributing from './pages/Contributing'
import Changelog from './pages/Changelog'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="start" element={<Start />} />
        <Route path="language" element={<Language />} />
        <Route path="cli" element={<Cli />} />
        <Route path="pipeline" element={<Pipeline />} />
        <Route path="examples" element={<Examples />} />
        <Route path="stdlib" element={<Stdlib />} />
        <Route path="internals" element={<Internals />} />
        <Route path="testing" element={<Testing />} />
        <Route path="status" element={<Status />} />
        <Route path="contributing" element={<Contributing />} />
        <Route path="changelog" element={<Changelog />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
