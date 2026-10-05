import { useEffect, useState } from 'react'

export default function DeferredModule({ load, ...props }) {
  const [state, setState] = useState(null)
  useEffect(() => {
    let active = true
    load().then((module) => { if (active) setState({ load, component: module.default }) }).catch(() => { if (active) setState({ load, error: true }) })
    return () => { active = false }
  }, [load])
  if (state?.load !== load) return <p role="status">Loading work area...</p>
  if (state.error) return <div role="alert"><p>This work area could not be loaded.</p><button type="button" onClick={() => location.reload()}>Reload page</button></div>
  const View = state.component
  return <View {...props} />
}
