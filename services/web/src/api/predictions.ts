import { apiRequest } from './client'
import type { ApiPrediction } from '../types/api'

type PredictionsResponse = {
    items: Array<Omit<ApiPrediction, 'id' | 'recorded_at' | 'source'>>
}

function toPrediction(prediction: PredictionsResponse['items'][number]): ApiPrediction {
    return {
        ...prediction,
        id: `${prediction.site_id}-${prediction.target_at}`,
        recorded_at: prediction.target_at,
        source: 'prediction',
    }
}

export async function getNextPrediction(siteId: string) {
    const prediction = await apiRequest<PredictionsResponse['items'][number]>(`/api/v1/predictions/latest?site_id=${encodeURIComponent(siteId)}`)
    return toPrediction(prediction)
}

export async function getPredictions(siteId: string, limit = 1000) {
    const response = await apiRequest<PredictionsResponse>(`/api/v1/predictions?site_id=${encodeURIComponent(siteId)}&limit=${limit}`)
    return response.items.map(toPrediction)
}