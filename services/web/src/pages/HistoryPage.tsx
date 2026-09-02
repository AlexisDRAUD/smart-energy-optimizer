import { useCallback, useEffect, useMemo, useState } from 'react'
import { getReadings } from '../api/readings'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { periodOptions } from '../data/dashboard'
import { useSiteSelection } from '../hooks/useSiteSelection'
import type { ApiReading } from '../types/api'
import { formatDateTime, formatEnergy, formatQuality, getReadingValue } from '../utils/formatters'

type DailyReading = { date: string; consumption: number | null; dataQuality: ApiReading['data_quality'] }

function groupByDay(readings: ApiReading[]): DailyReading[] {
    const grouped = new Map<string, ApiReading[]>()
    readings.forEach((reading) => {
        const key = reading.recorded_at.slice(0, 10)
        grouped.set(key, [...(grouped.get(key) ?? []), reading])
    })
    return [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([date, dailyReadings]) => {
        const values = dailyReadings.map(getReadingValue).filter((value): value is number => value !== null)
        const latest = dailyReadings[0]
        return { date, consumption: values.length ? values.reduce((total, value) => total + value, 0) : null, dataQuality: latest.data_quality }
    })
}

export function HistoryPage() {
    const { sites, siteId, setSiteId, error: sitesError, isLoading: sitesLoading, reload: reloadSites } = useSiteSelection()
    const [period, setPeriod] = useState(periodOptions[0])
    const [readings, setReadings] = useState<ApiReading[]>([])
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)

    const load = useCallback(async () => {
        if (siteId === null) return
        setIsLoading(true)
        setError(null)
        try {
            setReadings(await getReadings({ siteId }))
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de charger l’historique.')
        } finally {
            setIsLoading(false)
        }
    }, [siteId])

    useEffect(() => {
        void load()
    }, [load])

    const dailyReadings = useMemo(() => groupByDay(readings), [readings])
    const values = dailyReadings.map(({ consumption }) => consumption).filter((value): value is number => value !== null)
    const total = values.reduce((sum, value) => sum + value, 0)
    const max = Math.max(...values, 1)

    return (
        <>
            <DashboardFilters sites={sites} siteId={siteId} period={period} onSiteChange={setSiteId} onPeriodChange={setPeriod} onRefresh={load} />
            <PageFeedback isLoading={sitesLoading || isLoading} error={sitesError ?? error} onRetry={() => { void reloadSites(); void load() }} />
            <section className="history-summary-grid"><article className="metric-card"><p><span className="metric-dot blue" /> Consommation cumulée</p><strong>{formatEnergy(total)}</strong><small>Somme des relevés disponibles</small></article><article className="metric-card"><p><span className="metric-dot teal" /> Relevés reçus</p><strong>{readings.length}</strong><small>Données brutes et imputées conservées</small></article><article className="metric-card"><p><span className="metric-dot orange" /> Données dégradées</p><strong>{readings.filter((reading) => reading.data_quality !== 'good').length}</strong><small>À contrôler selon leur niveau de qualité</small></article></section>
            <article className="chart-card history-chart-card"><div className="card-heading"><div><h2>Consommation historique</h2><p>Somme quotidienne des relevés issus de l’API.</p></div></div><svg className="history-chart" viewBox="0 0 800 310" role="img" aria-label="Historique quotidien de consommation"><g className="grid-lines">{[0, 1, 2, 3].map((index) => <line key={index} x1="54" x2="770" y1={42 + index * 64} y2={42 + index * 64} />)}</g>{dailyReadings.map(({ date, consumption }, index) => { const x = 92 + index * (640 / Math.max(dailyReadings.length - 1, 1)); const height = consumption === null ? 0 : consumption / max * 190; return <g className="history-bars" key={date}><rect className="history-real-bar" x={x} y={234 - height} width="42" height={height} rx="5" /><text x={x + 21} y="266" textAnchor="middle">{new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short' }).format(new Date(`${date}T00:00:00Z`))}</text></g> })}</svg></article>
            <article className="history-table-card"><div className="sites-heading"><div><h2>Détail des relevés</h2><p>Les valeurs brutes nulles sont affichées sans être masquées.</p></div></div><div className="table-scroll"><table><thead><tr><th>Date</th><th>Valeur brute</th><th>Valeur imputée</th><th>Qualité</th><th>Source</th></tr></thead><tbody>{readings.map((reading) => <tr key={reading.id}><td>{formatDateTime(reading.recorded_at)}</td><td>{formatEnergy(reading.consumption_kwh_raw)}</td><td>{formatEnergy(reading.consumption_kwh_imputed)}</td><td>{formatQuality(reading.data_quality)}</td><td>{reading.source}</td></tr>)}</tbody></table></div></article>
        </>
    )
}
