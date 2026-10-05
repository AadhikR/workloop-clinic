import { useEffect, useMemo, useState } from 'react'

import { readDashboard } from './dashboardApi.js'
import { readSelfAssets } from './developmentAssetsApi.js'
import { readEmployeeSelf } from './employeeApi.js'
import { readPersonalAttendance } from './attendanceCalculationApi.js'
import { readAllEmployeeLeaveRequests } from './leaveBalanceApi.js'

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
  const hour = Number(new Intl.DateTimeFormat('en', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Asia/Dubai' }).format(new Date()))
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
  if (days <= 60) return 'warning'
  return 'valid'
}

export default function EmployeeHome({ authentication, navigator, role = 'employee' }) {
  const [state, setState] = useState({ status: 'loading', employee: null, dashboard: null, assets: [] })
  const [attendance, setAttendance] = useState(null)
  const [requests, setRequests] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    readPersonalAttendance(authentication).then((value) => { if (!controller.signal.aborted) setAttendance(value) }).catch(() => {})
    readAllEmployeeLeaveRequests(authentication, new Date().getUTCFullYear()).then((value) => { if (!controller.signal.aborted) setRequests(value) }).catch(() => {})
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

      <section className="employee-panel home-attendance"><div className="employee-section-heading"><h3>Today's status</h3><button type="button" className="btn btn-ghost btn-sm" onClick={() => navigator.go(`/${role}/attendance`)}>View attendance</button></div>
        {attendance ? <><strong>{attendance.record?.status.replaceAll('_', ' ') ?? 'Not calculated'}</strong><div className="home-attendance-times"><p>Clock in: {attendance.record?.clockInTime ? new Date(attendance.record.clockInTime).toLocaleTimeString('en-AE', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Dubai' }) : 'Not recorded'}</p><p>Clock out: {attendance.record?.clockOutTime ? new Date(attendance.record.clockOutTime).toLocaleTimeString('en-AE', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Dubai' }) : 'Not recorded'}</p><p>Hours: {attendance.record?.totalHours ?? 'Not calculated'}</p></div></> : <p>Attendance is unavailable.</p>}
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigator.go(`/${role}/schedule`)}>Today's shift: {cardValue(state.dashboard.cards.find((card) => card.code === 'todayShift'))}</button>
      </section>

      <div className="employee-kpi-grid home-quick-cards">
        {state.dashboard.cards.filter((card) => ['leaveBalance', 'latestPayslip'].includes(card.code)).map((card) => {
          const path = targets[card.drillDown.target]?.replace('/employee', `/${role}`)
          const content = <><span>{card.code === 'leaveBalance' ? 'Annual leave balance' : card.label}</span><strong>{cardValue(card)}{card.code === 'leaveBalance' && ' days'}</strong>{card.code === 'leaveBalance' && <small>{requests === null ? 'Pending requests unavailable' : `${requests.filter((item) => item.status.toLowerCase() === 'pending').length} pending requests`}</small>}{card.comparison && <small>{card.comparison.label}: {card.comparison.value}</small>}</>
          return path ? <button className="employee-kpi-card" data-severity={card.severity} key={card.code} type="button" onClick={() => navigator.go(path)}>{content}</button>
            : <article className="employee-kpi-card" data-severity={card.severity} key={card.code}>{content}</article>
        })}
      </div>

      {identityDates.some(([, date]) => ['warning', 'critical', 'expired'].includes(urgency(date))) && <section className="employee-panel alert alert-warning" aria-labelledby="identity-expiry-title"><h3 id="identity-expiry-title">Document expiry reminder</h3><ul className="employee-detail-list">{identityDates.filter(([, date]) => ['warning', 'critical', 'expired'].includes(urgency(date))).map(([label, date]) => <li key={label}><strong>{label}</strong><span>{date}</span><span className="status-pill" data-status={urgency(date)}>{urgency(date)}</span></li>)}</ul></section>}
      <div className="employee-home-grid">
        <section className="employee-panel" aria-labelledby="assigned-assets-title">
          <h3 id="assigned-assets-title">Assigned assets</h3>
          {state.assets.filter((item) => item.returnDate === null).length === 0 ? <p className="empty-copy">No assets are currently assigned to you.</p> : (
            <ul className="employee-detail-list">{state.assets.filter((item) => item.returnDate === null).map((asset) => (
              <li key={asset.id}><strong>{asset.assetName}</strong><span>{asset.assetCode} · Assigned {asset.assignedDate}</span></li>
            ))}</ul>
          )}
        </section>
        <section className="employee-panel"><div className="employee-section-heading"><h3>Recent leave requests</h3><button type="button" className="btn btn-ghost btn-sm" onClick={() => navigator.go(`/${role}/leave`)}>All requests</button></div>{requests === null ? <p>Leave requests are unavailable.</p> : requests.length === 0 ? <p>No leave requests this year.</p> : <ul className="employee-detail-list">{requests.slice(0, 3).map((request) => <li key={request.id}><strong>{request.startDate} to {request.endDate}</strong><span>{request.daysRequested} days</span><span className="status-pill" data-status={request.status.toLowerCase()}>{request.status}</span></li>)}</ul>}</section>
      </div>
    </section>
  )
}
