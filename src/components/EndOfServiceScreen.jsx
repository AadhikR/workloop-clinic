/**
 * EndOfServiceScreen.jsx — UAE End-of-Service Settlement Calculator
 *
 * Implements full MOHRE gratuity rules:
 *   - Daily rate = Basic ÷ 30
 *   - 1–5 years: 21 days/year
 *   - > 5 years: 30 days/year (ALL years)
 *   - Resignation partial: 1–3yr = 1/3, 3–5yr = 2/3, >5yr = full
 *   - Termination: always full
 *   - Cap: 24 months basic salary
 *   - Last working day is included in service period
 */
import { useState, useEffect } from 'react';
import { X, Calculator, Download } from 'lucide-react';
import { calculateEndOfService } from '../utils/gratuityCalculator';
import { calculateLeaveEncashment } from '../utils/leaveEngine';
import { formatAED, formatDateUAE } from '../utils/uaeValidators';
import { getAdvances } from '../utils/storage';

export default function EndOfServiceScreen({ employee, onClose }) {
  const today = new Date().toISOString().split('T')[0];

  const [terminationDate, setTerminationDate]   = useState(employee.terminationDate || today);
  const [outstandingAdvances, setOutstandingAdvances] = useState('0');
  const [advancesLoaded, setAdvancesLoaded]           = useState(false);
  const [unusedLeaveDays, setUnusedLeaveDays]   = useState('0');
  const [reason, setReason]                     = useState(
    employee.terminationReason?.toLowerCase().includes('resign') ? 'Resignation' : 'Termination'
  );
  const [result, setResult] = useState(null);

  // Auto-load outstanding advance balance from the Advances module
  useEffect(() => {
    if (!employee?.id) return;
    getAdvances(employee.id)
      .then(advances => {
        const total = advances
          .filter(a => a.status === 'active')
          .reduce((s, a) => s + a.outstandingBalance, 0);
        if (total > 0) {
          setOutstandingAdvances(total.toFixed(2));
        }
        setAdvancesLoaded(true);
      })
      .catch(() => setAdvancesLoaded(true)); // fail silently — table may not exist yet
  }, [employee?.id]);

  const calculate = () => {
    const startDate = employee.startDate || employee.employmentStartDate;
    if (!startDate) {
      alert('Employee start date is not set. Please update the employee profile first.');
      return;
    }
    const settlement = calculateEndOfService(
      employee,
      terminationDate,
      parseFloat(outstandingAdvances) || 0,
      reason
    );
    // Art. 29 — Leave encashment: unused annual leave days × (basic/30)
    const leaveEnc = calculateLeaveEncashment(
      parseFloat(unusedLeaveDays) || 0,
      employee.basicSalary
    );
    setResult({ ...settlement, leaveEncashment: leaveEnc });
  };

  const printSettlement = () => {
    if (!result) return;
    const serviceLabel = result.gratuity?.serviceLabel || '';
    const win = window.open('', '_blank');
    win.document.write(`
      <html><head><title>End of Service Settlement — ${employee.name}</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 40px; color: #111; }
        h1 { color: #1a56db; font-size: 22px; }
        h2 { font-size: 16px; color: #374151; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; margin-top: 24px; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        td { padding: 8px 12px; border-bottom: 1px solid #f3f4f6; font-size: 14px; }
        td:last-child { text-align: right; font-weight: 600; }
        .total { background: #eff6ff; font-weight: 700; font-size: 16px; }
        .deduct { color: #c81e1e; }
        .footer { margin-top: 40px; font-size: 12px; color: #9ca3af; }
      </style></head><body>
      <h1>End-of-Service Settlement</h1>
      <p><strong>Employee:</strong> ${result.employee}</p>
      <p><strong>Contract Type:</strong> ${result.contractType} &nbsp;|&nbsp; <strong>Reason:</strong> ${result.reason}</p>
      <p><strong>Start Date:</strong> ${formatDateUAE(result.startDate)} &nbsp;|&nbsp; <strong>Last Working Day:</strong> ${formatDateUAE(result.terminationDate)}</p>
      <p><strong>Service Period:</strong> ${serviceLabel}</p>
      <p><strong>Unused Annual Leave:</strong> ${result.leaveEncashment?.unusedDays || 0} days = ${formatAED(result.leaveEncashment?.encashmentAmount || 0)} (Art. 29 encashment)</p>

      <h2>Final Month Salary (Pro-rata)</h2>
      <table>
        <tr><td>Days Worked in Final Month</td><td>${result.daysWorked} / ${result.daysInMonth} days</td></tr>
        <tr><td>Monthly Total Package</td><td>${formatAED(result.totalMonthly)}</td></tr>
        <tr><td>Pro-rata Final Salary</td><td>${formatAED(result.proRataFinalSalary)}</td></tr>
      </table>

      <h2>Gratuity / EOSB (UAE Labour Law)</h2>
      <table>
        <tr><td>Service Period</td><td>${serviceLabel}</td></tr>
        <tr><td>Eligible</td><td>${result.gratuity.eligible ? 'Yes' : 'No (< 1 year service)'}</td></tr>
        ${result.gratuity.eligible ? `
        <tr><td>Daily Rate (Basic ÷ 30)</td><td>${formatAED(result.gratuity.dailyRate)}</td></tr>
        <tr><td>Calculation</td><td>${result.gratuity.breakdown}</td></tr>
        <tr><td>Full Gratuity Entitlement</td><td>${formatAED(result.gratuity.gratuityFull)}</td></tr>
        <tr><td>Entitlement Factor</td><td>${result.gratuity.reductionLabel}</td></tr>
        <tr><td>Gratuity After Reduction</td><td>${formatAED(result.gratuity.gratuityRaw)}</td></tr>
        <tr><td>2-Year Cap</td><td>${formatAED(result.gratuity.cap)}</td></tr>
        <tr><td>Gratuity Payable</td><td>${formatAED(result.gratuity.gratuityCapped)}</td></tr>
        ` : ''}
      </table>

      <h2>Settlement Summary</h2>
      <table>
        <tr><td>Pro-rata Final Salary</td><td>${formatAED(result.proRataFinalSalary)}</td></tr>
        <tr><td>Gratuity / EOSB</td><td>${formatAED(result.gratuity.gratuityCapped)}</td></tr>
        ${(result.leaveEncashment?.encashmentAmount || 0) > 0 ? `<tr><td>Annual Leave Encashment (Art. 29)</td><td>${formatAED(result.leaveEncashment.encashmentAmount)}</td></tr>` : ''}
        <tr><td>Total Gross</td><td>${formatAED((result.totalGross || 0) + (result.leaveEncashment?.encashmentAmount || 0))}</td></tr>
        ${result.outstandingAdvances > 0 ? `<tr class="deduct"><td>Outstanding Advances</td><td>- ${formatAED(result.outstandingAdvances)}</td></tr>` : ''}
        <tr class="total"><td>NET SETTLEMENT PAYABLE</td><td>${formatAED((result.totalGross || 0) + (result.leaveEncashment?.encashmentAmount || 0) - (result.outstandingAdvances || 0))}</td></tr>
      </table>

      <div class="footer">
        Generated by Workloop — UAE Payroll &amp; HRMS &nbsp;|&nbsp; ${formatDateUAE(today)}
      </div>
      </body></html>
    `);
    win.document.close();
    win.print();
  };

  const serviceLabel = result?.gratuity?.serviceLabel || '';

  return (
    <div className="modal-overlay">
      <div className="modal modal-lg">
        <div className="modal-header">
          <h3><Calculator size={16} style={{ marginRight:6 }}/>End-of-Service Settlement — {employee.name}</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18}/></button>
        </div>

        <div className="modal-body">
          {/* Input section */}
          <div className="card mb-4">
            <div className="card-header"><h3>Settlement Parameters</h3></div>
            <div className="card-body">
              <div className="form-grid form-grid-2">
                <div className="form-group">
                  <label>Employment Start Date</label>
                  <input
                    className="form-control"
                    type="date"
                    value={employee.startDate || employee.employmentStartDate || ''}
                    disabled
                  />
                  <span className="hint">From employee profile</span>
                </div>
                <div className="form-group">
                  <label>Last Working Day *</label>
                  <input
                    className="form-control"
                    type="date"
                    value={terminationDate}
                    onChange={e => { setTerminationDate(e.target.value); setResult(null); }}
                  />
                  <span className="hint">This day is included in the service period</span>
                </div>
                <div className="form-group">
                  <label>Contract Type</label>
                  <input className="form-control" value={employee.contractType || 'Unlimited'} disabled/>
                </div>
                <div className="form-group">
                  <label>Unused Annual Leave Days (Art. 29)</label>
                  <input
                    className="form-control"
                    type="number"
                    min="0"
                    step="0.5"
                    value={unusedLeaveDays}
                    onChange={e => { setUnusedLeaveDays(e.target.value); setResult(null); }}
                    placeholder="0"
                  />
                  <span className="hint">Unused annual leave is encashable on exit — check Leave module for balance</span>
                </div>
                <div className="form-group">
                  <label>Reason for Leaving *</label>
                  <select
                    className="form-control"
                    value={reason}
                    onChange={e => { setReason(e.target.value); setResult(null); }}
                  >
                    <option value="Termination">Termination (without misconduct)</option>
                    <option value="Resignation">Resignation</option>
                  </select>
                  <span className="hint">
                    Resignation may reduce entitlement: 1–3yr = 1/3, 3–5yr = 2/3, &gt;5yr = full
                  </span>
                </div>
                <div className="form-group">
                  <label>Basic Salary (AED)</label>
                  <input className="form-control" value={formatAED(employee.basicSalary)} disabled/>
                  <span className="hint">Gratuity is calculated on basic salary only</span>
                </div>
                <div className="form-group">
                  <label>Outstanding Salary Advances (AED)</label>
                  <input
                    className="form-control"
                    type="number"
                    min="0"
                    step="0.01"
                    value={outstandingAdvances}
                    onChange={e => { setOutstandingAdvances(e.target.value); setResult(null); }}
                    placeholder="0.00"
                  />
                  <span className="hint">
                    {advancesLoaded
                      ? 'Auto-loaded from Advances module. Edit to override.'
                      : 'Will be deducted from total settlement'}
                  </span>
                </div>
              </div>
              <div style={{ marginTop:16 }}>
                <button className="btn btn-primary" onClick={calculate}>
                  <Calculator size={15}/> Calculate Settlement
                </button>
              </div>
            </div>
          </div>

          {/* Results */}
          {result && (
            <>
              {/* Service summary */}
              <div className="alert alert-info mb-4">
                <div>
                  <strong>{result.employee}</strong> &nbsp;|&nbsp;
                  {result.contractType} Contract &nbsp;|&nbsp;
                  {result.reason} &nbsp;|&nbsp;
                  Start: {formatDateUAE(result.startDate)} → Last Day: {formatDateUAE(result.terminationDate)} &nbsp;|&nbsp;
                  Service: <strong>{serviceLabel}</strong>
                </div>
              </div>

              <div className="form-grid form-grid-2" style={{ gap:16 }}>
                {/* Pro-rata salary */}
                <div className="card">
                  <div className="card-header"><h3>Final Month Salary (Pro-rata)</h3></div>
                  <div className="card-body" style={{ padding:0 }}>
                    <table>
                      <tbody>
                        <tr>
                          <td>Days Worked</td>
                          <td className="text-right">{result.daysWorked} / {result.daysInMonth} days</td>
                        </tr>
                        <tr>
                          <td>Basic Salary</td>
                          <td className="text-right">{formatAED(result.basicSalary)}</td>
                        </tr>
                        {result.housingAllowance > 0 && (
                          <tr><td>Housing Allowance</td><td className="text-right">{formatAED(result.housingAllowance)}</td></tr>
                        )}
                        {result.transportAllowance > 0 && (
                          <tr><td>Transport Allowance</td><td className="text-right">{formatAED(result.transportAllowance)}</td></tr>
                        )}
                        {result.otherAllowances > 0 && (
                          <tr><td>Other Allowances</td><td className="text-right">{formatAED(result.otherAllowances)}</td></tr>
                        )}
                        <tr style={{ background:'var(--success-light)', fontWeight:700 }}>
                          <td>Pro-rata Final Salary</td>
                          <td className="text-right" style={{ color:'var(--success)' }}>{formatAED(result.proRataFinalSalary)}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Gratuity */}
                <div className="card">
                  <div className="card-header"><h3>Gratuity / EOSB</h3></div>
                  <div className="card-body" style={{ padding:0 }}>
                    {!result.gratuity.eligible ? (
                      <div style={{ padding:'16px 20px', color:'var(--gray-500)', fontSize:13 }}>
                        <strong>Not eligible</strong> — less than 1 year of service.
                        <br/>Service: {serviceLabel}
                      </div>
                    ) : (
                      <table>
                        <tbody>
                          <tr>
                            <td>Service Period</td>
                            <td className="text-right" style={{ fontWeight:600 }}>{serviceLabel}</td>
                          </tr>
                          <tr>
                            <td>Daily Rate (Basic ÷ 30)</td>
                            <td className="text-right">{formatAED(result.gratuity.dailyRate)}</td>
                          </tr>
                          <tr>
                            <td>Calculation</td>
                            <td className="text-right text-sm" style={{ color:'var(--gray-500)' }}>{result.gratuity.breakdown}</td>
                          </tr>
                          <tr>
                            <td>Full Gratuity Entitlement</td>
                            <td className="text-right">{formatAED(result.gratuity.gratuityFull)}</td>
                          </tr>
                          {result.gratuity.reductionFactor < 1 && (
                            <tr style={{ color:'var(--warning)' }}>
                              <td>Entitlement Factor</td>
                              <td className="text-right text-sm">{result.gratuity.reductionLabel}</td>
                            </tr>
                          )}
                          {result.gratuity.reductionFactor < 1 && (
                            <tr>
                              <td>Gratuity After Reduction</td>
                              <td className="text-right">{formatAED(result.gratuity.gratuityRaw)}</td>
                            </tr>
                          )}
                          <tr>
                            <td>2-Year Cap</td>
                            <td className="text-right text-sm" style={{ color:'var(--gray-500)' }}>{formatAED(result.gratuity.cap)}</td>
                          </tr>
                          <tr style={{ background:'var(--success-light)', fontWeight:700 }}>
                            <td>Gratuity Payable {result.gratuity.capped ? '(capped)' : ''}</td>
                            <td className="text-right" style={{ color:'var(--success)' }}>{formatAED(result.gratuity.gratuityCapped)}</td>
                          </tr>
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </div>

              {/* Net settlement */}
              <div className="card mt-4">
                <div className="card-header"><h3>Total Settlement Summary</h3></div>
                <div className="card-body" style={{ padding:0 }}>
                  <table>
                    <tbody>
                      <tr>
                        <td>Pro-rata Final Salary</td>
                        <td className="text-right">{formatAED(result.proRataFinalSalary)}</td>
                      </tr>
                      <tr>
                        <td>Gratuity / EOSB</td>
                        <td className="text-right">{formatAED(result.gratuity.gratuityCapped)}</td>
                      </tr>
                      {/* Art. 29 — Annual leave encashment */}
                      {(result.leaveEncashment?.encashmentAmount || 0) > 0 && (
                        <tr>
                          <td>
                            Annual Leave Encashment (Art. 29)
                            <span className="text-sm text-muted" style={{ marginLeft:8 }}>
                              {result.leaveEncashment.unusedDays} days × {formatAED(result.leaveEncashment.dailyRate)}/day
                            </span>
                          </td>
                          <td className="text-right">{formatAED(result.leaveEncashment.encashmentAmount)}</td>
                        </tr>
                      )}
                      <tr style={{ fontWeight:600 }}>
                        <td>Total Gross</td>
                        <td className="text-right">
                          {formatAED(result.totalGross + (result.leaveEncashment?.encashmentAmount || 0))}
                        </td>
                      </tr>
                      {result.outstandingAdvances > 0 && (
                        <tr style={{ color:'var(--danger)' }}>
                          <td>Less: Outstanding Advances</td>
                          <td className="text-right">- {formatAED(result.outstandingAdvances)}</td>
                        </tr>
                      )}
                      <tr style={{ background:'var(--primary-light)', fontWeight:700, fontSize:15 }}>
                        <td style={{ color:'var(--primary-dark)' }}>NET SETTLEMENT PAYABLE</td>
                        <td className="text-right" style={{ color:'var(--primary)' }}>
                          {formatAED(result.totalGross + (result.leaveEncashment?.encashmentAmount || 0) - result.outstandingAdvances)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>Close</button>
          {result && (
            <button className="btn btn-primary" onClick={printSettlement}>
              <Download size={15}/> Print / Save Settlement
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
