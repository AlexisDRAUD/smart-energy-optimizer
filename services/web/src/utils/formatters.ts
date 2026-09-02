import type { ApiReading } from '../types/api'

export function getReadingValue(reading: ApiReading) {
    return reading.consumption_kwh_raw ?? reading.consumption_kwh_imputed
}

export function formatEnergy(value: number | null | undefined) {
    return value === null || value === undefined ? 'Donnée indisponible' : `${value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWh`
}

export function formatDateTime(value: string) {
    return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function formatQuality(quality: ApiReading['data_quality']) {
    return { good: 'Bonne', partial: 'Partielle', degraded: 'Dégradée', critical: 'Critique', predicted: 'Prédite' }[quality]
}