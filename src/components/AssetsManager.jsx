/**
 * AssetsManager.jsx — Admin: Asset Registry & Tracking (Feature 16)
 *
 * Tabs:
 *   Assets      — full asset list with assign / return / edit / delete actions
 *   Assignments — full historical log (who had what, when)
 */
import { useState, useEffect } from 'react';
import { Package, Plus, X, Check, RefreshCw, AlertCircle, ChevronDown, ChevronUp, Pencil, Trash2 } from 'lucide-react';
import { getEmployees } from '../utils/storage';
import { getAssets, saveAsset, deleteAsset, getAssetAssignments, assignAsset, returnAsset } from '../utils/assetStorage';
import { formatDateUAE, validatePastDate } from '../utils/uaeValidators';

// ── Constants ─────────────────────────────────────────────────────────────────

export const ASSET_CATEGORIES = {
  laptop:    'Laptop / Computer',
  phone:     'Mobile Phone',
  tablet:    'Tablet',
  vehicle:   'Vehicle',
  furniture: 'Furniture',
  equipment: 'Equipment / Tools',
  other:     'Other',
};

const CONDITIONS = {
  new:  'New',
  good: 'Good',
  fair: 'Fair',
  poor: 'Poor / Damaged',
};

const STATUS_BADGE = {
  available:    'badge-green',
  assigned:     'badge-blue',
  under_repair: 'badge-amber',
  retired:      'badge-red',
  lost:         'badge-red',
};

const STATUS_LABEL = {
  available:    'Available',
  assigned:     'Assigned',
  under_repair: 'Under Repair',
  retired:      'Retired',
  lost:         'Lost',
};

const EMPTY_ASSET = {
  name: '', assetCode: '', category: 'laptop',
  brand: '', model: '', serialNumber: '',
  purchaseDate: '', purchaseCost: '', status: 'available', notes: '',
};

const FILTERS = ['all', 'available', 'assigned', 'under_repair', 'retired', 'lost'];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtCost(v) {
  if (v == null) return '—';
  return `AED ${parseFloat(v).toLocaleString('en-AE', { minimumFractionDigits: 0 })}`;
}

// ── Asset Modal (create / edit) ───────────────────────────────────────────────

function AssetModal({ asset, existingAssets = [], onSave, onClose }) {
  const [form, setForm]     = useState(asset ? { ...asset, purchaseCost: asset.purchaseCost ?? '' } : { ...EMPTY_ASSET });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState('');
  const f = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSave = async () => {
    if (!form.name.trim()) { setErr('Asset name is required.'); return; }
    // Duplicate asset code / serial number — case-insensitive, excludes self.
    const code = (form.assetCode || '').trim();
    if (code) {
      const dupCode = existingAssets.find(a => a.id !== form.id && (a.assetCode || '').trim().toLowerCase() === code.toLowerCase());
      if (dupCode) { setErr(`Asset code already used by "${dupCode.name}".`); return; }
    }
    const sn = (form.serialNumber || '').trim();
    if (sn) {
      const dupSn = existingAssets.find(a => a.id !== form.id && (a.serialNumber || '').trim().toLowerCase() === sn.toLowerCase());
      if (dupSn) { setErr(`Serial number already used by "${dupSn.name}".`); return; }
    }
    // Purchase date can't be in the future.
    const pastCheck = validatePastDate(form.purchaseDate, 'Purchase date');
    if (!pastCheck.valid) { setErr(pastCheck.message); return; }
    setSaving(true);
    try {
      await onSave({
        ...form,
        purchaseCost: form.purchaseCost !== '' ? parseFloat(form.purchaseCost) : null,
      });
      onClose();
    } catch (e) { setErr(e.message); }
    finally     { setSaving(false); }
  };

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth: 580 }}>
        <div className="modal-header">
          <h3>{asset?.id ? 'Edit Asset' : 'New Asset'}</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18}/></button>
        </div>
        <div className="modal-body">
          {err && <div className="alert alert-danger mb-3"><AlertCircle size={14}/> {err}</div>}
          <div className="form-grid form-grid-2">
            <div className="form-group" style={{ gridColumn: '1/-1' }}>
              <label>Asset Name *</label>
              <input className="form-control" value={form.name} onChange={e => f('name', e.target.value)} placeholder="e.g. Dell Latitude 5540"/>
            </div>
            <div className="form-group">
              <label>Asset Code / Tag</label>
              <input className="form-control" value={form.assetCode} onChange={e => f('assetCode', e.target.value)} placeholder="e.g. IT-0042"/>
            </div>
            <div className="form-group">
              <label>Category</label>
              <select className="form-control" value={form.category} onChange={e => f('category', e.target.value)}>
                {Object.entries(ASSET_CATEGORIES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Brand</label>
              <input className="form-control" value={form.brand} onChange={e => f('brand', e.target.value)} placeholder="e.g. Dell, Apple, Toyota"/>
            </div>
            <div className="form-group">
              <label>Model</label>
              <input className="form-control" value={form.model} onChange={e => f('model', e.target.value)} placeholder="e.g. Latitude 5540"/>
            </div>
            <div className="form-group">
              <label>Serial Number</label>
              <input className="form-control" value={form.serialNumber} onChange={e => f('serialNumber', e.target.value)} placeholder="e.g. SN123456"/>
            </div>
            <div className="form-group">
              <label>Status</label>
              <select className="form-control" value={form.status} onChange={e => f('status', e.target.value)}>
                {Object.entries(STATUS_LABEL).filter(([v]) => v !== 'assigned').map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
              <span className="hint">Cannot manually set "Assigned" — use the Assign action.</span>
            </div>
            <div className="form-group">
              <label>Purchase Date</label>
              <input className="form-control" type="date" value={form.purchaseDate || ''} onChange={e => f('purchaseDate', e.target.value)}/>
            </div>
            <div className="form-group">
              <label>Purchase Cost (AED)</label>
              <input className="form-control" type="number" min="0" step="0.01" value={form.purchaseCost} onChange={e => f('purchaseCost', e.target.value)} placeholder="0.00"/>
            </div>
            <div className="form-group" style={{ gridColumn: '1/-1' }}>
              <label>Notes</label>
              <textarea className="form-control" rows={2} value={form.notes} onChange={e => f('notes', e.target.value)} style={{ resize: 'vertical' }} placeholder="Any relevant notes…"/>
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving || !form.name.trim()}>
            {saving ? 'Saving…' : 'Save Asset'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Assign Modal ──────────────────────────────────────────────────────────────

function AssignModal({ asset, employees, onSave, onClose }) {
  const [form, setForm] = useState({
    employeeId:          '',
    assignedDate:        new Date().toISOString().split('T')[0],
    conditionAtHandover: 'good',
    notes:               '',
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState('');
  const f = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSave = async () => {
    if (!form.employeeId) { setErr('Please select an employee.'); return; }
    setSaving(true);
    try   { await onSave(form); onClose(); }
    catch (e) { setErr(e.message); }
    finally   { setSaving(false); }
  };

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth: 460 }}>
        <div className="modal-header">
          <h3>Assign Asset</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18}/></button>
        </div>
        <div className="modal-body">
          {err && <div className="alert alert-danger mb-3"><AlertCircle size={14}/> {err}</div>}
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--gray-50)', borderRadius: 6, fontSize: 13 }}>
            <strong>{asset.name}</strong>
            {asset.assetCode && <span className="text-muted" style={{ marginLeft: 6 }}>({asset.assetCode})</span>}
          </div>
          <div className="form-grid form-grid-2">
            <div className="form-group" style={{ gridColumn: '1/-1' }}>
              <label>Assign To *</label>
              <select className="form-control" value={form.employeeId} onChange={e => f('employeeId', e.target.value)}>
                <option value="">— Select employee —</option>
                {employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Assignment Date</label>
              <input className="form-control" type="date" value={form.assignedDate} onChange={e => f('assignedDate', e.target.value)}/>
            </div>
            <div className="form-group">
              <label>Condition at Handover</label>
              <select className="form-control" value={form.conditionAtHandover} onChange={e => f('conditionAtHandover', e.target.value)}>
                {Object.entries(CONDITIONS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ gridColumn: '1/-1' }}>
              <label>Notes</label>
              <input className="form-control" value={form.notes} onChange={e => f('notes', e.target.value)} placeholder="Optional handover notes…"/>
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving || !form.employeeId}>
            {saving ? 'Assigning…' : 'Assign Asset'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Return Modal ──────────────────────────────────────────────────────────────

function ReturnModal({ asset, onSave, onClose }) {
  const [form, setForm] = useState({
    returnDate:        new Date().toISOString().split('T')[0],
    conditionAtReturn: 'good',
    notes:             '',
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState('');
  const f = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSave = async () => {
    setSaving(true);
    try   { await onSave(form); onClose(); }
    catch (e) { setErr(e.message); }
    finally   { setSaving(false); }
  };

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth: 420 }}>
        <div className="modal-header">
          <h3>Return Asset</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18}/></button>
        </div>
        <div className="modal-body">
          {err && <div className="alert alert-danger mb-3"><AlertCircle size={14}/> {err}</div>}
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--gray-50)', borderRadius: 6, fontSize: 13 }}>
            <strong>{asset.name}</strong>
            {asset.currentAssignment?.employeeName && (
              <span className="text-muted" style={{ marginLeft: 6 }}>← {asset.currentAssignment.employeeName}</span>
            )}
          </div>
          <div className="form-grid form-grid-2">
            <div className="form-group">
              <label>Return Date</label>
              <input className="form-control" type="date" value={form.returnDate} onChange={e => f('returnDate', e.target.value)}/>
            </div>
            <div className="form-group">
              <label>Condition on Return</label>
              <select className="form-control" value={form.conditionAtReturn} onChange={e => f('conditionAtReturn', e.target.value)}>
                {Object.entries(CONDITIONS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ gridColumn: '1/-1' }}>
              <label>Notes</label>
              <input className="form-control" value={form.notes} onChange={e => f('notes', e.target.value)} placeholder="Optional return notes…"/>
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Confirm Return'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function AssetsManager() {
  const [tab, setTab]               = useState('assets');
  const [assets, setAssets]         = useState([]);
  const [employees, setEmployees]   = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading]       = useState(true);
  const [assignLoading, setAssignLoading] = useState(false);
  const [filter, setFilter]         = useState('all');
  const [msg, setMsg]               = useState(null);

  // Modals
  const [assetModal, setAssetModal]   = useState(null); // null | asset obj (empty = new)
  const [assignModal, setAssignModal] = useState(null); // null | asset
  const [returnModal, setReturnModal] = useState(null); // null | asset
  const [deleteConfirm, setDeleteConfirm] = useState(null); // null | assetId

  const flash = (type, text) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  };

  const loadAssets = () =>
    getAssets().then(setAssets).catch(e => flash('error', e.message));

  const loadAssignments = () => {
    setAssignLoading(true);
    getAssetAssignments().then(setAssignments).catch(e => flash('error', e.message)).finally(() => setAssignLoading(false));
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([getAssets(), getEmployees()])
      .then(([a, e]) => { setAssets(a); setEmployees(e.filter(emp => emp.active !== false)); })
      .catch(e => flash('error', e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (tab === 'assignments') loadAssignments();
  }, [tab]);

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleSaveAsset = async (asset) => {
    const saved = await saveAsset(asset);
    setAssets(prev => {
      const idx = prev.findIndex(a => a.id === saved.id);
      if (idx >= 0) { const next = [...prev]; next[idx] = { ...prev[idx], ...saved }; return next; }
      return [saved, ...prev];
    });
    flash('success', asset.id ? 'Asset updated.' : 'Asset created.');
  };

  const handleAssign = async (asset, formData) => {
    await assignAsset(asset.id, formData.employeeId, {
      assignedDate:        formData.assignedDate,
      conditionAtHandover: formData.conditionAtHandover,
      notes:               formData.notes,
    });
    await loadAssets();
    flash('success', 'Asset assigned.');
  };

  const handleReturn = async (asset, formData) => {
    await returnAsset(asset.currentAssignment.assignmentId, asset.id, {
      returnDate:        formData.returnDate,
      conditionAtReturn: formData.conditionAtReturn,
      notes:             formData.notes,
    });
    await loadAssets();
    flash('success', 'Asset returned.');
  };

  const handleDelete = async () => {
    try {
      await deleteAsset(deleteConfirm);
      setAssets(prev => prev.filter(a => a.id !== deleteConfirm));
      setDeleteConfirm(null);
      flash('success', 'Asset deleted.');
    } catch (e) { flash('error', e.message); setDeleteConfirm(null); }
  };

  // ── Derived ──────────────────────────────────────────────────────────────────

  const filtered = filter === 'all' ? assets : assets.filter(a => a.status === filter);

  const totalCount    = assets.length;
  const availCount    = assets.filter(a => a.status === 'available').length;
  const assignedCount = assets.filter(a => a.status === 'assigned').length;
  const repairCount   = assets.filter(a => a.status === 'under_repair').length;

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Asset Registry</h2>
          <p className="text-muted text-sm">Track company equipment assigned to employees</p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setAssetModal({ ...EMPTY_ASSET })}>
          <Plus size={14}/> New Asset
        </button>
      </div>

      <div className="page-body">

        {msg && (
          <div className={`alert alert-${msg.type === 'error' ? 'danger' : 'success'} mb-4`}>
            <AlertCircle size={14}/> {msg.text}
          </div>
        )}

        {/* ── Stat cards ── */}
        <div className="stats-grid mb-4" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          {[
            { label: 'Total Assets',  value: totalCount,    color: 'var(--primary)', bg: 'rgba(37,99,235,0.10)' },
            { label: 'Available',     value: availCount,    color: 'var(--success)', bg: 'rgba(22,163,74,0.10)' },
            { label: 'Assigned',      value: assignedCount, color: 'var(--accent)',  bg: 'rgba(6,182,212,0.10)' },
            { label: 'Under Repair',  value: repairCount,   color: 'var(--warning)', bg: 'rgba(245,158,11,0.10)' },
          ].map(s => (
            <div key={s.label} className="stat-card">
              <div className="stat-icon" style={{ background: s.bg }}>
                <Package size={20} color={s.color}/>
              </div>
              <div>
                <div className="stat-value">{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* ── Tab bar ── */}
        <div className="tab-bar mb-3">
          <button className={`tab-btn ${tab === 'assets' ? 'active' : ''}`} onClick={() => setTab('assets')}>
            Assets
          </button>
          <button className={`tab-btn ${tab === 'assignments' ? 'active' : ''}`} onClick={() => setTab('assignments')}>
            Assignment History
          </button>
        </div>

        {/* ══════════════════ ASSETS TAB ══════════════════ */}
        {tab === 'assets' && (
          <>
            {/* Filter chips */}
            <div className="tab-bar mb-3" style={{ flexWrap: 'wrap', gap: 4 }}>
              {FILTERS.map(f => (
                <button
                  key={f}
                  className={`tab-btn ${filter === f ? 'active' : ''}`}
                  onClick={() => setFilter(f)}
                  style={{ fontSize: 12, padding: '4px 12px' }}
                >
                  {f === 'all' ? 'All' : STATUS_LABEL[f]}
                  {f !== 'all' && (
                    <span style={{ marginLeft: 5, fontWeight: 700 }}>
                      ({assets.filter(a => a.status === f).length})
                    </span>
                  )}
                </button>
              ))}
            </div>

            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {loading ? (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading assets…</div>
              ) : filtered.length === 0 ? (
                <div style={{ padding: 48, textAlign: 'center', color: 'var(--gray-400)' }}>
                  <Package size={36} style={{ marginBottom: 12, opacity: 0.35 }}/>
                  <p>No {filter !== 'all' ? STATUS_LABEL[filter].toLowerCase() + ' ' : ''}assets found.</p>
                  {filter === 'all' && (
                    <button className="btn btn-primary btn-sm" style={{ marginTop: 12 }} onClick={() => setAssetModal({ ...EMPTY_ASSET })}>
                      <Plus size={13}/> Add First Asset
                    </button>
                  )}
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Code</th>
                        <th>Name</th>
                        <th>Category</th>
                        <th>Brand / Model</th>
                        <th>Status</th>
                        <th>Assigned To</th>
                        <th>Since</th>
                        <th>Value</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map(asset => (
                        <tr key={asset.id}>
                          <td style={{ fontFamily: 'monospace', fontSize: 12 }}>
                            {asset.assetCode || <span className="text-muted">—</span>}
                          </td>
                          <td style={{ fontWeight: 500 }}>
                            {asset.name}
                            {asset.serialNumber && (
                              <div style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 1 }}>
                                S/N: {asset.serialNumber}
                              </div>
                            )}
                          </td>
                          <td>{ASSET_CATEGORIES[asset.category] || asset.category}</td>
                          <td>
                            {[asset.brand, asset.model].filter(Boolean).join(' · ') || <span className="text-muted">—</span>}
                          </td>
                          <td>
                            <span className={`badge ${STATUS_BADGE[asset.status] || 'badge-yellow'}`}>
                              {STATUS_LABEL[asset.status] || asset.status}
                            </span>
                          </td>
                          <td>
                            {asset.currentAssignment
                              ? <span style={{ fontWeight: 500 }}>{asset.currentAssignment.employeeName}</span>
                              : <span className="text-muted">—</span>}
                          </td>
                          <td style={{ fontSize: 12 }}>
                            {asset.currentAssignment?.assignedDate || <span className="text-muted">—</span>}
                          </td>
                          <td style={{ fontSize: 12 }}>{fmtCost(asset.purchaseCost)}</td>
                          <td>
                            <div style={{ display: 'flex', gap: 4 }}>
                              {/* Assign — only if available */}
                              {asset.status === 'available' && (
                                <button
                                  className="btn btn-sm"
                                  style={{ background: 'var(--primary)', color: '#fff', border: 'none', whiteSpace: 'nowrap' }}
                                  onClick={() => setAssignModal(asset)}
                                  title="Assign to employee"
                                >
                                  Assign
                                </button>
                              )}
                              {/* Return — only if assigned */}
                              {asset.status === 'assigned' && (
                                <button
                                  className="btn btn-sm btn-outline"
                                  onClick={() => setReturnModal(asset)}
                                  style={{ whiteSpace: 'nowrap' }}
                                  title="Return from employee"
                                >
                                  Return
                                </button>
                              )}
                              {/* Edit */}
                              <button
                                className="btn btn-ghost btn-icon btn-sm"
                                onClick={() => setAssetModal(asset)}
                                title="Edit asset"
                              >
                                <Pencil size={13}/>
                              </button>
                              {/* Delete — only if not assigned */}
                              {asset.status !== 'assigned' && (
                                <button
                                  className="btn btn-ghost btn-icon btn-sm text-danger"
                                  onClick={() => setDeleteConfirm(asset.id)}
                                  title="Delete asset"
                                >
                                  <Trash2 size={13}/>
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}

        {/* ══════════════════ ASSIGNMENTS TAB ══════════════════ */}
        {tab === 'assignments' && (
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {assignLoading ? (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading history…</div>
            ) : assignments.length === 0 ? (
              <div style={{ padding: 48, textAlign: 'center', color: 'var(--gray-400)' }}>
                <Package size={36} style={{ marginBottom: 12, opacity: 0.35 }}/>
                <p>No assignment records yet.</p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Asset</th>
                      <th>Employee</th>
                      <th>Assigned</th>
                      <th>Returned</th>
                      <th>Condition Out</th>
                      <th>Condition In</th>
                      <th>Assigned By</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assignments.map(a => (
                      <tr key={a.id}>
                        <td style={{ fontWeight: 500 }}>
                          {a.assetName}
                          {a.assetCode && (
                            <div style={{ fontSize: 11, color: 'var(--gray-400)', fontFamily: 'monospace' }}>{a.assetCode}</div>
                          )}
                        </td>
                        <td>{a.employeeName || '—'}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{formatDateUAE(a.assignedDate)}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>
                          {a.returnDate
                            ? formatDateUAE(a.returnDate)
                            : <span className="badge badge-blue" style={{ fontSize: 10 }}>Active</span>}
                        </td>
                        <td>
                          <span style={{ fontSize: 12 }}>{CONDITIONS[a.conditionAtHandover] || a.conditionAtHandover}</span>
                        </td>
                        <td>
                          {a.conditionAtReturn
                            ? <span style={{ fontSize: 12 }}>{CONDITIONS[a.conditionAtReturn] || a.conditionAtReturn}</span>
                            : <span className="text-muted text-sm">—</span>}
                        </td>
                        <td style={{ fontSize: 12 }}>{a.assignedBy || '—'}</td>
                        <td style={{ fontSize: 12, maxWidth: 180 }}>
                          <span title={a.notes} style={{ display: 'block', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                            {a.notes || '—'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Modals ── */}
      {assetModal && (
        <AssetModal
          asset={assetModal.id ? assetModal : null}
          existingAssets={assets}
          onSave={handleSaveAsset}
          onClose={() => setAssetModal(null)}
        />
      )}

      {assignModal && (
        <AssignModal
          asset={assignModal}
          employees={employees}
          onSave={(formData) => handleAssign(assignModal, formData)}
          onClose={() => setAssignModal(null)}
        />
      )}

      {returnModal && (
        <ReturnModal
          asset={returnModal}
          onSave={(formData) => handleReturn(returnModal, formData)}
          onClose={() => setReturnModal(null)}
        />
      )}

      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: 380 }}>
            <div className="modal-header">
              <h3>Delete Asset</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setDeleteConfirm(null)}><X size={18}/></button>
            </div>
            <div className="modal-body">
              <p>Permanently delete this asset and all its assignment history? This cannot be undone.</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn" style={{ background: 'var(--danger)', color: '#fff', border: 'none' }} onClick={handleDelete}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
