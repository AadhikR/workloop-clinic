const cutoverError = () => new Error(
  'Legacy asset access is disabled. Use the migration assets and professional development workspace.',
)

export async function getAssets() { throw cutoverError() /* Use the migration assets and professional development workspace. */ }
export async function saveAsset() { throw cutoverError() /* Use the migration assets and professional development workspace. */ }
export async function deleteAsset() { throw cutoverError() /* Use the migration assets and professional development workspace. */ }
export async function getAssetAssignments() { throw cutoverError() /* Use the migration assets and professional development workspace. */ }
export async function assignAsset() { throw cutoverError() /* Use the migration assets and professional development workspace. */ }
export async function returnAsset() { throw cutoverError() /* Use the migration assets and professional development workspace. */ }
export async function getEmployeeCurrentAssets() { throw cutoverError() /* Use the migration assets and professional development workspace. */ }
