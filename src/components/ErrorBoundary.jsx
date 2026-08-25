import { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

function safeErrorMessage(error) {
  if (typeof error === 'string') return error;
  if (typeof error?.message === 'string') return error.message;
  return 'An unexpected error occurred.';
}

export default class ErrorBoundary extends Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: '#f8fafc', padding: 24,
      }}>
        <div style={{
          maxWidth: 420, textAlign: 'center', background: '#fff',
          borderRadius: 16, padding: '48px 32px',
          boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
        }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%', margin: '0 auto 20px',
            background: 'rgba(239,68,68,0.08)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <AlertTriangle size={28} style={{ color: '#ef4444' }} />
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', marginBottom: 8 }}>
            Something went wrong
          </h2>
          <p style={{ fontSize: 13, color: '#64748b', lineHeight: 1.6, marginBottom: 24 }}>
            An unexpected error occurred. Your data is safe — reload the page to continue.
          </p>
          {this.state.error && (
            <pre style={{
              fontSize: 11, color: '#94a3b8', background: '#f1f5f9',
              borderRadius: 8, padding: '10px 14px', marginBottom: 20,
              textAlign: 'left', overflow: 'auto', maxHeight: 80,
            }}>
              {safeErrorMessage(this.state.error)}
            </pre>
          )}
          <button
            onClick={this.handleReload}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '10px 24px', borderRadius: 10,
              background: '#2563eb', color: '#fff', border: 'none',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}
          >
            <RefreshCw size={14} /> Reload Page
          </button>
        </div>
      </div>
    );
  }
}
