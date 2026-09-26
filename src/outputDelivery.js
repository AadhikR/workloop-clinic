export function saveDownload(output, browser = globalThis) {
  if (
    !(output?.bytes instanceof Uint8Array)
    || typeof output.filename !== 'string'
    || !output.filename
    || typeof output.contentType !== 'string'
  ) throw new TypeError('Invalid download')
  const url = browser.URL.createObjectURL(new browser.Blob([output.bytes], { type: output.contentType }))
  try {
    const link = browser.document.createElement('a')
    link.href = url
    link.download = output.filename
    link.rel = 'noopener'
    link.click()
  } finally {
    browser.URL.revokeObjectURL(url)
  }
}

export function openPdf(output, browser = globalThis) {
  if (
    !(output?.bytes instanceof Uint8Array)
    || output.contentType !== 'application/pdf'
    || typeof browser.open !== 'function'
  ) throw new TypeError('Invalid PDF output')
  const url = browser.URL.createObjectURL(new browser.Blob([output.bytes], { type: output.contentType }))
  const viewer = browser.open(url, '_blank', 'noopener,noreferrer')
  if (!viewer) {
    browser.URL.revokeObjectURL(url)
    throw new Error('PDF viewer was blocked')
  }
  browser.setTimeout(() => browser.URL.revokeObjectURL(url), 60_000)
}
