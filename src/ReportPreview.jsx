const charts = {
  headcount: [['department', 'By department'], ['nationality', 'By nationality'], ['gender', 'By gender']],
  payrollCost: [['period', 'Payroll cost by period', 'net']],
  leaveUtilization: [['leaveType', 'Leave days by type', 'days']],
  attendanceSummary: [['department', 'Attendance hours by department', 'hours']],
  overtime: [['department', 'Overtime hours by department', 'hours']],
  documentExpiry: [['documentType', 'Expiring documents by type']],
  salaryMovement: [['department', 'Salary changes by department']],
  turnover: [['eventType', 'Joiners and leavers']],
  staffingCompliance: [['department', 'Staffing shortages by department', 'shortage']],
  wpsCompliance: [['entryStatus', 'WPS payment states']],
  emiratization: [['period', 'Emiratization rate by period', 'ratioPercent']],
  eosLiability: [['department', 'End of service liability by department', 'liability']],
  leaveBalance: [['leaveType', 'Leave balances by type', 'remaining']],
}

function Distribution({ rows, field, title, measure, partial }) {
  if (!rows.some((row) => Object.hasOwn(row, field))) return null
  const grouped = new Map()
  for (const row of rows) {
    if (measure && (row[measure] === null || !Number.isFinite(Number(row[measure])))) continue
    const label = row[field] == null || row[field] === '' ? 'Unspecified' : String(row[field])
    grouped.set(label, (grouped.get(label) ?? 0) + (measure ? Number(row[measure]) : 1))
  }
  const values = [...grouped].sort(([a], [b]) => a.localeCompare(b))
  const maximum = Math.max(1, ...values.map(([, value]) => Math.abs(value)))
  return <figure className="report-chart"><figcaption>{title}{partial && <small>Loaded records only. Load more to include the remaining records.</small>}</figcaption><ul>{values.map(([label, value]) => <li key={label}><span>{label}</span><span className="report-bar-track"><span className="report-bar" style={{ width: `${Math.abs(value) / maximum * 100}%` }} /></span><strong>{measure ? value.toLocaleString('en-AE', { maximumFractionDigits: 2 }) : value}</strong></li>)}</ul></figure>
}

export default function ReportPreview({ report, title }) {
  const numeric = new Set(['decimal', 'integer'])
  return <section className="card report-preview" data-report-family={report.reportId}>
    <div className="card-header"><h3>{title}</h3><span>{report.totals.rowCount} records</span></div>
    {Object.keys(report.totals.values).length > 0 && <div className="stats-grid report-totals">{Object.entries(report.totals.values).map(([key, value]) => <article key={key} className="stat-card"><div className="stat-label">{report.columns.find((column) => column.key === key)?.label ?? key}</div><div className="stat-value">{String(value)}</div></article>)}</div>}
    {report.rows.length > 0 && <div className="report-charts">{(charts[report.reportId] ?? []).map(([field, label, measure]) => <Distribution key={field} rows={report.rows} field={field} title={label} measure={measure} partial={report.rows.length < report.totals.rowCount} />)}</div>}
    {report.rows.length === 0 ? <div className="empty-state"><h4>No data</h4><p>No records match the current filters.</p></div> : <div className="table-wrap"><table><thead><tr>{report.columns.map((column) => <th key={column.key} className={numeric.has(column.type) ? 'text-right' : ''}>{column.label}</th>)}</tr></thead><tbody>{report.rows.map((row, index) => <tr key={index}>{report.columns.map((column) => <td key={column.key} className={numeric.has(column.type) ? 'text-right' : ''}>{row[column.key] === null ? 'Unavailable' : typeof row[column.key] === 'boolean' ? row[column.key] ? 'Yes' : 'No' : String(row[column.key])}</td>)}</tr>)}</tbody></table></div>}
  </section>
}
