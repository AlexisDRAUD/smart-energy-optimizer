import { apiRequest } from './client'
import type { ApiReadings, Granularity } from '../types/api'

export type ReadingsFilters = {
    siteId: string
    start?: string
    end?: string
    granularity?: Granularity
    limit?: number
}

export function getReadings({ siteId, start, end, granularity = 'hour', limit = 2000 }: ReadingsFilters) {
    const params = new URLSearchParams({ site_id: siteId, granularity, limit: String(limit) })
    if (start) params.set('start', start)
    if (end) params.set('end', end)
    return apiRequest<ApiReadings>(`/api/v1/readings?${params}`)
}
