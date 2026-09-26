import { useCallback, useEffect, useState } from 'react'

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

export default function Tasks({ account, authentication, branchId }) {
  const [catalogue, setCatalogue] = useState(null)
  const [status, setStatus] = useState('loading')
  const [category, setCategory] = useState('')
  const [urgency, setUrgency] = useState('')

  const load = useCallback(async (cursor = null) => {
    setStatus('loading')
    try {
      const result = await readTasks(authentication, account.role, branchId, {
        category, urgency, limit: 50, cursor,
      })
      setCatalogue((current) => cursor && current ? mergePage(current, result) : result)
      setStatus('ready')
    } catch {
      setStatus('unavailable')
    }
  }, [account.role, authentication, branchId, category, urgency])

  useEffect(() => {
    const request = globalThis.setTimeout(() => load(), 0)
    return () => globalThis.clearTimeout(request)
  }, [load])

  const categories = catalogue?.categories ?? []
  return (
    <section className="task-centre" aria-label="Tasks">
      <div className="task-heading">
        <div>
          <p className="eyebrow">Work queue</p>
          <h3>Tasks</h3>
        </div>
        <div className="task-filters">
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
          <h4>{value.label} <span>{value.count}</span></h4>
          {value.status === 'failed' && <p role="alert">This task source is unavailable.</p>}
          {value.status === 'empty' && <p>No tasks in this category.</p>}
          {value.items.length > 0 && (
            <ol>
              {value.items.map((task) => (
                <li key={task.id} data-urgency={task.urgency}>
                  <a href={`#${task.navigation.screen}`} data-task-id={task.id}>
                    <strong>{task.title}</strong>
                    <span>{task.subtitle}</span>
                    {task.dueDate && <time dateTime={task.dueDate}>Due {task.dueDate}</time>}
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
