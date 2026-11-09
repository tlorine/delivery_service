import { describe, expect, it } from 'vitest'
import { forgetVenue, isVenueSlug, rememberVenue, venueFromInput, venueFromLink } from '../../app/utils/venues'

describe('venue links', () => {
  it('reads the cafe from app links, custom scheme and query', () => {
    expect(venueFromLink('https://app.example.ru/t/demo')).toBe('demo')
    expect(venueFromLink('https://app.example.ru/t/Shaurma-U-Morya?utm=qr')).toBe('shaurma-u-morya')
    expect(venueFromLink('cafeorders://t/demo')).toBe('demo')
    expect(venueFromLink('https://app.example.ru/?venue=demo')).toBe('demo')
  })

  it('rejects anything that is not a plain cafe slug', () => {
    for (const bad of ['not a url', 'https://app.example.ru/', 'https://app.example.ru/t/', 'https://x.ru/t/..%2Fadmin',
      'https://x.ru/t/a_b', 'https://x.ru/t/-demo', 'javascript:alert(1)']) {
      expect(venueFromLink(bad), bad).toBeNull()
    }
  })

  it('accepts a typed code or a pasted link', () => {
    expect(venueFromInput('  Demo ')).toBe('demo')
    expect(venueFromInput('https://app.example.ru/t/demo')).toBe('demo')
    expect(venueFromInput('')).toBeNull()
    expect(isVenueSlug('a'.repeat(64))).toBe(false)
  })
})

describe('my venues', () => {
  const v = (slug: string, openedAt: number) => ({ slug, name: slug, openedAt })

  it('keeps the most recently opened first, without duplicates, at most 20', () => {
    let list = [v('a', 1), v('b', 2)]
    list = rememberVenue(list, v('b', 3))
    expect(list.map((x) => x.slug)).toEqual(['b', 'a'])
    for (let i = 0; i < 30; i++) {
      list = rememberVenue(list, v(`c${i}`, 10 + i))
    }
    expect(list).toHaveLength(20)
    expect(list[0]!.slug).toBe('c29')
    expect(forgetVenue(list, 'c29').map((x) => x.slug)).not.toContain('c29')
  })
})
