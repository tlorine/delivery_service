import { describe, expect, it } from 'vitest'
import { ApiError, createApiClient, formatMoney } from '../../src'

function fakeFetch(status: number, body: unknown, seen: Request[] = []): typeof fetch {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    seen.push(new Request(input, init))
    return new Response(body === undefined ? null : JSON.stringify(body), { status })
  }
}

const EMPTY_CART = { id: 'x', currency: 'RUB', items: [], item_count: 0, subtotal_minor: 0, has_problems: false }

describe('createApiClient', () => {
  it('sends context headers, path params, query and JSON body', async () => {
    const seen: Request[] = []
    const api = createApiClient({
      baseUrl: 'https://api.platform.test',
      channel: 'mobile',
      clientVersion: '1.2.0',
      tenantSlug: () => 'demo',
      cartToken: () => 'cart-secret',
      fetch: fakeFetch(200, EMPTY_CART, seen),
    })
    const cart = await api.patch('/v1/cart/items/{item_id}', {
      path: { item_id: 'a b' },
      query: { branch_id: 'br-1' },
      body: { quantity: 2 },
    })
    expect(cart.subtotal_minor).toBe(0)
    const req = seen[0]!
    expect(req.url).toBe('https://api.platform.test/v1/cart/items/a%20b?branch_id=br-1')
    expect(req.method).toBe('PATCH')
    expect(req.headers.get('X-Client')).toBe('mobile/1.2.0')
    expect(req.headers.get('X-Tenant')).toBe('demo')
    expect(req.headers.get('X-Cart-Token')).toBe('cart-secret')
    expect(await req.json()).toEqual({ quantity: 2 })
  })

  it('turns problem+json into ApiError with code and checkout problems', async () => {
    const problem = {
      title: 'Request cannot be fulfilled',
      status: 422,
      code: 'outside_delivery_zone',
      detail: 'the address is outside the delivery area',
      extra: { problems: [{ code: 'outside_delivery_zone', detail: '...' }] },
    }
    const api = createApiClient({ baseUrl: 'http://cafe.test', channel: 'web', fetch: fakeFetch(422, problem) })
    const error: ApiError = await api.get('/v1/storefront').catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('outside_delivery_zone')
    expect(error.checkoutProblems).toHaveLength(1)
  })

  it('maps non-JSON and network failures to stable codes', async () => {
    const badGateway = createApiClient({
      baseUrl: '',
      channel: 'web',
      fetch: async () => new Response('<html>Bad gateway</html>', { status: 502 }),
    })
    const e1: ApiError = await badGateway.get('/v1/storefront').catch((e) => e)
    expect([e1.code, e1.status]).toEqual(['http_error', 502])

    const offline = createApiClient({
      baseUrl: '',
      channel: 'web',
      fetch: async () => {
        throw new TypeError('Failed to fetch')
      },
    })
    const e2: ApiError = await offline.get('/v1/storefront').catch((e) => e)
    expect([e2.code, e2.status]).toEqual(['network_error', 0])
  })
})

describe('formatMoney', () => {
  it('formats integer kopecks as rubles', () => {
    expect(formatMoney(141000).replace(/\s/g, ' ')).toBe('1 410 ₽')
    expect(formatMoney(12345).replace(/\s/g, ' ')).toBe('123,45 ₽')
  })

  it('refuses floats', () => {
    expect(() => formatMoney(12.5)).toThrow(TypeError)
  })
})
