import { apiRequest } from './client'

export function getSummary() {
    return apiRequest<{
        site_count: number
        total_consumption_kw: number
    }>('/api/v1/overview').then((overview) => ({
        site_count: overview.site_count,
        reading_count: 0,
        active_alert_count: 0,
        average_consumption_kwh: overview.site_count ? overview.total_consumption_kw / overview.site_count : 0,
    }))
}
