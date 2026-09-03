import upstreamPlugin from "@mem0/opencode-plugin";
import MemoryClient from "mem0ai";
import { existsSync, readFileSync } from "node:fs";
import { homedir, userInfo } from "node:os";
import { join } from "node:path";

const MIN_RETRIEVAL_LENGTH = 40;
const MAX_MEMORIES = 5;
const SECRET_PATTERNS = [
  /sk-[A-Za-z0-9_-]{20,}/g,
  /m0-[A-Za-z0-9_-]{20,}/g,
  /AKIA[0-9A-Z]{16}/g,
  /xox[baprs]-[A-Za-z0-9-]{20,}/g,
  /ghp_[A-Za-z0-9]{36,}/g,
  /gho_[A-Za-z0-9]{36,}/g,
  /Bearer\s+[A-Za-z0-9._-]{20,}/gi,
];

export function redactMemoryText(text) {
  let result = String(text ?? "");
  for (const pattern of SECRET_PATTERNS) result = result.replace(pattern, "[REDACTED]");
  return result;
}

export function classifyDurableMemory(text) {
  const value = String(text ?? "").trim();
  if (value.length < MIN_RETRIEVAL_LENGTH) return null;
  const rules = [
    ["architecture_decisions", /(решили|оставляем|используем|не использовать|всегда|никогда|учти на будущее|запомни|архитектур|design decision|architecture decision)/i],
    ["debugging_notes", /(ошибк|exception|traceback|panic|bug|workaround|root cause|почини|исправил|диагностик|регрес)/i],
    ["dependencies", /(зависимост|dependency|package|библиотек|library|верси[яю]|sdk|runtime|провайдер)/i],
    ["environment_setup", /(env|environment|переменн.*окруж|конфиг|configuration|настройк|toolchain)/i],
    ["testing_strategy", /(test|тест|pytest|coverage|typecheck|lint|ruff|mypy|провер[кя]|верификац)/i],
    ["deployment", /(deploy|deployment|production|продакшен|сервер|инфраструктур|ci\/cd|release|релиз)/i],
    ["security", /(security|безопасн|secret|секрет|token|credential|auth|авторизац|privacy|приватност)/i],
    ["code_conventions", /(style|convention|conventions|правил.*кода|стандарт.*кода|кодстайл|naming|именование)/i],
    ["api_design", /(api|endpoint|schema|контракт|interface|интерфейс|protocol|протокол)/i],
    ["data_models", /(data model|модель данных|entity|сущност|migration|миграци|schema|таблиц|database|баз.*данн)/i],
    ["algorithms", /(algorithm|алгоритм|heuristic|эвристик|ranking|ранжирован|matching|матчинг|signal processing|обработк.*сигнал)/i],
    ["performance", /(performance|производительност|latency|задержк|benchmark|бенчмарк|bottleneck|узк.*мест|cache|кэш|concurr|параллел|resource budget|ресурс)/i],
    ["error_handling", /(error handling|обработк.*ошиб|retry|повторн.*попыт|fallback|отказоустойчив|resilien|failure mode|режим.*отказ)/i],
    ["refactoring_history", /(refactor|рефактор|migration|миграци|deprecated|устарел|removed approach|удалили|заменили|переписали)/i],
    ["integrations", /(integration|интеграц|mcp|plugin|плагин|external service|внешн.*сервис|webhook)/i],
    ["onboarding", /(onboarding|онбординг|entry point|точк.*вход|workflow|рабоч.*процесс|как устроен|архитектурн.*ориентир)/i],
    ["project_meta", /(project purpose|цель.*проекта|назначен.*проекта|scope|област.*проекта|goal|цель|roadmap|долгосроч)/i],
    ["user_preferences", /(предпочита|preference|не хочу|хочу использовать|предпочтитель|стиль работ|workflow preference)/i],
    ["tooling_workflow", /(opencode|codex|cursor|claude code|cli|terminal|tooling|инструмент.*разработ|автоматизац|agent workflow)/i],
    ["research_findings", /(исследован|research|arxiv|paper|научн|benchmark|официальн.*документац|documentation finding|статья)/i],
  ];
  return rules.find(([, rule]) => rule.test(value))?.[0] ?? null;
}

export function buildProjectFilters(userId, appId) {
  // Mem0 extracted memories are attributed to an entity; app_id is an additional
  // partition field. Do not require both user_id and app_id in one AND branch.
  return { AND: [{ user_id: userId }, { app_id: appId }] };
}

function extractMemories(response) {
  const values = response?.results ?? response;
  if (!Array.isArray(values)) return [];
  return values
    .filter((item) => item?.id && item?.memory)
    .map((item) => ({ id: item.id, memory: String(item.memory) }));
}

function resolveApiKey() {
  const direct = process.env.MEM0_API_KEY?.trim();
  if (direct) return direct;
  for (const profile of [".zprofile", ".zshrc", ".bash_profile", ".bashrc"]) {
    const path = join(homedir(), profile);
    if (!existsSync(path)) continue;
    const match = readFileSync(path, "utf8").match(/^\s*(?:export\s+)?MEM0_API_KEY=(.+)$/m);
    if (match) {
      const value = match[1].trim().replace(/^['"]|['"]$/g, "");
      if (value && !value.startsWith("$")) return value;
    }
  }
  return "";
}

async function resolveIdentity($, worktree) {
  const userId = process.env.MEM0_USER_ID?.trim() || userInfo().username;
  const shell = worktree ? $.cwd(worktree) : $;
  let appId = process.env.MEM0_APP_ID?.trim();
  if (!appId) {
    try {
      const result = await shell`git remote get-url origin`.quiet();
      const remote = result.stdout.toString().trim();
      const match = remote.match(/[:/]([^/:]+)\/([^/]+?)(?:\.git)?$/);
      appId = match ? `${match[1]}-${match[2]}` : "";
    } catch {}
  }
  if (!appId) {
    try {
      const result = await shell`git rev-parse --show-toplevel`.quiet();
      appId = result.stdout.toString().trim().split("/").pop();
    } catch {}
  }
  return { userId, appId: appId || "opencode-project" };
}

function uniqueMemories(...responses) {
  const seen = new Set();
  return responses.flatMap(extractMemories).filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  }).slice(0, MAX_MEMORIES);
}

function categoryFilters(userId, appId, category) {
  return {
    AND: [
      { user_id: userId },
      { app_id: appId },
      { metadata: { type: category } },
    ],
  };
}

export function createMem0PolicyHooks({ mem0, userId, appId, sessionId, branch, log = async () => {} }) {
  const stats = { searches: 0, adds: 0 };
  const projectFilters = buildProjectFilters(userId, appId);

  const reportError = async (operation, error) => {
    await log({ service: "mem0", level: "warn", message: `${operation} failed: ${error?.message ?? String(error)}` }).catch(() => {});
  };

  async function retrieve(prompt) {
    const safePrompt = redactMemoryText(prompt).trim();
    if (safePrompt.length < MIN_RETRIEVAL_LENGTH) return [];
    const category = classifyDurableMemory(safePrompt) ?? "task_learning";
    const focusedQuery = category === "task_learning"
      ? "task learning current project implementation"
      : safePrompt;
    try {
      const [semantic, focused] = await Promise.all([
        mem0.search(safePrompt, { filters: projectFilters, topK: 3 }),
        mem0.search(focusedQuery, { filters: categoryFilters(userId, appId, category), topK: 3 }),
      ]);
      stats.searches += 2;
      return uniqueMemories(semantic, focused);
    } catch (error) {
      await reportError("search", error);
      return [];
    }
  }

  async function capture(prompt) {
    const safePrompt = redactMemoryText(prompt).trim();
    const type = classifyDurableMemory(safePrompt);
    if (!type) return false;
    try {
      await mem0.add([{ role: "user", content: safePrompt }], {
        user_id: userId,
        app_id: appId,
        metadata: { type, source: "opencode-policy", confidence: 0.8, session_id: sessionId, branch },
        infer: true,
      });
      stats.adds += 1;
      return true;
    } catch (error) {
      await reportError("add", error);
      return false;
    }
  }

  return {
    stats,
    async chatMessage(input, output) {
      const parts = output?.parts ?? input?.parts ?? [];
      const text = parts.filter((part) => part?.type === "text" && !part.synthetic).map((part) => part.text ?? "").join("\n").trim();
      if (text.length < MIN_RETRIEVAL_LENGTH) return;
      const memories = await retrieve(text);
      if (memories.length) {
        const lines = memories.map((item) => `- ${item.memory}`).join("\n");
        await log({ service: "mem0", level: "info", message: `Retrieved ${memories.length} project memories for current task` }).catch(() => {});
        const target = output?.parts;
        if (Array.isArray(target)) target.unshift({ type: "text", text: `Relevant Mem0 memories:\n${lines}` });
      }
      void capture(text);
    },
  };
}

export default async function mem0PolicyPlugin(ctx) {
  const apiKey = resolveApiKey();
  if (!apiKey) return {};
  const upstream = await upstreamPlugin(ctx);
  const worktree = ctx.worktree || ctx.directory || "";
  const { userId, appId } = await resolveIdentity(ctx.$, worktree);
  const sessionId = `ses_${Date.now().toString(36)}`;
  let branch = "main";
  try {
    const result = await (worktree ? ctx.$.cwd(worktree) : ctx.$)`git branch --show-current`.quiet();
    branch = result.stdout.toString().trim() || branch;
  } catch {}

  const mem0 = new MemoryClient({ apiKey });
  const logger = async (body) => ctx.client?.app?.log ? ctx.client.app.log({ body }) : undefined;
  const policy = createMem0PolicyHooks({ mem0, userId, appId, sessionId, branch, log: logger });

  return {
    config: upstream.config,
    tool: upstream.tool,
    "chat.message": policy.chatMessage,
    "shell.env": async (_input, output) => {
      if (!output?.env) return;
      output.env.MEM0_USER_ID = userId;
      output.env.MEM0_APP_ID = appId;
      output.env.MEM0_SESSION_ID = sessionId;
      output.env.MEM0_BRANCH = branch;
      output.env.MEM0_MEMORY_SCOPE = "project";
    },
  };
}
