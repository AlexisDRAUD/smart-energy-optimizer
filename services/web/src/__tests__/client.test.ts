import { describe, it, expect } from 'vitest'

// Ensure a minimal sessionStorage is available before importing the module that accesses it at load time.
// Vitest runs tests in jsdom by default when --env=jsdom is passed.
if (typeof globalThis.sessionStorage === 'undefined') {
  ;(globalThis as any).sessionStorage = (function () {
    const store: Record<string, string> = {}
    return {
      getItem(key: string) {
        return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null
n      },
      setItem(key: string, value: string) {
        store[key] = String(value)
      },
      removeItem(key: string) {
        delete store[key]
      },
      clear() {
        for (const k of Object.keys(store)) delete store[k]
      },
    }
  })()
}

// dynamic import so the sessionStorage above is set before the module executes
const { setAccessToken, getAccessToken } = await import('../api/client')

describe('api client', () => {
  it('stores and retrieves the access token via sessionStorage', () => {
    setAccessToken('test-token-123')
    expect(getAccessToken()).toBe('test-token-123')
    setAccessToken(null)
    expect(getAccessToken()).toBeNull()
  })
})
