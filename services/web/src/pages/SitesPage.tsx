import { useCallback, useEffect, useState } from 'react'
import { getOverview } from '../api/dashboard'
import { DataTable, type Column } from '../components/common/DataTable'
import { PageFeedback } from '../components/common/PageFeedback'
import { useSites } from '../hooks/useSites'
import type { ApiOverview, ApiSite } from '../types/api'
import { formatDateTime, formatPercent, formatPower } from '../utils/formatters'

export function SitesPage() {
    const { sites, error, isLoading, reload } = useSites()
    const [overview, setOverview] = useState<ApiOverview | null>(null)
    const [overviewError, setOverviewError] = useState<string | null>(null)

    // Un seul appel donne la consommation de tous les sites, au lieu d'un
    // appel /latest par site.
    const loadOverview = useCallback(async () => {
        setOverviewError(null)
        try {
            setOverview(await getOverview())
        } catch (cause) {
            setOverviewError(cause instanceof Error ? cause.message : 'Impossible de charger les consommations.')
        }
    }, [])

    useEffect(() => {
        void loadOverview()
    }, [loadOverview])

    const measureOf = (siteId: string) => overview?.by_site.find((row) => row.site_id === siteId)

    const columns: Column<ApiSite>[] = [
        { header: 'Site', cell: (site) => site.site_name },
        { header: 'Identifiant', cell: (site) => site.site_id },
        { header: 'Type', cell: (site) => site.site_type },
        { header: 'Localisation', cell: (site) => site.location },
        { header: 'Puissance souscrite', cell: (site) => formatPower(site.capacity_kw) },
        { header: 'État', cell: (site) => (site.status === 'active' ? 'Actif' : 'Inactif') },
        { header: 'Consommation', cell: (site) => formatPower(measureOf(site.site_id)?.consumption_kw) },
        { header: 'Taux de charge', cell: (site) => formatPercent(measureOf(site.site_id)?.load_rate_percent) },
        { header: 'Dernière donnée', cell: (site) => formatDateTime(site.last_seen_at) },
    ]

    return (
        <>
            <PageFeedback
                isLoading={isLoading}
                error={error ?? overviewError}
                onRetry={() => { void reload(); void loadOverview() }}
            />
            <article className="table-card">
                <div className="card-heading">
                    <div>
                        <h2>Sites connectés</h2>
                    </div>
                    <span>{sites.length} site{sites.length > 1 ? 's' : ''}</span>
                </div>
                <DataTable columns={columns} rows={sites} rowKey={(site) => site.site_id} emptyLabel="Aucun site connecté." />
            </article>
        </>
    )
}
