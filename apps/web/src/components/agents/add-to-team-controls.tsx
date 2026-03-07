"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearAccessToken, fetchCurrentUser, getAccessToken, type AuthUser } from "@/lib/auth-client";
import { addTeamItem, fetchMyTeams, type Team } from "@/lib/api";

type AddToTeamControlsProps = {
  agentSlug: string;
};

export function AddToTeamControls({ agentSlug }: AddToTeamControlsProps) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [myTeams, setMyTeams] = useState<Team[]>([]);

  const [teamSlug, setTeamSlug] = useState("");
  const [teamSearch, setTeamSearch] = useState("");
  const [roleName, setRoleName] = useState("");
  const [isRequired, setIsRequired] = useState(true);
  const [orderIndex, setOrderIndex] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successTeamSlug, setSuccessTeamSlug] = useState<string | null>(null);

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
        const [currentUser, myTeamsPayload] = await Promise.all([
          fetchCurrentUser(currentToken),
          fetchMyTeams(currentToken, { status: "draft" })
        ]);
        if (!cancelled) {
          setUser(currentUser);
          setMyTeams(myTeamsPayload.items);
          if (myTeamsPayload.items.length > 0) {
            setTeamSlug(myTeamsPayload.items[0].slug);
          }
          setLoading(false);
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setUser(null);
          setToken(null);
          setMyTeams([]);
          setLoading(false);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, []);

  const filteredTeams = useMemo(() => {
    const normalizedSearch = teamSearch.trim().toLowerCase();
    return myTeams.filter((team) => {
      if (normalizedSearch.length === 0) {
        return true;
      }
      const haystack = `${team.title} ${team.slug}`.toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [myTeams, teamSearch]);

  useEffect(() => {
    if (filteredTeams.length === 0) {
      if (teamSlug !== "") {
        setTeamSlug("");
      }
      return;
    }

    if (!filteredTeams.some((team) => team.slug === teamSlug)) {
      setTeamSlug(filteredTeams[0].slug);
    }
  }, [filteredTeams, teamSlug]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      router.push("/auth/login");
      return;
    }

    const normalizedTeamSlug = teamSlug.trim();
    if (normalizedTeamSlug.length === 0) {
      setErrorMessage("Please select a team.");
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    setSuccessTeamSlug(null);

    try {
      await addTeamItem(
        normalizedTeamSlug,
        {
          agent_slug: agentSlug,
          role_name: roleName.trim(),
          order_index: orderIndex.trim().length > 0 ? Number(orderIndex) : undefined,
          is_required: isRequired
        },
        token
      );

      setRoleName("");
      setOrderIndex("");
      setIsRequired(true);
      setSuccessTeamSlug(normalizedTeamSlug);
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to add agent to team.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <section className="rounded-2xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5">
        <p className="text-sm text-slate-500 dark:text-slate-400">Checking authorization...</p>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="rounded-2xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5">
        <h2 className="mb-2 text-xl font-bold text-slate-900 dark:text-slate-50">Add To Team</h2>
        <p className="text-sm text-slate-600 dark:text-slate-300">Login to add this agent to your team.</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">Add To Team</h2>
          <p className="text-sm text-slate-600 dark:text-slate-300">Signed in as {user.display_name}</p>
        </div>
        <Link className="text-sm font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white" href="/teams/new">
          Create new team
        </Link>
      </div>

      {myTeams.length === 0 ? (
        <p className="rounded-lg border border-slate-200 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-800/70 px-3 py-2 text-sm text-slate-600 dark:text-slate-300">
          You do not have draft teams yet. Create a team first, then return here.
        </p>
      ) : null}

      <form className="space-y-3" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Search team
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
            onChange={(event) => setTeamSearch(event.target.value)}
            placeholder="Find by team title or slug"
            type="text"
            value={teamSearch}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Select team
          <select
            className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
            onChange={(event) => setTeamSlug(event.target.value)}
            required
            value={teamSlug}
          >
            {filteredTeams.length === 0 ? <option value="">No draft teams match search</option> : null}
            {filteredTeams.map((team) => (
              <option key={team.id} value={team.slug}>
                {team.title} ({team.slug}) [{team.status}]
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Role name
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
            minLength={2}
            onChange={(event) => setRoleName(event.target.value)}
            placeholder="reviewer"
            required
            type="text"
            value={roleName}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Order index (optional)
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
            min={0}
            onChange={(event) => setOrderIndex(event.target.value)}
            placeholder="auto"
            type="number"
            value={orderIndex}
          />
        </label>

        <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
          <input
            checked={isRequired}
            onChange={(event) => setIsRequired(event.target.checked)}
            type="checkbox"
          />
          Required role
        </label>

        {errorMessage ? (
          <p className="rounded-lg border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </p>
        ) : null}

        {successTeamSlug ? (
          <p className="rounded-lg border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            Agent was added to{" "}
            <Link className="font-semibold underline" href={`/teams/${successTeamSlug}`}>
              {successTeamSlug}
            </Link>
            .
          </p>
        ) : null}

        <Button disabled={submitting || filteredTeams.length === 0} type="submit">
          {submitting ? "Adding..." : "Add To Team"}
        </Button>
      </form>
    </section>
  );
}
