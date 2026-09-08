import { useEffect, useState } from 'react'
import { getCurrentUser } from '../../api/auth'
import { Select } from '../common/Select'
import type { ApiIdentity } from '../../types/api'

export type Theme = 'light' | 'dark'

type SettingsModalProps = {
    theme: Theme
    language: string
    timeZone: string
    onThemeChange: (theme: Theme) => void
    onLanguageChange: (language: string) => void
    onTimeZoneChange: (timeZone: string) => void
    onClose: () => void
    onLogout: () => void
}

const languages = [
    { value: 'fr-FR', label: 'Français' },
    { value: 'en-GB', label: 'English' },
    { value: 'es-ES', label: 'Español' },
]

const timeZones = [
    { value: 'Etc/GMT+12', label: 'Baker Island (UTC−12)' },
    { value: 'Pacific/Pago_Pago', label: 'Samoa américaines (UTC−11)' },
    { value: 'Pacific/Honolulu', label: 'Hawaï (UTC−10)' },
    { value: 'Pacific/Marquesas', label: 'Îles Marquises (UTC−09:30)' },
    { value: 'America/Anchorage', label: 'Alaska (UTC−09)' },
    { value: 'America/Los_Angeles', label: 'Pacifique Nord-Américain (UTC−08)' },
    { value: 'America/Denver', label: 'Rocheuses (UTC−07)' },
    { value: 'America/Chicago', label: 'Centre Nord-Américain (UTC−06)' },
    { value: 'America/Montreal', label: 'Est Nord-Américain (UTC−05)' },
    { value: 'America/Halifax', label: 'Atlantique Nord-Américain (UTC−04)' },
    { value: 'America/St_Johns', label: 'Terre-Neuve (UTC−03:30)' },
    { value: 'America/Sao_Paulo', label: 'Brésil (UTC−03)' },
    { value: 'America/Noronha', label: 'Atlantique Sud (UTC−02)' },
    { value: 'Atlantic/Azores', label: 'Açores (UTC−01)' },
    { value: 'Europe/London', label: 'Royaume-Uni (UTC+00)' },
    { value: 'Europe/Paris', label: 'Europe centrale (UTC+01)' },
    { value: 'Africa/Johannesburg', label: 'Afrique australe (UTC+02)' },
    { value: 'Europe/Moscow', label: 'Moscou (UTC+03)' },
    { value: 'Asia/Tehran', label: 'Iran (UTC+03:30)' },
    { value: 'Indian/Reunion', label: 'Océan Indien (UTC+04)' },
    { value: 'Asia/Kabul', label: 'Afghanistan (UTC+04:30)' },
    { value: 'Asia/Karachi', label: 'Pakistan (UTC+05)' },
    { value: 'Asia/Kolkata', label: 'Inde (UTC+05:30)' },
    { value: 'Asia/Kathmandu', label: 'Népal (UTC+05:45)' },
    { value: 'Asia/Dhaka', label: 'Bangladesh (UTC+06)' },
    { value: 'Asia/Yangon', label: 'Myanmar (UTC+06:30)' },
    { value: 'Asia/Bangkok', label: 'Indochine (UTC+07)' },
    { value: 'Asia/Singapore', label: 'Asie du Sud-Est (UTC+08)' },
    { value: 'Australia/Eucla', label: 'Australie centrale ouest (UTC+08:45)' },
    { value: 'Asia/Tokyo', label: 'Japon (UTC+09)' },
    { value: 'Australia/Adelaide', label: 'Australie centrale (UTC+09:30)' },
    { value: 'Australia/Brisbane', label: 'Australie orientale (UTC+10)' },
    { value: 'Australia/Lord_Howe', label: 'Île Lord Howe (UTC+10:30)' },
    { value: 'Pacific/Noumea', label: 'Nouvelle-Calédonie (UTC+11)' },
    { value: 'Pacific/Auckland', label: 'Nouvelle-Zélande (UTC+12)' },
    { value: 'Pacific/Chatham', label: 'Îles Chatham (UTC+12:45)' },
    { value: 'Pacific/Apia', label: 'Samoa (UTC+13)' },
    { value: 'Pacific/Kiritimati', label: 'Îles de la Ligne (UTC+14)' },
]

function formatGeographicTime(date: Date, locale: string, timeZone: string) {
    return new Intl.DateTimeFormat(locale, {
        timeZone,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        weekday: 'long',
        day: 'numeric',
        month: 'long',
    }).format(date)
}

const themes: { value: Theme; label: string; previewClass: string }[] = [
    { value: 'light', label: 'Clair', previewClass: 'light-preview' },
    { value: 'dark', label: 'Sombre', previewClass: 'dark-preview' },
]

const roleLabels = { viewer: 'Lecture seule', operator: 'Opérateur', admin: 'Administrateur' }

export function SettingsModal({ theme, language, timeZone, onThemeChange, onLanguageChange, onTimeZoneChange, onClose, onLogout }: Readonly<SettingsModalProps>) {
    const [currentTime, setCurrentTime] = useState(() => new Date())
    const [account, setAccount] = useState<ApiIdentity | null>(null)

    // Le compte connecté vient de /auth/me, il n'est pas déduit du jeton.
    useEffect(() => {
        let abandoned = false
        void getCurrentUser()
            .then((identity) => { if (!abandoned) setAccount(identity) })
            .catch(() => { if (!abandoned) setAccount(null) })
        return () => { abandoned = true }
    }, [])

    useEffect(() => {
        const timer = window.setInterval(() => setCurrentTime(new Date()), 1000)
        return () => window.clearInterval(timer)
    }, [])

    const geographicTime = formatGeographicTime(currentTime, language, timeZone)

    return (
        <div className="modal-backdrop" onMouseDown={onClose}>
            <section className="settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title" onMouseDown={(event) => event.stopPropagation()}>
                <header className="settings-modal-header">
                    <div><h2 id="settings-title">Paramètres</h2><p>Personnalisez votre espace de travail.</p></div>
                    <button type="button" className="modal-close" onClick={onClose} aria-label="Fermer les paramètres">×</button>
                </header>

                <div className="settings-section">
                    <div><h3>Compte</h3><p>Identité renvoyée par l’API.</p></div>
                    <div className="account-summary">
                        {account
                            ? <><strong>{account.email}</strong><span>{roleLabels[account.role]}</span></>
                            : <span>Compte indisponible</span>}
                    </div>
                </div>

                <div className="settings-section">
                    <div><h3>Thème</h3><p>Choisissez l’apparence de l’interface.</p></div>
                    <div className="theme-options">
                        {themes.map(({ value, label, previewClass }) => <button type="button" className={`theme-option ${theme === value ? 'selected' : ''}`} onClick={() => onThemeChange(value)} aria-pressed={theme === value} key={value}><span className={`theme-preview ${previewClass}`} /> {label}</button>)}
                    </div>
                </div>

                <div className="settings-section">
                    <div><h3>Langue</h3><p>Définissez la langue de votre espace.</p></div>
                    <Select id="settings-language" label="Langue" hideLabel value={language} options={languages} onChange={onLanguageChange} />
                </div>

                <div className="settings-section">
                    <div><h3>Heure géographique</h3><p>Utilisée pour l’horodatage de vos données.</p></div>
                    <Select id="settings-time-zone" label="Fuseau horaire" hideLabel value={timeZone} options={timeZones} onChange={onTimeZoneChange} />
                    <output className="geographic-time">{geographicTime}</output>
                </div>

                <footer className="settings-modal-footer">
                    <button type="button" className="logout-button" onClick={onLogout}>Se déconnecter</button>
                    <button type="button" className="save-settings-button" onClick={onClose}>Fermer</button>
                </footer>
            </section>
        </div>
    )
}
