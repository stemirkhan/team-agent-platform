import { cookies } from "next/headers";

import { ACCESS_TOKEN_COOKIE_NAME } from "@/lib/auth-client";

export function getRequestAccessToken(): string | null {
  return cookies().get(ACCESS_TOKEN_COOKIE_NAME)?.value ?? null;
}
