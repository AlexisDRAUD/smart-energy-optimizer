beforeEach(() => {
  jest.resetModules()
  sessionStorage.clear()
})

afterEach(() => {
  jest.restoreAllMocks()
})

describe('apiRequest behaviors', () => {
  it('returns parsed JSON on success', async () => {
    const fakeResponse = { ok: true, json: async () => ({ hello: 'world' }) }
    globalThis.fetch = jest.fn(() => Promise.resolve(fakeResponse)) as unknown as typeof fetch

    const { apiRequest } = await import('../src/api/client')
    const result = await apiRequest('/test', { method: 'GET' }, false)
    expect(result).toEqual({ hello: 'world' })
    expect(jest.mocked(globalThis.fetch).mock.calls[0][0]).toBe('/test')
  })

  it('includes Authorization header when token set', async () => {
    const fakeResponse = { ok: true, json: async () => ({}) }
    const spy = jest.fn((url: string, options: RequestInit) => {
      const headers = options.headers as Headers | Record<string, string>
      // Headers may be a Headers instance
      const auth =
        typeof (headers as Headers).get === 'function'
          ? (headers as Headers).get('Authorization')
          : (headers as Record<string, string>)['Authorization']
      expect(auth).toBe('Bearer token-xyz')
      return Promise.resolve(fakeResponse)
    })
    globalThis.fetch = spy as unknown as typeof fetch

    const { setAccessToken, apiRequest } = await import('../src/api/client')
    setAccessToken('token-xyz')
    await apiRequest('/secure', { method: 'POST' }, true)
    expect(spy).toHaveBeenCalled()
  })

  it('does not set Authorization header when requiresAuth is false', async () => {
    const fakeResponse = { ok: true, json: async () => ({}) }
    const spy = jest.fn((url: string, options: RequestInit) => {
      const headers = options.headers as Headers | Record<string, string>
      const auth =
        typeof (headers as Headers).get === 'function'
          ? (headers as Headers).get('Authorization')
          : (headers as Record<string, string>)['Authorization']
      expect(auth).toBeNull()
      return Promise.resolve(fakeResponse)
    })
    globalThis.fetch = spy as unknown as typeof fetch

    const { apiRequest } = await import('../src/api/client')
    await apiRequest('/public', { method: 'GET' }, false)
    expect(spy).toHaveBeenCalled()
  })

  it('throws ApiError with message from error.message', async () => {
    const fakeResponse = { ok: false, status: 400, json: async () => ({ error: { message: 'bad things' } }) }
    globalThis.fetch = jest.fn(() => Promise.resolve(fakeResponse)) as unknown as typeof fetch

    const { apiRequest } = await import('../src/api/client')
    await expect(apiRequest('/err', { method: 'GET' }, false)).rejects.toMatchObject({ message: 'bad things', status: 400 })
  })

  it('throws ApiError with message from detail', async () => {
    const fakeResponse = { ok: false, status: 422, json: async () => ({ detail: 'validation failed' }) }
    globalThis.fetch = jest.fn(() => Promise.resolve(fakeResponse)) as unknown as typeof fetch

    const { apiRequest } = await import('../src/api/client')
    await expect(apiRequest('/err2', { method: 'GET' }, false)).rejects.toMatchObject({ message: 'validation failed', status: 422 })
  })
})
