import { X, Download, Info } from 'lucide-react';
import { parseSIFPreview } from '../utils/sifGenerator';
import { formatDateUAE } from '../utils/uaeValidators';

export default function SIFPreviewModal({ sifContent, filename, onClose, onDownload }) {
  const lines = parseSIFPreview(sifContent);
  return (
    <div className="modal-overlay">
      <div className="modal modal-xl">
        <div className="modal-header">
          <h3>SIF Preview — {filename}</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="modal-body">
          <div className="alert alert-info mb-4">
            <Info size={16} />
            <div>
              <strong>Blue rows</strong> = Employee Detail Records (EDR) &nbsp;|&nbsp;
              <strong style={{ color: 'var(--warning)' }}>Yellow row</strong> = Salary Control Record (SCR)
            </div>
          </div>

          <div className="sif-preview">
            {lines.map((line, i) => (
              <div
                key={i}
                className={
                  line.type === 'EDR' ? 'sif-line-edr' :
                  line.type === 'SCR' ? 'sif-line-scr' : ''
                }
              >
                {line.type === 'EDR'
                  ? `EDR,${line.molId},${line.bankRouting},${line.iban},${line.startDate},${line.endDate},${line.days},${line.basic},${line.allowance},${line.leave}`
                  : line.type === 'SCR'
                  ? `SCR,${line.employerId},${line.bankRouting},${line.paymentDate},${line.sequence},${line.period},${line.count},${line.total},${line.currency},${line.description}`
                  : (line.raw || '')}
              </div>
            ))}
          </div>

          <h4 style={{ marginTop: 20, marginBottom: 10, fontWeight: 600 }}>Employee Summary</h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>MOL ID</th>
                  <th>IBAN</th>
                  <th>Period</th>
                  <th>Days</th>
                  <th>Basic (AED)</th>
                  <th>WPS Allow. (AED)</th>
                  <th>Total (AED)</th>
                </tr>
              </thead>
              <tbody>
                {lines.filter(l => l.type === 'EDR').map((l, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td className="font-mono text-sm">{l.molId}</td>
                    <td className="font-mono text-sm">{l.iban}</td>
                    <td>{formatDateUAE(l.startDate)} → {formatDateUAE(l.endDate)}</td>
                    <td>{l.days}</td>
                    <td className="text-right">{Number(l.basic).toLocaleString('en-AE')}</td>
                    <td className="text-right">{Number(l.allowance).toLocaleString('en-AE')}</td>
                    <td className="text-right font-bold">
                      {(Number(l.basic) + Number(l.allowance)).toLocaleString('en-AE')}
                    </td>
                  </tr>
                ))}
                {lines.filter(l => l.type === 'SCR').map((l, i) => (
                  <tr key={'scr' + i} style={{ background: '#fffbeb' }}>
                    <td colSpan={5} style={{ fontWeight: 600 }}>
                      TOTAL ({l.count} employees) — {l.description}
                    </td>
                    <td colSpan={2}></td>
                    <td className="text-right font-bold" style={{ color: 'var(--warning)' }}>
                      {Number(l.total).toLocaleString('en-AE')} AED
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>Close</button>
          <button className="btn btn-success" onClick={onDownload}>
            <Download size={15} /> Download {filename}
          </button>
        </div>
      </div>
    </div>
  );
}
