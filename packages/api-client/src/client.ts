import type { paths } from './schema'
import { ApiError, toProblem } from './errors'

export type ClientChannel = 'web' | 'telegram' | 'mobile'

export interface ApiClientOptions {
  /** '' for same-origin (web behind the proxy), absolute URL for SSR and mobile. */
  baseUrl: string
  channel: ClientChannel
  /** App version for X-Client (mobile builds live long; the server may answer 426). */
  clientVersion?: string
  /** Mobile only: tenant slug, used when the API host is the platform host. */
  tenantSlug?: () => string | undefined
  /** SSR only: forward the visitor's host so the server resolves the right tenant. */
  forwardedHost?: string
  cartToken?: () => string | undefined | null
  staffToken?: () => string | undefined | null
  /** Admin: which of the staff member's tenants to act on. */
  staffTenantId?: () => string | undefined | null
  fetch?: typeof globalThis.fetch
}

// ---- types derived from the generated OpenAPI schema --------------------------------------------
type Method = 'get' | 'post' | 'put' | 'patch' | 'delete'
type PathsFor<M extends Method> = {
  [P in keyof paths]: paths[P] extends { [K in M]: infer O } ? (O extends undefined | never ? never : P) : never
}[keyof paths]
type Operation<P extends keyof paths, M extends Method> = NonNullable<paths[P][M & keyof paths[P]]>
type Parameters_<O> = O extends { parameters: infer X } ? X : object
type RequestBodyOf<O> = O extends { requestBody?: infer R } ? NonNullable<R> : never
type JsonBody<O> = [RequestBodyOf<O>] extends [never] ? never
  : RequestBodyOf<O> extends { content: { 'application/json': infer B } } ? B : never
type Content<R> = R extends { content: { 'application/json': infer D } } ? D : undefined
/** 201 wins over 200: POST /v1/orders answers 201, or 200 with the same body on an idempotent replay. */
type Success<O> = O extends { responses: infer R }
  ? R extends { 201: infer A } ? Content<A> : R extends { 200: infer A } ? Content<A> : undefined
  : never

type QueryOf<O> = Parameters_<O> extends { query?: infer Q } ? Q : never
type PathOf<O> = Parameters_<O> extends { path: infer Q } ? Q : never
type HeaderOf<O> = Parameters_<O> extends { header?: infer Q } ? Q : never

export type RequestOptions<O> = {
  query?: QueryOf<O>
  // Declared headers of the operation plus context headers (e.g. X-Tenant when checking a cafe code).
  headers?: Partial<HeaderOf<O>> | Record<string, string | undefined>
  signal?: AbortSignal
} & ([PathOf<O>] extends [never] ? { path?: never } : { path: PathOf<O> })
& ([JsonBody<O>] extends [never] ? { body?: never } : { body: JsonBody<O> })

const PATH_PARAM_RE = /\{(\w+)\}/g

function buildUrl(base: string, template: string, path?: Record<string, unknown>, query?: Record<string, unknown>): string {
  const filled = template.replace(PATH_PARAM_RE, (_, key: string) => {
    const value = path?.[key]
    if (value === undefined) {
      throw new Error(`missing path parameter ${key}`)
    }
    return encodeURIComponent(String(value))
  })
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null) {
      continue
    }
    for (const item of Array.isArray(value) ? value : [value]) {
      params.append(key, String(item))
    }
  }
  const qs = params.toString()
  return `${base}${filled}${qs ? `?${qs}` : ''}`
}

/**
 * The one HTTP client for Web, Telegram Mini App, Mobile and Admin. Adds context headers and turns every
 * non-2xx response (and network failure) into an ApiError, so callers never parse errors themselves.
 */
export function createApiClient(options: ApiClientOptions) {
  const doFetch = options.fetch ?? globalThis.fetch.bind(globalThis)

  async function request<M extends Method, P extends PathsFor<M>>(
    method: M,
    path: P,
    init?: RequestOptions<Operation<P, M>>,
  ): Promise<Success<Operation<P, M>>> {
    const opts = (init ?? {}) as { query?: Record<string, unknown>, path?: Record<string, unknown>, body?: unknown, headers?: Record<string, string | undefined>, signal?: AbortSignal }
    const headers = new Headers({ 'Accept': 'application/json', 'X-Requested-With': 'fetch' })
    headers.set('X-Client', `${options.channel}/${options.clientVersion ?? 'dev'}`)
    const tenant = options.tenantSlug?.()
    if (tenant) {
      headers.set('X-Tenant', tenant)
    }
    if (options.forwardedHost) {
      headers.set('X-Forwarded-Host', options.forwardedHost)
    }
    const cart = options.cartToken?.()
    if (cart) {
      headers.set('X-Cart-Token', cart)
    }
    const staff = options.staffToken?.()
    if (staff) {
      headers.set('Authorization', `Bearer ${staff}`)
    }
    const staffTenant = options.staffTenantId?.()
    if (staffTenant) {
      headers.set('X-Tenant-Id', staffTenant)
    }
    for (const [key, value] of Object.entries(opts.headers ?? {})) {
      if (value !== undefined) {
        headers.set(key, value)
      }
    }
    let body: string | undefined
    if (opts.body !== undefined) {
      headers.set('Content-Type', 'application/json')
      body = JSON.stringify(opts.body)
    }

    let response: Response
    try {
      response = await doFetch(buildUrl(options.baseUrl, path as string, opts.path, opts.query), {
        method: method.toUpperCase(),
        headers,
        body,
        signal: opts.signal,
        credentials: 'include',
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw error
      }
      throw new ApiError(toProblem(0, undefined))
    }

    const text = response.status === 204 ? '' : await response.text()
    let data: unknown
    try {
      data = text ? JSON.parse(text) : undefined
    } catch {
      data = undefined
    }
    if (!response.ok) {
      throw new ApiError(toProblem(response.status, data))
    }
    return data as Success<Operation<P, M>>
  }

  return {
    request,
    get: <P extends PathsFor<'get'>>(path: P, init?: RequestOptions<Operation<P, 'get'>>) => request('get', path, init),
    post: <P extends PathsFor<'post'>>(path: P, init?: RequestOptions<Operation<P, 'post'>>) => request('post', path, init),
    patch: <P extends PathsFor<'patch'>>(path: P, init?: RequestOptions<Operation<P, 'patch'>>) => request('patch', path, init),
    delete: <P extends PathsFor<'delete'>>(path: P, init?: RequestOptions<Operation<P, 'delete'>>) => request('delete', path, init),
  }
}

export type ApiClient = ReturnType<typeof createApiClient>
