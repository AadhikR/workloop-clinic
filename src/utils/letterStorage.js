const MESSAGE = 'Legacy letter and custom request access is disabled after the Phase 11F cutover.'

function cutoverError() {
  return new Error(MESSAGE)
}

export async function getLetterRequests() {
  throw cutoverError()
}

export async function getPendingLetterCount() {
  throw cutoverError()
}

export async function completeLetterRequest() {
  throw cutoverError()
}

export async function rejectLetterRequest() {
  throw cutoverError()
}

export async function getMyLetterRequests() {
  throw cutoverError()
}

export async function submitLetterRequest() {
  throw cutoverError()
}
