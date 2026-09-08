import { apiRequest } from './client'
import type { ApiAlert } from '../types/api'

export type AlertsFilters = {
    siteId?: string
    start?: string
    limit?: number
}

export async function getAlerts({ siteId, start, limit = 100 }: AlertsFilters = {}) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (siteId) params.set('site_id', siteId)
    if (start) params.set('start', start)
    const response = await apiRequest<{ items: ApiAlert[] }>(`/api/v1/alerts?${params}`)
    return response.items
}
