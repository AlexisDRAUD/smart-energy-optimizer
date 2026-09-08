/** Les valeurs sont celles attendues par /alerts/summary, sans traduction. */
export type Period = 'day' | 'week' | 'month'

export const periods = [
    { value: 'day', label: 'Dernières 24 h', hours: 24 },
    { value: 'week', label: '7 derniers jours', hours: 24 * 7 },
    { value: 'month', label: '30 derniers jours', hours: 24 * 30 },
] as const satisfies ReadonlyArray<{ value: Period; label: string; hours: number }>

export const defaultPeriod: Period = 'day'

/** Date de début de la période, au format attendu par l'API. */
export function periodStart(period: Period) {
    const hours = periods.find((item) => item.value === period)?.hours ?? 24
    return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString()
}

/**
 * Granularité demandée à /readings selon la période.
 *
 * L'API additionne les relevés dans chaque intervalle : un point horaire vaut
 * la somme de ses soixante minutes. On garde donc la minute sur 24 h, seule
 * échelle comparable aux prévisions du modèle, et on agrège au-delà pour ne
 * pas rapatrier des dizaines de milliers de points.
 */
export function periodGranularity(period: Period) {
    if (period === 'day') return 'minute' as const
    if (period === 'week') return 'quarter' as const
    return 'hour' as const
}
