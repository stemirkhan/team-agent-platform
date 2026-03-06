"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearAccessToken, fetchCurrentUser, getAccessToken, type AuthUser } from "@/lib/auth-client";
import { addTeamItem, publishTeam, type Team } from "@/lib/api";

type TeamBuilderControlsProps = {
  teamSlug: string;
  teamStatus: Team["status"];
};

export function TeamBuilderControls({ teamSlug, teamStatus }: TeamBuilderControlsProps) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [agentSlug, setAgentSlug] = useState("");
  const [roleName, setRoleName] = useState("");
  const [isRequired, setIsRequired] = useState(true);
  const [orderIndex, setOrderIndex] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function resolveUser() {
      const currentToken = getAccessToken();
      if (!currentToken) {
        if (!cancelled) {
          setLoading(false);
          setUser(null);
          setToken(null);
        }
        return;
      }

      if (!cancelled) {
        setToken(currentToken);
        setLoading(true);
      }

      try {
        const currentUser = await fetchCurrentUser(currentToken);
        if (!cancelled) {
          setUser(currentUser);
          setLoading(false);
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setUser(null);
          setToken(null);
          setLoading(false);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, []);

  async function onAddItem(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      router.push("/auth/login");
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await addTeamItem(
        teamSlug,
        {
          agent_slug: agentSlug.trim(),
          role_name: roleName.trim(),
          order_index: orderIndex.trim().length > 0 ? Number(orderIndex) : undefined,
          is_required: isRequired
        },
        token
      );

      setAgentSlug("");
      setRoleName("");
      setOrderIndex("");
      setIsRequired(true);
      setSuccessMessage("Team item added.");
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to add team item.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onPublishTeam() {
    if (!token) {
      router.push("/auth/login");
      return;
    }

    setPublishing(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await publishTeam(teamSlug, token);
      setSuccessMessage("Team published.");
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to publish team.");
    } finally {
      setPublishing(false);
    }
  }

  if (loading) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">Checking authorization...</p>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="mb-2 text-lg font-bold text-slate-900">Team Builder</h2>
        <p className="text-sm text-slate-600">
          Login to manage team items and publish this team.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Team Builder</h2>
          <p className="text-sm text-slate-600">Signed in as {user.display_name}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link className="text-sm font-semibold text-brand-700 hover:text-brand-900" href="/agents">
            Browse agents
          </Link>
          {teamStatus !== "published" ? (
            <Button disabled={publishing} onClick={onPublishTeam} type="button" variant="secondary">
              {publishing ? "Publishing..." : "Publish Team"}
            </Button>
          ) : (
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
              Published
            </span>
          )}
        </div>
      </div>

      <form className="space-y-3" onSubmit={onAddItem}>
        <label className="block text-sm font-semibold text-slate-700">
          Agent slug
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            minLength={2}
            onChange={(event) => setAgentSlug(event.target.value)}
            placeholder="api-auditor"
            required
            type="text"
            value={agentSlug}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700">
          Role name
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            minLength={2}
            onChange={(event) => setRoleName(event.target.value)}
            placeholder="reviewer"
            required
            type="text"
            value={roleName}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700">
          Order index (optional)
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            min={0}
            onChange={(event) => setOrderIndex(event.target.value)}
            placeholder="auto"
            type="number"
            value={orderIndex}
          />
        </label>

        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input
            checked={isRequired}
            onChange={(event) => setIsRequired(event.target.checked)}
            type="checkbox"
          />
          Required role
        </label>

        {errorMessage ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </p>
        ) : null}

        {successMessage ? (
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {successMessage}
          </p>
        ) : null}

        <Button disabled={submitting} type="submit">
          {submitting ? "Adding..." : "Add Team Item"}
        </Button>
      </form>
    </section>
  );
}
