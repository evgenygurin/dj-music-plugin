---
name: help
description: Show DJ Music Plugin capabilities — skills, commands, agent, MCP tool categories
argument-hint: (none)
allowed-tools: Bash
---

# DJ Music Plugin — Capabilities

Print a concise overview of everything the plugin exposes.

```bash
cat <<'EOF'
╔══════════════════════════════════════════════════════════════════╗
║                    DJ Music Plugin                                ║
╚══════════════════════════════════════════════════════════════════╝

SKILLS (auto-trigger on natural language)
  /build-set          Build optimized DJ set from a playlist
  /curate-library     Classify, audit, distribute by subgenre
  /deliver-set        Export M3U8 / Rekordbox / JSON / cheat sheet
  /expand-playlist    Discover & import similar tracks
  /review-set         Analyze set quality, find weak transitions
  /ym-sync            Bidirectional sync with Yandex Music

COMMANDS (user-invoked)
  /panel              Start backend + dashboard (http://localhost:3000)
  /panel-setup        Render panel/.env.local from .claude/dj-music.local.md
  /help               This message

AGENT
  dj-assistant        Domain expert for end-to-end DJ workflows.
                      Delegates to MCP tools, follows tiered analysis,
                      uses 6-component transition scoring.

MCP TOOLS — 42 visible by default. Hidden categories unlocked via
unlock_tools(action="unlock", category="..."):
  delivery   discovery   curation   sync   platform   audio   memory

DOCS
  REQUIREMENTS.md         Full spec
  docs/architecture.md    Layered architecture + middleware pipeline
  docs/tool-catalog.md    Complete MCP tool reference
  docs/transition-scoring.md   6-component formula details
  docs/audio-pipeline.md  18 analyzers, tiered L1-L4
  docs/ym-api-guide.md    Yandex Music API quirks
  docs/panel-guide.md     Next.js dashboard architecture

QUICK STARTS
  • Build a peak-time set:    "Собери peak-hour сет из <playlist>"
  • Find why a transition is weak:  "Почему 7→8 в сете 42 слабый?"
  • Expand to N tracks:       "Расширь плейлист X до N треков"
  • Distribute by mood:       "Разложи импортированные треки по поджанрам"
EOF
```
