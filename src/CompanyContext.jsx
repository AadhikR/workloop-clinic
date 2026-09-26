import { useCallback, useEffect, useMemo, useState } from 'react'

import { CompanyContext } from './companyContextState.js'
import { HttpClientError } from './http.js'
import {
  createBranchSelection,
  readAllBranches,
  readCompany,
  readEmployer,
} from './organizationApi.js'

function safeStatus(error, signal) {
  if (signal.aborted || error instanceof HttpClientError && error.kind === 'cancelled') {
    return 'cancelled'
  }
  return 'unavailable'
}

export function CompanyProvider({ account, authentication, children }) {
  const selection = useMemo(
    () => createBranchSelection({ sessionStorage: globalThis.sessionStorage }),
    [],
  )
  const [state, setState] = useState({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()

    const load = async () => {
      if (account.role === 'admin') {
        const [company, branches] = await Promise.all([
          readCompany(authentication, { signal: controller.signal }),
          readAllBranches(authentication, { signal: controller.signal }),
        ])
        if (controller.signal.aborted) return
        const selectedBranch = selection.validate(branches)
        setState({
          status: selectedBranch === null ? 'choose-branch' : 'ready',
          company,
          branches,
          selectedBranch,
        })
        return
      }

      selection.clear()
      const [employer, branches] = await Promise.all([
        readEmployer(authentication, { signal: controller.signal }),
        readAllBranches(authentication, { signal: controller.signal }),
      ])
      if (controller.signal.aborted) return
      if (branches.length !== 1) {
        throw new Error('Invalid staff branch response')
      }
      setState({
        status: 'ready',
        employer,
        branches,
        selectedBranch: branches[0],
      })
    }

    load().catch((error) => {
      if (!controller.signal.aborted) setState({ status: safeStatus(error, controller.signal) })
    })
    return () => controller.abort()
  }, [account, authentication, selection])

  const chooseBranch = (branchId) => {
    if (state.status !== 'choose-branch' && state.status !== 'ready') return
    const selectedBranch = selection.select(branchId, state.branches)
    setState(selectedBranch === null
      ? { ...state, status: 'choose-branch', selectedBranch: null }
      : { ...state, status: 'ready', selectedBranch })
  }

  const clearBranch = () => {
    if (account.role !== 'admin' || !Array.isArray(state.branches)) return
    selection.clear()
    setState({ ...state, status: 'choose-branch', selectedBranch: null })
  }

  const replaceCompany = (company) => {
    if (account.role !== 'admin') return
    setState((current) => ({ ...current, company }))
  }

  const replaceBranch = (branch) => {
    if (account.role !== 'admin') return
    setState((current) => ({
      ...current,
      branches: current.branches.map((item) => item.id === branch.id ? branch : item),
      selectedBranch: current.selectedBranch?.id === branch.id ? branch : current.selectedBranch,
    }))
  }

  const addBranch = (branch) => {
    if (account.role !== 'admin') return
    selection.select(branch.id, [branch])
    setState((current) => ({
      ...current,
      status: 'ready',
      branches: [...current.branches, branch],
      selectedBranch: branch,
    }))
  }

  const removeBranch = (branchId) => {
    if (account.role !== 'admin') return
    selection.clear()
    setState((current) => ({
      ...current,
      status: 'choose-branch',
      branches: current.branches.filter((branch) => branch.id !== branchId),
      selectedBranch: null,
    }))
  }

  const refresh = useCallback(async (preferredBranchId = null) => {
    if (account.role !== 'admin') return
    const [company, branches] = await Promise.all([
      readCompany(authentication),
      readAllBranches(authentication),
    ])
    const selectedBranch = preferredBranchId === null
      ? selection.validate(branches)
      : selection.select(preferredBranchId, branches)
    setState({
      status: selectedBranch === null ? 'choose-branch' : 'ready',
      company,
      branches,
      selectedBranch,
    })
  }, [account.role, authentication, selection])

  return (
    <CompanyContext.Provider value={{
      ...state,
      chooseBranch,
      clearBranch,
      replaceCompany,
      replaceBranch,
      addBranch,
      removeBranch,
      refresh,
    }}>
      {children}
    </CompanyContext.Provider>
  )
}
