import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

import { legacyIsolationPlugin, legacyPublicEnvironmentNames } from './vite.legacy-isolation.js'

export default defineConfig({
  plugins: [legacyIsolationPlugin(), react()],
  envPrefix: legacyPublicEnvironmentNames,
  base: './',
})
