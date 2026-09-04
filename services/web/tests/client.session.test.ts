beforeEach(() => {
  jest.resetModules()
  sessionStorage.clear()
})

afterEach(() => {
  jest.restoreAllMocks()
})

const unauthorized = { ok: false, status: 401, json: async () => ({ error: { code: 'unauthorized', message: 'expired' } }) }
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body })

describe('renouvellement du jeton', () => {
  it('renouvelle puis rejoue l appel quand le jeton a expire', async () => {
    const calls: string[] = []
    globalThis.fetch = jest.fn((url: string) => {
      calls.push(url)
      if (url.endsWith('/api/v1/auth/refresh')) return Promise.resolve(ok({ access_token: 'token-neuf' }))
      return Promise.resolve(calls.filter((c) => c === '/sites').length > 1 ? ok({ items: [] }) : unauthorized)
    }) as unknown as typeof fetch

    const { apiRequest, setAccessToken, getAccessToken } = await import('../src/api/client')
    setAccessToken('token-perime')
    const result = await apiRequest('/sites')

    expect(result).toEqual({ items: [] })
    expect(calls).toEqual(['/sites', '/api/v1/auth/refresh', '/sites'])
    expect(getAccessToken()).toBe('token-neuf')
  })

  it('termine la session quand le renouvellement echoue', async () => {
    globalThis.fetch = jest.fn(() => Promise.resolve(unauthorized)) as unknown as typeof fetch

    const { apiRequest, setAccessToken, getAccessToken, setSessionEndHandler } = await import('../src/api/client')
    const onSessionEnd = jest.fn()
    setSessionEndHandler(onSessionEnd)
    setAccessToken('token-perime')

    await expect(apiRequest('/sites')).rejects.toMatchObject({ status: 401 })
    expect(onSessionEnd).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBeNull()
    expect(sessionStorage.getItem('enervision_access_token')).toBeNull()
  })

  it('ne renouvelle qu une fois quand plusieurs appels expirent ensemble', async () => {
    let refreshCalls = 0
    const served = new Set<string>()
    globalThis.fetch = jest.fn((url: string) => {
      if (url.endsWith('/api/v1/auth/refresh')) {
        refreshCalls += 1
        return Promise.resolve(ok({ access_token: 'token-neuf' }))
      }
      if (served.has(url)) return Promise.resolve(ok({ url }))
      served.add(url)
      return Promise.resolve(unauthorized)
    }) as unknown as typeof fetch

    const { apiRequest, setAccessToken } = await import('../src/api/client')
    setAccessToken('token-perime')
    await Promise.all([apiRequest('/sites'), apiRequest('/alerts'), apiRequest('/readings')])

    expect(refreshCalls).toBe(1)
  })

  it('ne tente aucun renouvellement sur un appel non authentifie', async () => {
    const calls: string[] = []
    globalThis.fetch = jest.fn((url: string) => {
      calls.push(url)
      return Promise.resolve(unauthorized)
    }) as unknown as typeof fetch

    const { apiRequest } = await import('../src/api/client')
    await expect(apiRequest('/api/v1/auth/login', { method: 'POST' }, false)).rejects.toMatchObject({ status: 401 })

    expect(calls).toEqual(['/api/v1/auth/login'])
  })

  it('accepte une reponse 204 sans corps', async () => {
    globalThis.fetch = jest.fn(() => Promise.resolve({
      ok: true,
      status: 204,
      json: async () => { throw new Error('pas de corps a lire') },
    })) as unknown as typeof fetch

    const { apiRequest } = await import('../src/api/client')
    await expect(apiRequest('/api/v1/auth/logout', { method: 'POST' }, false)).resolves.toBeUndefined()
  })
})
