import { act, render, screen, waitFor } from '@testing-library/react'
import { useAutoRefresh } from '../src/hooks/useAutoRefresh'

function Probe({ load }: Readonly<{ load: (signal: AbortSignal) => Promise<string> }>) {
    const state = useAutoRefresh({ enabled: true, key: 'site:day', load, errorMessage: 'Échec prévu' })
    return (
        <div>
            <span data-testid="data">{state.data ?? 'vide'}</span>
            <span data-testid="error">{state.error ?? 'aucune'}</span>
            <span data-testid="sync">{String(state.isSyncing)}</span>
        </div>
    )
}

beforeEach(() => {
    jest.useFakeTimers()
})

afterEach(() => {
    jest.useRealTimers()
    jest.restoreAllMocks()
})

test('aborts sibling requests when one resource fails', async () => {
    const signals: AbortSignal[] = []
    const load = jest.fn(async (signal: AbortSignal) => {
        signals.push(signal)
        throw new Error('Resource failed')
    })
    render(<Probe load={load} />)
    await screen.findByText('Resource failed')
    expect(signals[0].aborted).toBe(true)
})

test('pauses while hidden and does not duplicate a refresh after returning', async () => {
    const visibility = jest.spyOn(document, 'visibilityState', 'get')
    visibility.mockReturnValue('hidden')
    const load = jest.fn().mockResolvedValue('valid')
    render(<Probe load={load} />)
    await act(async () => { jest.advanceTimersByTime(90_000) })
    expect(load).not.toHaveBeenCalled()
    visibility.mockReturnValue('visible')
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    expect(load).toHaveBeenCalledTimes(1)
    await act(async () => {
        document.dispatchEvent(new Event('visibilitychange'))
        jest.advanceTimersByTime(30_000)
    })
    expect(load).toHaveBeenCalledTimes(1)
    await act(async () => { jest.advanceTimersByTime(60_000) })
    expect(load).toHaveBeenCalledTimes(2)
})

test('runs every 60 seconds without overlapping an unfinished request', async () => {
    let finishFirst!: (value: string) => void
    const first = new Promise<string>((resolve) => { finishFirst = resolve })
    const load = jest.fn().mockReturnValueOnce(first).mockResolvedValue('à jour')
    render(<Probe load={load} />)

    await waitFor(() => expect(load).toHaveBeenCalledTimes(1))
    act(() => { jest.advanceTimersByTime(60_000) })
    expect(load).toHaveBeenCalledTimes(1)

    await act(async () => { finishFirst('initial') })
    act(() => { jest.advanceTimersByTime(60_000) })
    await waitFor(() => expect(load).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('à jour')).toBeInTheDocument()
})

test('keeps the last valid data when a background refresh fails', async () => {
    const load = jest.fn().mockResolvedValueOnce('valide').mockRejectedValueOnce(new Error('Réseau indisponible'))
    render(<Probe load={load} />)

    expect(await screen.findByText('valide')).toBeInTheDocument()
    act(() => { jest.advanceTimersByTime(60_000) })
    await waitFor(() => expect(screen.getByTestId('error')).toHaveTextContent('Réseau indisponible'))
    expect(screen.getByTestId('data')).toHaveTextContent('valide')
})

test('aborts the active request and clears its timer on unmount', async () => {
    const capturedSignal: { current: AbortSignal | null } = { current: null }
    const load = jest.fn((signal: AbortSignal) => {
        capturedSignal.current = signal
        return new Promise<string>(() => undefined)
    })
    const { unmount } = render(<Probe load={load} />)

    await waitFor(() => expect(load).toHaveBeenCalledTimes(1))
    unmount()
    expect(capturedSignal.current?.aborted).toBe(true)
    expect(jest.getTimerCount()).toBe(0)
})
