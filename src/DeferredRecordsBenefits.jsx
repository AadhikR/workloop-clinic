import DeferredModule from './DeferredModule.jsx'

const loadRecords = () => import('./RecordsBenefits.jsx')
const loadEmployeeRecords = () => import('./RecordsBenefits.jsx').then((module) => ({ default: module.EmployeeRecordsEditor }))

export default function RecordsBenefits(props) {
  return <DeferredModule load={loadRecords} {...props} />
}

export function EmployeeRecordsEditor(props) {
  return <DeferredModule load={loadEmployeeRecords} {...props} />
}
