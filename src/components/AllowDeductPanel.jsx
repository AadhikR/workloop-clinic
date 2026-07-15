import { useState } from 'react';
import { X, Plus, Trash2, Info } from 'lucide-react';

/**
 * Compute Final Allowance for an entry (= variable allowance sent via WPS SIF):
 * = housing + transport + allowance + increment + bonus + otherPay + sum(additionalAllowances)
 *   - sum(deductions) - duCost - leaveDeduction
 *
 * Housing and transport are included here so the SIF variable allowance reflects the full
 * package. DU Cost is subtracted (employer-borne cost that reduces net employee transfer).
 */
export function computeFinalAllowance(entry) {
  const housing   = parseFloat(entry.housingAllowance) || 0;
  const transport = parseFloat(entry.transportAllowance) || 0;
  const base   = parseFloat(entry.allowance) || 0;
  const inc    = parseFloat(entry.increment) || 0;
  const bon    = parseFloat(entry.bonus) || 0;
  const oth    = parseFloat(entry.otherPay) || 0;
  const du     = parseFloat(entry.duCost) || 0;
  // leaveDeduction: editable leave deduction (unpaid/sick leave) — subtracted from net allowance
  const leaveDed = parseFloat(entry.leaveDeduction) || 0;
  const addAllow = (entry.additionalAllowances || []).reduce((s, a) => s + (parseFloat(a.amount) || 0), 0);
  const deds     = (entry.deductions || []).reduce((s, d) => s + (parseFloat(d.amount) || 0), 0);
  return housing + transport + base + inc + bon + oth + addAllow - deds - du - leaveDed;
}

export default function AllowDeductPanel({ entries, employees, onClose, onSave }) {
  const [localEntries, setLocalEntries] = useState(
    entries.map(e => ({
      ...e,
      additionalAllowances: (e.additionalAllowances || []).map(a => ({ ...a })),
      deductions: (e.deductions || []).map(d => ({ ...d })),
    }))
  );

  const getEmp = (id) => employees.find(e => e.id === id);

  const addItem = (entryIdx, side) => {
    setLocalEntries(prev => {
      const next = prev.map(e => ({
        ...e,
        additionalAllowances: [...(e.additionalAllowances || [])],
        deductions: [...(e.deductions || [])],
      }));
      const key = side === 'allow' ? 'additionalAllowances' : 'deductions';
      next[entryIdx][key] = [...next[entryIdx][key], { label: '', amount: '' }];
      return next;
    });
  };

  const removeItem = (entryIdx, side, itemIdx) => {
    setLocalEntries(prev => {
      const next = prev.map(e => ({
        ...e,
        additionalAllowances: [...(e.additionalAllowances || [])],
        deductions: [...(e.deductions || [])],
      }));
      const key = side === 'allow' ? 'additionalAllowances' : 'deductions';
      next[entryIdx][key] = next[entryIdx][key].filter((_, i) => i !== itemIdx);
      return next;
    });
  };

  const updateItem = (entryIdx, side, itemIdx, field, value) => {
    setLocalEntries(prev => {
      const next = prev.map(e => ({
        ...e,
        additionalAllowances: (e.additionalAllowances || []).map(a => ({ ...a })),
        deductions: (e.deductions || []).map(d => ({ ...d })),
      }));
      const key = side === 'allow' ? 'additionalAllowances' : 'deductions';
      next[entryIdx][key][itemIdx] = { ...next[entryIdx][key][itemIdx], [field]: value };
      return next;
    });
  };

  const activeEntries = localEntries.filter(e => !e.excluded);

  return (
    <div className="modal-overlay">
      <div className="modal modal-xl" style={{ maxWidth: 1000 }}>
        <div className="modal-header">
          <h3>Additional Allowances &amp; Deductions</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="modal-body" style={{ padding: 0 }}>
          <div className="alert alert-info" style={{ margin: '16px 20px 0', borderRadius: 6 }}>
            <Info size={15} />
            <span>
              Add named allowances (e.g. Accommodation, Travel) or deductions (e.g. Loan, Advance) per employee.
              These affect the <strong>Final Allowance</strong> (WPS variable allowance in the SIF file).
            </span>
          </div>

          {activeEntries.map((entry) => {
            const emp = getEmp(entry.employeeId);
            if (!emp) return null;
            const realIdx = localEntries.findIndex(e => e.employeeId === entry.employeeId);
            const addAllow = (entry.additionalAllowances || []).reduce((s, a) => s + (parseFloat(a.amount) || 0), 0);
            const deds = (entry.deductions || []).reduce((s, d) => s + (parseFloat(d.amount) || 0), 0);

            return (
              <div key={entry.employeeId} style={{ borderBottom: '1px solid var(--gray-200)', padding: '16px 20px' }}>
                <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 14, color: 'var(--gray-800)' }}>
                  {emp.name}
                  <span className="text-muted text-sm" style={{ marginLeft: 8, fontWeight: 400 }}>
                    MOL: {emp.molId}
                  </span>
                  {addAllow > 0 && (
                    <span className="badge badge-green" style={{ marginLeft: 8 }}>
                      +{addAllow.toLocaleString('en-AE')} allow
                    </span>
                  )}
                  {deds > 0 && (
                    <span className="badge badge-red" style={{ marginLeft: 4 }}>
                      -{deds.toLocaleString('en-AE')} ded
                    </span>
                  )}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  {/* Allowances */}
                  <div style={{ background: 'var(--success-light)', borderRadius: 6, padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--success)' }}>Additional Allowances</span>
                      <button
                        className="btn btn-sm"
                        style={{ background: 'var(--success)', color: 'white', border: 'none' }}
                        onClick={() => addItem(realIdx, 'allow')}
                      >
                        <Plus size={12} /> Add
                      </button>
                    </div>
                    {(entry.additionalAllowances || []).length === 0 && (
                      <p className="text-sm text-muted">No additional allowances</p>
                    )}
                    {(entry.additionalAllowances || []).map((item, iIdx) => (
                      <div key={iIdx} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                        <input
                          className="form-control"
                          style={{ flex: 2 }}
                          placeholder="Label (e.g. Accommodation)"
                          value={item.label}
                          onChange={e => updateItem(realIdx, 'allow', iIdx, 'label', e.target.value)}
                        />
                        <input
                          className="form-control"
                          style={{ flex: 1 }}
                          type="number" min="0" step="0.01"
                          placeholder="Amount"
                          value={item.amount}
                          onChange={e => updateItem(realIdx, 'allow', iIdx, 'amount', e.target.value)}
                        />
                        <button
                          className="btn btn-ghost btn-icon btn-sm text-danger"
                          onClick={() => removeItem(realIdx, 'allow', iIdx)}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                    {addAllow > 0 && (
                      <div style={{ textAlign: 'right', fontSize: 12, fontWeight: 600, color: 'var(--success)', marginTop: 4 }}>
                        Total: +{addAllow.toLocaleString('en-AE')} AED
                      </div>
                    )}
                  </div>

                  {/* Deductions */}
                  <div style={{ background: 'var(--danger-light)', borderRadius: 6, padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--danger)' }}>Deductions</span>
                      <button
                        className="btn btn-sm"
                        style={{ background: 'var(--danger)', color: 'white', border: 'none' }}
                        onClick={() => addItem(realIdx, 'deduct')}
                      >
                        <Plus size={12} /> Add
                      </button>
                    </div>
                    {(entry.deductions || []).length === 0 && (
                      <p className="text-sm text-muted">No deductions</p>
                    )}
                    {(entry.deductions || []).map((item, iIdx) => (
                      <div key={iIdx} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                        <input
                          className="form-control"
                          style={{ flex: 2 }}
                          placeholder="Label (e.g. Loan Repayment)"
                          value={item.label}
                          onChange={e => updateItem(realIdx, 'deduct', iIdx, 'label', e.target.value)}
                        />
                        <input
                          className="form-control"
                          style={{ flex: 1 }}
                          type="number" min="0" step="0.01"
                          placeholder="Amount"
                          value={item.amount}
                          onChange={e => updateItem(realIdx, 'deduct', iIdx, 'amount', e.target.value)}
                        />
                        <button
                          className="btn btn-ghost btn-icon btn-sm text-danger"
                          onClick={() => removeItem(realIdx, 'deduct', iIdx)}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                    {deds > 0 && (
                      <div style={{ textAlign: 'right', fontSize: 12, fontWeight: 600, color: 'var(--danger)', marginTop: 4 }}>
                        Total: -{deds.toLocaleString('en-AE')} AED
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={() => onSave(localEntries)}>
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}
