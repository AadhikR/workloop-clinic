import { useEffect, useState } from 'react'

import {
  readLeaveConfiguration,
  seedLeaveTypes,
  seedPublicHolidays,
} from './leaveConfigurationApi.js'

export default function LeaveConfiguration({ authentication, branchId }) {
  const [state, setState] = useState({ status: 'loading', data: null, message: '' })

  const refresh = () => {
    const controller = new AbortController()
    setState((current) => ({ ...current, status: 'loading', message: '' }))
    readLeaveConfiguration(authentication, branchId, { signal: controller.signal })
      .then((data) => setState({ status: 'ready', data, message: '' }))
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: 'error', data: null, message: 'Leave configuration is unavailable.' })
      })
    return () => controller.abort()
  }

  useEffect(() => refresh(), [authentication, branchId])

  const seedTypes = async () => {
    try {
      await seedLeaveTypes(authentication, branchId)
      refresh()
    } catch {
      setState((current) => ({ ...current, message: 'Leave types could not be seeded.' }))
    }
  }

  if (state.status === 'loading') return <section aria-label="Leave configuration"><p>Loading leave configuration...</p></section>
  if (state.status === 'error') return <section aria-label="Leave configuration"><p>{state.message}</p></section>

  return (
    <section className="leave-configuration" aria-labelledby="leave-configuration-title">
      <h2 id="leave-configuration-title">Leave configuration</h2>
      <p>Branch settings, active leave types, and public holidays.</p>
      <dl>
        <div><dt>Weekend</dt><dd>{state.data.settings.weekendDefinition}</dd></div>
        <div><dt>Approval chain</dt><dd>{state.data.settings.approvalChain}</dd></div>
        <div><dt>Active leave types</dt><dd>{state.data.types.filter((item) => item.isActive).length}</dd></div>
        <div><dt>Public holidays</dt><dd>{state.data.holidays.length}</dd></div>
      </dl>
      <div className="actions">
        <button type="button" onClick={seedTypes}>Seed default leave types</button>
        <button type="button" className="secondary" onClick={refresh}>Refresh</button>
      </div>
      {state.message && <p role="status">{state.message}</p>}
    </section>
  )
}
