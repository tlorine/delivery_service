/**
 * The admin's only conversion from typed rubles to API minor units (ADR-0008).
 * Inputs are rounded to whole kopecks; negative or non-finite values are refused.
 */
export function rublesToMinor(rubles: number | null | undefined): number {
  if (rubles === null || rubles === undefined || !Number.isFinite(rubles) || rubles < 0) {
    throw new RangeError('amount must be a non-negative number')
  }
  return Math.round(rubles * 100)
}

export function minorToRubles(minor: number): number {
  return minor / 100
}
