export async function readFinancialCollection(readPage) {
  const items = []
  const identifiers = new Set()
  const cursors = new Set()
  let cursor
  do {
    const result = await readPage({ limit: 100, ...(cursor ? { cursor } : {}) })
    for (const item of result.items) {
      if (identifiers.has(item.id)) throw new Error('Financial collection changed')
      identifiers.add(item.id)
      items.push(item)
    }
    cursor = result.page.nextCursor
    if (cursor && cursors.has(cursor)) throw new Error('Financial pagination repeated')
    if (cursor) cursors.add(cursor)
  } while (cursor)
  return { items }
}
