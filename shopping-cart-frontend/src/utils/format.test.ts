import { describe, it, expect } from 'vitest'
import { formatCurrency, formatDate, formatDateTime } from './format'

describe('formatCurrency', () => {
  it('formats USD correctly', () => {
    expect(formatCurrency(99.99, 'USD')).toContain('99,99')
    expect(formatCurrency(99.99, 'USD')).toContain('US$')
  })

  it('formats EUR correctly', () => {
    expect(formatCurrency(50, 'EUR')).toContain('50')
  })

  it('uses VND as default currency', () => {
    expect(formatCurrency(100)).toContain('100')
    expect(formatCurrency(100)).toContain('₫')
  })

  it('handles zero', () => {
    expect(formatCurrency(0)).toContain('0')
  })

  it('handles large numbers', () => {
    expect(formatCurrency(1000000)).toContain('1.000.000')
  })
})

describe('formatDate', () => {
  it('formats date string correctly', () => {
    // Use ISO format with timezone to avoid timezone issues
    const result = formatDate('2024-01-15T12:00:00Z')
    expect(result).toContain('tháng 1')
    expect(result).toContain('2024')
  })

  it('formats Date object correctly', () => {
    const date = new Date(2024, 0, 15, 12, 0, 0) // January 15, 2024 at noon
    const result = formatDate(date)
    expect(result).toContain('tháng 1')
    expect(result).toContain('15')
    expect(result).toContain('2024')
  })
})

describe('formatDateTime', () => {
  it('formats date and time correctly', () => {
    const result = formatDateTime('2024-01-15T10:30:00')
    expect(result).toContain('thg 1')
    expect(result).toContain('15')
    expect(result).toContain('2024')
  })
})
