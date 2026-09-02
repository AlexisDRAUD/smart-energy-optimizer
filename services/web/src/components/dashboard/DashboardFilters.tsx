import { Icon } from '../common/Icon'
import { periodOptions } from '../../data/dashboard'
import type { ApiSite } from '../../types/api'

export type DashboardFiltersProps = {
    sites: ApiSite[]
    siteId: string | null
    period: string
    onSiteChange: (siteId: string) => void
    onPeriodChange: (period: string) => void
    onRefresh: () => void | Promise<void>
}

export function DashboardFilters({ sites, siteId, period, onSiteChange, onPeriodChange, onRefresh }: Readonly<DashboardFiltersProps>) {
    return (
        <section className="filters-card" aria-label="Filtres du tableau de bord">
            <label htmlFor="dashboard-site">
                <span>Site</span>
                <select id="dashboard-site" value={siteId ?? ''} onChange={(event) => onSiteChange(event.target.value)} disabled={!sites.length}>
                    {!sites.length && <option value="">Aucun site disponible</option>}
                    {sites.map((site) => <option value={site.id} key={site.id}>{site.name} — {site.city}</option>)}
                </select>
                <Icon name="chevron" />
            </label>
            <label htmlFor="dashboard-period">
                <span>Période</span>
                <select id="dashboard-period" value={period} onChange={(event) => onPeriodChange(event.target.value)}>
                    {periodOptions.map((option) => <option key={option}>{option}</option>)}
                </select>
                <Icon name="chevron" />
            </label>
            <button className="refresh-button" type="button" onClick={onRefresh}><Icon name="refresh" /> Actualiser les données</button>
        </section>
    )
}
