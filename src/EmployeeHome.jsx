import { useEffect, useMemo, useState } from 'react'

import { readDashboard } from './dashboardApi.js'
import { readSelfAssets } from './developmentAssetsApi.js'
import { readEmployeeSelf } from './employeeApi.js'

const targets = {
  assignedAssets: '/employee/documents',
  developmentAssets: '/employee/documents',
  attendance: '/employee/attendance',
  leave: '/employee/leave',
  payslips: '/employee/payslips',
  profile: '/employee/profile',
  schedule: '/employee/schedule',
}

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function cardValue(card) {
  if (card.value === 'not_available') return 'Not available'
  if (card.unit === 'AED') return `AED ${card.value}`
  if (card.unit === 'percent') return `${card.value}%`
  return `${card.value}`
}

function urgency(date) {
  if (!date) return 'none'
  const days = Math.ceil((new Date(`${date}T00:00:00+04:00`) - Date.now()) / 86400000)
  if (days < 0) return 'expired'
  if (days <= 30) return 'critical'
  if (days <= 90) return 'warning'
  return 'valid'
}

export default function EmployeeHome({ authentication, navigator }) {
  const [state, setState] = useState({ status: 'loading', employee: null, dashboard: null, assets: [] })

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      readEmployeeSelf(authentication, { signal: controller.signal }),
      readDashboard(authentication, 'self'),
      readSelfAssets(authentication),
    ]).then(([employee, dashboard, assets]) => {
      if (!controller.signal.aborted) setState({ status: 'ready', employee, dashboard, assets: assets.items })
    }).catch(() => {
      if (!controller.signal.aborted) setState({ status: 'error', employee: null, dashboard: null, assets: [] })
    })
    return () => controller.abort()
  }, [authentication])

  const identityDates = useMemo(() => state.employee ? [
    ['Visa', state.employee.visaExpiry],
    ['Passport', state.employee.passportExpiry],
    ['Emirates ID', state.employee.emiratesIdExpiry],
    ['Labour card', state.employee.labourCardExpiry],
  ] : [], [state.employee])

  if (state.status === 'loading') return <section className="employee-home employee-state"><p>Loading your dashboard...</p></section>
  if (state.status === 'error') return <section className="employee-home employee-state"><h2>Home</h2><p role="alert">Your dashboard is unavailable. Try again shortly.</p></section>

  const employee = state.employee
  return (
    <section className="employee-home" aria-labelledby="employee-home-title">
      <header className="employee-welcome">
        <div>
          <p>{greeting()}</p>
          <h2 id="employee-home-title">{employee.name}</h2>
          <span>{employee.jobTitle || 'Employee'}{employee.department ? ` · ${employee.department}` : ''}</span>
        </div>
        <span className="status-pill" data-status={employee.employmentStatus}>{employee.employmentStatus.replaceAll('_', ' ')}</span>
      </header>

      <div className="employee-kpi-grid">
        {state.dashboard.cards.map((card) => {
          const path = targets[card.drillDown.target]
          const content = <><span>{card.label}</span><strong>{cardValue(card)}</strong>{card.comparison && <small>{card.comparison.label}: {card.comparison.value}</small>}</>
          return path ? <button className="employee-kpi-card" data-severity={card.severity} key={card.code} type="button" onClick={() => navigator.go(path)}>{content}</button>
            : <article className="employee-kpi-card" data-severity={card.severity} key={card.code}>{content}</article>
        })}
      </div>

      <div className="employee-home-grid">
        <section className="employee-panel" aria-labelledby="assigned-assets-title">
          <h3 id="assigned-assets-title">Assigned assets</h3>
          {state.assets.filter((item) => item.returnDate === null).length === 0 ? <p className="empty-copy">No assets are currently assigned to you.</p> : (
            <ul className="employee-detail-list">{state.assets.filter((item) => item.returnDate === null).map((asset) => (
              <li key={asset.id}><strong>{asset.assetName}</strong><span>{asset.assetCode} · Assigned {asset.assignedDate}</span></li>
            ))}</ul>
          )}
        </section>
        <section className="employee-panel" aria-labelledby="identity-expiry-title">
          <h3 id="identity-expiry-title">Identity document expiry</h3>
          <ul className="employee-detail-list">{identityDates.map(([label, date]) => (
            <li key={label}><strong>{label}</strong><span>{date ?? 'Not recorded'}</span><span className="status-pill" data-status={urgency(date)}>{urgency(date)}</span></li>
          ))}</ul>
        </section>
      </div>
    </section>
  )
}
