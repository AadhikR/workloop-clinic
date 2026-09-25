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
