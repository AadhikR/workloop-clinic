import { useEffect, useState } from 'react'

import BranchChooser from './BranchChooser.jsx'
import { CompanyProvider } from './CompanyContext.jsx'
import { useCompanyContext } from './companyContextState.js'
import DepartmentManager from './DepartmentManager.jsx'
import EmployeeDirectory from './EmployeeDirectory.jsx'
import Expenses from './Expenses.jsx'
import Advances from './Advances.jsx'
import { readCurrentAccount } from './sampleApi.js'
import OrganizationSettings from './OrganizationSettings.jsx'
import LeaveConfiguration from './LeaveConfiguration.jsx'
import LeaveApprovals from './LeaveApprovals.jsx'
import LeaveOverview from './LeaveOverview.jsx'
import Payroll from './Payroll.jsx'
import Payslips from './Payslips.jsx'
import WpsNafis from './WpsNafis.jsx'

function OrganizationSummary({ account, authentication }) {
  const organization = useCompanyContext()
  if (organization.status === 'loading') return <p>Loading organization...</p>
  if (organization.status === 'unavailable') return <p>Organization details are unavailable.</p>
  if (organization.status === 'cancelled') return null
  if (organization.status === 'choose-branch') return <BranchChooser />

  return (
    <div className="organization-summary">
      <h2>{organization.company?.name ?? organization.employer?.companyName}</h2>
      <p data-selected-branch-name>{organization.selectedBranch.name}</p>
      {organization.company && (
        <>
          <button type="button" className="secondary" onClick={organization.clearBranch}>
            Change branch
          </button>
          <OrganizationSettings authentication={authentication} />
        </>
      )}
      <EmployeeDirectory
        account={account}
        authentication={authentication}
        branchId={organization.selectedBranch.id}
        clearBranch={organization.clearBranch}
      />
      <LeaveOverview
        account={account}
        authentication={authentication}
        branchId={organization.selectedBranch.id}
      />
      <LeaveApprovals
        account={account}
        authentication={authentication}
        branchId={organization.selectedBranch.id}
      />
      <Expenses
        account={account}
        authentication={authentication}
        branchId={organization.selectedBranch.id}
      />
      <Advances
        account={account}
        authentication={authentication}
        branchId={organization.selectedBranch.id}
      />
      <Payroll
        account={account}
        authentication={authentication}
        branchId={organization.selectedBranch.id}
      />
      <Payslips account={account} authentication={authentication} />
      <WpsNafis
        account={account}
        authentication={authentication}
        branchId={organization.selectedBranch.id}
      />
      {account.role === 'admin' && (
        <>
          <LeaveConfiguration authentication={authentication} branchId={organization.selectedBranch.id} />
          <DepartmentManager
            authentication={authentication}
            branchId={organization.selectedBranch.id}
            clearBranch={organization.clearBranch}
          />
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
      <OrganizationSummary account={account} authentication={authentication} />
    </CompanyProvider>
  )
}
