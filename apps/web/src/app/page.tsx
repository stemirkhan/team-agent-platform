import { fetchBootstrapStatus } from "@/lib/auth-client";
import { redirect } from "next/navigation";

export default async function HomePage() {
  const bootstrapStatus = await fetchBootstrapStatus();
  redirect(bootstrapStatus.setup_required ? "/setup" : "/runs");
}
