/**
 * RosterManager.jsx — Shift Scheduling & Roster (Feature 8)
 *
 * Tabs:
 *   1. Templates — Create / edit / delete shift templates (name, color, times, grace periods)
 *   2. Roster    — Monthly grid: assign shifts to employees per day; publish to portal
 *   3. Swaps     — Review and approve / reject employee shift-swap requests
 */
import { useState, useEffect, useRef } from 'react';
import {
  Plus, Edit2, Trash2, Check, X,
  ChevronLeft, ChevronRight, Send, AlertCircle,
} from 'lucide-react';
import { getEmployees } from '../utils/storage';
import {
  getShifts, saveShift, deleteShift,
  getRosterForMonth, saveRosterAssignment, deleteRosterAssignment, publishRoster,
  getShiftSwapRequests, updateShiftSwapRequest,
} from '../utils/attendanceStorage';

// ── helpers ───────────────────────────────────────────────────────────────────

function pad2(n) { return String(n).padStart(2, '0'); }

function fmtTime(t) {
  if (!t) return '—';
  return String(t).slice(0, 5);
}

function autoExpectedHours(startTime, endTime, breakMinutes) {
  if (!startTime || !endTime) return 8;
  const [sh, sm] = startTime.split(':').map(Number);
  const [eh, em] = endTime.split(':').map(Number);
  let mins = (eh * 60 + em) - (sh * 60 + sm);
  if (mins < 0) mins += 24 * 60; // overnight shift
  mins -= (breakMinutes || 0);
  return Math.round(Math.max(0, mins) / 60 * 10) / 10;
}

const PALETTE = [
  '#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#06b6d4', '#84cc16', '#f97316', '#ec4899',
];

const EMPTY_FORM = {
  name: '', color: '#6366f1',
  startTime: '09:00', endTime: '18:00',
  breakMinutes: 60, expectedHours: 8,
  lateGraceMinutes: 10, earlyDepartureGraceMinutes: 10,
};

// ── component ─────────────────────────────────────────────────────────────────

export default function RosterManager() {
  const [tab, setTab]         = useState('templates');
  const [loading, setLoading] = useState(true);
  const [msg, setMsg]         = useState(null);

  // Shift templates
  const [shifts, setShifts]         = useState([]);
  const [shiftForm, setShiftForm]   = useState(null); // null = closed
  const [shiftSaving, setShiftSaving] = useState(false);

  // Employees & roster
  const [employees, setEmployees]         = useState([]);
  const [rosterMonth, setRosterMonth]     = useState(new Date());
  const [rosterData, setRosterData]       = useState({}); // `${empId}_${dateStr}` → assignment
  const [savingCell, setSavingCell]       = useState(null);
  const [publishing, setPublishing]       = useState(false);
  const [rosterDeptFilter, setRosterDeptFilter] = useState('');

  // Swaps
  const [swaps, setSwaps]           = useState([]);
  const [swapSaving, setSwapSaving] = useState(null);

  // Don't re-load roster on initial mount (loadAll already does it)
  const initialLoadDone = useRef(false);

  const rYear  = rosterMonth.getFullYear();
  const rMonth = rosterMonth.getMonth() + 1; // 1-indexed

  // ── data loading ────────────────────────────────────────────────────────────

  useEffect(() => { loadAll(); }, []);

  useEffect(() => {
    if (!initialLoadDone.current) return;
    loadRoster();
  }, [rosterMonth]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadAll() {
    setLoading(true);
    try {
      const [emps, shfts, swapReqs, roster] = await Promise.all([
        getEmployees(),
        getShifts(),
        getShiftSwapRequests().catch(() => []),
        getRosterForMonth(rYear, rMonth).catch(() => []),
      ]);
      setEmployees(emps.filter(e => e.employmentStatus !== 'Terminated'));
      setShifts(shfts);
      setSwaps(swapReqs);
      buildRosterMap(roster);
    } catch (err) {
      showMsg('danger', 'Load failed: ' + err.message);
    } finally {
      setLoading(false);
      initialLoadDone.current = true;
    }
  }

  async function loadRoster() {
    try {
      const roster = await getRosterForMonth(rYear, rMonth);
      buildRosterMap(roster);
    } catch (err) {
      showMsg('danger', 'Failed to load roster: ' + err.message);
    }
  }

  function buildRosterMap(assignments) {
    const map = {};
    for (const a of assignments) {
      map[`${a.employeeId}_${a.date}`] = a;
    }
    setRosterData(map);
  }

  function showMsg(type, text) {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  }

  // ── shift template CRUD ──────────────────────────────────────────────────────

  async function handleSaveShift() {
    if (!shiftForm?.name?.trim()) return;
    setShiftSaving(true);
    try {
      const saved = await saveShift(shiftForm);
      setShifts(prev =>
        shiftForm.id ? prev.map(s => s.id === saved.id ? saved : s) : [...prev, saved]
      );
      setShiftForm(null);
      showMsg('success', `Shift "${saved.name}" saved.`);
    } catch (err) {
      showMsg('danger', 'Failed to save shift: ' + err.message);
    } finally {
      setShiftSaving(false);
    }
  }

  async function handleDeleteShift(id) {
    if (!window.confirm('Deactivate this shift template?')) return;
    try {
      await deleteShift(id);
      setShifts(prev => prev.filter(s => s.id !== id));
    } catch (err) {
      showMsg('danger', 'Failed: ' + err.message);
    }
  }

  // ── roster cell change ───────────────────────────────────────────────────────

  async function handleCellChange(empId, dateStr, shiftId) {
    const cellKey = `${empId}_${dateStr}`;
    setSavingCell(cellKey);
    try {
      if (!shiftId) {
        await deleteRosterAssignment(empId, dateStr);
        setRosterData(prev => { const n = { ...prev }; delete n[cellKey]; return n; });
      } else {
        const saved = await saveRosterAssignment({ employeeId: empId, shiftId, date: dateStr });
        setRosterData(prev => ({ ...prev, [cellKey]: saved }));
      }
    } catch (err) {
      showMsg('danger', 'Roster update failed: ' + err.message);
    } finally {
      setSavingCell(null);
    }
  }

  async function handlePublish() {
    if (!window.confirm(
      `Publish roster for ${rosterMonth.toLocaleString('en-AE', { month: 'long', year: 'numeric' })}?\n\n` +
      `Employees will be able to see their schedule in the portal.`
    )) return;
    setPublishing(true);
    try {
      await publishRoster(rYear, rMonth);
      await loadRoster();
      showMsg('success', 'Roster published — employees can now view their schedule.');
    } catch (err) {
      showMsg('danger', 'Failed to publish roster: ' + err.message);
    } finally {
      setPublishing(false);
    }
  }

  // ── swap actions ─────────────────────────────────────────────────────────────

  async function handleSwapUpdate(id, status) {
    setSwapSaving(id);
    try {
      const updated = await updateShiftSwapRequest(id, status);
      setSwaps(prev => prev.map(s => s.id === id ? updated : s));
      showMsg('success', `Swap request ${status}.`);
    } catch (err) {
      showMsg('danger', 'Failed: ' + err.message);
    } finally {
      setSwapSaving(null);
    }
  }

  // ── derived ──────────────────────────────────────────────────────────────────

  const daysInMonth      = new Date(rYear, rMonth, 0).getDate();
  const departments      = [...new Set(employees.map(e => e.department).filter(Boolean))].sort();
  const filteredEmployees = rosterDeptFilter
    ? employees.filter(e => e.department === rosterDeptFilter)
    : employees;
  const pendingSwaps     = swaps.filter(s => s.status === 'pending');
  const monthIsPublished = Object.values(rosterData).some(a => a.published);

  const TABS = [
    { id: 'templates', label: 'Shift Templates' },
    { id: 'roster',    label: 'Monthly Roster' },
    { id: 'swaps',     label: `Swap Requests${pendingSwaps.length > 0 ? ` (${pendingSwaps.length})` : ''}` },
  ];

  if (loading) return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
      Loading Roster…
    </div>
  );

  return (
    <div>
      <div className="page-header">
        <h2>Shift Scheduling &amp; Roster</h2>
      </div>

      <div className="page-body">
        {msg && (
          <div className={`alert alert-${msg.type} mb-4`}>
            <AlertCircle size={14} /> {msg.text}
          </div>
        )}

        {/* Tab bar */}
        <div className="tabs" style={{ marginBottom: 20 }}>
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── TEMPLATES TAB ── */}
        {tab === 'templates' && (
          <div className="card">
            <div className="card-header">
              <h3>Shift Templates</h3>
              {!shiftForm && (
                <button className="btn btn-primary btn-sm" onClick={() => setShiftForm({ ...EMPTY_FORM })}>
                  <Plus size={14} /> New Shift
                </button>
              )}
            </div>

            <div className="card-body">
              {/* Form */}
              {shiftForm && (
                <div style={{
                  background: 'var(--gray-50)', border: '1px solid var(--gray-200)',
                  borderRadius: 10, padding: 20, marginBottom: 20,
                }}>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 14 }}>
                    {shiftForm.id ? `Edit — ${shiftForm.name}` : 'New Shift Template'}
                  </div>

                  <div className="form-grid form-grid-2" style={{ gap: 12 }}>
                    <div className="form-group">
                      <label>Shift Name</label>
                      <input
                        className="form-control"
                        value={shiftForm.name}
                        onChange={e => setShiftForm(p => ({ ...p, name: e.target.value }))}
                        placeholder="e.g. Morning, Night, Split"
                      />
                    </div>

                    <div className="form-group">
                      <label>Color</label>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                        {PALETTE.map(c => (
                          <button
                            key={c} type="button"
                            onClick={() => setShiftForm(p => ({ ...p, color: c }))}
                            style={{
                              width: 22, height: 22, borderRadius: '50%', background: c,
                              border: shiftForm.color === c ? '3px solid #1e293b' : '2px solid transparent',
                              cursor: 'pointer', padding: 0, flexShrink: 0,
                            }}
                          />
                        ))}
                        <input
                          type="color" value={shiftForm.color}
                          onChange={e => setShiftForm(p => ({ ...p, color: e.target.value }))}
                          style={{ width: 26, height: 26, borderRadius: 4, border: '1px solid var(--gray-300)', padding: 1, cursor: 'pointer' }}
                        />
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Start Time</label>
                      <input
                        className="form-control" type="time"
                        value={shiftForm.startTime || ''}
                        onChange={e => {
                          const v = e.target.value;
                          setShiftForm(p => ({ ...p, startTime: v, expectedHours: autoExpectedHours(v, p.endTime, p.breakMinutes) }));
                        }}
                      />
                    </div>

                    <div className="form-group">
                      <label>End Time</label>
                      <input
                        className="form-control" type="time"
                        value={shiftForm.endTime || ''}
                        onChange={e => {
                          const v = e.target.value;
                          setShiftForm(p => ({ ...p, endTime: v, expectedHours: autoExpectedHours(p.startTime, v, p.breakMinutes) }));
                        }}
                      />
                    </div>

                    <div className="form-group">
                      <label>Break (minutes)</label>
                      <input
                        className="form-control" type="number" min={0} max={180}
                        value={shiftForm.breakMinutes}
                        onChange={e => {
                          const v = parseInt(e.target.value) || 0;
                          setShiftForm(p => ({ ...p, breakMinutes: v, expectedHours: autoExpectedHours(p.startTime, p.endTime, v) }));
                        }}
                      />
                    </div>

                    <div className="form-group">
                      <label>Expected Hours <span style={{ fontWeight: 400, color: 'var(--gray-400)', fontSize: 11 }}>(auto-computed)</span></label>
                      <input
                        className="form-control" type="number" min={0} max={24} step={0.5}
                        value={shiftForm.expectedHours}
                        onChange={e => setShiftForm(p => ({ ...p, expectedHours: parseFloat(e.target.value) || 0 }))}
                      />
                    </div>

                    <div className="form-group">
                      <label>Late Grace (minutes)</label>
                      <input
                        className="form-control" type="number" min={0} max={60}
                        value={shiftForm.lateGraceMinutes}
                        onChange={e => setShiftForm(p => ({ ...p, lateGraceMinutes: parseInt(e.target.value) || 0 }))}
                      />
                    </div>

                    <div className="form-group">
                      <label>Early Departure Grace (minutes)</label>
                      <input
                        className="form-control" type="number" min={0} max={60}
                        value={shiftForm.earlyDepartureGraceMinutes}
                        onChange={e => setShiftForm(p => ({ ...p, earlyDepartureGraceMinutes: parseInt(e.target.value) || 0 }))}
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={handleSaveShift}
                      disabled={shiftSaving || !shiftForm.name?.trim()}
                    >
                      {shiftSaving ? 'Saving…' : shiftForm.id ? 'Update Shift' : 'Create Shift'}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setShiftForm(null)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Shift list */}
              {shifts.length === 0 ? (
                <div className="empty-state">
                  <h3>No shift templates yet</h3>
                  <p>Create at least one shift before building a roster.</p>
                </div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th style={{ width: 30 }}>Color</th>
                        <th>Name</th>
                        <th>Start</th>
                        <th>End</th>
                        <th>Break</th>
                        <th>Hours</th>
                        <th>Late Grace</th>
                        <th>Early Grace</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {shifts.map(s => (
                        <tr key={s.id}>
                          <td>
                            <div style={{ width: 18, height: 18, borderRadius: 4, background: s.color || '#6366f1' }} />
                          </td>
                          <td style={{ fontWeight: 600 }}>{s.name}</td>
                          <td>{fmtTime(s.startTime)}</td>
                          <td>{fmtTime(s.endTime)}</td>
                          <td>{s.breakMinutes} min</td>
                          <td>{s.expectedHours}h</td>
                          <td>{s.lateGraceMinutes} min</td>
                          <td>{s.earlyDepartureGraceMinutes} min</td>
                          <td>
                            <div style={{ display: 'flex', gap: 4 }}>
                              <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setShiftForm({ ...s })} title="Edit">
                                <Edit2 size={13} />
                              </button>
                              <button className="btn btn-ghost btn-icon btn-sm text-danger" onClick={() => handleDeleteShift(s.id)} title="Deactivate">
                                <Trash2 size={13} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── ROSTER TAB ── */}
        {tab === 'roster' && (
          <div className="card">
            {/* Header */}
            <div className="card-header" style={{ flexWrap: 'wrap', gap: 8 }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button
                  className="btn btn-ghost btn-icon btn-sm"
                  onClick={() => setRosterMonth(new Date(rYear, rMonth - 2, 1))}
                >
                  <ChevronLeft size={16} />
                </button>
                {rosterMonth.toLocaleString('en-AE', { month: 'long', year: 'numeric' })}
                <button
                  className="btn btn-ghost btn-icon btn-sm"
                  onClick={() => setRosterMonth(new Date(rYear, rMonth, 1))}
                >
                  <ChevronRight size={16} />
                </button>
              </h3>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                {departments.length > 0 && (
                  <select
                    className="form-control"
                    style={{ width: 160, height: 32, fontSize: 12, padding: '0 8px' }}
                    value={rosterDeptFilter}
                    onChange={e => setRosterDeptFilter(e.target.value)}
                  >
                    <option value="">All Departments</option>
                    {departments.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                )}
                <button
                  className="btn btn-primary btn-sm"
                  onClick={handlePublish}
                  disabled={publishing || Object.keys(rosterData).length === 0}
                  title={monthIsPublished ? 'Re-publish (update employee view)' : 'Publish roster for employees to see'}
                >
                  <Send size={13} /> {publishing ? 'Publishing…' : monthIsPublished ? 'Re-publish' : 'Publish'}
                </button>
              </div>
            </div>

            {shifts.length === 0 ? (
              <div className="empty-state">
                <h3>No shift templates</h3>
                <p>Create shifts in the Templates tab first.</p>
                <button className="btn btn-primary btn-sm mt-3" onClick={() => setTab('templates')}>
                  Go to Templates
                </button>
              </div>
            ) : filteredEmployees.length === 0 ? (
              <div className="empty-state"><h3>No active employees</h3></div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ borderCollapse: 'collapse', minWidth: '100%', fontSize: 11 }}>
                  <thead>
                    <tr style={{ background: 'var(--gray-50)' }}>
                      {/* Sticky employee name column */}
                      <th style={{
                        padding: '8px 12px', textAlign: 'left',
                        position: 'sticky', left: 0, zIndex: 2,
                        background: 'var(--gray-50)', minWidth: 160,
                        borderRight: '2px solid var(--gray-200)', borderBottom: '1px solid var(--gray-200)',
                      }}>
                        Employee
                      </th>
                      {Array.from({ length: daysInMonth }).map((_, i) => {
                        const day = i + 1;
                        const dow = new Date(`${rYear}-${pad2(rMonth)}-${pad2(day)}`).toLocaleString('en-AE', { weekday: 'short' });
                        const isWeekend = dow === 'Fri' || dow === 'Sat';
                        return (
                          <th key={day} style={{
                            padding: '4px 2px', textAlign: 'center',
                            minWidth: 70, width: 70,
                            borderRight: '1px solid var(--gray-100)',
                            borderBottom: '1px solid var(--gray-200)',
                            background: isWeekend ? '#f1f5f9' : 'var(--gray-50)',
                            color: isWeekend ? 'var(--gray-400)' : 'var(--gray-500)',
                          }}>
                            <div style={{ fontWeight: 700, fontSize: 12 }}>{day}</div>
                            <div style={{ fontSize: 9 }}>{dow}</div>
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEmployees.map(emp => (
                      <tr key={emp.id} style={{ borderBottom: '1px solid var(--gray-100)' }}>
                        <td style={{
                          padding: '6px 12px', fontWeight: 500,
                          position: 'sticky', left: 0, zIndex: 1,
                          background: 'white', borderRight: '2px solid var(--gray-200)',
                        }}>
                          <div style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
                            {emp.name}
                          </div>
                          {emp.department && (
                            <div style={{ fontSize: 10, color: 'var(--gray-400)' }}>{emp.department}</div>
                          )}
                        </td>
                        {Array.from({ length: daysInMonth }).map((_, i) => {
                          const day      = i + 1;
                          const dateStr  = `${rYear}-${pad2(rMonth)}-${pad2(day)}`;
                          const cellKey  = `${emp.id}_${dateStr}`;
                          const assignment = rosterData[cellKey];
                          const sh       = assignment ? shifts.find(s => s.id === assignment.shiftId) : null;
                          const dow      = new Date(dateStr).toLocaleString('en-AE', { weekday: 'short' });
                          const isWeekend = dow === 'Fri' || dow === 'Sat';
                          const isSaving = savingCell === cellKey;

                          return (
                            <td key={day} style={{
                              padding: '3px 2px', textAlign: 'center',
                              borderRight: '1px solid var(--gray-100)',
                              background: isWeekend ? '#f8fafc' : 'white',
                            }}>
                              <select
                                value={assignment?.shiftId || ''}
                                disabled={isSaving}
                                onChange={e => handleCellChange(emp.id, dateStr, e.target.value)}
                                title={sh
                                  ? `${sh.name}: ${fmtTime(sh.startTime)}–${fmtTime(sh.endTime)}${assignment?.published ? ' ✓' : ''}`
                                  : 'Click to assign a shift'}
                                style={{
                                  width: 66, height: 26, fontSize: 10,
                                  borderRadius: 5, padding: '0 2px',
                                  border: `2px solid ${sh ? sh.color : 'var(--gray-200)'}`,
                                  background: sh ? sh.color + '22' : 'transparent',
                                  color: sh ? sh.color : 'var(--gray-400)',
                                  fontWeight: sh ? 700 : 400,
                                  cursor: isSaving ? 'wait' : 'pointer',
                                  opacity: isSaving ? 0.5 : 1,
                                  textAlign: 'center',
                                  textAlignLast: 'center',
                                }}
                              >
                                <option value="">—</option>
                                {shifts.map(s => (
                                  <option key={s.id} value={s.id}>{s.name}</option>
                                ))}
                              </select>
                              {assignment?.published && (
                                <div style={{ fontSize: 8, color: 'var(--success)', lineHeight: 1 }}>✓ pub</div>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Legend */}
            {shifts.length > 0 && (
              <div style={{
                padding: '10px 16px', borderTop: '1px solid var(--gray-100)',
                display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center',
              }}>
                {shifts.map(s => (
                  <span key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--gray-600)' }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: s.color, display: 'inline-block' }} />
                    {s.name} {s.startTime ? `(${fmtTime(s.startTime)}–${fmtTime(s.endTime)})` : ''}
                  </span>
                ))}
                <span style={{ fontSize: 11, color: 'var(--gray-400)' }}>
                  "—" = not assigned · ✓ pub = published to portal
                </span>
              </div>
            )}
          </div>
        )}

        {/* ── SWAPS TAB ── */}
        {tab === 'swaps' && (
          <div className="card">
            <div className="card-header">
              <h3>Shift Swap Requests</h3>
              <span style={{ fontSize: 12, color: 'var(--gray-500)', fontWeight: 400 }}>
                {pendingSwaps.length} pending · {swaps.length} total
              </span>
            </div>

            {swaps.length === 0 ? (
              <div className="empty-state">
                <h3>No swap requests</h3>
                <p>Employees can submit shift swap requests from their Schedule tab in the portal.</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Requested By</th>
                      <th>Their Date</th>
                      <th>Swap With</th>
                      <th>Their Date</th>
                      <th>Reason</th>
                      <th>Status</th>
                      <th>Submitted</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {swaps.map(sw => {
                      const requester = employees.find(e => e.id === sw.requesterEmployeeId);
                      const target    = employees.find(e => e.id === sw.targetEmployeeId);
                      return (
                        <tr key={sw.id}>
                          <td style={{ fontWeight: 500 }}>{requester?.name || '—'}</td>
                          <td>{sw.requesterDate}</td>
                          <td>{target?.name || '—'}</td>
                          <td>{sw.targetDate || '—'}</td>
                          <td className="text-muted text-sm">{sw.reason || '—'}</td>
                          <td>
                            <span className={`badge ${
                              sw.status === 'approved'  ? 'badge-green' :
                              sw.status === 'rejected'  ? 'badge-red'   :
                              sw.status === 'cancelled' ? 'badge-gray'  : 'badge-amber'
                            }`}>
                              {sw.status}
                            </span>
                          </td>
                          <td className="text-muted text-sm">{sw.createdAt?.split('T')[0] || '—'}</td>
                          <td>
                            {sw.status === 'pending' && (
                              <div style={{ display: 'flex', gap: 4 }}>
                                <button
                                  className="btn btn-success btn-sm"
                                  disabled={swapSaving === sw.id}
                                  onClick={() => handleSwapUpdate(sw.id, 'approved')}
                                  title="Approve swap"
                                >
                                  <Check size={13} />
                                </button>
                                <button
                                  className="btn btn-danger btn-sm"
                                  disabled={swapSaving === sw.id}
                                  onClick={() => handleSwapUpdate(sw.id, 'rejected')}
                                  title="Reject swap"
                                >
                                  <X size={13} />
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
