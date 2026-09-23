export const DEFAULT_SECTIONS = Object.freeze([
  { section_name: 'Clinical Competency', weight: 2, sort_order: 10 },
  { section_name: 'Patient Care Quality', weight: 2, sort_order: 20 },
  { section_name: 'Communication and Teamwork', weight: 1.5, sort_order: 30 },
  { section_name: 'Punctuality and Attendance', weight: 1, sort_order: 40 },
  { section_name: 'Professional Development', weight: 1, sort_order: 50 },
])

export const RATING_LABELS = Object.freeze({
  1: 'Needs improvement', 2: 'Developing', 3: 'Meets expectations',
  4: 'Exceeds expectations', 5: 'Outstanding',
})

const cutoverError = () => new Error(
  'Legacy appraisal access is disabled. Use the migration appraisals and clinical incidents workspace.',
)

export async function getAppraisalCycles() { throw cutoverError() }
export async function saveAppraisalCycle() { throw cutoverError() }
export async function deleteAppraisalCycle() { throw cutoverError() }
export async function getAppraisalsForCycle() { throw cutoverError() }
export async function getMyAppraisals() { throw cutoverError() }
export async function getMyTeamAppraisals() { throw cutoverError() }
export async function managerRateSection() { throw cutoverError() }
export async function createAppraisalsForCycle() { throw cutoverError() }
export async function saveAppraisalReview() { throw cutoverError() }
export async function calibrateAppraisal() { throw cutoverError() }
export async function deleteAppraisal() { throw cutoverError() }
