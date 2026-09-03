import { useEffect, useState } from 'react'
import type { IconName } from '../components/common/Icon'

export type RouteId = 'overview' | 'alerts' | 'sites' | 'predictions' | 'history' | 'data-quality' | 'settings'
type NavigationGroup = 'navigation' | 'system'

type AppRoute = {
    id: RouteId
    path: `/${string}` | '/'
    label: string
    subtitle: string
    icon?: IconName
    group: NavigationGroup
}

export const routes: readonly AppRoute[] = [
    { id: 'overview', path: '/', label: 'Vue d’ensemble', subtitle: 'Suivi des consommations et comparaison avec le jumeau numérique', icon: 'grid', group: 'navigation' },
    { id: 'alerts', path: '/alertes', label: 'Alertes', subtitle: 'Suivez les anomalies détectées sur vos équipements.', icon: 'bell', group: 'navigation' },
    { id: 'sites', path: '/sites', label: 'Sites', subtitle: 'Consultez les mesures et le statut de chaque site connecté.', icon: 'building', group: 'navigation' },
    { id: 'predictions', path: '/modele-h2', label: 'Modèle H+2', subtitle: 'Suivez les prévisions produites par le jumeau numérique.', icon: 'brain', group: 'navigation' },
    { id: 'history', path: '/historique', label: 'Historique', subtitle: 'Analysez les consommations et les anomalies passées.', icon: 'clock', group: 'navigation' },
    { id: 'data-quality', path: '/qualite-des-donnees', label: 'Qualité des données', subtitle: 'Contrôlez la fraîcheur et la fiabilité des données IoT.', group: 'system' },
    { id: 'settings', path: '/parametres', label: 'Paramètres', subtitle: 'Gérez les préférences et les seuils de surveillance.', icon: 'settings', group: 'system' },
]

function getRoute(path: string): AppRoute {
    return routes.find((route) => route.path === path) ?? routes[0]
}

function getCurrentPath() {
    return window.location.hash.slice(1) || '/'
}

export function useRouter() {
    const [path, setPath] = useState(getCurrentPath)

    useEffect(() => {
        const updatePath = () => setPath(getCurrentPath())
        window.addEventListener('hashchange', updatePath)
        return () => window.removeEventListener('hashchange', updatePath)
    }, [])

    return getRoute(path)
}
