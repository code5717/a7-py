import { serve } from 'bun'
import { existsSync, statSync } from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dir, '..', 'dist')
const port = Number(process.env.PORT ?? '4173')

function contentType(file: string): string {
  if (file.endsWith('.html')) return 'text/html; charset=utf-8'
  if (file.endsWith('.css')) return 'text/css; charset=utf-8'
  if (file.endsWith('.js')) return 'text/javascript; charset=utf-8'
  if (file.endsWith('.svg')) return 'image/svg+xml'
  if (file.endsWith('.md') || file.endsWith('.txt')) return 'text/plain; charset=utf-8'
  if (file.endsWith('.xml')) return 'application/xml; charset=utf-8'
  return 'application/octet-stream'
}

serve({
  port,
  async fetch(req) {
    const url = new URL(req.url)
    const stripped = url.pathname.replace(/^\/a7-py\/?/, '/')
    const rel = decodeURIComponent(stripped === '/' ? '/index.html' : stripped)
    let file = path.join(root, rel)
    if (existsSync(file) && statSync(file).isDirectory()) {
      file = path.join(file, 'index.html')
    }
    if (!existsSync(file)) file = path.join(root, '404.html')
    return new Response(Bun.file(file), { headers: { 'content-type': contentType(file) } })
  },
})

console.log(`preview: http://localhost:${port}/a7-py/`)
