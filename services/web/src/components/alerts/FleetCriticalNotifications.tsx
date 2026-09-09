import { useCallback, useState } from 'react'
import { getAlertsPage } from '../../api/alerts'
import { useAutoRefresh } from '../../hooks/useAutoRefresh'
import { Icon } from '../common/Icon'
import { formatDateTime } from '../../utils/formatters'

export function FleetCriticalNotifications() {
    const [isExpanded, setIsExpanded] = useState(true)
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

    const countLabel = data.total > 99 ? '99+' : String(data.total)

    if (!isExpanded) {
        return (
            <button
                type="button"
                className="fleet-critical-notifications fleet-critical-notifications--collapsed"
                onClick={() => setIsExpanded(true)}
                aria-label={`Ouvrir les notifications, ${data.total} alertes critiques ouvertes`}
            >
                <Icon name="bell" size={21} />
                <span className="fleet-critical-notifications__count" aria-hidden="true">{countLabel}</span>
            </button>
        )
    }

    return (
        <aside className="fleet-critical-notifications" aria-label="Notifications critiques">
            <div className="fleet-critical-notifications__heading">
                <div>
                    <span className="fleet-critical-notifications__title">Alertes critiques</span>
                    <small>{data.total.toLocaleString('fr-FR')} ouverte{data.total > 1 ? 's' : ''}</small>
                </div>
                <button type="button" onClick={() => setIsExpanded(false)} aria-label="Réduire les notifications">×</button>
            </div>
            <div className="fleet-critical-notifications__list">
                {data.items.map((alert) => (
                    <a href={`#/alertes?site_id=${encodeURIComponent(alert.site_id)}&alert_id=${alert.id}`} onClick={() => setIsExpanded(false)} key={alert.id}>
                        <strong>{alert.message}</strong>
                        <small>{formatDateTime(alert.detected_at)}</small>
                    </a>
                ))}
            </div>
            <a className="fleet-critical-notifications__link" href="#/alertes" onClick={() => setIsExpanded(false)}>Voir toutes les alertes</a>
            <span className="fleet-critical-notifications__count" aria-label={`${data.total} alertes critiques ouvertes`}>
                {countLabel}
            </span>
                {error && <small>Synchronisation momentanément indisponible</small>}
        </aside>
    )
}
