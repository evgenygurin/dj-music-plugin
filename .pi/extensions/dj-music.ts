// .pi/extensions/dj-music.ts
// DJ Music Plugin — Pi extension that registers MCP server + project skills

export default async function djMusic(api) {
  // Register project skills for discovery
  api.tools?.register({
    name: "dj-music",
    description: "DJ techno library management tools",
  });

  // Register MCP server via the project's .mcp.json
  // Pi reads MCP config from mcpServers convention

  // Inject project context on session start
  api.hooks?.on("session:start", async () => {
    const agentyMd = await api.fs.read("AGENTS.md");
    return { context: agentyMd };
  });

  // Ensure skills are discoverable
  api.skills?.register("skills/");
}
