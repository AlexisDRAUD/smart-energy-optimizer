import { useCallback, useEffect, useRef, useState } from 'react'

const DEFAULT_INTERVAL_MS = 60_000

type RefreshSnapshot<T> = {
    key: string
    data: T | null
    error: string | null
    lastSyncedAt: number | null
}

type AutoRefreshOptions<T> = {
    enabled: boolean
    key: string
    load: (signal: AbortSignal) => Promise<T>
    errorMessage: string
    intervalMs?: number
}

function isAbortError(cause: unknown) {
    return cause instanceof Error && cause.name === 'AbortError'
}

/** Charge immédiatement, puis au plus une fois par intervalle tant que la page est visible. */
export function useAutoRefresh<T>({ enabled, key, load, errorMessage, intervalMs = DEFAULT_INTERVAL_MS }: AutoRefreshOptions<T>) {
    const [snapshot, setSnapshot] = useState<RefreshSnapshot<T>>({ key, data: null, error: null, lastSyncedAt: null })
    const [isSyncing, setIsSyncing] = useState(false)
    const executeRef = useRef<() => Promise<void>>(async () => undefined)

    useEffect(() => {
        let active = true
        let running = false
        let controller: AbortController | null = null

        const execute = async () => {
            if (!active || !enabled || running) return
            running = true
            controller = new AbortController()
            setIsSyncing(true)
            try {
                const data = await load(controller.signal)
                if (active) setSnapshot({ key, data, error: null, lastSyncedAt: Date.now() })
            } catch (cause) {
                if (active && !isAbortError(cause)) {
                    setSnapshot((current) => ({
                        key,
                        data: current.key === key ? current.data : null,
                        error: cause instanceof Error ? cause.message : errorMessage,
                        lastSyncedAt: current.key === key ? current.lastSyncedAt : null,
                    }))
                }
            } finally {
                if (active) setIsSyncing(false)
                running = false
                controller = null
            }
        }

        executeRef.current = execute
        setSnapshot((current) => current.key === key ? current : { key, data: null, error: null, lastSyncedAt: null })
        void execute()

        const timer = window.setInterval(() => {
            if (document.visibilityState === 'visible') void execute()
        }, intervalMs)
        const onVisibilityChange = () => {
            if (document.visibilityState === 'visible') void execute()
        }
        document.addEventListener('visibilitychange', onVisibilityChange)

        return () => {
            active = false
            controller?.abort()
            window.clearInterval(timer)
            document.removeEventListener('visibilitychange', onVisibilityChange)
        }
    }, [enabled, errorMessage, intervalMs, key, load])

    const refresh = useCallback(() => executeRef.current(), [])
    const current = snapshot.key === key ? snapshot : { key, data: null, error: null, lastSyncedAt: null }
    return {
        data: current.data,
        error: current.error,
        lastSyncedAt: current.lastSyncedAt,
        isInitialLoading: isSyncing && current.data === null,
        isSyncing,
        refresh,
    }
}
