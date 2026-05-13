import { Link } from 'react-router-dom'
import StatusChip from '../components/StatusChip'
import styles from './Home.module.css'

const PIPELINE = [
  { idx: '01', label: 'tokens', status: 'OK' as const },
  { idx: '02', label: 'parser', status: 'OK' as const },
  { idx: '03', label: 'sema', status: 'OK' as const },
  { idx: '04', label: 'zig codegen', status: 'OK' as const },
  { idx: '05', label: 'native binary', status: 'OK' as const },
]

const SECTIONS = [
  {
    idx: '01',
    label: 'LEARN',
    title: 'Start here',
    body: 'Five-minute path from clone to running an A7 example through Zig 0.16.',
    to: '/learn/start',
  },
  {
    idx: '02',
    label: 'REFERENCE',
    title: 'Read the spec',
    body: 'Language, CLI, stdlib, and API surfaces — the reference an agent reads first.',
    to: '/ref/language',
  },
  {
    idx: '03',
    label: 'COMPILER',
    title: 'Inside the binder',
    body: 'Pipeline, safety, testing, status — what the compiler does and refuses to do.',
    to: '/compiler/internals',
  },
  {
    idx: '05',
    label: 'AGENTS',
    title: 'Agent contracts',
    body: 'Skills, fetch order, trust boundaries, and per-editor plugin notes.',
    to: '/agents',
  },
]

export default function Home() {
  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroChrome}>
          <span className={styles.heroTag}>[A7//COMPILER]</span>
          <span className={styles.heroVer}>[v0.16]</span>
        </div>
        <div className={styles.heroGrid}>
          <div className={styles.heroLeft}>
            <p className={styles.eyebrow}>AHEAD-OF-TIME · ZIG BACKEND · ISSUE 04</p>
            <h1 className={styles.title}>
              A small, safe compiler<br />for the agent era.
            </h1>
            <p className={styles.lead}>
              A7 lowers <code>.a7</code> source through a constraint-discipline pipeline to Zig, then to a
              native binary via the host toolchain. Iterative passes. Banned recursion. Deterministic exit codes.
            </p>
            <div className={styles.cta}>
              <Link to="/learn/start" className={`${styles.btn} ${styles.btnPrimary}`}>
                Get started <span aria-hidden>→</span>
              </Link>
              <Link to="/ref/language" className={styles.btn}>
                Read the spec <span aria-hidden>→</span>
              </Link>
            </div>
          </div>
          <div className={styles.heroRight}>
            <div className={styles.terminal}>
              <header className={styles.terminalStrip}>
                <span>term.exe</span>
                <span>/A7-PL-001</span>
              </header>
              <pre className={styles.terminalBody}>
                <span className={styles.term_prompt}>$ </span>
                <span className={styles.term_cmd}>uv run a7 build hello.a7 --release</span>
                {'\n'}
                <span className={styles.term_ok}>✓ parsed</span>{'    '}
                <span className={styles.term_ok}>✓ typed</span>{'    '}
                <span className={styles.term_ok}>✓ codegen</span>{'\n'}
                <span className={styles.term_ok}>✓ zig build</span>{'\n'}
                <span className={styles.term_dim}>→ out/hello (12 KB)</span>
              </pre>
            </div>
            <div className={styles.pipeline}>
              <header className={styles.pipelineHead}>
                <span>COMPILE PIPELINE — DIAGRAM</span>
                <StatusChip tone="accent">ACTIVE</StatusChip>
              </header>
              <ol className={styles.pipelineList}>
                {PIPELINE.map((s, i) => (
                  <li key={s.idx} className={styles.pipelineItem}>
                    <span className={styles.pipelineIdx}>{s.idx}</span>
                    <span className={styles.pipelineLabel}>{s.label}</span>
                    <StatusChip tone="ok">{s.status}</StatusChip>
                    {i < PIPELINE.length - 1 && <span className={styles.pipelineArrow} aria-hidden>→</span>}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.sections} aria-label="Documentation entry points">
        {SECTIONS.map((s) => (
          <Link key={s.idx} to={s.to} className={styles.card}>
            <div className={styles.cardHead}>
              <span className={styles.cardIdx}>{s.idx}</span>
              <span className={styles.cardLabel}>[ {s.label} ]</span>
            </div>
            <h2 className={styles.cardTitle}>{s.title}</h2>
            <p className={styles.cardBody}>{s.body}</p>
            <span className={styles.cardCta}>READ →</span>
          </Link>
        ))}
      </section>

      <section className={styles.specStrip}>
        <header className={styles.specHead}>
          <span className={styles.specLeft}>[ SPECIFICATIONS ]</span>
          <span className={styles.specRight}>A7 · ZIG 0.16 · LINUX/x86_64</span>
        </header>
        <dl className={styles.specGrid}>
          <div>
            <dt>Source</dt>
            <dd>.a7 → .zig → native binary</dd>
          </div>
          <div>
            <dt>Recursion</dt>
            <dd>Rejected at compile time</dd>
          </div>
          <div>
            <dt>Traversal</dt>
            <dd>Iterative · stack-bounded</dd>
          </div>
          <div>
            <dt>Exit codes</dt>
            <dd>0 / 2 / 3 / 4 / 5 / 6 / 7 / 8</dd>
          </div>
          <div>
            <dt>Toolchain</dt>
            <dd>uv · zig 0.16</dd>
          </div>
          <div>
            <dt>License</dt>
            <dd>MIT</dd>
          </div>
        </dl>
      </section>
    </div>
  )
}
