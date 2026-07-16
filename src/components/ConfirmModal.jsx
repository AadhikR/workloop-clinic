import { useRef, useEffect } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { useEscapeKey } from '../utils/useEscapeKey';

export default function ConfirmModal({
  title = 'Confirm',
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  onConfirm,
  onCancel,
}) {
  const confirmRef = useRef(null);
  useEscapeKey(onCancel);
  useEffect(() => {
    confirmRef.current?.focus();
  }, []);
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-modal-title"
      aria-describedby="confirm-modal-desc"
      style={{
        position: 'fixed', inset: 0, zIndex: 3000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
      <div
        style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.25)' }}
        onClick={onCancel}
      />
      <div style={{
        position: 'relative', zIndex: 3001,
        background: '#fff', borderRadius: 14, padding: '28px 24px 20px',
        width: 380, maxWidth: '90vw',
        boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
      }}>
        <button
          onClick={onCancel}
          aria-label="Close dialog"
          style={{
            position: 'absolute', top: 12, right: 12,
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#94a3b8', padding: 4,
          }}
        >
          <X size={16} aria-hidden="true" />
        </button>

        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
          {destructive && (
            <div aria-hidden="true" style={{
              width: 40, height: 40, borderRadius: 10, flexShrink: 0,
              background: 'rgba(239,68,68,0.08)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <AlertTriangle size={20} style={{ color: '#ef4444' }} />
            </div>
          )}
          <div style={{ flex: 1 }}>
            <div id="confirm-modal-title" style={{ fontWeight: 700, fontSize: 15, color: '#0f172a', marginBottom: 6 }}>
              {title}
            </div>
            <div id="confirm-modal-desc" style={{ fontSize: 13, color: '#64748b', lineHeight: 1.6 }}>
              {message}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
          <button
            onClick={onCancel}
            style={{
              padding: '8px 18px', borderRadius: 8, fontSize: 13, fontWeight: 600,
              background: '#f1f5f9', color: '#475569', border: 'none', cursor: 'pointer',
            }}
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            style={{
              padding: '8px 18px', borderRadius: 8, fontSize: 13, fontWeight: 600,
              background: destructive ? '#ef4444' : '#2563eb',
              color: '#fff', border: 'none', cursor: 'pointer',
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
