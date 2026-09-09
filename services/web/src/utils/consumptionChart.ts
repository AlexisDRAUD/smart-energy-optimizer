import { periods, type Period } from '../data/periods'

export type ChartPoint = { time: number; value: number | null; segmentStart?: boolean }

/** Elapsed UTC hours, independent of local daylight-saving transitions. */
export function chartWindow(period: Period, now = Date.now()) {
    const hours = periods.find((item) => item.value === period)!.hours
    return { start: new Date(now - hours * 3600000).toISOString(), end: new Date(now).toISOString() }
}

/** Keep native points; only separate paths at nulls and missing samples. */
export function chartSegments(points: ChartPoint[], start: number, end: number, cadenceSeconds: number) {
    const segments: ChartPoint[][] = []
    let segment: ChartPoint[] = []
    const serverDefinesContinuity = points.some((point) => point.segmentStart !== undefined)
    for (const point of [...points].sort((a, b) => a.time - b.time)) {
        if (point.time < start || point.time >= end) continue
        const previous = segment[segment.length - 1]
        const missingInterval = serverDefinesContinuity
            ? point.segmentStart === true && Boolean(previous)
            : Boolean(previous && point.time - previous.time > cadenceSeconds * 1000)
        if (point.value === null || missingInterval) {
            if (segment.length) segments.push(segment)
            segment = []
        }
        if (point.value !== null) segment.push(point)
    }
    if (segment.length) segments.push(segment)
    return segments
}
