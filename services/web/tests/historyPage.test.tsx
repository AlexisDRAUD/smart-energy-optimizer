import { render, screen, waitFor, within } from '@testing-library/react'
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

const sites = [
    { site_id: 'LYO-01', site_name: 'Lyon', site_type: 'office', location: 'Lyon', capacity_kw: 1000, status: 'active' as const, last_seen_at: '2026-09-03T12:00:00Z' },
    { site_id: 'PAR-01', site_name: 'Paris', site_type: 'office', location: 'Paris', capacity_kw: 900, status: 'active' as const, last_seen_at: '2026-09-03T12:00:00Z' },
]

function filters(siteId = 'LYO-01'): ReturnType<typeof useFilters> {
    return {
        sites,
        siteId,
        setSiteId: jest.fn(),
        period: 'day',
        setPeriod: jest.fn(),
        error: null,
        isLoading: false,
        reload: jest.fn(),
    }
}

beforeEach(() => {
    jest.mocked(useFilters).mockReturnValue(filters())
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

test('history metrics follow the selected site and ignore an obsolete response', async () => {
    let resolveLyon!: (value: ApiReadings) => void
    jest.mocked(getReadings).mockImplementationOnce(() => new Promise((resolve) => { resolveLyon = resolve }))
    const { rerender } = render(<HistoryPage />)
    await waitFor(() => expect(getReadings).toHaveBeenCalledTimes(1))

    const parisReadings: ApiReadings = {
        ...readings,
        site_id: 'PAR-01',
        completeness: { expected_points: 10, received_points: 7, imputed_points: 2, missing_points: 3, percent: 70 },
        total: 7,
    }
    jest.mocked(useFilters).mockReturnValue(filters('PAR-01'))
    jest.mocked(getReadings).mockResolvedValue(parisReadings)
    rerender(<HistoryPage />)

    const receivedCard = (await screen.findByText('Relevés reçus')).closest('article')!
    await waitFor(() => expect(receivedCard).toHaveTextContent('7'))
    expect(receivedCard).toHaveTextContent('Sur 10 attendus')
    expect(screen.getByText('Complétude').closest('article')).toHaveTextContent('70 %')
    expect(screen.getByText('Relevés imputés').closest('article')).toHaveTextContent('2')
    const latestCall = jest.mocked(getReadings).mock.calls[jest.mocked(getReadings).mock.calls.length - 1]
    expect(latestCall[0]).toEqual(expect.objectContaining({ siteId: 'PAR-01' }))
    expect(latestCall[1]).toBeInstanceOf(AbortSignal)

    resolveLyon({ ...readings, completeness: { expected_points: 99, received_points: 99, imputed_points: 99, missing_points: 0, percent: 100 } })
    await waitFor(() => expect(receivedCard).toHaveTextContent('7'))
    expect(receivedCard).not.toHaveTextContent('99')
})
