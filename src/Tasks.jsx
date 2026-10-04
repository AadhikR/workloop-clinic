import { useCallback, useEffect, useRef, useState } from 'react'

import { readTasks } from './taskApi.js'

function mergePage(current, next) {
  return {
    ...next,
    categories: next.categories.map((category) => {
      const previous = current.categories.find((value) => value.code === category.code)
      return previous ? { ...category, items: [...previous.items, ...category.items] } : category
    }),
  }
}

const employeeScreens = {
  advances: '/employee/advances',
  attendance: '/employee/attendance',
  certifications: '/employee/training',
  developmentAssets: '/employee/training',
  documents: '/employee/documents',
  expenses: '/employee/expenses',
  leave: '/employee/leave',
  letterRequests: '/employee/requests',
  personalAttendance: '/employee/attendance',
  recordsBenefits: '/employee/documents',
  requests: '/employee/requests',
}

const adminScreens = {
  advances: '/admin/advances',
  appraisals: '/admin/appraisals',
  attendanceExceptions: '/admin/attendance',
  developmentAssets: '/admin/training',
  employees: '/admin/employees',
  expenses: '/admin/expenses',
  leaveApprovals: '/admin/leave',
  letterRequests: '/admin/requests',
  offboarding: '/admin/employees',
  payroll: '/admin/payroll',
  recordsBenefits: '/admin/employees',
  shiftSwaps: '/admin/roster',
}

const managerScreens = {
  ...Object.fromEntries(Object.entries(employeeScreens).map(([key, path]) => [key, path.replace('/employee/', '/manager/')])),
  appraisals: '/manager/appraisals',
  developmentAssets: '/manager/training',
  expenses: '/manager/expense-queue',
  leaveApprovals: '/manager/leave-queue',
}

const taskScreens = { admin: adminScreens, employee: employeeScreens, manager: managerScreens }

export default function Tasks({ account, authentication, branchId, navigator }) {
  return <ScopedTasks key={`${account.appUserId}:${account.role}:${branchId}`} account={account} authentication={authentication} branchId={branchId} navigator={navigator} />
}

function ScopedTasks({ account, authentication, branchId, navigator }) {
  const [catalogue, setCatalogue] = useState(null)
  const [status, setStatus] = useState('loading')
  const [category, setCategory] = useState('')
  const [urgency, setUrgency] = useState('')
  const [collapsed, setCollapsed] = useState({})
  const generation = useRef(0)

  const load = useCallback(async (cursor = null) => {
    const currentGeneration = ++generation.current
    setStatus('loading')
    try {
      const result = await readTasks(authentication, account.role, branchId, {
        category, urgency, limit: 50, cursor,
      })
      if (currentGeneration !== generation.current) return
      setCatalogue((current) => cursor && current ? mergePage(current, result) : result)
      setStatus('ready')
    } catch {
      if (currentGeneration === generation.current) setStatus('unavailable')
    }
  }, [account.role, authentication, branchId, category, urgency])

  useEffect(() => {
    const invalidate = () => { generation.current++ }
    const request = globalThis.setTimeout(() => load(), 0)
    const timer = globalThis.setInterval(() => load(), 60_000)
    return () => { globalThis.clearTimeout(request); globalThis.clearInterval(timer); invalidate() }
  }, [load])

  const categories = catalogue?.categories ?? []
  const taskFallback = `/${account.role}/tasks`
  const targetFor = (task) => taskScreens[account.role]?.[task.navigation.screen] ?? taskFallback
  return (
    <section className="task-centre" aria-label="Tasks">
      <div className="task-heading">
        <div>
          <p className="eyebrow">Work queue</p>
          <h3>Tasks</h3>
          {catalogue && <span>{categories.reduce((sum, item) => sum + item.count, 0)} items</span>}
        </div>
        <div className="task-filters">
          <button type="button" className="btn btn-outline" disabled={status === 'loading'} onClick={() => load()}>Refresh</button>
          <label>
            Category
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">All categories</option>
              {categories.map((value) => (
                <option key={value.code} value={value.code}>{value.label}</option>
              ))}
            </select>
          </label>
          <label>
            Urgency
            <select value={urgency} onChange={(event) => setUrgency(event.target.value)}>
              <option value="">All urgency levels</option>
              <option value="action">Action</option>
              <option value="expired">Expired</option>
              <option value="urgent">Urgent</option>
              <option value="warning">Warning</option>
              <option value="info">Information</option>
            </select>
          </label>
        </div>
      </div>
      {status === 'loading' && catalogue === null && <p>Loading tasks...</p>}
      {status === 'unavailable' && <p role="alert">Tasks are unavailable. Try again.</p>}
      {status !== 'unavailable' && categories.map((value) => (
        <section className="task-category" key={value.code} data-task-status={value.status}>
          <h4><button type="button" className="task-group-toggle" aria-expanded={!collapsed[value.code]} onClick={() => setCollapsed({ ...collapsed, [value.code]: !collapsed[value.code] })}>{value.label} <span>{value.count}</span><span aria-hidden="true">{collapsed[value.code] ? '›' : '⌄'}</span></button></h4>
          {value.status === 'failed' && <p role="alert">This task source is unavailable.</p>}
          {value.status === 'empty' && <p>No tasks in this category.</p>}
          {!collapsed[value.code] && value.items.length > 0 && (
            <ol>
              {value.items.map((task) => (
                <li key={task.id} data-urgency={task.urgency}>
                  <a href={targetFor(task)} data-task-id={task.id} onClick={navigator ? (event) => {
                    event.preventDefault()
                    navigator.go(targetFor(task))
                  } : undefined}>
                    <strong>{task.title}</strong>
                    <span>{task.subtitle}</span>
                    {task.dueDate && <time dateTime={task.dueDate}>Due {task.dueDate}</time>}
                    <span className="badge task-urgency">{task.urgency}</span>
                  </a>
                </li>
              ))}
            </ol>
          )}
        </section>
      ))}
      {catalogue?.nextCursor && (
        <button type="button" className="secondary" disabled={status === 'loading'}
          onClick={() => load(catalogue.nextCursor)}>
          {status === 'loading' ? 'Loading...' : 'Load more'}
        </button>
      )}
    </section>
  )
}
