export const SUPPORTED_LOCALES = ["ru", "en"] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "ru";
export const LOCALE_COOKIE_NAME = "locale";

export function resolveLocale(value: string | null | undefined): Locale {
  return value === "en" ? "en" : DEFAULT_LOCALE;
}

export function t(locale: Locale, copy: { ru: string; en: string }): string {
  return locale === "ru" ? copy.ru : copy.en;
}

export function formatStatus(
  locale: Locale,
  status: "draft" | "published" | "archived" | "hidden"
): string {
  switch (status) {
    case "draft":
      return t(locale, { ru: "черновик", en: "draft" });
    case "published":
      return t(locale, { ru: "опубликован", en: "published" });
    case "archived":
      return t(locale, { ru: "архив", en: "archived" });
    case "hidden":
      return t(locale, { ru: "скрыт", en: "hidden" });
    default:
      return status;
  }
}

export function formatVerificationStatus(
  locale: Locale,
  status: "none" | "validated" | "verified"
): string {
  switch (status) {
    case "none":
      return t(locale, { ru: "нет", en: "none" });
    case "validated":
      return t(locale, { ru: "проверен", en: "validated" });
    case "verified":
      return t(locale, { ru: "верифицирован", en: "verified" });
    default:
      return status;
  }
}

export function formatGeneralCategory(locale: Locale): string {
  return t(locale, { ru: "общее", en: "general" });
}

export function formatAuthLoading(locale: Locale): string {
  return t(locale, { ru: "проверка авторизации...", en: "checking authorization..." });
}
