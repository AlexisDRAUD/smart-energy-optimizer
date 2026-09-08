import type { ApiPrediction, ApiReadingPoint } from '../../types/api'

const PLOT_BOTTOM = 246
const PLOT_HEIGHT = 190
const PLOT_LEFT = 58
const PLOT_WIDTH = 720

type ConsumptionChartProps = {
    points: ApiReadingPoint[]
    predictions: ApiPrediction[]
}

/** Courbe des relevés réels prolongée par les prévisions du modèle. */
export function ConsumptionChart({ points, predictions }: Readonly<ConsumptionChartProps>) {
    const measured = points.filter((point): point is ApiReadingPoint & { consumption_kwh: number } => point.consumption_kwh !== null)
    const values = [...measured.map((point) => point.consumption_kwh), ...predictions.map((prediction) => prediction.predicted_kwh)]
    const lowest = Math.floor(Math.min(...values, 0) / 50) * 50
    const highest = Math.ceil(Math.max(...values, 1) / 50) * 50
    const range = Math.max(highest - lowest, 1)

    const times = [
        ...measured.map((point) => new Date(point.measured_at).getTime()),
        ...predictions.map((prediction) => new Date(prediction.target_at).getTime()),
    ].sort((left, right) => left - right)
    const start = times[0] ?? 0
    const end = times[times.length - 1] ?? start + 1
    const duration = Math.max(end - start, 1)

    const pointAt = (time: number, value: number) => ({
        x: PLOT_LEFT + (time - start) / duration * PLOT_WIDTH,
        y: PLOT_BOTTOM - (value - lowest) / range * PLOT_HEIGHT,
    })

    const realPoints = measured.map((point) => pointAt(new Date(point.measured_at).getTime(), point.consumption_kwh))
    const predictionPoints = predictions.map((prediction) => pointAt(new Date(prediction.target_at).getTime(), prediction.predicted_kwh))
    const lastReal = realPoints[realPoints.length - 1]
    const lastPrediction = predictionPoints[predictionPoints.length - 1]

    const toPath = (list: { x: number; y: number }[]) => list.map(({ x, y }) => `${x},${y}`).join(' ')
    const realPath = toPath(realPoints)
    // La courbe de prévision part du dernier point réel, sinon elle flotte.
    const predictionPath = lastReal ? toPath([lastReal, ...predictionPoints]) : ''

    const timeTicks = Array.from({ length: 7 }, (_, index) => ({
        x: PLOT_LEFT + PLOT_WIDTH * index / 6,
        label: new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(new Date(start + duration * index / 6)),
    }))

    return (
        <svg className="consumption-chart" viewBox="0 0 820 330" role="img" aria-label="Courbe de consommation réelle et prédite">
            <g className="grid-lines">
                {[0, 1, 2, 3].map((index) => (
                    <line key={index} x1="52" x2="790" y1={56 + index * (PLOT_HEIGHT / 3)} y2={56 + index * (PLOT_HEIGHT / 3)} />
                ))}
            </g>
            <g className="axis-labels">
                {[0, 1, 2, 3].map((index) => (
                    <text key={index} x="42" y={250 - index * (PLOT_HEIGHT / 3)} textAnchor="end">{Math.round(lowest + range * index / 3)}</text>
                ))}
            </g>

            {lastReal && (
                <>
                    <line className="now-line" x1={lastReal.x} x2={lastReal.x} y1="42" y2={PLOT_BOTTOM} />
                    <rect className="now-label" x={lastReal.x - 52} y="16" width="104" height="24" rx="12" />
                    <text className="now-text" x={lastReal.x} y="32" textAnchor="middle">MAINTENANT</text>
                </>
            )}

            {realPath && <polyline className="real-line" points={realPath} />}
            {predictionPath && <polyline className="prediction-line" points={predictionPath} />}
            {lastReal && <g className="real-points"><circle cx={lastReal.x} cy={lastReal.y} r="4" /></g>}
            {lastPrediction && <g className="prediction-points"><circle cx={lastPrediction.x} cy={lastPrediction.y} r="4" /></g>}

            <g className="axis-labels">
                {timeTicks.map(({ x, label }) => <text key={label} x={x} y="278" textAnchor="middle">{label}</text>)}
            </g>
        </svg>
    )
}
