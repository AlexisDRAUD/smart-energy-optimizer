import { useEffect, useState } from 'react'

/**
 * État React conservé dans le navigateur, pour qu'un réglage survive au
 * rechargement de la page. Ne convient qu'aux valeurs textuelles.
 */
export function useStoredState<T extends string>(key: string, initialValue: T) {
    const [value, setValue] = useState<T>(() => (localStorage.getItem(key) as T | null) ?? initialValue)

    useEffect(() => {
        localStorage.setItem(key, value)
    }, [key, value])

    return [value, setValue] as const
}
