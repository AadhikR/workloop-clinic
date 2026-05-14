import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { FileText, Mail, Lock, Eye, EyeOff, AlertCircle, Building2, User, ArrowLeft, Loader } from 'lucide-react';

const BG = 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%)';

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
      background: 'white', borderRadius: 16, padding: '32px 28px',
      boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
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
      <AlertCircle size={15} /> {msg}
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
function CreateCompanyForm({ onBack }) {
  const { createCompany } = useAuth();
  const [company, setCompany]   = useState('');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) { setError('Passwords do not match.'); return; }
    if (password.length < 8)  { setError('Password must be at least 8 characters.'); return; }
    setLoading(true);
    try {
      await createCompany(company.trim(), email.trim(), password);
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <button type="button" onClick={onBack} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-500)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, marginBottom: 20, padding: 0 }}>
        <ArrowLeft size={14} /> Back
      </button>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4, color: 'var(--gray-900)' }}>Create Company Account</h2>
      <p style={{ fontSize: 13, color: 'var(--gray-500)', marginBottom: 24 }}>Set up your company and admin access</p>

      <ErrorBanner msg={error} />

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
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const [resetSent, setResetSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signInAsAdmin(email.trim(), password);
    } catch (err) {
      setError(err.message || 'Sign-in failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!email) { setError('Enter your email address first.'); return; }
    try {
      await resetPassword(email.trim());
      setResetSent(true);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Card>
      <button type="button" onClick={onBack} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-500)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, marginBottom: 20, padding: 0 }}>
        <ArrowLeft size={14} /> Back
      </button>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4, color: 'var(--gray-900)' }}>Admin Sign In</h2>
      <p style={{ fontSize: 13, color: 'var(--gray-500)', marginBottom: 24 }}>Sign in to manage your company</p>

      <ErrorBanner msg={error} />
      {resetSent && (
        <div className="alert alert-success mb-4" style={{ fontSize: 13 }}>
          Password reset email sent — check your inbox.
        </div>
      )}

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

// ── Employee Sign In ──────────────────────────────────────────────────────────
function EmployeeSignInForm({ onBack }) {
  const { signInAsEmployee } = useAuth();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signInAsEmployee(email.trim(), password);
    } catch (err) {
      setError(err.message || 'Sign-in failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <button type="button" onClick={onBack} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-500)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, marginBottom: 20, padding: 0 }}>
        <ArrowLeft size={14} /> Back
      </button>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4, color: 'var(--gray-900)' }}>Employee Sign In</h2>
      <p style={{ fontSize: 13, color: 'var(--gray-500)', marginBottom: 24 }}>Access your payslips, leave &amp; attendance</p>

      <ErrorBanner msg={error} />

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

        <div className="form-group" style={{ marginBottom: 24 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Password</label>
          <PasswordInput value={password} onChange={e => setPassword(e.target.value)} />
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}
          style={{ width: '100%', justifyContent: 'center' }}>
          {loading ? <><Loader size={15} style={{ animation: 'spin 1s linear infinite' }} /> Signing in…</> : 'Sign in as Employee'}
        </button>
      </form>

      <p style={{ fontSize: 12, color: 'var(--gray-400)', textAlign: 'center', marginTop: 16 }}>
        First time? Ask your HR admin to add your work email, then create an account using that email address.
      </p>
    </Card>
  );
}

// ── Root export ───────────────────────────────────────────────────────────────
export default function AuthPage() {
  const [view, setView] = useState('landing');

  const renderView = () => {
    switch (view) {
      case 'create':   return <CreateCompanyForm   onBack={() => setView('landing')} />;
      case 'admin':    return <AdminSignInForm      onBack={() => setView('landing')} />;
      case 'employee': return <EmployeeSignInForm   onBack={() => setView('landing')} />;
      default:         return <Landing onSelect={setView} />;
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      background: BG, padding: '24px',
    }}>
      {/* Brand header */}
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <div style={{
          width: 52, height: 52, borderRadius: 13,
          background: 'linear-gradient(135deg, #1a56db, #1e429f)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 12px',
          boxShadow: '0 8px 24px rgba(26,86,219,0.4)',
        }}>
          <FileText size={26} color="white" />
        </div>
        <h1 style={{ color: 'white', fontSize: 22, fontWeight: 700, margin: 0 }}>Workloop</h1>
        <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 12, marginTop: 4 }}>UAE Payroll &amp; HRMS</p>
      </div>

      {renderView()}

      <p style={{ color: 'rgba(255,255,255,0.25)', fontSize: 11, marginTop: 20 }}>
        Your data is encrypted and stored securely.
      </p>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .alert-success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; border-radius: 8px; padding: 10px 14px; display: flex; align-items: flex-start; gap: 8px; }
        .alert-danger  { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; border-radius: 8px; padding: 10px 14px; display: flex; align-items: flex-start; gap: 8px; }
        .mb-4 { margin-bottom: 16px; }
      `}</style>
    </div>
  );
}
