import { createApiClient } from '@delivery/api-client'

export default defineNuxtPlugin(() => {
  const tenantId = useState<string | null>('admin-tenant', () => null)
  // Same origin (/v1 via proxy): the HttpOnly session cookie travels automatically; the client adds
  // X-Requested-With (CSRF check) and X-Tenant-Id (which of the staff member's cafes).
  const adminApi = createApiClient({ baseUrl: '', channel: 'web', staffTenantId: () => tenantId.value })
  return { provide: { adminApi } }
})
