/**
 * CompanyContext.jsx — Multi-company / branch state management (Feature 21)
 *
 * Provides:
 *   companies         — array of all company/branch rows for this admin
 *   activeCompany     — the currently selected company object
 *   activeCompanyId   — UUID of the active branch (filter key for storage queries)
 *   setActiveCompanyId — switch the active branch
 *   createBranch(name, templateCompany) — create a new branch, auto-switch to it
 *   deleteBranch(id)  — delete a branch (guards against active employees)
 *   refreshCompanies  — re-fetch the list from Supabase
 *   loading           — true while the initial fetch is in progress
 *
 * Usage:
 *   const { activeCompanyId, activeCompany, companies, setActiveCompanyId } = useCompany();
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  getCompanies,
  createBranch as storageCreateBranch,
  deleteBranch as storageDeleteBranch,
} from '../utils/storage';

const CompanyContext = createContext(null);

export function CompanyProvider({ children }) {
  const [companies, setCompanies]           = useState([]);
  const [activeCompanyId, setActiveCompanyIdState] = useState(null);
  const [loading, setLoading]               = useState(true);

  const refreshCompanies = useCallback(async () => {
    const list = await getCompanies();
    setCompanies(list);
    // Keep current selection if still valid; fall back to first branch
    setActiveCompanyIdState(prev => {
      if (prev && list.some(c => c.id === prev)) return prev;
      return list[0]?.id ?? null;
    });
    return list;
  }, []);

  // Initial load
  useEffect(() => {
    refreshCompanies().finally(() => setLoading(false));
  }, [refreshCompanies]);

  // Switch the active branch — page components re-query with the new ID
  const setActiveCompanyId = useCallback((id) => {
    setActiveCompanyIdState(id);
  }, []);

  const createBranch = useCallback(async (name, templateCompany) => {
    const newBranch = await storageCreateBranch(name, templateCompany);
    await refreshCompanies();
    setActiveCompanyIdState(newBranch.id);
    return newBranch;
  }, [refreshCompanies]);

  const deleteBranch = useCallback(async (id) => {
    await storageDeleteBranch(id);
    await refreshCompanies();
  }, [refreshCompanies]);

  const activeCompany = companies.find(c => c.id === activeCompanyId) ?? companies[0] ?? null;

  return (
    <CompanyContext.Provider value={{
      companies,
      activeCompany,
      activeCompanyId,
      setActiveCompanyId,
      createBranch,
      deleteBranch,
      refreshCompanies,
      loading,
    }}>
      {children}
    </CompanyContext.Provider>
  );
}

export function useCompany() {
  const ctx = useContext(CompanyContext);
  if (!ctx) throw new Error('useCompany must be used within <CompanyProvider>');
  return ctx;
}
