import { RegisterForm } from "@/components/auth/register-form";
import { getRequestLocale } from "@/lib/i18n.server";

export default function RegisterPage() {
  const locale = getRequestLocale();

  return <RegisterForm locale={locale} />;
}
