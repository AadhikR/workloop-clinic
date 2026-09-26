import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const publicEnvironmentNames = [
  'VITE_API_BASE_URL',
  'VITE_OIDC_AUTHORITY',
  'VITE_OIDC_CLIENT_ID',
  'VITE_OIDC_REDIRECT_URI',
  'VITE_OIDC_POST_LOGOUT_REDIRECT_URI',
  'VITE_OIDC_AUDIENCE',
]

export default defineConfig({
  plugins: [react()],
  envPrefix: publicEnvironmentNames,
  server: {
    headers: { 'Referrer-Policy': 'no-referrer' },
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
  },
  preview: {
    headers: { 'Referrer-Policy': 'no-referrer' },
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
