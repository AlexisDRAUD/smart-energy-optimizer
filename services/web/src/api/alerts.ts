import { apiRequest } from './client'
import type { ApiAlert } from '../types/api'

export function getAlerts(activeOnly = true) {
    return apiRequest<ApiAlert[]>(`/api/v1/alerts?active_only=${activeOnly}`)
}