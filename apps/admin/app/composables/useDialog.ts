interface DialogState {
  open: boolean
  title: string
  message?: string
  input?: string
  withInput: boolean
  danger: boolean
  resolve?: (value: string | boolean | null) => void
}

/** In-app confirm/prompt (native dialogs are blocked or ugly in some mobile WebViews). */
export function useDialog() {
  const state = useState<DialogState>('admin-dialog', () => ({ open: false, title: '', withInput: false, danger: false }))

  function show(opts: Partial<DialogState>): Promise<string | boolean | null> {
    return new Promise((resolve) => {
      state.value = { open: true, title: '', withInput: false, danger: false, ...opts, resolve }
    })
  }

  function close(value: string | boolean | null) {
    state.value.resolve?.(value)
    state.value = { ...state.value, open: false, resolve: undefined }
  }

  return {
    state,
    close,
    confirm: async (title: string, message?: string, danger = true) => (await show({ title, message, danger })) === true,
    prompt: async (title: string, initial = '') => {
      const value = await show({ title, input: initial, withInput: true })
      return typeof value === 'string' && value.trim() ? value.trim() : null
    },
  }
}
