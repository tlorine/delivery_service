import type { ModifierGroup } from '@delivery/api-client'

/** UI-side helpers for a modifier selection. The server re-validates everything (pricing module). */
export function selectionExtraMinor(groups: ModifierGroup[], selection: Record<string, number>): number {
  let total = 0
  for (const g of groups) {
    for (const m of g.modifiers) {
      total += m.price_minor * (selection[m.id] ?? 0)
    }
  }
  return total
}

export function selectionIsComplete(groups: ModifierGroup[], selection: Record<string, number>): boolean {
  return groups.every((g) => {
    const n = g.modifiers.reduce((sum, m) => sum + (selection[m.id] ?? 0), 0)
    return n >= g.min_selected && n <= g.max_selected
  })
}
