import { apiRequest, setAccessToken } from './client'
import type { ApiToken } from '../types/api'

export async function login(email: string, password: string) {
    const token = await apiRequest<ApiToken>('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
    }, false)
    setAccessToken(token.access_token)
    return token
}

export function logout() {
    setAccessToken(null)
}
