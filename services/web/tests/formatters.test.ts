import { formatDateTime, formatEnergy, formatNumber, formatPercent, formatPower, formatQuality, formatSeverity, severityDot } from '../src/utils/formatters'

const singleSpaces = (value: string) => value.replace(/[\u00a0\u202f\s]+/g, ' ')

describe('formatters', () => {
  it('formatEnergy returns placeholder for null/undefined', () => {
    expect(formatEnergy(null)).toBe('Donnée indisponible')
    expect(formatEnergy(undefined)).toBe('Donnée indisponible')
  })

  it('formatEnergy formats numeric values with one decimal French locale and kWh', () => {
    expect(singleSpaces(formatEnergy(1234.56))).toBe('1 234,6 kWh')
  })

  it('formatPower uses kW', () => {
    expect(singleSpaces(formatPower(1234.56))).toBe('1 234,6 kW')
    expect(formatPower(null)).toBe('Donnée indisponible')
  })

  it('formatPercent and formatNumber fall back to a dash', () => {
    expect(singleSpaces(formatPercent(12.34))).toBe('12,3 %')
    expect(formatPercent(null)).toBe('—')
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber(2.5)).toBe('2,5')
  })

  it('formatDateTime returns a localized string with a time, and a dash for null', () => {
    expect(formatDateTime('2026-09-03T09:30:00.000Z')).toMatch(/:/)
    expect(formatDateTime(null)).toBe('—')
  })

  it('formatQuality maps the four values of the contract', () => {
    expect(formatQuality('good')).toBe('Bonne')
    expect(formatQuality('partial')).toBe('Partielle')
    expect(formatQuality('degraded')).toBe('Dégradée')
    expect(formatQuality('critical')).toBe('Critique')
  })

  it('formatSeverity maps the four severities of the contract', () => {
    expect(formatSeverity('low')).toBe('Faible')
    expect(formatSeverity('medium')).toBe('Moyenne')
    expect(formatSeverity('high')).toBe('Haute')
    expect(formatSeverity('critical')).toBe('Critique')
  })

  it('severityDot gives a colour to every severity', () => {
    expect(severityDot('critical')).toBe('red')
    expect(severityDot('high')).toBe('orange')
    expect(severityDot('medium')).toBe('blue')
    expect(severityDot('low')).toBe('blue')
  })
})
