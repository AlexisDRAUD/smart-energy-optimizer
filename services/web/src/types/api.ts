export type ApiSite = {
    id: string
    code: string
    name: string
    city: string
    country: string
    surface_m2: number
    subscribed_power_kw: number
}

export type ApiReading = {
    id: string
    site_id: string
    recorded_at: string
    consumption_kwh_raw: number | null
    consumption_kwh_imputed: number | null
    data_quality: 'good' | 'partial' | 'degraded' | 'critical' | 'predicted'
    null_reasons: string[] | null
    source: string
}

export type ApiAlert = {
    id: number
    site_id: string
    severity: 'info' | 'warning' | 'critical'
    message: string
    triggered_at: string
    is_active: boolean
}

export type ApiRecommendation = {
    action: string
    estimated_savings_kwh: number
}

export type ApiPrediction = Omit<ApiReading, 'consumption_kwh_raw' | 'consumption_kwh_imputed' | 'data_quality' | 'null_reasons' | 'source'> & {
    predicted_at: string
    target_at: string
    horizon_minutes: number
    predicted_kwh: number
    model_version: string
    actual_kwh: number | null
    absolute_error: number | null
    consumption_kwh_raw?: never
    consumption_kwh_imputed?: never
    data_quality?: never
    null_reasons?: never
    source: 'prediction'
}

export type ApiSummary = {
    site_count: number
    reading_count: number
    active_alert_count: number
    average_consumption_kwh: number
}

export type ApiToken = {
    access_token: string
    token_type: string
    expires_in: number
}
