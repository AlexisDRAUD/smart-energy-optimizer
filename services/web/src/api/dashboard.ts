import { apiRequest } from './client'
import type { ApiOverview, ApiQuality, ApiSensorSite } from '../types/api'

/** Consommation et taux de charge de tous les sites, en un seul appel. */
export function getOverview(signal?: AbortSignal) {
    return apiRequest<ApiOverview>('/api/v1/overview', { signal })
}

/** Complétude quotidienne des relevés d'un site. */
export function getQuality(siteId: string, start?: string) {
    const params = new URLSearchParams({ site_id: siteId })
    if (start) params.set('start', start)
    return apiRequest<ApiQuality>(`/api/v1/quality?${params}`)
}

export async function getSensorStatus(siteId?: string) {
    const params = new URLSearchParams()
    if (siteId) params.set('site_id', siteId)
    const response = await apiRequest<{ items: ApiSensorSite[] }>(`/api/v1/quality/sensors?${params}`)
    return response.items
}
