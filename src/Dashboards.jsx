import { useEffect, useState } from 'react'

import { readDashboard } from './dashboardApi.js'

const titles = {
  admin: 'Administrator dashboard',
  clinical: 'Clinical dashboard',
  self: 'My dashboard',
}

function displayValue(card) {
  if (card.value === 'not_available') return 'Not available'
  if (card.unit === 'AED' && typeof card.value === 'string') return `AED ${card.value}`
  if (card.unit === 'percent' && typeof card.value === 'string') return `${card.value}%`
  return `${card.value}`
}

export default function Dashboard({ authentication, branchId, kind }) {
  const [state, setState] = useState({ status: 'loading' })
  const requestKey = `${kind}:${branchId ?? 'self'}`

  useEffect(() => {
    const controller = new AbortController()
    readDashboard(authentication, kind, branchId)
      .then((data) => {
        if (!controller.signal.aborted) setState({ status: 'ready', data, requestKey })
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: 'unavailable', requestKey })
      })
    return () => controller.abort()
  }, [authentication, branchId, kind, requestKey])

  const view = state.requestKey === requestKey ? state : { status: 'loading' }

  return (
    <section className="dashboard card" data-dashboard-kind={kind} data-dashboard-status={view.status}>
      <div className="card-header dashboard-heading">
        <h3>{titles[kind]}</h3>
        {view.status === 'ready' && <time dateTime={view.data.businessDate}>{view.data.businessDate}</time>}
      </div>
      {view.status === 'loading' && <p>Loading dashboard...</p>}
      {view.status === 'unavailable' && <p role="alert">Dashboard data is unavailable.</p>}
      {view.status === 'ready' && (
        <div className="card-body">
          <div className="dashboard-cards stats-grid">
            {view.data.cards.map((card) => (
              <article className="stat-card" key={card.code} data-card-code={card.code} data-severity={card.severity}>
                <h4>{card.label}</h4>
                <p>{displayValue(card)}</p>
                {card.comparison && (
                  <small>{card.comparison.label}: {card.comparison.value} {card.comparison.unit}</small>
                )}
                <a href={`#${card.drillDown.target}`}>View details</a>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
