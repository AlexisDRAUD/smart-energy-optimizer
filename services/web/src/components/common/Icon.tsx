import type { ReactNode } from 'react'

export type IconName = 'grid' | 'bell' | 'building' | 'brain' | 'clock' | 'settings' | 'chevron' | 'refresh'

export function Icon({ name, size = 18 }: Readonly<{ name: IconName; size?: number }>) {
    const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
    const icons: Record<IconName, ReactNode> = {
        grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
        bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
        building: <><path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16" /><path d="M14 9h6v12M8 7h2M8 11h2M8 15h2M16 13h1M16 17h1" /></>,
        brain: <><path d="M12 5a3 3 0 0 0-5.8 1A3.5 3.5 0 0 0 5 12.5 3.5 3.5 0 0 0 8 18a3 3 0 0 0 4 1 3 3 0 0 0 4-1 3.5 3.5 0 0 0 3-5.5A3.5 3.5 0 0 0 17.8 6 3 3 0 0 0 12 5Z" /><path d="M12 5v14M8 9c1 0 2 .7 2 2M16 9c-1 0-2 .7-2 2M8 15c1 0 2-.7 2-2M16 15c-1 0-2 .7-2 2" /></>,
        clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
        settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.1 2.1-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5v.2h-3v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1-2.1-2.1.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H5.4v-3h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1 2.1-2.1.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.5v-.2h3v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1 2.1 2.1-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.2v3h-.2a1.7 1.7 0 0 0-1.5 1Z" /></>,
        chevron: <path d="m8 10 4 4 4-4" />,
        refresh: <><path d="M20 11a8 8 0 0 0-14.9-4L3 9" /><path d="M3 4v5h5M4 13a8 8 0 0 0 14.9 4L21 15" /><path d="M21 20v-5h-5" /></>,
    }
    return <svg {...common} aria-hidden="true">{icons[name]}</svg>
}
