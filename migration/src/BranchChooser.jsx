import { useCompanyContext } from './companyContextState.js'

export default function BranchChooser() {
  const organization = useCompanyContext()
  if (organization.status !== 'choose-branch') return null

  return (
    <section className="branch-chooser" aria-labelledby="branch-chooser-title">
      <h2 id="branch-chooser-title">Choose a branch</h2>
      <p>Select the branch you want to work with in this tab.</p>
      <div className="branch-options">
        {organization.branches.map((branch) => (
          <button
            key={branch.id}
            type="button"
            className="secondary"
            onClick={() => organization.chooseBranch(branch.id)}
          >
            {branch.name || 'Unnamed branch'}
          </button>
        ))}
      </div>
    </section>
  )
}
