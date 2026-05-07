import { Fragment, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import CodeBlock from '../components/CodeBlock'
import SectionPanel from '../components/SectionPanel'

const FIBONACCI = `io :: import "std/io"

fib :: fn(n: usize) u64 {
    if n < 2 {
        ret cast(u64, n)
    }

    prev: u64 = 0
    acc: u64 = 1
    i: usize = 2

    while i <= n {
        next := prev + acc
        prev = acc
        acc = next
        i += 1
    }

    ret acc
}

main :: fn() {
    i: usize = 0
    while i < 10 {
        io.println("fib({}) = {}", i, fib(i))
        i += 1
    }
}`

const QUICKSTART = [
  { step: '01', label: 'Clone', command: 'git clone https://github.com/code5717/a7-py.git' },
  { step: '02', label: 'Enter', command: 'cd a7-py' },
  { step: '03', label: 'Install', command: 'uv sync' },
  { step: '04', label: 'Run', command: 'uv run python main.py examples/001_hello.a7' },
]

const FEATURES = [
  {
    title: 'Agent-ready markdown',
    copy: 'llms.txt, full context, and route-level docs.',
  },
  {
    title: 'CLI first',
    copy: 'Commands, exit codes, and JSON output are documented.',
  },
  {
    title: 'Verified examples',
    copy: 'Zig and C outputs are checked against golden output.',
  },
  {
    title: 'Honest status',
    copy: 'Known gaps stay visible for agents and maintainers.',
  },
]

const PIPELINE = [
  { title: 'Tokenize', copy: 'Source to tokens' },
  { title: 'Parse', copy: 'Tokens to AST' },
  { title: 'Validate', copy: 'Semantic checks' },
  { title: 'Preprocess', copy: 'Lowering annotations' },
  { title: 'Codegen', copy: 'Zig or C output' },
]

const HIGHLIGHTS = [
  { title: 'Introduction', copy: 'Start, install, why, FAQ.' },
  { title: 'Guide', copy: 'Features, agent usage, CLI, API.' },
  { title: 'Plugins', copy: 'Codex, Claude, Cursor, OpenCode.' },
  { title: 'LLM resources', copy: 'Skills, llms.txt, full context.' },
  { title: 'Contributing', copy: 'Develop, deploy, kitchen sink.' },
  { title: 'A7 reference', copy: 'Language, examples, compiler, status.' },
]

function publicDocsPath(path: string) {
  return `${import.meta.env.BASE_URL.replace(/\/$/, '')}${path}`
}

function QuickstartCommand({ step, label, command }: { step: string; label: string; command: string }) {
  const [copied, setCopied] = useState(false)
  const resetTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (resetTimerRef.current !== null) {
        window.clearTimeout(resetTimerRef.current)
      }
    }
  }, [])

  const copyCommand = async () => {
    if (!navigator.clipboard) {
      setCopied(false)
      return
    }

    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)

      if (resetTimerRef.current !== null) {
        window.clearTimeout(resetTimerRef.current)
      }

      resetTimerRef.current = window.setTimeout(() => {
        setCopied(false)
        resetTimerRef.current = null
      }, 1400)
    } catch {
      setCopied(false)
    }
  }

  return (
    <article className="quickstart-step">
      <span className="quickstart-num">{step}</span>
      <span className="quickstart-name">{label}</span>
      <code className="command-key">
        <span className="command-prompt" aria-hidden="true">$</span>
        <span className="command-text">{command}</span>
      </code>
      <button
        type="button"
        className={`command-copy${copied ? ' copied' : ''}`}
        onClick={copyCommand}
        aria-label={`Copy ${label.toLowerCase()} command`}
      >
        <span className="command-copy-text">{copied ? 'Copied' : 'Copy'}</span>
      </button>
    </article>
  )
}

export default function Home() {
  return (
    <div className="page home-page">
      <section className="home-hero" data-reveal>
        <div className="home-hero-copy">
          <span className="page-header-eyebrow">A7 docs · curl.md ready</span>
          <h1 className="page-header-title">A7, simple, fast.</h1>
          <p className="page-header-summary">
            A small systems language with fetchable docs, direct compiler output, and verified examples.
          </p>

          <div className="home-hero-actions">
            <Link to="/start" className="primary-action">
              Getting Started <span aria-hidden="true">→</span>
            </Link>
            <a href={publicDocsPath('/llms.txt')} className="secondary-action">
              llms.txt <span aria-hidden="true">→</span>
            </a>
          </div>
        </div>

        <div className="home-hero-media">
          <div className="home-hero-code">
            <CodeBlock code={FIBONACCI} lang="a7" title="033_fibonacci.a7" />
          </div>
        </div>
      </section>

      <SectionPanel className="home-quickstart quickstart-strip">
        <div className="quickstart-intro">
          <p className="quickstart-label">Quick start</p>
          <h2 className="quickstart-title">From zero to running.</h2>
          <p className="text-tertiary text-small">
            Python 3.13+, uv, and Zig for generated output.
          </p>
        </div>

        <div className="quickstart-steps">
          {QUICKSTART.map((item) => <QuickstartCommand key={item.step} {...item} />)}
        </div>
      </SectionPanel>

      <SectionPanel className="home-feature-grid">
        <div className="feature-list">
          {FEATURES.map((feature) => (
            <article key={feature.title} className="feature-row">
              <h3 className="feature-title">{feature.title}</h3>
              <p className="feature-copy">{feature.copy}</p>
            </article>
          ))}
        </div>
      </SectionPanel>

      <SectionPanel className="home-pipeline pipeline-showcase">
        <div className="pipeline-intro">
          <p className="section-label">Under the hood</p>
          <h2 className="home-section-title">Transparent pipeline.</h2>
          <p className="pipeline-intro-copy">
            Five visible stages from source to generated code.
          </p>
          <Link to="/internals#pipeline" className="pipeline-intro-link">
            Learn more <span aria-hidden="true">→</span>
          </Link>
        </div>

        <div className="pipeline-stage-grid">
          <div className="pipeline-stage-row">
            {PIPELINE.map((stage, index) => (
              <Fragment key={stage.title}>
                <article className="pipeline-tile">
                  <span className="pipeline-tile-title">{stage.title}</span>
                  <span className="pipeline-tile-copy">{stage.copy}</span>
                </article>
                {index < PIPELINE.length - 1 ? <span className="pipeline-arrow" aria-hidden="true">→</span> : null}
              </Fragment>
            ))}
          </div>
        </div>
      </SectionPanel>

      <SectionPanel className="home-highlights highlights-section">
        <div className="highlights-intro">
          <p className="section-label">Docs map</p>
          <h2 className="home-section-title">Built for curl.md fetches.</h2>
          <Link to="/features" className="pipeline-intro-link">
            Browse guide <span aria-hidden="true">→</span>
          </Link>
        </div>

        <div className="highlights-grid">
          {HIGHLIGHTS.map((item) => (
            <article key={item.title} className="highlight-item">
              <div className="highlight-title">{item.title}</div>
              <div className="highlight-copy">{item.copy}</div>
            </article>
          ))}
        </div>
      </SectionPanel>

      <SectionPanel className="home-cta-panel home-cta">
        <div className="home-cta-copy">
          <h2 className="home-cta-title">A7, simple, fast.</h2>
          <p>Start with one file.</p>
          <div className="home-cta-actions">
            <Link to="/start" className="primary-action">
              Get started <span aria-hidden="true">→</span>
            </Link>
            <a
              href="https://github.com/code5717/a7-py"
              className="secondary-action"
              target="_blank"
              rel="noopener noreferrer"
            >
              Star on GitHub <span aria-hidden="true">↗</span>
            </a>
          </div>
        </div>
      </SectionPanel>
    </div>
  )
}
