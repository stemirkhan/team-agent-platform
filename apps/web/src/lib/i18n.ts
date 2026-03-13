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

export function formatRunStatus(
  locale: Locale,
  status:
    | "queued"
    | "preparing"
    | "cloning_repo"
    | "materializing_team"
    | "running_setup"
    | "starting_codex"
    | "running"
    | "interrupted"
    | "resuming"
    | "running_checks"
    | "committing"
    | "pushing"
    | "creating_pr"
    | "completed"
    | "failed"
    | "cancelled"
): string {
  switch (status) {
    case "queued":
      return t(locale, { ru: "в очереди", en: "queued" });
    case "preparing":
      return t(locale, { ru: "подготовка", en: "preparing" });
    case "cloning_repo":
      return t(locale, { ru: "клонирование", en: "cloning repo" });
    case "materializing_team":
      return t(locale, { ru: "материализация команды", en: "materializing team" });
    case "running_setup":
      return t(locale, { ru: "setup", en: "running setup" });
    case "starting_codex":
      return t(locale, { ru: "старт Codex", en: "starting Codex" });
    case "running":
      return t(locale, { ru: "выполняется", en: "running" });
    case "interrupted":
      return t(locale, { ru: "прерван", en: "interrupted" });
    case "resuming":
      return t(locale, { ru: "возобновление", en: "resuming" });
    case "running_checks":
      return t(locale, { ru: "проверки", en: "running checks" });
    case "committing":
      return t(locale, { ru: "коммит", en: "committing" });
    case "pushing":
      return t(locale, { ru: "пуш", en: "pushing" });
    case "creating_pr":
      return t(locale, { ru: "создание PR", en: "creating PR" });
    case "completed":
      return t(locale, { ru: "завершен", en: "completed" });
    case "failed":
      return t(locale, { ru: "ошибка", en: "failed" });
    case "cancelled":
      return t(locale, { ru: "отменен", en: "cancelled" });
    default:
      return status;
  }
}
