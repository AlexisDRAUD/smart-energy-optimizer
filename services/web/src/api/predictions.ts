import { apiRequest } from './client'
import type { ApiModel, ApiModelPerformance, ApiPrediction } from '../types/api'

export function getLatestPrediction(siteId: string) {
    return apiRequest<ApiPrediction>(`/api/v1/predictions/latest?site_id=${encodeURIComponent(siteId)}`)
}

export async function getPredictions(siteId: string, start?: string, limit = 500) {
    const params = new URLSearchParams({ site_id: siteId, limit: String(limit) })
    if (start) params.set('start', start)
    const response = await apiRequest<{ items: ApiPrediction[] }>(`/api/v1/predictions?${params}`)
    return response.items
}

export function getModel() {
    return apiRequest<ApiModel>('/api/v1/model')
}

export function getModelPerformance(siteId: string, start?: string) {
    const params = new URLSearchParams({ site_id: siteId })
    if (start) params.set('start', start)
    return apiRequest<ApiModelPerformance>(`/api/v1/model/performance?${params}`)
}
