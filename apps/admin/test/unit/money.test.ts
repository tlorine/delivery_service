import { describe, expect, it } from 'vitest'
import { minorToRubles, rublesToMinor } from '../../app/utils/money'

describe('rublesToMinor', () => {
  it('converts typed rubles to integer kopecks', () => {
    expect(rublesToMinor(390)).toBe(39_000)
    expect(rublesToMinor(390.5)).toBe(39_050)
    expect(rublesToMinor(0.1 + 0.2)).toBe(30) // float noise is rounded away
    expect(rublesToMinor(19.999)).toBe(2_000)
  })

  it('refuses negative and non-numeric input', () => {
    for (const bad of [-1, Number.NaN, Infinity, null, undefined]) {
      expect(() => rublesToMinor(bad as number)).toThrow(RangeError)
    }
  })

  it('round-trips for display', () => {
    expect(minorToRubles(rublesToMinor(123.45))).toBe(123.45)
  })
})
