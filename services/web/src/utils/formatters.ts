import type { DotColor } from '../components/common/MetricCard'
import type { DataQuality, Severity } from '../types/api'

export function formatEnergy(value: number | null | undefined) {
    return value === null || value === undefined
        ? 'Donnée indisponible'
        : `${value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWh`
}

export function formatPower(value: number | null | undefined) {
    return value === null || value === undefined
        ? 'Donnée indisponible'
        : `${value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kW`
}

export function formatPercent(value: number | null | undefined) {
    return value === null || value === undefined
        ? '—'
        : `${value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`
}

export function formatNumber(value: number | null | undefined) {
    return value === null || value === undefined ? '—' : value.toLocaleString('fr-FR', { maximumFractionDigits: 2 })
}

export function formatDateTime(value: string | null) {
    return value === null ? '—' : new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

/** Une date seule, au format « 04 sept. », à partir d'une chaîne AAAA-MM-JJ. */
export function formatDay(day: string) {
    return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short' }).format(new Date(`${day}T00:00:00Z`))
}

export function formatQuality(quality: DataQuality) {
    return { good: 'Bonne', partial: 'Partielle', degraded: 'Dégradée', critical: 'Critique' }[quality]
}

export function formatSeverity(severity: Severity) {
    return { low: 'Faible', medium: 'Moyenne', high: 'Haute', critical: 'Critique' }[severity]
}

/** Couleur de la pastille associée à une gravité. */
export function severityDot(severity: Severity): DotColor {
    if (severity === 'critical') return 'red'
    if (severity === 'high') return 'orange'
    return 'blue'
}
