import { useCallback } from 'react'
import { getAlerts } from '../api/alerts'
import { getOverview } from '../api/dashboard'
import { getConsumptionChart } from '../api/consumptionChart'
import { getLatestReading } from '../api/sites'
import { ApiError } from '../api/client'
import { ConsumptionChart } from '../components/charts/ConsumptionChart'
import { DataDetails } from '../components/charts/DataDetails'
import { DataTable, type Column } from '../components/common/DataTable'
import { MetricCard } from '../components/common/MetricCard'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { chartWindow } from '../utils/consumptionChart'
import { useFilters } from '../hooks/useFilters'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import type { ApiAlert, ApiConsumptionChart, ApiLatestReading, ApiOverview, ApiOverviewSite } from '../types/api'
import { formatAlertOrigin, formatDateTime, formatEnergy, formatPercent, formatPower, severityDot } from '../utils/formatters'

type DashboardData = {
    overview: ApiOverview
    alerts: ApiAlert[]
    latest: ApiLatestReading | null
    chart: ApiConsumptionChart
}

export function DashboardPage() {
    const { sites, siteId, setSiteId, period, setPeriod, error: sitesError, isLoading: sitesLoading, reload: reloadSites } = useFilters()
    const fetchDashboard = useCallback(async (signal: AbortSignal): Promise<DashboardData> => {
        if (siteId === null) throw new Error('Aucun site sélectionné.')
        const { start, end } = chartWindow(period)
        const latestRequest = getLatestReading(siteId, signal).catch((cause: unknown) => {
            if (cause instanceof ApiError && cause.status === 404) return null
            throw cause
        })
        const [overview, alerts, chart, latest] = await Promise.all([
            getOverview(signal),
            getAlerts({ siteId, start }, signal),
            getConsumptionChart(siteId, start, end, signal),
            latestRequest,
        ])
        return { overview, alerts, latest, chart }
    }, [period, siteId])
    const { data, error, isInitialLoading, isSyncing, lastSyncedAt, refresh } = useAutoRefresh({
        enabled: siteId !== null,
        key: `${siteId ?? 'none'}:${period}`,
        load: fetchDashboard,
        errorMessage: 'Impossible de charger le tableau de bord.',
    })

    const selectedSite = sites.find((site) => site.site_id === siteId)
    const currentValue = data?.latest?.consumption_kwh ?? null
    const futurePredictions = data?.chart.future_predictions ?? []
    const prediction = futurePredictions[futurePredictions.length - 1]
    const comparison = data?.chart.last_evaluated
    const deviation = comparison?.deviation_percent ?? null

    const siteNameOf = (siteIdentifier: string) => sites.find((site) => site.site_id === siteIdentifier)?.site_name ?? siteIdentifier

    const columns: Column<ApiOverviewSite>[] = [
        { header: 'Site', cell: (row) => siteNameOf(row.site_id) },
        { header: 'Consommation', cell: (row) => formatPower(row.consumption_kw) },
        { header: 'Puissance souscrite', cell: (row) => formatPower(row.capacity_kw) },
        { header: 'Taux de charge', cell: (row) => formatPercent(row.load_rate_percent) },
        { header: 'Dernière donnée', cell: (row) => formatDateTime(row.measured_at) },
    ]

    return (
        <>
            <DashboardFilters
                sites={sites}
                siteId={siteId}
                onSiteChange={setSiteId}
                onRefresh={refresh}
                period={period}
                onPeriodChange={setPeriod}
                isSyncing={isSyncing}
                lastSyncedAt={lastSyncedAt}
                syncError={error !== null}
            />
            <PageFeedback
                isLoading={sitesLoading || isInitialLoading}
                error={sitesError ?? error}
                onRetry={() => { void reloadSites(); void refresh() }}
            />

            {data && selectedSite && (
                <>
                    <section className="card-grid">
                        <MetricCard
                            label="Consommation actuelle"
                            value={formatEnergy(currentValue)}
                            hint={data.latest ? formatDateTime(data.latest.measured_at) : 'Aucun relevé disponible'}
                            dot="blue"
                        />
                        <MetricCard
                            label="Prédiction H+2"
                            value={formatEnergy(prediction?.predicted_kwh)}
                            hint={prediction ? `Pour ${formatDateTime(prediction.target_at)} · version ${data.chart.model_version}` : 'Aucune prévision future H+2 disponible'}
                            dot="teal"
                        />
                        <MetricCard
                            label="Dernier écart évalué"
                            value={deviation === null ? 'Indisponible' : `${deviation > 0 ? '+' : ''}${formatPercent(deviation)}`}
                            hint={<>
                                {comparison ? `${formatDateTime(comparison.target_at)} · H+2 (${comparison.horizon_minutes} min) · version ${comparison.model_version}` : `Aucune paire réel/prédit sur la période · H+2 · version ${data.chart.model_version}`}
                                {comparison && <><br />Réel {formatEnergy(comparison.actual_kwh)} · prédit {formatEnergy(comparison.predicted_kwh)}</>}
                                {comparison?.predicted_kwh === 0 && <><br />Pourcentage indisponible : prédiction égale à zéro.</>}
                                <br />Dernière comparaison historique de la période.
                            </>}
                            dot="orange"
                        />
                        <MetricCard
                            label="Charge du parc"
                            value={formatPercent(data.overview.average_load_rate_percent)}
                            hint={`${formatPower(data.overview.total_consumption_kw)} sur ${formatPower(data.overview.total_capacity_kw)}`}
                            dot="green"
                        />
                    </section>

                    <section className="analysis-grid">
                        <article className="chart-card">
                            <div className="card-heading">
                                <div>
                                    <h2>Consommation réelle et prédite</h2>
                                    <p>{selectedSite.site_name}</p>
                                </div>
                                <div className="legend">
                                    <span><i className="solid-line" /> Réel</span>
                                    <span><i className="dashed-line" /> Prédiction H+2</span>
                                </div>
                            </div>
                            <ConsumptionChart points={data.chart.readings} predictions={data.chart.historical_predictions} start={data.chart.start} end={data.chart.end} cadenceSeconds={data.chart.cadence_seconds} />
                            <div className="data-quality-summary" aria-label="Qualité des données réelles">
                                <span><small>Couverture exploitable</small><strong>{formatPercent(data.chart.reading_coverage.percent)}</strong></span>
                                <span><small>Valeurs nulles</small><strong>{data.chart.reading_coverage.null_minutes.toLocaleString('fr-FR')}</strong></span>
                                <span><small>Minutes absentes</small><strong>{data.chart.reading_coverage.missing_minutes.toLocaleString('fr-FR')}</strong></span>
                            </div>
                            <DataDetails chart={data.chart} />
                        </article>

                        <div className="right-column">
                            <article className="side-card">
                                <h2>Prévisions futures H+2</h2>
                                <ConsumptionChart points={[]} predictions={data.chart.future_predictions} start={data.chart.end} end={data.chart.future_end} cadenceSeconds={data.chart.cadence_seconds} label="Prévisions futures H+2" />
                            </article>
                            <article className="side-card">
                                <h2>Alertes récentes</h2>
                                {data.alerts.length
                                    ? data.alerts.slice(0, 3).map((alert) => (
                                        <div className="alert-item" key={alert.id}>
                                            <span className={`metric-dot ${severityDot(alert.severity)}`} />
                                            <div>
                                                <strong>{alert.message}</strong>
                                                <small>{formatAlertOrigin(alert.origin)} · {formatDateTime(alert.detected_at)}</small>
                                            </div>
                                        </div>
                                    ))
                                    : <p className="empty-state">Aucune alerte sur la période.</p>}
                            </article>

                        </div>
                    </section>

                    <article className="table-card">
                        <div className="card-heading">
                            <div><h2>Vue multi-sites</h2></div>
                            <span>
                                {data.overview.site_count} site{data.overview.site_count > 1 ? 's' : ''}
                                {data.overview.incomplete && `, dont ${data.overview.sites_without_valid_reading_count} sans relevé exploitable`}
                            </span>
                        </div>
                        <DataTable
                            columns={columns}
                            rows={data.overview.by_site}
                            rowKey={(row) => row.site_id}
                            emptyLabel="Aucun site avec un relevé exploitable."
                        />
                    </article>
                </>
            )}
        </>
    )
}
