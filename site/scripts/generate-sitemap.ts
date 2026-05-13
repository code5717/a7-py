/*
 * Tiny build helper: regenerate public/sitemap.xml from the manifest.
 * Invoked manually via `bunx tsx scripts/generate-sitemap.ts` after editing the manifest.
 * Not wired into vite build to keep the sitemap committed in version control.
 */

import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SITE_ROOT = path.resolve(__dirname, '..')

const ORIGIN = 'https://code5717.github.io/a7-py'

async function main() {
  const manifestModule = await import('../src/content/manifest.ts')
  const entries = manifestModule.MANIFEST as Array<{ path: string }>
  const routes = ['/', ...entries.map((e) => e.path)]
  const assets = ['/llms.txt', '/llms-full.txt']

  const body = [
    ...routes.map((u) => {
      const trimmed = u.replace(/\/$/, '')
      const final = trimmed === '' ? '/' : trimmed + '/'
      return `  <url><loc>${ORIGIN}${final}</loc></url>`
    }),
    ...assets.map((u) => `  <url><loc>${ORIGIN}${u}</loc></url>`),
  ].join('\n')

  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`

  const out = path.join(SITE_ROOT, 'public', 'sitemap.xml')
  await fs.writeFile(out, xml, 'utf8')
  console.log(`sitemap.xml: wrote ${routes.length + assets.length} urls → ${out}`)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
