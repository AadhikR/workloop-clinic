const movedMessage = 'Staffing-rule reads and writes have moved to the migration settings screen.';

/** Legacy staffing-rule reads are disabled after the Phase 7E authority switch. */
export async function getDeptStaffingRules() {
  throw new Error(movedMessage);
}

/** Legacy staffing-rule saves are disabled after the Phase 7E authority switch. */
export async function saveDeptStaffingRule(rule) {
  void rule;
  throw new Error(movedMessage);
}

/** Legacy staffing-rule deletes are disabled after the Phase 7E authority switch. */
export async function deleteDeptStaffingRule(ruleId) {
  void ruleId;
  throw new Error(movedMessage);
}
