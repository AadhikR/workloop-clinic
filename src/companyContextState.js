import { createContext, useContext } from 'react'

export const CompanyContext = createContext(null)

export function useCompanyContext() {
  const value = useContext(CompanyContext)
  if (value === null) throw new Error('Company context is unavailable')
  return value
}
