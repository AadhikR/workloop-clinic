import { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, Download } from 'lucide-react';
import { getMyPayslips, getMyEmployeeRecord } from '../../utils/profileStorage';
import { getCompany } from '../../utils/storage';
import { downloadPayslip } from '../../utils/payslipGenerator';

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function fmtAED(n) {
  return (parseFloat(n) || 0).toLocaleString('en-AE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-AE', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function EmpPayslips() {
  const [payslips, setPayslips]       = useState([]);
  const [company, setCompany]         = useState(null);
  const [emp, setEmp]                 = useState(null);
  const [loading, setLoading]         = useState(true);
  const [expandedId, setExpandedId]   = useState(null);
  const [downloading, setDownloading] = useState(null);

  useEffect(() => {
    Promise.all([
      getMyPayslips(),
      getMyEmployeeRecord(),
      getCompany(),
    ]).then(([slips, empRec, co]) => {
      setPayslips(slips);
      setEmp(empRec);
      setCompany(co);
      setLoading(false);
    });
  }, []);

  async function handleDownload(ps) {
    if (!emp || !company) return;
    setDownloading(ps.id);

    const empObj = {
      name:                emp.name,
      empNo:               emp.emp_no,
      jobTitle:            emp.job_title,
      department:          emp.department,
      iban:                emp.iban,
      bankName:            emp.bank_name,
      molId:               emp.mol_id,
      employmentStartDate: emp.employment_start_date,
      basicSalary:         parseFloat(emp.basic_salary) || 0,
    };

    // Reconstruct the run-like object that generatePayslipPDF expects
    const run   = { id: ps.payrollRunId, period: ps.period, paymentDate: ps.paymentDate, status: 'generated' };
    const entry = { ...ps.snapshot, employeeId: ps.employeeId };

    try {
      await downloadPayslip(company, empObj, run, entry);
    } catch (err) {
      console.error('payslip PDF error:', err);
    }
    setDownloading(null);
  }

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>;

  return (
    <div>
      <div className="emp-page-header">
        <h2>My Payslips</h2>
        <p>{payslips.length} payslip{payslips.length !== 1 ? 's' : ''}</p>
      </div>

      <div className="emp-page-body">
        {payslips.length === 0
          ? <div className="empty-state"><p>No payslips available yet.</p></div>
          : payslips.map(ps => {
              const [year, month] = ps.period.split('-').map(Number);
              const label    = `${MONTHS[month - 1]} ${year}`;
              const snap     = ps.snapshot ?? {};
              const expanded = expandedId === ps.id;

              const gross = ps.grossPay;
              const totalDeductions =
                (snap.deductions || []).reduce((s, d) => s + (parseFloat(d.amount) || 0), 0) +
                (parseFloat(snap.leaveDeduction) || 0) +
                (parseFloat(snap.duCost) || 0);
              const net = ps.netPay;

              return (
                <div key={ps.id} className="emp-card" style={{ marginBottom: 12 }}>
                  {/* Summary row */}
                  <div
                    style={{ padding: '14px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                    onClick={() => setExpandedId(expanded ? null : ps.id)}
                  >
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--gray-900)' }}>{label}</div>
                      <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                        Payment: {fmtDate(ps.paymentDate)}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--success)' }}>
                          AED {fmtAED(net)}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--gray-400)' }}>net pay</div>
                      </div>
                      {expanded ? <ChevronUp size={15} color="var(--gray-400)" /> : <ChevronDown size={15} color="var(--gray-400)" />}
                    </div>
                  </div>

                  {/* Detail breakdown */}
                  {expanded && (
                    <div style={{ borderTop: '1px solid rgba(100,116,139,0.10)', padding: '12px 16px' }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 10 }}>
                        Earnings
                      </div>
                      {[
                        { label: 'Basic Salary',        amount: snap.basicSalary },
                        { label: 'Housing Allowance',    amount: snap.housingAllowance },
                        { label: 'Transport Allowance',  amount: snap.transportAllowance },
                        // Show fixed allowance only when there is no housing/transport breakdown
                        ...(!parseFloat(snap.housingAllowance) && !parseFloat(snap.transportAllowance) && parseFloat(snap.allowance) > 0
                          ? [{ label: 'Fixed Allowance', amount: snap.allowance }]
                          : []),
                        { label: 'Bonus / Incentive',    amount: snap.bonus },
                        { label: 'Other Pay',            amount: snap.otherPay },
                        ...(snap.additionalAllowances || []).map(a => ({ label: a.label, amount: a.amount })),
                      ].filter(r => parseFloat(r.amount) > 0).map((row, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '3px 0' }}>
                          <span style={{ color: 'var(--gray-600)' }}>{row.label}</span>
                          <span style={{ color: 'var(--gray-800)', fontWeight: 500 }}>AED {fmtAED(row.amount)}</span>
                        </div>
                      ))}
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, fontWeight: 700, borderTop: '1px solid rgba(100,116,139,0.14)', marginTop: 6, paddingTop: 6 }}>
                        <span>Gross</span>
                        <span>AED {fmtAED(gross)}</span>
                      </div>

                      {totalDeductions > 0 && (
                        <>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '14px 0 8px' }}>
                            Deductions
                          </div>
                          {(snap.deductions || []).map((d, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '3px 0' }}>
                              <span style={{ color: 'var(--gray-600)' }}>{d.label}</span>
                              <span style={{ color: 'var(--danger)', fontWeight: 500 }}>− AED {fmtAED(d.amount)}</span>
                            </div>
                          ))}
                          {parseFloat(snap.leaveDeduction) > 0 && (
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '3px 0' }}>
                              <span style={{ color: 'var(--gray-600)' }}>Leave Deduction</span>
                              <span style={{ color: 'var(--danger)', fontWeight: 500 }}>− AED {fmtAED(snap.leaveDeduction)}</span>
                            </div>
                          )}
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, fontWeight: 700, borderTop: '1px solid rgba(100,116,139,0.14)', marginTop: 6, paddingTop: 6 }}>
                            <span>Total Deductions</span>
                            <span style={{ color: 'var(--danger)' }}>− AED {fmtAED(totalDeductions)}</span>
                          </div>
                        </>
                      )}

                      <div style={{
                        display: 'flex', justifyContent: 'space-between', fontSize: 15, fontWeight: 800,
                        borderTop: '2px solid var(--gray-900)', marginTop: 10, paddingTop: 10,
                        color: 'var(--success)',
                      }}>
                        <span style={{ color: 'var(--gray-900)' }}>Net Pay</span>
                        <span>AED {fmtAED(net)}</span>
                      </div>

                      <button
                        className="btn btn-outline btn-sm"
                        style={{ marginTop: 14, width: '100%', justifyContent: 'center' }}
                        disabled={downloading === ps.id}
                        onClick={() => handleDownload(ps)}
                      >
                        <Download size={13} />
                        {downloading === ps.id ? 'Generating…' : 'Download PDF'}
                      </button>
                    </div>
                  )}
                </div>
              );
            })
        }
      </div>
    </div>
  );
}
