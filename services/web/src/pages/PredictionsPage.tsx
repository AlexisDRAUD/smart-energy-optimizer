import { useCallback, useEffect, useState } from 'react'
import { getLatestPrediction, getModel, getModelPerformance, getPredictions } from '../api/predictions'
import { DataTable, type Column } from '../components/common/DataTable'
import { MetricCard } from '../components/common/MetricCard'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { periodStart } from '../data/periods'
import { useFilters } from '../hooks/useFilters'
import type { ApiMetric, ApiModel, ApiModelPerformance, ApiPrediction } from '../types/api'
import { formatDateTime, formatEnergy, formatNumber, formatPercent } from '../utils/formatters'

type ModelData = {
    model: ApiModel
    performance: ApiModelPerformance
    prediction: ApiPrediction | null
    history: ApiPrediction[]
}

const availabilityLabels = { local_fallback: 'Repli local', mlflow: 'MLflow' }

const columns: Column<ApiPrediction>[] = [
    { header: 'Prévue pour', cell: (row) => formatDateTime(row.target_at) },
    { header: 'Calculée le', cell: (row) => formatDateTime(row.predicted_at) },
    { header: 'Prévision', cell: (row) => formatEnergy(row.predicted_kwh) },
    { header: 'Réalisé', cell: (row) => formatEnergy(row.actual_kwh) },
    { header: 'Erreur absolue', cell: (row) => formatNumber(row.absolute_error) },
    { header: 'Modèle', cell: (row) => row.model_version },
]

/** Une ligne du tableau de comparaison entre le modèle et ses références. */
function MetricRow({ label, metric }: Readonly<{ label: string; metric: ApiMetric }>) {
    return (
        <tr>
            <td>{label}</td>
            <td>{formatNumber(metric.mae)}</td>
            <td>{formatNumber(metric.rmse)}</td>
            <td>{formatPercent(metric.mape_percent)}</td>
        </tr>
    )
}

export function PredictionsPage() {
    const { sites, siteId, setSiteId, period, setPeriod, error: sitesError, isLoading: sitesLoading, reload: reloadSites } = useFilters()
    const [data, setData] = useState<ModelData | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)

    const load = useCallback(async () => {
        if (siteId === null) return
        setIsLoading(true)
        setError(null)
        try {
            const start = periodStart(period)
            const [model, performance, history] = await Promise.all([
                getModel(),
                getModelPerformance(siteId, start),
                getPredictions(siteId, start),
            ])
            // 404 quand aucune prévision n'existe encore pour ce site.
            const prediction = await getLatestPrediction(siteId).catch(() => null)
            setData({ model, performance, prediction, history })
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de charger le modèle.')
        } finally {
            setIsLoading(false)
        }
    }, [period, siteId])

    useEffect(() => {
        void load()
    }, [load])

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

            {data && (
                <>
                    <article className="prediction-highlight">
                        <p>Prochaine prévision de consommation</p>
                        <strong>{formatEnergy(data.prediction?.predicted_kwh)}</strong>
                        <span>
                            {data.prediction
                                ? `Attendue pour ${formatDateTime(data.prediction.target_at)}, horizon ${data.model.horizon_minutes} minutes`
                                : 'Aucune prévision disponible pour ce site'}
                        </span>
                    </article>

                    <section className="card-grid">
                        <MetricCard label="Modèle" value={data.model.model_version} hint={data.model.model_name} dot="blue" />
                        <MetricCard
                            label="Disponibilité"
                            value={availabilityLabels[data.model.availability]}
                            hint={`MLflow ${data.model.mlflow_available ? 'joignable' : 'injoignable'}`}
                            dot="teal"
                        />
                        <MetricCard
                            label="Entraîné le"
                            value={formatDateTime(data.model.trained_at)}
                            hint={`Horizon ${data.model.horizon_minutes} minutes`}
                            dot="green"
                        />
                        <MetricCard label="Prévisions évaluées" value={data.performance.sample_size} dot="green" />
                    </section>

                    <article className="table-card">
                        <div className="card-heading">
                            <div>
                                <h2>Qualité des prévisions</h2>
                            </div>
                        </div>
                        {data.performance.sample_size
                            ? (
                                <div className="table-scroll">
                                    <table>
                                        <thead>
                                            <tr><th>Méthode</th><th>MAE</th><th>RMSE</th><th>MAPE</th></tr>
                                        </thead>
                                        <tbody>
                                            <MetricRow label="Modèle" metric={data.performance.model} />
                                            <MetricRow label="Persistance" metric={data.performance.persistence_baseline} />
                                            <MetricRow label="Régression linéaire" metric={data.performance.linear_baseline} />
                                        </tbody>
                                    </table>
                                </div>
                            )
                            : <p className="empty-state">Aucune prévision évaluable sur la période.</p>}
                    </article>

                    <article className="table-card">
                        <div className="card-heading">
                            <div><h2>Prévisions produites</h2></div>
                            <span>{data.history.length} prévision{data.history.length > 1 ? 's' : ''}</span>
                        </div>
                        <DataTable
                            columns={columns}
                            rows={data.history}
                            rowKey={(row) => row.target_at}
                            emptyLabel="Aucune prévision sur la période."
                        />
                    </article>
                </>
            )}
        </>
    )
}
