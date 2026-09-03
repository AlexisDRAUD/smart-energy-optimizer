const API_URL = (import.meta.env.VITE_BACK_API_URL ?? '').replace(/\/$/, '')
const TOKEN_STORAGE_KEY = 'enervision_access_token'

export class ApiError extends Error {
    constructor(message: string, public readonly status: number) {
        super(message)
        this.name = 'ApiError'
    }
}

let accessToken = sessionStorage.getItem(TOKEN_STORAGE_KEY)

export function setAccessToken(token: string | null) {
    accessToken = token
    if (token) {
        sessionStorage.setItem(TOKEN_STORAGE_KEY, token)
    } else {
        sessionStorage.removeItem(TOKEN_STORAGE_KEY)
    }
}

export function getAccessToken() {
    return accessToken
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, requiresAuth = true): Promise<T> {
    const headers = new Headers(options.headers)
    headers.set('Accept', 'application/json')

    if (requiresAuth && accessToken) {
        headers.set('Authorization', `Bearer ${accessToken}`)
    }

    const response = await fetch(`${API_URL}${path}`, { ...options, headers })
    if (!response.ok) {
        let message = 'La requête vers l’API a échoué.'
        try {
            const body: unknown = await response.json()
            if (typeof body === 'object' && body !== null && 'error' in body && typeof body.error === 'object' && body.error !== null && 'message' in body.error && typeof body.error.message === 'string') {
                message = body.error.message
            }
            if (typeof body === 'object' && body !== null && 'detail' in body && typeof body.detail === 'string') {
                message = body.detail
            }
        } catch {
            message = `Erreur API (${response.status}).`
        }
        throw new ApiError(message, response.status)
    }

    return response.json() as Promise<T>
}
