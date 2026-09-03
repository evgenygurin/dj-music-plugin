# Cell 14 — OpenCode Runtime Smoke

Run this exact bounded MECE smoke test.

1. Do not inspect the application source. Do not modify any existing user file. Do not stage or commit.
2. Run exactly these shell checks from repository root:
   - `git status --short`
   - `test -f .mece/WAVE.md && echo WAVE_OK`
   - `for d in .mece/cells/*; do [ -d "$d" ] || continue; printf '%s ' "$(basename "$d")"; [ -f "$d/TASK.md" ] && printf 'TASK ' || printf 'NO_TASK '; [ -f "$d/REPORT.md" ] && echo REPORT || echo NO_REPORT; done`
   - `opencode debug config | grep -A2 -B1 '"plugin"' | head -20`
3. Create `.mece/cells/14-opencode-runtime-smoke/REPORT.md` yourself using a shell heredoc. Include the observed output summary, PASS if OpenCode reached this task and the commands ran, otherwise BLOCKED.
4. The report must say this is a runtime smoke, not a full application verification.
5. Stop immediately after writing REPORT.md.
