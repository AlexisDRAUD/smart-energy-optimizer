// dynamic import of client inside beforeAll to avoid top-level await
let setAccessToken: (token: string | null) => void
let getAccessToken: () => string | null

beforeAll(async () => {
  const mod = await import('../src/api/client')
  setAccessToken = mod.setAccessToken
  getAccessToken = mod.getAccessToken
})

describe('api client', () => {
  it('stores and retrieves the access token via sessionStorage', () => {
    setAccessToken('test-token-123')
    expect(getAccessToken()).toBe('test-token-123')
    setAccessToken(null)
    expect(getAccessToken()).toBeNull()
  })
})
