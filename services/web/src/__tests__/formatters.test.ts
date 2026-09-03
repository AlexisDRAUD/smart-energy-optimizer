import { describe, it, expect } from 'vitest'
import { getReadingValue, formatEnergy, formatDateTime, formatQuality } from '../utils/formatters'

describe('formatters', () => {
  it('getReadingValue prefers raw if present', () => {
    const reading = { consumption_kwh_raw: 12.345, consumption_kwh_imputed: 99.9 } as any
    expect(getReadingValue(reading)).toBe(12.345)
  })

  it('getReadingValue falls back to imputed when raw absent', () => {
    const reading = { consumption_kwh_raw: null, consumption_kwh_imputed: 42 } as any
    expect(getReadingValue(reading)).toBe(42)
  })

  it('formatEnergy returns placeholder for null/undefined', () => {
    expect(formatEnergy(null)).toBe('Donnée indisponible')
    expect(formatEnergy(undefined)).toBe('Donnée indisponible')
  })

  it('formatEnergy formats numeric values with one decimal French locale and kWh', () => {
    // 1234.56 -> "1 234,6 kWh" in fr-FR (non-breaking space)
    const out = formatEnergy(1234.56)
    expect(out).toContain('kWh')
    expect(out).toMatch(/1234|1.234|1\s234|1\u00A0234/) // tolerate different spacing representations
  })

  it('formatDateTime returns a non-empty localized string including time', () => {
    const iso = '2026-09-03T09:30:00.000Z'
    const s = formatDateTime(iso)
    expect(typeof s).toBe('string')
    expect(s.length).toBeGreaterThan(0)
    // should include a colon for the time portion
    expect(s).toMatch(/:/)
  })

  it('formatQuality maps quality codes to French labels', () => {
    expect(formatQuality('good')).toBe('Bonne')
    expect(formatQuality('partial')).toBe('Partielle')
    expect(formatQuality('degraded')).toBe('Dégradée')
    expect(formatQuality('critical')).toBe('Critique')
    expect(formatQuality('predicted')).toBe('Prédite')
  })
})
