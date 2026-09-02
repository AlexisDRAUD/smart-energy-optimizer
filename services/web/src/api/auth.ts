import { apiRequest, setAccessToken } from './client'
import type { ApiToken } from '../types/api'

export async function login(username: string, password: string) {
    const body = new URLSearchParams({ username, password })
    const token = await apiRequest<ApiToken>('/api/v1/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
    }, false)
    setAccessToken(token.access_token)
    return token
}

export function logout() {
    setAccessToken(null)
}