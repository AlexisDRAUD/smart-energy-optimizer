export type ApiSite = {
    id: number
    code: string
    name: string
    city: string
    country: string
    surface_m2: number
    subscribed_power_kw: number
}

export type ApiReading = {
    id: number
    site_id: number
    recorded_at: string
    consumption_kwh_raw: number | null
    consumption_kwh_imputed: number | null
    data_quality: 'good' | 'partial' | 'degraded' | 'critical' | 'predicted'
    null_reasons: string[] | null
    source: string
}

export type ApiAlert = {
    id: number
    site_id: number
    severity: 'info' | 'warning' | 'critical'
    message: string
    triggered_at: string
    is_active: boolean
}

export type ApiPrediction = Omit<ApiReading, 'consumption_kwh_raw' | 'consumption_kwh_imputed' | 'data_quality' | 'null_reasons' | 'source'> & {
    consumption_kwh_raw: number
    consumption_kwh_imputed: null
    data_quality: 'predicted'
    null_reasons: null
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
}