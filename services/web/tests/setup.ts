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

// Ensure global.fetch exists in the environment (tests frequently mock it)
if (typeof globalThis.fetch === 'undefined') {
  ;(globalThis as any).fetch = (() => {
    return (..._args: any[]) => Promise.resolve({ ok: true, json: async () => ({}) })
  })()
}
