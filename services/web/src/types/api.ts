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

export type ApiChartCoverage = {
    expected_minutes: number
    received_minutes: number
    missing_minutes: number
    null_minutes: number
    valid_minutes: number
    percent: number
    first_at: string | null
    last_at: string | null
}

export type ApiChartComparison = {
    target_at: string
    actual_kwh: number
    predicted_kwh: number
    deviation_percent: number | null
    horizon_minutes: 120
    model_version: string
}

export type ApiConsumptionChart = {
    site_id: string
    start: string
    end: string
    future_end: string
    unit: 'kWh'
    unit_basis: 'source_declared'
    measurement_interval_seconds: null
    cadence_seconds: 60
    horizon_minutes: 120
    model_name: string
    model_version: string
    max_readings: number
    max_predictions: number
    readings: ApiReadingPoint[]
    historical_predictions: ApiPrediction[]
    future_predictions: ApiPrediction[]
    reading_coverage: ApiChartCoverage
    prediction_coverage: ApiChartCoverage
    future_coverage: ApiChartCoverage
    last_evaluated: ApiChartComparison | null
}

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

/** Une observation reellement enregistree. Un capteur muet n'apparait pas. */
export type ApiSensorPoint = {
    sensor: 'consumption' | 'electrical' | 'temperature' | 'humidity' | 'network'
    observed_at: string
    status: 'ok' | 'failing'
    failing_until: string | null
}

export type ApiSensorSite = {
    site_id: string
    sensors: ApiSensorPoint[]
    /** null quand le site n'a aucune observation : son etat est inconnu. */
    overall: 'ok' | 'failing' | null
}

export type ApiMetric = {
    mae: number | null
    rmse: number | null
    mape_percent: number | null
}

/** Ce que la table predictions dit du modele. Null tant qu'aucune prevision n'existe. */
export type ApiModel = {
    model_name: string | null
    model_version: string | null
    horizon_minutes: number | null
    last_prediction_at: string | null
    predictions_total: number
    predictions_scored: number
}

export type ApiModelPerformance = {
    sample_size: number
    model: ApiMetric
    persistence_baseline: ApiMetric
    linear_baseline: ApiMetric
}
