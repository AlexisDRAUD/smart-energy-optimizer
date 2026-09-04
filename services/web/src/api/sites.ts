import { apiRequest } from './client'
import type { ApiLatestReading, ApiSite } from '../types/api'

export async function getSites() {
    const response = await apiRequest<{ items: ApiSite[] }>('/api/v1/sites')
    return response.items
}

export function getLatestReading(siteId: string) {
    return apiRequest<ApiLatestReading>(`/api/v1/sites/${encodeURIComponent(siteId)}/latest`)
}
