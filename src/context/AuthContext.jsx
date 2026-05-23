import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { supabase } from '../lib/supabase';
import { getProfile, linkEmployeeAccount } from '../utils/profileStorage';

const AuthContext = createContext(null);

// ── Friendly error messages ───────────────────────────────────────────────────
// Supabase returns terse/technical strings; map them to user-readable ones.
function mapAuthError(err) {
  const msg = err?.message ?? String(err);
  if (/invalid login credentials/i.test(msg))
    return 'Incorrect email or password. Please try again.';
  if (/email not confirmed/i.test(msg))
    return 'Please confirm your email address before signing in. Check your inbox.';
  if (/too many requests/i.test(msg))
    return 'Too many attempts. Please wait a few minutes and try again.';
  if (/user already registered/i.test(msg))
    return 'This email is already registered. Please sign in instead.';
  if (/password.*characters/i.test(msg))
    return 'Password must be at least 8 characters.';
  return msg || 'Something went wrong. Please try again.';
}

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [profile, setProfile] = useState(null);
  // loading is ONLY for the initial page-load session restore.
  // Individual auth actions use their own local loading state in the form components.
  const [loading, setLoading] = useState(true);

  // Prevent stale async resolutions if auth state changes quickly
  const resolvingFor = useRef(null);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      const newUser = session?.user ?? null;
      resolvingFor.current = newUser?.id ?? null;

      if (!newUser) {
        setUser(null);
        setProfile(null);
        setLoading(false);
        return;
      }

      // On page reload / token refresh: restore profile from DB.
      // SIGNED_IN is handled by the explicit sign-in functions below,
      // which call setUser/setProfile directly — skip auto-read to avoid races.
      if (event === 'INITIAL_SESSION' || event === 'TOKEN_REFRESHED') {
        setUser(newUser);
        try {
          const prof = await getProfile();
          if (resolvingFor.current === newUser.id) setProfile(prof);
        } catch {
          if (resolvingFor.current === newUser.id) setProfile(null);
        }
        if (resolvingFor.current === newUser.id) setLoading(false);
      }
    });

    return () => subscription.unsubscribe();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Create a new company (first-time admin registration) ─────────────────
  // No global setLoading — the form component controls its own button spinner.
  // Errors thrown here are caught by the form's try/catch and shown in the UI.
  const createCompany = async (companyName, email, password) => {
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) throw new Error(mapAuthError(error));

    const u = data.user;

    // Supabase silently returns a user with empty identities when the email is
    // already registered — detect this and give a clear message.
    if (!u || (Array.isArray(u.identities) && u.identities.length === 0)) {
      throw new Error(
        'This email is already registered. Sign in as Admin, or use a different email to create a new company.'
      );
    }

    const { error: coErr } = await supabase
      .from('companies')
      .insert({ user_id: u.id, name: companyName });
    if (coErr) throw new Error(mapAuthError(coErr));

    const { error: profErr } = await supabase.from('user_profiles').upsert(
      { user_id: u.id, role: 'admin', company_user_id: u.id, employee_id: null },
      { onConflict: 'user_id' }
    );
    if (profErr) throw new Error(mapAuthError(profErr));

    // React batches both of these together — App renders portal in one pass.
    setUser(u);
    setProfile({ role: 'admin', companyUserId: u.id, employeeId: null });
  };

  // ── Admin sign-in ─────────────────────────────────────────────────────────
  const signInAsAdmin = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw new Error(mapAuthError(error));

    const u = data.user;

    // Verify this user owns a company (RLS: companies.user_id = auth.uid())
    const { data: company } = await supabase
      .from('companies').select('id').limit(1).maybeSingle();

    if (!company) {
      await supabase.auth.signOut();
      throw new Error(
        'No company account found for this email. Use "Create Company" to register, or try signing in as Employee if you are a staff member.'
      );
    }

    await supabase.from('user_profiles').upsert(
      { user_id: u.id, role: 'admin', company_user_id: u.id, employee_id: null },
      { onConflict: 'user_id' }
    );

    setUser(u);
    setProfile({ role: 'admin', companyUserId: u.id, employeeId: null });
  };

  // ── Employee sign-in ──────────────────────────────────────────────────────
  const signInAsEmployee = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw new Error(mapAuthError(error));

    const u = data.user;

    // If a valid employee profile already exists (idempotent re-login), use it.
    const existingProf = await getProfile();
    if (existingProf?.role === 'employee') {
      setUser(u);
      setProfile(existingProf);
      return;
    }

    // First sign-in after admin added them — run the link RPC.
    const linked = await linkEmployeeAccount();
    if (!linked?.success) {
      await supabase.auth.signOut();
      // If the user has an admin account, steer them to the right portal.
      const { data: company } = await supabase
        .from('companies').select('id').limit(1).maybeSingle().catch(() => ({ data: null }));
      if (company) {
        throw new Error(
          'This email belongs to an Admin account. Please go back and use "Sign in as Admin" instead.'
        );
      }
      throw new Error(
        'Your work email has not been added to any company yet. Ask your HR admin to add your email to the employee list first.'
      );
    }

    await supabase.from('user_profiles').upsert(
      {
        user_id:         u.id,
        role:            'employee',
        company_user_id: linked.company_user_id,
        employee_id:     linked.employee_id,
      },
      { onConflict: 'user_id' }
    );

    setUser(u);
    setProfile({ role: 'employee', companyUserId: linked.company_user_id, employeeId: linked.employee_id });
  };

  // ── Employee sign-up (first time, after admin added their work email) ──────
  // Does NOT call setLoading or setUser/setProfile — the form component shows
  // a success banner and switches to sign-in mode after this resolves.
  const signUpAsEmployee = async (email, password) => {
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) throw new Error(mapAuthError(error));

    const u = data.user;

    // Supabase silently returns a user with empty identities for existing emails.
    if (!u || (Array.isArray(u.identities) && u.identities.length === 0)) {
      throw new Error(
        'This email is already registered. Switch to "Sign in" below to log in to your account.'
      );
    }

    // Link the auth user to their employee record.
    const linked = await linkEmployeeAccount();
    if (!linked?.success) {
      await supabase.auth.signOut();
      throw new Error(
        'Your email has not been added to any company. Ask your HR admin to add your work email first, then try again.'
      );
    }

    await supabase.from('user_profiles').upsert(
      {
        user_id:         u.id,
        role:            'employee',
        company_user_id: linked.company_user_id,
        employee_id:     linked.employee_id,
      },
      { onConflict: 'user_id' }
    );

    // Account created and linked. Do NOT auto-login — let AuthPage show a
    // success banner and let the employee sign in manually.
    // (Profile row is already written; sign-in will find it without re-linking.)
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  };

  const resetPassword = async (email) => {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin,
    });
    if (error) throw new Error(mapAuthError(error));
  };

  return (
    <AuthContext.Provider value={{
      user,
      profile,
      loading,
      createCompany,
      signInAsAdmin,
      signInAsEmployee,
      signUpAsEmployee,
      signOut,
      resetPassword,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
