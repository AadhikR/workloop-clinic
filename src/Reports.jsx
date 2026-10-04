import { useEffect, useMemo, useRef, useState } from 'react'
import { openPdf, saveDownload } from './outputDelivery.js'
import { downloadReportCsv, readReport, reportDefinitions } from './reportApi.js'
import { downloadReportPdf } from './renderedOutputApi.js'
import { readAllEmployees } from './employeeApi.js'
import { readAllDepartments } from './departmentApi.js'
import ReportPreview from './ReportPreview.jsx'

const families = {
  workforce: ['headcount', 'salaryMovement', 'turnover', 'eosLiability'],
  payroll: ['payrollCost', 'wpsCompliance', 'emiratization'],
  leave: ['leaveUtilization', 'leaveBalance'],
  attendance: ['attendanceSummary', 'overtime', 'staffingCompliance'],
  documents: ['documentExpiry'],
}
const familyLabels = { workforce: 'Workforce', payroll: 'Payroll and compliance', leave: 'Leave', attendance: 'Attendance and staffing', documents: 'Documents' }
export default function Reports({ authentication, branchId }) {
  const [family, setFamily] = useState('workforce')
  const [reportId, setReportId] = useState('headcount')
  const [inputs, setInputs] = useState({ period: '', status: '', from: '', to: '', employeeId: '', departmentId: '' })
  const [result, setResult] = useState({ status: 'loading' })
  const [choices, setChoices] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const activeKey = useRef(null)
  const definition = reportDefinitions[reportId]
  const filters = useMemo(() => Object.fromEntries([['limit', 50], ...Object.entries(inputs).filter(([key, value]) => definition.filters.includes(key) && value)]), [inputs, definition])
  const requestKey = JSON.stringify([branchId, reportId, filters])
  useEffect(() => { activeKey.current = requestKey }, [requestKey])
  const view = result.requestKey === requestKey ? result : { status: 'loading' }
  useEffect(() => {
    let active = true
    readReport(authentication, branchId, reportId, filters).then((data) => { if (active) setResult({ requestKey, status: 'ready', data }) }).catch(() => { if (active) setResult({ requestKey, status: 'error' }) })
    return () => { active = false }
  }, [authentication, branchId, reportId, filters, requestKey])
  useEffect(() => {
    let active = true
    Promise.all([readAllEmployees(authentication, branchId), readAllDepartments(authentication, branchId)]).then(([employees, departments]) => { if (active) setChoices({ branchId, employees, departments }) }).catch(() => {})
    return () => { active = false }
  }, [authentication, branchId])
  const change = (key) => (event) => setInputs({ ...inputs, [key]: event.target.value })
  const output = async (format) => {
    setBusy(true)
    setMessage(null)
    try {
      const exportFilters = Object.fromEntries(Object.entries(filters).filter(([key]) => key !== 'limit'))
      const bytes = format === 'csv' ? await downloadReportCsv(authentication, branchId, reportId, exportFilters) : await downloadReportPdf(authentication, branchId, reportId, exportFilters)
      if (activeKey.current === requestKey) { if (format === 'csv') saveDownload(bytes); else openPdf(bytes) }
    } catch { setMessage({ requestKey, text: 'The output could not be prepared. Your preview and filters are retained.' }) }
    finally { setBusy(false) }
  }
  const more = async () => {
    setBusy(true)
    try {
      const page = await readReport(authentication, branchId, reportId, { ...filters, cursor: view.data.nextCursor })
      if (page.sourceVersion !== view.data.sourceVersion || page.nextCursor === view.data.nextCursor) throw new Error('Report changed')
      if (activeKey.current === requestKey) setResult({ requestKey, status: 'ready', data: { ...page, rows: [...view.data.rows, ...page.rows] } })
    } catch { setMessage({ requestKey, text: 'More rows could not be loaded. Refresh this report to try again.' }) }
    finally { setBusy(false) }
  }
  const scopedChoices = choices?.branchId === branchId ? choices : null
  return <section className="migration-reports restoration-reports" aria-labelledby="migration-reports-title">
    <div className="module-toolbar"><div><h2 id="migration-reports-title">Reports</h2><p>Workforce and payroll reports for the selected branch</p></div></div>
    <section className="card"><div className="card-body report-filters">
      <label>Report family<select value={family} onChange={(event) => { const value = event.target.value; setFamily(value); setReportId(families[value][0]); setInputs({ period: '', status: '', from: '', to: '', employeeId: '', departmentId: '' }) }}>{Object.entries(familyLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Report type<select value={reportId} onChange={(event) => { setReportId(event.target.value); setInputs({ period: '', status: '', from: '', to: '', employeeId: '', departmentId: '' }) }}>{families[family].map((id) => <option key={id} value={id}>{reportDefinitions[id].label}</option>)}</select></label>
      {definition.filters.includes('period') && <label>Period<input type="month" value={inputs.period} onChange={change('period')} /></label>}
      {definition.filters.includes('status') && <label>Status<input value={inputs.status} onChange={change('status')} placeholder="All statuses" /></label>}
      {['from', 'to'].filter((key) => definition.filters.includes(key)).map((key) => <label key={key}>{key === 'from' ? 'From' : 'To'}<input type="date" value={inputs[key]} onChange={change(key)} /></label>)}
      {definition.filters.includes('employeeId') && <label>Employee<select value={inputs.employeeId} onChange={change('employeeId')} disabled={!scopedChoices}><option value="">All employees</option>{scopedChoices?.employees.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      {definition.filters.includes('departmentId') && <label>Department<select value={inputs.departmentId} onChange={change('departmentId')} disabled={!scopedChoices}><option value="">All departments</option>{scopedChoices?.departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
    </div></section>
    {view.status === 'loading' && <p>Loading report...</p>}{view.status === 'error' && <p role="alert">This report is unavailable.</p>}
    {message?.requestKey === requestKey && <p role="alert">{message.text}</p>}
    {view.status === 'ready' && <><ReportPreview report={view.data} title={definition.label} /><div className="actions report-output-actions"><button type="button" className="btn btn-outline" disabled={busy} onClick={() => output('csv')}>Download CSV</button><button type="button" className="btn btn-outline" disabled={busy} onClick={() => output('pdf')}>Open PDF</button>{view.data.nextCursor && <button type="button" disabled={busy} onClick={more}>Load more</button>}</div></>}
  </section>
}
