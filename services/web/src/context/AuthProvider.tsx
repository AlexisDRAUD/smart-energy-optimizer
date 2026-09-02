import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { getAccessToken } from '../api/client'
import { login as requestLogin, logout as clearToken } from '../api/auth'

type AuthContextValue = {
    isAuthenticated: boolean
    login: (username: string, password: string) => Promise<void>
    logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: Readonly<{ children: ReactNode }>) {
    const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(getAccessToken()))

    const value = useMemo<AuthContextValue>(() => ({
        isAuthenticated,
        async login(username, password) {
            await requestLogin(username, password)
            setIsAuthenticated(true)
        },
        logout() {
            clearToken()
            setIsAuthenticated(false)
        },
    }), [isAuthenticated])

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (!context) throw new Error('useAuth doit être utilisé dans AuthProvider.')
    return context
}