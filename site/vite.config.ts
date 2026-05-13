import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import a7Docs from './scripts/vite-plugin-a7-docs'

export default defineConfig({
  plugins: [react(), a7Docs()],
  base: '/a7-py/',
  server: {
    fs: {
      allow: [path.resolve(__dirname, '..')],
    },
  },
})
