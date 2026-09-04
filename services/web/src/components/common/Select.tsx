import { Icon } from './Icon'

export type SelectOption = { value: string; label: string }

type SelectProps = {
    id: string
    label: string
    value: string
    options: readonly SelectOption[]
    onChange: (value: string) => void
    disabled?: boolean
    hideLabel?: boolean
}

/**
 * Le seul champ de sélection de l'application.
 *
 * On garde le <select> natif : le clavier, la recherche à la frappe et le
 * comportement sur mobile viennent avec, sans code. En contrepartie la liste
 * qui s'ouvre est dessinée par le système d'exploitation et aucun CSS ne
 * l'atteint. Seul le champ fermé est stylé, et il l'est ici pour tout le
 * monde, ce qui évite d'avoir deux apparences selon la page.
 */
export function Select({ id, label, value, options, onChange, disabled = false, hideLabel = false }: Readonly<SelectProps>) {
    return (
        <label className="field" htmlFor={id}>
            <span className={hideLabel ? 'visually-hidden' : undefined}>{label}</span>
            <select id={id} value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled}>
                {options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
            </select>
            <Icon name="chevron" />
        </label>
    )
}
