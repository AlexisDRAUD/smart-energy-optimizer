import { apiRequest } from './client'
import type { ApiModel, ApiModelPerformance, ApiPrediction } from '../types/api'

export function getLatestPrediction(siteId: string, signal?: AbortSignal) {
    return apiRequest<ApiPrediction>(`/api/v1/predictions/latest?site_id=${encodeURIComponent(siteId)}`, { signal })
}

export async function getPredictions(siteId: string, start?: string, limit = 500, signal?: AbortSignal) {
    const params = new URLSearchParams({ site_id: siteId, limit: String(limit) })
    if (start) params.set('start', start)
    const response = await apiRequest<{ items: ApiPrediction[] }>(`/api/v1/predictions?${params}`, { signal })
    return response.items
}

export function getModel(signal?: AbortSignal) {
    return apiRequest<ApiModel>('/api/v1/model', { signal })
}

export function getModelPerformance(siteId: string, start?: string, signal?: AbortSignal) {
    const params = new URLSearchParams({ site_id: siteId })
    if (start) params.set('start', start)
    return apiRequest<ApiModelPerformance>(`/api/v1/model/performance?${params}`, { signal })
}
