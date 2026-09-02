import { useCallback, useEffect, useState } from 'react'
import { getAlerts } from '../api/alerts'
import { getNextPrediction } from '../api/predictions'
import { getReadings } from '../api/readings'
import { getCurrentReading } from '../api/sites'
import { getSummary } from '../api/stats'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { PageFeedback } from '../components/common/PageFeedback'
import { periodOptions } from '../data/dashboard'
import { useSiteSelection } from '../hooks/useSiteSelection'
import type { ApiAlert, ApiPrediction, ApiReading, ApiSummary } from '../types/api'
import { formatDateTime, formatEnergy, getReadingValue } from '../utils/formatters'

type DashboardData = {
    summary: ApiSummary
    alerts: ApiAlert[]
    currentReading: ApiReading
    prediction: ApiPrediction
    readings: ApiReading[]
    currentReadings: Map<number, ApiReading>
}

export function DashboardPage() {
    const { sites, siteId, setSiteId, error: sitesError, isLoading: sitesLoading, reload: reloadSites } = useSiteSelection()
    const [period, setPeriod] = useState(periodOptions[0])
    const [data, setData] = useState<DashboardData | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)

    const load = useCallback(async () => {
        if (siteId === null || !sites.length) return
        setIsLoading(true)
        setError(null)
        try {
            const [summary, alerts, currentReading, prediction, readings, allCurrentReadings] = await Promise.all([
                getSummary(),
                getAlerts(),
                getCurrentReading(siteId),
                getNextPrediction(siteId),
                getReadings({ siteId }),
                Promise.all(sites.map(async (site) => [site.id, await getCurrentReading(site.id)] as const)),
            ])
            setData({ summary, alerts, currentReading, prediction, readings, currentReadings: new Map(allCurrentReadings) })
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de charger le tableau de bord.')
        } finally {
            setIsLoading(false)
        }
    }, [siteId, sites])

    useEffect(() => {
        void load()
    }, [load])

    const refresh = async () => {
        await reloadSites()
        await load()
    }

    const selectedSite = sites.find((site) => site.id === siteId)
    const currentValue = data ? getReadingValue(data.currentReading) : null
    const predictionValue = data?.prediction.consumption_kwh_raw ?? null
    const deviation = data && currentValue !== null && predictionValue !== null ? (currentValue - predictionValue) / predictionValue * 100 : null
    const chartReadings = (data?.readings ?? []).slice().sort((left, right) => new Date(left.recorded_at).getTime() - new Date(right.recorded_at).getTime())
    const realReadings = chartReadings.filter((reading) => reading.source !== 'prediction')
    const persistedPredictions = chartReadings.filter((reading) => reading.source === 'prediction')
    const chartValues = chartReadings.map((reading) => getReadingValue(reading)).filter((value): value is number => value !== null)
    const chartMin = Math.floor(Math.min(...chartValues, 0) / 50) * 50
    const chartMax = Math.ceil(Math.max(...chartValues, 1) / 50) * 50
    const chartRange = Math.max(chartMax - chartMin, 1)
    const plotBottom = 246
    const plotHeight = 190
    const timelineStart = chartReadings[0] ? new Date(chartReadings[0].recorded_at).getTime() : 0
    const timelineEnd = chartReadings[chartReadings.length - 1] ? new Date(chartReadings[chartReadings.length - 1].recorded_at).getTime() : timelineStart + 1
    const timelineRange = Math.max(timelineEnd - timelineStart, 1)
    const pointAt = (reading: ApiReading) => {
        const value = getReadingValue(reading) ?? chartMin
        const timestamp = new Date(reading.recorded_at).getTime()
        const x = 58 + (timestamp - timelineStart) / timelineRange * 720
        const y = plotBottom - (value - chartMin) / chartRange * plotHeight
        return { x, y }
    }
    const realPoints = realReadings.map(pointAt)
    const predictionPoints = persistedPredictions.map(pointAt)
    const lastRealPoint = realPoints[realPoints.length - 1]
    const realLinePoints = realPoints.map(({ x, y }) => `${x},${y}`).join(' ')
    const predictionLinePoints = lastRealPoint ? [lastRealPoint, ...predictionPoints].map(({ x, y }) => `${x},${y}`).join(' ') : ''
    const timeTicks = Array.from({ length: 7 }, (_, index) => {
        const timestamp = timelineStart + timelineRange * index / 6
        return { x: 58 + 720 * index / 6, label: new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(new Date(timestamp)) }
    })
    const deviationPrefix = deviation !== null && deviation > 0 ? '+' : ''
    const deviationLabel = deviation === null ? '—' : `${deviationPrefix}${deviation.toFixed(1).replace('.', ',')} %`

    return (
        <>
            <DashboardFilters sites={sites} siteId={siteId} period={period} onSiteChange={setSiteId} onPeriodChange={setPeriod} onRefresh={refresh} />
            <PageFeedback isLoading={sitesLoading || isLoading} error={sitesError ?? error} onRetry={() => { void reloadSites(); void load() }} />
            {data && selectedSite && (
                <>
                    <section className="metrics-grid">
                        <article className="metric-card"><p><span className="metric-dot blue" /> Consommation actuelle</p><strong>{formatEnergy(currentValue)}</strong><small>{formatDateTime(data.currentReading.recorded_at)}</small></article>
                        <article className="metric-card"><p><span className="metric-dot teal" /> Prédiction actuelle <em>H+2</em></p><strong>{formatEnergy(predictionValue)}</strong><small>Prévision pour {formatDateTime(data.prediction.recorded_at)}</small></article>
                        <article className="metric-card"><p><span className="metric-dot orange" /> Écart modèle / réel</p><strong>{deviationLabel}</strong><small>Seuil d’alerte configurable à 15 %</small></article>
                        <article className="metric-card"><p><span className="metric-dot green" /> État du parc</p><strong>{data.summary.site_count} sites</strong><small>{data.summary.active_alert_count} alerte{data.summary.active_alert_count > 1 ? 's' : ''} active{data.summary.active_alert_count > 1 ? 's' : ''}</small></article>
                    </section>
                    <section className="analysis-grid">
                        <article className="chart-card">
                            <div className="card-heading"><div><h2>Consommation réelle et prédite</h2><p>24 h de mesures et 2 h de prévisions pour {selectedSite.name}</p></div><div className="legend"><span><i className="solid-line" /> Réel</span><span><i className="dashed-line" /> Prédiction</span></div></div>
                            <div className="chart-wrap"><svg className="consumption-chart" viewBox="0 0 820 330" role="img" aria-label="Courbe de consommation réelle et prédite sur 26 heures"><g className="grid-lines">{[0, 1, 2, 3].map((index) => <line x1="52" x2="790" y1={56 + index * (plotHeight / 3)} y2={56 + index * (plotHeight / 3)} key={index} />)}</g><g className="axis-labels">{[0, 1, 2, 3].map((index) => <text x="42" y={250 - index * (plotHeight / 3)} textAnchor="end" key={index}>{Math.round(chartMin + chartRange * index / 3)}</text>)}</g>{lastRealPoint && <><line className="now-line" x1={lastRealPoint.x} x2={lastRealPoint.x} y1="42" y2={plotBottom} /><rect className="now-label" x={lastRealPoint.x - 52} y="16" width="104" height="24" rx="12" /><text className="now-text" x={lastRealPoint.x} y="32" textAnchor="middle">MAINTENANT</text></>}{realLinePoints && <polyline className="real-line" points={realLinePoints} />}{predictionLinePoints && <polyline className="prediction-line" points={predictionLinePoints} />}<g className="real-points">{lastRealPoint && <circle cx={lastRealPoint.x} cy={lastRealPoint.y} r="4" />}</g>{predictionPoints.length > 0 && <g className="prediction-points"><circle cx={predictionPoints[predictionPoints.length - 1].x} cy={predictionPoints[predictionPoints.length - 1].y} r="4" /></g>}<g className="axis-labels">{timeTicks.map(({ x, label }) => <text x={x} y="278" textAnchor="middle" key={label}>{label}</text>)}</g></svg></div>
                        </article>
                        <div className="right-column">
                            <article className="side-card alerts-card"><h2>État des alertes</h2><div className="alert-totals"><span>{data.alerts.filter((alert) => alert.severity === 'critical').length} Critique</span><span>{data.alerts.filter((alert) => alert.severity === 'warning').length} À surveiller</span></div>{data.alerts.slice(0, 2).map((alert) => <div className="alert-item" key={alert.id}><span className={`metric-dot ${alert.severity === 'critical' ? 'red' : 'orange'}`} /><div><strong>{alert.message}</strong><small>{formatDateTime(alert.triggered_at)}</small></div></div>)}</article>
                            <article className="side-card recommendations-card"><h2>Recommandations</h2><div className="recommendation"><b>01</b><div><strong>Contrôler les alertes actives</strong><p>Traitez en priorité les écarts de consommation signalés.</p></div></div><div className="recommendation"><b>02</b><div><strong>Vérifier la qualité des données</strong><p>Les relevés dégradés restent identifiables dans l’historique.</p></div></div></article>
                        </div>
                    </section>
                    <section className="sites-card"><div className="sites-heading"><h2>Vue multi-sites</h2><span>{data.summary.reading_count} relevés enregistrés</span></div><div className="table-scroll"><table><thead><tr><th>Site</th><th>Ville</th><th>Dernière consommation</th><th>Qualité</th><th>Dernière donnée</th></tr></thead><tbody>{sites.map((site) => { const reading = data.currentReadings.get(site.id); return <tr key={site.id}><td>{site.name}</td><td>{site.city}</td><td>{formatEnergy(reading ? getReadingValue(reading) : null)}</td><td>{reading?.data_quality ?? '—'}</td><td>{reading ? formatDateTime(reading.recorded_at) : '—'}</td></tr> })}</tbody></table></div></section>
                </>
            )}
        </>
    )
}
