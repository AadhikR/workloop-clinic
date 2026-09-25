import { useEffect, useMemo, useState } from 'react'

import { readReport, reportDefinitions } from './reportApi.js'

function display(value) {
  if (value === null) return 'Unavailable'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

export default function Reports({ authentication, branchId }) {
  const [reportId, setReportId] = useState('headcount')
  const [period, setPeriod] = useState('')
  const [status, setStatus] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [employeeId, setEmployeeId] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [result, setResult] = useState({ requestKey: null, status: 'loading', data: null })
  const [loadingMore, setLoadingMore] = useState(false)
  const definition = reportDefinitions[reportId]
  const filters = useMemo(() => {
    const value = { limit: 50 }
    if (definition.filters.includes('period') && period) value.period = period
    if (definition.filters.includes('status') && status) value.status = status
    if (definition.filters.includes('from') && dateFrom) value.from = dateFrom
    if (definition.filters.includes('to') && dateTo) value.to = dateTo
    if (definition.filters.includes('employeeId') && employeeId) value.employeeId = employeeId
    if (definition.filters.includes('departmentId') && departmentId) {
      value.departmentId = departmentId
    }
    return value
  }, [dateFrom, dateTo, definition, departmentId, employeeId, period, status])
  const requestKey = useMemo(
    () => JSON.stringify([branchId, reportId, filters]),
    [branchId, filters, reportId],
  )
  const visibleResult = result.requestKey === requestKey
    ? result
    : { requestKey, status: 'loading', data: null }

  useEffect(() => {
    const controller = new AbortController()
    readReport(authentication, branchId, reportId, filters)
      .then((data) => {
        if (!controller.signal.aborted) setResult({ requestKey, status: 'ready', data })
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setResult({ requestKey, status: 'error', data: null })
        }
      })
    return () => controller.abort()
  }, [authentication, branchId, filters, reportId, requestKey])

  const loadMore = async () => {
    if (visibleResult.status !== 'ready' || !visibleResult.data.nextCursor || loadingMore) return
    setLoadingMore(true)
    try {
      const page = await readReport(authentication, branchId, reportId, {
        ...filters,
        cursor: visibleResult.data.nextCursor,
      })
      setResult({
        requestKey,
        status: 'ready',
        data: { ...page, rows: [...visibleResult.data.rows, ...page.rows] },
      })
    } catch {
      setResult({ requestKey, status: 'error', data: null })
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <section className="migration-reports" aria-labelledby="migration-reports-title">
      <h3 id="migration-reports-title">Reports</h3>
      <div className="report-tabs" role="tablist" aria-label="Report type">
        {Object.entries(reportDefinitions).map(([id, item]) => (
          <button
            aria-selected={id === reportId}
            className={id === reportId ? 'primary' : 'secondary'}
            key={id}
            onClick={() => setReportId(id)}
            role="tab"
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="report-filters">
        {definition.filters.includes('period') && (
          <label>
            Period
            <input type="month" value={period} onChange={(event) => setPeriod(event.target.value)} />
          </label>
        )}
        {definition.filters.includes('status') && (
          <label>
            Exact source status
            <input value={status} onChange={(event) => setStatus(event.target.value)} />
          </label>
        )}
        {definition.filters.includes('from') && (
          <label>
            From
            <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
          </label>
        )}
        {definition.filters.includes('to') && (
          <label>
            To
            <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
          </label>
        )}
        {definition.filters.includes('employeeId') && (
          <label>
            Employee ID
            <input value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} />
          </label>
        )}
        {definition.filters.includes('departmentId') && (
          <label>
            Department ID
            <input value={departmentId} onChange={(event) => setDepartmentId(event.target.value)} />
          </label>
        )}
      </div>
      {visibleResult.status === 'loading' && <p>Loading report...</p>}
      {visibleResult.status === 'error' && <p role="status">This report is unavailable.</p>}
      {visibleResult.status === 'ready' && (
        <>
          <p>{visibleResult.data.totals.rowCount} filtered row{visibleResult.data.totals.rowCount === 1 ? '' : 's'}</p>
          {visibleResult.data.rows.length === 0 ? <p>No records match these filters.</p> : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>{visibleResult.data.columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr>
                </thead>
                <tbody>
                  {visibleResult.data.rows.map((row, index) => (
                    <tr key={`${reportId}:${index}`}>
                      {visibleResult.data.columns.map((column) => <td key={column.key}>{display(row[column.key])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {visibleResult.data.nextCursor && (
            <button disabled={loadingMore} onClick={loadMore} type="button">
              {loadingMore ? 'Loading...' : 'Load more'}
            </button>
          )}
        </>
      )}
    </section>
  )
}
