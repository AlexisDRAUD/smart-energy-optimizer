import { apiRequest } from './client'
import type { ApiAlert } from '../types/api'

export type AlertsFilters = {
    siteId?: string
    start?: string
    limit?: number
    severity?: 'low' | 'medium' | 'high' | 'critical'
    status?: 'open' | 'acknowledged' | 'closed' | 'all'
}

export type AlertsPage = {
    items: ApiAlert[]
    total: number
    limit: number
    offset: number
}

export async function getAlertsPage({ siteId, start, limit = 100, severity, status }: AlertsFilters = {}, signal?: AbortSignal) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (siteId) params.set('site_id', siteId)
    if (start) params.set('start', start)
    if (severity) params.set('severity', severity)
    if (status) params.set('status', status)
    return apiRequest<AlertsPage>(`/api/v1/alerts?${params}`, { signal })
}

export async function getAlerts(filters: AlertsFilters = {}, signal?: AbortSignal) {
    return (await getAlertsPage(filters, signal)).items
}

export function acknowledgeAlert(alertId: number) {
    return apiRequest<ApiAlert>(`/api/v1/alerts/${alertId}/acknowledge`, { method: 'POST' })
}

export function acknowledgeAllCriticalAlerts() {
    return apiRequest<{ acknowledged_count: number }>('/api/v1/alerts/acknowledge-all-critical', { method: 'POST' })
}
