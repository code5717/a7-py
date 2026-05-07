import { NavLink } from 'react-router-dom'
import { NAV_GROUPS } from '../content/navigation'

export default function Sidebar({ onClose }: { onClose: () => void }) {
  return (
    <nav className="nav-root" aria-label="Documentation navigation">
      <div className="nav-head">
        <NavLink to="/" className="nav-brand" onClick={onClose}>
          <span className="nav-brand-mark">A7</span>
          <span className="nav-brand-text">Docs</span>
        </NavLink>
        <button type="button" onClick={onClose} className="icon-button sidebar-close-btn" aria-label="Close navigation">
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="nav-scroll">
        {NAV_GROUPS.map((group) => (
          <section key={group.label} className="nav-group">
            <h2 className="nav-group-title">{group.label}</h2>
            <ul className="stack-1">
              {group.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/'}
                    onClick={onClose}
                    className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                  >
                    <span className="nav-link-title">{item.label}</span>
                    <span className="nav-link-note">{item.note}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <div className="nav-foot">
        <a
          href="https://github.com/code5717/a7-py"
          target="_blank"
          rel="noopener noreferrer"
          className="nav-foot-link"
        >
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
          </svg>
          GitHub repository
        </a>
      </div>
    </nav>
  )
}
