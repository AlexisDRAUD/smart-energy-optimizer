import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark' | 'rose' | 'aurora' | 'sunset' | 'ocean'

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
    { value: 'Etc/GMT+12', city: 'Baker Island', label: 'Baker Island (UTC−12)' },
    { value: 'Pacific/Pago_Pago', city: 'Pago Pago', label: 'Samoa américaines (UTC−11)' },
    { value: 'Pacific/Honolulu', city: 'Honolulu', label: 'Hawaï (UTC−10)' },
    { value: 'Pacific/Marquesas', city: 'Taiohae', label: 'Îles Marquises (UTC−09:30)' },
    { value: 'America/Anchorage', city: 'Anchorage', label: 'Alaska (UTC−09)' },
    { value: 'America/Los_Angeles', city: 'Los Angeles', label: 'Pacifique Nord-Américain (UTC−08)' },
    { value: 'America/Denver', city: 'Denver', label: 'Rocheuses (UTC−07)' },
    { value: 'America/Chicago', city: 'Chicago', label: 'Centre Nord-Américain (UTC−06)' },
    { value: 'America/Montreal', city: 'Montréal', label: 'Est Nord-Américain (UTC−05)' },
    { value: 'America/Halifax', city: 'Halifax', label: 'Atlantique Nord-Américain (UTC−04)' },
    { value: 'America/St_Johns', city: 'Saint-Jean', label: 'Terre-Neuve (UTC−03:30)' },
    { value: 'America/Sao_Paulo', city: 'São Paulo', label: 'Brésil (UTC−03)' },
    { value: 'America/Noronha', city: 'Fernando de Noronha', label: 'Atlantique Sud (UTC−02)' },
    { value: 'Atlantic/Azores', city: 'Açores', label: 'Açores (UTC−01)' },
    { value: 'Europe/London', city: 'Londres', label: 'Royaume-Uni (UTC+00)' },
    { value: 'Europe/Paris', city: 'Paris', label: 'Europe centrale (UTC+01)' },
    { value: 'Africa/Johannesburg', city: 'Johannesburg', label: 'Afrique australe (UTC+02)' },
    { value: 'Europe/Moscow', city: 'Moscou', label: 'Moscou (UTC+03)' },
    { value: 'Asia/Tehran', city: 'Téhéran', label: 'Iran (UTC+03:30)' },
    { value: 'Indian/Reunion', city: 'La Réunion', label: 'Océan Indien (UTC+04)' },
    { value: 'Asia/Kabul', city: 'Kaboul', label: 'Afghanistan (UTC+04:30)' },
    { value: 'Asia/Karachi', city: 'Karachi', label: 'Pakistan (UTC+05)' },
    { value: 'Asia/Kolkata', city: 'Kolkata', label: 'Inde (UTC+05:30)' },
    { value: 'Asia/Kathmandu', city: 'Katmandou', label: 'Népal (UTC+05:45)' },
    { value: 'Asia/Dhaka', city: 'Dacca', label: 'Bangladesh (UTC+06)' },
    { value: 'Asia/Yangon', city: 'Rangoun', label: 'Myanmar (UTC+06:30)' },
    { value: 'Asia/Bangkok', city: 'Bangkok', label: 'Indochine (UTC+07)' },
    { value: 'Asia/Singapore', city: 'Singapour', label: 'Asie du Sud-Est (UTC+08)' },
    { value: 'Australia/Eucla', city: 'Eucla', label: 'Australie centrale ouest (UTC+08:45)' },
    { value: 'Asia/Tokyo', city: 'Tokyo', label: 'Japon (UTC+09)' },
    { value: 'Australia/Adelaide', city: 'Adélaïde', label: 'Australie centrale (UTC+09:30)' },
    { value: 'Australia/Brisbane', city: 'Brisbane', label: 'Australie orientale (UTC+10)' },
    { value: 'Australia/Lord_Howe', city: 'Lord Howe', label: 'Île Lord Howe (UTC+10:30)' },
    { value: 'Pacific/Noumea', city: 'Nouméa', label: 'Nouvelle-Calédonie (UTC+11)' },
    { value: 'Pacific/Auckland', city: 'Auckland', label: 'Nouvelle-Zélande (UTC+12)' },
    { value: 'Pacific/Chatham', city: 'Chatham', label: 'Îles Chatham (UTC+12:45)' },
    { value: 'Pacific/Apia', city: 'Apia', label: 'Samoa (UTC+13)' },
    { value: 'Pacific/Kiritimati', city: 'Kiritimati', label: 'Îles de la Ligne (UTC+14)' },
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
    { value: 'rose', label: 'Rose poudré', previewClass: 'rose-preview' },
    { value: 'aurora', label: 'Aurore', previewClass: 'aurora-preview' },
    { value: 'sunset', label: 'Coucher de soleil', previewClass: 'sunset-preview' },
    { value: 'ocean', label: 'Océan', previewClass: 'ocean-preview' },
]

export function SettingsModal({ theme, language, timeZone, onThemeChange, onLanguageChange, onTimeZoneChange, onClose, onLogout }: Readonly<SettingsModalProps>) {
    const [currentTime, setCurrentTime] = useState(() => new Date())

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
                    <div><h3>Thème</h3><p>Choisissez l’apparence de l’interface.</p></div>
                    <div className="theme-options">
                        {themes.map(({ value, label, previewClass }) => <button type="button" className={`theme-option ${theme === value ? 'selected' : ''}`} onClick={() => onThemeChange(value)} aria-pressed={theme === value} key={value}><span className={`theme-preview ${previewClass}`} /> {label}</button>)}
                    </div>
                </div>

                <div className="settings-section">
                    <div><h3>Langue</h3><p>Définissez la langue de votre espace.</p></div>
                    <label className="settings-select" htmlFor="settings-language"><span className="visually-hidden">Langue</span><select id="settings-language" value={language} onChange={(event) => onLanguageChange(event.target.value)}>{languages.map(({ value, label }) => <option value={value} key={value}>{label}</option>)}</select></label>
                </div>

                <div className="settings-section">
                    <div><h3>Heure géographique</h3><p>Utilisée pour l’horodatage de vos données.</p></div>
                    <label className="settings-select" htmlFor="settings-time-zone"><span className="visually-hidden">Fuseau horaire</span><select id="settings-time-zone" value={timeZone} onChange={(event) => onTimeZoneChange(event.target.value)}>{timeZones.map(({ value, label }) => <option value={value} key={value}>{label}</option>)}</select></label>
                    <output className="geographic-time">{geographicTime}</output>
                </div>

                <footer className="settings-modal-footer">
                    <button type="button" className="logout-button" onClick={onLogout}>Se déconnecter</button>
                    <button type="button" className="save-settings-button" onClick={onClose}>Terminer</button>
                </footer>
            </section>
        </div>
    )
}
