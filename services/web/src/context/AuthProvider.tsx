import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getAccessToken, setSessionEndHandler } from '../api/client'
import { login as requestLogin, logout as endSession, restoreSession } from '../api/auth'

type AuthStatus = 'checking' | 'authenticated' | 'anonymous'

type AuthContextValue = {
    status: AuthStatus
    isAuthenticated: boolean
    sessionExpired: boolean
    login: (email: string, password: string) => Promise<void>
    logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: Readonly<{ children: ReactNode }>) {
    const [status, setStatus] = useState<AuthStatus>(() => (getAccessToken() ? 'authenticated' : 'checking'))
    const [sessionExpired, setSessionExpired] = useState(false)

    // Au chargement, l onglet n a pas de jeton en memoire mais le cookie de
    // session peut encore etre valide. On tente une reprise avant d afficher
    // la page de connexion.
    useEffect(() => {
        if (getAccessToken()) return
        let abandoned = false
        void restoreSession().then((restored) => {
            if (!abandoned) setStatus(restored ? 'authenticated' : 'anonymous')
        })
        return () => { abandoned = true }
    }, [])

    // Le client HTTP previent quand un renouvellement a echoue en cours de route.
    useEffect(() => {
        setSessionEndHandler(() => {
            setSessionExpired(true)
            setStatus('anonymous')
        })
        return () => setSessionEndHandler(null)
    }, [])

    const value = useMemo<AuthContextValue>(() => ({
        status,
        isAuthenticated: status === 'authenticated',
        sessionExpired,
        async login(email, password) {
            await requestLogin(email, password)
            setSessionExpired(false)
            setStatus('authenticated')
        },
        async logout() {
            await endSession()
            setSessionExpired(false)
            setStatus('anonymous')
        },
    }), [status, sessionExpired])

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (!context) throw new Error('useAuth doit être utilisé dans AuthProvider.')
    return context
}
