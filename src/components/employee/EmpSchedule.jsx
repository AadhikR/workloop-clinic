/**
 * EmpSchedule.jsx — Employee Schedule View (Feature 8)
 *
 * Shows the employee's published roster assignments for the selected month.
 * Employees can also submit a shift swap request for any upcoming shift.
 */
import { useState, useEffect } from 'react';
import { CalendarClock, ChevronLeft, ChevronRight, Send, X, AlertCircle, CheckCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getMyRoster, getMyColleagues, requestShiftSwap } from '../../utils/attendanceStorage';

function fmtDate(iso) {
  if (!iso) return '—';
  // Parse as local date to avoid timezone-off-by-one
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-AE', {
    weekday: 'short', day: 'numeric', month: 'short',
  });
}

function fmtTime(t) {
  if (!t) return '';
  return String(t).slice(0, 5);
}

// ── Swap request modal ────────────────────────────────────────────────────────

function SwapModal({ shift, colleagues, onSubmit, onClose }) {
  const [targetId, setTargetId] = useState('');
  const [targetDate, setTargetDate] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!targetId) return;
    setSaving(true);
    setErr('');
    try {
      await onSubmit({ targetEmployeeId: targetId, requesterDate: shift.date, targetDate: targetDate || null, reason });
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000, padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 14, padding: 24,
        width: '100%', maxWidth: 420, boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Request Shift Swap</div>
            <div style={{ fontSize: 12, color: 'var(--gray-400)', marginTop: 2 }}>
              Your shift: {shift.shiftName} on {fmtDate(shift.date)}
            </div>
          </div>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose}><X size={16} /></button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Swap with colleague</label>
            <select
              className="form-control"
              value={targetId}
              onChange={e => setTargetId(e.target.value)}
              required
            >
              <option value="">Select colleague…</option>
              {colleagues.map(c => (
                <option key={c.id} value={c.id}>{c.name}{c.jobTitle ? ` — ${c.jobTitle}` : ''}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Their date (optional)</label>
            <input
              className="form-control" type="date"
              value={targetDate}
              onChange={e => setTargetDate(e.target.value)}
            />
            <span className="hint">Leave blank if you just want to give up your shift</span>
          </div>

          <div className="form-group">
            <label>Reason (optional)</label>
            <textarea
              className="form-control" rows={2}
              value={reason}
              onChange={e => setReason(e.target.value)}
              style={{ resize: 'vertical' }}
            />
          </div>

          {err && (
            <div className="alert alert-danger" style={{ padding: '8px 12px', borderRadius: 6, marginBottom: 10 }}>
              <AlertCircle size={13} /> {err}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={saving || !targetId}
              style={{ flex: 1, justifyContent: 'center' }}
            >
              <Send size={13} /> {saving ? 'Submitting…' : 'Submit Request'}
            </button>
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function EmpSchedule() {
  const { profile } = useAuth();
  const [schedule, setSchedule]     = useState([]);
  const [colleagues, setColleagues] = useState([]);
  const [loading, setLoading]       = useState(true);
  const [calMonth, setCalMonth]     = useState(new Date());
  const [swapShift, setSwapShift]   = useState(null); // shift the user wants to swap
  const [toast, setToast]           = useState(null);

  const calYear     = calMonth.getFullYear();
  const calMonthNum = calMonth.getMonth() + 1;

  useEffect(() => {
    if (!profile?.employeeId) return;
    loadSchedule();
  }, [calMonth, profile?.employeeId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // Load colleagues list once
    getMyColleagues().then(setColleagues).catch(() => {});
  }, []);

  async function loadSchedule() {
    setLoading(true);
    try {
      const lastDay  = new Date(calYear, calMonthNum, 0).getDate();
      const dateFrom = `${calYear}-${String(calMonthNum).padStart(2, '0')}-01`;
      const dateTo   = `${calYear}-${String(calMonthNum).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
      const data = await getMyRoster(dateFrom, dateTo);
      setSchedule(data);
    } catch (err) {
      console.error('EmpSchedule:', err);
    } finally {
      setLoading(false);
    }
  }

  function showToast(type, msg) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3500);
  }

  async function handleSwapSubmit({ targetEmployeeId, requesterDate, targetDate, reason }) {
    await requestShiftSwap({ requesterDate, targetEmployeeId, targetDate, reason });
    setSwapShift(null);
    showToast('success', 'Swap request submitted — HR will review and approve.');
  }

  const todayStr = new Date().toISOString().split('T')[0];
  const totalHours = schedule.reduce((s, r) => s + r.expectedHours, 0);

  return (
    <div>
      <div className="emp-page-header">
        <div>
          <h2>My Schedule</h2>
          <p>Published shift roster from HR</p>
        </div>
      </div>

      <div className="emp-page-body">
        {/* Toast */}
        {toast && (
          <div className={`alert ${toast.type === 'success' ? 'alert-success' : 'alert-danger'}`}
               style={{ marginBottom: 12, borderRadius: 10 }}>
            {toast.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
            {toast.msg}
          </div>
        )}

        {/* Month navigation */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <button
            className="btn btn-ghost btn-sm btn-icon"
            onClick={() => setCalMonth(new Date(calYear, calMonthNum - 2, 1))}
          >
            <ChevronLeft size={16} />
          </button>
          <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--gray-900)' }}>
            {calMonth.toLocaleString('en-AE', { month: 'long', year: 'numeric' })}
          </span>
          <button
            className="btn btn-ghost btn-sm btn-icon"
            onClick={() => setCalMonth(new Date(calYear, calMonthNum, 1))}
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--gray-400)' }}>
            Loading schedule…
          </div>
        ) : schedule.length === 0 ? (
          <div className="empty-state">
            <CalendarClock size={40} color="var(--gray-300)" />
            <h3 style={{ marginTop: 12, color: 'var(--gray-500)' }}>No published shifts</h3>
            <p>Your HR admin hasn't published the roster for this month yet.</p>
          </div>
        ) : (
          <>
            {/* Summary strip */}
            <div style={{
              background: 'var(--primary-light)', borderRadius: 10,
              padding: '10px 16px', marginBottom: 14,
              display: 'flex', gap: 24, flexWrap: 'wrap',
            }}>
              <span style={{ fontSize: 13, color: 'var(--primary-dark)' }}>
                <strong>{schedule.length}</strong> shifts scheduled
              </span>
              <span style={{ fontSize: 13, color: 'var(--primary-dark)' }}>
                <strong>{totalHours}h</strong> total
              </span>
              <span style={{ fontSize: 13, color: 'var(--primary-dark)' }}>
                <strong>{schedule.filter(s => s.date >= todayStr).length}</strong> upcoming
              </span>
            </div>

            {/* Shift cards */}
            {schedule.map(item => {
              const isPast  = item.date < todayStr;
              const isToday = item.date === todayStr;
              const color   = item.shiftColor || '#6366f1';

              return (
                <div
                  key={item.id}
                  className="emp-card"
                  style={{
                    padding: '12px 16px', marginBottom: 8,
                    display: 'flex', alignItems: 'center', gap: 12,
                    opacity: isPast ? 0.55 : 1,
                    borderLeft: `4px solid ${color}`,
                  }}
                >
                  {/* Color swatch with initial */}
                  <div style={{
                    width: 38, height: 38, borderRadius: 8, flexShrink: 0,
                    background: color + '22', color,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: 13,
                  }}>
                    {item.shiftName?.[0]?.toUpperCase() || '?'}
                  </div>

                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--gray-900)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      {item.shiftName}
                      {isToday && (
                        <span style={{
                          fontSize: 9, fontWeight: 700, background: 'var(--primary)',
                          color: '#fff', borderRadius: 4, padding: '2px 6px',
                          letterSpacing: 0.5,
                        }}>
                          TODAY
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                      {fmtDate(item.date)}
                      {item.startTime && (
                        <span style={{ marginLeft: 8 }}>
                          {fmtTime(item.startTime)}–{fmtTime(item.endTime)} · {item.expectedHours}h
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Swap button — only for upcoming shifts */}
                  {!isPast && colleagues.length > 0 && (
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => setSwapShift(item)}
                      style={{ flexShrink: 0, fontSize: 11 }}
                    >
                      Swap
                    </button>
                  )}
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* Swap request modal */}
      {swapShift && (
        <SwapModal
          shift={swapShift}
          colleagues={colleagues}
          onSubmit={handleSwapSubmit}
          onClose={() => setSwapShift(null)}
        />
      )}
    </div>
  );
}
