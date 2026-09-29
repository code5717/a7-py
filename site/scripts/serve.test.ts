import { test, expect } from 'bun:test'
import { mkdtemp, mkdir, writeFile, symlink, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { startPreview } from './serve'

test('preview serves docs and confines requests to its directory', async () => {
  const fixture = await mkdtemp(path.join(tmpdir(), 'a7-preview-'))
  const root = path.join(fixture, 'dist')
  await mkdir(path.join(root, 'guide'), { recursive: true })
  await writeFile(path.join(root, 'index.html'), '<h1>A7</h1>')
  await writeFile(path.join(root, 'guide', 'index.html'), 'Guide')
  await writeFile(path.join(root, 'notes.md'), '# Notes')
  await writeFile(path.join(root, 'manifest.json'), '{"schemaVersion":1}')
  await writeFile(path.join(fixture, 'private.txt'), 'outside fixture')
  await symlink(path.join(fixture, 'private.txt'), path.join(root, 'escape.txt'))
  await mkdir(path.join(root, 'linked'))
  await symlink(path.join(fixture, 'private.txt'), path.join(root, 'linked', 'index.html'))
  const server = await startPreview(root, 0)
  try {
    const base = `http://127.0.0.1:${server.port}`
    for (const [url, body] of [['/a7-py/', '<h1>A7</h1>'], ['/a7-py/guide/', 'Guide'], ['/a7-py/notes.md', '# Notes']]) {
      const response = await fetch(base + url)
      expect(response.status).toBe(200)
      expect(await response.text()).toBe(body)
    }
    for (const url of ['/a7-py/..%2fprivate.txt', '/a7-py/%2e%2e%2fprivate.txt', '/a7-py/escape.txt', '/a7-py/linked/']) {
      const response = await fetch(base + url)
      expect(response.status).toBe(403)
      expect(await response.text()).not.toContain('outside fixture')
    }
    expect((await fetch(base + '/a7-py/%ZZ')).status).toBe(400)
    expect((await fetch(base + '/a7-py/missing')).status).toBe(404)
    expect((await fetch(base + '/a7-py/manifest.json')).headers.get('content-type')).toBe('application/json; charset=utf-8')
    expect((await fetch(base + '/a7-py/missing.md')).status).toBe(404)
    expect((await fetch(base + '/a7-py/notes.md')).headers.get('content-type')).toBe('text/plain; charset=utf-8')
  } finally {
    server.stop(true)
    await rm(fixture, { recursive: true, force: true })
  }
})
