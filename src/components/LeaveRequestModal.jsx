/**
 * LeaveRequestModal.jsx — Submit a leave request
 *
 * Handles all UAE leave types with type-specific fields:
 *   - Bereavement: relationship, deceased name, date of death
 *   - Paternity: child birth date, child name
 *   - Maternity: expected due date
 *   - Study: institution name, exam dates
 *   - Half-day option for single-day requests
 *
 * Shows balance before/after and compliance warnings.
 */
import { useState, useEffect } from 'react';
import { X, AlertCircle, Info, Calendar, Upload } from 'lucide-react';
import { formatDateUAE, formatAED } from '../utils/uaeValidators';
import {
  countLeaveDays, validateLeaveRequest, calculateAnnualLeaveAccrual,
  calculateSickLeavePay
} from '../utils/leaveEngine';

const BEREAVEMENT_RELATIONSHIPS = [
  { label: 'Spouse', days: 5 },
  { label: 'Parent', days: 3 },
  { label: 'Child', days: 3 },
  { label: 'Sibling', days: 3 },
];

export default function LeaveRequestModal({
  employee,
  allEmployees,
  onEmployeeChange,
  leaveTypes,
  leaveBalances,
  publicHolidayDates,
  weekendDef,
  onSubmit,
  onClose,
}) {
  const today = new Date().toISOString().split('T')[0];

  const [form, setForm] = useState({
    leaveTypeId:    '',
    leaveTypeCode:  '',
    startDate:      today,
    endDate:        today,
    isHalfDay:      false,
    halfDayPeriod:  'AM',
    reason:         '',
    attachmentUrl:  '',
    // Bereavement
    relationship:   '',
    deceasedName:   '',
    dateOfDeath:    '',
    // Paternity
    childBirthDate: '',
    childName:      '',
    // Maternity
    expectedDueDate: '',
    // Study
    institutionName: '',
    examDates:       '',
  });

  const [errors, setErrors]     = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  const selectedType = leaveTypes.find(lt => lt.id === form.leaveTypeId);
  const balance      = leaveBalances.find(b => b.leaveTypeCode === selectedType?.code);

  // Auto-set end date for bereavement based on relationship
  useEffect(() => {
    if (selectedType?.code === 'BEREAVEMENT' && form.relationship) {
      const rel = BEREAVEMENT_RELATIONSHIPS.find(r => r.label === form.relationship);
      if (rel && form.startDate) {
        // Working days — add rel.days working days from start
        const start = new Date(form.startDate);
        let count = 0;
        let current = new Date(start);
        while (count < rel.days) {
          const day = current.getDay();
          const isWeekend = weekendDef === 'fri-sat' ? (day === 5 || day === 6) : (day === 0 || day === 6);
          if (!isWeekend) count++;
          if (count < rel.days) current.setDate(current.getDate() + 1);
        }
        setForm(prev => ({ ...prev, endDate: current.toISOString().split('T')[0] }));
      }
    }
  }, [form.relationship, form.startDate, selectedType?.code, weekendDef]);

  const daysRequested = selectedType
    ? countLeaveDays(form.startDate, form.endDate, selectedType.dayCountType, publicHolidayDates, weekendDef, form.isHalfDay)
    : 0;

  const remainingAfter = balance ? (balance.remaining - daysRequested) : null;

  // Run validation on type/date change
  useEffect(() => {
    if (!selectedType || !form.startDate || !form.endDate) {
      setErrors([]); setWarnings([]); return;
    }
    const { errors: e, warnings: w } = validateLeaveRequest(
      { ...form, daysRequested },
      employee,
      selectedType,
      balance,
      publicHolidayDates,
      weekendDef
    );
    setErrors(e);
    setWarnings(w);
  }, [form.leaveTypeId, form.startDate, form.endDate, form.relationship, form.childBirthDate, form.attachmentUrl]);

  const f = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  const handleTypeChange = (typeId) => {
    const lt = leaveTypes.find(t => t.id === typeId);
    setForm(prev => ({ ...prev, leaveTypeId: typeId, leaveTypeCode: lt?.code || '' }));
  };

  const handleSubmit = async () => {
    if (!form.leaveTypeId) { setErrors(['Please select a leave type.']); return; }
    if (errors.length > 0) return; // hard errors block submission
    setSubmitting(true);
    try {
      await onSubmit({
        ...form,
        employeeId:    employee.id,
        daysRequested,
      });
      onClose();
    } catch (err) {
      setErrors([err.message || 'Failed to submit leave request.']);
    } finally {
      setSubmitting(false);
    }
  };

  // Sick leave pay breakdown
  const sickPayBreakdown = selectedType?.code === 'SICK' && daysRequested > 0
    ? calculateSickLeavePay(
        balance?.sickFullPayUsed || 0,
        daysRequested,
        (parseFloat(employee.basicSalary) || 0) / 30
      )
    : null;

  return (
    <div className="modal-overlay">
      <div className="modal modal-lg">
        <div className="modal-header">
          <h3><Calendar size={16} style={{ marginRight:6 }}/>Request Leave — {employee.name}</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18}/></button>
        </div>

        <div className="modal-body">
          {/* Errors */}
          {errors.length > 0 && (
            <div className="alert alert-danger mb-3">
              <AlertCircle size={15}/>
              <div>
                {errors.map((e, i) => <div key={i}>{e}</div>)}
              </div>
            </div>
          )}
          {/* Warnings */}
          {warnings.length > 0 && (
            <div className="alert alert-warning mb-3">
              <AlertCircle size={15}/>
              <div>
                {warnings.map((w, i) => <div key={i}>{w}</div>)}
              </div>
            </div>
          )}

          <div className="form-grid form-grid-2">
            {/* Employee selector — shown when HR is submitting on behalf of an employee */}
            {allEmployees && allEmployees.length > 1 && (
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <label>Employee *</label>
                <select className="form-control" value={employee?.id || ''}
                  onChange={e => onEmployeeChange && onEmployeeChange(allEmployees.find(emp => emp.id === e.target.value))}>
                  {allEmployees.map(e => (
                    <option key={e.id} value={e.id}>{e.name}{e.department ? ` — ${e.department}` : ''}</option>
                  ))}
                </select>
              </div>
            )}
            {/* Leave Type */}
            <div className="form-group" style={{ gridColumn:'1/-1' }}>
              <label>Leave Type *</label>
              <select className="form-control" value={form.leaveTypeId} onChange={e => handleTypeChange(e.target.value)}>
                <option value="">Select leave type…</option>
                {leaveTypes.map(lt => (
                  <option key={lt.id} value={lt.id}
                    disabled={lt.code === 'HAJJ' && (balance?.hajjTaken || false)}
                  >
                    {lt.name}
                    {lt.code === 'HAJJ' && balance?.hajjTaken ? ' (Already taken)' : ''}
                    {lt.lawReference ? ` — ${lt.lawReference}` : ''}
                  </option>
                ))}
              </select>
              {selectedType && (
                <span className="hint" style={{ color: selectedType.color }}>
                  {selectedType.lawReference}
                  {selectedType.dayCountType === 'working' ? ' · Working days only' : ' · Calendar days'}
                </span>
              )}
            </div>

            {/* Dates */}
            <div className="form-group">
              <label>Start Date *</label>
              <input className="form-control" type="date" value={form.startDate}
                onChange={e => { f('startDate', e.target.value); if (!form.isHalfDay) f('endDate', e.target.value); }}/>
            </div>
            <div className="form-group">
              <label>End Date *</label>
              <input className="form-control" type="date" value={form.endDate}
                disabled={form.isHalfDay}
                onChange={e => f('endDate', e.target.value)}/>
            </div>

            {/* Half day option */}
            {form.startDate === form.endDate && (
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <label style={{ display:'flex', alignItems:'center', gap:8, cursor:'pointer' }}>
                  <input type="checkbox" checked={form.isHalfDay}
                    onChange={e => { f('isHalfDay', e.target.checked); if (e.target.checked) f('endDate', form.startDate); }}/>
                  Half-day leave
                </label>
                {form.isHalfDay && (
                  <div style={{ display:'flex', gap:12, marginTop:8 }}>
                    {['AM','PM'].map(p => (
                      <label key={p} style={{ display:'flex', alignItems:'center', gap:6, cursor:'pointer' }}>
                        <input type="radio" name="halfDayPeriod" value={p}
                          checked={form.halfDayPeriod === p}
                          onChange={() => f('halfDayPeriod', p)}/>
                        {p === 'AM' ? 'Morning (AM)' : 'Afternoon (PM)'}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Duration & balance preview */}
            {selectedType && daysRequested > 0 && (
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <div style={{ display:'flex', gap:16, flexWrap:'wrap' }}>
                  <div style={{ background:'var(--primary-light)', borderRadius:8, padding:'10px 16px', flex:1 }}>
                    <div style={{ fontSize:11, color:'var(--gray-500)', textTransform:'uppercase', letterSpacing:'0.05em' }}>Days Requested</div>
                    <div style={{ fontSize:20, fontWeight:700, color:'var(--primary)' }}>{daysRequested}</div>
                    <div style={{ fontSize:11, color:'var(--gray-500)' }}>{selectedType.dayCountType} days</div>
                  </div>
                  {balance && !selectedType.isUnlimited && (
                    <>
                      <div style={{ background:'var(--success-light)', borderRadius:8, padding:'10px 16px', flex:1 }}>
                        <div style={{ fontSize:11, color:'var(--gray-500)', textTransform:'uppercase', letterSpacing:'0.05em' }}>Available Balance</div>
                        <div style={{ fontSize:20, fontWeight:700, color:'var(--success)' }}>{balance.remaining}</div>
                        <div style={{ fontSize:11, color:'var(--gray-500)' }}>days remaining</div>
                      </div>
                      <div style={{ background: remainingAfter < 0 ? 'var(--danger-light)' : 'var(--gray-50)', borderRadius:8, padding:'10px 16px', flex:1 }}>
                        <div style={{ fontSize:11, color:'var(--gray-500)', textTransform:'uppercase', letterSpacing:'0.05em' }}>Balance After</div>
                        <div style={{ fontSize:20, fontWeight:700, color: remainingAfter < 0 ? 'var(--danger)' : 'var(--gray-800)' }}>{remainingAfter}</div>
                        <div style={{ fontSize:11, color:'var(--gray-500)' }}>days remaining</div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Sick leave pay breakdown */}
            {sickPayBreakdown && (
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <div className="alert alert-info">
                  <Info size={14}/>
                  <div style={{ fontSize:12.5 }}>
                    <strong>Art. 31 Sick Leave Pay:</strong> {sickPayBreakdown.breakdown}
                    {sickPayBreakdown.totalDeduction > 0 && (
                      <span> · Salary deduction: <strong>{formatAED(sickPayBreakdown.totalDeduction)}</strong></span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Bereavement-specific fields */}
            {selectedType?.code === 'BEREAVEMENT' && (
              <>
                <div className="form-group">
                  <label>Relationship to Deceased *</label>
                  <select className="form-control" value={form.relationship} onChange={e => f('relationship', e.target.value)}>
                    <option value="">Select relationship…</option>
                    {BEREAVEMENT_RELATIONSHIPS.map(r => (
                      <option key={r.label} value={r.label}>{r.label} ({r.days} working days)</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Date of Death</label>
                  <input className="form-control" type="date" value={form.dateOfDeath} onChange={e => f('dateOfDeath', e.target.value)}/>
                </div>
                <div className="form-group" style={{ gridColumn:'1/-1' }}>
                  <label>Deceased Name</label>
                  <input className="form-control" value={form.deceasedName} onChange={e => f('deceasedName', e.target.value)} placeholder="Full name of deceased"/>
                </div>
              </>
            )}

            {/* Paternity-specific fields */}
            {selectedType?.code === 'PATERNITY' && (
              <>
                <div className="form-group">
                  <label>Child's Birth Date *</label>
                  <input className="form-control" type="date" value={form.childBirthDate} onChange={e => f('childBirthDate', e.target.value)}/>
                  <span className="hint">Art. 32: Leave must be taken within 6 months of birth</span>
                </div>
                <div className="form-group">
                  <label>Child's Name (optional)</label>
                  <input className="form-control" value={form.childName} onChange={e => f('childName', e.target.value)} placeholder="Child's name"/>
                </div>
              </>
            )}

            {/* Maternity-specific fields */}
            {selectedType?.code === 'MATERNITY' && (
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <label>Expected Due Date</label>
                <input className="form-control" type="date" value={form.expectedDueDate} onChange={e => f('expectedDueDate', e.target.value)}/>
                <span className="hint">Art. 30: 60 days total (45 full pay + 15 half pay). 1 year service required for paid leave.</span>
              </div>
            )}

            {/* Study leave fields */}
            {selectedType?.code === 'STUDY' && (
              <>
                <div className="form-group">
                  <label>Institution Name *</label>
                  <input className="form-control" value={form.institutionName} onChange={e => f('institutionName', e.target.value)} placeholder="UAE-accredited institution"/>
                </div>
                <div className="form-group">
                  <label>Exam Dates</label>
                  <input className="form-control" value={form.examDates} onChange={e => f('examDates', e.target.value)} placeholder="e.g. 15/06/2026, 18/06/2026"/>
                </div>
              </>
            )}

            {/* Reason */}
            <div className="form-group" style={{ gridColumn:'1/-1' }}>
              <label>Reason / Notes {selectedType?.requiresReason ? '*' : ''}</label>
              <textarea className="form-control" rows={3} value={form.reason}
                onChange={e => f('reason', e.target.value)}
                placeholder={selectedType?.code === 'SICK' ? 'Brief description of illness (medical certificate required)' : 'Optional notes for manager'}
                style={{ resize:'vertical' }}/>
            </div>

            {/* Attachment */}
            {selectedType?.requiresAttachment && (
              <div className="form-group" style={{ gridColumn:'1/-1' }}>
                <label>
                  <Upload size={13} style={{ marginRight:5 }}/>
                  Attachment {selectedType.requiresAttachment ? '*' : ''}
                </label>
                <input className="form-control" value={form.attachmentUrl}
                  onChange={e => f('attachmentUrl', e.target.value)}
                  placeholder="Paste document URL or file path"/>
                <span className="hint">
                  {selectedType.code === 'SICK' && 'Medical certificate required for all sick leave.'}
                  {selectedType.code === 'STUDY' && 'Art. 36: Proof of enrollment and exam schedule required.'}
                  {selectedType.code === 'MATERNITY' && 'Medical documentation required.'}
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={submitting}>Cancel</button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={submitting || errors.length > 0 || !form.leaveTypeId}
          >
            {submitting ? 'Submitting…' : 'Submit Leave Request'}
          </button>
        </div>
      </div>
    </div>
  );
}
