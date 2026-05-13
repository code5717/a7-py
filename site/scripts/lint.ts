import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'

const ROOT = path.resolve(import.meta.dir, '..')
const DOCS = path.join(ROOT, 'public', 'docs')
const REQUIRED = ['index.md', 'start.md', 'language.md', 'stdlib.md', 'compiler.md', 'status.md', 'release.md', 'agent-usage.md']

async function listFiles(dir: string): Promise<string[]> {
  const out: string[] = []
  const entries = await readdir(dir, { withFileTypes: true })
  for (const entry of entries) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...await listFiles(full))
    else if (entry.isFile()) out.push(full)
  }
  return out
}

let failed = false
function fail(message: string) {
  failed = true
  console.error(message)
}

const docs = new Set((await readdir(DOCS)).filter((name) => name.endsWith('.md')))
for (const file of REQUIRED) {
  if (!docs.has(file)) fail(`missing public doc: ${file}`)
}

for (const file of await listFiles(ROOT)) {
  if (file.includes('/node_modules/') || file.includes('/dist/')) continue
  const text = await readFile(file, 'utf8')
  const legacyManager = new RegExp(String.raw`\bnp` + String.raw`m\b|package-` + String.raw`lock|np` + String.raw`x\b`)
  if (legacyManager.test(text)) fail(`legacy package-manager reference: ${path.relative(ROOT, file)}`)
  if (file.endsWith('.md') && /\bTODO\b|\bTBD\b/.test(text)) fail(`placeholder marker in ${path.relative(ROOT, file)}`)
}

if (failed) process.exit(1)
console.log('site-lint: ok')
