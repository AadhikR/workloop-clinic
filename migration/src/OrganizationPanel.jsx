import { useEffect, useState } from 'react'

import BranchChooser from './BranchChooser.jsx'
import { CompanyProvider } from './CompanyContext.jsx'
import { useCompanyContext } from './companyContextState.js'
import DepartmentManager from './DepartmentManager.jsx'
import EmployeeDirectory from './EmployeeDirectory.jsx'
import Expenses from './Expenses.jsx'
import Advances from './Advances.jsx'
import AttendanceConfiguration from './AttendanceConfiguration.jsx'
import AttendanceIngestion from './AttendanceIngestion.jsx'
import AttendanceCalculation from './AttendanceCalculation.jsx'
import AttendanceExceptions from './AttendanceExceptions.jsx'
import AttendancePeriods from './AttendancePeriods.jsx'
import RosterDrafts from './RosterDrafts.jsx'
import PersonalAttendance from './PersonalAttendance.jsx'
import PersonalSchedule from './PersonalSchedule.jsx'
import ShiftSwapQueue from './ShiftSwapQueue.jsx'
import { readCurrentAccount } from './sampleApi.js'
import OrganizationSettings from './OrganizationSettings.jsx'
import LeaveConfiguration from './LeaveConfiguration.jsx'
import LeaveApprovals from './LeaveApprovals.jsx'
import LeaveOverview from './LeaveOverview.jsx'
import Payroll from './Payroll.jsx'
import Payslips from './Payslips.jsx'
import WpsNafis from './WpsNafis.jsx'
import RecordsBenefits from './RecordsBenefits.jsx'
import DevelopmentAssets from './DevelopmentAssets.jsx'

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
      <RecordsBenefits
        account={account}
        authentication={authentication}
        branchId={organization.selectedBranch.id}
      />
      <DevelopmentAssets
        account={account}
        authentication={authentication}
        branchId={organization.selectedBranch.id}
      />
      {account.role !== 'admin' && <PersonalAttendance authentication={authentication} />}
      {account.role !== 'admin' && <PersonalSchedule authentication={authentication} />}
      {account.role === 'admin' && (
        <>
          <LeaveConfiguration authentication={authentication} branchId={organization.selectedBranch.id} />
          <AttendanceConfiguration authentication={authentication} branchId={organization.selectedBranch.id} />
          <AttendanceIngestion authentication={authentication} branchId={organization.selectedBranch.id} />
          <AttendanceCalculation authentication={authentication} branchId={organization.selectedBranch.id} />
          <AttendanceExceptions authentication={authentication} branchId={organization.selectedBranch.id} />
          <AttendancePeriods authentication={authentication} branchId={organization.selectedBranch.id} />
          <RosterDrafts authentication={authentication} branchId={organization.selectedBranch.id} />
          <ShiftSwapQueue authentication={authentication} branchId={organization.selectedBranch.id} />
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
