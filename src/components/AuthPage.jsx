import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { FileText, Mail, Lock, Eye, EyeOff, AlertCircle, CheckCircle, Loader } from 'lucide-react';

export default function AuthPage() {
  const { signIn, signUp, resetPassword } = useAuth();

  const [mode, setMode]           = useState('login');   // 'login' | 'register' | 'reset'
  const [email, setEmail]         = useState('');
  const [password, setPassword]   = useState('');
  const [confirm, setConfirm]     = useState('');
  const [showPw, setShowPw]       = useState(false);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');
  const [success, setSuccess]     = useState('');

  const clearMessages = () => { setError(''); setSuccess(''); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    clearMessages();

    if (mode === 'register' && password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    if (mode === 'register' && password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        await signIn(email, password);
        // AuthContext will update user → App re-renders automatically
      } else if (mode === 'register') {
        await signUp(email, password);
        setSuccess('Account created! Check your email to confirm your address, then log in.');
        setMode('login');
      } else if (mode === 'reset') {
        await resetPassword(email);
        setSuccess('Password reset email sent. Check your inbox.');
      }
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (m) => { setMode(m); clearMessages(); setPassword(''); setConfirm(''); };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%)',
      padding: '24px',
    }}>
      <div style={{ width: '100%', maxWidth: 420 }}>

        {/* Logo / Brand */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14,
            background: 'linear-gradient(135deg, #1a56db, #1e429f)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: '0 8px 24px rgba(26,86,219,0.4)',
          }}>
            <FileText size={28} color="white" />
          </div>
          <h1 style={{ color: 'white', fontSize: 24, fontWeight: 700, margin: 0 }}>Workloop</h1>
          <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: 13, marginTop: 6 }}>
            UAE Payroll &amp; HRMS
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: 'white',
          borderRadius: 16,
          padding: '32px 28px',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4, color: 'var(--gray-900)' }}>
            {mode === 'login'    && 'Sign in to your account'}
            {mode === 'register' && 'Create an account'}
            {mode === 'reset'    && 'Reset your password'}
          </h2>
          <p style={{ fontSize: 13, color: 'var(--gray-500)', marginBottom: 24 }}>
            {mode === 'login'    && 'Enter your credentials to continue'}
            {mode === 'register' && 'Start generating WPS SIF files for free'}
            {mode === 'reset'    && "We'll send a reset link to your email"}
          </p>

          {/* Error / Success banners */}
          {error && (
            <div className="alert alert-danger mb-4" style={{ fontSize: 13 }}>
              <AlertCircle size={15} /> {error}
            </div>
          )}
          {success && (
            <div className="alert alert-success mb-4" style={{ fontSize: 13 }}>
              <CheckCircle size={15} /> {success}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Email */}
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 13, fontWeight: 600 }}>Email address</label>
              <div style={{ position: 'relative' }}>
                <Mail size={15} style={{
                  position: 'absolute', left: 11, top: '50%',
                  transform: 'translateY(-50%)', color: 'var(--gray-400)',
                }} />
                <input
                  className="form-control"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  style={{ paddingLeft: 34 }}
                />
              </div>
            </div>

            {/* Password */}
            {mode !== 'reset' && (
              <div className="form-group" style={{ marginBottom: 16 }}>
                <label style={{ fontSize: 13, fontWeight: 600 }}>Password</label>
                <div style={{ position: 'relative' }}>
                  <Lock size={15} style={{
                    position: 'absolute', left: 11, top: '50%',
                    transform: 'translateY(-50%)', color: 'var(--gray-400)',
                  }} />
                  <input
                    className="form-control"
                    type={showPw ? 'text' : 'password'}
                    required
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                    placeholder={mode === 'register' ? 'Min. 8 characters' : '••••••••'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    style={{ paddingLeft: 34, paddingRight: 38 }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(p => !p)}
                    style={{
                      position: 'absolute', right: 10, top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: 'var(--gray-400)', padding: 2,
                    }}
                  >
                    {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>
            )}

            {/* Confirm password (register only) */}
            {mode === 'register' && (
              <div className="form-group" style={{ marginBottom: 16 }}>
                <label style={{ fontSize: 13, fontWeight: 600 }}>Confirm password</label>
                <div style={{ position: 'relative' }}>
                  <Lock size={15} style={{
                    position: 'absolute', left: 11, top: '50%',
                    transform: 'translateY(-50%)', color: 'var(--gray-400)',
                  }} />
                  <input
                    className="form-control"
                    type={showPw ? 'text' : 'password'}
                    required
                    autoComplete="new-password"
                    placeholder="Re-enter password"
                    value={confirm}
                    onChange={e => setConfirm(e.target.value)}
                    style={{ paddingLeft: 34 }}
                  />
                </div>
              </div>
            )}

            {/* Forgot password link */}
            {mode === 'login' && (
              <div style={{ textAlign: 'right', marginBottom: 20, marginTop: -8 }}>
                <button
                  type="button"
                  onClick={() => switchMode('reset')}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--primary)', fontSize: 12, fontWeight: 500,
                  }}
                >
                  Forgot password?
                </button>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: mode === 'register' ? 8 : 0 }}
            >
              {loading
                ? <><Loader size={15} style={{ animation: 'spin 1s linear infinite' }} /> Please wait…</>
                : mode === 'login'    ? 'Sign in'
                : mode === 'register' ? 'Create account'
                : 'Send reset email'
              }
            </button>
          </form>

          {/* Mode switcher */}
          <div style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: 'var(--gray-500)' }}>
            {mode === 'login' && (
              <>Don't have an account?{' '}
                <button type="button" onClick={() => switchMode('register')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary)', fontWeight: 600 }}>
                  Sign up
                </button>
              </>
            )}
            {(mode === 'register' || mode === 'reset') && (
              <>Already have an account?{' '}
                <button type="button" onClick={() => switchMode('login')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary)', fontWeight: 600 }}>
                  Sign in
                </button>
              </>
            )}
          </div>
        </div>

        <p style={{ textAlign: 'center', color: 'rgba(255,255,255,0.3)', fontSize: 11, marginTop: 20 }}>
          Your data is encrypted and stored securely. We never share your payroll data.
        </p>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .alert-success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; border-radius: 8px; padding: 10px 14px; display: flex; align-items: flex-start; gap: 8px; }
        .alert-danger  { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; border-radius: 8px; padding: 10px 14px; display: flex; align-items: flex-start; gap: 8px; }
      `}</style>
    </div>
  );
}
