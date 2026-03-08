import { CreateAgentForm } from "@/components/agents/create-agent-form";
import { getRequestLocale } from "@/lib/i18n.server";

export default function CreateAgentPage() {
  const locale = getRequestLocale();

  return <CreateAgentForm locale={locale} />;
}
