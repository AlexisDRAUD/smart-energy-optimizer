import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'


beforeEach(() => {
  vi.resetModules()
  sessionStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('apiRequest behaviors', () => {
  it('returns parsed JSON on success', async () => {
    const fakeResponse = { ok: true, json: async () => ({ hello: 'world' }) }
    global.fetch = vi.fn(() => Promise.resolve(fakeResponse)) as any

    const { apiRequest } = await import('../src/api/client')
    const result = await apiRequest('/test', { method: 'GET' }, false)
    expect(result).toEqual({ hello: 'world' })
    expect((global.fetch as any).mock.calls[0][0]).toBe('/test')
  })

  it('includes Authorization header when token set', async () => {
    const fakeResponse = { ok: true, json: async () => ({}) }
    const spy = vi.fn((url, options) => {
      const headers = options.headers
      // Headers may be a Headers instance
      const auth = typeof headers.get === 'function' ? headers.get('Authorization') : headers['Authorization']
      expect(auth).toBe('Bearer token-xyz')
      return Promise.resolve(fakeResponse)
    })
    global.fetch = spy as any

    const { setAccessToken, apiRequest } = await import('../src/api/client')
    setAccessToken('token-xyz')
    await apiRequest('/secure', { method: 'POST' }, true)
    expect(spy).toHaveBeenCalled()
  })

  it('does not set Authorization header when requiresAuth is false', async () => {
    const fakeResponse = { ok: true, json: async () => ({}) }
    const spy = vi.fn((url, options) => {
      const headers = options.headers
      const auth = typeof headers.get === 'function' ? headers.get('Authorization') : headers['Authorization']
      expect(auth).toBeNull()
      return Promise.resolve(fakeResponse)
    })
    global.fetch = spy as any

    const { apiRequest } = await import('../src/api/client')
    await apiRequest('/public', { method: 'GET' }, false)
    expect(spy).toHaveBeenCalled()
  })

  it('throws ApiError with message from error.message', async () => {
    const fakeResponse = { ok: false, status: 400, json: async () => ({ error: { message: 'bad things' } }) }
    global.fetch = vi.fn(() => Promise.resolve(fakeResponse)) as any

    const { apiRequest, ApiError } = await import('../src/api/client')
    await expect(apiRequest('/err', { method: 'GET' }, false)).rejects.toMatchObject({ message: 'bad things', status: 400 })
  })

  it('throws ApiError with message from detail', async () => {
    const fakeResponse = { ok: false, status: 422, json: async () => ({ detail: 'validation failed' }) }
    global.fetch = vi.fn(() => Promise.resolve(fakeResponse)) as any

    const { apiRequest } = await import('../src/api/client')
    await expect(apiRequest('/err2', { method: 'GET' }, false)).rejects.toMatchObject({ message: 'validation failed', status: 422 })
  })
})
