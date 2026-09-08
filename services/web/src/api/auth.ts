import { apiRequest, refreshSession, setAccessToken } from './client'
import type { ApiIdentity, ApiToken } from '../types/api'

export async function login(email: string, password: string) {
    const token = await apiRequest<ApiToken>('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
    }, false)
    setAccessToken(token.access_token)
    return token
}

/**
 * Tente de reprendre la session au chargement de l application.
 *
 * Le jeton vit dans le sessionStorage de l onglet, le cookie de session vit
 * dans le navigateur. Rouvrir l application dans un nouvel onglet vide le
 * premier mais pas le second : on demande donc un jeton neuf avant de
 * conclure que personne n est connecte.
 */
export function restoreSession() {
    return refreshSession()
}

/** Compte connecté, tel que l'API le voit. */
export function getCurrentUser() {
    return apiRequest<ApiIdentity>('/api/v1/auth/me')
}

export async function logout() {
    try {
        await apiRequest('/api/v1/auth/logout', { method: 'POST' }, false)
    } catch {
        // L API est injoignable. Le cookie expirera de lui-meme, et on
        // deconnecte quand meme cote navigateur.
    }
    setAccessToken(null)
}
