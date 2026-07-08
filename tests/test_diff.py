"""The exit contract (0 unchanged / 10 changed / 1 error) is what the whole
workflow branches on — exercised here end-to-end via subprocess."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def snapshot(findings, status="ok", run_id="r1"):
    import cvelib
    return {"run_id": run_id, "status": status,
            "targets": {"backend": "ok"},
            "waived_count": 0, "findings": findings,
            "content_hash": cvelib.content_hash(findings)}


FINDING = {"target": "backend", "cve_id": "CVE-2025-1111", "package": "libssl3",
           "installed_version": "3.0.11-1", "fixed_version": "3.0.14-1",
           "severity": "HIGH", "cvss": 8.1, "layer_origin": "base"}


def run_diff(state_dir, *args):
    env = {**os.environ, "CVE_PATROL_STATE": str(state_dir)}
    env.pop("GITHUB_OUTPUT", None)
    return subprocess.run([sys.executable, str(SCRIPTS / "diff.py"), *args],
                          env=env, capture_output=True, text=True)


def write(state_dir, name, obj):
    state_dir.mkdir(exist_ok=True)
    (state_dir / name).write_text(json.dumps(obj))


def test_unchanged_exits_0(tmp_path):
    s = snapshot([FINDING])
    write(tmp_path, "scan-latest.json", s)
    write(tmp_path, "snapshot.json", {**s, "run_id": "r0"})
    assert run_diff(tmp_path).returncode == 0


def test_changed_exits_10_and_writes_diff(tmp_path):
    write(tmp_path, "scan-latest.json", snapshot([FINDING]))
    write(tmp_path, "snapshot.json", snapshot([], run_id="r0"))
    proc = run_diff(tmp_path)
    assert proc.returncode == 10
    diff = json.loads((tmp_path / "diff.json").read_text())
    assert [f["cve_id"] for f in diff["new"]] == ["CVE-2025-1111"]
    assert diff["per_target"]["backend"]["new"] == 1
    assert diff["per_target"]["backend"]["worst"] == "HIGH"


def test_first_run_is_changed(tmp_path):
    write(tmp_path, "scan-latest.json", snapshot([FINDING]))
    assert run_diff(tmp_path).returncode == 10


def test_fixed_finding_is_a_change(tmp_path):
    write(tmp_path, "scan-latest.json", snapshot([]))
    write(tmp_path, "snapshot.json", snapshot([FINDING], run_id="r0"))
    proc = run_diff(tmp_path)
    assert proc.returncode == 10
    diff = json.loads((tmp_path / "diff.json").read_text())
    assert [f["cve_id"] for f in diff["fixed"]] == ["CVE-2025-1111"]


def test_partial_scan_exits_1_error(tmp_path):
    write(tmp_path, "scan-latest.json", snapshot([FINDING], status="partial"))
    proc = run_diff(tmp_path)
    assert proc.returncode == 1
    assert json.loads((tmp_path / "diff.json").read_text())["kind"] == "error"


def test_missing_scan_exits_1(tmp_path):
    assert run_diff(tmp_path).returncode == 1


def test_promote_copies_latest_over_snapshot(tmp_path):
    write(tmp_path, "scan-latest.json", snapshot([FINDING]))
    assert run_diff(tmp_path, "--promote").returncode == 0
    assert json.loads((tmp_path / "snapshot.json").read_text())["run_id"] == "r1"
