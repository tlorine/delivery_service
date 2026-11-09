import type { OrderStatus } from '@delivery/api-client'

/** Russian labels for the cafe staff. The admin is Russian-only in the MVP (STATUS.md, tech debt). */
export const STATUS_LABEL: Record<OrderStatus, string> = {
  pending: 'Новый',
  confirmed: 'Подтверждён',
  preparing: 'Готовится',
  ready: 'Готов',
  delivering: 'В пути',
  completed: 'Выполнен',
  cancelled: 'Отменён',
  rejected: 'Отклонён',
}

/** Button text for moving an order to the status. */
export const ACTION_LABEL: Record<OrderStatus, string> = {
  pending: '',
  confirmed: 'Подтвердить',
  preparing: 'Начать готовить',
  ready: 'Готов',
  delivering: 'Передать курьеру',
  completed: 'Выдан / доставлен',
  cancelled: 'Отменить',
  rejected: 'Отклонить',
}

export const STATUS_COLOR: Record<OrderStatus, 'warning' | 'info' | 'primary' | 'success' | 'neutral' | 'error'> = {
  pending: 'warning',
  confirmed: 'info',
  preparing: 'info',
  ready: 'primary',
  delivering: 'primary',
  completed: 'success',
  cancelled: 'neutral',
  rejected: 'error',
}

export const PAYMENT_LABEL: Record<string, string> = {
  cash: 'Наличными',
  card_on_delivery: 'Картой при получении',
  online: 'Онлайн',
}

export const ROLE_LABEL: Record<string, string> = {
  owner: 'Владелец',
  manager: 'Менеджер',
  operator: 'Оператор',
}

export const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

const ERRORS: Record<string, string> = {
  invalid_credentials: 'Неверный email или пароль',
  session_expired: 'Сессия истекла, войдите снова',
  unauthorized: 'Нужно войти',
  insufficient_role: 'Недостаточно прав',
  tenant_access_denied: 'Нет доступа к этому заведению',
  invalid_status_transition: 'Нельзя перевести заказ в этот статус',
  reason_required: 'Укажите причину',
  product_has_orders: 'Товар уже заказывали — его можно только скрыть',
  variant_has_orders: 'Вариант уже заказывали — его можно только скрыть',
  modifier_has_orders: 'Добавку уже заказывали — её можно только скрыть',
  group_has_orders: 'Добавки группы уже заказывали — их можно только скрыть',
  category_not_empty: 'Сначала перенесите или удалите товары категории',
  last_variant: 'У товара должен остаться хотя бы один вариант',
  slug_taken: 'Такой адрес страницы уже занят',
  invalid_polygon: 'Неверные границы зоны',
  invalid_hours: 'Неверный интервал времени',
  no_fulfillment: 'Включите доставку или самовывоз',
  last_owner: 'У заведения должен остаться владелец',
  cannot_remove_self: 'Нельзя удалить самого себя',
  password_required: 'Для нового сотрудника нужен пароль',
  already_member: 'Этот сотрудник уже добавлен',
  validation_error: 'Проверьте заполнение полей',
  rate_limited: 'Слишком много попыток, подождите минуту',
  network_error: 'Нет соединения с сервером',
}

export function errorText(code: string | undefined): string {
  return (code && ERRORS[code]) || 'Не получилось. Попробуйте ещё раз'
}
