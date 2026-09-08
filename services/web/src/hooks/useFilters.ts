import { useEffect, useState } from 'react'
import { useSites } from './useSites'
import { defaultPeriod, type Period } from '../data/periods'

/**
 * Site sélectionné et période choisie, pour les pages qui affichent la barre
 * de filtres.
 */
export function useFilters() {
    const { sites, error, isLoading, reload } = useSites()
    const [siteId, setSiteId] = useState<string | null>(null)
    const [period, setPeriod] = useState<Period>(defaultPeriod)

    // Dès que la liste arrive, on sélectionne le premier site.
    useEffect(() => {
        if (sites.length && !sites.some((site) => site.site_id === siteId)) {
            setSiteId(sites[0].site_id)
        }
    }, [siteId, sites])

    return { sites, siteId, setSiteId, period, setPeriod, error, isLoading, reload }
}
