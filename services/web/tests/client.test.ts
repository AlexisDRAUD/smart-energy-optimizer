import { describe, it, expect } from 'vitest'

// dynamic import of the client after global test setup (tests/setup.ts provides sessionStorage)

const { setAccessToken, getAccessToken } = await import('../src/api/client')

describe('api client', () => {
  it('stores and retrieves the access token via sessionStorage', () => {
    setAccessToken('test-token-123')
    expect(getAccessToken()).toBe('test-token-123')
    setAccessToken(null)
    expect(getAccessToken()).toBeNull()
  })
})
