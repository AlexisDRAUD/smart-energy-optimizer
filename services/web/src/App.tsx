import { useEffect, type ReactNode } from 'react'
import './App.css'
import { Icon } from './components/common/Icon'
import { SettingsModal, type Theme } from './components/settings/SettingsModal'
import { useAuth } from './context/AuthProvider'
import { useStoredState } from './hooks/useStoredState'
import { AlertsPage } from './pages/AlertsPage'
import { DashboardPage } from './pages/DashboardPage'
import { DataQualityPage } from './pages/DataQualityPage'
import { HistoryPage } from './pages/HistoryPage'
import { LoginPage } from './pages/LoginPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { PredictionsPage } from './pages/PredictionsPage'
import { SitesPage } from './pages/SitesPage'
import { routes, type RouteId, useRouter } from './router/routes'

const navigationRoutes = routes.filter((route) => route.group === 'navigation')
const systemRoutes = routes.filter((route) => route.group === 'system')
const settingsRoute = systemRoutes.find((route) => route.id === 'settings')

const pages: Partial<Record<RouteId, ReactNode>> = {
    overview: <DashboardPage />,
    alerts: <AlertsPage />,
    history: <HistoryPage />,
    sites: <SitesPage />,
    predictions: <PredictionsPage />,
    'data-quality': <DataQualityPage />,
}

function NavLink({ path, label, icon, isActive }: Readonly<{ path: string; label: string; icon?: Parameters<typeof Icon>[0]['name']; isActive: boolean }>) {
    return (
        <a className={`nav-item ${isActive ? 'active' : ''}`} href={`#${path}`} aria-current={isActive ? 'page' : undefined}>
            {icon && <Icon name={icon} />}
            {label}
        </a>
    )
}

function App() {
    const { status, isAuthenticated, logout: logoutSession } = useAuth()
    const route = useRouter()
    const [theme, setTheme] = useStoredState<Theme>('enervision_theme', 'light')
    const [language, setLanguage] = useStoredState<string>('enervision_language', 'fr-FR')
    const [timeZone, setTimeZone] = useStoredState<string>('enervision_time_zone', 'Europe/Paris')

    useEffect(() => {
        document.documentElement.lang = language
    }, [language])

    const closeSettings = () => {
        window.location.hash = '/'
    }

    const logout = () => {
        void logoutSession()
        closeSettings()
    }

    if (!isAuthenticated) return <LoginPage />

    // Les paramètres s'ouvrent par-dessus la page d'accueil, pas à la place.
    const displayedRoute = route.id === 'settings' ? routes[0] : route
    const page = pages[displayedRoute.id] ?? <PlaceholderPage title={displayedRoute.label} description={displayedRoute.subtitle} />

    // Une reprise de session est en cours : afficher la page de connexion
    // maintenant la ferait clignoter pour rien.
    if (status === 'checking') return <main className="session-check" role="status">Vérification de la session…</main>
    if (!isAuthenticated) return <LoginPage />

    return (
        <main className={`dashboard-shell theme-${theme}`}>
            <div className="dashboard-layout">
                <aside className="sidebar">
                    <div className="sidebar-brand">
                        <div className="brand">
                            <img src="/logo.png" alt="" className="brand-logo" width="48" height="48" />
                            <span>EnerVision</span>
                        </div>
                    </div>

                    <div className="nav-label">Navigation</div>
                    <nav aria-label="Navigation principale">
                        {navigationRoutes.map((item) => (
                            <NavLink key={item.id} path={item.path} label={item.label} icon={item.icon} isActive={route.id === item.id} />
                        ))}
                        {settingsRoute && (
                            <span className="mobile-settings-link">
                                <NavLink path={settingsRoute.path} label={settingsRoute.label} icon="settings" isActive={route.id === settingsRoute.id} />
                            </span>
                        )}
                    </nav>

                    <div className="sidebar-system">
                        <div className="nav-label">Système</div>
                        {systemRoutes.map((item) => (
                            <NavLink key={item.id} path={item.path} label={item.label} icon={item.icon} isActive={route.id === item.id} />
                        ))}
                    </div>
                </aside>

                <section className="dashboard-content">
                    <header className="topbar">
                        <div className="title-block">
                            <h1>{displayedRoute.label}</h1>
                            <p className="subtitle">{displayedRoute.subtitle}</p>
                        </div>
                    </header>
                    {page}
                </section>
            </div>

            {route.id === 'settings' && (
                <SettingsModal
                    theme={theme}
                    language={language}
                    timeZone={timeZone}
                    onThemeChange={setTheme}
                    onLanguageChange={setLanguage}
                    onTimeZoneChange={setTimeZone}
                    onClose={closeSettings}
                    onLogout={logout}
                />
            )}
        </main>
    )
}

export default App
