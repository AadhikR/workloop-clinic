export async function readCollectionPages(readPage, identify = (item) => item?.id) {
  const items = []
  const cursors = new Set()
  const identities = new Set()
  let cursor = null
  do {
    const response = await readPage(cursor)
    const page = response?.page
    if (!Array.isArray(response?.items) || !page || typeof page.hasMore !== 'boolean'
      || !Number.isInteger(page.limit) || page.limit < 1 || page.limit > 100
      || response.items.length > page.limit
      || page.hasMore && (typeof page.nextCursor !== 'string' || !page.nextCursor || !response.items.length)
      || !page.hasMore && page.nextCursor !== null) throw new Error('Invalid collection page')
    for (const item of response.items) {
      const identity = identify(item)
      if (typeof identity !== 'string' || !identity || identities.has(identity)) throw new Error('Collection changed while loading. Refresh and try again.')
      identities.add(identity)
      items.push(item)
    }
    cursor = page.hasMore ? page.nextCursor : null
    if (cursor && cursors.has(cursor)) throw new Error('Collection pagination is unavailable')
    cursors.add(cursor)
  } while (cursor)
  return items
}
