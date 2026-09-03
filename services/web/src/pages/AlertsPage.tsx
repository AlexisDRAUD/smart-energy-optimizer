import { useCallback, useEffect, useMemo, useState } from 'react'
import { getAlerts } from '../api/alerts'
import { ErrorBarChart } from '../components/charts/ErrorBarChart'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { periodOptions } from '../data/dashboard'
import { useSiteSelection } from '../hooks/useSiteSelection'
import type { ApiAlert } from '../types/api'
import { formatDateTime } from '../utils/formatters'

function getDailyAlerts(alerts: ApiAlert[]) {
    const days = Array.from({ length: 7 }, (_, index) => {
        const date = new Date()
        date.setDate(date.getDate() - (6 - index))
        return date
    })
    return days.map((date) => {
        const key = date.toISOString().slice(0, 10)
        return {
            label: new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short' }).format(date),
            errors: alerts.filter((alert) => alert.triggered_at.slice(0, 10) === key).length,
        }
    })
}

export function AlertsPage() {
    const { sites, siteId, setSiteId, error: sitesError, isLoading: sitesLoading, reload: reloadSites } = useSiteSelection()
    const [period, setPeriod] = useState(periodOptions[0])
    const [alerts, setAlerts] = useState<ApiAlert[]>([])
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)

    const load = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            setAlerts(await getAlerts(false))
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de charger les alertes.')
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        void load()
    }, [load])

    const siteAlerts = useMemo(() => alerts.filter((alert) => alert.site_id === siteId), [alerts, siteId])
    const criticalAlerts = siteAlerts.filter((alert) => alert.severity === 'critical').length

    return (
        <>
            <DashboardFilters sites={sites} siteId={siteId} period={period} onSiteChange={setSiteId} onPeriodChange={setPeriod} onRefresh={load} />
            <PageFeedback isLoading={sitesLoading || isLoading} error={sitesError ?? error} onRetry={() => { void reloadSites(); void load() }} />
            {siteId !== null && (
                <>
                    <section className="alert-summary-grid"><article className="metric-card"><p><span className="metric-dot orange" /> Alertes relevées</p><strong>{siteAlerts.length}</strong><small>Pour le site sélectionné</small></article><article className="metric-card"><p><span className="metric-dot red" /> Alertes critiques</p><strong>{criticalAlerts}</strong><small>Nécessitent une intervention</small></article><article className="metric-card"><p><span className="metric-dot green" /> Alertes actives</p><strong>{siteAlerts.filter((alert) => alert.is_active).length}</strong><small>Non résolues</small></article></section>
                    <section className="alerts-analysis-grid"><article className="chart-card errors-chart-card"><div className="card-heading"><div><h2>Alertes détectées par jour</h2><p>Données issues de l’API pour le site sélectionné</p></div><span className="chart-unit">Alertes</span></div><ErrorBarChart data={getDailyAlerts(siteAlerts)} /></article><article className="side-card recent-alerts-card"><h2>Alertes récentes</h2><div className="alert-totals"><span>{criticalAlerts} Critique{criticalAlerts > 1 ? 's' : ''}</span><span>{siteAlerts.filter((alert) => alert.severity === 'warning').length} À surveiller</span></div><div className="recent-alert-list">{siteAlerts.length ? siteAlerts.map((alert) => <div className="alert-item" key={alert.id}><span className={`metric-dot ${alert.severity === 'critical' ? 'red' : 'orange'}`} /><div><strong>{alert.message}</strong><p>{alert.is_active ? 'Alerte active' : 'Alerte résolue'}</p><small>{formatDateTime(alert.triggered_at)}</small></div></div>) : <p className="empty-state">Aucune alerte pour ce site.</p>}</div></article></section>
                </>
            )}
        </>
    )
}
