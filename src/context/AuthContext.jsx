import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { supabase } from '../lib/supabase';
import { getProfile, createAdminProfile, linkEmployeeAccount } from '../utils/profileStorage';

const AuthContext = createContext(null);

/**
 * Determine and return the profile for a signed-in user.
 *
 * Resolution order (stops at the first match):
 *   1. Existing user_profiles row → use it.
 *   2. User owns a companies row  → create admin profile.
 *   3. link_employee_account() matches work_email → employee profile created by RPC.
 *   4. Fallback                   → create admin profile (brand-new HR user, no company yet).
 */
async function resolveProfile() {
  // 1 — existing profile
  const existing = await getProfile();
  if (existing) return existing;

  // 2 — does this user own a company? (RLS: companies.user_id = auth.uid())
  const { data: company } = await supabase
    .from('companies')
    .select('id')
    .limit(1)
    .maybeSingle();

  if (company) {
    return createAdminProfile();
  }

  // 3 — try to link as employee (SECURITY DEFINER RPC matches on work_email)
  const linked = await linkEmployeeAccount();
  if (linked?.success) {
    return getProfile();
  }

  // 4 — new admin who hasn't set up their company yet
  return createAdminProfile();
}

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  // Guard against stale async resolutions if auth state changes quickly
  const resolvingFor = useRef(null);

  async function handleUser(newUser) {
    resolvingFor.current = newUser?.id ?? null;

    if (!newUser) {
      setUser(null);
      setProfile(null);
      setLoading(false);
      return;
    }

    setUser(newUser);
    setLoading(true);

    const prof = await resolveProfile();

    // Discard result if auth changed while we were awaiting
    if (resolvingFor.current !== newUser.id) return;

    setProfile(prof);
    setLoading(false);
  }

  useEffect(() => {
    // Initial session check
    supabase.auth.getSession().then(({ data: { session } }) => {
      handleUser(session?.user ?? null);
    });

    // Subsequent auth state changes (login, logout, token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      handleUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const signUp = async (email, password) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: window.location.origin },
    });
    if (error) throw error;
    return data;
  };

  const signIn = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    return data;
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
      profile,        // { role, companyUserId, employeeId } — null while loading
      loading,
      signUp,
      signIn,
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
