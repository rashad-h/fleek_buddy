const STORAGE_KEY = 'fleek-buyer-id'

/** Stable anonymous buyer identity; only usable in the browser (SSR returns ''). */
export function getBuyerId(): string {
  if (typeof window === 'undefined') return ''
  let id = window.localStorage.getItem(STORAGE_KEY)
  if (!id) {
    id = crypto.randomUUID()
    window.localStorage.setItem(STORAGE_KEY, id)
  }
  return id
}
