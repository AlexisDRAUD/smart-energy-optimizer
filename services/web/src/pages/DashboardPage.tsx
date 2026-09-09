import { useCallback, useState } from 'react'
import { getAlertsPage, type AlertsPage } from '../api/alerts'
import { getOverview } from '../api/dashboard'
import { getConsumptionChart } from '../api/consumptionChart'
import { getLatestReading } from '../api/sites'
import { ApiError } from '../api/client'
import { CriticalAlertPopup } from '../components/alerts/CriticalAlertPopup'
import { ConsumptionChart } from '../components/charts/ConsumptionChart'
import { DataDetails } from '../components/charts/DataDetails'
import { DataTable, type Column } from '../components/common/DataTable'
import { MetricCard } from '../components/common/MetricCard'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { chartWindow } from '../utils/consumptionChart'
import { useFilters } from '../hooks/useFilters'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import type { ApiConsumptionChart, ApiLatestReading, ApiOverview, ApiOverviewSite } from '../types/api'
import { formatAlertOrigin, formatDateTime, formatEnergy, formatPercent, formatPower, severityDot } from '../utils/formatters'

type DashboardData = {
    overview: ApiOverview
    alerts: AlertsPage
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
            getAlertsPage({ start, limit: 100 }, signal),
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
    const selectedSiteOverview = data?.overview.by_site.find((site) => site.site_id === siteId)
    const currentValue = data?.latest?.consumption_kwh ?? null
    const futurePredictions = data?.chart.future_predictions ?? []
    const prediction = futurePredictions[futurePredictions.length - 1]
    const comparison = data?.chart.last_evaluated
    const deviation = comparison?.deviation_percent ?? null
    const criticalAlert = data?.alerts.items.find((alert) => alert.severity === 'critical')
    const [dismissedCriticalId, setDismissedCriticalId] = useState<number | null>(() => {
        const stored = sessionStorage.getItem('enervision_dismissed_critical_alert')
        return stored === null ? null : Number(stored)
    })

    const siteNameOf = (siteIdentifier: string) => sites.find((site) => site.site_id === siteIdentifier)?.site_name ?? siteIdentifier
    const dismissCriticalAlert = () => {
        if (!criticalAlert) return
        sessionStorage.setItem('enervision_dismissed_critical_alert', String(criticalAlert.id))
        setDismissedCriticalId(criticalAlert.id)
    }

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
                error={sitesError ?? (error && data ? `${error} Les dernières données reçues restent affichées ; elles ne sont pas à jour.` : error)}
                onRetry={() => { void reloadSites(); void refresh() }}
            />

            {data && selectedSite && (
                <>
                    <section className="card-grid">
                        <MetricCard
                            label="Consommation actuelle"
                            value={currentValue === null ? 'Mesure manquante' : formatEnergy(currentValue)}
                            hint={<>{data.latest ? formatDateTime(data.latest.measured_at) : 'Aucun relevé disponible'}{currentValue === null && <><br />La dernière mesure ne contient pas de consommation. Une prévision peut exister à partir de relevés antérieurs.</>}</>}
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
                            label="Charge du site"
                            value={selectedSiteOverview ? formatPercent(selectedSiteOverview.load_rate_percent) : 'Indisponible'}
                            hint={selectedSiteOverview
                                ? <>{selectedSite.site_name} · {formatPower(selectedSiteOverview.consumption_kw)} sur {formatPower(selectedSiteOverview.capacity_kw)}<br />{formatDateTime(selectedSiteOverview.measured_at)}</>
                                : `${selectedSite.site_name} · aucun relevé exploitable sur ${formatPower(selectedSite.capacity_kw)}`}
                            dot="green"
                        />
                    </section>

                    <section className="analysis-grid">
                        <article className="chart-card">
                            <div className="card-heading">
                                <div>
                                    <h2>Consommation réelle et prédite</h2>
                                    <p>{selectedSite.site_name} · H+2 · version {data.chart.model_version}</p>
                                </div>
                                <div className="legend">
                                    <span><i className="solid-line" /> Réel</span>
                                    <span><i className="dashed-line" /> Prédiction H+2</span>
                                </div>
                            </div>
                            <p className="chart-context">Du {formatDateTime(data.chart.start)} au {formatDateTime(data.chart.end)} · heures locales</p>
                            <ConsumptionChart points={data.chart.readings} predictions={data.chart.historical_predictions} futurePredictions={data.chart.future_predictions} futureEnd={data.chart.future_end} start={data.chart.start} end={data.chart.end} cadenceSeconds={data.chart.cadence_seconds} />
                            <p className="chart-context">Zone teintée : futur H+2 agrandi pour rester lisible. L’échelle de consommation reste commune. L’écart n’est évaluable qu’à réception du réel au même instant.</p>
                            {data.chart.future_coverage.valid_minutes === 0 && <p className="chart-context">Emplacement réservé aux prévisions futures : aucune valeur disponible.</p>}
                            {data.chart.prediction_coverage.valid_minutes === 0 && <p className="chart-context">Aucune prédiction historique exploitable pour cette version sur la période.</p>}
                            <div className="data-quality-summary" aria-label="Qualité des données réelles">
                                <span><small>Couverture exploitable</small><strong>{formatPercent(data.chart.reading_coverage.percent)}</strong></span>
                                <span><small>Valeurs nulles</small><strong>{data.chart.reading_coverage.null_minutes.toLocaleString('fr-FR')}</strong></span>
                                <span><small>Minutes absentes</small><strong>{data.chart.reading_coverage.missing_minutes.toLocaleString('fr-FR')}</strong></span>
                            </div>
                            <DataDetails chart={data.chart} />
                        </article>

                        <div className="right-column">
                            <article className="side-card">
                                <h2>Alertes récentes du parc</h2>
                                <p className="alert-feed-summary">
                                    {data.alerts.total.toLocaleString('fr-FR')} alerte{data.alerts.total > 1 ? 's' : ''} ouverte{data.alerts.total > 1 ? 's' : ''} sur les sites accessibles
                                </p>
                                {data.alerts.items.length
                                    ? data.alerts.items.slice(0, 3).map((alert) => (
                                        <div className="alert-item" key={alert.id}>
                                            <span className={`metric-dot ${severityDot(alert.severity)}`} />
                                            <div>
                                                <strong>{alert.message}</strong>
                                                <small>{siteNameOf(alert.site_id)} · {formatAlertOrigin(alert.origin)} · {formatDateTime(alert.detected_at)}</small>
                                            </div>
                                        </div>
                                    ))
                                    : <p className="empty-state">Aucune alerte sur les sites accessibles pendant la période.</p>}
                                <a className="alert-feed-link" href="#/alertes">Voir le détail des alertes</a>
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

                    {criticalAlert && criticalAlert.id !== dismissedCriticalId && (
                        <CriticalAlertPopup alert={criticalAlert} siteName={siteNameOf(criticalAlert.site_id)} onClose={dismissCriticalAlert} />
                    )}
                </>
            )}
        </>
    )
}
