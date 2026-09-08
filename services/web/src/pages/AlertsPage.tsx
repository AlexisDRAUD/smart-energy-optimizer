import { useCallback, useEffect, useMemo, useState } from 'react'
import { getAlerts } from '../api/alerts'
import { ErrorBarChart, type AlertDay } from '../components/charts/ErrorBarChart'
import { DataTable, type Column } from '../components/common/DataTable'
import { MetricCard } from '../components/common/MetricCard'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { periodStart } from '../data/periods'
import { useFilters } from '../hooks/useFilters'
import type { ApiAlert, Severity } from '../types/api'
import { formatDateTime, formatDay, formatNumber, formatSeverity } from '../utils/formatters'

const statusLabels = { open: 'Ouverte', acknowledged: 'Acquittée', closed: 'Fermée' }

const columns: Column<ApiAlert>[] = [
    { header: 'Détectée le', cell: (alert) => formatDateTime(alert.detected_at) },
    { header: 'Type', cell: (alert) => alert.type },
    { header: 'Gravité', cell: (alert) => formatSeverity(alert.severity) },
    { header: 'Message', cell: (alert) => alert.message },
    { header: 'Valeur', cell: (alert) => formatNumber(alert.value) },
    { header: 'Seuil', cell: (alert) => formatNumber(alert.threshold_value) },
    { header: 'État', cell: (alert) => statusLabels[alert.status] },
]

/** Une barre par jour où au moins une alerte a été détectée. */
function alertsByDay(alerts: ApiAlert[]): AlertDay[] {
    const counts = new Map<string, number>()
    alerts.forEach((alert) => {
        const day = alert.detected_at.slice(0, 10)
        counts.set(day, (counts.get(day) ?? 0) + 1)
    })
    return [...counts.entries()]
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([day, errors]) => ({ label: formatDay(day), errors }))
}

function countBySeverity(alerts: ApiAlert[], ...severities: Severity[]) {
    return alerts.filter((alert) => severities.includes(alert.severity)).length
}

export function AlertsPage() {
    const { sites, siteId, setSiteId, period, setPeriod, error: sitesError, isLoading: sitesLoading, reload: reloadSites } = useFilters()
    const [alerts, setAlerts] = useState<ApiAlert[]>([])
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)

    // Une seule requête, donc une seule source pour les compteurs, le
    // graphique et le tableau. /alerts/summary ne sait pas filtrer par site,
    // ses chiffres porteraient sur tout le parc.
    const load = useCallback(async () => {
        if (siteId === null) return
        setIsLoading(true)
        setError(null)
        try {
            setAlerts(await getAlerts({ siteId, start: periodStart(period) }))
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de charger les alertes.')
        } finally {
            setIsLoading(false)
        }
    }, [period, siteId])

    useEffect(() => {
        void load()
    }, [load])

    const chartData = useMemo(() => alertsByDay(alerts), [alerts])

    return (
        <>
            <DashboardFilters
                sites={sites}
                siteId={siteId}
                onSiteChange={setSiteId}
                onRefresh={load}
                period={period}
                onPeriodChange={setPeriod}
            />
            <PageFeedback
                isLoading={sitesLoading || isLoading}
                error={sitesError ?? error}
                onRetry={() => { void reloadSites(); void load() }}
            />

            <section className="card-grid">
                <MetricCard label="Alertes ouvertes" value={alerts.length} dot="blue" />
                <MetricCard label="Critiques" value={countBySeverity(alerts, 'critical')} dot="red" />
                <MetricCard label="Hautes" value={countBySeverity(alerts, 'high')} dot="orange" />
                <MetricCard label="Moyennes et faibles" value={countBySeverity(alerts, 'medium', 'low')} dot="teal" />
            </section>

            <article className="chart-card">
                <div className="card-heading">
                    <div><h2>Alertes ouvertes par jour</h2></div>
                    <span className="chart-unit">Alertes</span>
                </div>
                {chartData.length
                    ? <ErrorBarChart data={chartData} />
                    : <p className="empty-state">Aucune alerte sur la période.</p>}
            </article>

            <article className="table-card">
                <div className="card-heading">
                    <div><h2>Détail des alertes</h2></div>
                    <span>{alerts.length} alerte{alerts.length > 1 ? 's' : ''}</span>
                </div>
                <DataTable columns={columns} rows={alerts} rowKey={(alert) => String(alert.id)} emptyLabel="Aucune alerte sur la période." />
            </article>
        </>
    )
}
