const API_URL = (import.meta.env.VITE_BACK_API_URL ?? '').replace(/\/$/, '')
const TOKEN_STORAGE_KEY = 'enervision_access_token'
const REFRESH_PATH = '/api/v1/auth/refresh'

export class ApiError extends Error {
    constructor(message: string, public readonly status: number) {
        super(message)
        this.name = 'ApiError'
    }
}

let accessToken = sessionStorage.getItem(TOKEN_STORAGE_KEY)
let onSessionEnd: (() => void) | null = null
let pendingRefresh: Promise<boolean> | null = null

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

/** Prevenu quand la session est finie, pour ramener sur la page de connexion. */
export function setSessionEndHandler(handler: (() => void) | null) {
    onSessionEnd = handler
}

/**
 * Demande un access token neuf. Le serveur lit le cookie de session, que le
 * JavaScript ne voit pas.
 *
 * Les appels simultanes partagent la meme requete : une page qui charge cinq
 * graphiques d un coup ne doit pas declencher cinq renouvellements.
 */
export function refreshSession(): Promise<boolean> {
    pendingRefresh ??= (async () => {
        try {
            const response = await fetch(`${API_URL}${REFRESH_PATH}`, {
                method: 'POST',
                headers: { Accept: 'application/json' },
            })
            if (!response.ok) return false
            const token = (await response.json()) as { access_token?: string }
            if (!token.access_token) return false
            setAccessToken(token.access_token)
            return true
        } catch {
            return false
        } finally {
            pendingRefresh = null
        }
    })()
    return pendingRefresh
}

function send(path: string, options: RequestInit, withAuth: boolean) {
    const headers = new Headers(options.headers)
    headers.set('Accept', 'application/json')
    if (withAuth && accessToken) {
        headers.set('Authorization', `Bearer ${accessToken}`)
    }
    return fetch(`${API_URL}${path}`, { ...options, headers })
}

async function readErrorMessage(response: Response) {
    try {
        const body: unknown = await response.json()
        if (typeof body === 'object' && body !== null && 'error' in body && typeof body.error === 'object' && body.error !== null && 'message' in body.error && typeof body.error.message === 'string') {
            return body.error.message
        }
        if (typeof body === 'object' && body !== null && 'detail' in body && typeof body.detail === 'string') {
            return body.detail
        }
        return 'La requête vers l’API a échoué.'
    } catch {
        return `Erreur API (${response.status}).`
    }
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, requiresAuth = true): Promise<T> {
    let response = await send(path, options, requiresAuth)

    // Le jeton a expire pendant la navigation. On en demande un neuf et on
    // rejoue l appel une seule fois. Si le renouvellement echoue, la session
    // est finie : on vide le jeton et on previent l application, qui repasse
    // par la page de connexion au lieu d afficher une erreur sur chaque carte.
    if (response.status === 401 && requiresAuth) {
        const renewed = await refreshSession()
        if (renewed) {
            response = await send(path, options, true)
        }
        if (!renewed || response.status === 401) {
            setAccessToken(null)
            onSessionEnd?.()
        }
    }

    if (!response.ok) {
        throw new ApiError(await readErrorMessage(response), response.status)
    }

    // 204 sur la deconnexion : pas de corps a lire.
    if (response.status === 204) {
        return undefined as T
    }

    return response.json() as Promise<T>
}
