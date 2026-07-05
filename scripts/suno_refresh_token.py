#!/usr/bin/env python3
"""Refresh the Suno Clerk bearer JWT in .env from a live Chrome session (macOS).

Suno uses header-based Clerk with no persisted ``__session`` cookie, so a
cookie-only ``.env`` cannot mint a bearer server-side (Clerk reports zero
sessions). The only durable source of a fresh token is the browser's own
authenticated session.

This script drives the already-open Suno tab in Chrome: it runs a page-context
``fetch`` to ``auth.suno.com`` (which sends the browser's live cookies, incl.
whatever is only in the browser's jar) to mint a Clerk token, then writes it to
``DJ_SUNO_BEARER_TOKEN`` in ``.env``. The token is valid ~57 min.

Requirements (one-time):
- Chrome open, logged into https://suno.com
- Chrome ▸ View ▸ Developer ▸ "Allow JavaScript from Apple Events" enabled

Usage:
    uv run python scripts/suno_refresh_token.py [--env PATH]
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

CLERK_PARAMS = "?__clerk_api_version=2025-11-10&_clerk_js_version=5.117.0"

# Page-context Clerk mint. Stores the JWT in window.__djTok, a reason in
# window.__djInfo. Runs on any suno.com tab (credentials:include uses the
# browser's live cookie jar).
_FIRE_JS = f"""
(function(){{
  window.__djTok=null; window.__djInfo="pending";
  var V="{CLERK_PARAMS}";
  var C="https://auth.suno.com/v1/client";
  (async function(){{
    try{{
      var c=await fetch(C+V,{{credentials:"include"}}).then(r=>r.json());
      var resp=c.response||c; var sessions=resp.sessions||[];
      var sid=resp.last_active_session_id||(sessions[0]&&sessions[0].id);
      if(!sid){{
        window.__djInfo="no-session (re-login on suno.com?) n="+sessions.length;
        return;
      }}
      var url=C+"/sessions/"+sid+"/tokens"+V;
      var t=await fetch(url,{{method:"POST",credentials:"include"}}).then(r=>r.json());
      window.__djTok=t.jwt||(t.response&&t.response.jwt)||null;
      window.__djInfo=window.__djTok?"ok":"no-jwt-in-response";
    }}catch(e){{ window.__djInfo="err:"+String(e); }}
  }})();
  return "fired";
}})()
"""


def _osascript(applescript: str) -> tuple[int, str]:
    proc = subprocess.run(["osascript", "-"], input=applescript, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or proc.stderr).strip()


def _chrome_running() -> bool:
    code, out = _osascript(
        'tell application "System Events" to (name of processes) contains "Google Chrome"'
    )
    return code == 0 and "true" in out.lower()


def _open_suno() -> None:
    _osascript(
        'tell application "Google Chrome"\n'
        " activate\n"
        ' open location "https://suno.com/create"\n'
        "end tell"
    )


def _mint_token() -> tuple[str | None, str]:
    """Return (jwt|None, info). Drives the live Suno tab."""
    fire_path = Path("/tmp/dj_suno_refresh_fire.js")
    fire_path.write_text(_FIRE_JS, encoding="utf-8")
    script = f"""
set fireJS to (read POSIX file "{fire_path}" as «class utf8»)
tell application "Google Chrome"
  set targetTab to missing value
  repeat with w in windows
    repeat with t in tabs of w
      if (URL of t) contains "suno.com" then set targetTab to t
    end repeat
  end repeat
  if targetTab is missing value then return "NO_SUNO_TAB"
  execute targetTab javascript fireJS
  delay 3
  return execute targetTab javascript "window.__djTok || (\\"INFO:\\" & window.__djInfo)"
end tell
"""
    code, out = _osascript(script)
    if code != 0:
        if "JavaScript through AppleScript" in out or "события Apple" in out:
            return None, (
                "Chrome blocks AppleScript JS. Enable: View ▸ Developer ▸ "
                "'Allow JavaScript from Apple Events', then retry."
            )
        return None, f"osascript error: {out}"
    if out == "NO_SUNO_TAB":
        return None, "NO_SUNO_TAB"
    if out.startswith("INFO:"):
        return None, out[5:]
    if out.count(".") == 2 and len(out) > 100:
        return out, "ok"
    return None, f"unexpected result: {out[:120]}"


def _write_env(env_path: Path, token: str) -> None:
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    key = "DJ_SUNO_BEARER_TOKEN"
    idx = next(
        (i for i, ln in enumerate(lines) if ln.split("=", 1)[0] == key and not ln.startswith("#")),
        None,
    )
    newline = f"{key}={token}"
    if idx is not None:
        lines[idx] = newline
    else:
        lines.append(newline)
    env_path.write_text("\n".join(lines) + "\n")


def _exp_seconds(token: str) -> int | None:
    try:
        p = token.split(".")[1]
        p += "=" * (-len(p) % 4)
        claims = json.loads(base64.urlsafe_b64decode(p))
        exp = claims.get("exp")
        return int(exp - time.time()) if exp else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh Suno bearer JWT in .env from live Chrome.")
    ap.add_argument("--env", default=str(Path(__file__).resolve().parent.parent / ".env"))
    args = ap.parse_args()

    if sys.platform != "darwin":
        print("This helper is macOS-only (osascript + Chrome).", file=sys.stderr)
        return 2
    if not _chrome_running():
        print("Chrome is not running. Open Chrome, log into suno.com, retry.", file=sys.stderr)
        return 2

    token, info = _mint_token()
    if token is None and info == "NO_SUNO_TAB":
        print("No suno.com tab found — opening one; give it a few seconds and re-run.")
        _open_suno()
        return 3
    if token is None:
        print(f"Failed to mint token: {info}", file=sys.stderr)
        return 1

    env_path = Path(args.env).expanduser()
    _write_env(env_path, token)
    exp = _exp_seconds(token)
    mins = f"{exp // 60} min" if exp is not None else "unknown"
    print(f"✅ wrote DJ_SUNO_BEARER_TOKEN ({len(token)} chars) to {env_path}; expires in {mins}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
