export type AlertDay = { label: string; errors: number }

const CHART_HEIGHT = 190
const BASELINE = 242

export function ErrorBarChart({ data }: Readonly<{ data: AlertDay[] }>) {
    // Une graduation entière, sinon l'axe affiche « 1, 1, 2, 2 » quand le
    // maximum est petit.
    const step = Math.max(1, Math.ceil(Math.max(...data.map(({ errors }) => errors), 1) / 4))
    const top = step * 4
    const barWidth = Math.min(48, 640 / data.length - 12)

    return (
        <svg className="errors-chart" viewBox="0 0 760 300" role="img" aria-label="Nombre d'alertes détectées par jour">
            <g className="grid-lines">
                {[0, 1, 2, 3, 4].map((index) => (
                    <line key={index} x1="58" x2="730" y1={52 + index * (CHART_HEIGHT / 4)} y2={52 + index * (CHART_HEIGHT / 4)} />
                ))}
            </g>
            <g className="axis-labels">
                {[0, 1, 2, 3, 4].map((index) => (
                    <text key={index} x="42" y={246 - index * (CHART_HEIGHT / 4)} textAnchor="end">{step * index}</text>
                ))}
            </g>
            {data.map(({ label, errors }, index) => {
                const height = errors / top * CHART_HEIGHT
                const x = 94 + index * (640 / data.length)
                const y = BASELINE - height
                return (
                    <g className="error-bar" key={label}>
                        <title>{`${label} : ${errors} alerte${errors > 1 ? 's' : ''}`}</title>
                        <rect x={x} y={y} width={barWidth} height={height} rx="7" />
                        <text className="bar-value" x={x + barWidth / 2} y={y - 10} textAnchor="middle">{errors}</text>
                        <text className="bar-label" x={x + barWidth / 2} y="272" textAnchor="middle">{label}</text>
                    </g>
                )
            })}
        </svg>
    )
}
