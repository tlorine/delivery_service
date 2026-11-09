import type { components } from '@delivery/api-client'

export type BranchAdmin = components['schemas']['BranchAdminOut']

/** Branches of the current cafe and the selected one (remembered per device). */
export function useBranches() {
  const api = useAdminApi()
  const branches = useState<BranchAdmin[]>('admin-branches', () => [])
  const selectedId = useState<string | null>('admin-branch', () => null)
  const selected = computed(() => branches.value.find((b) => b.id === selectedId.value) ?? branches.value[0])

  async function load() {
    branches.value = await api.get('/v1/admin/branches')
    if (!branches.value.some((b) => b.id === selectedId.value)) {
      selectedId.value = branches.value[0]?.id ?? null
    }
  }

  const items = computed(() => branches.value.map((b) => ({ label: b.name, value: b.id })))
  return { branches, selectedId, selected, items, load }
}
