export type SiteStatus = 'normal' | 'stable' | 'alert'

export type Site = {
    name: string
    consumption: string
    prediction: string
    deviation: string
    state: string
    lastReading: string
    status: SiteStatus
}

export type AlertDay = {
    label: string
    errors: number
}

export type Alert = {
    level: 'Critique' | 'À surveiller'
    title: string
    detail: string
    updatedAt: string
}

export const siteOptions = ['Piscine Aqualudique — Niort', 'Centre aquatique — Poitiers', 'Piscine municipale — Parthenay']

export const periodOptions = ['Dernières 24 h', '7 derniers jours', '30 derniers jours']

export const sites: Site[] = [
    { name: 'Aqualudique — Niort', consumption: '286 kWh', prediction: '312 kWh', deviation: '+9,1 %', state: 'Sous contrôle', lastReading: '09:58', status: 'normal' },
    { name: 'Centre aquatique — Poitiers', consumption: '241 kWh', prediction: '238 kWh', deviation: '−1,2 %', state: 'Stable', lastReading: '09:57', status: 'stable' },
    { name: 'Piscine municipale — Parthenay', consumption: '198 kWh', prediction: '232 kWh', deviation: '+17,2 %', state: 'Alerte', lastReading: '09:56', status: 'alert' },
]

export const alertDaysBySite: Record<string, AlertDay[]> = {
    'Piscine Aqualudique — Niort': [{ label: '25 août', errors: 1 }, { label: '26 août', errors: 0 }, { label: '27 août', errors: 2 }, { label: '28 août', errors: 1 }, { label: '29 août', errors: 3 }, { label: '30 août', errors: 1 }, { label: '31 août', errors: 2 }],
    'Centre aquatique — Poitiers': [{ label: '25 août', errors: 0 }, { label: '26 août', errors: 1 }, { label: '27 août', errors: 0 }, { label: '28 août', errors: 1 }, { label: '29 août', errors: 1 }, { label: '30 août', errors: 0 }, { label: '31 août', errors: 1 }],
    'Piscine municipale — Parthenay': [{ label: '25 août', errors: 2 }, { label: '26 août', errors: 3 }, { label: '27 août', errors: 1 }, { label: '28 août', errors: 4 }, { label: '29 août', errors: 2 }, { label: '30 août', errors: 3 }, { label: '31 août', errors: 5 }],
}

export const alertsBySite: Record<string, Alert[]> = {
    'Piscine Aqualudique — Niort': [
        { level: 'À surveiller', title: 'Écart en hausse sur le bassin nord', detail: '9,1 % — reste sous le seuil de 15 %', updatedAt: 'Mis à jour il y a 42 s' },
        { level: 'À surveiller', title: 'Mesure incohérente détectée', detail: 'Capteur de température à contrôler', updatedAt: 'Mis à jour il y a 18 min' },
    ],
    'Centre aquatique — Poitiers': [
        { level: 'À surveiller', title: 'Écart ponctuel de consommation', detail: '6,4 % — retour à la normale attendu', updatedAt: 'Mis à jour il y a 11 min' },
    ],
    'Piscine municipale — Parthenay': [
        { level: 'Critique', title: 'Seuil de consommation dépassé', detail: 'Écart de 17,2 % avec la prédiction H+2', updatedAt: 'Mis à jour il y a 2 min' },
        { level: 'À surveiller', title: 'Pompe bassin sportif sollicitée', detail: 'Cycle de fonctionnement prolongé détecté', updatedAt: 'Mis à jour il y a 9 min' },
        { level: 'À surveiller', title: 'Mesure de débit inhabituelle', detail: 'Vérifier le capteur du bassin extérieur', updatedAt: 'Mis à jour il y a 24 min' },
    ],
}

export function deviationClass(status: SiteStatus) {
    if (status === 'alert') return 'danger-text'
    if (status === 'stable') return 'success-text'
    return 'warning-text'
}
