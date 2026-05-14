import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { supabase } from '../lib/supabase';
import { getProfile, linkEmployeeAccount } from '../utils/profileStorage';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [profile, setProfile] = useState(null);
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
      // which set profile directly — skip auto-read to avoid races.
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
  const createCompany = async (companyName, email, password) => {
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signUp({ email, password });
      if (error) throw error;

      const u = data.user;
      if (!u) throw new Error('Sign-up succeeded but no user was returned. Check your email to confirm, then sign in.');

      const { error: coErr } = await supabase
        .from('companies')
        .insert({ user_id: u.id, name: companyName });
      if (coErr) throw coErr;

      await supabase.from('user_profiles').upsert(
        { user_id: u.id, role: 'admin', company_user_id: u.id, employee_id: null },
        { onConflict: 'user_id' }
      );

      setUser(u);
      setProfile({ role: 'admin', companyUserId: u.id, employeeId: null });
    } finally {
      setLoading(false);
    }
  };

  // ── Admin sign-in ─────────────────────────────────────────────────────────
  const signInAsAdmin = async (email, password) => {
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;

      const u = data.user;

      // Verify this user owns a company (RLS: companies.user_id = auth.uid())
      const { data: company } = await supabase
        .from('companies').select('id').limit(1).maybeSingle();

      if (!company) {
        await supabase.auth.signOut();
        throw new Error('No company account found for this email. Use "Create Company" to register, or sign in as Employee.');
      }

      // Ensure profile row is correct
      await supabase.from('user_profiles').upsert(
        { user_id: u.id, role: 'admin', company_user_id: u.id, employee_id: null },
        { onConflict: 'user_id' }
      );

      setUser(u);
      setProfile({ role: 'admin', companyUserId: u.id, employeeId: null });
    } finally {
      setLoading(false);
    }
  };

  // ── Employee sign-in ──────────────────────────────────────────────────────
  const signInAsEmployee = async (email, password) => {
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;

      const linked = await linkEmployeeAccount();
      if (!linked?.success) {
        await supabase.auth.signOut();
        throw new Error('No employee record found for this email. Contact your HR admin to add your work email.');
      }

      const prof = await getProfile();
      setUser(data.user);
      setProfile(prof);
    } finally {
      setLoading(false);
    }
  };

  // ── Employee sign-up (first time, after admin added their work email) ──────
  const signUpAsEmployee = async (email, password) => {
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signUp({ email, password });
      if (error) throw error;

      const u = data.user;
      if (!u) throw new Error('Account created — check your email to confirm, then sign in.');

      const linked = await linkEmployeeAccount();
      if (!linked?.success) {
        await supabase.auth.signOut();
        throw new Error('Your email has not been added to any company. Ask your HR admin to add your work email first.');
      }

      const prof = await getProfile();
      setUser(u);
      setProfile(prof);
    } finally {
      setLoading(false);
    }
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  };

  const resetPassword = async (email) => {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin,
    });
    if (error) throw error;
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
