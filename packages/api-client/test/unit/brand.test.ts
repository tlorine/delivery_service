import { describe, expect, it } from 'vitest'
import { brandTokens, contrastRatio, DEFAULT_ACCENT, normalizeHex, textOn } from '../../src/brand'

describe('brand colour', () => {
  it('normalizes hex and rejects anything else (no CSS injection from data)', () => {
    expect(normalizeHex('#e5482b')).toBe('#E5482B')
    expect(normalizeHex('fc0')).toBe('#FFCC00')
    for (const bad of ['red', 'url(x)', '#12345', 'var(--x)', '#E5482B; color: red', 42, null]) {
      expect(normalizeHex(bad)).toBeNull()
    }
  })

  it('picks readable text for light and dark accents', () => {
    expect(textOn('#1F6F43')).toBe('#FFFFFF') // dark green
    expect(textOn('#FFD43B')).toBe('#1C1B19') // yellow coffee-shop accent
    // Any owner-chosen colour ends up readable (AA), mid-tones are darkened keeping the hue.
    for (const input of ['#D2381F', '#E5482B', '#FFD43B', '#1F6F43', '#7C3AED', '#F2F2F2', '#00A3FF', '#FF7A00']) {
      const { accent, onAccent } = brandTokens(input)
      expect(contrastRatio(accent, onAccent)).toBeGreaterThanOrEqual(4.5)
    }
    expect(brandTokens('#E5482B').accent).not.toBe('#E5482B')
  })

  it('default accent passes WCAG AA with white text', () => {
    expect(contrastRatio(DEFAULT_ACCENT, '#FFFFFF')).toBeGreaterThanOrEqual(4.5)
  })

  it('falls back to the platform accent', () => {
    expect(brandTokens(undefined)).toEqual({ accent: DEFAULT_ACCENT, onAccent: '#FFFFFF' })
    expect(brandTokens('#FFD43B').onAccent).toBe('#1C1B19')
  })
})
