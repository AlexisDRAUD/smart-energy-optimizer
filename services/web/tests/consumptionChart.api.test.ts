import { getConsumptionChart } from '../src/api/consumptionChart'
import { apiRequest } from '../src/api/client'

jest.mock('../src/api/client', () => ({ apiRequest: jest.fn() }))

test('sends one bounded window without legacy pagination, propagates overflow errors', async () => {
    const failure = new Error('Chart volume exceeds the supported limit')
    jest.mocked(apiRequest).mockRejectedValueOnce(failure)
    await expect(getConsumptionChart('site / A', '2026-01-01T00:00:00Z', '2026-01-31T00:00:00Z')).rejects.toBe(failure)
    const url = new URL(jest.mocked(apiRequest).mock.calls[0][0], 'http://localhost')
    expect(url.pathname).toBe('/api/v1/consumption-chart')
    expect(url.searchParams.get('site_id')).toBe('site / A')
    expect(url.searchParams.get('start')).toBe('2026-01-01T00:00:00Z')
    expect(url.searchParams.get('end')).toBe('2026-01-31T00:00:00Z')
    expect(url.searchParams.has('limit')).toBe(false)
    expect(url.searchParams.has('offset')).toBe(false)
})
