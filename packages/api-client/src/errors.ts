/** RFC 9457 problem details as returned by the backend (docs/architecture/api-contract.md). */
export interface Problem {
  type?: string
  title: string
  status: number
  code: string
  detail?: string
  errors?: { loc: (string | number)[], code: string, message: string }[]
  extra?: Record<string, unknown>
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly problem: Problem

  constructor(problem: Problem) {
    super(problem.detail ?? problem.title)
    this.name = 'ApiError'
    this.status = problem.status
    this.code = problem.code
    this.problem = problem
  }

  /** Problems found at checkout (all of them, not only the first). */
  get checkoutProblems(): { code: string, detail: string, item_id?: string | null }[] {
    const list = this.problem.extra?.problems
    return Array.isArray(list) ? list as { code: string, detail: string, item_id?: string | null }[] : []
  }
}

export function toProblem(status: number, body: unknown): Problem {
  if (body && typeof body === 'object' && 'code' in body && typeof (body as Problem).code === 'string') {
    return { ...(body as Problem), status }
  }
  // Proxy errors, HTML pages, network failures: keep a stable code for the UI.
  return { status, title: 'Unexpected response', code: status === 0 ? 'network_error' : 'http_error' }
}
