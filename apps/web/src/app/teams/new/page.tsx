import { CreateTeamForm } from "@/components/teams/create-team-form";
import { getRequestLocale } from "@/lib/i18n.server";

export default function CreateTeamPage() {
  const locale = getRequestLocale();

  return <CreateTeamForm locale={locale} />;
}
