import { useState } from 'react';
import { X, Download, Save, ShieldCheck, AlertTriangle } from 'lucide-react';
import { saveNafisReport } from '../utils/storage';

function exportCSV(emiratiEmps, period) {
  const header = ['Emp No', 'Full Name', 'Job Title', 'Department', 'Nafis Reg. No', 'Employment Start Date', 'Status'];
  const rows = emiratiEmps.map(e => [
    e.empNo ?? '',
    `"${(e.name ?? '').replace(/"/g, '""')}"`,
    `"${(e.jobTitle ?? '').replace(/"/g, '""')}"`,
    `"${(e.department ?? '').replace(/"/g, '""')}"`,
    e.nafisRegistrationNo ?? '',
    e.startDate || e.employmentStartDate || '',
    e.employmentStatus ?? '',
  ].join(','));

  const csv = [header.join(','), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `Nafis_Emiratization_Report_${period}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function NafisReportModal({ employees, company, onClose }) {
  const today  = new Date();
  const period = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
  const monthLabel = today.toLocaleString('en-AE', { month: 'long', year: 'numeric' });

  const activeEmps    = employees.filter(e => e.active !== false && e.employmentStatus !== 'Terminated');
  const emiratiEmps   = activeEmps.filter(e => e.nationality === 'United Arab Emirates');
  const totalHeadcount = activeEmps.length;
  const emiratiCount  = emiratiEmps.length;
  const ratio         = totalHeadcount > 0 ? (emiratiCount / totalHeadcount) * 100 : 0;
  const required      = parseFloat(company?.nafisQuotaPercent) || 2;
  const compliant     = ratio >= required;
  const gap           = Math.max(0, Math.ceil((required / 100) * totalHeadcount) - emiratiCount);
  const potentialFine = gap * 6000;

  // Employees missing Nafis registration number
  const missingNafis = emiratiEmps.filter(e => !e.nafisRegistrationNo);

  const [saved, setSaved]   = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState('');

  const handleSave = async () => {
    setSaving(true);
    setSaveErr('');
    try {
      await saveNafisReport({
        period,
        totalHeadcount,
        emiratiCount,
        ratioPercent:    parseFloat(ratio.toFixed(2)),
        requiredPercent: required,
        compliant,
        snapshot: emiratiEmps.map(e => ({
          id:                 e.id,
          name:               e.name,
          jobTitle:           e.jobTitle ?? '',
          department:         e.department ?? '',
          nafisRegistrationNo: e.nafisRegistrationNo ?? '',
        })),
      });
      setSaved(true);
    } catch (err) {
      setSaveErr(err.message || 'Failed to save report.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal modal-lg">
        <div className="modal-header">
          <h3>
            <ShieldCheck size={16} style={{ marginRight:6 }} />
            Emiratization / Nafis Compliance Report — {monthLabel}
          </h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="modal-body">

          {/* Status banner */}
          <div className={`alert ${compliant ? 'alert-info' : 'alert-danger'} mb-4`}>
            {compliant ? <ShieldCheck size={15} /> : <AlertTriangle size={15} />}
            <div>
              {compliant
                ? <><strong>Compliant</strong> — Current rate {ratio.toFixed(1)}% meets the {required}% target for {company?.sector || 'your sector'}.</>
                : <><strong>Non-Compliant</strong> — Current rate <strong>{ratio.toFixed(1)}%</strong> ({emiratiCount} UAE national{emiratiCount !== 1 ? 's' : ''})
                    is below the required <strong>{required}%</strong> for {company?.sector || 'your sector'}.
                    {gap > 0 && <> Hire <strong>{gap} more UAE national{gap !== 1 ? 's' : ''}</strong> to comply.
                    Potential fine: <strong>AED {potentialFine.toLocaleString('en-AE')} / month</strong>.</>}
                  </>
              }
            </div>
          </div>

          {/* Ratio visual */}
          <div className="card mb-4">
            <div className="card-header"><h3>Compliance Overview</h3></div>
            <div className="card-body">
              <div style={{ display:'flex', alignItems:'center', gap:28, flexWrap:'wrap' }}>

                {/* Current % */}
                <div style={{ textAlign:'center', minWidth:90 }}>
                  <div style={{ fontSize:40, fontWeight:800, lineHeight:1, color: compliant ? 'var(--success)' : 'var(--danger)' }}>
                    {ratio.toFixed(1)}%
                  </div>
                  <div style={{ fontSize:11, color:'var(--gray-500)', marginTop:5 }}>Current Rate</div>
                </div>

                {/* Bar */}
                <div style={{ flex:1, minWidth:180 }}>
                  <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, color:'var(--gray-400)', marginBottom:5 }}>
                    <span>0%</span>
                    <span style={{ fontWeight:600, color:'var(--gray-600)' }}>Required: {required}%</span>
                  </div>
                  <div style={{ height:14, background:'var(--gray-200)', borderRadius:7, overflow:'hidden', position:'relative' }}>
                    {/* Target marker */}
                    <div style={{ position:'absolute', top:0, bottom:0, left:`${Math.min(required, 100)}%`, width:2, background:'var(--gray-600)', zIndex:2 }} />
                    {/* Fill */}
                    <div style={{ height:'100%', width:`${Math.min(ratio, 100)}%`, background: compliant ? 'var(--success)' : 'var(--danger)', borderRadius:7, transition:'width 0.4s' }} />
                  </div>
                  <div style={{ marginTop:8, fontSize:13 }}>
                    <strong>{emiratiCount}</strong> UAE national{emiratiCount !== 1 ? 's' : ''}{' '}
                    of <strong>{totalHeadcount}</strong> active employees
                  </div>
                  {!compliant && gap > 0 && (
                    <div style={{ marginTop:5, fontSize:12.5, color:'var(--danger)', fontWeight:600 }}>
                      {gap} more needed · AED {potentialFine.toLocaleString('en-AE')} / month at risk
                    </div>
                  )}
                </div>

                {/* Required % */}
                <div style={{ textAlign:'center', minWidth:90 }}>
                  <div style={{ fontSize:40, fontWeight:800, lineHeight:1, color:'var(--gray-500)' }}>
                    {required}%
                  </div>
                  <div style={{ fontSize:11, color:'var(--gray-500)', marginTop:5 }}>Required</div>
                </div>
              </div>

              {/* Summary row */}
              <div style={{ marginTop:18, display:'flex', gap:16, flexWrap:'wrap' }}>
                {[
                  { label:'Total Active Headcount', value: totalHeadcount },
                  { label:'UAE Nationals',           value: emiratiCount, color: compliant ? 'var(--success)' : 'var(--danger)' },
                  { label:'Non-UAE Employees',       value: totalHeadcount - emiratiCount },
                  { label:'Target Rate',             value: `${required}%` },
                  { label:'Actual Rate',             value: `${ratio.toFixed(1)}%`, color: compliant ? 'var(--success)' : 'var(--danger)' },
                ].map(item => (
                  <div key={item.label} style={{ flex:1, minWidth:110, background:'var(--gray-50)', borderRadius:8, padding:'10px 14px', border:'1px solid var(--gray-200)' }}>
                    <div style={{ fontSize:18, fontWeight:700, color: item.color || 'var(--gray-800)' }}>{item.value}</div>
                    <div style={{ fontSize:11, color:'var(--gray-500)', marginTop:2 }}>{item.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Missing Nafis reg numbers */}
          {missingNafis.length > 0 && (
            <div className="alert alert-warning mb-4">
              <AlertTriangle size={15} />
              <div>
                <strong>{missingNafis.length} UAE national{missingNafis.length !== 1 ? 's' : ''} missing Nafis registration number:</strong>{' '}
                {missingNafis.map(e => e.name).join(', ')}.
                Add the number in the UAE Compliance tab of their employee profile.
              </div>
            </div>
          )}

          {/* Employee table */}
          <div className="card">
            <div className="card-header">
              <h3>UAE National Employees ({emiratiCount})</h3>
            </div>
            {emiratiEmps.length === 0 ? (
              <div style={{ padding:'24px 20px', color:'var(--gray-500)', textAlign:'center', fontSize:14 }}>
                No UAE national employees on record. Set <strong>Nationality = United Arab Emirates</strong> in the UAE Compliance tab of each employee profile.
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Emp No.</th>
                      <th>Name</th>
                      <th>Job Title</th>
                      <th>Department</th>
                      <th>Nafis Reg. No.</th>
                      <th>Start Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {emiratiEmps.map(emp => (
                      <tr key={emp.id}>
                        <td style={{ color:'var(--gray-500)', fontSize:12 }}>{emp.empNo || '—'}</td>
                        <td style={{ fontWeight:600 }}>{emp.name}</td>
                        <td>{emp.jobTitle || '—'}</td>
                        <td>{emp.department || '—'}</td>
                        <td style={{ fontFamily:'monospace', fontSize:12 }}>
                          {emp.nafisRegistrationNo
                            ? <span style={{ color:'var(--success)', fontWeight:600 }}>{emp.nafisRegistrationNo}</span>
                            : <span style={{ color:'var(--warning)', fontWeight:600 }}>Not set</span>
                          }
                        </td>
                        <td style={{ fontSize:12 }}>{emp.startDate || emp.employmentStartDate || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {saveErr && (
            <div className="alert alert-danger mt-3">
              <AlertTriangle size={15} /> {saveErr}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>Close</button>
          <button
            className="btn btn-outline"
            onClick={() => exportCSV(emiratiEmps, period)}
            disabled={emiratiEmps.length === 0}
          >
            <Download size={14} /> Export CSV
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving || saved}
          >
            <Save size={14} />
            {saved ? 'Saved' : saving ? 'Saving…' : 'Save Report Snapshot'}
          </button>
        </div>
      </div>
    </div>
  );
}
