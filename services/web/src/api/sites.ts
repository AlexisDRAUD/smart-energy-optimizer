import { apiRequest } from './client'
import type { ApiReading, ApiSite } from '../types/api'

type SitesResponse = {
    items: Array<{
        site_id: string
        site_type: string
        site_name: string
        location: string
        capacity_kw: number
        status: 'active' | 'inactive'
        last_seen_at: string
    }>
}

type LatestReadingResponse = {
    measured_at: string
    consumption_kwh: number | null
    is_imputed: boolean
    data_quality: ApiReading['data_quality']
    site_id: string
    consumption_kwh_raw: number | null
    null_reasons: string[]
}

function toSite(site: SitesResponse['items'][number]): ApiSite {
    const [city = site.location, country = ''] = site.location.split(',').map((value) => value.trim())
    return {
        id: site.site_id,
        code: site.site_id,
        name: site.site_name,
        city,
        country,
        surface_m2: 0,
        subscribed_power_kw: site.capacity_kw,
    }
}

function toReading(reading: LatestReadingResponse): ApiReading {
    return {
        id: `${reading.site_id}-${reading.measured_at}`,
        site_id: reading.site_id,
        recorded_at: reading.measured_at,
        consumption_kwh_raw: reading.consumption_kwh_raw,
        consumption_kwh_imputed: reading.is_imputed ? reading.consumption_kwh : null,
        data_quality: reading.data_quality,
        null_reasons: reading.null_reasons,
        source: 'reading',
    }
}

export async function getSites() {
    const response = await apiRequest<SitesResponse>('/api/v1/sites')
    return response.items.map(toSite)
}

export async function getCurrentReading(siteId: string) {
    const response = await apiRequest<LatestReadingResponse>(`/api/v1/sites/${encodeURIComponent(siteId)}/latest`)
    return toReading(response)
}
