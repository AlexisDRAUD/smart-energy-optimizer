import { useCallback, useEffect, useState } from 'react'
import { getAlerts } from '../api/alerts'
import { getOverview, getRecommendations } from '../api/dashboard'
import { getLatestPrediction, getPredictions } from '../api/predictions'
import { getLatestReading } from '../api/sites'
import { getReadings } from '../api/readings'
import { ConsumptionChart } from '../components/charts/ConsumptionChart'
import { DataTable, type Column } from '../components/common/DataTable'
import { MetricCard } from '../components/common/MetricCard'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { periodGranularity, periodStart } from '../data/periods'
import { useFilters } from '../hooks/useFilters'
import type { ApiAlert, ApiLatestReading, ApiOverview, ApiOverviewSite, ApiPrediction, ApiReadings, ApiRecommendation } from '../types/api'
import { formatDateTime, formatEnergy, formatPercent, formatPower, severityDot } from '../utils/formatters'

type DashboardData = {
    overview: ApiOverview
    alerts: ApiAlert[]
    latest: ApiLatestReading | null
    prediction: ApiPrediction | null
    predictions: ApiPrediction[]
    readings: ApiReadings
    recommendations: ApiRecommendation[]
}

export function DashboardPage() {
    const { sites, siteId, setSiteId, period, setPeriod, error: sitesError, isLoading: sitesLoading, reload: reloadSites } = useFilters()
    const [data, setData] = useState<DashboardData | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)

    const load = useCallback(async () => {
        if (siteId === null) return
        setIsLoading(true)
        setError(null)
        try {
            const start = periodStart(period)
            const [overview, alerts, predictions, readings, recommendations] = await Promise.all([
                getOverview(),
                getAlerts({ start }),
                getPredictions(siteId, start),
                getReadings({ siteId, start, granularity: periodGranularity(period) }),
                getRecommendations(siteId),
            ])
            // L'API répond 404 quand rien n'existe encore pour ce site. Ce
            // n'est pas une panne, la page doit rester affichable.
            const [latest, prediction] = await Promise.all([
                getLatestReading(siteId).catch(() => null),
                getLatestPrediction(siteId).catch(() => null),
            ])
            setData({ overview, alerts, latest, prediction, predictions, readings, recommendations })
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de charger le tableau de bord.')
        } finally {
            setIsLoading(false)
        }
    }, [period, siteId])

    useEffect(() => {
        void load()
    }, [load])

    const selectedSite = sites.find((site) => site.site_id === siteId)
    // Le dernier relevé, pas le dernier point du graphique : les points
    // agrégés sont des sommes et ne se comparent pas à une prévision.
    const currentValue = data?.latest?.consumption_kwh ?? null
    const predictionValue = data?.prediction?.predicted_kwh ?? null
    const deviation = currentValue !== null && predictionValue !== null && predictionValue !== 0
        ? (currentValue - predictionValue) / predictionValue * 100
        : null

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
                onRefresh={() => { void reloadSites(); void load() }}
                period={period}
                onPeriodChange={setPeriod}
            />
            <PageFeedback
                isLoading={sitesLoading || isLoading}
                error={sitesError ?? error}
                onRetry={() => { void reloadSites(); void load() }}
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
                            value={formatEnergy(predictionValue)}
                            hint={data.prediction ? `Prévision pour ${formatDateTime(data.prediction.target_at)}` : 'Aucune prévision disponible'}
                            dot="teal"
                        />
                        <MetricCard
                            label="Écart modèle / réel"
                            value={deviation === null ? '—' : `${deviation > 0 ? '+' : ''}${formatPercent(deviation)}`}
                            hint="Entre le dernier relevé et la prévision"
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
                                    <p>
                                        {period === 'day'
                                            ? `Mesures à la minute et prévisions pour ${selectedSite.site_name}`
                                            : `Consommation agrégée pour ${selectedSite.site_name}`}
                                    </p>
                                </div>
                                <div className="legend">
                                    <span><i className="solid-line" /> Réel</span>
                                    {period === 'day' && <span><i className="dashed-line" /> Prédiction</span>}
                                </div>
                            </div>
                            {data.readings.points.length
                                ? <ConsumptionChart points={data.readings.points} predictions={period === 'day' ? data.predictions : []} />
                                : <p className="empty-state">Aucun relevé sur la période.</p>}
                        </article>

                        <div className="right-column">
                            <article className="side-card">
                                <h2>Alertes récentes</h2>
                                {data.alerts.length
                                    ? data.alerts.slice(0, 3).map((alert) => (
                                        <div className="alert-item" key={alert.id}>
                                            <span className={`metric-dot ${severityDot(alert.severity)}`} />
                                            <div>
                                                <strong>{alert.message}</strong>
                                                <small>{formatDateTime(alert.detected_at)}</small>
                                            </div>
                                        </div>
                                    ))
                                    : <p className="empty-state">Aucune alerte sur la période.</p>}
                            </article>

                            <article className="side-card">
                                <h2>Recommandations</h2>
                                {data.recommendations.length
                                    ? data.recommendations.slice(0, 3).map((recommendation, index) => (
                                        <div className="recommendation" key={recommendation.action}>
                                            <b>{String(index + 1).padStart(2, '0')}</b>
                                            <div>
                                                <strong>{recommendation.action}</strong>
                                                <p>Économie estimée : {formatEnergy(recommendation.estimated_savings_kwh)}</p>
                                            </div>
                                        </div>
                                    ))
                                    : <p className="empty-state">Aucune recommandation.</p>}
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
