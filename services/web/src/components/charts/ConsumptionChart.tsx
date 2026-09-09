import { useEffect, useRef, useState } from 'react'
import type { ApiPrediction, ApiReadingPoint } from '../../types/api'
import { chartSegments, type ChartPoint } from '../../utils/consumptionChart'

const BOTTOM = 246
const HEIGHT = 190
const LEFT = 60

type ConsumptionChartProps = {
    points: (ApiReadingPoint & { segment_start?: boolean })[]
    predictions: (ApiPrediction & { segment_start?: boolean })[]
    start: string
    end: string
    cadenceSeconds: number
    label?: string
    futureEnd?: string
    futurePredictions?: (ApiPrediction & { segment_start?: boolean })[]
}

export function ConsumptionChart({ points, predictions, start, end, cadenceSeconds, futureEnd, futurePredictions = [], label = 'Consommation réelle et prédite' }: Readonly<ConsumptionChartProps>) {
    const svgRef = useRef<SVGSVGElement>(null)
    const [viewWidth, setViewWidth] = useState(640)
    useEffect(() => {
        if (!svgRef.current || typeof ResizeObserver === 'undefined') return
        const observer = new ResizeObserver(([entry]) => setViewWidth(Math.max(300, entry.contentRect.width)))
        observer.observe(svgRef.current)
        return () => observer.disconnect()
    }, [])
    const plotWidth = viewWidth - 2 * LEFT
    const tickCount = viewWidth < 500 ? 3 : 5
    const startTime = Date.parse(start)
    const endTime = Date.parse(end)
    const futureTime = futureEnd ? Date.parse(futureEnd) : endTime
    const hasFuture = futureTime > endTime
    const historicalWidth = hasFuture ? plotWidth * 0.75 : plotWidth
    const future = chartSegments(futurePredictions.map((p) => ({ time: Date.parse(p.target_at), value: p.predicted_kwh, segmentStart: p.segment_start })), endTime, futureTime, cadenceSeconds)
    const real = chartSegments(points.map((p) => ({ time: Date.parse(p.measured_at), value: p.consumption_kwh, segmentStart: p.segment_start })), startTime, endTime, cadenceSeconds)
    const predicted = chartSegments(predictions.map((p) => ({ time: Date.parse(p.target_at), value: p.predicted_kwh, segmentStart: p.segment_start })), startTime, endTime, cadenceSeconds)
    // Avoid spreading tens of thousands of arguments into Math.max/min.
    let minimum = 0
    let maximum = 1
    for (const segments of [real, predicted, future]) {
        for (const segment of segments) {
            for (const point of segment) {
                minimum = Math.min(minimum, point.value!)
                maximum = Math.max(maximum, point.value!)
            }
        }
    }
    const lowest = Math.floor(minimum / 50) * 50
    const highest = Math.ceil(maximum / 50) * 50
    const x = (time: number) => hasFuture && time > endTime
        ? LEFT + historicalWidth + (time - endTime) / (futureTime - endTime) * (plotWidth - historicalWidth)
        : LEFT + (time - startTime) / (endTime - startTime) * historicalWidth
    const y = (value: number) => BOTTOM - (value - lowest) / (highest - lowest) * HEIGHT
    const date = new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: '2-digit' })
    const time = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' })
    const series = (segments: ChartPoint[][], kind: 'real' | 'prediction', scope: 'historical' | 'future') => segments.map((segment) => (
        <g className={`${scope}-series`} key={`${scope}-${kind}-${segment[0].time}`}>
            {segment.length > 1 && <polyline className={`${kind}-line`} points={segment.map((p) => `${x(p.time)},${y(p.value!)}`).join(' ')} />}
            {segment.length === 1 && <g className={`${kind}-points`}><circle cx={x(segment[0].time)} cy={y(segment[0].value!)} r="4" /></g>}
        </g>
    ))

    return (
        <svg ref={svgRef} className="consumption-chart" viewBox={`0 0 ${viewWidth} 330`} role="img" aria-label={label} data-start={start} data-end={end} data-future-end={hasFuture ? futureEnd : undefined}>
            {hasFuture && <g className="future-zone">
                <rect x={x(endTime)} y="42" width={plotWidth - historicalWidth} height={BOTTOM - 42} fill="#20a6b6" fillOpacity="0.07" />
                <line className="now-line" x1={x(endTime)} x2={x(endTime)} y1="42" y2={BOTTOM} strokeDasharray="4 4" />
                <text className="axis-labels" x={LEFT + historicalWidth + (plotWidth - historicalWidth) / 2} y="54" textAnchor="middle">Futur H+2 (zone agrandie)</text>
                <text className="axis-labels" x={x(endTime)} y="318" textAnchor="middle">Maintenant</text>
            </g>}
            <text className="axis-labels" x={LEFT} y="30">kWh — unité déclarée par la source</text>
            {[0, 1, 2, 3].map((index) => (
                <g key={index}>
                    <g className="grid-lines"><line x1={LEFT} x2={LEFT + plotWidth} y1={BOTTOM - index * HEIGHT / 3} y2={BOTTOM - index * HEIGHT / 3} /></g>
                    <g className="axis-labels"><text x={LEFT - 10} y={BOTTOM + 4 - index * HEIGHT / 3} textAnchor="end">{Math.round(lowest + (highest - lowest) * index / 3)}</text></g>
                </g>
            ))}
            {series(real, 'real', 'historical')}
            {series(predicted, 'prediction', 'historical')}
            {series(future, 'prediction', 'future')}
            {!real.length && !predicted.length && !future.length && <text x={viewWidth / 2} y="145" textAnchor="middle"><tspan x={viewWidth / 2}>Aucune valeur disponible</tspan><tspan x={viewWidth / 2} dy="20">sur cette fenêtre</tspan></text>}
            <g className="axis-labels">
                {Array.from({ length: tickCount }, (_, index) => {
                    const at = startTime + (endTime - startTime) * index / (tickCount - 1)
                    return <text key={index} x={x(at)} y="278" textAnchor="middle"><tspan x={x(at)}>{date.format(at)}</tspan><tspan x={x(at)} dy="18">{time.format(at)}</tspan></text>
                })}
                {hasFuture && <text x={x(futureTime)} y="278" textAnchor="end"><tspan x={x(futureTime)}>{date.format(futureTime)}</tspan><tspan x={x(futureTime)} dy="18">{time.format(futureTime)}</tspan></text>}
            </g>
        </svg>
    )
}
