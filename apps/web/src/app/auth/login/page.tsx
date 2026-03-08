import { LoginForm } from "@/components/auth/login-form";
import { getRequestLocale } from "@/lib/i18n.server";

export default function LoginPage() {
  const locale = getRequestLocale();

  return <LoginForm locale={locale} />;
}
