import { useCallback, useState } from 'react'
import { acknowledgeAlert, acknowledgeAllCriticalAlerts, getAlertsPage } from '../../api/alerts'
import { useAutoRefresh } from '../../hooks/useAutoRefresh'
import { Icon } from '../common/Icon'
import { formatDateTime } from '../../utils/formatters'

export function FleetCriticalNotifications() {
    const [isExpanded, setIsExpanded] = useState(true)
    const [pendingAction, setPendingAction] = useState<number | 'all' | null>(null)
    const [actionError, setActionError] = useState<string | null>(null)
    const load = useCallback(
        (signal: AbortSignal) => getAlertsPage({ severity: 'critical', limit: 3 }, signal),
        [],
    )
    const { data, error, refresh } = useAutoRefresh({
        enabled: true,
        key: 'fleet-critical-notifications',
        load,
        errorMessage: 'Impossible de synchroniser les alertes critiques.',
    })

    if (!data?.total) return null

    const countLabel = data.total > 99 ? '99+' : String(data.total)
    const acknowledgeOne = async (alertId: number) => {
        setPendingAction(alertId)
        setActionError(null)
        try {
            await acknowledgeAlert(alertId)
            await refresh()
        } catch {
            setActionError('Impossible de retirer cette notification. Vérifiez vos droits.')
        } finally {
            setPendingAction(null)
        }
    }
    const acknowledgeAll = async () => {
        setPendingAction('all')
        setActionError(null)
        try {
            await acknowledgeAllCriticalAlerts()
            await refresh()
        } catch {
            setActionError('Impossible de retirer les notifications. Vérifiez vos droits.')
        } finally {
            setPendingAction(null)
        }
    }

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
                    <div className="fleet-critical-notifications__item" key={alert.id}>
                        <a href={`#/alertes?site_id=${encodeURIComponent(alert.site_id)}&alert_id=${alert.id}`} onClick={() => setIsExpanded(false)}>
                            <strong>{alert.message}</strong>
                            <small>{formatDateTime(alert.detected_at)}</small>
                        </a>
                        <button
                            type="button"
                            disabled={pendingAction !== null}
                            onClick={() => void acknowledgeOne(alert.id)}
                            aria-label={`Retirer la notification : ${alert.message}`}
                        >×</button>
                    </div>
                ))}
            </div>
            <div className="fleet-critical-notifications__footer">
                <a className="fleet-critical-notifications__link" href="#/alertes" onClick={() => setIsExpanded(false)}>Voir toutes les alertes</a>
                <button type="button" disabled={pendingAction !== null} onClick={() => void acknowledgeAll()}>
                    {pendingAction === 'all' ? 'Retrait…' : 'Tout retirer'}
                </button>
            </div>
            <span className="fleet-critical-notifications__count" aria-label={`${data.total} alertes critiques ouvertes`}>
                {countLabel}
            </span>
            {actionError && <small className="fleet-critical-notifications__error" role="alert">{actionError}</small>}
            {error && <small>Synchronisation momentanément indisponible</small>}
        </aside>
    )
}
