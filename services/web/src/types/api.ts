/**
 * Miroir de services/backend/app/schemas/contract.py.
 *
 * Les noms sont ceux de l'API, sans traduction. Le front n'invente aucun
 * champ : si une donnée n'est pas ici, c'est que l'API ne la renvoie pas.
 */

export type DataQuality = 'good' | 'partial' | 'degraded' | 'critical'
export type Severity = 'low' | 'medium' | 'high' | 'critical'
export type AlertStatus = 'open' | 'acknowledged' | 'closed'
export type Granularity = 'minute' | 'quarter' | 'hour' | 'day'

export type ApiToken = {
    access_token: string
    token_type: string
    expires_in: number
}

export type ApiIdentity = {
    id: number
    email: string
    role: 'viewer' | 'operator' | 'admin'
    is_active: boolean
    created_at: string
}

export type ApiSite = {
    site_id: string
    site_type: string
    site_name: string
    location: string
    capacity_kw: number
    status: 'active' | 'inactive'
    last_seen_at: string
}

export type ApiReadingPoint = {
    measured_at: string
    consumption_kwh: number | null
    is_imputed: boolean
    data_quality: DataQuality
}

export type ApiCompleteness = {
    expected_points: number
    received_points: number
    imputed_points: number
    missing_points: number
    percent: number
}

export type ApiReadings = {
    site_id: string
    granularity: Granularity
    points: ApiReadingPoint[]
    completeness: ApiCompleteness
    total: number
}

export type ApiLatestReading = ApiReadingPoint & {
    site_id: string
    consumption_kwh_raw: number | null
    imputation_method: string | null
    temperature_celsius: number | null
    humidity_percent: number | null
    null_reasons: string[]
    ingested_at: string
    age_seconds: number
}

export type ApiAlert = {
    id: number
    site_id: string
    detected_at: string
    type: 'spike' | 'threshold' | 'anomaly' | 'outage' | 'sensor'
    severity: Severity
    message: string
    value: number | null
    threshold_value: number | null
    status: AlertStatus
    acknowledged_at: string | null
}

export type ApiPrediction = {
    site_id: string
    predicted_at: string
    target_at: string
    horizon_minutes: number
    predicted_kwh: number
    model_version: string
    actual_kwh: number | null
    absolute_error: number | null
}

export type ApiOverviewSite = {
    site_id: string
    consumption_kw: number
    capacity_kw: number
    load_rate_percent: number
    measured_at: string
}

export type ApiOverview = {
    site_count: number
    total_consumption_kw: number
    total_capacity_kw: number
    average_load_rate_percent: number
    by_site: ApiOverviewSite[]
    sites_without_valid_reading: string[]
    sites_without_valid_reading_count: number
    incomplete: boolean
}

export type ApiQualityPoint = {
    day: string
    expected_points: number
    received_points: number
    missing_points: number
    null_points: number
    imputed_points: number
    computed_at: string
}

export type ApiQuality = {
    site_id: string
    start: string
    end: string
    points: ApiQualityPoint[]
    total: number
}

export type ApiSensorPoint = {
    sensor: 'consumption' | 'electrical' | 'temperature' | 'humidity' | 'network'
    observed_at: string | null
    status: 'ok' | 'failing'
    failing_until: string | null
}

export type ApiSensorSite = {
    site_id: string
    sensors: ApiSensorPoint[]
    overall: 'ok' | 'failing'
}

export type ApiMetric = {
    mae: number | null
    rmse: number | null
    mape_percent: number | null
}

export type ApiModel = {
    model_name: string
    model_version: string
    trained_at: string | null
    horizon_minutes: number
    test_metrics: Record<string, number | null>
    availability: 'local_fallback' | 'mlflow'
    mlflow_available: boolean
}

export type ApiModelPerformance = {
    sample_size: number
    model: ApiMetric
    persistence_baseline: ApiMetric
    linear_baseline: ApiMetric
}

export type ApiRecommendation = {
    action: string
    estimated_savings_kwh: number
}
