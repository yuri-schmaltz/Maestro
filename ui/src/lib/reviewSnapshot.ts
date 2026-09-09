/** Clone mutable configuration while retaining immutable File/Blob handles
 * and store actions. Never freeze the live Zustand state itself. */
export function reviewSnapshot<T>(value: T): T {
  if (Array.isArray(value)) return value.map(item => reviewSnapshot(item)) as T
  if (value && typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, reviewSnapshot(item)])) as T
  }
  return value
}
