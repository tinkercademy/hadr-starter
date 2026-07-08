#!/usr/bin/env python3
"""Stage 3: the only thing that talks to Telegram. Deterministic template.

Modes (--auto picks from env, the workflow uses that):
  digest   — state/diff.json says "change": per-target counts + MR links
  failure  — scan errored or a later stage failed: ⚠️ alert
  nothing  — unchanged run: send nothing, exit 0

Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID => dry-run: print the exact
message and exit 0 (never crash, never skip silently). A non-2xx Bot API
response exits 1 — an undelivered alert is a failure.

Env consumed by --auto:
  SCAN_RESULT    unchanged|changed|error   (from diff.py's $GITHUB_OUTPUT)
  REPORT_RESULT  success|failure|skipped   (model stage job result)
  DASHBOARD_URL  link put in the digest
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cvelib
from cvelib import STATE_DIR, severity_rank

MAX_TARGET_LINES = 20  # Telegram hard-caps messages at 4096 chars
SEV_ICON = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢",
            "UNKNOWN": "⚪"}


def digest_message(diff: dict, fixes: list[dict], dashboard_url: str,
                   date: str) -> str:
    lines = [f"🛡 CVE Patrol — {date}", ""]
    per_target = diff.get("per_target", {})
    ranked = sorted(per_target.items(),
                    key=lambda kv: (severity_rank(kv[1].get("worst") or "UNKNOWN"),
                                    -kv[1].get("new", 0), kv[0]))
    for name, t in ranked[:MAX_TARGET_LINES]:
        icon = SEV_ICON.get(t.get("worst") or "UNKNOWN", "⚪")
        bits = [f"+{t['new']} new" if t.get("new") else None,
                f"-{t['fixed']} fixed" if t.get("fixed") else None,
                f"{t['changed']} revised" if t.get("changed") else None]
        delta = ", ".join(b for b in bits if b) or "no movement"
        lines.append(f"{icon} {name}: {delta} · {t.get('open', 0)} open"
                     f" ({t.get('fixable', 0)} fixable)")
    if len(ranked) > MAX_TARGET_LINES:
        lines.append(f"…and {len(ranked) - MAX_TARGET_LINES} more services — see dashboard")
    lines.append("")
    if fixes:
        lines.append("Fix MRs:")
        for fx in fixes:
            lines.append(f"• {fx['target']}: {fx['mr_url']}")
    else:
        lines.append("Fix MRs: none this run")
    if diff.get("waived_count"):
        lines.append(f"Waived: {diff['waived_count']} findings suppressed")
    lines.append("")
    lines.append(f"Dashboard: {dashboard_url}")
    return "\n".join(lines)


def failure_message(scan_result: str, report_result: str, diff: dict | None,
                    date: str) -> str:
    lines = [f"⚠️ CVE Patrol FAILED — {date}", ""]
    if scan_result == "error":
        lines.append("The scan stage errored — findings are NOT current.")
        for name, status in ((diff or {}).get("targets") or {}).items():
            if status != "ok":
                lines.append(f"• {name}: {status[:200]}")
    elif report_result == "failure":
        lines.append("Scan succeeded but the report/fix stage failed — "
                     "the dashboard and MRs were not updated for this change.")
    else:
        lines.append("The pipeline failed after the scan stage.")
    lines.append("")
    lines.append("Check the GitHub Actions run log. No findings were published "
                 "for this run; do not treat the current dashboard as fresh.")
    return "\n".join(lines)


def send(text: str) -> bool:
    """Send via Bot API. Returns delivered. Dry-run prints and returns False."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("notify: [dry-run] TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set. "
              "Message that would be sent:\n" + "-" * 60)
        print(text)
        print("-" * 60)
        return False
    import requests  # deferred so tests never need it
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text[:4096],
              "disable_web_page_preview": True},
        timeout=15,
    )
    if not resp.ok:
        raise RuntimeError(f"telegram sendMessage failed: {resp.status_code} "
                           f"{resp.text[:300]}")
    return True


def record(kind: str, delivered: bool, run_id: str | None) -> None:
    path = STATE_DIR / "notifications.json"
    log = cvelib.read_json(path) or []
    log.append({"run_id": run_id, "kind": kind, "delivered": delivered,
                "sent_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    cvelib.write_json(path, log[-200:])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true",
                    help="pick digest/failure/nothing from env results")
    ap.add_argument("--mode", choices=["digest", "failure"], default=None)
    ap.add_argument("--date", default=None, help="override date shown (tests)")
    args = ap.parse_args()

    scan_result = os.environ.get("SCAN_RESULT", "")
    report_result = os.environ.get("REPORT_RESULT", "")
    dashboard_url = os.environ.get(
        "DASHBOARD_URL",
        "https://normalwalrus.github.io/container-cve-fixer/dashboard.html")
    date = args.date or dt.date.today().isoformat()

    diff = cvelib.read_json(STATE_DIR / "diff.json")
    fixes = cvelib.read_json(STATE_DIR / "fixes.json") or []

    mode = args.mode
    if args.auto:
        if scan_result == "error" or report_result == "failure":
            mode = "failure"
        elif scan_result == "changed":
            mode = "digest"
        else:
            print("notify: unchanged run — staying quiet")
            return 0

    if mode == "digest":
        if diff is None or diff.get("kind") != "change":
            print("notify: no change diff to report", file=sys.stderr)
            return 1
        text = digest_message(diff, fixes, dashboard_url, date)
    elif mode == "failure":
        text = failure_message(scan_result, report_result, diff, date)
    else:
        print("notify: nothing to do (use --auto or --mode)", file=sys.stderr)
        return 1

    delivered = send(text)
    record(mode, delivered, (diff or {}).get("run_id"))
    print(f"notify: {mode} {'delivered' if delivered else 'dry-run'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
