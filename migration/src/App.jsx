import { migrationPublicConfig } from './config.js'

export default function App() {
  return (
    <main data-api-configured={Boolean(migrationPublicConfig.apiBaseUrl)}>
      <p className="eyebrow">Workloop Clinic</p>
      <h1>Migration build</h1>
      <p>
        This isolated frontend is ready for the authentication work scheduled in Phase 3G.
      </p>
    </main>
  )
}
