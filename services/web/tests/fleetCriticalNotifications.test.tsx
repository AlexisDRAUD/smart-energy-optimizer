import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { acknowledgeAlert, acknowledgeAllCriticalAlerts, getAlertsPage } from '../src/api/alerts'
import { FleetCriticalNotifications } from '../src/components/alerts/FleetCriticalNotifications'

jest.mock('../src/api/alerts')

beforeEach(() => {
    jest.mocked(getAlertsPage).mockReset()
    jest.mocked(acknowledgeAlert).mockReset()
    jest.mocked(acknowledgeAllCriticalAlerts).mockReset()
})

test('opens the related alert and can collapse then reopen the notification centre', async () => {
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
        total: 104,
        limit: 3,
        offset: 0,
    })

    render(<FleetCriticalNotifications />)

    const notification = await screen.findByLabelText('Notifications critiques')
    expect(notification).toHaveTextContent('Risque de surcharge sur Data Center Marseille')
    expect(screen.getByLabelText('104 alertes critiques ouvertes')).toHaveTextContent('99+')
    expect(screen.getByRole('link', { name: /Risque de surcharge/ })).toHaveAttribute('href', '#/alertes?site_id=SITE003&alert_id=7')

    fireEvent.click(screen.getByRole('button', { name: 'Réduire les notifications' }))
    expect(screen.queryByLabelText('Notifications critiques')).not.toBeInTheDocument()
    const collapsed = screen.getByRole('button', { name: 'Ouvrir les notifications, 104 alertes critiques ouvertes' })
    expect(collapsed).toHaveTextContent('99+')

    fireEvent.click(collapsed)
    expect(screen.getByLabelText('Notifications critiques')).toBeInTheDocument()
    expect(getAlertsPage).toHaveBeenCalledWith({ severity: 'critical', limit: 3 }, expect.any(AbortSignal))
})

test('removes one notification by acknowledging it', async () => {
    const alert = {
        id: 7,
        site_id: 'SITE003',
        detected_at: '2026-09-09T08:51:00Z',
        type: 'outage' as const,
        severity: 'critical' as const,
        message: 'Risque de surcharge sur Data Center Marseille',
        value: 1800,
        threshold_value: 900,
        status: 'open' as const,
        origin: 'source' as const,
        acknowledged_at: null,
    }
    jest.mocked(getAlertsPage)
        .mockResolvedValueOnce({ items: [alert], total: 1, limit: 3, offset: 0 })
        .mockResolvedValue({ items: [], total: 0, limit: 3, offset: 0 })
    jest.mocked(acknowledgeAlert).mockResolvedValue({ ...alert, status: 'acknowledged', acknowledged_at: '2026-09-09T09:00:00Z' })

    render(<FleetCriticalNotifications />)
    fireEvent.click(await screen.findByRole('button', { name: `Retirer la notification : ${alert.message}` }))

    await waitFor(() => expect(acknowledgeAlert).toHaveBeenCalledWith(7))
    await waitFor(() => expect(screen.queryByLabelText('Notifications critiques')).not.toBeInTheDocument())
})

test('removes all current critical notifications at once', async () => {
    const alert = {
        id: 8,
        site_id: 'SITE004',
        detected_at: '2026-09-09T09:01:00Z',
        type: 'outage' as const,
        severity: 'critical' as const,
        message: 'Risque critique',
        value: 500,
        threshold_value: 450,
        status: 'open' as const,
        origin: 'source' as const,
        acknowledged_at: null,
    }
    jest.mocked(getAlertsPage)
        .mockResolvedValueOnce({ items: [alert], total: 1, limit: 3, offset: 0 })
        .mockResolvedValue({ items: [], total: 0, limit: 3, offset: 0 })
    jest.mocked(acknowledgeAllCriticalAlerts).mockResolvedValue({ acknowledged_count: 1 })

    render(<FleetCriticalNotifications />)
    fireEvent.click(await screen.findByRole('button', { name: 'Tout retirer' }))

    await waitFor(() => expect(acknowledgeAllCriticalAlerts).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(screen.queryByLabelText('Notifications critiques')).not.toBeInTheDocument())
})

test('does not display an empty notification panel', async () => {
    jest.mocked(getAlertsPage).mockResolvedValue({ items: [], total: 0, limit: 3, offset: 0 })

    render(<FleetCriticalNotifications />)

    await waitFor(() => expect(getAlertsPage).toHaveBeenCalled())
    expect(screen.queryByLabelText('Notifications critiques')).not.toBeInTheDocument()
})
