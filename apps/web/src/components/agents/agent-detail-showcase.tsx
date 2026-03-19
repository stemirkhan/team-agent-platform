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
  type AgentUpdatePayload,
  type RuntimeTarget,
  createAgentDraftRevision,
  fetchAgentDraft,
  publishAgentDraft,
  updateAgent,
  updateAgentDraft
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

function normalizeCompatibilityMatrix(
  matrix: Record<string, unknown> | null | undefined
): Record<string, unknown> {
  if (!matrix || typeof matrix !== "object") {
    return { codex: true, claude_code: true };
  }
  return { ...matrix };
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
  const [agentSnapshot, setAgentSnapshot] = useState(agent);

  const [activeTab, setActiveTab] = useState<AgentPageTabId>("overview");
  const [assetFilter, setAssetFilter] = useState<AssetFilter>("all");
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);

  const [user, setUser] = useState<AuthUser | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [draftRevisionLoading, setDraftRevisionLoading] = useState(false);
  const [isDraftRevisionView, setIsDraftRevisionView] = useState(false);
  const [savingOverview, setSavingOverview] = useState(false);
  const [overviewErrorMessage, setOverviewErrorMessage] = useState<string | null>(null);
  const [overviewSuccessMessage, setOverviewSuccessMessage] = useState<string | null>(null);
  const [submittingAssets, setSubmittingAssets] = useState(false);
  const [assetErrorMessage, setAssetErrorMessage] = useState<string | null>(null);
  const [assetSuccessMessage, setAssetSuccessMessage] = useState<string | null>(null);
  const [titleDraft, setTitleDraft] = useState(agentSnapshot.title);
  const [shortDescriptionDraft, setShortDescriptionDraft] = useState(agentSnapshot.short_description);
  const [fullDescriptionDraft, setFullDescriptionDraft] = useState(agentSnapshot.full_description ?? "");
  const [categoryDraft, setCategoryDraft] = useState(agentSnapshot.category ?? "");
  const [installInstructionsDraft, setInstallInstructionsDraft] = useState(
    agentSnapshot.install_instructions ?? ""
  );
  const [sourceArchiveUrlDraft, setSourceArchiveUrlDraft] = useState(agentSnapshot.source_archive_url ?? "");
  const [baseInstructions, setBaseInstructions] = useState(
    () =>
      readNestedString(
        agentSnapshot.manifest_json && typeof agentSnapshot.manifest_json === "object"
          ? agentSnapshot.manifest_json
          : null,
        "instructions"
      ) ??
      agentSnapshot.install_instructions ??
      agentSnapshot.short_description
  );
  const [codexInstructions, setCodexInstructions] = useState(
    () =>
      readNestedString(
        agentSnapshot.manifest_json && typeof agentSnapshot.manifest_json === "object"
          ? agentSnapshot.manifest_json
          : null,
        "codex",
        "developer_instructions"
      ) ??
      readNestedString(
        agentSnapshot.manifest_json && typeof agentSnapshot.manifest_json === "object"
          ? agentSnapshot.manifest_json
          : null,
        "instructions"
      ) ??
      agentSnapshot.install_instructions ??
      agentSnapshot.short_description
  );
  const [claudeInstructions, setClaudeInstructions] = useState(
    () =>
      readNestedString(
        agentSnapshot.manifest_json && typeof agentSnapshot.manifest_json === "object"
          ? agentSnapshot.manifest_json
          : null,
        "claude",
        "developer_instructions"
      ) ??
      readNestedString(
        agentSnapshot.manifest_json && typeof agentSnapshot.manifest_json === "object"
          ? agentSnapshot.manifest_json
          : null,
        "instructions"
      ) ??
      agentSnapshot.install_instructions ??
      agentSnapshot.short_description
  );
  const [codexOverrideEnabled, setCodexOverrideEnabled] = useState(
    () =>
      readNestedString(
        agentSnapshot.manifest_json && typeof agentSnapshot.manifest_json === "object"
          ? agentSnapshot.manifest_json
          : null,
        "codex",
        "developer_instructions"
      ) !== null
  );
  const [claudeOverrideEnabled, setClaudeOverrideEnabled] = useState(
    () =>
      readNestedString(
        agentSnapshot.manifest_json && typeof agentSnapshot.manifest_json === "object"
          ? agentSnapshot.manifest_json
          : null,
        "claude",
        "developer_instructions"
      ) !== null
  );
  const [exportTargets, setExportTargets] = useState<RuntimeTarget[]>(
    () => normalizeRuntimeTargets(agentSnapshot.export_targets)
  );
  const [compatibilityMatrixDraft, setCompatibilityMatrixDraft] = useState<Record<string, unknown>>(
    () => normalizeCompatibilityMatrix(agentSnapshot.compatibility_matrix)
  );
  const [previewRuntime, setPreviewRuntime] = useState<RuntimeTarget>(
    normalizeRuntimeTargets(agentSnapshot.export_targets)[0] ?? "codex"
  );

  const [skills, setSkills] = useState<EditableSkill[]>(() =>
    agentSnapshot.skills.map((skill, index) => createEditableSkill(skill, index))
  );
  const [markdownFiles, setMarkdownFiles] = useState<EditableMarkdownFile[]>(() =>
    agentSnapshot.markdown_files.map((file, index) => createEditableMarkdownFile(file, index))
  );

  const manifest = useMemo(
    () =>
      agentSnapshot.manifest_json && typeof agentSnapshot.manifest_json === "object"
        ? agentSnapshot.manifest_json
        : null,
    [agentSnapshot.manifest_json]
  );
  const manifestCodex = useMemo(
    () => (manifest && typeof manifest.codex === "object" ? (manifest.codex as Record<string, unknown>) : null),
    [manifest]
  );
  const manifestClaude = useMemo(
    () => (manifest && typeof manifest.claude === "object" ? (manifest.claude as Record<string, unknown>) : null),
    [manifest]
  );
  const canManageAgent = Boolean(
    user && agentSnapshot.author_id && user.id === agentSnapshot.author_id
  );
  const canEditAgentDraft = canManageAgent && agentSnapshot.status === "draft";
  const activeRuntimeInstructions = previewRuntime === "claude_code"
    ? claudeOverrideEnabled
      ? claudeInstructions
      : baseInstructions
    : codexOverrideEnabled
      ? codexInstructions
      : baseInstructions;
  const runtimeHasExplicitOverride = previewRuntime === "claude_code"
    ? claudeOverrideEnabled
    : codexOverrideEnabled;

  useEffect(() => {
    setAgentSnapshot(agent);
    setIsDraftRevisionView(false);
  }, [agent]);

  useEffect(() => {
    const nextBaseInstructions =
      readNestedString(manifest, "instructions") ??
      agentSnapshot.install_instructions ??
      agentSnapshot.short_description;

    setTitleDraft(agentSnapshot.title);
    setShortDescriptionDraft(agentSnapshot.short_description);
    setFullDescriptionDraft(agentSnapshot.full_description ?? "");
    setCategoryDraft(agentSnapshot.category ?? "");
    setInstallInstructionsDraft(agentSnapshot.install_instructions ?? nextBaseInstructions);
    setSourceArchiveUrlDraft(agentSnapshot.source_archive_url ?? "");
    setBaseInstructions(nextBaseInstructions);
    setCodexInstructions(
      readNestedString(manifest, "codex", "developer_instructions") ?? nextBaseInstructions
    );
    setClaudeInstructions(
      readNestedString(manifest, "claude", "developer_instructions") ?? nextBaseInstructions
    );
    setCodexOverrideEnabled(
      readNestedString(manifest, "codex", "developer_instructions") !== null
    );
    setClaudeOverrideEnabled(
      readNestedString(manifest, "claude", "developer_instructions") !== null
    );
    setExportTargets(normalizeRuntimeTargets(agentSnapshot.export_targets));
    setCompatibilityMatrixDraft(normalizeCompatibilityMatrix(agentSnapshot.compatibility_matrix));
    setSkills(agentSnapshot.skills.map((skill, index) => createEditableSkill(skill, index)));
    setMarkdownFiles(
      agentSnapshot.markdown_files.map((file, index) => createEditableMarkdownFile(file, index))
    );
    setOverviewErrorMessage(null);
    setOverviewSuccessMessage(null);
    setAssetErrorMessage(null);
    setAssetSuccessMessage(null);
  }, [agentSnapshot, manifest]);

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

  useEffect(() => {
    if (loadingAuth || !user || !canManageAgent || agent.status !== "published" || isDraftRevisionView) {
      return;
    }

    const token = getAccessToken();
    if (!token) {
      return;
    }
    const accessToken = token;

    let cancelled = false;
    setDraftRevisionLoading(true);

    async function loadDraftRevision() {
      try {
        const draftAgent = await fetchAgentDraft(agentSnapshot.slug, accessToken);
        if (!cancelled) {
          setAgentSnapshot(draftAgent);
          setIsDraftRevisionView(true);
        }
      } catch (error) {
        if (!cancelled && error instanceof Error && error.message !== "Draft revision not found.") {
          setOverviewErrorMessage(error.message);
        }
      } finally {
        if (!cancelled) {
          setDraftRevisionLoading(false);
        }
      }
    }

    void loadDraftRevision();

    return () => {
      cancelled = true;
    };
  }, [agent.status, agentSnapshot.slug, canManageAgent, isDraftRevisionView, loadingAuth, user]);

  function applyServerAgent(nextAgent: Agent, options?: { draftRevisionView?: boolean }) {
    setAgentSnapshot(nextAgent);
    setIsDraftRevisionView(options?.draftRevisionView ?? false);
  }

  function nextDraftId(prefix: "skill" | "markdown"): string {
    draftCounterRef.current += 1;
    return `${prefix}-draft-${draftCounterRef.current}`;
  }

  function toggleRuntimeTarget(runtime: RuntimeTarget, enabled: boolean) {
    setExportTargets((current) => {
      const next = enabled
        ? Array.from(new Set([...current, runtime]))
        : current.filter((item) => item !== runtime);
      return next;
    });
    setCompatibilityMatrixDraft((current) => ({
      ...current,
      [runtime]: enabled
    }));
  }

  function buildCompatibilityMatrixPayload(): Record<string, unknown> {
    return {
      ...compatibilityMatrixDraft,
      codex: exportTargets.includes("codex"),
      claude_code: exportTargets.includes("claude_code")
    };
  }

  function buildAgentUpdatePayload(): AgentUpdatePayload {
    const normalizedTitle = titleDraft.trim();
    const normalizedShortDescription = shortDescriptionDraft.trim();
    const normalizedFullDescription = fullDescriptionDraft.trim();
    const normalizedBaseInstructions = baseInstructions.trim();

    const nextCodexManifest: Record<string, unknown> = {
      ...(manifestCodex ?? {}),
      description: normalizedShortDescription
    };
    if (codexOverrideEnabled) {
      nextCodexManifest.developer_instructions =
        codexInstructions.trim() || normalizedBaseInstructions;
    } else {
      delete nextCodexManifest.developer_instructions;
    }

    const nextClaudeManifest: Record<string, unknown> = {
      ...(manifestClaude ?? {}),
      description: normalizedShortDescription
    };
    if (claudeOverrideEnabled) {
      nextClaudeManifest.developer_instructions =
        claudeInstructions.trim() || normalizedBaseInstructions;
    } else {
      delete nextClaudeManifest.developer_instructions;
    }

    return {
      title: normalizedTitle,
      short_description: normalizedShortDescription,
      full_description: normalizedFullDescription || null,
      category: categoryDraft.trim() || null,
      manifest_json: {
        ...(manifest ?? {}),
        title: normalizedTitle,
        description: normalizedFullDescription || normalizedShortDescription,
        instructions: normalizedBaseInstructions,
        codex: nextCodexManifest,
        claude: nextClaudeManifest
      },
      source_archive_url: sourceArchiveUrlDraft.trim() || null,
      compatibility_matrix: buildCompatibilityMatrixPayload(),
      export_targets: exportTargets,
      install_instructions: installInstructionsDraft.trim() || null,
      skills: skills
        .map(({ clientId: _clientId, ...skill }) => skill)
        .filter((item) => item.slug.trim() || item.content.trim()),
      markdown_files: markdownFiles
        .map(({ clientId: _clientId, ...file }) => file)
        .filter((item) => item.path.trim() || item.content.trim())
    };
  }

  function validateAgentDraft(): string | null {
    if (titleDraft.trim().length < 2) {
      return t(locale, {
        ru: "Название агента должно содержать минимум 2 символа.",
        en: "Agent title must contain at least 2 characters."
      });
    }
    if (shortDescriptionDraft.trim().length < 10) {
      return t(locale, {
        ru: "Короткое описание агента должно содержать минимум 10 символов.",
        en: "Agent short description must contain at least 10 characters."
      });
    }
    if (baseInstructions.trim().length === 0) {
      return t(locale, {
        ru: "Базовые инструкции агента не могут быть пустыми.",
        en: "Base agent instructions cannot be empty."
      });
    }
    if (exportTargets.length === 0) {
      return t(locale, {
        ru: "Нужно оставить хотя бы один runtime target.",
        en: "At least one runtime target must remain enabled."
      });
    }
    return null;
  }

  async function onCreateDraftRevision() {
    const token = getAccessToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }

    setDraftRevisionLoading(true);
    setOverviewErrorMessage(null);
    setOverviewSuccessMessage(null);

    try {
      const draftAgent = await createAgentDraftRevision(agentSnapshot.slug, token);
      applyServerAgent(draftAgent, { draftRevisionView: true });
      setOverviewSuccessMessage(
        t(locale, {
          ru: "Draft revision создан. Теперь изменения идут в черновик, а не в live-профиль.",
          en: "Draft revision created. Changes now go into the draft instead of the live profile."
        })
      );
    } catch (error) {
      setOverviewErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось создать draft revision.", en: "Failed to create draft revision." })
      );
    } finally {
      setDraftRevisionLoading(false);
    }
  }

  async function onPublishDraftRevision() {
    const token = getAccessToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }

    setDraftRevisionLoading(true);
    setOverviewErrorMessage(null);
    setOverviewSuccessMessage(null);

    try {
      const publishedAgent = await publishAgentDraft(agentSnapshot.slug, token);
      applyServerAgent(publishedAgent, { draftRevisionView: false });
      setOverviewSuccessMessage(
        t(locale, {
          ru: "Draft revision опубликован в live-профиль агента.",
          en: "Draft revision published into the live agent profile."
        })
      );
      router.refresh();
    } catch (error) {
      setOverviewErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось опубликовать draft revision.", en: "Failed to publish draft revision." })
      );
    } finally {
      setDraftRevisionLoading(false);
    }
  }

  async function saveOverview() {
    const token = getAccessToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }

    const validationError = validateAgentDraft();
    if (validationError) {
      setOverviewErrorMessage(validationError);
      setOverviewSuccessMessage(null);
      return;
    }

    setSavingOverview(true);
    setOverviewErrorMessage(null);
    setOverviewSuccessMessage(null);

    try {
      const nextAgent = isDraftRevisionView
        ? await updateAgentDraft(agentSnapshot.slug, buildAgentUpdatePayload(), token)
        : await updateAgent(agentSnapshot.slug, buildAgentUpdatePayload(), token);
      applyServerAgent(nextAgent, { draftRevisionView: isDraftRevisionView });
      setOverviewSuccessMessage(
        t(locale, {
          ru: isDraftRevisionView
            ? "Draft revision агента обновлен."
            : "Профиль агента обновлен.",
          en: isDraftRevisionView
            ? "Agent draft revision updated."
            : "Agent profile updated."
        })
      );
    } catch (error) {
      setOverviewErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось обновить профиль агента.", en: "Failed to update agent profile." })
      );
    } finally {
      setSavingOverview(false);
    }
  }

  const treeLines = useMemo(
    () =>
      buildTreeLines(
        buildAgentBundlePaths(previewRuntime, agentSnapshot.slug, markdownFiles, skills).filter(Boolean)
      ),
    [agentSnapshot.slug, markdownFiles, previewRuntime, skills]
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
              ? `agents/${agentSnapshot.slug}/${file.path}`
              : file.path) || t(locale, { ru: "без пути", en: "no path" }),
          description: null,
          content: file.content
        })),
        ...skills.map((skill) => ({
          id: skill.clientId,
          kind: "skill" as const,
          label: skill.slug || t(locale, { ru: "Новый skill", en: "New skill" }),
          path: buildSkillAssetPath(previewRuntime, agentSnapshot.slug, skill.slug),
          description: skill.description ?? null,
          content: skill.content
        }))
      ].sort((left, right) => left.path.localeCompare(right.path)),
    [agentSnapshot.slug, locale, markdownFiles, previewRuntime, skills]
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
    if (!canEditAgentDraft) {
      return;
    }

    setAssetSuccessMessage(null);
    setAssetErrorMessage(null);

    if (asset.kind === "skill") {
      setSkills((current) => current.filter((skill) => skill.clientId !== asset.id));
      return;
    }

    setMarkdownFiles((current) => current.filter((file) => file.clientId !== asset.id));
  }

  function addSkill() {
    if (!canEditAgentDraft) {
      return;
    }

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
    if (!canEditAgentDraft) {
      return;
    }

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

    if (!canEditAgentDraft) {
      setAssetErrorMessage(
        t(locale, {
          ru: "Файлы и skills можно менять только в draft-агенте или в draft revision опубликованного агента.",
          en: "Files and skills can only be edited in a draft agent or in a published agent's draft revision."
        })
      );
      setAssetSuccessMessage(null);
      return;
    }

    const validationError = validateAgentDraft();
    if (validationError) {
      setAssetErrorMessage(validationError);
      setAssetSuccessMessage(null);
      return;
    }

    setSubmittingAssets(true);
    setAssetErrorMessage(null);
    setAssetSuccessMessage(null);

    try {
      const nextAgent = isDraftRevisionView
        ? await updateAgentDraft(agentSnapshot.slug, buildAgentUpdatePayload(), token)
        : await updateAgent(agentSnapshot.slug, buildAgentUpdatePayload(), token);
      applyServerAgent(nextAgent, { draftRevisionView: isDraftRevisionView });

      setAssetSuccessMessage(
        t(locale, {
          ru: isDraftRevisionView
            ? "Файлы и skills draft revision обновлены."
            : "Файлы и skills обновлены.",
          en: isDraftRevisionView
            ? "Draft revision files and skills were updated."
            : "Files and skills were updated."
        })
      );
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
          <code className="text-xs">{buildRuntimeEntryPath(previewRuntime, agentSnapshot.slug)}</code>
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
        {canManageAgent && agentSnapshot.status === "draft" ? (
          <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <ScrollText className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                  <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                    {t(locale, { ru: "Редактор профиля", en: "Profile editor" })}
                  </h2>
                </div>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600 dark:text-slate-300">
                  {isDraftRevisionView
                    ? t(locale, {
                        ru: "Вы редактируете draft revision опубликованного агента. Live-профиль останется неизменным до отдельной публикации этого draft.",
                        en: "You are editing a draft revision of a published agent. The live profile will stay unchanged until this draft is published separately."
                      })
                    : agentSnapshot.status === "draft"
                    ? t(locale, {
                        ru: "Обновите metadata, runtime instructions и delivery settings для текущего draft-агента.",
                        en: "Update metadata, runtime instructions, and delivery settings for the current draft agent."
                      })
                    : t(locale, {
                        ru: "Сейчас изменения применяются прямо к текущему профилю агента. Отдельные revision-потоки для published-агентов появятся позже.",
                        en: "Changes currently update the live agent profile directly. Dedicated revision flows for published agents will come later."
                      })}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {isDraftRevisionView ? (
                  <Button
                    disabled={draftRevisionLoading}
                    onClick={() => void onPublishDraftRevision()}
                    type="button"
                    variant="secondary"
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    {draftRevisionLoading
                      ? t(locale, { ru: "Публикация...", en: "Publishing..." })
                      : t(locale, { ru: "Опубликовать draft", en: "Publish draft" })}
                  </Button>
                ) : null}
                <Button disabled={savingOverview} onClick={() => void saveOverview()} type="button">
                  <Save className="mr-2 h-4 w-4" />
                  {savingOverview
                    ? t(locale, { ru: "Сохранение...", en: "Saving..." })
                    : t(locale, {
                        ru: isDraftRevisionView ? "Сохранить draft" : "Сохранить профиль",
                        en: isDraftRevisionView ? "Save draft" : "Save profile"
                      })}
                </Button>
              </div>
            </div>

            {overviewErrorMessage ? (
              <p className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
                {overviewErrorMessage}
              </p>
            ) : null}

            {overviewSuccessMessage ? (
              <p className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
                {overviewSuccessMessage}
              </p>
            ) : null}

            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Название", en: "Title" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  minLength={2}
                  onChange={(event) => setTitleDraft(event.target.value)}
                  value={titleDraft}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Категория", en: "Category" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  onChange={(event) => setCategoryDraft(event.target.value)}
                  placeholder={t(locale, { ru: "backend, frontend, orchestrator...", en: "backend, frontend, orchestrator..." })}
                  value={categoryDraft}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200 lg:col-span-2">
                {t(locale, { ru: "Короткое описание", en: "Short description" })}
                <textarea
                  className="mt-1 min-h-24 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  onChange={(event) => setShortDescriptionDraft(event.target.value)}
                  value={shortDescriptionDraft}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200 lg:col-span-2">
                {t(locale, { ru: "Полное описание роли", en: "Full role summary" })}
                <textarea
                  className="mt-1 min-h-36 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  onChange={(event) => setFullDescriptionDraft(event.target.value)}
                  value={fullDescriptionDraft}
                />
              </label>
            </div>

            <div className="mt-6 grid gap-4 xl:grid-cols-2">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Базовые инструкции", en: "Base instructions" })}
                <textarea
                  className="mt-1 min-h-56 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  onChange={(event) => setBaseInstructions(event.target.value)}
                  value={baseInstructions}
                />
              </label>

              <div className="space-y-4">
                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {t(locale, { ru: "Install instructions", en: "Install instructions" })}
                  <textarea
                    className="mt-1 min-h-28 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                    onChange={(event) => setInstallInstructionsDraft(event.target.value)}
                    value={installInstructionsDraft}
                  />
                </label>

                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {t(locale, { ru: "Source archive URL", en: "Source archive URL" })}
                  <input
                    className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                    onChange={(event) => setSourceArchiveUrlDraft(event.target.value)}
                    placeholder="https://example.com/agent-source.zip"
                    value={sourceArchiveUrlDraft}
                  />
                </label>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-300">
                  {t(locale, {
                    ru: "Поддержка runtime сейчас задаётся через enabled targets. Compatibility matrix будет синхронизирована с ними при сохранении.",
                    en: "Runtime support is currently controlled through enabled targets. The compatibility matrix will be synchronized with them on save."
                  })}
                </div>
              </div>
            </div>

            <div className="mt-6 rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/60">
              <div className="flex items-center gap-2">
                <Package2 className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Runtime targets", en: "Runtime targets" })}
                </h3>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {(["codex", "claude_code"] as RuntimeTarget[]).map((runtime) => {
                  const enabled = exportTargets.includes(runtime);
                  return (
                    <label
                      className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950"
                      key={runtime}
                    >
                      <input
                        checked={enabled}
                        className="mt-1"
                        onChange={(event) => toggleRuntimeTarget(runtime, event.target.checked)}
                        type="checkbox"
                      />
                      <div>
                        <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                          {runtimeLabel(locale, runtime)}
                        </p>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                          {enabled
                            ? t(locale, { ru: "Bundle будет materialize для этого runtime.", en: "Bundle will be materialized for this runtime." })
                            : t(locale, { ru: "Runtime отключен для export и delivery.", en: "Runtime is disabled for export and delivery." })}
                        </p>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="mt-6 grid gap-4 xl:grid-cols-2">
              <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
                <label className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                  <input
                    checked={codexOverrideEnabled}
                    onChange={(event) => setCodexOverrideEnabled(event.target.checked)}
                    type="checkbox"
                  />
                  {t(locale, { ru: "Отдельный Codex override", en: "Custom Codex override" })}
                </label>
                <textarea
                  className="mt-4 min-h-44 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  disabled={!codexOverrideEnabled}
                  onChange={(event) => setCodexInstructions(event.target.value)}
                  placeholder={t(locale, {
                    ru: "Если override выключен, Codex унаследует базовые инструкции.",
                    en: "If override is disabled, Codex inherits the base instructions."
                  })}
                  value={codexInstructions}
                />
              </div>

              <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
                <label className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                  <input
                    checked={claudeOverrideEnabled}
                    onChange={(event) => setClaudeOverrideEnabled(event.target.checked)}
                    type="checkbox"
                  />
                  {t(locale, { ru: "Отдельный Claude Code override", en: "Custom Claude Code override" })}
                </label>
                <textarea
                  className="mt-4 min-h-44 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  disabled={!claudeOverrideEnabled}
                  onChange={(event) => setClaudeInstructions(event.target.value)}
                  placeholder={t(locale, {
                    ru: "Если override выключен, Claude Code унаследует базовые инструкции.",
                    en: "If override is disabled, Claude Code inherits the base instructions."
                  })}
                  value={claudeInstructions}
                />
              </div>
            </div>
          </div>
        ) : canManageAgent && agentSnapshot.status === "published" ? (
          <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <ScrollText className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                  <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                    {t(locale, { ru: "Draft revision", en: "Draft revision" })}
                  </h2>
                </div>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600 dark:text-slate-300">
                  {t(locale, {
                    ru: "Опубликованный агент теперь редактируется через отдельный draft revision. Создайте черновик, чтобы менять metadata, instructions, files и delivery settings без изменения live-профиля.",
                    en: "Published agents are now edited through a separate draft revision. Create a draft to change metadata, instructions, files, and delivery settings without touching the live profile."
                  })}
                </p>
              </div>

              <Button
                disabled={draftRevisionLoading}
                onClick={() => void onCreateDraftRevision()}
                type="button"
              >
                <Sparkles className="mr-2 h-4 w-4" />
                {draftRevisionLoading
                  ? t(locale, { ru: "Подготовка...", en: "Preparing..." })
                  : t(locale, { ru: "Создать draft revision", en: "Create draft revision" })}
              </Button>
            </div>

            {overviewErrorMessage ? (
              <p className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
                {overviewErrorMessage}
              </p>
            ) : null}

            {overviewSuccessMessage ? (
              <p className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
                {overviewSuccessMessage}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center gap-2">
            <ScrollText className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Описание роли", en: "Role summary" })}
            </h2>
          </div>
          <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700 dark:text-slate-200">
            {fullDescriptionDraft.trim() ||
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
              {baseInstructions.trim()}
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
              {activeRuntimeInstructions.trim() || baseInstructions.trim()}
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
                        {buildSkillAssetPath(previewRuntime, agentSnapshot.slug, skill.slug || "new-skill")}
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
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">{agentSnapshot.author_name}</dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Slug", en: "Slug" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">{agentSnapshot.slug}</dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Категория", en: "Category" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                {categoryDraft.trim() || formatGeneralCategory(locale)}
              </dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Статус", en: "Status" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                {formatStatus(locale, agentSnapshot.status)}
              </dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Верификация", en: "Verification" })}
              </dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                {formatVerificationStatus(locale, agentSnapshot.verification_status)}
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
            <Button
              disabled={!canEditAgentDraft || submittingAssets}
              onClick={addMarkdownFile}
              size="sm"
              type="button"
              variant="secondary"
            >
              <Plus className="mr-2 h-4 w-4" />
              {t(locale, { ru: "Markdown", en: "Markdown" })}
            </Button>
            <Button
              disabled={!canEditAgentDraft || submittingAssets}
              onClick={addSkill}
              size="sm"
              type="button"
              variant="secondary"
            >
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
          ) : !canManageAgent ? (
            <p className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-300">
              {t(locale, {
                ru: "Только автор агента может менять файлы и skills этого профиля.",
                en: "Only the agent author can modify this profile's files and skills."
              })}
            </p>
          ) : agentSnapshot.status === "published" ? (
            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-300">
              <p>
                {t(locale, {
                  ru: "Для опубликованного агента сначала нужен draft revision. Только в нем можно менять файлы и skills без изменения live-профиля.",
                  en: "Published agents need a draft revision first. Files and skills can only be edited there without touching the live profile."
                })}
              </p>
              <Button
                className="mt-3"
                disabled={draftRevisionLoading}
                onClick={() => void onCreateDraftRevision()}
                size="sm"
                type="button"
                variant="secondary"
              >
                <Sparkles className="mr-2 h-4 w-4" />
                {draftRevisionLoading
                  ? t(locale, { ru: "Подготовка...", en: "Preparing..." })
                  : t(locale, { ru: "Создать draft revision", en: "Create draft revision" })}
              </Button>
            </div>
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
                disabled={!canEditAgentDraft || submittingAssets}
                onClick={() => removeAsset(selectedAsset)}
                size="sm"
                type="button"
                variant="ghost"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {t(locale, { ru: "Удалить", en: "Remove" })}
              </Button>
            ) : null}
            <Button
              disabled={!canEditAgentDraft || submittingAssets}
              onClick={() => void saveAssets()}
              size="sm"
              type="button"
            >
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
                disabled={!canEditAgentDraft || submittingAssets}
                onChange={(event) => updateMarkdownFile(selectedAsset.id, { path: event.target.value })}
                placeholder="docs/agent-playbook.md"
                value={markdownFiles.find((file) => file.clientId === selectedAsset.id)?.path ?? ""}
              />
            </label>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              Markdown
              <textarea
                className="mt-1 min-h-[420px] w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-900"
                disabled={!canEditAgentDraft || submittingAssets}
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
                  disabled={!canEditAgentDraft || submittingAssets}
                  onChange={(event) => updateSkill(selectedAsset.id, { slug: event.target.value })}
                  placeholder="delivery-checkpoint"
                  value={skills.find((skill) => skill.clientId === selectedAsset.id)?.slug ?? ""}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Описание", en: "Description" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  disabled={!canEditAgentDraft || submittingAssets}
                  onChange={(event) => updateSkill(selectedAsset.id, { description: event.target.value })}
                  value={skills.find((skill) => skill.clientId === selectedAsset.id)?.description ?? ""}
                />
              </label>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/70">
              <code className="text-xs font-semibold text-brand-700 dark:text-brand-300">
                {buildSkillAssetPath(
                  previewRuntime,
                  agentSnapshot.slug,
                  skills.find((skill) => skill.clientId === selectedAsset.id)?.slug || "new-skill"
                )}
              </code>
            </div>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              SKILL.md
              <textarea
                className="mt-1 min-h-[420px] w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-900"
                disabled={!canEditAgentDraft || submittingAssets}
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
                  {formatStatus(locale, agentSnapshot.status)}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                  <Sparkles className="h-3.5 w-3.5" />
                  {formatVerificationStatus(locale, agentSnapshot.verification_status)}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                  <Bot className="h-3.5 w-3.5" />
                  {categoryDraft.trim() || formatGeneralCategory(locale)}
                </span>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Agent profile", en: "Agent profile" })}
                </p>
                <h1 className="text-3xl font-black tracking-tight text-slate-950 dark:text-slate-50">
                  {titleDraft}
                </h1>
                <p className="max-w-3xl text-sm leading-7 text-slate-600 dark:text-slate-300">
                  {shortDescriptionDraft}
                </p>
              </div>

              <div className="flex flex-wrap gap-x-6 gap-y-3 text-sm">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                    {t(locale, { ru: "Автор", en: "Author" })}
                  </p>
                  <p className="font-semibold text-slate-900 dark:text-slate-100">{agentSnapshot.author_name}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                    {t(locale, { ru: "Slug", en: "Slug" })}
                  </p>
                  <p className="font-semibold text-slate-900 dark:text-slate-100">{agentSnapshot.slug}</p>
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
              slug={agentSnapshot.slug}
              status={agentSnapshot.status}
              supportedRuntimes={exportTargets}
            />
          ) : null}
        </div>
      </div>
    </section>
  );
}
