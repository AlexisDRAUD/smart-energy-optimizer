import { render, screen, waitFor } from '@testing-library/react'
import { getAlertsPage } from '../src/api/alerts'
import { FleetCriticalNotifications } from '../src/components/alerts/FleetCriticalNotifications'

jest.mock('../src/api/alerts')

beforeEach(() => {
    jest.mocked(getAlertsPage).mockReset()
})

test('keeps a critical fleet notification visible with a link to alerts', async () => {
    jest.mocked(getAlertsPage).mockResolvedValue({
        items: [{
            id: 7,
            site_id: 'SITE003',
            detected_at: '2026-09-09T08:51:00Z',
            type: 'outage',
            severity: 'critical',
            message: 'Risque de surcharge sur Data Center Marseille',
            value: 1800,
            threshold_value: 900,
            status: 'open',
            origin: 'source',
            acknowledged_at: null,
        }],
        total: 4,
        limit: 3,
        offset: 0,
    })

    render(<FleetCriticalNotifications />)

    const notification = await screen.findByLabelText('Notifications critiques')
    expect(notification).toHaveTextContent('Risque de surcharge sur Data Center Marseille')
    expect(screen.getByLabelText('4 alertes critiques ouvertes')).toHaveTextContent('4')
    expect(screen.getByRole('link', { name: /Risque de surcharge/ })).toHaveAttribute('href', '#/alertes')
    expect(getAlertsPage).toHaveBeenCalledWith({ severity: 'critical', limit: 3 }, expect.any(AbortSignal))
})

test('does not display an empty notification panel', async () => {
    jest.mocked(getAlertsPage).mockResolvedValue({ items: [], total: 0, limit: 3, offset: 0 })

    render(<FleetCriticalNotifications />)

    await waitFor(() => expect(getAlertsPage).toHaveBeenCalled())
    expect(screen.queryByLabelText('Notifications critiques')).not.toBeInTheDocument()
})
