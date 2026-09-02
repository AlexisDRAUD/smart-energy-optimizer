import { useCallback, useEffect, useState } from 'react'
import { getNextPrediction } from '../api/predictions'
import { getCurrentReading } from '../api/sites'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { periodOptions } from '../data/dashboard'
import { useSiteSelection } from '../hooks/useSiteSelection'
import type { ApiPrediction, ApiReading } from '../types/api'
import { formatDateTime, formatEnergy, getReadingValue } from '../utils/formatters'

export function PredictionsPage() {
    const { sites, siteId, setSiteId, error: sitesError, isLoading: sitesLoading, reload: reloadSites } = useSiteSelection()
    const [period, setPeriod] = useState(periodOptions[0])
    const [prediction, setPrediction] = useState<ApiPrediction | null>(null)
    const [currentReading, setCurrentReading] = useState<ApiReading | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)

    const load = useCallback(async () => {
        if (siteId === null) return
        setIsLoading(true)
        setError(null)
        try {
            const [nextPrediction, reading] = await Promise.all([getNextPrediction(siteId), getCurrentReading(siteId)])
            setPrediction(nextPrediction)
            setCurrentReading(reading)
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de calculer la prévision.')
        } finally {
            setIsLoading(false)
        }
    }, [siteId])

    useEffect(() => {
        void load()
    }, [load])

    const currentValue = currentReading ? getReadingValue(currentReading) : null
    const predictionValue = prediction?.consumption_kwh_raw ?? null
    const difference = predictionValue !== null && currentValue !== null ? predictionValue - currentValue : null

    return (
        <>
            <DashboardFilters sites={sites} siteId={siteId} period={period} onSiteChange={setSiteId} onPeriodChange={setPeriod} onRefresh={load} />
            <PageFeedback isLoading={sitesLoading || isLoading} error={sitesError ?? error} onRetry={() => { void reloadSites(); void load() }} />
            {prediction && <section className="prediction-content"><article className="prediction-highlight"><p>Prévision de consommation H+2</p><strong>{formatEnergy(predictionValue)}</strong><span>Prévision générée pour {formatDateTime(prediction.recorded_at)}</span></article><section className="alert-summary-grid"><article className="metric-card"><p><span className="metric-dot blue" /> Dernière consommation</p><strong>{formatEnergy(currentValue)}</strong><small>{currentReading && formatDateTime(currentReading.recorded_at)}</small></article><article className="metric-card"><p><span className="metric-dot teal" /> Évolution prévue</p><strong>{difference === null ? '—' : `${difference > 0 ? '+' : ''}${formatEnergy(difference)}`}</strong><small>Par rapport au dernier relevé</small></article><article className="metric-card"><p><span className="metric-dot green" /> Qualité de la donnée</p><strong>Prédite</strong><small>Source : {prediction.source}</small></article></section></section>}
        </>
    )
}
