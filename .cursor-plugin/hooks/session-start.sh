#!/bin/bash
# Cursor session-start hook — injects project context
# Reads AGENTS.md + superpowers bootstrap on session start

plugin_root="$(dirname "$(dirname "$(dirname "$(realpath "$0")")")")"
context=""

# DJ Music plugin context
if [ -f "$plugin_root/AGENTS.md" ]; then
    agenty_content=$(cat "$plugin_root/AGENTS.md")
    context+="$agenty_content\n\n"
fi

# Superpowers bootstrap (if installed)
if [ -f "$plugin_root/.claude/skills/using-superpowers/SKILL.md" ] || \
   [ -d "$plugin_root/node_modules/superpowers/skills/using-superpowers" ]; then
    context+="You have Superpowers. Check for relevant skills before acting."
fi

# Escape for JSON and output
context_json=$(python3 -c "import json; print(json.dumps('''$context'''))" 2>/dev/null || echo "\"$context\"")
echo "{\"additional_context\": $context_json}"
