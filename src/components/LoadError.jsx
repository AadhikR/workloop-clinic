import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function LoadError({ message, onRetry, isAdmin = true }) {
  const cardClass = isAdmin ? 'card' : 'emp-card';
  return (
    <div className={cardClass} style={{ padding: 40, textAlign: 'center' }}>
      <div style={{
        width: 48, height: 48, borderRadius: '50%', margin: '0 auto 14px',
        background: 'rgba(239,68,68,0.08)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <AlertTriangle size={22} style={{ color: '#ef4444' }} />
      </div>
      <p style={{ color: '#1e293b', fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
        Failed to load data
      </p>
      <p style={{ color: '#64748b', fontSize: 12, marginBottom: 16, lineHeight: 1.5 }}>
        {message || 'Something went wrong. Check your connection and try again.'}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '8px 18px', borderRadius: 8,
            background: '#2563eb', color: '#fff', border: 'none',
            fontSize: 12, fontWeight: 600, cursor: 'pointer',
          }}
        >
          <RefreshCw size={13} /> Retry
        </button>
      )}
    </div>
  );
}
