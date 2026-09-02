import { apiRequest } from './client'
import type { ApiRecommendation } from '../types/api'

type RecommendationsResponse = {
    recommendations: ApiRecommendation[]
}

export async function getRecommendations(siteId: string) {
    const response = await apiRequest<RecommendationsResponse>(`/api/v1/recommendations?site_id=${encodeURIComponent(siteId)}`)
    return response.recommendations
}
