import type { LocaleValue, Options } from '@nextorders/food-schema'

const DIGIT_OR_SPACE_RE = /\d|\s/g

export const useOptionsStore = defineStore('options', () => {
  const storefront = useStorefrontStore()
  const options = computed(() => storefront.data ? optionsView(storefront.data) : null)

  const selectorTitleValues = computed(() => options.value?.selectorTitle ?? [])
  const selectorDescriptionValues = computed(() => options.value?.selectorDescription)
  const logoUrl = computed(() => options.value?.logoUrl)
  const headLinks = computed<Options['headLinks']>(() => [])
  const headScripts = computed<Options['headScripts']>(() => [])
  const headStyles = computed<Options['headStyles']>(() => [])
  const availableLocales = computed(() => options.value?.availableLocales ?? [])
  const currencyCode = computed(() => options.value?.currencyCode)
  const countryCode = computed(() => options.value?.countryCode)
  const defaultLocale = computed(() => options.value?.defaultLocale)
  const addressSuggestEnabled = computed(() => options.value?.addressSuggestEnabled ?? false)
  const deliveryZonesEnabled = computed(() => options.value?.deliveryZonesEnabled ?? false)
  const deliveryZoneNotFoundMessageValues = computed(() => options.value?.deliveryZoneNotFoundMessage)

  const { locale, locales } = useI18n()

  const selectorTitle = computed(() => getLocaleValue(selectorTitleValues.value))
  const selectorDescription = computed(() => getLocaleValue(selectorDescriptionValues.value))

  const appLocale = computed(() => locales.value.find((l) => l.code === locale.value))
  const currencySign = computed<string>(() => getCurrencySymbol())
  const deliveryZoneNotFoundMessage = computed(() => getLocaleValue(deliveryZoneNotFoundMessageValues.value))

  async function update() {
    await storefront.update()
  }

  function getLocaleValue(values: LocaleValue[] | undefined): string {
    try {
      if (!values || !Array.isArray(values)) {
        return ''
      }

      const hasCurrentLocale = values.find((n) => n.locale === locale.value)
      if (!hasCurrentLocale) {
        return values.find((v) => v.locale === defaultLocale.value)?.value ?? ''
      }

      return hasCurrentLocale.value
    } catch {
      return ''
    }
  }

  /** `amount` is a display value in major units (rubles), produced by the adapter. */
  function formatCurrency(amount: number): string {
    try {
      return new Intl.NumberFormat(appLocale.value?.language, { maximumFractionDigits: 2 }).format(amount)
    } catch {
      return amount.toString()
    }
  }

  function getCurrencySymbol(): string {
    try {
      const formatter = new Intl.NumberFormat(appLocale.value?.language, {
        style: 'currency',
        currency: currencyCode.value,
        currencyDisplay: 'symbol',
        // Minimize the output of a number - we only need the symbol
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      })
      // Format zero to get only the currency symbol
      return formatter.format(0).replace(DIGIT_OR_SPACE_RE, '').trim()
    } catch {
      return currencyCode.value ?? ''
    }
  }

  return {
    logoUrl,
    headLinks,
    headScripts,
    headStyles,
    availableLocales,
    countryCode,
    currencyCode,
    defaultLocale,
    addressSuggestEnabled,
    deliveryZonesEnabled,

    selectorTitle,
    selectorDescription,
    currencySign,
    deliveryZoneNotFoundMessage,

    update,
    getLocaleValue,
    formatCurrency,
  }
})
