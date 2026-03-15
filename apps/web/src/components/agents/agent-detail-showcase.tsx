"use client";

import {
  Bot,
  FileCode2,
  FileText,
  FolderTree,
  Package2,
  Plus,
  Save,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Trash2
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearAccessToken, fetchCurrentUser, getAccessToken, type AuthUser } from "@/lib/auth-client";
import {
  type Agent,
  type AgentMarkdownFile,
  type AgentSkill,
  type RuntimeTarget,
  updateAgent
} from "@/lib/api";
import {
  formatAuthLoading,
  formatGeneralCategory,
  formatStatus,
  formatVerificationStatus,
  t,
  type Locale
} from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { ExportControls } from "@/components/exports/export-controls";

type AgentDetailShowcaseProps = {
  agent: Agent;
  locale: Locale;
};

type AgentPageTabId = "overview" | "files" | "export";
type AssetFilter = "all" | "markdown" | "skill";
type TreeNode = {
  children: Map<string, TreeNode>;
  isFile: boolean;
};

type EditableSkill = AgentSkill & {
  clientId: string;
};

type EditableMarkdownFile = AgentMarkdownFile & {
  clientId: string;
};

type ExplorerAsset = {
  id: string;
  kind: "markdown" | "skill";
  label: string;
  path: string;
  description: string | null;
  content: string;
};

function readNestedString(
  source: Record<string, unknown> | null | undefined,
  ...path: string[]
): string | null {
  let current: unknown = source;
  for (const key of path) {
    if (!current || typeof current !== "object") {
      return null;
    }
    current = (current as Record<string, unknown>)[key];
  }

  if (typeof current !== "string") {
    return null;
  }

  const normalized = current.trim();
  return normalized.length > 0 ? normalized : null;
}

function createTreeNode(): TreeNode {
  return { children: new Map<string, TreeNode>(), isFile: false };
}

function buildTreeLines(paths: string[]): string[] {
  const root = createTreeNode();

  for (const path of paths) {
    const parts = path.split("/").filter(Boolean);
    let current = root;

    parts.forEach((part, index) => {
      const existing = current.children.get(part);
      if (existing) {
        if (index === parts.length - 1) {
          existing.isFile = true;
        }
        current = existing;
        return;
      }

      const next = createTreeNode();
      if (index === parts.length - 1) {
        next.isFile = true;
      }
      current.children.set(part, next);
      current = next;
    });
  }

  function render(node: TreeNode, prefix: string): string[] {
    const entries = Array.from(node.children.entries()).sort(([leftName, leftNode], [rightName, rightNode]) => {
      if (leftNode.isFile !== rightNode.isFile) {
        return leftNode.isFile ? 1 : -1;
      }
      return leftName.localeCompare(rightName);
    });

    return entries.flatMap(([name, child], index) => {
      const isLast = index === entries.length - 1;
      const connector = isLast ? "└── " : "├── ";
      const nextPrefix = prefix + (isLast ? "    " : "│   ");
      return [`${prefix}${connector}${name}`, ...render(child, nextPrefix)];
    });
  }

  return [".", ...render(root, "")];
}

function createEditableSkill(skill: AgentSkill, index: number): EditableSkill {
  return { ...skill, clientId: `skill-${index}-${skill.slug || "item"}` };
}

function createEditableMarkdownFile(file: AgentMarkdownFile, index: number): EditableMarkdownFile {
  return { ...file, clientId: `markdown-${index}-${file.path || "item"}` };
}

function buildDefaultMarkdownPath(files: Array<Pick<AgentMarkdownFile, "path">>): string {
  const existingPaths = new Set(
    files.map((file) => file.path.trim()).filter((path) => path.length > 0)
  );

  let index = 1;
  while (true) {
    const candidate = `docs/new-markdown${index === 1 ? "" : `-${index}`}.md`;
    if (!existingPaths.has(candidate)) {
      return candidate;
    }
    index += 1;
  }
}

function runtimeLabel(locale: Locale, runtimeTarget: RuntimeTarget): string {
  return runtimeTarget === "claude_code"
    ? t(locale, { ru: "Claude Code", en: "Claude Code" })
    : t(locale, { ru: "Codex", en: "Codex" });
}

function normalizeRuntimeTargets(targets: RuntimeTarget[] | null | undefined): RuntimeTarget[] {
  return targets?.length ? targets : ["codex", "claude_code"];
}

function buildSkillAssetPath(runtimeTarget: RuntimeTarget, agentSlug: string, skillSlug: string): string {
  const normalizedSlug = skillSlug || "new-skill";
  return runtimeTarget === "claude_code"
    ? `agents/${agentSlug}/skills/${normalizedSlug}.md`
    : `.codex/skills/${normalizedSlug}/SKILL.md`;
}

function buildRuntimeEntryPath(runtimeTarget: RuntimeTarget, agentSlug: string): string {
  return runtimeTarget === "claude_code" ? `.claude/agents/${agentSlug}.md` : `${agentSlug}.toml`;
}

function buildAgentBundlePaths(
  runtimeTarget: RuntimeTarget,
  agentSlug: string,
  markdownFiles: Array<Pick<AgentMarkdownFile, "path">>,
  skills: Array<Pick<AgentSkill, "slug">>
): string[] {
  const files = [buildRuntimeEntryPath(runtimeTarget, agentSlug)];
  const normalizedMarkdownPaths = markdownFiles
    .map((file) => file.path.trim())
    .filter((path) => path.length > 0);
  if (runtimeTarget === "claude_code") {
    files.push(
      ...normalizedMarkdownPaths.map((path) => `agents/${agentSlug}/${path}`),
      ...skills.map((skill) => buildSkillAssetPath(runtimeTarget, agentSlug, skill.slug))
    );
    return files;
  }

  files.push(
    ...normalizedMarkdownPaths,
    ...skills.map((skill) => buildSkillAssetPath(runtimeTarget, agentSlug, skill.slug))
  );
  return files;
}

export function AgentDetailShowcase({ agent, locale }: AgentDetailShowcaseProps) {
  const router = useRouter();
  const draftCounterRef = useRef(0);
  const exportTargets = useMemo(() => normalizeRuntimeTargets(agent.export_targets), [agent.export_targets]);

  const [activeTab, setActiveTab] = useState<AgentPageTabId>("overview");
  const [assetFilter, setAssetFilter] = useState<AssetFilter>("all");
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [previewRuntime, setPreviewRuntime] = useState<RuntimeTarget>(exportTargets[0] ?? "codex");

  const [user, setUser] = useState<AuthUser | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [submittingAssets, setSubmittingAssets] = useState(false);
  const [assetErrorMessage, setAssetErrorMessage] = useState<string | null>(null);
  const [assetSuccessMessage, setAssetSuccessMessage] = useState<string | null>(null);

  const [skills, setSkills] = useState<EditableSkill[]>(() =>
    agent.skills.map((skill, index) => createEditableSkill(skill, index))
  );
  const [markdownFiles, setMarkdownFiles] = useState<EditableMarkdownFile[]>(() =>
    agent.markdown_files.map((file, index) => createEditableMarkdownFile(file, index))
  );

  const manifest = useMemo(
    () =>
      agent.manifest_json && typeof agent.manifest_json === "object"
        ? agent.manifest_json
        : null,
    [agent.manifest_json]
  );
  const manifestCodex = useMemo(
    () => (manifest && typeof manifest.codex === "object" ? (manifest.codex as Record<string, unknown>) : null),
    [manifest]
  );
  const manifestClaude = useMemo(
    () => (manifest && typeof manifest.claude === "object" ? (manifest.claude as Record<string, unknown>) : null),
    [manifest]
  );
  const baseInstructions = useMemo(
    () =>
      readNestedString(manifest, "instructions") ??
      agent.install_instructions ??
      agent.short_description,
    [agent.install_instructions, agent.short_description, manifest]
  );
  const codexInstructions = useMemo(
    () =>
      readNestedString(manifest, "codex", "developer_instructions") ??
      baseInstructions,
    [baseInstructions, manifest]
  );
  const claudeInstructions = useMemo(
    () =>
      readNestedString(manifest, "claude", "developer_instructions") ??
      baseInstructions,
    [baseInstructions, manifest]
  );
  const activeRuntimeInstructions = previewRuntime === "claude_code" ? claudeInstructions : codexInstructions;
  const runtimeHasExplicitOverride = useMemo(() => {
    return previewRuntime === "claude_code"
      ? readNestedString(manifest, "claude", "developer_instructions") !== null
      : readNestedString(manifest, "codex", "developer_instructions") !== null;
  }, [manifest, previewRuntime]);

  useEffect(() => {
    setSkills(agent.skills.map((skill, index) => createEditableSkill(skill, index)));
    setMarkdownFiles(agent.markdown_files.map((file, index) => createEditableMarkdownFile(file, index)));
    setAssetErrorMessage(null);
  }, [agent]);

  useEffect(() => {
    if (!exportTargets.includes(previewRuntime)) {
      setPreviewRuntime(exportTargets[0] ?? "codex");
    }
  }, [exportTargets, previewRuntime]);

  useEffect(() => {
    let cancelled = false;

    async function resolveUser() {
      const token = getAccessToken();
      if (!token) {
        if (!cancelled) {
          setUser(null);
          setLoadingAuth(false);
        }
        return;
      }

      try {
        const currentUser = await fetchCurrentUser(token);
        if (!cancelled) {
          setUser(currentUser);
          setLoadingAuth(false);
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setUser(null);
          setLoadingAuth(false);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, []);

  function nextDraftId(prefix: "skill" | "markdown"): string {
    draftCounterRef.current += 1;
    return `${prefix}-draft-${draftCounterRef.current}`;
  }

  const treeLines = useMemo(
    () =>
      buildTreeLines(
        buildAgentBundlePaths(previewRuntime, agent.slug, markdownFiles, skills).filter(Boolean)
      ),
    [agent.slug, markdownFiles, previewRuntime, skills]
  );
  const assets = useMemo<ExplorerAsset[]>(
    () =>
      [
        ...markdownFiles.map((file) => ({
          id: file.clientId,
          kind: "markdown" as const,
          label:
            (file.path.split("/").at(-1) ?? file.path) ||
            t(locale, { ru: "Новый markdown", en: "New markdown" }),
          path:
            (previewRuntime === "claude_code" && file.path
              ? `agents/${agent.slug}/${file.path}`
              : file.path) || t(locale, { ru: "без пути", en: "no path" }),
          description: null,
          content: file.content
        })),
        ...skills.map((skill) => ({
          id: skill.clientId,
          kind: "skill" as const,
          label: skill.slug || t(locale, { ru: "Новый skill", en: "New skill" }),
          path: buildSkillAssetPath(previewRuntime, agent.slug, skill.slug),
          description: skill.description ?? null,
          content: skill.content
        }))
      ].sort((left, right) => left.path.localeCompare(right.path)),
    [agent.slug, locale, markdownFiles, previewRuntime, skills]
  );
  const visibleAssets = useMemo(
    () =>
      assets.filter((asset) => {
        if (assetFilter === "all") {
          return true;
        }
        return asset.kind === assetFilter;
      }),
    [assetFilter, assets]
  );
  const selectedAsset = useMemo(
    () =>
      visibleAssets.find((asset) => asset.id === selectedAssetId) ??
      visibleAssets[0] ??
      null,
    [selectedAssetId, visibleAssets]
  );

  useEffect(() => {
    if (visibleAssets.length === 0) {
      setSelectedAssetId(null);
      return;
    }

    if (!selectedAssetId || !visibleAssets.some((asset) => asset.id === selectedAssetId)) {
      setSelectedAssetId(visibleAssets[0].id);
    }
  }, [selectedAssetId, visibleAssets]);

  function updateSkill(clientId: string, patch: Partial<EditableSkill>) {
    setSkills((current) => current.map((skill) => (skill.clientId === clientId ? { ...skill, ...patch } : skill)));
  }

  function updateMarkdownFile(clientId: string, patch: Partial<EditableMarkdownFile>) {
    setMarkdownFiles((current) => current.map((file) => (file.clientId === clientId ? { ...file, ...patch } : file)));
  }

  function removeAsset(asset: ExplorerAsset) {
    setAssetSuccessMessage(null);
    setAssetErrorMessage(null);

    if (asset.kind === "skill") {
      setSkills((current) => current.filter((skill) => skill.clientId !== asset.id));
      return;
    }

    setMarkdownFiles((current) => current.filter((file) => file.clientId !== asset.id));
  }

  function addSkill() {
    const clientId = nextDraftId("skill");
    setSkills((current) => [
      ...current,
      {
        clientId,
        slug: "",
        description: "",
        content: ""
      }
    ]);
    setAssetFilter("skill");
    setSelectedAssetId(clientId);
    setAssetSuccessMessage(null);
    setAssetErrorMessage(null);
  }

  function addMarkdownFile() {
    const clientId = nextDraftId("markdown");
    setMarkdownFiles((current) => [
      ...current,
      {
        clientId,
        path: buildDefaultMarkdownPath(current),
        content: ""
      }
    ]);
    setAssetFilter("markdown");
    setSelectedAssetId(clientId);
    setAssetSuccessMessage(null);
    setAssetErrorMessage(null);
  }

  async function saveAssets() {
    const token = getAccessToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }

    setSubmittingAssets(true);
    setAssetErrorMessage(null);
    setAssetSuccessMessage(null);

    try {
      await updateAgent(
        agent.slug,
        {
          manifest_json: {
            ...(manifest ?? {}),
            title: agent.title,
            description: agent.full_description ?? agent.short_description,
            instructions: baseInstructions.trim(),
            codex: {
              ...(manifestCodex ?? {}),
              description: agent.short_description,
              developer_instructions: codexInstructions.trim()
            },
            claude: {
              ...(manifestClaude ?? {}),
              description: agent.short_description,
              developer_instructions: claudeInstructions.trim()
            }
          },
          export_targets: exportTargets,
          compatibility_matrix: agent.compatibility_matrix ?? { codex: true, claude_code: true },
          install_instructions: baseInstructions.trim(),
          skills: skills
            .map(({ clientId: _clientId, ...skill }) => skill)
            .filter((item) => item.slug.trim() || item.content.trim()),
          markdown_files: markdownFiles
            .map(({ clientId: _clientId, ...file }) => file)
            .filter((item) => item.path.trim() || item.content.trim())
        },
        token
      );

      setAssetSuccessMessage(
        t(locale, {
          ru: "Файлы и skills обновлены. Перезагружаю страницу.",
          en: "Files and skills were updated. Refreshing page."
        })
      );
      router.refresh();
    } catch (error) {
      setAssetErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось сохранить файлы агента.", en: "Failed to save agent files." })
      );
    } finally {
      setSubmittingAssets(false);
    }
  }

  const mainTabs = [
    {
      id: "overview" as const,
      label: t(locale, { ru: "Overview", en: "Overview" }),
      note: t(locale, { ru: "роль и инструкции", en: "role and instructions" })
    },
    {
      id: "files" as const,
      label: t(locale, { ru: "Files", en: "Files" }),
      note: t(locale, { ru: "редактирование assets", en: "edit assets" })
    },
    {
      id: "export" as const,
      label: t(locale, { ru: "Export", en: "Export" }),
      note: t(locale, { ru: "runtime bundle", en: "runtime bundle" })
    }
  ];
  const fileFilters = [
    { id: "all" as const, label: t(locale, { ru: "Все", en: "All" }) },
    { id: "markdown" as const, label: t(locale, { ru: "Markdown", en: "Markdown" }) },
    { id: "skill" as const, label: t(locale, { ru: "Skills", en: "Skills" }) }
  ];

  const renderAssetIcon = (kind: ExplorerAsset["kind"]) =>
    kind === "markdown" ? (
      <FileText className="h-4 w-4 text-slate-500 dark:text-slate-400" />
    ) : (
      <FileCode2 className="h-4 w-4 text-slate-500 dark:text-slate-400" />
    );

  const renderDeveloperTree = () => (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FolderTree className="h-4 w-4 text-slate-500 dark:text-slate-400" />
          <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
            {t(locale, { ru: "Файловое дерево", en: "File tree" })}
          </h3>
        </div>
        <div className="flex flex-wrap gap-2">
          {exportTargets.map((runtime) => {
            const active = previewRuntime === runtime;
            return (
              <button
                className={cn(
                  "rounded-full px-3 py-1.5 text-xs font-semibold transition",
                  active
                    ? "bg-slate-950 text-slate-50 dark:bg-slate-100 dark:text-slate-950"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-zinc-900 dark:text-slate-200 dark:hover:bg-zinc-800"
                )}
                key={runtime}
                onClick={() => setPreviewRuntime(runtime)}
                type="button"
              >
                {runtimeLabel(locale, runtime)}
              </button>
            );
          })}
        </div>
      </div>
      <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
        {t(locale, {
          ru: `Превью single-agent ${runtimeLabel(locale, previewRuntime)} bundle в стиле Linux tree.`,
          en: `Single-agent ${runtimeLabel(locale, previewRuntime)} bundle preview in a Linux tree style.`
        })}
      </p>
      <div className="mt-4 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950">
        <div className="border-b border-slate-800 px-4 py-2 text-[11px] uppercase tracking-[0.24em] text-slate-400">
          $ tree -a
        </div>
        <pre className="overflow-x-auto px-4 py-4 text-xs leading-6 text-slate-100">{treeLines.join("\n")}</pre>
      </div>
    </div>
  );

  const renderBundleSummary = () => (
    <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
      <div className="flex items-center gap-2">
        <Package2 className="h-4 w-4 text-slate-500 dark:text-slate-400" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
          {t(locale, { ru: "Bundle summary", en: "Bundle summary" })}
        </h3>
      </div>
      <ul className="mt-4 space-y-3 text-sm text-slate-700 dark:text-slate-200">
        <li className="flex items-center justify-between gap-3">
          <span>{t(locale, { ru: "Runtime entrypoint", en: "Runtime entrypoint" })}</span>
          <code className="text-xs">{buildRuntimeEntryPath(previewRuntime, agent.slug)}</code>
        </li>
        <li className="flex items-center justify-between gap-3">
          <span>{t(locale, { ru: "Markdown assets", en: "Markdown assets" })}</span>
          <span className="font-semibold">{markdownFiles.length}</span>
        </li>
        <li className="flex items-center justify-between gap-3">
          <span>{t(locale, { ru: "Skill assets", en: "Skill assets" })}</span>
          <span className="font-semibold">{skills.length}</span>
        </li>
        <li className="flex items-center justify-between gap-3">
          <span>{t(locale, { ru: "Runtime", en: "Runtime" })}</span>
          <span className="font-semibold">{exportTargets.map((runtime) => runtimeLabel(locale, runtime)).join(", ")}</span>
        </li>
      </ul>
    </div>
  );

  const renderOverview = () => (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center gap-2">
            <ScrollText className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Описание роли", en: "Role summary" })}
            </h2>
          </div>
          <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700 dark:text-slate-200">
            {agent.full_description ??
              t(locale, {
                ru: "Полное описание пока не добавлено.",
                en: "No full description has been added yet."
              })}
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Базовые инструкции", en: "Base instructions" })}
              </h2>
            </div>
            <pre className="mt-4 overflow-x-auto whitespace-pre-wrap rounded-2xl bg-slate-950 px-4 py-4 text-sm leading-6 text-slate-100">
              {baseInstructions}
            </pre>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
            <div className="flex items-center gap-2">
              <FileCode2 className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Runtime override", en: "Runtime override" })}
              </h2>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {exportTargets.map((runtime) => {
                const active = previewRuntime === runtime;
                return (
                  <button
                    className={cn(
                      "rounded-full px-3 py-1.5 text-xs font-semibold transition",
                      active
                        ? "bg-slate-950 text-slate-50 dark:bg-slate-100 dark:text-slate-950"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-zinc-900 dark:text-slate-200 dark:hover:bg-zinc-800"
                    )}
                    key={runtime}
                    onClick={() => setPreviewRuntime(runtime)}
                    type="button"
                  >
                    {runtimeLabel(locale, runtime)}
                  </button>
                );
              })}
            </div>
            <p className="mt-4 text-xs uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
              {runtimeHasExplicitOverride
                ? t(locale, { ru: "Отдельный override", en: "Explicit override" })
                : t(locale, { ru: "Наследует базовые инструкции", en: "Inherits general instructions" })}
            </p>
            <pre className="mt-4 overflow-x-auto whitespace-pre-wrap rounded-2xl bg-slate-950 px-4 py-4 text-sm leading-6 text-slate-100">
              {activeRuntimeInstructions}
            </pre>
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Skills", en: "Skills" })}
              </h2>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-900 dark:text-slate-200 dark:ring-zinc-700">
              {skills.length}
            </span>
          </div>

          {skills.length === 0 ? (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
              {t(locale, { ru: "У агента пока нет skills.", en: "This agent has no skills yet." })}
            </div>
          ) : (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {skills.map((skill) => (
                <div
                  className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/60"
                  key={skill.clientId}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <code className="block truncate text-xs font-semibold text-brand-700 dark:text-brand-300">
                        {skill.slug || t(locale, { ru: "Новый skill", en: "New skill" })}
                      </code>
                      <p className="mt-1 text-[11px] uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                        {buildSkillAssetPath(previewRuntime, agent.slug, skill.slug || "new-skill")}
                      </p>
                    </div>
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {skill.content.length} chars
                    </span>
                  </div>
                  {skill.description ? (
                    <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{skill.description}</p>
                  ) : null}
                  <pre className="mt-3 line-clamp-6 overflow-x-auto whitespace-pre-wrap rounded-xl bg-slate-950 px-3 py-3 text-xs leading-6 text-slate-100">
                    {skill.content}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
        <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Профиль агента", en: "Agent profile" })}
            </h3>
          </div>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Автор", en: "Author" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">{agent.author_name}</dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Slug", en: "Slug" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">{agent.slug}</dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Категория", en: "Category" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                {agent.category ?? formatGeneralCategory(locale)}
              </dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Статус", en: "Status" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                {formatStatus(locale, agent.status)}
              </dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Верификация", en: "Verification" })}
              </dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                {formatVerificationStatus(locale, agent.verification_status)}
              </dd>
            </div>
          </dl>
        </div>

        {renderDeveloperTree()}
        {renderBundleSummary()}
      </aside>
    </div>
  );

  const renderFiles = () => (
    <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)_280px]">
      <div className="space-y-4">
        <div className="rounded-3xl border border-slate-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Package2 className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Explorer", en: "Explorer" })}
              </h2>
            </div>
            <span className="text-xs text-slate-500 dark:text-slate-400">{assets.length}</span>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {fileFilters.map((filter) => {
              const active = assetFilter === filter.id;
              return (
                <button
                  className={cn(
                    "rounded-full px-3 py-1.5 text-xs font-semibold transition",
                    active
                      ? "bg-slate-950 text-slate-50 dark:bg-slate-100 dark:text-slate-950"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-zinc-900 dark:text-slate-200 dark:hover:bg-zinc-800"
                  )}
                  key={filter.id}
                  onClick={() => setAssetFilter(filter.id)}
                  type="button"
                >
                  {filter.label}
                </button>
              );
            })}
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <Button disabled={!user || submittingAssets} onClick={addMarkdownFile} size="sm" type="button" variant="secondary">
              <Plus className="mr-2 h-4 w-4" />
              {t(locale, { ru: "Markdown", en: "Markdown" })}
            </Button>
            <Button disabled={!user || submittingAssets} onClick={addSkill} size="sm" type="button" variant="secondary">
              <Plus className="mr-2 h-4 w-4" />
              {t(locale, { ru: "Skill", en: "Skill" })}
            </Button>
          </div>

          {visibleAssets.length === 0 ? (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
              {t(locale, {
                ru: "Под выбранным фильтром файлов пока нет.",
                en: "No files are available under the selected filter."
              })}
            </div>
          ) : (
            <div className="mt-4 space-y-2">
              {visibleAssets.map((asset) => {
                const active = asset.id === selectedAsset?.id;
                return (
                  <button
                    className={cn(
                      "block w-full rounded-2xl border px-4 py-3 text-left transition",
                      active
                        ? "border-brand-300 bg-slate-50 shadow-sm dark:border-brand-500/50 dark:bg-zinc-900/80"
                        : "border-slate-200 bg-white hover:border-slate-300 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-700"
                    )}
                    key={asset.id}
                    onClick={() => setSelectedAssetId(asset.id)}
                    type="button"
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5">{renderAssetIcon(asset.kind)}</div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                          {asset.label}
                        </p>
                        <code className="mt-1 block truncate text-[11px] text-slate-500 dark:text-slate-400">
                          {asset.path}
                        </code>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {loadingAuth ? (
            <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">{formatAuthLoading(locale)}</p>
          ) : !user ? (
            <p className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-300">
              {t(locale, {
                ru: "Войдите, чтобы добавлять и редактировать файлы прямо в explorer.",
                en: "Login to add and edit files directly in the explorer."
              })}
            </p>
          ) : null}
        </div>

        {renderDeveloperTree()}
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {selectedAsset ? renderAssetIcon(selectedAsset.kind) : <FileText className="h-4 w-4 text-slate-500 dark:text-slate-400" />}
            <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Редактор", en: "Editor" })}
            </h2>
          </div>

          <div className="flex flex-wrap gap-2">
            {selectedAsset ? (
              <Button
                disabled={!user || submittingAssets}
                onClick={() => removeAsset(selectedAsset)}
                size="sm"
                type="button"
                variant="ghost"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {t(locale, { ru: "Удалить", en: "Remove" })}
              </Button>
            ) : null}
            <Button disabled={!user || submittingAssets} onClick={() => void saveAssets()} size="sm" type="button">
              <Save className="mr-2 h-4 w-4" />
              {submittingAssets
                ? t(locale, { ru: "Сохраняем...", en: "Saving..." })
                : t(locale, { ru: "Сохранить", en: "Save" })}
            </Button>
          </div>
        </div>

        {assetErrorMessage ? (
          <p className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {assetErrorMessage}
          </p>
        ) : null}

        {assetSuccessMessage ? (
          <p className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {assetSuccessMessage}
          </p>
        ) : null}

        {!selectedAsset ? (
          <div className="mt-4 rounded-2xl border border-dashed border-slate-300 px-4 py-10 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
            {t(locale, {
              ru: "Выберите файл слева или добавьте новый asset.",
              en: "Select a file on the left or add a new asset."
            })}
          </div>
        ) : selectedAsset.kind === "markdown" ? (
          <div className="mt-4 space-y-4">
            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Путь файла", en: "File path" })}
              <input
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                disabled={!user || submittingAssets}
                onChange={(event) => updateMarkdownFile(selectedAsset.id, { path: event.target.value })}
                placeholder="docs/agent-playbook.md"
                value={markdownFiles.find((file) => file.clientId === selectedAsset.id)?.path ?? ""}
              />
            </label>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              Markdown
              <textarea
                className="mt-1 min-h-[420px] w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-900"
                disabled={!user || submittingAssets}
                onChange={(event) => updateMarkdownFile(selectedAsset.id, { content: event.target.value })}
                value={markdownFiles.find((file) => file.clientId === selectedAsset.id)?.content ?? ""}
              />
            </label>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            <div className="grid gap-4 lg:grid-cols-2">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                Slug
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  disabled={!user || submittingAssets}
                  onChange={(event) => updateSkill(selectedAsset.id, { slug: event.target.value })}
                  placeholder="delivery-checkpoint"
                  value={skills.find((skill) => skill.clientId === selectedAsset.id)?.slug ?? ""}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Описание", en: "Description" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  disabled={!user || submittingAssets}
                  onChange={(event) => updateSkill(selectedAsset.id, { description: event.target.value })}
                  value={skills.find((skill) => skill.clientId === selectedAsset.id)?.description ?? ""}
                />
              </label>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/70">
              <code className="text-xs font-semibold text-brand-700 dark:text-brand-300">
                {buildSkillAssetPath(
                  previewRuntime,
                  agent.slug,
                  skills.find((skill) => skill.clientId === selectedAsset.id)?.slug || "new-skill"
                )}
              </code>
            </div>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              SKILL.md
              <textarea
                className="mt-1 min-h-[420px] w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-900"
                disabled={!user || submittingAssets}
                onChange={(event) => updateSkill(selectedAsset.id, { content: event.target.value })}
                value={skills.find((skill) => skill.clientId === selectedAsset.id)?.content ?? ""}
              />
            </label>
          </div>
        )}
      </div>

      <aside className="space-y-4">
        <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Состав bundle", en: "Bundle contents" })}
            </h3>
          </div>
          <ul className="mt-4 space-y-3 text-sm text-slate-700 dark:text-slate-200">
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Всего assets", en: "Total assets" })}</span>
              <span className="font-semibold">{assets.length}</span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Markdown", en: "Markdown" })}</span>
              <span className="font-semibold">{markdownFiles.length}</span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Skills", en: "Skills" })}</span>
              <span className="font-semibold">{skills.length}</span>
            </li>
          </ul>
        </div>

        {renderBundleSummary()}
      </aside>
    </div>
  );

  return (
    <section className="space-y-6">
      <div className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
        <div className="border-b border-slate-200 bg-[linear-gradient(135deg,rgba(15,23,42,0.02),rgba(59,130,246,0.08),rgba(16,185,129,0.08))] px-6 py-8 dark:border-zinc-800 dark:bg-[linear-gradient(135deg,rgba(255,255,255,0.03),rgba(37,99,235,0.12),rgba(16,185,129,0.12))]">
          <div className="flex flex-col gap-8 xl:flex-row xl:items-start xl:justify-between">
            <div className="space-y-5">
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {formatStatus(locale, agent.status)}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                  <Sparkles className="h-3.5 w-3.5" />
                  {formatVerificationStatus(locale, agent.verification_status)}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                  <Bot className="h-3.5 w-3.5" />
                  {agent.category ?? formatGeneralCategory(locale)}
                </span>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Agent profile", en: "Agent profile" })}
                </p>
                <h1 className="text-3xl font-black tracking-tight text-slate-950 dark:text-slate-50">
                  {agent.title}
                </h1>
                <p className="max-w-3xl text-sm leading-7 text-slate-600 dark:text-slate-300">
                  {agent.short_description}
                </p>
              </div>

              <div className="flex flex-wrap gap-x-6 gap-y-3 text-sm">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                    {t(locale, { ru: "Автор", en: "Author" })}
                  </p>
                  <p className="font-semibold text-slate-900 dark:text-slate-100">{agent.author_name}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                    {t(locale, { ru: "Slug", en: "Slug" })}
                  </p>
                  <p className="font-semibold text-slate-900 dark:text-slate-100">{agent.slug}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                    {t(locale, { ru: "Runtime", en: "Runtime" })}
                  </p>
                  <p className="font-semibold text-slate-900 dark:text-slate-100">
                    {exportTargets.map((runtime) => runtimeLabel(locale, runtime)).join(", ")}
                  </p>
                </div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 xl:w-[320px] xl:grid-cols-1">
              <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950/90">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Skills", en: "Skills" })}
                </p>
                <p className="mt-2 text-2xl font-black text-slate-950 dark:text-slate-50">{skills.length}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950/90">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Markdown files", en: "Markdown files" })}
                </p>
                <p className="mt-2 text-2xl font-black text-slate-950 dark:text-slate-50">{markdownFiles.length}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950/90">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Runtime bundle", en: "Runtime bundle" })}
                </p>
                <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {runtimeLabel(locale, previewRuntime)} {t(locale, { ru: "готов к materialize", en: "ready to materialize" })}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="border-b border-slate-200 px-6 py-4 dark:border-zinc-800">
          <div className="flex flex-wrap gap-2">
            {mainTabs.map((tab) => {
              const active = activeTab === tab.id;
              return (
                <button
                  className={cn(
                    "rounded-2xl border px-4 py-3 text-left transition",
                    active
                      ? "border-slate-300 bg-slate-950 text-slate-50 dark:border-zinc-700 dark:bg-slate-100 dark:text-slate-950"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-200 dark:hover:border-zinc-700"
                  )}
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  type="button"
                >
                  <p className="text-sm font-semibold">{tab.label}</p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      active ? "text-slate-300 dark:text-slate-600" : "text-slate-500 dark:text-slate-400"
                    )}
                  >
                    {tab.note}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        <div className="px-6 py-6">
          {activeTab === "overview" ? renderOverview() : null}
          {activeTab === "files" ? renderFiles() : null}
          {activeTab === "export" ? (
            <ExportControls
              entityType="agent"
              locale={locale}
              slug={agent.slug}
              status={agent.status}
              supportedRuntimes={exportTargets}
            />
          ) : null}
        </div>
      </div>
    </section>
  );
}
