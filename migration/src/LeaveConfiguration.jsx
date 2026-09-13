import { useEffect, useState } from 'react'

import {
  createLeaveType,
  createPublicHoliday,
  deletePublicHoliday,
  readLeaveConfiguration,
  seedLeaveTypes,
  seedPublicHolidays,
  updateLeaveSettings,
  updateLeaveType,
  updatePublicHoliday,
} from './leaveConfigurationApi.js'

const emptySettings = {
  leaveYearType: 'calendar',
  weekendDefinition: 'fri-sat',
  carryForwardEnabled: true,
  carryForwardMaxDays: 15,
  approvalChain: '1-level',
  ramadanActive: false,
  ramadanStart: null,
  ramadanEnd: null,
}

const emptyType = {
  id: null,
  code: '',
  name: '',
  color: '#6b7280',
  isPaid: true,
  requiresApproval: true,
  requiresAttachment: false,
  requiresReason: false,
  minNoticeDays: 0,
  annualEntitlementDays: '0.00',
  dayCountType: 'calendar',
}

const emptyHoliday = { id: null, date: '', name: '', type: 'federal' }

function messageFor(error, fallback) {
  if (error?.code === 'state_conflict') return 'The configuration changed. Refresh and try again.'
  if (error?.code === 'branch_conflict') return 'The branch state prevents that change.'
  if (error?.code === 'operation_not_permitted') return 'That configuration cannot be changed.'
  return fallback
}

export default function LeaveConfiguration({ authentication, branchId }) {
  const [state, setState] = useState({ status: 'loading', data: null, message: '' })
  const [settingsForm, setSettingsForm] = useState(emptySettings)
  const [typeForm, setTypeForm] = useState(emptyType)
  const [holidayForm, setHolidayForm] = useState(emptyHoliday)

  const applyData = (data, message = '') => {
    setState({ status: 'ready', data, message })
    setSettingsForm(data.settings ? {
      leaveYearType: data.settings.leaveYearType,
      weekendDefinition: data.settings.weekendDefinition,
      carryForwardEnabled: data.settings.carryForwardEnabled,
      carryForwardMaxDays: data.settings.carryForwardMaxDays,
      approvalChain: data.settings.approvalChain,
      ramadanActive: data.settings.ramadanActive,
      ramadanStart: data.settings.ramadanStart,
      ramadanEnd: data.settings.ramadanEnd,
    } : emptySettings)
  }

  const refresh = async (message = '') => {
    const data = await readLeaveConfiguration(authentication, branchId)
    applyData(data, message)
  }

  useEffect(() => {
    const controller = new AbortController()
    readLeaveConfiguration(authentication, branchId, { signal: controller.signal })
      .then((data) => applyData(data))
      .catch(() => {
        if (!controller.signal.aborted) {
          setState({ status: 'error', data: null, message: 'Leave configuration is unavailable.' })
        }
      })
    return () => controller.abort()
  }, [authentication, branchId])

  const saveSettings = async (event) => {
    event.preventDefault()
    try {
      const settings = await updateLeaveSettings(authentication, branchId, {
        ...settingsForm,
        ...(state.data.settings ? { expectedUpdatedAt: state.data.settings.updatedAt } : {}),
      })
      applyData({ ...state.data, settings }, 'Leave settings saved.')
    } catch (error) {
      setState((current) => ({
        ...current,
        message: messageFor(error, 'Leave settings could not be saved.'),
      }))
    }
  }

  const seedTypes = async () => {
    try {
      await seedLeaveTypes(authentication, branchId)
      await refresh('Default leave types are ready.')
    } catch (error) {
      setState((current) => ({
        ...current,
        message: messageFor(error, 'Leave types could not be seeded.'),
      }))
    }
  }

  const saveType = async (event) => {
    event.preventDefault()
    try {
      const values = {
        code: typeForm.code,
        name: typeForm.name,
        color: typeForm.color,
        isPaid: typeForm.isPaid,
        requiresApproval: typeForm.requiresApproval,
        requiresAttachment: typeForm.requiresAttachment,
        requiresReason: typeForm.requiresReason,
        minNoticeDays: typeForm.minNoticeDays,
        annualEntitlementDays: typeForm.annualEntitlementDays,
        dayCountType: typeForm.dayCountType,
      }
      if (typeForm.id) {
        const current = state.data.types.find((item) => item.id === typeForm.id)
        await updateLeaveType(authentication, branchId, typeForm.id, {
          expectedUpdatedAt: current.updatedAt,
          ...values,
        })
      } else {
        await createLeaveType(authentication, branchId, values)
      }
      setTypeForm(emptyType)
      await refresh(typeForm.id ? 'Leave type updated.' : 'Leave type created.')
    } catch (error) {
      setState((current) => ({
        ...current,
        message: messageFor(error, 'Leave type could not be created.'),
      }))
    }
  }

  const toggleType = async (type) => {
    try {
      await updateLeaveType(authentication, branchId, type.id, {
        expectedUpdatedAt: type.updatedAt,
        isActive: !type.isActive,
      })
      await refresh(type.isActive ? 'Leave type deactivated.' : 'Leave type reactivated.')
    } catch (error) {
      setState((current) => ({
        ...current,
        message: messageFor(error, 'Leave type could not be changed.'),
      }))
    }
  }

  const saveHoliday = async (event) => {
    event.preventDefault()
    try {
      if (holidayForm.id) {
        const current = state.data.holidays.find((item) => item.id === holidayForm.id)
        await updatePublicHoliday(authentication, branchId, current, {
          date: holidayForm.date,
          name: holidayForm.name,
          type: holidayForm.type,
        })
      } else {
        await createPublicHoliday(authentication, branchId, {
          date: holidayForm.date,
          name: holidayForm.name,
          type: holidayForm.type,
        })
      }
      setHolidayForm(emptyHoliday)
      await refresh(holidayForm.id ? 'Holiday updated.' : 'Holiday created.')
    } catch (error) {
      setState((current) => ({
        ...current,
        message: messageFor(error, 'Holiday could not be saved.'),
      }))
    }
  }

  const seedHoliday = async () => {
    try {
      const year = Number(holidayForm.date.slice(0, 4))
      await seedPublicHolidays(authentication, branchId, year, [{
        date: holidayForm.date,
        name: holidayForm.name,
        type: holidayForm.type,
      }])
      setHolidayForm(emptyHoliday)
      await refresh('Holiday year seeded without duplicates.')
    } catch (error) {
      setState((current) => ({
        ...current,
        message: messageFor(error, 'Holiday year could not be seeded.'),
      }))
    }
  }

  const removeHoliday = async (holiday) => {
    try {
      await deletePublicHoliday(authentication, branchId, holiday)
      await refresh('Holiday removed.')
    } catch (error) {
      setState((current) => ({
        ...current,
        message: messageFor(error, 'Holiday could not be removed.'),
      }))
    }
  }

  if (state.status === 'loading') {
    return <section aria-label="Leave configuration"><p>Loading leave configuration...</p></section>
  }
  if (state.status === 'error') {
    return <section aria-label="Leave configuration"><p>{state.message}</p></section>
  }

  return (
    <section className="leave-configuration" aria-labelledby="leave-configuration-title">
      <h2 id="leave-configuration-title">Leave configuration</h2>
      {state.message && <p role="status">{state.message}</p>}

      <form onSubmit={saveSettings}>
        <h3>Branch settings</h3>
        <label>
          Leave year
          <select value={settingsForm.leaveYearType} disabled>
            <option value="calendar">Calendar year</option>
          </select>
        </label>
        <label>
          Weekend
          <select
            value={settingsForm.weekendDefinition}
            onChange={(event) => setSettingsForm({
              ...settingsForm, weekendDefinition: event.target.value,
            })}
          >
            <option value="fri-sat">Friday and Saturday</option>
            <option value="sat-sun">Saturday and Sunday</option>
          </select>
        </label>
        <label>
          Approval chain
          <select
            value={settingsForm.approvalChain}
            onChange={(event) => setSettingsForm({
              ...settingsForm, approvalChain: event.target.value,
            })}
          >
            <option value="1-level">One level</option>
            <option value="2-level">Two levels</option>
          </select>
        </label>
        <label>
          Carry-forward limit
          <input
            type="number"
            min="0"
            max="366"
            value={settingsForm.carryForwardMaxDays}
            onChange={(event) => setSettingsForm({
              ...settingsForm, carryForwardMaxDays: Number(event.target.value),
            })}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={settingsForm.carryForwardEnabled}
            onChange={(event) => setSettingsForm({
              ...settingsForm, carryForwardEnabled: event.target.checked,
            })}
          />
          Allow carry-forward
        </label>
        <label>
          <input
            type="checkbox"
            checked={settingsForm.ramadanActive}
            onChange={(event) => setSettingsForm({
              ...settingsForm, ramadanActive: event.target.checked,
            })}
          />
          Ramadan schedule active
        </label>
        <label>
          Ramadan start
          <input
            type="date"
            value={settingsForm.ramadanStart ?? ''}
            onChange={(event) => setSettingsForm({
              ...settingsForm, ramadanStart: event.target.value || null,
            })}
          />
        </label>
        <label>
          Ramadan end
          <input
            type="date"
            value={settingsForm.ramadanEnd ?? ''}
            onChange={(event) => setSettingsForm({
              ...settingsForm, ramadanEnd: event.target.value || null,
            })}
          />
        </label>
        <button type="submit">Save settings</button>
      </form>

      <div>
        <h3>Leave types</h3>
        <button type="button" className="secondary" onClick={seedTypes}>
          Seed default leave types
        </button>
        <ul>
          {state.data.types.map((type) => (
            <li key={type.id}>
              {type.name} ({type.code}), {type.annualEntitlementDays} days
              <button type="button" className="secondary" onClick={() => toggleType(type)}>
                {type.isActive ? 'Deactivate' : 'Reactivate'}
              </button>
              <button type="button" className="secondary" onClick={() => setTypeForm(type)}>
                Edit
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={saveType}>
          <h4>{typeForm.id ? 'Edit leave type' : 'Create leave type'}</h4>
          <label>Code<input value={typeForm.code} onChange={(event) => setTypeForm({ ...typeForm, code: event.target.value })} required /></label>
          <label>Name<input value={typeForm.name} onChange={(event) => setTypeForm({ ...typeForm, name: event.target.value })} required /></label>
          <label>Color<input value={typeForm.color} onChange={(event) => setTypeForm({ ...typeForm, color: event.target.value })} required /></label>
          <label>Days<input value={typeForm.annualEntitlementDays} onChange={(event) => setTypeForm({ ...typeForm, annualEntitlementDays: event.target.value })} pattern="(?:0|[1-9][0-9]{0,3})\.[0-9]{2}" required /></label>
          <label>Minimum notice days<input type="number" min="0" max="366" value={typeForm.minNoticeDays} onChange={(event) => setTypeForm({ ...typeForm, minNoticeDays: Number(event.target.value) })} required /></label>
          <label>Count<select value={typeForm.dayCountType} onChange={(event) => setTypeForm({ ...typeForm, dayCountType: event.target.value })}><option value="calendar">Calendar days</option><option value="working">Working days</option></select></label>
          <label><input type="checkbox" checked={typeForm.isPaid} onChange={(event) => setTypeForm({ ...typeForm, isPaid: event.target.checked })} />Paid</label>
          <label><input type="checkbox" checked={typeForm.requiresApproval} onChange={(event) => setTypeForm({ ...typeForm, requiresApproval: event.target.checked })} />Requires approval</label>
          <label><input type="checkbox" checked={typeForm.requiresAttachment} onChange={(event) => setTypeForm({ ...typeForm, requiresAttachment: event.target.checked })} />Requires attachment</label>
          <label><input type="checkbox" checked={typeForm.requiresReason} onChange={(event) => setTypeForm({ ...typeForm, requiresReason: event.target.checked })} />Requires reason</label>
          <button type="submit">{typeForm.id ? 'Update leave type' : 'Create leave type'}</button>
          {typeForm.id && <button type="button" className="secondary" onClick={() => setTypeForm(emptyType)}>Cancel edit</button>}
        </form>
      </div>

      <div>
        <h3>Public holidays</h3>
        <ul>
          {state.data.holidays.map((holiday) => (
            <li key={holiday.id}>
              {holiday.date}: {holiday.name}
              <button type="button" className="secondary" onClick={() => setHolidayForm(holiday)}>
                Edit
              </button>
              <button type="button" className="secondary" onClick={() => removeHoliday(holiday)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={saveHoliday}>
          <h4>{holidayForm.id ? 'Edit holiday' : 'Add or seed holiday'}</h4>
          <label>Date<input type="date" value={holidayForm.date} onChange={(event) => setHolidayForm({ ...holidayForm, date: event.target.value })} required /></label>
          <label>Name<input value={holidayForm.name} onChange={(event) => setHolidayForm({ ...holidayForm, name: event.target.value })} required /></label>
          <label>Type<input value={holidayForm.type} onChange={(event) => setHolidayForm({ ...holidayForm, type: event.target.value })} required /></label>
          <button type="submit">{holidayForm.id ? 'Update holiday' : 'Add holiday'}</button>
          {!holidayForm.id && <button type="button" className="secondary" onClick={seedHoliday}>Seed named year</button>}
        </form>
      </div>
    </section>
  )
}
