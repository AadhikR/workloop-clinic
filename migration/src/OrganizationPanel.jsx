import { useEffect, useState } from 'react'

import BranchChooser from './BranchChooser.jsx'
import { CompanyProvider } from './CompanyContext.jsx'
import { useCompanyContext } from './companyContextState.js'
import { readCurrentAccount } from './sampleApi.js'
import OrganizationSettings from './OrganizationSettings.jsx'

function OrganizationSummary({ authentication }) {
  const organization = useCompanyContext()
  if (organization.status === 'loading') return <p>Loading organization...</p>
  if (organization.status === 'unavailable') return <p>Organization details are unavailable.</p>
  if (organization.status === 'cancelled') return null
  if (organization.status === 'choose-branch') return <BranchChooser />

  return (
    <div className="organization-summary">
      <h2>{organization.company?.name ?? organization.employer?.companyName}</h2>
      <p>{organization.selectedBranch.name}</p>
      {organization.company && (
        <>
          <button type="button" className="secondary" onClick={organization.clearBranch}>
            Change branch
          </button>
          <OrganizationSettings authentication={authentication} />
        </>
      )}
    </div>
  )
}

export default function OrganizationPanel({ authentication }) {
  const [account, setAccount] = useState(undefined)

  useEffect(() => {
    const controller = new AbortController()
    readCurrentAccount(authentication, { signal: controller.signal })
      .then(setAccount)
      .catch(() => {
        if (!controller.signal.aborted) setAccount(null)
      })
    return () => controller.abort()
  }, [authentication])

  if (account === undefined) return <p>Loading organization...</p>
  if (account === null) return <p>Organization details are unavailable.</p>
  return (
    <CompanyProvider account={account} authentication={authentication}>
      <OrganizationSummary authentication={authentication} />
    </CompanyProvider>
  )
}
