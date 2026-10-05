import DeferredModule from './DeferredModule.jsx'

const loadReviews = () => import('./AppraisalsIncidents.jsx')

export default function AppraisalsIncidents(props) {
  return <DeferredModule load={loadReviews} {...props} />
}
