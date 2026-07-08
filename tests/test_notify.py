"""The digest is a deterministic template: same diff, same message — pinned
by a golden file. Failure alerts must never render as digests."""
import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import FIXTURES
from notify import digest_message, failure_message

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

DIFF = {
    "run_id": "r1",
    "kind": "change",
    "waived_count": 2,
    "per_target": {
        "backend": {"new": 2, "fixed": 1, "changed": 0, "open": 41,
                    "fixable": 12, "worst": "CRITICAL", "status": "ok"},
        "ingestion": {"new": 0, "fixed": 0, "changed": 0, "open": 3,
                      "fixable": 0, "worst": "MEDIUM", "status": "ok"},
    },
}
FIXES = [{"target": "backend",
          "mr_url": "https://gitlab.com/group/backend/-/merge_requests/7"}]
URL = "https://normalwalrus.github.io/container-cve-fixer/dashboard.html"


def test_digest_matches_golden():
    got = digest_message(DIFF, FIXES, URL, date="2026-07-08")
    want = (FIXTURES / "digest_message.txt").read_text().rstrip("\n")
    assert got == want


def test_digest_truncates_to_message_limit():
    many = {f"svc{i:03d}": {"new": 1, "fixed": 0, "changed": 0, "open": 5,
                            "fixable": 1, "worst": "LOW", "status": "ok"}
            for i in range(60)}
    text = digest_message({**DIFF, "per_target": many}, [], URL, "2026-07-08")
    assert "…and 40 more services — see dashboard" in text
    assert len(text) <= 4096


def test_failure_message_names_broken_targets():
    text = failure_message("error", "", {"targets": {"backend": "error: boom"}},
                           "2026-07-08")
    assert text.startswith("⚠️ CVE Patrol FAILED")
    assert "backend: error: boom" in text
    assert "do not treat the current dashboard as fresh" in text


def run_notify(state_dir, env_extra):
    env = {**os.environ, "CVE_PATROL_STATE": str(state_dir), **env_extra}
    env.pop("TELEGRAM_BOT_TOKEN", None)
    env.pop("TELEGRAM_CHAT_ID", None)
    return subprocess.run([sys.executable, str(SCRIPTS / "notify.py"), "--auto",
                           "--date", "2026-07-08"],
                          env=env, capture_output=True, text=True)


def test_auto_unchanged_sends_nothing(tmp_path):
    proc = run_notify(tmp_path, {"SCAN_RESULT": "unchanged"})
    assert proc.returncode == 0
    assert "staying quiet" in proc.stdout
    assert not (tmp_path / "notifications.json").exists()


def test_auto_changed_dry_runs_digest_without_secrets(tmp_path):
    (tmp_path).mkdir(exist_ok=True)
    (tmp_path / "diff.json").write_text(json.dumps(DIFF))
    proc = run_notify(tmp_path, {"SCAN_RESULT": "changed"})
    assert proc.returncode == 0
    assert "[dry-run]" in proc.stdout and "🛡 CVE Patrol" in proc.stdout
    log = json.loads((tmp_path / "notifications.json").read_text())
    assert log[-1]["kind"] == "digest" and log[-1]["delivered"] is False


def test_auto_error_sends_failure_not_digest(tmp_path):
    (tmp_path / "diff.json").write_text(json.dumps({"kind": "error", "run_id": "r1",
                                                    "targets": {"backend": "error: x"}}))
    proc = run_notify(tmp_path, {"SCAN_RESULT": "error"})
    assert proc.returncode == 0
    assert "⚠️ CVE Patrol FAILED" in proc.stdout
    assert "🛡" not in proc.stdout
