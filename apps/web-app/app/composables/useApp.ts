function _useApp() {
  const route = useRoute()

  const isCartDrawerOpened = ref(false)
  const searchQuery = ref('')

  watch(
    () => route.fullPath,
    () => {
      isCartDrawerOpened.value = false
      searchQuery.value = ''
    },
  )

  return {
    isCartDrawerOpened,
    searchQuery,
  }
}

export const useApp = createSharedComposable(_useApp)
