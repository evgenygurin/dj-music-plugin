// dist/index.js
import { execFileSync as execFileSync4 } from "node:child_process";
import { tool } from "@opencode-ai/plugin";

// dist/config.js
import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { homedir } from "os";
var DEFAULTS = {
  gitnexusVersion: "1.5.2",
  autoRefreshStale: true,
  autoRefreshOnCommit: true
};
var CONFIG_FILENAME = "gitnexus-opencode.json";
function loadConfig(cwd) {
  const projectPath = join(cwd, ".opencode", CONFIG_FILENAME);
  const globalPath = join(homedir(), ".config", "opencode", CONFIG_FILENAME);
  let merged = { ...DEFAULTS };
  for (const cfgPath of [globalPath, projectPath]) {
    if (existsSync(cfgPath)) {
      try {
        const raw = JSON.parse(readFileSync(cfgPath, "utf-8"));
        merged = { ...merged, ...raw };
      } catch {
      }
    }
  }
  return merged;
}
function gitnexusCmd(config) {
  const pkg = config.gitnexusVersion === "latest" ? "gitnexus" : `gitnexus@${config.gitnexusVersion}`;
  return ["npx", "-y", pkg];
}

// dist/discovery.js
import { readdirSync, realpathSync, statSync } from "node:fs";
import { execFileSync as execFileSync2 } from "node:child_process";
import { basename, join as join3 } from "node:path";

// dist/staleness.js
import { existsSync as existsSync2, readFileSync as readFileSync2 } from "fs";
import { execFileSync } from "child_process";
import { join as join2 } from "path";
function readMeta(repoPath) {
  const metaPath = join2(repoPath, ".gitnexus", "meta.json");
  if (!existsSync2(metaPath))
    return null;
  try {
    return JSON.parse(readFileSync2(metaPath, "utf-8"));
  } catch {
    return null;
  }
}
function getHeadCommit(repoPath) {
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: repoPath,
      encoding: "utf-8",
      timeout: 5e3,
      stdio: ["pipe", "pipe", "pipe"]
    }).trim();
  } catch {
    return "";
  }
}
function hasIndex(repoPath) {
  return existsSync2(join2(repoPath, ".gitnexus", "meta.json"));
}
function isStale(repoPath) {
  const meta = readMeta(repoPath);
  if (!meta)
    return false;
  const head = getHeadCommit(repoPath);
  if (!head)
    return false;
  return head !== meta.lastCommit;
}

// dist/discovery.js
function isGitRepo(dirPath) {
  try {
    const root = execFileSync2("git", ["rev-parse", "--show-toplevel"], {
      cwd: dirPath,
      encoding: "utf-8",
      timeout: 3e3,
      stdio: ["pipe", "pipe", "pipe"]
    }).trim();
    return root === realpathSync(dirPath);
  } catch {
    return false;
  }
}
function discoverRepos(parentDir, onError) {
  const repos = [];
  if (isGitRepo(parentDir)) {
    repos.push({
      name: basename(parentDir) || parentDir,
      path: parentDir,
      hasIndex: hasIndex(parentDir),
      isStale: isStale(parentDir)
    });
    return repos;
  }
  let entries;
  try {
    entries = readdirSync(parentDir);
  } catch (err) {
    onError?.(`Cannot read ${parentDir}: ${err instanceof Error ? err.message : String(err)}`);
    return repos;
  }
  for (const entry of entries) {
    if (entry.startsWith("."))
      continue;
    const fullPath = join3(parentDir, entry);
    try {
      if (!statSync(fullPath).isDirectory())
        continue;
    } catch {
      continue;
    }
    if (isGitRepo(fullPath)) {
      repos.push({
        name: entry,
        path: fullPath,
        hasIndex: hasIndex(fullPath),
        isStale: isStale(fullPath)
      });
    }
  }
  return repos;
}

// dist/context.js
function buildUserToast(repos) {
  if (repos.length === 0)
    return null;
  const unindexed = repos.filter((r) => !r.hasIndex);
  const stale = repos.filter((r) => r.hasIndex && r.isStale);
  if (stale.length === 0 && unindexed.length === 0)
    return null;
  const total = stale.length + unindexed.length;
  const parts = [];
  if (stale.length > 0)
    parts.push(`${stale.length} stale`);
  if (unindexed.length > 0)
    parts.push(`${unindexed.length} unindexed`);
  return `Knowledge graph: ${parts.join(", ")} repo${total > 1 ? "s" : ""}. Ask agent to index.`;
}

// dist/hooks.js
import { execFileSync as execFileSync3, spawn } from "node:child_process";
import { closeSync, existsSync as existsSync3, openSync } from "fs";
import { join as join4 } from "path";

// dist/hint-envelope.js
var OPT_IN_MARKER = "[[gitnexus:graph]]";
function createHintEnvelopeState() {
  const refreshing = /* @__PURE__ */ new Set();
  let cache = {
    envelope: "",
    freshness: "missing",
    updatedAt: 0
  };
  function rebuildHintCache(repos) {
    const indexed = repos.filter((r) => r.hasIndex);
    if (indexed.length === 0) {
      cache = { envelope: "", freshness: "missing", updatedAt: Date.now() };
      return;
    }
    const anyRefreshing = indexed.some((r) => refreshing.has(r.path));
    const anyStale = indexed.some((r) => r.isStale);
    let freshness;
    if (anyRefreshing)
      freshness = "refreshing";
    else if (anyStale)
      freshness = "may_be_stale";
    else
      freshness = "up_to_date";
    cache = {
      envelope: buildEnvelope(indexed, freshness),
      freshness,
      updatedAt: Date.now()
    };
  }
  return {
    markRefreshing(repoPath) {
      refreshing.add(repoPath);
    },
    markRefreshDone(repoPath) {
      refreshing.delete(repoPath);
    },
    getHintCache() {
      return cache;
    },
    rebuildHintCache,
    refreshHintCache(scanRoot) {
      const repos = discoverRepos(scanRoot);
      rebuildHintCache(repos);
    },
    reset() {
      refreshing.clear();
      cache = { envelope: "", freshness: "missing", updatedAt: 0 };
    }
  };
}
var LEADING_ENVELOPE_RE = /^<gitnexus_graph\b[^>]*>[\s\S]*?<\/gitnexus_graph>(?:\r?\n){0,2}/;
function scrubPromptGitnexusBlocks(text) {
  let scrubbed = text;
  while (LEADING_ENVELOPE_RE.test(scrubbed)) {
    scrubbed = scrubbed.replace(LEADING_ENVELOPE_RE, "");
  }
  return scrubbed;
}
function stripOptInMarker(text) {
  if (!text.includes(OPT_IN_MARKER))
    return text;
  const SOLO_LINE = new RegExp(`(^|\r?
)[ 	]*${escapeRegex(OPT_IN_MARKER)}[ 	]*(?=\r?
|$)\r?
?`, "g");
  let out = text.replace(SOLO_LINE, (_m, lead) => lead);
  out = out.split(OPT_IN_MARKER).join("");
  return out.replace(/^[ \t]+/, "").replace(/[ \t]+$/, "");
}
function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function escapeXml(value) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}
function freshnessSummary(freshness) {
  switch (freshness) {
    case "up_to_date":
      return "Code knowledge graph is available. Graph is current.";
    case "refreshing":
      return "Code knowledge graph is available. A background refresh is in progress; some symbols may be from the previous HEAD until it completes.";
    case "may_be_stale":
      return "Code knowledge graph is available but may be stale (HEAD has moved since last analyze). Results are still useful for structure; re-run gitnexus_analyze if precision matters.";
    case "missing":
      return "";
  }
}
function buildEnvelope(indexed, freshness) {
  const repoLines = indexed.map((r) => `<repo name="${escapeXml(r.name)}" path="${escapeXml(r.path)}"/>`).join("\n");
  return `<gitnexus_graph source="gitnexus" version="2" freshness="${freshness}">
<summary>${escapeXml(freshnessSummary(freshness))}</summary>
<indexed_repos>
${repoLines}
</indexed_repos>
<rules>See the GitNexus section of the system prompt for tool preference and subagent propagation rules (marker ${OPT_IN_MARKER}).</rules>
</gitnexus_graph>`;
}

// dist/system-addendum.js
var SYSTEM_ADDENDUM_START = "<!-- gitnexus:system:start -->";
var SYSTEM_ADDENDUM_END = "<!-- gitnexus:system:end -->";
var STATIC_SYSTEM_ADDENDUM = `${SYSTEM_ADDENDUM_START}
# GitNexus knowledge graph

A \`<gitnexus_graph>\` envelope is delivered in user messages with the live
list of indexed repos and their freshness \u2014 re-read it each turn. If absent
(cwd has no local indexes), call \`gitnexus_list_repos\` once to discover
repos indexed elsewhere; target them via the \`repo\` parameter on any
gitnexus_* tool.

## Subagent propagation

Spawned subagents do NOT inherit the user-message envelope. Include the
literal marker \`${OPT_IN_MARKER}\` in the prompt to grant graph access \u2014
the plugin swaps it for the envelope and strips the marker.

- INCLUDE for code agents: explore, deep, build, quick, refactor, sisyphus-junior, general
- OMIT for non-code agents: librarian, oracle, Momus, Metis, Prometheus, multimodal-looker
- INCLUDE regardless of agent type when the prompt references an absolute
  path under any \`<repo path="...">\` in the envelope \u2014 without the marker
  the subagent will Grep the tree where one gitnexus_query would suffice.

## Tools (your own calls)

Prefer for structural questions: gitnexus_query, gitnexus_context,
gitnexus_impact, gitnexus_cypher, gitnexus_list_repos. Keep Grep/Read for
literal strings, configs, file-level navigation.
For open-ended exploration or multi-flow tracing, delegate to a subagent
with \`${OPT_IN_MARKER}\` instead of stacking inline calls.

## When to build a graph yourself

Default: if you are going to touch an unindexed repo more than trivially,
start with \`gitnexus_analyze\`. "Trivially" = one file, already open, edit
you could make without understanding the rest of the repo.

Everything else \u2014 exploration, debugging, multi-file changes, anything that
starts with "look into\u2026" / "how does\u2026" / "why\u2026" / "add\u2026" \u2014 warrants building
the graph first because graph queries will outpace grep within 2 tool calls.
${SYSTEM_ADDENDUM_END}`;
var STATIC_SYSTEM_ADDENDUM_SUBAGENT = `${SYSTEM_ADDENDUM_START}
# GitNexus knowledge graph

If a \`<gitnexus_graph>\` envelope is delivered in your user messages, it lists
the repos currently indexed and reachable via the \`repo\` parameter. Re-read
it each turn for live data. If absent, call \`gitnexus_list_repos\` once to
discover repos indexed elsewhere on the machine.

## Tools (your own calls)

Prefer for structural questions: gitnexus_query, gitnexus_context,
gitnexus_impact, gitnexus_cypher, gitnexus_list_repos. Keep Grep/Read for
literal strings, configs, file-level navigation.
${SYSTEM_ADDENDUM_END}`;
function systemAddendumPresent(sections) {
  for (const section of sections) {
    if (section.includes(SYSTEM_ADDENDUM_START))
      return true;
  }
  return false;
}

// dist/hooks.js
var GIT_MUTATION_RE = /(?:^|[;&|]\s*)(?:\w+=\S+\s+)*git(?:\s+-C\s+\S+|\s+--\S+(?:=\S+)?)*\s+(commit|merge|rebase|pull|cherry-pick|switch|reset)\b/;
var GRAPH_HINT = `
[gitnexus] Code knowledge graph available. Use gitnexus_query/context/impact
instead of explore agents for structure/flows/dependencies.
Use grep only for: comments, config files, runtime behavior.`;
var INIT_PREREQUISITE = `
[gitnexus:prerequisite]
Before starting exploration, run the gitnexus_analyze tool to build the code knowledge graph.
This costs 0 tokens and provides all functional areas, execution flows,
symbol density, and callers/callees \u2014 saving ~80% of exploration tokens.
After analyze completes, use gitnexus_query/context/cypher instead of spawning
explore agents for codebase understanding.
Only spawn explore agents for: conventions, anti-patterns, CI/build.`;
function createAnalyzeState() {
  const inFlight = /* @__PURE__ */ new Set();
  return {
    schedule(repoPath, config, scanRoot, hintState) {
      if (inFlight.has(repoPath))
        return false;
      inFlight.add(repoPath);
      hintState.markRefreshing(repoPath);
      hintState.refreshHintCache(scanRoot);
      const cleanup = () => {
        inFlight.delete(repoPath);
        hintState.markRefreshDone(repoPath);
        hintState.refreshHintCache(scanRoot);
      };
      try {
        analyzeInBackground(repoPath, config, cleanup);
        return true;
      } catch {
        cleanup();
        return false;
      }
    },
    reset() {
      inFlight.clear();
    }
  };
}
function analyzeInBackground(repoPath, config, onDone) {
  const cmd = gitnexusCmd(config);
  const devNull = openSync("/dev/null", "w");
  let child;
  try {
    child = spawn(cmd[0], [...cmd.slice(1), "analyze", repoPath], {
      stdio: ["ignore", devNull, devNull],
      detached: true,
      cwd: repoPath
    });
  } finally {
    closeSync(devNull);
  }
  child.unref();
  let settled = false;
  const settleOnce = () => {
    if (settled)
      return;
    settled = true;
    onDone();
  };
  child.on("close", settleOnce);
  child.on("error", settleOnce);
}
function createToolHooks(deps) {
  const { cwd, config, disabled, analyzeState, hintState } = deps;
  return {
    onToolExecuteAfter(input, output) {
      if (disabled())
        return;
      if (input.tool === "skill") {
        const name = input.args?.name;
        if (!name)
          return;
        if (name === "init-deep" || name === "init") {
          output.output += INIT_PREREQUISITE;
          return;
        }
        const anyIndexed = existsSync3(join4(cwd, ".gitnexus", "meta.json")) || discoverRepos(cwd).some((r) => r.hasIndex);
        if (anyIndexed) {
          output.output += GRAPH_HINT;
        }
        return;
      }
      if (input.tool === "bash" && config.autoRefreshOnCommit) {
        const cmd = input.args?.command;
        if (!cmd || !GIT_MUTATION_RE.test(cmd))
          return;
        const explicit = extractGitDashCPath(cmd, cwd);
        const repoPath = explicit ?? findGitRoot(cwd);
        if (repoPath && hasIndex(repoPath)) {
          analyzeState.schedule(repoPath, config, cwd, hintState);
        }
      }
    }
  };
}
function findGitRoot(from) {
  try {
    return execFileSync3("git", ["rev-parse", "--show-toplevel"], {
      cwd: from,
      encoding: "utf-8",
      timeout: 3e3,
      stdio: ["pipe", "pipe", "pipe"]
    }).trim();
  } catch {
    return null;
  }
}
function extractGitDashCPath(cmd, cwd) {
  const m = cmd.match(/(?:^|[;&|]\s*)(?:\w+=\S+\s+)*git\s+-C\s+(?:"([^"]+)"|'([^']+)'|(\S+))/);
  if (!m)
    return null;
  const raw = m[1] ?? m[2] ?? m[3];
  if (!raw)
    return null;
  const abs = raw.startsWith("/") ? raw : join4(cwd, raw);
  try {
    const root = findGitRoot(abs);
    return root;
  } catch {
    return null;
  }
}
function historyHasEnvelope(messages) {
  for (const m of messages) {
    if (m.info.role !== "user")
      continue;
    for (const p of m.parts) {
      const text = p.text;
      if (typeof text === "string" && text.includes("<gitnexus_graph")) {
        return true;
      }
    }
  }
  return false;
}
function createMessagesTransformHandler(deps) {
  const { isMain, getCache, lastInjected } = deps;
  const log = deps.log ?? (() => {
  });
  return async function handle(_input, output) {
    try {
      if (output.messages.length === 0)
        return;
      const last = output.messages[output.messages.length - 1];
      if (last.info.role !== "user")
        return;
      const textPart = last.parts.find((p) => p.type === "text" && typeof p.text === "string");
      if (!textPart)
        return;
      const sessionID = last.info.sessionID;
      if (!sessionID)
        return;
      const originalText = textPart.text;
      const scrubbed = scrubPromptGitnexusBlocks(originalText);
      const hasMarker = scrubbed.includes(OPT_IN_MARKER);
      const main = isMain(sessionID);
      const eligible = main || hasMarker;
      if (!eligible)
        return;
      const cache = getCache();
      if (cache.freshness === "missing")
        return;
      const cleaned = hasMarker ? stripOptInMarker(scrubbed) : scrubbed;
      if (lastInjected && !historyHasEnvelope(output.messages)) {
        lastInjected.clear(sessionID);
      }
      const previous = lastInjected?.get(sessionID);
      if (previous !== void 0 && previous === cache.envelope) {
        log("messages.transform skipped (dedup hit): sessionID=" + sessionID + " main=" + main + " marker=" + hasMarker + " freshness=" + cache.freshness, "info");
        if (hasMarker)
          textPart.text = cleaned;
        return;
      }
      textPart.text = `${cache.envelope}

${cleaned}`;
      lastInjected?.set(sessionID, cache.envelope);
      log("messages.transform injected: sessionID=" + sessionID + " main=" + main + " marker=" + hasMarker + " freshness=" + cache.freshness + " dedup=" + (previous === void 0 ? "first" : "changed") + ' textPreview="' + cleaned.slice(0, 60).replace(/\n/g, " ") + '"', "info");
    } catch (err) {
      log(`messages.transform hook error: ${err instanceof Error ? err.message : String(err)}`, "warn");
    }
  };
}
function createSystemTransformHandler(deps) {
  const { disabled, isMain } = deps;
  const log = deps.log ?? (() => {
  });
  return async function handle(input, output) {
    try {
      if (disabled())
        return;
      if (systemAddendumPresent(output.system))
        return;
      const sessionIsKnownSubagent = !!input.sessionID && !isMain(input.sessionID);
      const addendum = sessionIsKnownSubagent ? STATIC_SYSTEM_ADDENDUM_SUBAGENT : STATIC_SYSTEM_ADDENDUM;
      const isMainSession = !sessionIsKnownSubagent;
      output.system.push(addendum);
      log(`system.transform pushed gitnexus addendum (variant=${isMainSession ? "full" : "subagent-lite"} sessionID=${input.sessionID ?? "<none>"})`, "info");
    } catch (err) {
      log(`system.transform hook error: ${err instanceof Error ? err.message : String(err)}`, "warn");
    }
  };
}

// dist/last-injected.js
function createLastInjectedRegistry() {
  const lastBySession = /* @__PURE__ */ new Map();
  return {
    get(sessionID) {
      return lastBySession.get(sessionID);
    },
    set(sessionID, envelope) {
      lastBySession.set(sessionID, envelope);
    },
    clear(sessionID) {
      lastBySession.delete(sessionID);
    },
    reset() {
      lastBySession.clear();
    }
  };
}

// dist/sessions.js
function createSessionRegistry() {
  const subagentSessions = /* @__PURE__ */ new Set();
  return {
    trackCreated(info) {
      if (info.parentID)
        subagentSessions.add(info.id);
    },
    trackDeleted(info) {
      subagentSessions.delete(info.id);
    },
    isMain(sessionID) {
      return !subagentSessions.has(sessionID);
    },
    reset() {
      subagentSessions.clear();
    }
  };
}

// dist/index.js
var TOAST_DELAY_MS = 6e3;
function isGitNexusCliAvailable(config) {
  const cmd = gitnexusCmd(config);
  try {
    execFileSync4(cmd[0], [...cmd.slice(1), "--version"], {
      encoding: "utf-8",
      timeout: 1e4,
      stdio: ["pipe", "pipe", "pipe"]
    });
    return true;
  } catch {
    return false;
  }
}
async function hydrateSubagentRegistry(client, registry, log) {
  try {
    const result = await client.session.list();
    const sessions = result?.data ?? [];
    let subagentCount = 0;
    for (const s of sessions) {
      if (s?.id && s?.parentID) {
        registry.trackCreated({ id: s.id, parentID: s.parentID });
        subagentCount++;
      }
    }
    log(`Hydrated subagent registry from session.list(): ${subagentCount} subagent(s) of ${sessions.length} session(s)`);
  } catch (err) {
    log(`session.list() failed during hydration: ${err instanceof Error ? err.message : String(err)}. Unknown sessions will default to main (safe).`, "warn");
  }
}
var plugin = async ({ directory, worktree, client }) => {
  const scanRoot = worktree ?? directory;
  const config = loadConfig(scanRoot);
  let disabled = false;
  const log = (message, level = "info") => {
    void client.app.log({ body: { service: "gitnexus", level, message } });
  };
  const hintState = createHintEnvelopeState();
  const sessions = createSessionRegistry();
  const analyzeState = createAnalyzeState();
  const lastInjected = createLastInjectedRegistry();
  void hydrateSubagentRegistry(client, sessions, log);
  const toolHooks = createToolHooks({
    cwd: scanRoot,
    config,
    disabled: () => disabled,
    analyzeState,
    hintState
  });
  const messagesTransformHandler = createMessagesTransformHandler({
    isMain: (sessionID) => sessions.isMain(sessionID),
    getCache: () => hintState.getHintCache(),
    lastInjected,
    log
  });
  const systemTransformHandler = createSystemTransformHandler({
    disabled: () => disabled,
    isMain: (sessionID) => sessions.isMain(sessionID),
    log
  });
  const cmd = gitnexusCmd(config);
  const tools = {
    gitnexus_analyze: tool({
      description: "Build or refresh the GitNexus code knowledge graph for a repository. Intended for the main agent; not delegated to subagents.",
      args: {
        path: tool.schema.string().optional().describe("Path to the git repository. Defaults to current directory.")
      },
      async execute(args) {
        const repoPath = args.path || scanRoot;
        try {
          const result = execFileSync4(cmd[0], [...cmd.slice(1), "analyze", repoPath], { encoding: "utf-8", timeout: 3e5, cwd: repoPath });
          return `Graph built successfully for ${repoPath}.
${result}`;
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          return `Failed to build graph: ${msg}`;
        }
      }
    })
  };
  return {
    tool: tools,
    event: async ({ event }) => {
      if (event.type === "session.deleted") {
        const info = event.properties?.info;
        if (info?.id) {
          sessions.trackDeleted({ id: info.id });
          lastInjected.clear(info.id);
        }
        return;
      }
      if (event.type !== "session.created")
        return;
      try {
        const info = event.properties?.info;
        const sessionID = info?.id;
        if (info?.id)
          sessions.trackCreated({ id: info.id, parentID: info.parentID });
        if (!isGitNexusCliAvailable(config)) {
          const cmdStr = gitnexusCmd(config).join(" ");
          log(`CLI not available (${cmdStr} --version failed). Plugin disabled for this session.`, "warn");
          disabled = true;
          return;
        }
        const repos = discoverRepos(scanRoot, (msg) => log(msg, "warn"));
        hintState.refreshHintCache(scanRoot);
        log(`Discovered ${repos.length} repo(s): ${repos.map((r) => r.name).join(", ") || "none"}`);
        if (config.autoRefreshStale) {
          for (const repo of repos) {
            if (repo.hasIndex && repo.isStale) {
              analyzeState.schedule(repo.path, config, scanRoot, hintState);
            }
          }
        }
        if (sessionID) {
          log(`Session ${sessionID} ready; envelope will be injected via messages.transform when eligible`);
        }
        const toastMessage = buildUserToast(repos);
        if (toastMessage) {
          setTimeout(() => {
            client.tui.showToast({
              body: {
                title: "GitNexus",
                message: toastMessage,
                variant: "info",
                duration: 5e3
              }
            }).catch(() => {
            });
          }, TOAST_DELAY_MS);
        }
      } catch (err) {
        log(`session.created handler error: ${err instanceof Error ? err.message : String(err)}`, "error");
      }
    },
    "tool.execute.after": async (input, output) => {
      toolHooks.onToolExecuteAfter(input, output);
    },
    "experimental.chat.messages.transform": async (input, output) => {
      if (disabled)
        return;
      await messagesTransformHandler(input, output);
    },
    "experimental.chat.system.transform": async (input, output) => {
      await systemTransformHandler(input, output);
    }
  };
};
var index_default = plugin;
export {
  index_default as default
};
