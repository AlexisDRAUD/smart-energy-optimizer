import { apiRequest } from './client'
import type { ApiReading } from '../types/api'

export type ReadingsFilters = {
    siteId: string
    start?: string
    end?: string
    granularity?: 'minute' | 'quarter' | 'hour' | 'day'
    limit?: number
    offset?: number
}

type ReadingsResponse = {
    site_id: string
    points: Array<{
        measured_at: string
        consumption_kwh: number | null
        is_imputed: boolean
        data_quality: ApiReading['data_quality']
    }>
}

export async function getReadings({ siteId, start, end, granularity = 'minute', limit = 2000, offset = 0 }: ReadingsFilters) {
    const params = new URLSearchParams()
    params.set('site_id', siteId)
    if (start) params.set('start', start)
    if (end) params.set('end', end)
    params.set('granularity', granularity)
    params.set('limit', String(limit))
    params.set('offset', String(offset))
    const response = await apiRequest<ReadingsResponse>(`/api/v1/readings?${params}`)
    return response.points.map((point) => ({
        id: `${response.site_id}-${point.measured_at}`,
        site_id: response.site_id,
        recorded_at: point.measured_at,
        consumption_kwh_raw: point.is_imputed ? null : point.consumption_kwh,
        consumption_kwh_imputed: point.is_imputed ? point.consumption_kwh : null,
        data_quality: point.data_quality,
        null_reasons: [],
        source: 'reading',
    }))
}