import { redirect } from "next/navigation";

import { BootstrapSetupForm } from "@/components/auth/bootstrap-setup-form";
import { fetchBootstrapStatus } from "@/lib/auth-client";
import { getRequestLocale } from "@/lib/i18n.server";

export default async function SetupPage() {
  const locale = getRequestLocale();
  const bootstrapStatus = await fetchBootstrapStatus();

  if (!bootstrapStatus.setup_required) {
    redirect("/runs");
  }

  return (
    <section className="mx-auto w-full max-w-6xl">
      <BootstrapSetupForm
        initialAllowOpenRegistration={bootstrapStatus.allow_open_registration}
        locale={locale}
      />
    </section>
  );
}
