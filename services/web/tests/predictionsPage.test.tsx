import { act, render, screen, within } from '@testing-library/react'
import { getLatestPrediction, getModel, getModelPerformance, getPredictions } from '../src/api/predictions'
import { useFilters } from '../src/hooks/useFilters'
import { PredictionsPage } from '../src/pages/PredictionsPage'

jest.mock('../src/api/predictions')
jest.mock('../src/hooks/useFilters')

const at = '2026-09-08T16:00:00Z'
const metric = { mae: 1, rmse: 2, mape_percent: 3 }

beforeEach(() => {
    jest.useFakeTimers()
    jest.mocked(useFilters).mockReturnValue({
        sites: [{ site_id: 'SITE001', site_name: 'Site', site_type: 'office', location: 'Paris', capacity_kw: 500, status: 'active', last_seen_at: at }],
        siteId: 'SITE001', setSiteId: jest.fn(), period: 'day', setPeriod: jest.fn(),
        error: null, isLoading: false, reload: jest.fn(),
    })
    jest.mocked(getModel).mockResolvedValue({ model_name: 'local-moving-average', model_version: 'local-1', horizon_minutes: 120, last_prediction_at: at, predictions_total: 1, predictions_scored: 1 })
    jest.mocked(getModelPerformance).mockResolvedValue({ sample_size: 1, model: metric, persistence_baseline: metric, linear_baseline: metric })
    jest.mocked(getPredictions).mockResolvedValue([])
    jest.mocked(getLatestPrediction).mockResolvedValue({ site_id: 'SITE001', predicted_at: at, target_at: at, horizon_minutes: 120, predicted_kwh: 150, model_version: 'local-1', actual_kwh: null, absolute_error: null })
})

afterEach(() => {
    jest.useRealTimers()
})

test('refreshes model cards, performance, latest prediction and history every minute', async () => {
    render(<PredictionsPage />)
    await act(async () => undefined)

    expect(await screen.findByText('150 kWh')).toBeInTheDocument()
    expect(getModel).toHaveBeenCalledTimes(1)
    expect(getModel).toHaveBeenLastCalledWith('SITE001', expect.anything())
    expect(getModelPerformance).toHaveBeenCalledTimes(1)
    expect(getPredictions).toHaveBeenCalledTimes(1)
    expect(getLatestPrediction).toHaveBeenCalledTimes(1)

    await act(async () => {
        jest.advanceTimersByTime(60_000)
        await Promise.resolve()
    })

    expect(getModel).toHaveBeenCalledTimes(2)
    expect(getModelPerformance).toHaveBeenCalledTimes(2)
    expect(getPredictions).toHaveBeenCalledTimes(2)
    expect(getLatestPrediction).toHaveBeenCalledTimes(2)
})

test('shows the predictions table rows and the active model that produced them', async () => {
    jest.mocked(getModel).mockResolvedValue({ model_name: 'EnerVision_RF_Predictor_SITE001', model_version: '2', horizon_minutes: 120, last_prediction_at: at, predictions_total: 42, predictions_scored: 10 })
    jest.mocked(getPredictions).mockResolvedValue([
        { site_id: 'SITE001', predicted_at: '2026-09-08T14:00:00Z', target_at: '2026-09-08T16:00:00Z', horizon_minutes: 120, predicted_kwh: 312.5, model_version: '2', actual_kwh: 305, absolute_error: 7.5 },
        { site_id: 'SITE001', predicted_at: '2026-09-08T14:01:00Z', target_at: '2026-09-08T16:01:00Z', horizon_minutes: 120, predicted_kwh: 314, model_version: '2', actual_kwh: null, absolute_error: null },
    ])

    render(<PredictionsPage />)
    await act(async () => undefined)

    const table = (await screen.findByText('Prévisions produites')).closest('article')!
    expect(table).toHaveTextContent('EnerVision_RF_Predictor_SITE001 · version 2')
    expect(table).toHaveTextContent('2 prévisions')
    const firstRow = within(table).getByText('312,5 kWh').closest('tr')!
    expect(firstRow).toHaveTextContent('305 kWh')
    expect(firstRow).toHaveTextContent('7,5')
})
