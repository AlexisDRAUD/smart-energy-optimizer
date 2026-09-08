import { render, screen } from '@testing-library/react'
import { ConsumptionChart } from '../src/components/charts/ConsumptionChart'
import { chartSegments, chartWindow } from '../src/utils/consumptionChart'
import type { ApiPrediction, ApiReadingPoint } from '../src/types/api'

const start = '2026-03-29T00:00:00.000Z'
const base = Date.parse(start)
const at = (minute: number) => new Date(base + minute * 60000).toISOString()
const real = (minute: number, value: number | null): ApiReadingPoint => ({ measured_at: at(minute), consumption_kwh: value, is_imputed: false, data_quality: 'good' })
const prediction = (minute: number): ApiPrediction => ({ site_id: 'LYO-01', target_at: at(minute), predicted_at: at(minute - 120), predicted_kwh: 300, actual_kwh: null, absolute_error: null, horizon_minutes: 120, model_version: 'local-1' })

test.each([['day', 24], ['week', 168], ['month', 720]] as const)('exact %s duration across DST and partial data', (period, hours) => {
    const window = chartWindow(period, Date.parse('2026-03-29T12:34:56.789Z'))
    expect(Date.parse(window.end) - Date.parse(window.start)).toBe(hours * 3600000)
    const { container } = render(<ConsumptionChart points={[real(3, 342.62)]} predictions={[prediction(4)]} {...window} cadenceSeconds={60} />)
    expect(screen.getByRole('img')).toHaveAttribute('data-start', window.start)
    expect(screen.getByRole('img')).toHaveAttribute('data-end', window.end)
    expect(container.querySelector('.prediction-points circle')).toBeInTheDocument()
    expect(container.querySelectorAll('.axis-labels tspan')).toHaveLength(10)
    expect(screen.queryByText('MAINTENANT')).not.toBeInTheDocument()
})

test('nulls and absent minutes split paths without changing native points', () => {
    const points = [{ time: 0, value: 342.62 }, { time: 60000, value: null },
        { time: 120000, value: 10 }, { time: 180000, value: 11 }, { time: 300000, value: 12 }]
    const segments = chartSegments(points, 0, 360000, 60)
    expect(segments).toEqual([[points[0]], [points[2], points[3]], [points[4]]])
    expect(segments[0][0]).toBe(points[0])
    expect(points[1].value).toBeNull()
})

test('sorts predictions, keeps isolated points, and never links real to prediction', () => {
    const { container } = render(<ConsumptionChart points={[real(0, 340), real(1, null), real(3, 350)]} predictions={[prediction(6), prediction(4), prediction(5), prediction(10)]} start={start} end={at(60)} cadenceSeconds={60} />)
    expect(container.querySelector('.real-line')).not.toBeInTheDocument()
    expect(container.querySelectorAll('.real-points circle')).toHaveLength(2)
    const path = container.querySelector('.prediction-line')!.getAttribute('points')!.split(' ')
    expect(path).toHaveLength(3)
    const positions = path.map((p) => Number(p.split(',')[0]))
    expect(positions).toEqual([...positions].sort((a, b) => a - b))
    expect(container.querySelectorAll('.prediction-points circle')).toHaveLength(1)
})

test('empty chart keeps requested domain and future remains outside historical chart', () => {
    const { container } = render(<ConsumptionChart points={[]} predictions={[prediction(60)]} start={start} end={at(60)} cadenceSeconds={60} />)
    expect(screen.getByText('Aucune valeur disponible')).toBeInTheDocument()
    expect(screen.getByRole('img')).toHaveAttribute('data-end', at(60))
    expect(container.querySelector('.prediction-line')).not.toBeInTheDocument()
    expect(container.querySelector('.prediction-points')).not.toBeInTheDocument()
})

test('server continuity joins spaced LTTB points and keeps actual breaks', () => {
    const points = [
        { time: base, value: 340, segmentStart: true },
        { time: base + 10 * 60000, value: 350, segmentStart: false },
        { time: base + 20 * 60000, value: 360, segmentStart: true },
        { time: base + 30 * 60000, value: 370, segmentStart: false },
    ]
    const segments = chartSegments(points, base, base + 60 * 60000, 60)

    expect(segments).toEqual([[points[0], points[1]], [points[2], points[3]]])
})
