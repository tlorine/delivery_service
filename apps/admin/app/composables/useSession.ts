import type { ApiError } from '@delivery/api-client'

export type StaffRole = 'owner' | 'manager' | 'operator'
const RANK: Record<StaffRole, number> = { operator: 1, manager: 2, owner: 3 }
const TENANT_KEY = 'admin-tenant-id'

interface Membership { tenant_id: string, tenant_name: string, tenant_slug: string, role: string }
interface Me { user_id: string, email: string, name: string, memberships: Membership[] }

/**
 * Staff session. The session secret is an HttpOnly cookie set by the API (ADR-0009); the page never
 * sees it. Only the chosen cafe id is remembered locally.
 */
export function useSession() {
  const me = useState<Me | null>('admin-me', () => null)
  const tenantId = useState<string | null>('admin-tenant', () => null)
  const { $adminApi } = useNuxtApp()

  const membership = computed(() => me.value?.memberships.find((m) => m.tenant_id === tenantId.value) ?? null)
  const role = computed(() => (membership.value?.role ?? null) as StaffRole | null)

  function can(minimum: StaffRole): boolean {
    return role.value !== null && RANK[role.value] >= RANK[minimum]
  }

  function choose(id: string) {
    tenantId.value = id
    try {
      localStorage.setItem(TENANT_KEY, id)
    } catch {}
  }

  function pickTenant(list: Membership[]) {
    let saved: string | null = null
    try {
      saved = localStorage.getItem(TENANT_KEY)
    } catch {}
    const next = list.find((m) => m.tenant_id === saved) ?? list[0]
    if (next) {
      choose(next.tenant_id)
    }
  }

  async function load(): Promise<boolean> {
    try {
      me.value = await $adminApi.get('/v1/admin/auth/me')
      pickTenant(me.value.memberships)
      return true
    } catch (e) {
      if ((e as ApiError).status === 401) {
        me.value = null
        return false
      }
      throw e
    }
  }

  async function login(email: string, password: string) {
    const result = await $adminApi.post('/v1/admin/auth/login', { body: { email, password } })
    me.value = { user_id: result.user_id, email: result.email, name: result.name, memberships: result.memberships }
    pickTenant(result.memberships)
  }

  async function logout() {
    try {
      await $adminApi.post('/v1/admin/auth/logout')
    } finally {
      me.value = null
      await navigateTo('/login')
    }
  }

  return { me, tenantId, membership, role, can, choose, load, login, logout }
}
