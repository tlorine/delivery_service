/**
 * Tenant accent colour from data (branding.accent_color) with WCAG-based text colour on top of it,
 * so any cafe colour stays readable without a designer.
 */
const HEX_RE = /^#?([0-9a-f]{6}|[0-9a-f]{3})$/i
// Warm tomato; contrast with white text is 4.85 (WCAG AA).
export const DEFAULT_ACCENT = '#D2381F'

export function normalizeHex(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }
  const m = HEX_RE.exec(value.trim())
  if (!m) {
    return null
  }
  const hex = m[1]!.length === 3 ? Array.from(m[1]!, (c) => c + c).join('') : m[1]!
  return `#${hex.toUpperCase()}`
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16) / 255)
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)) as [number, number, number]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrastRatio(a: string, b: string): number {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (l1 + 0.05) / (l2 + 0.05)
}

/** White or near-black text, whichever reads better on the accent. */
export function textOn(accent: string): '#FFFFFF' | '#1C1B19' {
  return contrastRatio(accent, '#FFFFFF') >= contrastRatio(accent, '#1C1B19') ? '#FFFFFF' : '#1C1B19'
}

function darken(hex: string, amount: number): string {
  const parts = [1, 3, 5].map((i) => Math.round(Number.parseInt(hex.slice(i, i + 2), 16) * (1 - amount)))
  return `#${parts.map((p) => p.toString(16).padStart(2, '0')).join('').toUpperCase()}`
}

const AA = 4.5

/**
 * Accent for buttons and text on it. Mid-tone colours (e.g. #E5482B) reach AA with neither white nor black
 * text; then the accent is darkened in small steps, keeping its hue, until white text passes AA.
 */
export function brandTokens(accent: unknown): { accent: string, onAccent: string } {
  let color = normalizeHex(accent) ?? DEFAULT_ACCENT
  const text = textOn(color)
  if (contrastRatio(color, text) >= AA) {
    return { accent: color, onAccent: text }
  }
  for (let step = 1; step <= 20 && contrastRatio(color, '#FFFFFF') < AA; step++) {
    color = darken(color, 0.04)
  }
  return { accent: color, onAccent: '#FFFFFF' }
}
