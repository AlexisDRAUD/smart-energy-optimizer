import type { AlertDay } from '../../data/dashboard'

export function ErrorBarChart({ data }: Readonly<{ data: AlertDay[] }>) {
    const maxErrors = Math.max(...data.map(({ errors }) => errors), 1)
    const chartHeight = 190
    const baseline = 242

    return (
        <svg className="errors-chart" viewBox="0 0 760 300" role="img" aria-label="Nombre d'erreurs détectées par jour">
            <g className="grid-lines">
                {[0, 1, 2, 3, 4].map((index) => <line key={index} x1="58" y1={52 + index * (chartHeight / 4)} x2="730" y2={52 + index * (chartHeight / 4)} />)}
            </g>
            <g className="axis-labels">
                {[0, 1, 2, 3, 4].map((index) => <text key={index} x="42" y={246 - index * (chartHeight / 4)} textAnchor="end">{Math.round(maxErrors * index / 4)}</text>)}
            </g>
            {data.map(({ label, errors }, index) => {
                const height = errors === 0 ? 0 : (errors / maxErrors) * chartHeight
                const x = 94 + index * 94
                const y = baseline - height
                return (
                    <g className="error-bar" key={label}>
                        <title>{`${label} : ${errors} erreur${errors > 1 ? 's' : ''}`}</title>
                        <rect x={x} y={y} width="48" height={height} rx="7" />
                        <text className="bar-value" x={x + 24} y={y - 10} textAnchor="middle">{errors}</text>
                        <text className="bar-label" x={x + 24} y="272" textAnchor="middle">{label}</text>
                    </g>
                )
            })}
        </svg>
    )
}
