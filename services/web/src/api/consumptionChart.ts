import { apiRequest } from './client'
import type { ApiConsumptionChart } from '../types/api'

export function getConsumptionChart(siteId: string, start: string, end: string, signal?: AbortSignal) {
    const params = new URLSearchParams({ site_id: siteId, start, end })
    return apiRequest<ApiConsumptionChart>(`/api/v1/consumption-chart?${params}`, { signal })
}
