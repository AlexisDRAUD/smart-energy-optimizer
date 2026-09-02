import { useEffect, useState } from 'react'
import { useSites } from './useSites'

export function useSiteSelection() {
    const { sites, error, isLoading, reload } = useSites()
    const [siteId, setSiteId] = useState<string | null>(null)

    useEffect(() => {
        if (sites.length && !sites.some((site) => site.id === siteId)) {
            setSiteId(sites[0].id)
        }
    }, [siteId, sites])

    return { sites, siteId, setSiteId, error, isLoading, reload }
}
