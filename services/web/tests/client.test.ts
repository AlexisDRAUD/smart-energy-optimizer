import { describe, it, expect } from 'vitest'

// dynamic import of client inside beforeAll to avoid top-level await
import { beforeAll } from 'vitest'
let setAccessToken: any
let getAccessToken: any
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
