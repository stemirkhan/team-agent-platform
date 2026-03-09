import { RegisterForm } from "@/components/auth/register-form";
import { getRequestLocale } from "@/lib/i18n.server";

export default function RegisterPage() {
  const locale = getRequestLocale();

  return (
    <section className="mx-auto w-full max-w-6xl">
      <RegisterForm locale={locale} />
    </section>
  );
}
