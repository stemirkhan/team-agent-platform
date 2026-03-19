import { fetchBootstrapStatus } from "@/lib/auth-client";
import { redirect } from "next/navigation";
import { RegisterForm } from "@/components/auth/register-form";
import { getRequestLocale } from "@/lib/i18n.server";

export default async function RegisterPage() {
  const locale = getRequestLocale();
  const bootstrapStatus = await fetchBootstrapStatus();

  if (bootstrapStatus.setup_required) {
    redirect("/setup");
  }
  if (!bootstrapStatus.allow_open_registration) {
    redirect("/auth/login");
  }

  return (
    <section className="mx-auto w-full max-w-6xl">
      <RegisterForm locale={locale} />
    </section>
  );
}
