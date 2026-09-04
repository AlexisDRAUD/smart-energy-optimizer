import { Icon } from '../common/Icon'
import { Select } from '../common/Select'
import { periods, type Period } from '../../data/periods'
import type { ApiSite } from '../../types/api'

type DashboardFiltersProps = {
    sites: ApiSite[]
    siteId: string | null
    onSiteChange: (siteId: string) => void
    onRefresh: () => void | Promise<void>
    period?: Period
    onPeriodChange?: (period: Period) => void
}

/** Barre de filtres. La période est optionnelle : toutes les pages n'en ont pas besoin. */
export function DashboardFilters({ sites, siteId, onSiteChange, onRefresh, period, onPeriodChange }: Readonly<DashboardFiltersProps>) {
    const siteOptions = sites.length
        ? sites.map((site) => ({ value: site.site_id, label: `${site.site_name} — ${site.location}` }))
        : [{ value: '', label: 'Aucun site disponible' }]

    return (
        <section className="filters-card" aria-label="Filtres">
            <Select
                id="filter-site"
                label="Site"
                value={siteId ?? ''}
                options={siteOptions}
                onChange={onSiteChange}
                disabled={!sites.length}
            />
            {period !== undefined && onPeriodChange !== undefined && (
                <Select
                    id="filter-period"
                    label="Période"
                    value={period}
                    options={periods.map(({ value, label }) => ({ value, label }))}
                    onChange={(value) => onPeriodChange(value as Period)}
                />
            )}
            <button className="refresh-button" type="button" onClick={onRefresh}>
                <Icon name="refresh" /> Actualiser les données
            </button>
        </section>
    )
}
