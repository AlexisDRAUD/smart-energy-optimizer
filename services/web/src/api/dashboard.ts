import { apiRequest } from './client'
import type { ApiOverview, ApiQuality, ApiRecommendation, ApiSensorSite } from '../types/api'

/** Consommation et taux de charge de tous les sites, en un seul appel. */
export function getOverview() {
    return apiRequest<ApiOverview>('/api/v1/overview')
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

export async function getRecommendations(siteId: string) {
    const response = await apiRequest<{ recommendations: ApiRecommendation[] }>(`/api/v1/recommendations?site_id=${encodeURIComponent(siteId)}`)
    return response.recommendations
}
