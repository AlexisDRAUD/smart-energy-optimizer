import { apiRequest } from './client'
import type { ApiAlert } from '../types/api'

type AlertsResponse = {
    items: Array<{
        id: number
        site_id: string
        detected_at: string
        severity: 'low' | 'medium' | 'high' | 'critical'
        message: string
        status: 'open' | 'acknowledged' | 'closed'
    }>
}

export async function getAlerts(activeOnly = true): Promise<ApiAlert[]> {
    const query = activeOnly ? '?status=open' : ''
    const response = await apiRequest<AlertsResponse>(`/api/v1/alerts${query}`)
    return response.items.map((alert) => ({
        id: alert.id,
        site_id: alert.site_id,
        severity: alert.severity === 'critical' ? 'critical' : alert.severity === 'high' ? 'warning' : 'info',
        message: alert.message,
        triggered_at: alert.detected_at,
        is_active: alert.status === 'open',
    }))
}
