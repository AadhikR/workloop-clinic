import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

import { migrationIsolationPlugin } from './vite-isolation.js'

const migrationPublicEnvironmentNames = [
  'VITE_API_BASE_URL',
  'VITE_OIDC_AUTHORITY',
  'VITE_OIDC_CLIENT_ID',
  'VITE_OIDC_REDIRECT_URI',
  'VITE_OIDC_POST_LOGOUT_REDIRECT_URI',
  'VITE_OIDC_AUDIENCE',
]

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [migrationIsolationPlugin(), react()],
  envPrefix: migrationPublicEnvironmentNames,
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
  },
  preview: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
  },
  build: {
    outDir: '../dist-migration',
    emptyOutDir: true,
  },
})
