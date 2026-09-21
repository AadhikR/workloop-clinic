import { useEffect, useState } from 'react'

import { readPersonalAttendance, readPersonalAttendanceHistory } from './attendanceCalculationApi.js'

export default function PersonalAttendance({ authentication }) {
  const [attendance, setAttendance] = useState(null)
  const [history, setHistory] = useState([])
  const [message, setMessage] = useState('')
  useEffect(() => {
    Promise.all([readPersonalAttendance(authentication), readPersonalAttendanceHistory(authentication, { limit: 31 })])
      .then(([today, previous]) => { setAttendance(today); setHistory(previous.data) })
      .catch(() => setMessage('Personal attendance is unavailable.'))
  }, [authentication])
  if (message) return <p role="status">{message}</p>
  if (attendance === null) return <p>Loading personal attendance...</p>
  return <section aria-labelledby="personal-attendance-title"><h2 id="personal-attendance-title">My attendance</h2>{attendance.record ? <p>Today: {attendance.record.status} — {attendance.record.totalHours} hours</p> : <><p>No calculated attendance is available for today.</p><ul>{attendance.rawEvents.map((item) => <li key={item.id}>{item.eventTime} — {item.eventType}</li>)}</ul></>}<h3>History</h3><ul>{history.map((item) => <li key={item.id}>{item.date} — {item.status} — {item.totalHours} hours</li>)}</ul></section>
}
