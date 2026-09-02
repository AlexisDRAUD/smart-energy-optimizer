import { useCallback, useEffect, useState } from 'react'
import { getCurrentReading } from '../api/sites'
import { PageFeedback } from '../components/common/PageFeedback'
import { useSites } from '../hooks/useSites'
import type { ApiReading } from '../types/api'
import { formatDateTime, formatEnergy, formatQuality, getReadingValue } from '../utils/formatters'

export function SitesPage() {
    const { sites, error, isLoading, reload } = useSites()
    const [readings, setReadings] = useState<Map<number, ApiReading>>(new Map())
    const [readingsError, setReadingsError] = useState<string | null>(null)

    const loadCurrentReadings = useCallback(async () => {
        if (!sites.length) return
        setReadingsError(null)
        try {
            const currentReadings = await Promise.all(sites.map(async (site) => [site.id, await getCurrentReading(site.id)] as const))
            setReadings(new Map(currentReadings))
        } catch (cause) {
            setReadingsError(cause instanceof Error ? cause.message : 'Impossible de charger les derniers relevés.')
        }
    }, [sites])

    useEffect(() => {
        void loadCurrentReadings()
    }, [loadCurrentReadings])

    return (
        <>
            <PageFeedback isLoading={isLoading} error={error ?? readingsError} onRetry={() => { void reload(); void loadCurrentReadings() }} />
            <section className="sites-card sites-page-card"><div className="sites-heading"><div><h2>Sites connectés</h2><p>Informations et dernier relevé remontés par l’API.</p></div><span>{sites.length} site{sites.length > 1 ? 's' : ''}</span></div><div className="table-scroll"><table><thead><tr><th>Site</th><th>Code</th><th>Localisation</th><th>Puissance souscrite</th><th>Dernière consommation</th><th>Qualité</th><th>Dernière donnée</th></tr></thead><tbody>{sites.map((site) => { const reading = readings.get(site.id); return <tr key={site.id}><td>{site.name}</td><td>{site.code}</td><td>{site.city}, {site.country}</td><td>{site.subscribed_power_kw} kW</td><td>{formatEnergy(reading ? getReadingValue(reading) : null)}</td><td>{reading ? formatQuality(reading.data_quality) : '—'}</td><td>{reading ? formatDateTime(reading.recorded_at) : '—'}</td></tr> })}</tbody></table></div></section>
        </>
    )
}
