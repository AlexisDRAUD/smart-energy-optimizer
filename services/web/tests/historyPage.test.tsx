import { render, screen, within } from '@testing-library/react'
import { getReadings } from '../src/api/readings'
import { useFilters } from '../src/hooks/useFilters'
import { HistoryPage } from '../src/pages/HistoryPage'
import type { ApiReadings } from '../src/types/api'

jest.mock('../src/api/readings')
jest.mock('../src/hooks/useFilters')

const readings: ApiReadings = {
    site_id: 'LYO-01',
    granularity: 'minute',
    points: [
        { measured_at: '2026-09-01T12:00:00Z', consumption_kwh: 100, is_imputed: false, data_quality: 'good' },
        { measured_at: '2026-09-03T12:00:00Z', consumption_kwh: 300, is_imputed: false, data_quality: 'good' },
        { measured_at: '2026-09-02T12:00:00Z', consumption_kwh: 200, is_imputed: false, data_quality: 'good' },
    ],
    completeness: { expected_points: 3, received_points: 3, imputed_points: 0, missing_points: 0, percent: 100 },
    total: 3,
}

beforeEach(() => {
    jest.mocked(useFilters).mockReturnValue({
        sites: [{ site_id: 'LYO-01', site_name: 'Lyon', site_type: 'office', location: 'Lyon', capacity_kw: 1000, status: 'active', last_seen_at: '2026-09-03T12:00:00Z' }],
        siteId: 'LYO-01',
        setSiteId: jest.fn(),
        period: 'day',
        setPeriod: jest.fn(),
        error: null,
        isLoading: false,
        reload: jest.fn(),
    })
    jest.mocked(getReadings).mockResolvedValue(readings)
})

test('shows detail readings from newest to oldest without changing the source order', async () => {
    render(<HistoryPage />)

    const rows = await screen.findAllByRole('row')
    expect(within(rows[1]).getByText(/3 sept\. 2026/)).toBeInTheDocument()
    expect(within(rows[2]).getByText(/2 sept\. 2026/)).toBeInTheDocument()
    expect(within(rows[3]).getByText(/1 sept\. 2026/)).toBeInTheDocument()
    expect(readings.points.map((point) => point.measured_at)).toEqual([
        '2026-09-01T12:00:00Z',
        '2026-09-03T12:00:00Z',
        '2026-09-02T12:00:00Z',
    ])
})
