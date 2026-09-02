import { useEffect, useState, type ReactNode } from 'react'
import './App.css'
import { Icon } from './components/common/Icon'
import { SettingsModal, type Theme } from './components/settings/SettingsModal'
import { useAuth } from './context/AuthProvider'
import { AlertsPage } from './pages/AlertsPage'
import { DashboardPage } from './pages/DashboardPage'
import { DataQualityPage } from './pages/DataQualityPage'
import { HistoryPage } from './pages/HistoryPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { LoginPage } from './pages/LoginPage'
import { PredictionsPage } from './pages/PredictionsPage'
import { SitesPage } from './pages/SitesPage'
import { routes, type RouteId, useRouter } from './router/routes'

const navigationRoutes = routes.filter((route) => route.group === 'navigation')
const systemRoutes = routes.filter((route) => route.group === 'system')
const mobileSettingsRoute = systemRoutes.find((route) => route.id === 'settings')

function HeaderBrand() {
    return <div className="brand"><img src="/logo.png" alt="EnerVision" className="brand-logo" /><span>EnerVision</span></div>
}

function App() {
    const { isAuthenticated, logout: logoutSession } = useAuth()
    const route = useRouter()
    const lastUpdated = 'en direct'
    const [theme, setTheme] = useState<Theme>('light')
    const [language, setLanguage] = useState('fr-FR')
    const [timeZone, setTimeZone] = useState('Europe/Paris')

    useEffect(() => {
        document.documentElement.lang = language
    }, [language])

    const closeSettings = () => {
        window.location.hash = '/'
    }
    const logout = () => {
        logoutSession()
        closeSettings()
    }

    const displayedRoute = route.id === 'settings' ? routes[0] : route
    const pages: Partial<Record<RouteId, ReactNode>> = {
        overview: <DashboardPage />,
        alerts: <AlertsPage />,
        history: <HistoryPage />,
        sites: <SitesPage />,
        predictions: <PredictionsPage />,
        'data-quality': <DataQualityPage />,
    }
    const page = pages[displayedRoute.id] ?? <PlaceholderPage title={displayedRoute.label} description={displayedRoute.subtitle} />

    if (!isAuthenticated) return <LoginPage />

    return (
        <main className={`dashboard-shell theme-${theme}`}>
            <div className="dashboard-layout">
                <aside className="sidebar">
                    <div className="sidebar-brand"><HeaderBrand /></div>
                    <div className="nav-label">Navigation</div>
                    <nav aria-label="Navigation principale">
                        {navigationRoutes.map((item) => (
                            <a className={`nav-item ${route.id === item.id ? 'active' : ''}`} href={`#${item.path}`} key={item.id} aria-current={route.id === item.id ? 'page' : undefined}>
                                {item.icon && <Icon name={item.icon} />}
                                {item.label}
                            </a>
                        ))}
                        {mobileSettingsRoute && (
                            <a className={`nav-item mobile-settings-link ${route.id === mobileSettingsRoute.id ? 'active' : ''}`} href={`#${mobileSettingsRoute.path}`} aria-current={route.id === mobileSettingsRoute.id ? 'page' : undefined}>
                                <Icon name="settings" />
                                {mobileSettingsRoute.label}
                            </a>
                        )}
                    </nav>

                    <div className="sidebar-system">
                        <div className="nav-label">Système</div>
                        {systemRoutes.map((item) => (
                            <a className={`nav-item ${route.id === item.id ? 'active' : ''}`} href={`#${item.path}`} key={item.id} aria-current={route.id === item.id ? 'page' : undefined}>
                                {item.icon ? <Icon name={item.icon} /> : <span className="status-dot success" />}
                                {item.label}
                            </a>
                        ))}
                    </div>

                    <div className="api-status">
                        <div><span className="status-dot success" /> API IoT opérationnelle</div>
                        <span>Dernière synchro</span>
                        <strong>{lastUpdated}</strong>
                    </div>
                </aside>

                <section className="dashboard-content">
                    <header className="topbar">
                        <div className="title-block"><h1>{displayedRoute.label}</h1><p className="subtitle">{displayedRoute.subtitle}</p></div>
                        <div className="live-pill"><span className="status-dot success" /> Données en direct</div>
                    </header>
                    {page}
                </section>
            </div>
            {route.id === 'settings' && <SettingsModal theme={theme} language={language} timeZone={timeZone} onThemeChange={setTheme} onLanguageChange={setLanguage} onTimeZoneChange={setTimeZone} onClose={closeSettings} onLogout={logout} />}
        </main>
    )
}

export default App
