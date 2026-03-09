"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, MessageSquarePlus, Tag, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LocalizedTimestamp } from "@/components/ui/localized-timestamp";
import {
  addGitHubIssueLabels,
  createGitHubIssueComment,
  removeGitHubIssueLabel,
  type GitHubIssueDetail
} from "@/lib/api";
import { t, type Locale } from "@/lib/i18n";

type GitHubIssueTrackerPanelProps = {
  locale: Locale;
  owner: string;
  repo: string;
  issueNumber: number;
  initialIssue: GitHubIssueDetail;
};

type PendingAction = "comment" | "labels" | `remove:${string}` | null;

export function GitHubIssueTrackerPanel({
  locale,
  owner,
  repo,
  issueNumber,
  initialIssue
}: GitHubIssueTrackerPanelProps) {
  const router = useRouter();

  const [issue, setIssue] = useState(initialIssue);
  const [commentBody, setCommentBody] = useState("");
  const [labelInput, setLabelInput] = useState("");
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setIssue(initialIssue);
  }, [initialIssue]);

  async function submitComment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = commentBody.trim();
    if (!body) {
      return;
    }

    setPendingAction("comment");
    setErrorMessage(null);

    try {
      const nextIssue = await createGitHubIssueComment(owner, repo, issueNumber, { body });
      setIssue(nextIssue);
      setCommentBody("");
      router.refresh();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось добавить комментарий.", en: "Failed to add comment." })
      );
    } finally {
      setPendingAction(null);
    }
  }

  async function submitLabels(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const labels = labelInput
      .split(",")
      .map((label) => label.trim())
      .filter(Boolean);

    if (labels.length === 0) {
      return;
    }

    setPendingAction("labels");
    setErrorMessage(null);

    try {
      const nextIssue = await addGitHubIssueLabels(owner, repo, issueNumber, { labels });
      setIssue(nextIssue);
      setLabelInput("");
      router.refresh();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось обновить labels.", en: "Failed to update labels." })
      );
    } finally {
      setPendingAction(null);
    }
  }

  async function handleRemoveLabel(label: string) {
    setPendingAction(`remove:${label}`);
    setErrorMessage(null);

    try {
      const nextIssue = await removeGitHubIssueLabel(owner, repo, issueNumber, label);
      setIssue(nextIssue);
      router.refresh();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось удалить label.", en: "Failed to remove label." })
      );
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <section className="space-y-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-slate-900 dark:text-slate-50">
            {t(locale, { ru: "Tracker actions", en: "Tracker actions" })}
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru: "Комментарий и labels применяются через локальный gh CLI и сразу перечитывают issue.",
              en: "Comments and labels are applied through the local gh CLI and immediately refresh the issue."
            })}
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-zinc-900/70 dark:text-slate-300">
          {t(locale, {
            ru: `${issue.comments_count} комментариев`,
            en: `${issue.comments_count} comments`
          })}
        </span>
      </div>

      {errorMessage ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
          {errorMessage}
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-5">
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
            <div className="mb-3 flex items-center gap-2 text-slate-900 dark:text-slate-50">
              <Tag className="h-4 w-4" />
              <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Labels", en: "Labels" })}
              </h3>
            </div>

            <div className="mb-4 flex flex-wrap gap-2">
              {issue.labels.length > 0 ? (
                issue.labels.map((label) => (
                  <span
                    className="inline-flex items-center gap-1.5 rounded-full bg-slate-200 px-3 py-1 text-xs font-semibold text-slate-700 dark:bg-zinc-800 dark:text-slate-200"
                    key={label}
                  >
                    {label}
                    <button
                      aria-label={`${t(locale, { ru: "Удалить label", en: "Remove label" })}: ${label}`}
                      className="rounded-full p-0.5 text-slate-500 transition hover:bg-slate-300 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-zinc-700 dark:hover:text-slate-100"
                      disabled={pendingAction !== null}
                      onClick={() => void handleRemoveLabel(label)}
                      type="button"
                    >
                      {pendingAction === `remove:${label}` ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <X className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </span>
                ))
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Labels пока нет.", en: "No labels yet." })}
                </p>
              )}
            </div>

            <form className="space-y-3" onSubmit={submitLabels}>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Добавить labels", en: "Add labels" })}
                <input
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setLabelInput(event.target.value)}
                  placeholder={t(locale, {
                    ru: "bug, needs-review",
                    en: "bug, needs-review"
                  })}
                  type="text"
                  value={labelInput}
                />
              </label>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t(locale, {
                  ru: "Используй запятые, если нужно добавить несколько labels за один вызов.",
                  en: "Use commas when you want to add multiple labels in one request."
                })}
              </p>
              <Button disabled={pendingAction !== null || labelInput.trim().length === 0} type="submit">
                {pendingAction === "labels"
                  ? t(locale, { ru: "Обновление...", en: "Updating..." })
                  : t(locale, { ru: "Добавить labels", en: "Add labels" })}
              </Button>
            </form>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
            <div className="mb-3 flex items-center gap-2 text-slate-900 dark:text-slate-50">
              <MessageSquarePlus className="h-4 w-4" />
              <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Добавить комментарий", en: "Add comment" })}
              </h3>
            </div>

            <form className="space-y-3" onSubmit={submitComment}>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Текст комментария", en: "Comment body" })}
                <textarea
                  className="mt-1 min-h-32 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setCommentBody(event.target.value)}
                  placeholder={t(locale, {
                    ru: "Напиши краткий статус, решение или уточнение по issue.",
                    en: "Write a short status update, solution note, or clarification for this issue."
                  })}
                  value={commentBody}
                />
              </label>
              <Button disabled={pendingAction !== null || commentBody.trim().length === 0} type="submit">
                {pendingAction === "comment"
                  ? t(locale, { ru: "Отправка...", en: "Submitting..." })
                  : t(locale, { ru: "Добавить комментарий", en: "Add comment" })}
              </Button>
            </form>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
          <h3 className="mb-4 text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
            {t(locale, { ru: "Комментарии issue", en: "Issue comments" })}
          </h3>

          {issue.comments.length > 0 ? (
            <ul className="space-y-3">
              {issue.comments.map((comment, index) => (
                <li
                  className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
                  key={comment.id ?? `${comment.author_login ?? "unknown"}-${comment.created_at ?? index}`}
                >
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    <span>{comment.author_login ?? t(locale, { ru: "неизвестный автор", en: "unknown author" })}</span>
                    <LocalizedTimestamp
                      emptyLabel={t(locale, { ru: "время неизвестно", en: "time unavailable" })}
                      locale={locale}
                      timeStyle="short"
                      value={comment.created_at}
                    />
                  </div>
                  <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-slate-700 dark:text-slate-200">
                    {comment.body}
                  </pre>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Комментариев пока нет.", en: "No comments yet." })}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
