import { useCallback, useEffect, useMemo, useState } from 'react'
import { getReadings } from '../api/readings'
import { DataTable, type Column } from '../components/common/DataTable'
import { MetricCard } from '../components/common/MetricCard'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { periodGranularity, periodStart } from '../data/periods'
import { useFilters } from '../hooks/useFilters'
import type { ApiReadingPoint, ApiReadings } from '../types/api'
import { formatDateTime, formatDay, formatEnergy, formatPercent, formatQuality } from '../utils/formatters'

type DailyTotal = { day: string; consumption: number }

/** Somme des relevés de chaque journée, dans l'ordre chronologique. */
function totalByDay(points: ApiReadingPoint[]): DailyTotal[] {
    const totals = new Map<string, number>()
    points.forEach((point) => {
        if (point.consumption_kwh === null) return
        const day = point.measured_at.slice(0, 10)
        totals.set(day, (totals.get(day) ?? 0) + point.consumption_kwh)
    })
    return [...totals.entries()]
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([day, consumption]) => ({ day, consumption }))
}

const columns: Column<ApiReadingPoint>[] = [
    { header: 'Date', cell: (point) => formatDateTime(point.measured_at) },
    { header: 'Consommation', cell: (point) => formatEnergy(point.consumption_kwh) },
    { header: 'Imputée', cell: (point) => (point.is_imputed ? 'Oui' : 'Non') },
    { header: 'Qualité', cell: (point) => formatQuality(point.data_quality) },
]

export function HistoryPage() {
    const { sites, siteId, setSiteId, period, setPeriod, error: sitesError, isLoading: sitesLoading, reload: reloadSites } = useFilters()
    const [readings, setReadings] = useState<ApiReadings | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)

    const load = useCallback(async () => {
        if (siteId === null) return
        setIsLoading(true)
        setError(null)
        try {
            setReadings(await getReadings({ siteId, start: periodStart(period), granularity: periodGranularity(period) }))
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de charger l’historique.')
        } finally {
            setIsLoading(false)
        }
    }, [period, siteId])

    useEffect(() => {
        void load()
    }, [load])

    const points = useMemo(() => readings?.points ?? [], [readings])
    const dailyTotals = useMemo(() => totalByDay(points), [points])
    const total = dailyTotals.reduce((sum, { consumption }) => sum + consumption, 0)
    const highest = Math.max(...dailyTotals.map(({ consumption }) => consumption), 1)

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
                <MetricCard label="Consommation cumulée" value={formatEnergy(total)} dot="blue" />
                <MetricCard label="Relevés reçus" value={readings?.completeness.received_points ?? 0} hint={`Sur ${readings?.completeness.expected_points ?? 0} attendus`} dot="teal" />
                <MetricCard label="Complétude" value={formatPercent(readings?.completeness.percent)} hint={`${readings?.completeness.missing_points ?? 0} relevés manquants`} dot="green" />
                <MetricCard label="Relevés imputés" value={readings?.completeness.imputed_points ?? 0} dot="orange" />
            </section>

            <article className="chart-card">
                <div className="card-heading">
                    <div>
                        <h2>Consommation historique</h2>
                    </div>
                </div>
                {dailyTotals.length
                    ? (
                        <svg className="history-chart" viewBox="0 0 800 310" role="img" aria-label="Historique quotidien de consommation">
                            <g className="grid-lines">
                                {[0, 1, 2, 3].map((index) => (
                                    <line key={index} x1="54" x2="770" y1={42 + index * 64} y2={42 + index * 64} />
                                ))}
                            </g>
                            {dailyTotals.map(({ day, consumption }, index) => {
                                const x = 92 + index * (640 / Math.max(dailyTotals.length, 1))
                                const width = Math.min(42, 640 / dailyTotals.length - 8)
                                const height = consumption / highest * 190
                                return (
                                    <g className="history-bars" key={day}>
                                        <title>{`${formatDay(day)} : ${formatEnergy(consumption)}`}</title>
                                        <rect className="history-real-bar" x={x} y={234 - height} width={width} height={height} rx="5" />
                                        <text x={x + width / 2} y="266" textAnchor="middle">{formatDay(day)}</text>
                                    </g>
                                )
                            })}
                        </svg>
                    )
                    : <p className="empty-state">Aucun relevé sur la période.</p>}
            </article>

            <article className="table-card">
                <div className="card-heading">
                    <div>
                        <h2>Détail des relevés</h2>
                    </div>
                    <span>{points.length} relevés</span>
                </div>
                <DataTable columns={columns} rows={points} rowKey={(point) => point.measured_at} emptyLabel="Aucun relevé sur la période." />
            </article>
        </>
    )
}
