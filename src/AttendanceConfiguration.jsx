import { useEffect, useState } from 'react'

import { readAllEmployees } from './employeeApi.js'
import { HttpClientError } from './http.js'
import {
  assignShift,
  createShift,
  deactivateShift,
  readAttendanceSettings,
  readShiftAssignments,
  readShifts,
  updateAttendanceSettings,
  updateShift,
} from './attendanceConfigurationApi.js'

const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const emptyShift = {
  name: '', code: '', shiftType: 'fixed', shiftCategory: 'morning', startTime: '08:00:00',
  endTime: '17:00:00', splitStartTime: null, splitEndTime: null, breakMinutes: 60,
  expectedHours: '8.00', lateGraceMinutes: 10, earlyDepartureGraceMinutes: 10,
  isOvernight: false, minHoursFlexible: null, color: '#6366F1', minStaff: 1,
}

function messageFor(error) {
  if (!(error instanceof HttpClientError)) return 'The request failed. No changes were saved.'
  if (error.code === 'state_conflict') return 'Someone changed this record. Reload and review it before saving.'
  if (error.code === 'retained_shift') return 'This shift is retained by current or historical records.'
  if (error.code === 'shift_assignment_conflict') return 'The assignment conflicts with current shift history.'
  return error.message
}

export default function AttendanceConfiguration({ authentication, branchId }) {
  const [settings, setSettings] = useState(null)
  const [settingsDraft, setSettingsDraft] = useState(null)
  const [shifts, setShifts] = useState([])
  const [employees, setEmployees] = useState([])
  const [shiftDraft, setShiftDraft] = useState(emptyShift)
  const [editingShift, setEditingShift] = useState(null)
  const [assignment, setAssignment] = useState({ employeeId: '', shiftId: '', effectiveFrom: '' })
  const [message, setMessage] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      readAttendanceSettings(authentication, branchId, { signal: controller.signal }),
      readShifts(authentication, branchId, { limit: 100, signal: controller.signal }),
      readAllEmployees(authentication, branchId, { signal: controller.signal }),
    ])
      .then(([nextSettings, nextShifts, nextEmployees]) => {
        if (controller.signal.aborted) return
        setSettings(nextSettings)
        setSettingsDraft({ ...nextSettings })
        setShifts(nextShifts.data)
        setEmployees(nextEmployees)
      })
      .catch((error) => {
        if (!controller.signal.aborted) setMessage(messageFor(error))
      })
    return () => controller.abort()
  }, [authentication, branchId])

  const saveSettings = async (event) => {
    event.preventDefault(); setMessage('')
    try {
      const result = await updateAttendanceSettings(authentication, branchId, settingsDraft, { idempotencyKey: crypto.randomUUID() })
      setSettings(result.data); setSettingsDraft({ ...result.data })
      setMessage(result.replayed ? 'The existing settings result was recovered.' : 'Attendance settings saved.')
    } catch (error) { setMessage(messageFor(error)) }
  }

  const toggleWeekend = (day) => {
    const weekend = new Set(settingsDraft.weekendDays)
    if (weekend.has(day)) weekend.delete(day); else weekend.add(day)
    setSettingsDraft({ ...settingsDraft, weekendDays: dayNames.filter((item) => weekend.has(item)), workingDays: dayNames.filter((item) => !weekend.has(item)) })
  }

  const saveShift = async (event) => {
    event.preventDefault(); setMessage('')
    try {
      const prepared = { ...shiftDraft, code: shiftDraft.code || null }
      const saved = editingShift
        ? await updateShift(authentication, branchId, editingShift, prepared, { idempotencyKey: crypto.randomUUID() })
        : await createShift(authentication, branchId, prepared, { idempotencyKey: crypto.randomUUID() })
      setShifts((rows) => editingShift ? rows.map((row) => row.id === saved.id ? saved : row) : [...rows, saved].sort((a, b) => a.name.localeCompare(b.name)))
      setEditingShift(null); setShiftDraft(emptyShift); setMessage('Shift saved.')
    } catch (error) { setMessage(messageFor(error)) }
  }

  const disableShift = async (shift) => {
    try {
      const result = await deactivateShift(authentication, branchId, shift, { idempotencyKey: crypto.randomUUID() })
      setShifts((rows) => rows.map((row) => row.id === shift.id ? result.data : row))
      setMessage('Shift deactivated.')
    } catch (error) { setMessage(messageFor(error)) }
  }

  const saveAssignment = async (event) => {
    event.preventDefault(); setMessage('')
    try {
      const current = await readShiftAssignments(authentication, branchId, { employeeId: assignment.employeeId, effectiveOn: assignment.effectiveFrom, limit: 1 })
      const row = current.data[0] ?? null
      await assignShift(authentication, branchId, { ...assignment, expectedCurrentAssignmentId: row?.id ?? null, expectedCurrentAssignmentUpdatedAt: row?.updatedAt ?? null }, { idempotencyKey: crypto.randomUUID() })
      setMessage('Shift assignment saved. Prior coverage was closed without overlap.')
    } catch (error) { setMessage(messageFor(error)) }
  }

  if (!settingsDraft) return <section className="attendance-configuration"><h2>Attendance configuration</h2><p>Loading configuration...</p></section>
  const setting = (name) => (event) => setSettingsDraft({ ...settingsDraft, [name]: event.target.type === 'checkbox' ? event.target.checked : event.target.value })
  const biometricKey = (event) => {
    const next = { ...settingsDraft }
    if (event.target.value) next.biometricApiKey = event.target.value
    else delete next.biometricApiKey
    setSettingsDraft(next)
  }
  const shiftField = (name) => (event) => setShiftDraft({ ...shiftDraft, [name]: event.target.type === 'number' ? Number(event.target.value) : event.target.value })
  const shiftType = (event) => {
    const type = event.target.value
    const shapes = {
      fixed: { shiftType: type, shiftCategory: 'morning', startTime: '08:00:00', endTime: '17:00:00', splitStartTime: null, splitEndTime: null, isOvernight: false, minHoursFlexible: null },
      overnight: { shiftType: type, shiftCategory: 'night', startTime: '20:00:00', endTime: '08:00:00', splitStartTime: null, splitEndTime: null, isOvernight: true, minHoursFlexible: null },
      split: { shiftType: type, shiftCategory: 'split', startTime: '08:00:00', endTime: '12:00:00', splitStartTime: '13:00:00', splitEndTime: '17:00:00', isOvernight: false, minHoursFlexible: null },
      flexible: { shiftType: type, shiftCategory: 'flexible', startTime: null, endTime: null, splitStartTime: null, splitEndTime: null, isOvernight: false, breakMinutes: 0, minHoursFlexible: shiftDraft.expectedHours },
    }
    setShiftDraft({ ...shiftDraft, ...shapes[type] })
  }

  return (
    <section className="attendance-configuration" aria-labelledby="attendance-configuration-title">
      <h2 id="attendance-configuration-title">Attendance configuration</h2>
      <form className="settings-form" onSubmit={saveSettings}>
        <h3>Branch rules</h3>
        <fieldset><legend>Weekend days</legend>{dayNames.map((day) => <label className="checkbox" key={day}><input type="checkbox" checked={settingsDraft.weekendDays.includes(day)} onChange={() => toggleWeekend(day)} /> {day}</label>)}</fieldset>
        <label>Default hours<input value={settingsDraft.defaultHoursPerDay} onChange={setting('defaultHoursPerDay')} inputMode="decimal" required /></label>
        <label>Late grace minutes<input type="number" min="0" max="240" value={settingsDraft.lateGraceMinutes} onChange={setting('lateGraceMinutes')} required /></label>
        <label>Early departure grace minutes<input type="number" min="0" max="240" value={settingsDraft.earlyDepartureGraceMinutes} onChange={setting('earlyDepartureGraceMinutes')} required /></label>
        <label>Maximum daily overtime hours<input value={settingsDraft.maxDailyOvertimeHours} onChange={setting('maxDailyOvertimeHours')} inputMode="decimal" required /></label>
        <label>Late deduction policy<select value={settingsDraft.lateDeductionPolicy} onChange={setting('lateDeductionPolicy')}><option value="none">None</option><option value="per_minute">Per minute</option><option value="per_occurrence">Per occurrence</option></select></label>
        <label>Late deduction amount<input value={settingsDraft.lateDeductionAmount} onChange={setting('lateDeductionAmount')} inputMode="decimal" required /></label>
        <label>Regularisation days per month<input type="number" min="0" max="31" value={settingsDraft.regularisationMaxDaysPerMonth} onChange={setting('regularisationMaxDaysPerMonth')} /></label>
        <label>Regularisation window days<input type="number" min="0" max="365" value={settingsDraft.regularisationWindowDays} onChange={setting('regularisationWindowDays')} /></label>
        <label className="checkbox"><input type="checkbox" checked={settingsDraft.overtimeRequiresApproval} onChange={setting('overtimeRequiresApproval')} /> Require overtime approval</label>
        <label className="checkbox"><input type="checkbox" checked={settingsDraft.wfhEnabled} onChange={setting('wfhEnabled')} /> Enable work from home</label>
        <label className="checkbox"><input type="checkbox" checked={settingsDraft.biometricApiEnabled} onChange={setting('biometricApiEnabled')} /> Enable biometric API</label>
        <label>Biometric API key<input type="password" autoComplete="new-password" value={settingsDraft.biometricApiKey ?? ''} onChange={biometricKey} placeholder={settings.biometricApiKeyConfigured ? 'Configured; leave blank to preserve' : 'Not configured'} /></label>
        <button type="submit">Save attendance settings</button>
      </form>

      <form className="settings-form" onSubmit={saveShift}>
        <h3>{editingShift ? 'Edit shift' : 'Create shift'}</h3>
        <label>Name<input value={shiftDraft.name} onChange={shiftField('name')} required /></label>
        <label>Code<input value={shiftDraft.code ?? ''} onChange={shiftField('code')} maxLength="12" /></label>
        <label>Type<select value={shiftDraft.shiftType} onChange={shiftType}><option value="fixed">Fixed</option><option value="overnight">Overnight</option><option value="split">Split</option><option value="flexible">Flexible</option></select></label>
        <label>Category<select value={shiftDraft.shiftCategory} onChange={shiftField('shiftCategory')} disabled={shiftDraft.shiftType !== 'fixed'}><option value="morning">Morning</option><option value="afternoon">Afternoon</option><option value="night">Night</option><option value="split">Split</option><option value="flexible">Flexible</option></select></label>
        {shiftDraft.shiftType !== 'flexible' && <label>Start<input type="time" step="1" value={shiftDraft.startTime ?? ''} onChange={shiftField('startTime')} required /></label>}
        {shiftDraft.shiftType !== 'flexible' && <label>End<input type="time" step="1" value={shiftDraft.endTime ?? ''} onChange={shiftField('endTime')} required /></label>}
        {shiftDraft.shiftType === 'split' && <label>Second start<input type="time" step="1" value={shiftDraft.splitStartTime ?? ''} onChange={shiftField('splitStartTime')} required /></label>}
        {shiftDraft.shiftType === 'split' && <label>Second end<input type="time" step="1" value={shiftDraft.splitEndTime ?? ''} onChange={shiftField('splitEndTime')} required /></label>}
        {shiftDraft.shiftType === 'flexible' && <label>Minimum flexible hours<input value={shiftDraft.minHoursFlexible ?? ''} onChange={shiftField('minHoursFlexible')} inputMode="decimal" required /></label>}
        <label>Expected hours<input value={shiftDraft.expectedHours} onChange={shiftField('expectedHours')} inputMode="decimal" /></label>
        <label>Break minutes<input type="number" min="0" max="240" value={shiftDraft.breakMinutes} onChange={shiftField('breakMinutes')} /></label>
        <label>Late grace minutes<input type="number" min="0" max="240" value={shiftDraft.lateGraceMinutes} onChange={shiftField('lateGraceMinutes')} /></label>
        <label>Early departure grace minutes<input type="number" min="0" max="240" value={shiftDraft.earlyDepartureGraceMinutes} onChange={shiftField('earlyDepartureGraceMinutes')} /></label>
        <label>Display color<input type="color" value={shiftDraft.color} onChange={shiftField('color')} /></label>
        <label>Minimum staff<input type="number" min="0" max="999" value={shiftDraft.minStaff} onChange={shiftField('minStaff')} /></label>
        <button type="submit">Save shift</button>
        {editingShift && <button type="button" className="secondary" onClick={() => { setEditingShift(null); setShiftDraft(emptyShift) }}>Cancel edit</button>}
      </form>
      <ul className="shift-list">{shifts.map((shift) => <li key={shift.id}><span>{shift.name} ({shift.code ?? 'no code'}) — {shift.isActive ? 'active' : 'inactive'}</span><button type="button" className="secondary" onClick={() => { setEditingShift(shift); setShiftDraft(Object.fromEntries(Object.keys(emptyShift).map((key) => [key, shift[key]]))) }}>Edit</button>{shift.isActive && <button type="button" className="danger" onClick={() => disableShift(shift)}>Deactivate</button>}</li>)}</ul>

      <form className="settings-form" onSubmit={saveAssignment}>
        <h3>Effective shift assignment</h3>
        <label>Employee<select value={assignment.employeeId} onChange={(event) => setAssignment({ ...assignment, employeeId: event.target.value })} required><option value="">Select employee</option>{employees.filter((employee) => employee.active).map((employee) => <option key={employee.id} value={employee.id}>{employee.employeeNo} — {employee.name}</option>)}</select></label>
        <label>Shift<select value={assignment.shiftId} onChange={(event) => setAssignment({ ...assignment, shiftId: event.target.value })} required><option value="">Select shift</option>{shifts.filter((shift) => shift.isActive).map((shift) => <option key={shift.id} value={shift.id}>{shift.name}</option>)}</select></label>
        <label>Effective from<input type="date" value={assignment.effectiveFrom} onChange={(event) => setAssignment({ ...assignment, effectiveFrom: event.target.value })} required /></label>
        <button type="submit">Assign shift</button>
      </form>
      {message && <p role="status">{message}</p>}
    </section>
  )
}
