import { useCallback, useEffect, useState } from 'react'
import { getSites } from '../api/sites'
import type { ApiSite } from '../types/api'

export function useSites() {
    const [sites, setSites] = useState<ApiSite[]>([])
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    const reload = useCallback(async () => {
        setIsLoading(true)
        setError(null)
        try {
            setSites(await getSites())
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Impossible de charger les sites.')
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        void reload()
    }, [reload])

    return { sites, error, isLoading, reload }
}
