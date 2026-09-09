import { apiRequest } from './client'
import type { ApiAlert } from '../types/api'

export type AlertsFilters = {
    siteId?: string
    start?: string
    limit?: number
}

export type AlertsPage = {
    items: ApiAlert[]
    total: number
    limit: number
    offset: number
}

export async function getAlertsPage({ siteId, start, limit = 100 }: AlertsFilters = {}, signal?: AbortSignal) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (siteId) params.set('site_id', siteId)
    if (start) params.set('start', start)
    return apiRequest<AlertsPage>(`/api/v1/alerts?${params}`, { signal })
}

export async function getAlerts(filters: AlertsFilters = {}, signal?: AbortSignal) {
    return (await getAlertsPage(filters, signal)).items
}
