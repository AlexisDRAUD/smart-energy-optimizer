// Vitest setup file: provide browser-like globals for tests
if (typeof globalThis.sessionStorage === 'undefined') {
  ;(globalThis as any).sessionStorage = (function () {
    const store: Record<string, string> = {}
    return {
      getItem(key: string) {
        return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null
      },
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

// Ensure global.fetch exists in the environment (tests should mock it explicitly)
if (typeof globalThis.fetch === 'undefined') {
  ;(globalThis as any).fetch = (..._args: any[]) =>
    Promise.reject(new Error('fetch is not available in this test environment; mock global.fetch in the test.'))
}
