import { useEffect, useState, useCallback } from 'react';
import { LogIn, LogOut, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getAttendanceRecords, recordClockEvent } from '../../utils/attendanceStorage';
import { ATTENDANCE_STATUS, STATUS_LABELS, STATUS_COLORS } from '../../utils/attendanceEngine';
import { supabase } from '../../lib/supabase';

const UAE_TZ_OFFSET = 4 * 60;

function todayUAE() {
  const now = new Date();
  const uae = new Date(now.getTime() + (UAE_TZ_OFFSET - now.getTimezoneOffset()) * 60000);
  return uae.toISOString().split('T')[0];
}

function fmtTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('en-AE', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Dubai' });
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-AE', { weekday: 'short', day: 'numeric', month: 'short' });
}

const RECENT_DAYS = 14;

export default function EmpAttendance() {
  const { profile } = useAuth();
  const [todayRec, setTodayRec]   = useState(null);
  const [history, setHistory]     = useState([]);
  const [loading, setLoading]     = useState(true);
  const [clocking, setClocking]   = useState(false);
  const [toast, setToast]         = useState(null);

  // Regularisation form
  const [showRegForm, setShowRegForm] = useState(false);
  const [regDate, setRegDate]         = useState('');
  const [regClockIn, setRegClockIn]   = useState('');
  const [regClockOut, setRegClockOut] = useState('');
  const [regReason, setRegReason]     = useState('');
  const [regSaving, setRegSaving]     = useState(false);

  function showToast(type, msg) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3500);
  }

  const loadData = useCallback(async () => {
    if (!profile?.employeeId) { setLoading(false); return; }
    const today = todayUAE();
    const from  = new Date(new Date(today).getTime() - RECENT_DAYS * 86400000).toISOString().split('T')[0];

    const [todayRecs, histRecs] = await Promise.all([
      getAttendanceRecords({ employeeId: profile.employeeId, dateFrom: today, dateTo: today }),
      getAttendanceRecords({ employeeId: profile.employeeId, dateFrom: from, dateTo: today }),
    ]);

    if (todayRecs.length > 0 || histRecs.length > 0) {
      setTodayRec(todayRecs[0] ?? null);
      setHistory(histRecs.filter(r => r.date !== today));
    } else {
      // Fallback: derive records from clock_events (employee's own entries)
      const { data: evts } = await supabase
        .from('clock_events')
        .select('*')
        .eq('employee_id', profile.employeeId)
        .gte('event_time', `${from}T00:00:00+04:00`)
        .order('event_time', { ascending: true });

      if (evts?.length) {
        const byDate = {};
        for (const ev of evts) {
          const d = new Date(ev.event_time).toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' });
          if (!byDate[d]) byDate[d] = { date: d, clockInTime: null, clockOutTime: null, lateMinutes: 0, overtimeHours: 0, status: ATTENDANCE_STATUS.PRESENT };
          if (ev.event_type === 'CLOCK_IN' && !byDate[d].clockInTime) byDate[d].clockInTime = ev.event_time;
          if (ev.event_type === 'CLOCK_OUT') byDate[d].clockOutTime = ev.event_time;
        }
        const allRecs = Object.values(byDate)
          .sort((a, b) => b.date.localeCompare(a.date))
          .map(r => ({
            ...r,
            totalHours: r.clockInTime && r.clockOutTime
              ? (new Date(r.clockOutTime) - new Date(r.clockInTime)) / 3600000
              : 0,
          }));
        setTodayRec(allRecs.find(r => r.date === today) ?? null);
        setHistory(allRecs.filter(r => r.date !== today));
      }
    }

    setLoading(false);
  }, [profile?.employeeId]);

  useEffect(() => { loadData(); }, [loadData]);

  async function clock(eventType) {
    setClocking(true);
    const now = new Date().toISOString();

    // Try server-side RPC (handles attendance computation + cross-RLS write)
    const { data: rpcData, error: rpcError } = await supabase.rpc('employee_record_clock_event', {
      p_event_type: eventType,
      p_notes: '',
    });

    if (!rpcError && rpcData?.success) {
      showToast('success', eventType === 'CLOCK_IN' ? 'Clocked in.' : 'Clocked out.');
      await loadData();
    } else {
      const rpcMsg = rpcError?.message ?? rpcData?.error ?? 'unknown';
      console.error('[Attendance] RPC failed:', rpcMsg);

      // Fallback: direct insert into clock_events under employee's own auth context
      try {
        await recordClockEvent({ employeeId: profile.employeeId, eventType, method: 'WEB' });
        setTodayRec(prev => {
          const base = prev ?? { date: todayUAE(), status: ATTENDANCE_STATUS.PRESENT, lateMinutes: 0, totalHours: 0, overtimeHours: 0, clockInTime: null, clockOutTime: null };
          return eventType === 'CLOCK_IN'
            ? { ...base, clockInTime: now, status: ATTENDANCE_STATUS.PRESENT }
            : { ...base, clockOutTime: now };
        });
        showToast('success', eventType === 'CLOCK_IN' ? 'Clocked in.' : 'Clocked out.');
      } catch (fallbackErr) {
        console.error('[Attendance] Direct insert failed:', fallbackErr?.message);
        showToast('error', `Clock failed: ${rpcMsg}`);
      }
    }

    setClocking(false);
  }

  async function submitRegularisation(e) {
    e.preventDefault();
    setRegSaving(true);
    const { data, error } = await supabase.rpc('employee_submit_regularisation', {
      p_attendance_date:    regDate,
      p_correct_clock_in:   regDate && regClockIn ? `${regDate}T${regClockIn}:00+04:00` : null,
      p_correct_clock_out:  regDate && regClockOut ? `${regDate}T${regClockOut}:00+04:00` : null,
      p_reason:             regReason,
    });
    setRegSaving(false);
    if (error || !data?.success) {
      showToast('error', 'Submission failed.');
      return;
    }
    showToast('success', 'Regularisation request submitted.');
    setShowRegForm(false);
    setRegDate(''); setRegClockIn(''); setRegClockOut(''); setRegReason('');
  }

  const canClockIn  = !todayRec?.clockInTime;
  const canClockOut = !!todayRec?.clockInTime && !todayRec?.clockOutTime;

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>;

  return (
    <div>
      <div className="emp-page-header">
        <h2>Attendance</h2>
        <p>UAE GMT+4 · {todayUAE()}</p>
      </div>

      <div className="emp-page-body">

        {toast && (
          <div className={`alert ${toast.type === 'success' ? 'alert-success' : 'alert-danger'}`}
               style={{ marginBottom: 16, borderRadius: 10 }}>
            {toast.type === 'success' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
            {toast.msg}
          </div>
        )}

        {/* Today's card + clock buttons */}
        <div className="emp-card" style={{ marginBottom: 16 }}>
          <div style={{ padding: '16px 16px 12px' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
              Today
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <div style={{
                width: 48, height: 48, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: todayRec ? STATUS_COLORS[todayRec.status] + '22' : 'var(--gray-100)',
              }}>
                <Clock size={22} color={todayRec ? STATUS_COLORS[todayRec.status] : 'var(--gray-400)'} />
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700, color: todayRec ? STATUS_COLORS[todayRec.status] : 'var(--gray-500)' }}>
                  {todayRec ? STATUS_LABELS[todayRec.status] : 'Not started'}
                </div>
                {todayRec?.totalHours > 0 && (
                  <div style={{ fontSize: 13, color: 'var(--gray-500)' }}>
                    {todayRec.totalHours.toFixed(1)} hrs
                    {todayRec.overtimeHours > 0 && ` · ${todayRec.overtimeHours.toFixed(1)} OT`}
                  </div>
                )}
              </div>
            </div>

            {/* Time row */}
            <div style={{ display: 'flex', gap: 24, marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--gray-400)', fontWeight: 500 }}>CLOCK IN</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--gray-800)', marginTop: 2 }}>
                  {todayRec?.clockInTime ? fmtTime(todayRec.clockInTime) : '—'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--gray-400)', fontWeight: 500 }}>CLOCK OUT</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--gray-800)', marginTop: 2 }}>
                  {todayRec?.clockOutTime ? fmtTime(todayRec.clockOutTime) : '—'}
                </div>
              </div>
              {todayRec?.lateMinutes > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: 'var(--warning)', fontWeight: 500 }}>LATE BY</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--warning)', marginTop: 2 }}>
                    {todayRec.lateMinutes}m
                  </div>
                </div>
              )}
            </div>

            {/* Clock buttons */}
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                className="btn btn-success"
                style={{ flex: 1, justifyContent: 'center', fontSize: 14, padding: '10px 0' }}
                disabled={!canClockIn || clocking}
                onClick={() => clock('CLOCK_IN')}
              >
                <LogIn size={16} />
                {clocking && canClockIn ? 'Clocking in…' : 'Clock In'}
              </button>
              <button
                className="btn btn-danger"
                style={{ flex: 1, justifyContent: 'center', fontSize: 14, padding: '10px 0' }}
                disabled={!canClockOut || clocking}
                onClick={() => clock('CLOCK_OUT')}
              >
                <LogOut size={16} />
                {clocking && canClockOut ? 'Clocking out…' : 'Clock Out'}
              </button>
            </div>
          </div>
        </div>

        {/* Regularisation */}
        <div style={{ marginBottom: 16 }}>
          <button
            className="btn btn-outline btn-sm"
            onClick={() => setShowRegForm(v => !v)}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            Request Attendance Correction
          </button>
        </div>

        {showRegForm && (
          <div className="emp-card" style={{ padding: 16, marginBottom: 16 }}>
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>Attendance Regularisation</div>
            <form onSubmit={submitRegularisation}>
              <div className="form-grid" style={{ gap: 10 }}>
                <div className="form-group">
                  <label>Date to correct</label>
                  <input className="form-control" type="date" value={regDate}
                    onChange={e => setRegDate(e.target.value)} required />
                </div>
                <div className="form-grid form-grid-2" style={{ gap: 10 }}>
                  <div className="form-group">
                    <label>Correct clock-in</label>
                    <input className="form-control" type="time" value={regClockIn}
                      onChange={e => setRegClockIn(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label>Correct clock-out</label>
                    <input className="form-control" type="time" value={regClockOut}
                      onChange={e => setRegClockOut(e.target.value)} />
                  </div>
                </div>
                <div className="form-group">
                  <label>Reason</label>
                  <textarea className="form-control" rows={2} value={regReason}
                    onChange={e => setRegReason(e.target.value)} required style={{ resize: 'vertical' }} />
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="submit" className="btn btn-primary btn-sm" disabled={regSaving}>
                    {regSaving ? 'Submitting…' : 'Submit'}
                  </button>
                  <button type="button" className="btn btn-outline btn-sm"
                    onClick={() => setShowRegForm(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            </form>
          </div>
        )}

        {/* Recent history */}
        <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--gray-600)', marginBottom: 8 }}>
          Recent ({RECENT_DAYS} days)
        </div>
        {history.length === 0
          ? <div className="empty-state" style={{ paddingTop: 24 }}><p>No records found.</p></div>
          : history.map(rec => (
              <div key={rec.id ?? rec.date} className="emp-card" style={{ marginBottom: 8 }}>
                <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-800)' }}>
                      {fmtDate(rec.date)}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--gray-500)', marginTop: 2 }}>
                      {rec.clockInTime ? fmtTime(rec.clockInTime) : '—'}
                      {' → '}
                      {rec.clockOutTime ? fmtTime(rec.clockOutTime) : '—'}
                      {rec.totalHours > 0 && ` · ${rec.totalHours.toFixed(1)}h`}
                    </div>
                  </div>
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 20,
                    background: STATUS_COLORS[rec.status] + '22',
                    color: STATUS_COLORS[rec.status],
                  }}>
                    {STATUS_LABELS[rec.status] ?? rec.status}
                  </span>
                </div>
              </div>
            ))
        }
      </div>
    </div>
  );
}
