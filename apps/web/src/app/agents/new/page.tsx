import { CreateAgentForm } from "@/components/agents/create-agent-form";
import { getRequestLocale } from "@/lib/i18n.server";

export default function CreateAgentPage() {
  const locale = getRequestLocale();

  return (
    <section className="mx-auto w-full max-w-6xl">
      <CreateAgentForm locale={locale} />
    </section>
  );
}
