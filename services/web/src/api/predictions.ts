import { apiRequest } from './client'
import type { ApiPrediction } from '../types/api'

export function getNextPrediction(siteId: number) {
    return apiRequest<ApiPrediction>(`/api/v1/predictions/sites/${siteId}/next`)
}