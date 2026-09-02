import { apiRequest } from './client'
import type { ApiReading } from '../types/api'

export type ReadingsFilters = {
    siteId?: number
    startAt?: string
    endAt?: string
}

export function getReadings({ siteId, startAt, endAt }: ReadingsFilters = {}) {
    const params = new URLSearchParams()
    if (siteId !== undefined) params.set('site_id', String(siteId))
    if (startAt) params.set('start_at', startAt)
    if (endAt) params.set('end_at', endAt)
    const query = params.size ? `?${params}` : ''
    return apiRequest<ApiReading[]>(`/api/v1/readings${query}`)
}