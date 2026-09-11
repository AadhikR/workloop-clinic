const movedMessage = 'Department reads and writes have moved to the migration settings screen.';

/** Legacy department reads are disabled after the Phase 7E authority switch. */
export async function getDepartments() {
  throw new Error(movedMessage);
}

/** Legacy department saves are disabled after the Phase 7E authority switch. */
export async function saveDepartment(department) {
  void department;
  throw new Error(movedMessage);
}

/** Legacy department deletes are disabled after the Phase 7E authority switch. */
export async function deleteDepartment(departmentId) {
  void departmentId;
  throw new Error(movedMessage);
}
