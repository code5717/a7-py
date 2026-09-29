import { serve } from 'bun'
import { realpath, stat } from 'node:fs/promises'
import path from 'node:path'

function contentType(file: string): string {
  if (file.endsWith('.json')) return 'application/json; charset=utf-8'
  if (file.endsWith('.woff2')) return 'font/woff2'
  if (file.endsWith('.html')) return 'text/html; charset=utf-8'
  if (file.endsWith('.css')) return 'text/css; charset=utf-8'
  if (file.endsWith('.js')) return 'text/javascript; charset=utf-8'
  if (file.endsWith('.svg')) return 'image/svg+xml'
  if (file.endsWith('.md') || file.endsWith('.txt')) return 'text/plain; charset=utf-8'
  if (file.endsWith('.xml')) return 'application/xml; charset=utf-8'
  return 'application/octet-stream'
}

export async function startPreview(directory: string, port: number) {
  const root = await realpath(directory)
  const inside = (file: string) => file === root || file.startsWith(root + path.sep)
  return serve({
    hostname: '127.0.0.1',
    port,
    async fetch(req) {
      let pathname: string
      try {
        pathname = decodeURIComponent(new URL(req.url).pathname)
      } catch {
        return new Response('Invalid URL encoding', { status: 400 })
      }
      if (pathname.includes('\0') || pathname.includes('\\') || pathname.split('/').includes('..')) {
        return new Response('Forbidden', { status: 403 })
      }
      const relative = pathname.replace(/^\/a7-py(?:\/|$)/, '/')
      let file = path.resolve(root, '.' + relative)
      if (!inside(file)) return new Response('Forbidden', { status: 403 })
      try {
        file = await realpath(file)
        if (!inside(file)) return new Response('Forbidden', { status: 403 })
        if ((await stat(file)).isDirectory()) file = await realpath(path.join(file, 'index.html'))
        if (!inside(file)) return new Response('Forbidden', { status: 403 })
        if (!(await stat(file)).isFile()) return new Response('Not found', { status: 404 })
        return new Response(Bun.file(file), { headers: { 'content-type': contentType(file) } })
      } catch (error) {
        if (['ENOENT', 'ENOTDIR'].includes((error as NodeJS.ErrnoException).code ?? '')) {
          return new Response('Not found', { status: 404 })
        }
        throw error
      }
    },
  })
}

if (import.meta.main) {
  const server = await startPreview(path.resolve(import.meta.dir, '..', 'dist'), Number(process.env.PORT ?? '4173'))
  console.log(`preview: http://127.0.0.1:${server.port}/a7-py/`)
}
