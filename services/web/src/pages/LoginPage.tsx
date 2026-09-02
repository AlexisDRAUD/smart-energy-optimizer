import { FormEvent, useState } from 'react'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthProvider'

export function LoginPage() {
    const { login } = useAuth()
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState<string | null>(null)
    const [isSubmitting, setIsSubmitting] = useState(false)

    const submit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        setError(null)
        setIsSubmitting(true)
        try {
            await login(username, password)
        } catch (cause) {
            setError(cause instanceof ApiError ? cause.message : 'Connexion impossible. Vérifiez que l’API est disponible.')
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <main className="login-shell">
            <section className="login-card" aria-labelledby="login-title">
                <img src="/logo.png" alt="EnerVision" className="login-logo" />
                <h1 id="login-title">Bienvenue sur EnerVision</h1>
                <p>Connectez-vous pour suivre vos consommations énergétiques.</p>
                <form onSubmit={submit}>
                    <label htmlFor="username">Identifiant<input id="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required /></label>
                    <label htmlFor="password">Mot de passe<input id="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
                    {error && <p className="login-error" role="alert">{error}</p>}
                    <button type="submit" disabled={isSubmitting}>{isSubmitting ? 'Connexion…' : 'Se connecter'}</button>
                </form>
            </section>
        </main>
    )
}
