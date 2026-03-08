import { cookies } from "next/headers";

import { LOCALE_COOKIE_NAME, resolveLocale, type Locale } from "@/lib/i18n";

export function getRequestLocale(): Locale {
  return resolveLocale(cookies().get(LOCALE_COOKIE_NAME)?.value);
}
