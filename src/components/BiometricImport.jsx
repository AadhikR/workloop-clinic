/**
 * BiometricImport.jsx — Feature 2.2: Biometric / Punching Machine Integration
 *
 * Two panels:
 *   1. Upload & Preview — parse CSV, show matched/unmatched punches, confirm import
 *   2. Badge Mappings   — map device badge numbers to system employees
 */
import { useState, useEffect, useRef } from 'react';
import { Upload, X, Check, AlertCircle, Fingerprint, Trash2 } from 'lucide-react';
import {
  getBiometricMappings, saveBiometricMapping, deleteBiometricMapping,
  parseBiometricCsv, importBiometricPunches,
} from '../utils/biometricStorage';

function formatDT(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-AE', { dateStyle: 'short', timeStyle: 'short' });
}

export default function BiometricImport({ employees = [] }) {
  const [mappings,       setMappings]       = useState([]);
  const [loadingMaps,    setLoadingMaps]    = useState(true);
  const [parsedPunches,  setParsedPunches]  = useState([]);
  const [parseError,     setParseError]     = useState('');
  const [importing,      setImporting]      = useState(false);
  const [importResult,   setImportResult]   = useState(null);
  const [newMap,         setNewMap]         = useState({ badgeNo: '', employeeId: '', deviceName: 'Main Entrance' });
  const [savingMap,      setSavingMap]      = useState(false);
  const [mapMsg,         setMapMsg]         = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    getBiometricMappings()
      .then(m => { setMappings(m); setLoadingMaps(false); })
      .catch(() => setLoadingMaps(false));
  }, []);

  // Enrich parsed punches with employee lookup via mappings
  const enriched = parsedPunches.map(p => {
    const map = mappings.find(m => m.badgeNo === p.badgeNo);
    const emp = map ? employees.find(e => e.id === map.employeeId) : null;
    return { ...p, employeeId: map?.employeeId ?? null, employeeName: emp?.name ?? null };
  });

  const matched         = enriched.filter(p => p.employeeId);
  const unmatchedBadges = [...new Set(enriched.filter(p => !p.employeeId).map(p => p.badgeNo))];

  // ── File handling ─────────────────────────────────────────────────────────

  const handleFile = e => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      try {
        const punches = parseBiometricCsv(ev.target.result);
        setParsedPunches(punches);
        setParseError('');
        setImportResult(null);
      } catch (err) {
        setParseError(err.message);
        setParsedPunches([]);
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handleDrop = e => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) { fileRef.current.files = e.dataTransfer.files; handleFile({ target: { files: e.dataTransfer.files } }); }
  };

  // ── Import ────────────────────────────────────────────────────────────────

  const handleImport = async () => {
    if (matched.length === 0) return;
    setImporting(true);
    try {
      const result = await importBiometricPunches(matched);
      setImportResult(result);
      setParsedPunches([]);
    } catch (err) {
      setParseError('Import failed: ' + err.message);
    } finally {
      setImporting(false);
    }
  };

  // ── Badge mappings ────────────────────────────────────────────────────────

  const handleSaveMap = async () => {
    if (!newMap.badgeNo.trim() || !newMap.employeeId) return;
    // Duplicate badge check — a badge should point to exactly one employee.
    // The upstream `saveBiometricMapping` already upserts by badgeNo, so this
    // is a UX guard: warn the admin before silently re-pointing an existing
    // mapping to a different employee.
    const trimmedBadge = newMap.badgeNo.trim();
    const existing = mappings.find(m => m.badgeNo === trimmedBadge);
    if (existing && existing.employeeId !== newMap.employeeId) {
      const currentEmp = employees.find(e => e.id === existing.employeeId);
      const targetEmp  = employees.find(e => e.id === newMap.employeeId);
      const proceed = window.confirm(
        `Badge ${trimmedBadge} is currently mapped to ${currentEmp?.name || 'another employee'}. ` +
        `Re-point it to ${targetEmp?.name || 'the new employee'}?`,
      );
      if (!proceed) return;
    }
    setSavingMap(true);
    setMapMsg(null);
    try {
      const saved = await saveBiometricMapping(newMap);
      setMappings(prev => {
        const idx = prev.findIndex(m => m.badgeNo === saved.badgeNo);
        return idx >= 0 ? prev.map((m, i) => i === idx ? saved : m) : [...prev, saved];
      });
      setNewMap(p => ({ ...p, badgeNo: '', employeeId: '' }));
      setMapMsg({ type: 'success', text: `Badge ${saved.badgeNo} mapped.` });
      setTimeout(() => setMapMsg(null), 3000);
    } catch (err) {
      setMapMsg({ type: 'danger', text: err.message });
    } finally {
      setSavingMap(false);
    }
  };

  const handleDeleteMap = async id => {
    try {
      await deleteBiometricMapping(id);
      setMappings(prev => prev.filter(m => m.id !== id));
    } catch (err) {
      setMapMsg({ type: 'danger', text: 'Delete failed: ' + err.message });
    }
  };

  // Pre-fill badge when clicking an unmatched badge pill
  const fillBadge = badgeNo => setNewMap(p => ({ ...p, badgeNo }));

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div>
      {/* ── Panel 1: Upload & Preview ── */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Fingerprint size={16} /> Biometric Punch Import
          </h3>
          <button
            className="btn btn-primary btn-sm"
            style={{ display: 'flex', alignItems: 'center', gap: 5 }}
            onClick={() => fileRef.current?.click()}
          >
            <Upload size={13} /> Upload CSV
          </button>
          <input
            ref={fileRef}
            type="file" accept=".csv,.txt"
            style={{ display: 'none' }}
            onChange={handleFile}
          />
        </div>

        <div className="card-body">
          {/* Format help */}
          <p style={{ fontSize: 12, color: 'var(--gray-500)', marginBottom: 12 }}>
            Export punch data from your biometric device software as CSV and upload here. Auto-detects
            ZKTeco Report, ZKTeco Simple, and generic formats (BadgeNo / DateTime / PunchType).
          </p>

          {/* Result banner */}
          {importResult && (
            <div className="alert alert-success" style={{ marginBottom: 12 }}>
              <Check size={13} />
              &nbsp;{importResult.imported} punch{importResult.imported !== 1 ? 'es' : ''} imported.
              {importResult.skipped > 0 && ` ${importResult.skipped} already existed and were skipped.`}
            </div>
          )}

          {parseError && (
            <div className="alert alert-danger" style={{ marginBottom: 12 }}>
              <AlertCircle size={13} /> {parseError}
            </div>
          )}

          {/* Drop zone (shown when no data) */}
          {parsedPunches.length === 0 && !parseError && (
            <div
              style={{
                border: '2px dashed var(--gray-200)', borderRadius: 10,
                padding: '32px 20px', textAlign: 'center', cursor: 'pointer',
                transition: 'border-color 0.15s',
              }}
              onClick={() => fileRef.current?.click()}
              onDragOver={e => e.preventDefault()}
              onDrop={handleDrop}
            >
              <Fingerprint size={32} style={{ margin: '0 auto 10px', display: 'block', opacity: 0.2 }} />
              <p style={{ fontSize: 13, color: 'var(--gray-500)', marginBottom: 4 }}>
                Drop a CSV file here or click to browse
              </p>
              <p style={{ fontSize: 11, color: 'var(--gray-400)' }}>
                ZKTeco · Suprema · Any generic punch CSV
              </p>
            </div>
          )}

          {/* Parsed data summary + preview */}
          {parsedPunches.length > 0 && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>
                  {parsedPunches.length} punches parsed
                </span>
                <span style={{ fontSize: 12, color: 'var(--success)', fontWeight: 500 }}>
                  ✓ {matched.length} matched
                </span>
                {unmatchedBadges.length > 0 && (
                  <span style={{ fontSize: 12, color: 'var(--danger)', fontWeight: 500 }}>
                    ⚠ {unmatchedBadges.length} unrecognized badge{unmatchedBadges.length > 1 ? 's' : ''}
                  </span>
                )}
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}
                  onClick={() => { setParsedPunches([]); setParseError(''); setImportResult(null); }}
                >
                  <X size={12} /> Clear
                </button>
              </div>

              {/* Unmatched badge pills → click to pre-fill mapping form */}
              {unmatchedBadges.length > 0 && (
                <div style={{
                  background: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.15)',
                  borderRadius: 8, padding: '10px 14px', marginBottom: 12,
                }}>
                  <p style={{ fontSize: 12, color: 'var(--danger)', fontWeight: 600, marginBottom: 6 }}>
                    <AlertCircle size={12} style={{ marginRight: 4 }} />
                    These badges have no employee mapping — their punches will be skipped:
                  </p>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {unmatchedBadges.map(b => (
                      <button
                        key={b}
                        className="btn btn-ghost btn-sm"
                        style={{
                          fontFamily: 'monospace', fontWeight: 700, fontSize: 12,
                          border: '1px solid rgba(239,68,68,0.3)', color: 'var(--danger)',
                        }}
                        onClick={() => fillBadge(b)}
                        title="Click to map this badge to an employee below"
                      >
                        {b}
                      </button>
                    ))}
                  </div>
                  <p style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 6 }}>
                    Click a badge to pre-fill the mapping form below, then save. The import preview will update automatically.
                  </p>
                </div>
              )}

              {/* Preview table */}
              <div className="table-wrap" style={{ maxHeight: 260, overflowY: 'auto', borderRadius: 8 }}>
                <table style={{ fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th>Badge</th>
                      <th>Employee</th>
                      <th>Date &amp; Time</th>
                      <th>Punch</th>
                    </tr>
                  </thead>
                  <tbody>
                    {enriched.slice(0, 300).map((p, i) => (
                      <tr key={i} style={{ opacity: p.employeeId ? 1 : 0.4 }}>
                        <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{p.badgeNo}</td>
                        <td>
                          {p.employeeName
                            ? p.employeeName
                            : <span style={{ color: 'var(--danger)', fontSize: 11 }}>Unknown badge</span>}
                        </td>
                        <td>{formatDT(p.eventTime)}</td>
                        <td>
                          <span className={`badge ${p.eventType === 'CLOCK_IN' ? 'badge-green' : 'badge-blue'}`} style={{ fontSize: 10 }}>
                            {p.eventType === 'CLOCK_IN' ? '▶ IN' : '■ OUT'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {enriched.length > 300 && (
                  <p style={{ fontSize: 11, color: 'var(--gray-400)', textAlign: 'center', padding: '6px 0' }}>
                    Showing 300 of {enriched.length} — all matched will be imported.
                  </p>
                )}
              </div>

              <div style={{ marginTop: 14, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                {matched.length === 0 && (
                  <span style={{ fontSize: 12, color: 'var(--gray-400)', alignSelf: 'center' }}>
                    No matched punches to import. Add badge mappings below.
                  </span>
                )}
                <button
                  className="btn btn-primary"
                  onClick={handleImport}
                  disabled={importing || matched.length === 0}
                  style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  {importing
                    ? 'Importing…'
                    : <><Check size={14} /> Import {matched.length} Matched Punch{matched.length !== 1 ? 'es' : ''}</>}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Panel 2: Badge Mappings ── */}
      <div className="card">
        <div className="card-header">
          <h3>Badge → Employee Mappings</h3>
          <span style={{ fontSize: 12, color: 'var(--gray-500)', fontWeight: 400 }}>
            {mappings.length} configured
          </span>
        </div>
        <div className="card-body">
          {mapMsg && (
            <div className={`alert alert-${mapMsg.type}`} style={{ marginBottom: 12 }}>
              {mapMsg.text}
            </div>
          )}

          {/* Add form */}
          <div style={{
            display: 'flex', gap: 10, alignItems: 'flex-end',
            flexWrap: 'wrap', marginBottom: 20,
            padding: '14px 16px', borderRadius: 8,
            background: 'var(--gray-50)', border: '1px solid var(--gray-200)',
          }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label style={{ fontSize: 11 }}>Badge / Device ID</label>
              <input
                className="form-control"
                style={{ width: 110, fontFamily: 'monospace', fontWeight: 600 }}
                placeholder="00001"
                value={newMap.badgeNo}
                onChange={e => setNewMap(p => ({ ...p, badgeNo: e.target.value.trim() }))}
              />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label style={{ fontSize: 11 }}>Employee</label>
              <select
                className="form-control"
                style={{ width: 210 }}
                value={newMap.employeeId}
                onChange={e => setNewMap(p => ({ ...p, employeeId: e.target.value }))}
              >
                <option value="">— Select —</option>
                {employees.filter(e => e.employmentStatus !== 'Terminated').map(e => (
                  <option key={e.id} value={e.id}>{e.name}</option>
                ))}
              </select>
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label style={{ fontSize: 11 }}>Device / Location</label>
              <input
                className="form-control"
                style={{ width: 140 }}
                placeholder="e.g. Main Entrance"
                value={newMap.deviceName}
                onChange={e => setNewMap(p => ({ ...p, deviceName: e.target.value }))}
              />
            </div>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleSaveMap}
              disabled={savingMap || !newMap.badgeNo || !newMap.employeeId}
              style={{ display: 'flex', alignItems: 'center', gap: 5 }}
            >
              {savingMap ? 'Saving…' : <><Check size={13} /> Add Mapping</>}
            </button>
          </div>

          {/* Mappings table */}
          {loadingMaps ? (
            <p style={{ fontSize: 13, color: 'var(--gray-400)', padding: '12px 0' }}>Loading…</p>
          ) : mappings.length === 0 ? (
            <div className="empty-state">
              <Fingerprint size={32} style={{ margin: '0 auto 10px', display: 'block', opacity: 0.2 }} />
              <h3>No badge mappings yet</h3>
              <p>Add each employee's biometric badge number above so the importer can match their punches.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Badge / Device ID</th>
                    <th>Employee</th>
                    <th>Department</th>
                    <th>Device / Location</th>
                    <th>Added</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {mappings.map(m => {
                    const emp = employees.find(e => e.id === m.employeeId);
                    return (
                      <tr key={m.id}>
                        <td style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 13 }}>{m.badgeNo}</td>
                        <td style={{ fontWeight: 500, fontSize: 13 }}>
                          {emp ? emp.name : <span style={{ color: 'var(--danger)', fontSize: 12 }}>Employee removed</span>}
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--gray-500)' }}>{emp?.department || '—'}</td>
                        <td style={{ fontSize: 12, color: 'var(--gray-500)' }}>{m.deviceName || '—'}</td>
                        <td style={{ fontSize: 12, color: 'var(--gray-400)' }}>{m.createdAt?.substring(0, 10) || '—'}</td>
                        <td>
                          <button
                            className="btn btn-ghost btn-icon btn-sm text-danger"
                            title="Remove mapping"
                            onClick={() => handleDeleteMap(m.id)}
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
