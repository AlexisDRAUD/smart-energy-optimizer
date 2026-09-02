export type HistoricalReading = {
    consumption: number
    prediction: number
    deviation: number
    status: 'Conforme' | 'À surveiller'
}

export const historicalReadingsBySite: Record<string, HistoricalReading[]> = {
    'Piscine Aqualudique — Niort': [
        { consumption: 278, prediction: 284, deviation: -2.1, status: 'Conforme' },
        { consumption: 291, prediction: 288, deviation: 1.0, status: 'Conforme' },
        { consumption: 304, prediction: 296, deviation: 2.7, status: 'Conforme' },
        { consumption: 285, prediction: 301, deviation: -5.3, status: 'Conforme' },
        { consumption: 321, prediction: 298, deviation: 7.7, status: 'À surveiller' },
        { consumption: 294, prediction: 289, deviation: 1.7, status: 'Conforme' },
        { consumption: 286, prediction: 312, deviation: -8.3, status: 'À surveiller' },
    ],
    'Centre aquatique — Poitiers': [
        { consumption: 235, prediction: 239, deviation: -1.7, status: 'Conforme' },
        { consumption: 242, prediction: 244, deviation: -0.8, status: 'Conforme' },
        { consumption: 249, prediction: 245, deviation: 1.6, status: 'Conforme' },
        { consumption: 238, prediction: 240, deviation: -0.8, status: 'Conforme' },
        { consumption: 251, prediction: 246, deviation: 2.0, status: 'Conforme' },
        { consumption: 240, prediction: 239, deviation: 0.4, status: 'Conforme' },
        { consumption: 241, prediction: 238, deviation: 1.2, status: 'Conforme' },
    ],
    'Piscine municipale — Parthenay': [
        { consumption: 204, prediction: 212, deviation: -3.8, status: 'Conforme' },
        { consumption: 218, prediction: 214, deviation: 1.9, status: 'Conforme' },
        { consumption: 228, prediction: 216, deviation: 5.6, status: 'À surveiller' },
        { consumption: 221, prediction: 219, deviation: 0.9, status: 'Conforme' },
        { consumption: 239, prediction: 220, deviation: 8.6, status: 'À surveiller' },
        { consumption: 234, prediction: 225, deviation: 4.0, status: 'Conforme' },
        { consumption: 198, prediction: 232, deviation: -14.7, status: 'À surveiller' },
    ],
}

export const periodDays: Record<string, string[]> = {
    '25 août 2026 → 31 août 2026': ['25 août', '26 août', '27 août', '28 août', '29 août', '30 août', '31 août'],
    '18 août 2026 → 24 août 2026': ['18 août', '19 août', '20 août', '21 août', '22 août', '23 août', '24 août'],
    '11 août 2026 → 17 août 2026': ['11 août', '12 août', '13 août', '14 août', '15 août', '16 août', '17 août'],
}
