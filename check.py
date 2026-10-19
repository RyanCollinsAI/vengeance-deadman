"""Dead-man's switch check, run by GitHub Actions.

Vengeance writes a UTC timestamp to the repo variable VM_HEARTBEAT every run of
RemoteAccessWatch (15 min). This script reads it, and tells Telegram once when
check-ins stop and once when they return. The "already alerted" flag lives in
state.json, committed by the workflow only when it changes.

Env: VARS_JSON (all repo variables), BOT_TOKEN, CHAT_ID, STALE_MIN,
     VAR_NAME (default VM_HEARTBEAT), STATE_FILE (default state.json),
     PREFIX (default empty; "TEST " for tests), DRY (1 = print, send nothing)
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

var_name = os.environ.get("VAR_NAME") or "VM_HEARTBEAT"
state_path = Path(os.environ.get("STATE_FILE") or "state.json")
stale_min = float(os.environ["STALE_MIN"])
prefix = os.environ.get("PREFIX", "")
dry = os.environ.get("DRY") == "1"

beat = json.loads(os.environ["VARS_JSON"])[var_name]
last = datetime.fromisoformat(beat)
now = datetime.now(timezone.utc)
age_min = (now - last).total_seconds() / 60

state = json.loads(state_path.read_text()) if state_path.exists() else {"down": False}
stale = age_min > stale_min
print(f"heartbeat {beat} age {age_min:.0f} min, threshold {stale_min:.0f}, was_down={state['down']}")


def send(text: str) -> None:
    print("SEND:", text)
    if dry:
        return
    body = json.dumps({"chat_id": os.environ["CHAT_ID"], "text": text,
                       "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{os.environ['BOT_TOKEN']}/sendMessage",
        body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        assert resp.status == 200, resp.status


if stale and not state["down"]:
    send(f"{prefix}\U0001F534 remote-access: DEAD - Vengeance has not checked in for "
         f"{age_min:.0f} min (last {beat}). Power, home internet or Windows is down. "
         "See routines/remote-access-watch/Abroad-Runbook.md.")
    state = {"down": True, "since": beat}
elif not stale and state["down"]:
    send(f"{prefix}\U0001F7E2 remote-access: back - Vengeance checked in again "
         f"(it was silent since {state['since']}).")
    state = {"down": False}

state["checked"] = now.strftime("%Y-%m-%d")  # a daily commit keeps GitHub from pausing the cron
state_path.write_text(json.dumps(state, indent=1) + "\n")
