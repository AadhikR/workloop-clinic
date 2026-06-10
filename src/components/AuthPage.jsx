import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { FileText, Mail, Lock, Eye, EyeOff, AlertCircle, CheckCircle, Building2, User, ArrowLeft, Loader } from 'lucide-react';

const BG_STYLE = {
  background: '#EEF2F7',
  backgroundImage: [
    'radial-gradient(ellipse 70% 55% at 15% 40%, rgba(255,71,67,0.07) 0%, transparent 65%)',
    'radial-gradient(ellipse 60% 45% at 85% 18%, rgba(255,107,107,0.05) 0%, transparent 65%)',
    'radial-gradient(ellipse 50% 40% at 55% 88%, rgba(255,71,67,0.04) 0%, transparent 60%)',
  ].join(', '),
};

function PasswordInput({ value, onChange, placeholder = '••••••••', autoComplete = 'current-password' }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <Lock size={15} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
      <input
        className="form-control"
        type={show ? 'text' : 'password'}
        required
        autoComplete={autoComplete}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        style={{ paddingLeft: 34, paddingRight: 38 }}
      />
      <button type="button" onClick={() => setShow(s => !s)} style={{
        position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
        background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-400)', padding: 2,
      }}>
        {show ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
    </div>
  );
}

function Card({ children }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.72)',
      backdropFilter: 'saturate(180%) blur(32px)',
      WebkitBackdropFilter: 'saturate(180%) blur(32px)',
      border: '1px solid rgba(255,255,255,0.65)',
      borderRadius: 22,
      padding: '32px 28px',
      boxShadow: '0 8px 40px rgba(0,0,0,0.09), 0 2px 8px rgba(0,0,0,0.05)',
      width: '100%', maxWidth: 420,
    }}>
      {children}
    </div>
  );
}

function ErrorBanner({ msg }) {
  if (!msg) return null;
  return (
    <div className="alert alert-danger mb-4" style={{ fontSize: 13 }}>
      <AlertCircle size={15} style={{ flexShrink: 0 }} /> {msg}
    </div>
  );
}

function SuccessBanner({ msg }) {
  if (!msg) return null;
  return (
    <div className="alert alert-success mb-4" style={{ fontSize: 13 }}>
      <CheckCircle size={15} style={{ flexShrink: 0 }} /> {msg}
    </div>
  );
}

// ── Landing ──────────────────────────────────────────────────────────────────
function Landing({ onSelect }) {
  return (
    <Card>
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--gray-900)', marginBottom: 6 }}>Welcome to Workloop</h2>
        <p style={{ fontSize: 13, color: 'var(--gray-500)' }}>UAE Payroll &amp; HR Management</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <button
          className="btn btn-primary"
          style={{ width: '100%', justifyContent: 'center', gap: 10, padding: '13px 20px' }}
          onClick={() => onSelect('create')}
        >
          <Building2 size={16} />
          Create a Company Account
        </button>

        <button
          className="btn btn-outline"
          style={{ width: '100%', justifyContent: 'center', gap: 10, padding: '13px 20px' }}
          onClick={() => onSelect('admin')}
        >
          <User size={16} />
          Sign in as Admin
        </button>

        <button
          className="btn btn-outline"
          style={{ width: '100%', justifyContent: 'center', gap: 10, padding: '13px 20px' }}
          onClick={() => onSelect('employee')}
        >
          <User size={16} />
          Sign in as Employee
        </button>
      </div>

      <p style={{ fontSize: 12, color: 'var(--gray-400)', textAlign: 'center', marginTop: 20 }}>
        Employees: your HR admin must add your work email before you can sign in.
      </p>
    </Card>
  );
}

// ── Create Company ───────────────────────────────────────────────────────────
function CreateCompanyForm({ onBack, onGoAdmin }) {
  const { createCompany } = useAuth();
  const [company, setCompany]   = useState('');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  // show == true while we wait for setUser/setProfile to propagate and portal to load
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) { setError('Passwords do not match.'); return; }
    if (password.length < 8)  { setError('Password must be at least 8 characters.'); return; }
    setLoading(true);
    try {
      await createCompany(company.trim(), email.trim().toLowerCase(), password);
      // createCompany called setUser/setProfile — App.jsx will render the portal
      // on the next render cycle. Show a brief "Setting up…" state.
      setSubmitted(true);
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <div style={{
            width: 48, height: 48,
            border: '3px solid rgba(255,71,67,0.18)',
            borderTopColor: '#FF4743', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
            margin: '0 auto 20px',
          }} />
          <p style={{ fontSize: 14, color: 'var(--gray-600)', fontWeight: 500 }}>Setting up your company…</p>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <button type="button" onClick={onBack} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-500)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, marginBottom: 20, padding: 0 }}>
        <ArrowLeft size={14} /> Back
      </button>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4, color: 'var(--gray-900)' }}>Create Company Account</h2>
      <p style={{ fontSize: 13, color: 'var(--gray-500)', marginBottom: 24 }}>Set up your company and admin access</p>

      <ErrorBanner msg={error} />

      {/* Quick link when they already have an account */}
      {/already registered/i.test(error) && (
        <div style={{ textAlign: 'center', marginTop: -8, marginBottom: 16, fontSize: 13 }}>
          <button type="button" onClick={onGoAdmin}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary)', fontWeight: 600, textDecoration: 'underline' }}>
            Go to Admin Sign In →
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group" style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Company name</label>
          <div style={{ position: 'relative' }}>
            <Building2 size={15} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
            <input className="form-control" type="text" required placeholder="Acme LLC" value={company}
              onChange={e => setCompany(e.target.value)} style={{ paddingLeft: 34 }} />
          </div>
        </div>

        <div className="form-group" style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Admin email</label>
          <div style={{ position: 'relative' }}>
            <Mail size={15} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
            <input className="form-control" type="email" required autoComplete="email"
              placeholder="admin@company.com" value={email}
              onChange={e => setEmail(e.target.value)} style={{ paddingLeft: 34 }} />
          </div>
        </div>

        <div className="form-group" style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Password</label>
          <PasswordInput value={password} onChange={e => setPassword(e.target.value)}
            placeholder="Min. 8 characters" autoComplete="new-password" />
        </div>

        <div className="form-group" style={{ marginBottom: 24 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Confirm password</label>
          <PasswordInput value={confirm} onChange={e => setConfirm(e.target.value)}
            placeholder="Re-enter password" autoComplete="new-password" />
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}
          style={{ width: '100%', justifyContent: 'center' }}>
          {loading ? <><Loader size={15} style={{ animation: 'spin 1s linear infinite' }} /> Creating…</> : 'Create Company Account'}
        </button>
      </form>
    </Card>
  );
}

// ── Admin Sign In ─────────────────────────────────────────────────────────────
function AdminSignInForm({ onBack }) {
  const { signInAsAdmin, resetPassword } = useAuth();
  const [email, setEmail]         = useState('');
  const [password, setPassword]   = useState('');
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');
  const [resetSent, setResetSent] = useState(false);
  // show brief "signing in…" card after successful auth while portal loads
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signInAsAdmin(email.trim().toLowerCase(), password);
      setSubmitted(true);
    } catch (err) {
      setError(err.message || 'Sign-in failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!email) { setError('Enter your email address first.'); return; }
    setError('');
    try {
      await resetPassword(email.trim().toLowerCase());
      setResetSent(true);
    } catch (err) {
      setError(err.message || 'Failed to send reset email. Try again.');
    }
  };

  if (submitted) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <div style={{
            width: 48, height: 48,
            border: '3px solid rgba(255,71,67,0.18)',
            borderTopColor: '#FF4743', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
            margin: '0 auto 20px',
          }} />
          <p style={{ fontSize: 14, color: 'var(--gray-600)', fontWeight: 500 }}>Signing in…</p>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <button type="button" onClick={onBack} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-500)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, marginBottom: 20, padding: 0 }}>
        <ArrowLeft size={14} /> Back
      </button>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4, color: 'var(--gray-900)' }}>Admin Sign In</h2>
      <p style={{ fontSize: 13, color: 'var(--gray-500)', marginBottom: 24 }}>Sign in to manage your company</p>

      <ErrorBanner msg={error} />
      {resetSent && <SuccessBanner msg="Password reset email sent — check your inbox." />}

      <form onSubmit={handleSubmit}>
        <div className="form-group" style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Email address</label>
          <div style={{ position: 'relative' }}>
            <Mail size={15} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
            <input className="form-control" type="email" required autoComplete="email"
              placeholder="admin@company.com" value={email}
              onChange={e => setEmail(e.target.value)} style={{ paddingLeft: 34 }} />
          </div>
        </div>

        <div className="form-group" style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Password</label>
          <PasswordInput value={password} onChange={e => setPassword(e.target.value)} />
        </div>

        <div style={{ textAlign: 'right', marginBottom: 20 }}>
          <button type="button" onClick={handleReset}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary)', fontSize: 12, fontWeight: 500 }}>
            Forgot password?
          </button>
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}
          style={{ width: '100%', justifyContent: 'center' }}>
          {loading ? <><Loader size={15} style={{ animation: 'spin 1s linear infinite' }} /> Signing in…</> : 'Sign in as Admin'}
        </button>
      </form>
    </Card>
  );
}

// ── Employee Sign In / Sign Up ────────────────────────────────────────────────
function EmployeeSignInForm({ onBack }) {
  const { signInAsEmployee, signUpAsEmployee } = useAuth();
  const [mode, setMode]             = useState('signin'); // 'signin' | 'signup'
  const [email, setEmail]           = useState('');
  const [password, setPassword]     = useState('');
  const [confirm, setConfirm]       = useState('');
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  // show brief "signing in…" card after successful sign-in while portal loads
  const [submitted, setSubmitted]   = useState(false);

  const switchMode = (m) => {
    setMode(m);
    setError('');
    setSuccessMsg('');
    setPassword('');
    setConfirm('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    if (mode === 'signup') {
      if (password !== confirm) { setError('Passwords do not match.'); return; }
      if (password.length < 8)  { setError('Password must be at least 8 characters.'); return; }
    }
    setLoading(true);
    try {
      if (mode === 'signin') {
        await signInAsEmployee(email.trim().toLowerCase(), password);
        setSubmitted(true); // portal will load shortly
      } else {
        await signUpAsEmployee(email.trim().toLowerCase(), password);
        // Account created but NOT auto-logged-in. Switch to sign-in and tell the user.
        setSuccessMsg('Account created! Sign in below with your email and password.');
        switchMode('signin');
      }
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const isSignUp = mode === 'signup';

  if (submitted) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <div style={{
            width: 48, height: 48,
            border: '3px solid rgba(255,71,67,0.18)',
            borderTopColor: '#FF4743', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
            margin: '0 auto 20px',
          }} />
          <p style={{ fontSize: 14, color: 'var(--gray-600)', fontWeight: 500 }}>Signing in…</p>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <button type="button" onClick={onBack} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-500)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, marginBottom: 20, padding: 0 }}>
        <ArrowLeft size={14} /> Back
      </button>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4, color: 'var(--gray-900)' }}>
        {isSignUp ? 'Employee Sign Up' : 'Employee Sign In'}
      </h2>
      <p style={{ fontSize: 13, color: 'var(--gray-500)', marginBottom: 24 }}>
        {isSignUp ? 'Create your account using your work email' : 'Access your payslips, leave & attendance'}
      </p>

      <SuccessBanner msg={successMsg} />
      <ErrorBanner msg={error} />

      {/* If they get a "already registered" error during signup, offer a quick switch */}
      {isSignUp && /already registered/i.test(error) && (
        <div style={{ textAlign: 'center', marginTop: -8, marginBottom: 16, fontSize: 13 }}>
          <button type="button" onClick={() => switchMode('signin')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary)', fontWeight: 600, textDecoration: 'underline' }}>
            Switch to Sign In →
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group" style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Work email</label>
          <div style={{ position: 'relative' }}>
            <Mail size={15} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-400)' }} />
            <input className="form-control" type="email" required autoComplete="email"
              placeholder="you@company.com" value={email}
              onChange={e => setEmail(e.target.value)} style={{ paddingLeft: 34 }} />
          </div>
        </div>

        <div className="form-group" style={{ marginBottom: isSignUp ? 16 : 24 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Password</label>
          <PasswordInput value={password} onChange={e => setPassword(e.target.value)}
            placeholder={isSignUp ? 'Min. 8 characters' : '••••••••'}
            autoComplete={isSignUp ? 'new-password' : 'current-password'} />
        </div>

        {isSignUp && (
          <div className="form-group" style={{ marginBottom: 24 }}>
            <label style={{ fontSize: 13, fontWeight: 600 }}>Confirm password</label>
            <PasswordInput value={confirm} onChange={e => setConfirm(e.target.value)}
              placeholder="Re-enter password" autoComplete="new-password" />
          </div>
        )}

        <button type="submit" className="btn btn-primary" disabled={loading}
          style={{ width: '100%', justifyContent: 'center' }}>
          {loading
            ? <><Loader size={15} style={{ animation: 'spin 1s linear infinite' }} /> {isSignUp ? 'Creating account…' : 'Signing in…'}</>
            : isSignUp ? 'Create Employee Account' : 'Sign in as Employee'}
        </button>
      </form>

      <div style={{ textAlign: 'center', marginTop: 16, fontSize: 13, color: 'var(--gray-500)' }}>
        {isSignUp ? (
          <>Already have an account?{' '}
            <button type="button" onClick={() => switchMode('signin')}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary)', fontWeight: 600 }}>
              Sign in
            </button>
          </>
        ) : (
          <>First time here?{' '}
            <button type="button" onClick={() => switchMode('signup')}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary)', fontWeight: 600 }}>
              Create account
            </button>
          </>
        )}
      </div>

      {!isSignUp && (
        <p style={{ fontSize: 12, color: 'var(--gray-400)', textAlign: 'center', marginTop: 8 }}>
          Your HR admin must add your work email before you can sign up.
        </p>
      )}
    </Card>
  );
}

// ── Root export ───────────────────────────────────────────────────────────────
export default function AuthPage() {
  const [view, setView] = useState('landing');

  const renderView = () => {
    switch (view) {
      case 'create':
        return <CreateCompanyForm onBack={() => setView('landing')} onGoAdmin={() => setView('admin')} />;
      case 'admin':
        return <AdminSignInForm onBack={() => setView('landing')} />;
      case 'employee':
        return <EmployeeSignInForm onBack={() => setView('landing')} />;
      default:
        return <Landing onSelect={setView} />;
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      ...BG_STYLE, padding: '24px',
    }}>
      {/* Brand header */}
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <div style={{
          width: 56, height: 56, borderRadius: 16,
          background: 'linear-gradient(135deg, #FF4743 0%, #FF6B6B 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 14px',
          boxShadow: '0 8px 28px rgba(255,71,67,0.30)',
        }}>
          <FileText size={28} color="white" />
        </div>
        <h1 style={{ color: '#0F172A', fontSize: 24, fontWeight: 700, margin: 0, letterSpacing: '-0.4px' }}>Workloop</h1>
        <p style={{ color: '#64748B', fontSize: 13, marginTop: 4 }}>UAE Payroll &amp; HRMS</p>
      </div>

      {renderView()}

      <p style={{ color: '#94A3B8', fontSize: 11, marginTop: 20 }}>
        Your data is encrypted and stored securely.
      </p>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .alert-success { background: rgba(22,163,74,0.09); border: 1px solid rgba(22,163,74,0.18); color: #15803D; border-radius: 10px; padding: 10px 14px; display: flex; align-items: flex-start; gap: 8px; }
        .alert-danger  { background: rgba(220,38,38,0.09); border: 1px solid rgba(220,38,38,0.18); color: #991B1B; border-radius: 10px; padding: 10px 14px; display: flex; align-items: flex-start; gap: 8px; }
        .mb-4 { margin-bottom: 16px; }
      `}</style>
    </div>
  );
}
