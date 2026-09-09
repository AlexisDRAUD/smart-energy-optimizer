import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { DashboardPage } from '../src/pages/DashboardPage'
import { useFilters } from '../src/hooks/useFilters'
import { getConsumptionChart } from '../src/api/consumptionChart'
import { getLatestReading } from '../src/api/sites'
import { getOverview } from '../src/api/dashboard'
import { getAlertsPage } from '../src/api/alerts'
import type { ApiConsumptionChart, ApiLatestReading } from '../src/types/api'
import type { Period } from '../src/data/periods'

jest.mock('../src/hooks/useFilters')
jest.mock('../src/api/consumptionChart')
jest.mock('../src/api/sites')
jest.mock('../src/api/dashboard')
jest.mock('../src/api/alerts')

const start = '2026-09-01T12:00:00Z'
const end = '2026-09-02T12:00:00Z'
const coverage = { expected_minutes: 1440, received_minutes: 2, valid_minutes: 1, missing_minutes: 1438, null_minutes: 1, percent: 0.07, first_at: start, last_at: start }
const fixture = (): ApiConsumptionChart => ({
    site_id: 'LYO-01', start, end, future_end: '2026-09-02T14:00:00Z', unit: 'kWh', unit_basis: 'source_declared', measurement_interval_seconds: null,
    cadence_seconds: 60, horizon_minutes: 120, model_name: 'production', model_version: 'prod-v1', max_readings: 43201, max_predictions: 43321,
    readings: [{ measured_at: start, consumption_kwh: 330, is_imputed: false, data_quality: 'good', segment_start: true }],
    historical_predictions: [{ site_id: 'LYO-01', target_at: start, predicted_at: '2026-09-01T10:00:00Z', predicted_kwh: 300, actual_kwh: null, absolute_error: null, horizon_minutes: 120, model_version: 'prod-v1', segment_start: true }],
    future_predictions: [{ site_id: 'LYO-01', target_at: '2026-09-02T13:59:00Z', predicted_at: end, predicted_kwh: 310, actual_kwh: null, absolute_error: null, horizon_minutes: 120, model_version: 'prod-v1', segment_start: true }], reading_coverage: coverage, prediction_coverage: coverage, future_coverage: { ...coverage, expected_minutes: 120, received_minutes: 1, valid_minutes: 1 },
    downsampling: {
        algorithm: 'lttb', target_points_per_series: 600,
        readings: { input_points: 1440, output_points: 600, applied: true },
        historical_predictions: { input_points: 1200, output_points: 600, applied: true },
        future_predictions: { input_points: 0, output_points: 0, applied: false },
    },
    last_evaluated: { target_at: start, actual_kwh: 330, predicted_kwh: 300, deviation_percent: 10, horizon_minutes: 120, model_version: 'prod-v1' },
})

function filters(period: Period = 'day'): ReturnType<typeof useFilters> {
    return { sites: [
        { site_id: 'LYO-01', site_name: 'Lyon', site_type: 'office', location: 'Lyon', capacity_kw: 1000, status: 'active', last_seen_at: start },
        { site_id: 'PAR-01', site_name: 'Paris', site_type: 'office', location: 'Paris', capacity_kw: 900, status: 'active', last_seen_at: start },
    ], siteId: 'LYO-01', setSiteId: jest.fn(), period, setPeriod: jest.fn(), error: null, isLoading: false, reload: jest.fn() }
}

beforeEach(() => {
    sessionStorage.clear()
    jest.mocked(useFilters).mockReturnValue(filters())
    jest.mocked(getConsumptionChart).mockResolvedValue(fixture())
    jest.mocked(getLatestReading).mockResolvedValue({ consumption_kwh: 999, measured_at: end } as ApiLatestReading)
    jest.mocked(getOverview).mockResolvedValue({ site_count: 1, total_consumption_kw: 999, total_capacity_kw: 1000, average_load_rate_percent: 99.9, by_site: [], sites_without_valid_reading: [], sites_without_valid_reading_count: 0, incomplete: false })
    jest.mocked(getAlertsPage).mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 })
})

test.each(['day', 'week', 'month'] as const)('historical comparison and prediction remain visible on %s', async (period) => {
    jest.mocked(useFilters).mockReturnValue(filters(period))
    const { container } = render(<DashboardPage />)
    const card = (await screen.findByText('Dernier écart évalué')).closest('article')!
    expect(card).toHaveTextContent('+10')
    expect(card).toHaveTextContent('H+2 (120 min)')
    expect(card).toHaveTextContent('prod-v1')
    expect(card).toHaveTextContent('1 sept. 2026')
    expect(card).not.toHaveTextContent('999')
    expect(container.querySelector('.prediction-points circle')).toBeInTheDocument()
    expect(screen.getByLabelText('Qualité des données réelles')).toHaveTextContent('1 438')
    expect(screen.getByText('Détails des données')).toBeInTheDocument()
    expect(screen.getByText('Affichage LTTB')).toBeInTheDocument()
    expect(screen.getByText('600/1440')).toBeInTheDocument()
    expect(screen.getByText('600/1200')).toBeInTheDocument()
    const chart = screen.getByRole('img', { name: 'Consommation réelle et prédite' })
    expect(chart).toHaveAttribute('data-end', end)
    expect(chart).toHaveAttribute('data-future-end', '2026-09-02T14:00:00Z')
    expect(container.querySelector('.future-series .prediction-points circle')).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: 'Prévisions futures H+2' })).not.toBeInTheDocument()
    expect(jest.mocked(getAlertsPage).mock.calls[0][0]).toEqual(expect.objectContaining({ limit: 100 }))
    expect(jest.mocked(getAlertsPage).mock.calls[0][0]).not.toHaveProperty('siteId')
    const [, requestedStart, requestedEnd] = jest.mocked(getConsumptionChart).mock.calls[0]
    expect(Date.parse(requestedEnd) - Date.parse(requestedStart)).toBe(({ day: 1, week: 7, month: 30 }[period]) * 86400000)
})

test('recent alerts include another accessible site regardless of the chart selection', async () => {
    jest.mocked(getAlertsPage).mockResolvedValue({ items: [{
        id: 42,
        site_id: 'PAR-01',
        detected_at: end,
        type: 'spike',
        severity: 'high',
        message: 'Pic détecté',
        value: 700,
        threshold_value: 600,
        status: 'open',
        origin: 'source',
        acknowledged_at: null,
    }], total: 27, limit: 100, offset: 0 })

    render(<DashboardPage />)

    const alerts = (await screen.findByText('Alertes récentes du parc')).closest('article')!
    expect(alerts).toHaveTextContent('Pic détecté')
    expect(alerts).toHaveTextContent('Paris')
    expect(alerts).toHaveTextContent('Source collectée')
    expect(alerts).toHaveTextContent('27 alertes ouvertes sur les sites accessibles')
    expect(within(alerts).getByRole('link', { name: 'Voir le détail des alertes' })).toHaveAttribute('href', '#/alertes')
})

test('shows each critical fleet alert once per browser tab', async () => {
    jest.mocked(getAlertsPage).mockResolvedValue({ items: [{
        id: 99,
        site_id: 'PAR-01',
        detected_at: end,
        type: 'outage',
        severity: 'critical',
        message: 'Risque critique',
        value: 900,
        threshold_value: 800,
        status: 'open',
        origin: 'source',
        acknowledged_at: null,
    }], total: 1, limit: 100, offset: 0 })

    const { unmount } = render(<DashboardPage />)
    const popup = await screen.findByRole('alertdialog', { name: 'Paris' })
    expect(popup).toHaveTextContent('Risque critique')
    expect(popup).toHaveTextContent('Source collectée')
    fireEvent.click(within(popup).getByRole('button', { name: 'Fermer' }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(sessionStorage.getItem('enervision_dismissed_critical_alert')).toBe('99')

    unmount()
    render(<DashboardPage />)
    await screen.findByText('Alertes récentes du parc')
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
})

test('no evaluated pair is explicitly unavailable', async () => {
    jest.mocked(getConsumptionChart).mockResolvedValue({ ...fixture(), last_evaluated: null })
    render(<DashboardPage />)
    const card = (await screen.findByText('Dernier écart évalué')).closest('article')!
    expect(card).toHaveTextContent('Indisponible')
    expect(card).toHaveTextContent('Aucune paire réel/prédit sur la période')
})

test('a missing latest measure does not hide an available H+2 prediction', async () => {
    jest.mocked(getLatestReading).mockResolvedValue({ consumption_kwh: null, measured_at: end } as ApiLatestReading)
    render(<DashboardPage />)

    const current = (await screen.findByText('Consommation actuelle')).closest('article')!
    expect(current).toHaveTextContent('Mesure manquante')
    expect(current).toHaveTextContent('Une prévision peut exister à partir de relevés antérieurs')
    const forecast = screen.getAllByText('Prédiction H+2')[0].closest('article')!
    expect(forecast).toHaveTextContent('310 kWh')
})

test('zero forecast keeps pair metadata but no percentage', async () => {
    const chart = fixture()
    chart.last_evaluated = { ...chart.last_evaluated!, predicted_kwh: 0, deviation_percent: null }
    jest.mocked(getConsumptionChart).mockResolvedValue(chart)
    render(<DashboardPage />)
    const card = (await screen.findByText('Dernier écart évalué')).closest('article')!
    expect(card).toHaveTextContent('Indisponible')
    expect(card).toHaveTextContent('prédiction égale à zéro')
    expect(card).toHaveTextContent('prod-v1')
})

test('slow response from a previous period cannot replace current selection', async () => {
    let resolveOld!: (value: ApiConsumptionChart) => void
    jest.mocked(getConsumptionChart).mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve }))
    const { rerender } = render(<DashboardPage />)
    await waitFor(() => expect(getConsumptionChart).toHaveBeenCalledTimes(1))
    jest.mocked(useFilters).mockReturnValue(filters('month'))
    jest.mocked(getConsumptionChart).mockResolvedValue({ ...fixture(), model_version: 'current-response' })
    rerender(<DashboardPage />)
    await screen.findByText('Dernier écart évalué')
    await act(async () => { resolveOld({ ...fixture(), model_version: 'obsolete-response' }) })
    expect(screen.queryByText('obsolete-response')).not.toBeInTheDocument()
})
