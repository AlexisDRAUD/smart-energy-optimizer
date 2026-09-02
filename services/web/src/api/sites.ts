import { apiRequest } from './client'
import type { ApiReading, ApiSite } from '../types/api'

export function getSites() {
    return apiRequest<ApiSite[]>('/api/v1/sites')
}

export function getCurrentReading(siteId: number) {
    return apiRequest<ApiReading>(`/api/v1/sites/${siteId}/current`)
}