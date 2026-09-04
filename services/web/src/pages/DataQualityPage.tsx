import { useCallback, useEffect, useState } from 'react'
import { getQuality, getSensorStatus } from '../api/dashboard'
import { DataTable, type Column } from '../components/common/DataTable'
import { MetricCard } from '../components/common/MetricCard'
import { PageFeedback } from '../components/common/PageFeedback'
import { DashboardFilters } from '../components/dashboard/DashboardFilters'
import { periodStart } from '../data/periods'
import { useFilters } from '../hooks/useFilters'
import type { ApiQuality, ApiQualityPoint, ApiSensorSite } from '../types/api'
import { formatDateTime, formatDay, formatPercent } from '../utils/formatters'

const sensorLabels = {
    consumption: 'Consommation',
    electrical: 'Électrique',
    temperature: 'Température',
    humidity: 'Humidité',
    network: 'Réseau',
}

const columns: Column<ApiQualityPoint>[] = [
    { header: 'Jour', cell: (point) => formatDay(point.day) },
    { header: 'Attendus', cell: (point) => point.expected_points },
    { header: 'Reçus', cell: (point) => point.received_points },
    { header: 'Manquants', cell: (point) => point.missing_points },
    { header: 'Nuls', cell: (point) => point.null_points },
    { header: 'Imputés', cell: (point) => point.imputed_points },
    { header: 'Calculé le', cell: (point) => formatDateTime(point.computed_at) },
]

/** Somme d'une colonne sur toute la période. */
function sum(points: ApiQualityPoint[], field: keyof ApiQualityPoint) {
    return points.reduce((total, point) => total + Number(point[field]), 0)
}

export function DataQualityPage() {
    const { sites, siteId, setSiteId, period, setPeriod, error: sitesError, isLoading: sitesLoading, reload: reloadSites } = useFilters()
    const [quality, setQuality] = useState<ApiQuality | null>(null)
    const [sensors, setSensors] = useState<ApiSensorSite | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)

    const load = useCallback(async () => {
        if (siteId === null) return
        setIsLoading(true)
        setError(null)
        try {
            const [qualityData, sensorSites] = await Promise.all([
                getQuality(siteId, periodStart(period)),
                getSensorStatus(siteId),
            ])
            setQuality(qualityData)
            setSensors(sensorSites[0] ?? null)
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de charger la qualité des données.')
        } finally {
            setIsLoading(false)
        }
    }, [period, siteId])

    useEffect(() => {
        void load()
    }, [load])

    const points = quality?.points ?? []
    const expected = sum(points, 'expected_points')
    const received = sum(points, 'received_points')
    const completeness = expected ? received / expected * 100 : null

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
                <MetricCard label="Complétude" value={formatPercent(completeness)} hint={`${received} relevés reçus sur ${expected} attendus`} dot="green" />
                <MetricCard label="Relevés manquants" value={sum(points, 'missing_points')} dot="red" />
                <MetricCard label="Valeurs nulles" value={sum(points, 'null_points')} dot="orange" />
                <MetricCard label="Valeurs imputées" value={sum(points, 'imputed_points')} dot="teal" />
            </section>

            <article className="table-card">
                <div className="card-heading">
                    <div>
                        <h2>État des capteurs</h2>
                    </div>
                    <span>{sensors ? (sensors.overall === 'ok' ? 'Tous opérationnels' : 'Au moins un capteur en défaut') : '—'}</span>
                </div>
                {sensors
                    ? (
                        <div className="sensor-grid">
                            {sensors.sensors.map((sensor) => (
                                <div className="sensor-item" key={sensor.sensor}>
                                    <span className={`metric-dot ${sensor.status === 'ok' ? 'green' : 'red'}`} />
                                    <div>
                                        <strong>{sensorLabels[sensor.sensor]}</strong>
                                        <p>{sensor.status === 'ok' ? 'Opérationnel' : 'En défaut'}</p>
                                        <small>{formatDateTime(sensor.observed_at)}</small>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )
                    : <p className="empty-state">Aucune information capteur pour ce site.</p>}
            </article>

            <article className="table-card">
                <div className="card-heading">
                    <div>
                        <h2>Complétude jour par jour</h2>
                    </div>
                    <span>{points.length} jour{points.length > 1 ? 's' : ''}</span>
                </div>
                <DataTable columns={columns} rows={points} rowKey={(point) => point.day} emptyLabel="Aucune donnée de qualité sur la période." />
            </article>
        </>
    )
}
