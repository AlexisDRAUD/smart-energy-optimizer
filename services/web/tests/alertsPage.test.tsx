import { render, screen } from '@testing-library/react'
import { getAlerts } from '../src/api/alerts'
import { useFilters } from '../src/hooks/useFilters'
import { AlertsPage } from '../src/pages/AlertsPage'

jest.mock('../src/api/alerts')
jest.mock('../src/hooks/useFilters')

const detectedAt = '2026-09-08T08:05:00Z'

beforeEach(() => {
    window.location.hash = '#/alertes'
    jest.mocked(useFilters).mockReturnValue({
        sites: [{ site_id: 'SITE001', site_name: 'Site', site_type: 'office', location: 'Paris', capacity_kw: 500, status: 'active', last_seen_at: detectedAt }],
        siteId: 'SITE001', setSiteId: jest.fn(), period: 'day', setPeriod: jest.fn(),
        error: null, isLoading: false, reload: jest.fn(),
    })
    jest.mocked(getAlerts).mockResolvedValue([
        {
            id: 1, site_id: 'SITE001', detected_at: detectedAt, type: 'threshold',
            severity: 'medium', message: 'Seuil source dépassé', value: 420.5,
            threshold_value: 400, status: 'open', origin: 'source', acknowledged_at: null,
        },
        {
            id: 2, site_id: 'SITE001', detected_at: detectedAt, type: 'threshold',
            severity: 'high', message: 'Alerte interne', value: 450,
            threshold_value: 400, status: 'open', origin: 'internal', acknowledged_at: null,
        },
    ])
})

test('shows materialized source alerts with their origin', async () => {
    render(<AlertsPage />)

    expect(await screen.findByText('Seuil source dépassé')).toBeInTheDocument()
    expect(screen.getByText('Source collectée')).toBeInTheDocument()
    expect(screen.getByText('Règle interne — non attribuée au ML')).toBeInTheDocument()
    expect(screen.queryByText(/raw|brut/i)).not.toBeInTheDocument()
})

test('a notification link selects and highlights the related alert', async () => {
    const setPeriod = jest.fn()
    jest.mocked(useFilters).mockReturnValue({
        ...jest.mocked(useFilters)(),
        setPeriod,
    })
    window.location.hash = '#/alertes?site_id=SITE001&alert_id=2'

    render(<AlertsPage />)

    expect(await screen.findByText('Alerte interne')).toBeInTheDocument()
    expect(setPeriod).toHaveBeenCalledWith('week')
    expect(document.getElementById('alert-2')).toHaveClass('alert-row-highlight')
})
