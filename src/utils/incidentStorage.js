export const INCIDENT_TYPES = Object.freeze([
  'patient_safety', 'medication_error', 'injury', 'needlestick', 'infection',
  'equipment', 'near_miss', 'workplace', 'other',
])
export const INCIDENT_SEVERITY = Object.freeze(['low', 'moderate', 'high', 'critical'])
export const INCIDENT_STATUS = Object.freeze(['open', 'investigating', 'closed'])

const cutoverError = () => new Error(
  'Legacy clinical incident access is disabled. Use the migration appraisals and clinical incidents workspace.',
)

export async function getIncidents() { throw cutoverError() }
export async function saveIncident() { throw cutoverError() }
export async function deleteIncident() { throw cutoverError() }
