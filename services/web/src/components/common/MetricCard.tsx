import type { ReactNode } from 'react'

export type DotColor = 'blue' | 'teal' | 'orange' | 'green' | 'red'

type MetricCardProps = {
    label: string
    value: ReactNode
    hint?: ReactNode
    dot?: DotColor
}

/** Carte à chiffre : un intitulé, une valeur, une précision en dessous. */
export function MetricCard({ label, value, hint, dot = 'blue' }: Readonly<MetricCardProps>) {
    return (
        <article className="metric-card">
            <p><span className={`metric-dot ${dot}`} /> {label}</p>
            <strong>{value}</strong>
            {hint && <small>{hint}</small>}
        </article>
    )
}
