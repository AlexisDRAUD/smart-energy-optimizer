import { useCallback } from 'react'
import { ApiError } from '../api/client'
import { getLatestPrediction, getModel, getModelPerformance, getPredictions } from '../api/predictions'
import { DataTable, type Column } from '../components/common/DataTable'
import { MetricCard } from '../components/common/MetricCard'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { periodStart } from '../data/periods'
import { useFilters } from '../hooks/useFilters'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import type { ApiMetric, ApiModel, ApiModelPerformance, ApiPrediction } from '../types/api'
import { formatDateTime, formatEnergy, formatNumber, formatPercent } from '../utils/formatters'

type ModelData = {
    model: ApiModel
    performance: ApiModelPerformance
    prediction: ApiPrediction | null
    history: ApiPrediction[]
}

const columns: Column<ApiPrediction>[] = [
    { header: 'Prévue pour', cell: (row) => formatDateTime(row.target_at) },
    { header: 'Calculée le', cell: (row) => formatDateTime(row.predicted_at) },
    { header: 'Horizon', cell: (row) => `${row.horizon_minutes} min` },
    { header: 'Prévision', cell: (row) => formatEnergy(row.predicted_kwh) },
    { header: 'Réalisé', cell: (row) => formatEnergy(row.actual_kwh) },
    { header: 'Erreur absolue', cell: (row) => formatNumber(row.absolute_error) },
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
    const fetchPredictions = useCallback(async (signal: AbortSignal): Promise<ModelData> => {
        if (siteId === null) throw new Error('Aucun site sélectionné.')
        const start = periodStart(period)
        const latestRequest = getLatestPrediction(siteId, signal).catch((cause: unknown) => {
            if (cause instanceof ApiError && cause.status === 404) return null
            throw cause
        })
        const [model, performance, history, prediction] = await Promise.all([
            getModel(siteId, signal),
            getModelPerformance(siteId, start, signal),
            getPredictions(siteId, start, 500, signal),
            latestRequest,
        ])
        return { model, performance, prediction, history }
    }, [period, siteId])
    const { data, error, isInitialLoading, isSyncing, lastSyncedAt, refresh } = useAutoRefresh({
        enabled: siteId !== null,
        key: `${siteId ?? 'none'}:${period}`,
        load: fetchPredictions,
        errorMessage: 'Impossible de charger le modèle.',
    })

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

            {data && (
                <>
                    <article className="prediction-highlight">
                        <p>Prochaine prévision de consommation</p>
                        <strong>{formatEnergy(data.prediction?.predicted_kwh)}</strong>
                        <span>
                            {data.prediction
                                ? `Attendue pour ${formatDateTime(data.prediction.target_at)}, horizon ${data.prediction.horizon_minutes} minutes`
                                : 'Aucune prévision disponible pour ce site'}
                        </span>
                    </article>

                    <section className="card-grid">
                        <MetricCard
                            label="Modèle"
                            value={data.model.model_version ?? '—'}
                            hint={data.model.model_name ?? undefined}
                            dot="blue"
                        />
                        <MetricCard
                            label="Horizon"
                            value={data.model.horizon_minutes === null ? '—' : `${data.model.horizon_minutes} minutes`}
                            dot="teal"
                        />
                        <MetricCard
                            label="Dernière prévision"
                            value={formatDateTime(data.model.last_prediction_at)}
                            hint={`${data.model.predictions_total} produites, dont ${data.model.predictions_scored} évaluées`}
                            dot="green"
                        />
                        <MetricCard label="Évaluées sur la période" value={data.performance.sample_size} dot="orange" />
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
                            <div>
                                <h2>Prévisions produites</h2>
                                <p>{data.model.model_name ?? 'modèle inconnu'}{data.model.model_version ? ` · version ${data.model.model_version}` : ''} · lignes de la table des prévisions pour ce site</p>
                            </div>
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
