import { useEffect, useRef } from 'react'
import type { ApiAlert } from '../../types/api'
import { formatAlertOrigin, formatDateTime } from '../../utils/formatters'

type CriticalAlertPopupProps = {
    alert: ApiAlert
    siteName: string
    onClose: () => void
}

export function CriticalAlertPopup({ alert, siteName, onClose }: Readonly<CriticalAlertPopupProps>) {
    const closeRef = useRef<HTMLButtonElement>(null)

    useEffect(() => {
        closeRef.current?.focus()
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') onClose()
        }
        document.addEventListener('keydown', closeOnEscape)
        return () => document.removeEventListener('keydown', closeOnEscape)
    }, [onClose])

    return (
        <div className="critical-alert-overlay">
            <section className="critical-alert-popup" role="alertdialog" aria-modal="true" aria-labelledby="critical-alert-title" aria-describedby="critical-alert-message">
                <div className="critical-alert-heading">
                    <div>
                        <span className="critical-alert-kicker">Alerte critique</span>
                        <h2 id="critical-alert-title">{siteName}</h2>
                    </div>
                    <button ref={closeRef} type="button" onClick={onClose} aria-label="Fermer l’alerte critique">×</button>
                </div>
                <p id="critical-alert-message">{alert.message}</p>
                <small>{formatAlertOrigin(alert.origin)} · {formatDateTime(alert.detected_at)}</small>
                <div className="critical-alert-actions">
                    <a href="#/alertes" onClick={onClose}>Voir les alertes</a>
                    <button type="button" onClick={onClose}>Fermer</button>
                </div>
            </section>
        </div>
    )
}
