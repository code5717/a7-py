import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'
import { NAV_GROUPS } from '../content/navigation'

export default function NotFound() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="404"
        title="Page not found"
        summary="This route does not exist in the A7 docs."
        actions={
          <Link className="primary-action" to="/">
            Back to docs <span aria-hidden="true">→</span>
          </Link>
        }
      />

      <SectionPanel title="Try these instead" subtitle="All major docs groups are available below.">
        <div className="link-card-grid">
          {NAV_GROUPS.flatMap((group) => group.items).map((item) => (
            <Link key={item.to} className="link-card" to={item.to}>
              <span className="link-card-title">{item.label}</span>
              <span className="link-card-desc">{item.note}</span>
            </Link>
          ))}
        </div>
      </SectionPanel>
    </div>
  )
}
