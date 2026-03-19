import { fetchBootstrapStatus } from "@/lib/auth-client";
import { redirect } from "next/navigation";
import { LoginForm } from "@/components/auth/login-form";
import { getRequestLocale } from "@/lib/i18n.server";

export default async function LoginPage() {
  const locale = getRequestLocale();
  const bootstrapStatus = await fetchBootstrapStatus();

  if (bootstrapStatus.setup_required) {
    redirect("/setup");
  }

  return (
    <section className="mx-auto w-full max-w-6xl">
      <LoginForm locale={locale} allowOpenRegistration={bootstrapStatus.allow_open_registration} />
    </section>
  );
}
