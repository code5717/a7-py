import { useHighlight } from '../hooks/useHighlight'

interface CodeBlockProps {
  code: string
  lang?: string
  title?: string
}

export default function CodeBlock({ code, lang, title }: CodeBlockProps) {
  const html = useHighlight(code, lang)

  return (
    <figure className="code-shell" data-reveal>
      {(title || lang) && (
        <figcaption className="code-head">
          <span className="code-head-title">{title || lang}</span>
          {lang ? <span className="code-head-meta">{lang}</span> : null}
        </figcaption>
      )}
      {html ? (
        <div className="code-pre code-highlighted" dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <pre className="code-pre">
          <code>{code}</code>
        </pre>
      )}
    </figure>
  )
}
