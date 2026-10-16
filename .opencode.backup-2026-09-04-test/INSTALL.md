# Installing Superpowers for OpenCode

## Prerequisites

- [OpenCode.ai](https://opencode.ai) installed

## Installation

Add superpowers to the `plugin` array in your `opencode.json` (global or project-level):

```json
{
  "plugin": ["superpowers@git+https://github.com/obra/superpowers.git"]
}
```

Restart OpenCode. The plugin installs through OpenCode's plugin manager.

## Migrating from old symlink install

```bash
rm -f ~/.config/opencode/plugins/superpowers.js
rm -rf ~/.config/opencode/skills/superpowers
rm -rf ~/.config/opencode/superpowers
```

Then follow installation above.

## Usage

Use OpenCode's native `skill` tool:
```
use skill tool to list skills
use skill tool to load brainstorming
```

## Tool Mapping

Skills name actions; these map to OpenCode tools:
- "Create a todo" → `todowrite`
- "Dispatch a subagent" → `task` with `subagent_type: "general"` or `"explore"`
- "Invoke a skill" → OpenCode's native `skill` tool
- "Read/edit/write files" → `read`, `apply_patch`
- "Run a shell command" → `bash`
- "Search" → `grep`, `glob`
- "Fetch a URL" → `webfetch`

## Updating

Clear the package cache or reinstall to pick up updates:
```json
{
  "plugin": ["superpowers@git+https://github.com/obra/superpowers.git#v6.1.1"]
}
```
