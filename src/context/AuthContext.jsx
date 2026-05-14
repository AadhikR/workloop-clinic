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
async function resolveProfile(user) {
  // 1 — Always try employee link first.
  //     The RPC upserts user_profiles with the correct role, so this also
  //     repairs any stale admin profile that was created on a previous attempt.
  const linked = await linkEmployeeAccount();
  if (linked?.success) {
    return getProfile();
  }

  // 2 — Not an employee — check for an existing admin profile.
  const existing = await getProfile();
  if (existing) return existing;

  // 3 — New admin: create the profile row (no company set up yet is fine).
  return createAdminProfile(user);
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

    try {
      const prof = await resolveProfile(newUser);
      if (resolvingFor.current !== newUser.id) return;
      // Hard fallback: authenticated users are always at least admin
      setProfile(prof ?? { role: 'admin', companyUserId: newUser.id, employeeId: null });
    } catch (err) {
      console.error('resolveProfile failed:', err);
      if (resolvingFor.current !== newUser.id) return;
      setProfile({ role: 'admin', companyUserId: newUser.id, employeeId: null });
    } finally {
      if (resolvingFor.current === newUser.id) setLoading(false);
    }
  }

  useEffect(() => {
    // onAuthStateChange fires INITIAL_SESSION immediately — no need for a
    // separate getSession() call, which would trigger a second concurrent resolution.
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
