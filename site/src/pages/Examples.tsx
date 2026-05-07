import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import CodeModal from '../components/CodeModal'
import PageHeader from '../components/PageHeader'
import SectionPanel from '../components/SectionPanel'
import { EXAMPLES, type Example, exampleModules } from '../content/examples'

const CATEGORIES = ['All', ...new Set(EXAMPLES.map((example) => example.category))]

export default function Examples() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [category, setCategory] = useState('All')
  const [query, setQuery] = useState('')
  const [modal, setModal] = useState<{ example: Example; code: string } | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const selectedExampleId = searchParams.get('example')

  const filtered = useMemo(
    () =>
      EXAMPLES.filter((example) => {
        const matchesCategory = category === 'All' || example.category === category
        const search = query.trim().toLowerCase()
        const matchesQuery =
          search.length === 0 ||
          example.file.toLowerCase().includes(search) ||
          example.title.toLowerCase().includes(search) ||
          example.desc.toLowerCase().includes(search)

        return matchesCategory && matchesQuery
      }),
    [category, query],
  )

  const loadExample = useCallback((example: Example) => {
    setLoadError(null)

    const key = `../../../examples/${example.file}`
    const loader = exampleModules[key]
    if (!loader) {
      setLoadError(`Source for ${example.file} is not available in this build.`)
      return
    }
    loader()
      .then((code) => {
        setModal({ example, code })
      })
      .catch(() => {
        setLoadError(`Could not load ${example.file}.`)
      })
  }, [])

  const openExample = useCallback((example: Example) => {
    setSearchParams({ example: example.id })
  }, [setSearchParams])

  const closeExample = useCallback(() => {
    setModal(null)
    setSearchParams({})
  }, [setSearchParams])

  useEffect(() => {
    if (!selectedExampleId) {
      return
    }

    const example = EXAMPLES.find((item) => item.id === selectedExampleId)
    if (example) {
      void Promise.resolve().then(() => loadExample(example))
    } else {
      void Promise.resolve().then(() => setLoadError(`Example ${selectedExampleId} was not found.`))
    }
  }, [loadExample, selectedExampleId])

  return (
    <div className="page">
      <PageHeader
        eyebrow="Learn by Running"
        title="Examples"
        summary={`${EXAMPLES.length} programs to inspect and run.`}
      />

      <SectionPanel title="Browse" subtitle="Filter by category or search.">
        <div className="filters stack-2">
          <input
            className="doc-input"
            placeholder="Search examples..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Search examples"
          />

          <div className="chip-row">
            {CATEGORIES.map((item) => (
              <button
                key={item}
                type="button"
                className={`doc-chip-button ${item === category ? 'active' : ''}`}
                onClick={() => setCategory(item)}
              >
                {item}
              </button>
            ))}
          </div>

          <p className="text-tertiary">
            Showing <strong>{filtered.length}</strong> of <strong>{EXAMPLES.length}</strong> examples.
          </p>

          {loadError && (
            <p className="doc-callout warning m-0" role="status" aria-live="polite">
              {loadError}
            </p>
          )}
        </div>
      </SectionPanel>

      <section className="link-card-grid">
        {filtered.map((example) => (
          <button
            type="button"
            key={example.id}
            className="example-card"
            onClick={() => openExample(example)}
            aria-label={`Open ${example.file}: ${example.title}`}
          >
            <div className="example-card-top">
              <code className="doc-inline-code" title={example.file}>{example.file}</code>
              <span className="doc-chip">{example.category}</span>
            </div>
            <h2 className="example-card-title">{example.title}</h2>
            <p className="example-card-desc">{example.desc}</p>
          </button>
        ))}
      </section>

      {modal && selectedExampleId === modal.example.id && (
        <CodeModal
          title={modal.example.file}
          code={modal.code}
          onClose={closeExample}
          runCommand={`uv run python main.py examples/${modal.example.file}`}
          lineCount={modal.code.split(/\r?\n/).length}
        />
      )}
    </div>
  )
}
