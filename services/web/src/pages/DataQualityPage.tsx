import { useCallback, useEffect, useMemo, useState } from 'react'
import { getReadings } from '../api/readings'
import { PageFeedback } from '../components/common/PageFeedback'
import type { ApiReading } from '../types/api'
import { formatDateTime, formatEnergy, formatQuality } from '../utils/formatters'

export function DataQualityPage() {
    const [readings, setReadings] = useState<ApiReading[]>([])
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    const load = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            setReadings(await getReadings())
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de charger la qualité des données.')
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        void load()
    }, [load])

    const qualityCounts = useMemo(() => readings.reduce<Record<string, number>>((counts, reading) => ({ ...counts, [reading.data_quality]: (counts[reading.data_quality] ?? 0) + 1 }), {}), [readings])

    return (
        <>
            <PageFeedback isLoading={isLoading} error={error} onRetry={() => { void load() }} />
            <section className="quality-summary-grid"><article className="metric-card"><p><span className="metric-dot green" /> Données bonnes</p><strong>{qualityCounts.good ?? 0}</strong><small>Relevés de qualité optimale</small></article><article className="metric-card"><p><span className="metric-dot orange" /> Données à contrôler</p><strong>{(qualityCounts.partial ?? 0) + (qualityCounts.degraded ?? 0)}</strong><small>Relevés partiels ou dégradés</small></article><article className="metric-card"><p><span className="metric-dot red" /> Données critiques</p><strong>{qualityCounts.critical ?? 0}</strong><small>Intervention requise</small></article></section>
            <article className="history-table-card"><div className="sites-heading"><div><h2>Qualité des relevés</h2><p>Les valeurs brutes nulles sont conservées et identifiées avec leur cause.</p></div><span>{readings.length} relevés</span></div><div className="table-scroll"><table><thead><tr><th>Date</th><th>Site</th><th>Valeur brute</th><th>Valeur imputée</th><th>Qualité</th><th>Motif de donnée nulle</th></tr></thead><tbody>{readings.map((reading) => <tr key={reading.id}><td>{formatDateTime(reading.recorded_at)}</td><td>#{reading.site_id}</td><td>{formatEnergy(reading.consumption_kwh_raw)}</td><td>{formatEnergy(reading.consumption_kwh_imputed)}</td><td>{formatQuality(reading.data_quality)}</td><td>{reading.null_reasons?.join(', ') ?? '—'}</td></tr>)}</tbody></table></div></article>
        </>
    )
}
