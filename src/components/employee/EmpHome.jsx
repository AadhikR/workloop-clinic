import { useEffect, useState } from 'react';
import { CalendarDays, Clock, FileText, ChevronRight, AlertCircle, Package } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getMyEmployeeRecord, getMyPayslips } from '../../utils/profileStorage';
import { getLeaveBalances, getLeaveRequests, getLeaveTypes } from '../../utils/leaveStorage';
import { calculateAnnualLeaveAccrual } from '../../utils/leaveEngine';
import { getAttendanceRecords } from '../../utils/attendanceStorage';
import { getEmployeeCurrentAssets } from '../../utils/assetStorage';
import { ATTENDANCE_STATUS, STATUS_LABELS, STATUS_COLORS } from '../../utils/attendanceEngine';

const UAE_TZ_OFFSET = 4 * 60; // GMT+4 in minutes

function todayUAE() {
  const now = new Date();
  const uae = new Date(now.getTime() + (UAE_TZ_OFFSET - now.getTimezoneOffset()) * 60000);
  return uae.toISOString().split('T')[0];
}

function greetingFor(name) {
  const hour = new Date().getHours();
  const first = (name || '').split(' ')[0];
  if (hour < 12) return `Good morning, ${first}`;
  if (hour < 17) return `Good afternoon, ${first}`;
  return `Good evening, ${first}`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-AE', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function EmpHome({ onNavigate }) {
  const { profile } = useAuth();
  const [emp, setEmp]               = useState(null);
  const [balances, setBalances]     = useState([]);
  const [requests, setRequests]     = useState([]);
  const [lastPayslip, setLastPayslip] = useState(null);
  const [todayRec, setTodayRec]     = useState(null);
  const [myAssets, setMyAssets]     = useState([]);
  const [loading, setLoading]       = useState(true);

  useEffect(() => {
    if (!profile?.employeeId) return;
    const today = todayUAE();
    const year  = new Date().getFullYear();

    Promise.all([
      getMyEmployeeRecord(),
      getLeaveBalances(profile.employeeId, year),
      getLeaveRequests({ employeeId: profile.employeeId }),
      getMyPayslips(),
      getAttendanceRecords({ employeeId: profile.employeeId, dateFrom: today, dateTo: today }),
      getLeaveTypes(),
      getEmployeeCurrentAssets(profile.employeeId).catch(() => []),
    ]).then(([empRec, bal, reqs, slips, attRecs, lts, assets]) => {
      setEmp(empRec);

      let resolvedBal = bal;
      if (bal.length === 0 && empRec && lts.length > 0) {
        const startDate = empRec.employment_start_date || empRec.startDate;
        const accrual = startDate ? calculateAnnualLeaveAccrual(startDate, new Date()) : null;
        const approvedAnnual = reqs
          .filter(r => r.leaveTypeCode === 'ANNUAL' && r.status === 'Approved' && r.startDate?.startsWith(String(year)))
          .reduce((s, r) => s + (parseFloat(r.daysRequested) || 0), 0);
        const pendingAnnual = reqs
          .filter(r => r.leaveTypeCode === 'ANNUAL' && r.status === 'Pending' && r.startDate?.startsWith(String(year)))
          .reduce((s, r) => s + (parseFloat(r.daysRequested) || 0), 0);
        if (accrual) {
          resolvedBal = [{
            leaveTypeCode: 'ANNUAL',
            entitledDays:  accrual.entitlementPerYear,
            accruedDays:   accrual.totalAccrued,
            usedDays:      approvedAnnual,
            pendingDays:   pendingAnnual,
            remaining:     Math.max(0, accrual.totalAccrued - approvedAnnual),
          }];
        }
      }

      setBalances(resolvedBal);
      setRequests(reqs.filter(r => r.status === 'Pending' || r.status === 'Approved'));
      setLastPayslip(slips[0] ?? null); // already sorted newest-first
      setTodayRec(attRecs[0] ?? null);
      setMyAssets(assets || []);
      setLoading(false);
    });
  }, [profile?.employeeId]);

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--gray-400)', paddingTop: 60 }}>
        Loading…
      </div>
    );
  }

  const annualBal = balances.find(b => b.leaveTypeCode === 'ANNUAL');
  const pendingReqs = requests.filter(r => r.status === 'Pending').length;
  const todayStatus = todayRec?.status ?? null;

  const [pyear, pmonth] = lastPayslip?.period?.split('-').map(Number) ?? [];
  const monthName = pmonth
    ? ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][pmonth - 1]
    : null;

  return (
    <div>
      {/* Header */}
      <div className="emp-page-header">
        <div>
          <h2>{greetingFor(emp?.name)}</h2>
          <p>{fmtDate(todayUAE())}</p>
        </div>
      </div>

      <div className="emp-page-body">

        {/* Today's attendance status */}
        <div className="emp-card" style={{ marginBottom: 16 }}>
          <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 36, height: 36, borderRadius: '50%',
                background: todayStatus ? STATUS_COLORS[todayStatus] + '20' : 'rgba(100,116,139,0.10)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Clock size={16} color={todayStatus ? STATUS_COLORS[todayStatus] : 'var(--gray-400)'} />
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--gray-500)', fontWeight: 500 }}>TODAY'S STATUS</div>
                <div style={{
                  fontSize: 15, fontWeight: 700,
                  color: todayStatus ? STATUS_COLORS[todayStatus] : 'var(--gray-500)',
                }}>
                  {todayStatus ? STATUS_LABELS[todayStatus] : 'Not recorded yet'}
                </div>
              </div>
            </div>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => onNavigate('attendance')}
              style={{ color: 'var(--primary)', gap: 2 }}
            >
              View <ChevronRight size={13} />
            </button>
          </div>
          {todayRec?.clockInTime && (
            <div style={{
              padding: '10px 16px', borderTop: '1px solid rgba(100,116,139,0.10)',
              display: 'flex', gap: 24, fontSize: 13,
            }}>
              <span style={{ color: 'var(--gray-500)' }}>
                In: <strong style={{ color: 'var(--gray-800)' }}>
                  {new Date(todayRec.clockInTime).toLocaleTimeString('en-AE', { hour: '2-digit', minute: '2-digit' })}
                </strong>
              </span>
              {todayRec.clockOutTime && (
                <span style={{ color: 'var(--gray-500)' }}>
                  Out: <strong style={{ color: 'var(--gray-800)' }}>
                    {new Date(todayRec.clockOutTime).toLocaleTimeString('en-AE', { hour: '2-digit', minute: '2-digit' })}
                  </strong>
                </span>
              )}
            </div>
          )}
        </div>

        {/* Quick stats */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <div
            className="emp-card"
            style={{ padding: 16, cursor: 'pointer' }}
            onClick={() => onNavigate('leave')}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <CalendarDays size={15} color="var(--primary)" />
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Annual Leave</span>
            </div>
            <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--gray-900)', lineHeight: 1 }}>
              {annualBal ? parseFloat(annualBal.remaining).toFixed(1) : '—'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 4 }}>
              days remaining
              {annualBal && ` of ${annualBal.entitledDays}`}
            </div>
            {pendingReqs > 0 && (
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--warning)', fontWeight: 500 }}>
                {pendingReqs} pending request{pendingReqs > 1 ? 's' : ''}
              </div>
            )}
          </div>

          <div
            className="emp-card"
            style={{ padding: 16, cursor: 'pointer' }}
            onClick={() => onNavigate('payslips')}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <FileText size={15} color="var(--success)" />
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Last Payslip</span>
            </div>
            {lastPayslip ? (
              <>
                <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--gray-900)', lineHeight: 1 }}>
                  {lastPayslip.netPay.toLocaleString('en-AE', { minimumFractionDigits: 0 })}
                </div>
                <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 4 }}>
                  AED net · {monthName} {pyear}
                </div>
              </>
            ) : (
              <div style={{ fontSize: 13, color: 'var(--gray-400)', marginTop: 4 }}>No payslips yet</div>
            )}
          </div>
        </div>

        {/* Document expiry warnings */}
        {emp && (() => {
          const checks = [
            { label: 'Visa', date: emp.visa_expiry },
            { label: 'Passport', date: emp.passport_expiry },
            { label: 'Emirates ID', date: emp.emirates_id_expiry },
            { label: 'Labour Card', date: emp.labour_card_expiry },
          ];
          const today = new Date();
          const expiring = checks.filter(c => {
            if (!c.date) return false;
            const days = Math.ceil((new Date(c.date) - today) / 86400000);
            return days >= 0 && days <= 60;
          }).map(c => ({
            ...c,
            days: Math.ceil((new Date(c.date) - today) / 86400000),
          }));

          if (!expiring.length) return null;
          return (
            <div className="alert alert-warning emp-card" style={{ borderRadius: 12, marginBottom: 16 }}>
              <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <div>
                <strong>Document expiry reminder</strong>
                <ul style={{ margin: '6px 0 0', paddingLeft: 16, fontSize: 13 }}>
                  {expiring.map(c => (
                    <li key={c.label}>
                      {c.label} expires in <strong>{c.days} day{c.days !== 1 ? 's' : ''}</strong>
                      {' '}({fmtDate(c.date)})
                    </li>
                  ))}
                </ul>
                <div style={{ marginTop: 6, fontSize: 12, color: 'var(--gray-600)' }}>
                  Contact HR to initiate renewal.
                </div>
              </div>
            </div>
          );
        })()}

        {/* My assigned assets (Feature 16) */}
        {myAssets.length > 0 && (
          <div className="emp-card" style={{ marginBottom: 16 }}>
            <div style={{
              padding: '12px 16px', borderBottom: '1px solid rgba(100,116,139,0.10)',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <Package size={14} color="var(--primary)" />
              <span style={{ fontWeight: 600, fontSize: 14 }}>My Assigned Assets</span>
            </div>
            {myAssets.map(a => (
              <div key={a.assignmentId} style={{
                padding: '10px 16px', borderBottom: '1px solid rgba(100,116,139,0.07)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-800)' }}>
                    {a.name}
                    {a.assetCode && (
                      <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--gray-400)', marginLeft: 6 }}>
                        {a.assetCode}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 1 }}>
                    {[a.brand, a.model].filter(Boolean).join(' · ') || a.category}
                    {' · '}Since {fmtDate(a.assignedDate)}
                  </div>
                </div>
                <span style={{
                  fontSize: 11, padding: '2px 8px', borderRadius: 999,
                  background: 'rgba(37,99,235,0.10)', color: 'var(--primary)',
                  fontWeight: 500,
                }}>
                  {a.category?.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Recent leave requests */}
        {requests.length > 0 && (
          <div className="emp-card">
            <div style={{
              padding: '12px 16px', borderBottom: '1px solid rgba(100,116,139,0.10)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>Recent Leave Requests</span>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => onNavigate('leave')}
                style={{ color: 'var(--primary)', gap: 2 }}
              >
                All <ChevronRight size={13} />
              </button>
            </div>
            {requests.slice(0, 3).map(req => (
              <div key={req.id} style={{
                padding: '12px 16px', borderBottom: '1px solid rgba(100,116,139,0.07)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-800)' }}>
                    {req.leaveTypeCode}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 1 }}>
                    {fmtDate(req.startDate)} – {fmtDate(req.endDate)} · {req.daysRequested} day{req.daysRequested !== 1 ? 's' : ''}
                  </div>
                </div>
                <span className={`badge ${req.status === 'Approved' ? 'badge-green' : req.status === 'Pending' ? 'badge-amber' : 'badge-gray'}`}>
                  {req.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
