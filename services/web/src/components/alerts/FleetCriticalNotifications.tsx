import { useCallback } from 'react'
import { getAlertsPage } from '../../api/alerts'
import { useAutoRefresh } from '../../hooks/useAutoRefresh'
import { formatDateTime } from '../../utils/formatters'

export function FleetCriticalNotifications() {
    const load = useCallback(
        (signal: AbortSignal) => getAlertsPage({ severity: 'critical', limit: 3 }, signal),
        [],
    )
    const { data, error } = useAutoRefresh({
        enabled: true,
        key: 'fleet-critical-notifications',
        load,
        errorMessage: 'Impossible de synchroniser les alertes critiques.',
    })

    if (!data?.total) return null

    const latest = data.items[0]
    return (
        <aside className="fleet-critical-notifications" aria-label="Notifications critiques">
            <a href="#/alertes">
                <span className="fleet-critical-notifications__count" aria-label={`${data.total} alertes critiques ouvertes`}>
                    {data.total > 99 ? '99+' : data.total}
                </span>
                <span className="fleet-critical-notifications__title">Alerte critique</span>
                {latest && <>
                    <strong>{latest.message}</strong>
                    <small>{formatDateTime(latest.detected_at)}</small>
                </>}
                {error && <small>Synchronisation momentanément indisponible</small>}
                <span className="fleet-critical-notifications__link">Voir les alertes</span>
            </a>
        </aside>
    )
}
