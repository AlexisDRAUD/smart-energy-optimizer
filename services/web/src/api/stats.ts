import { apiRequest } from './client'
import type { ApiSummary } from '../types/api'

export function getSummary() {
    return apiRequest<ApiSummary>('/api/v1/stats/summary')
}