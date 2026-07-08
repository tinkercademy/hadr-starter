#!/usr/bin/env python3
"""Stage 1b: compare state/scan-latest.json against state/snapshot.json.

THE exit contract the workflow branches on (never repurpose):
  0  = unchanged  (identical content hash)
  10 = changed    (state/diff.json written with the movement)
  1  = error      (scan failed/partial, or state unreadable)

Also writes result=<unchanged|changed|error> to $GITHUB_OUTPUT when set.

--promote: copy scan-latest.json over snapshot.json (run only after the
dashboard for that scan has been published).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cvelib
from cvelib import STATE_DIR, finding_key, severity_rank

LATEST = STATE_DIR / "scan-latest.json"
SNAPSHOT = STATE_DIR / "snapshot.json"
DIFF = STATE_DIR / "diff.json"


def gh_output(result: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"result={result}\n")


def build_diff(prev: dict | None, latest: dict) -> dict:
    prev_findings = {tuple(finding_key(f)): f for f in (prev or {}).get("findings", [])}
    new_findings = {tuple(finding_key(f)): f for f in latest["findings"]}

    new = [new_findings[k] for k in sorted(new_findings.keys() - prev_findings.keys())]
    fixed = [prev_findings[k] for k in sorted(prev_findings.keys() - new_findings.keys())]
    changed = [
        {"before": prev_findings[k], "after": new_findings[k]}
        for k in sorted(new_findings.keys() & prev_findings.keys())
        if (prev_findings[k]["severity"], prev_findings[k]["fixed_version"],
            prev_findings[k]["installed_version"])
        != (new_findings[k]["severity"], new_findings[k]["fixed_version"],
            new_findings[k]["installed_version"])
    ]

    per_target: dict[str, dict] = {}
    for name, status in latest.get("targets", {}).items():
        bucket = {"new": 0, "fixed": 0, "changed": 0, "open": 0,
                  "worst": None, "fixable": 0, "status": status}
        per_target[name] = bucket
    for f in latest["findings"]:
        b = per_target.setdefault(f["target"], {"new": 0, "fixed": 0, "changed": 0,
                                                "open": 0, "worst": None,
                                                "fixable": 0, "status": "ok"})
        b["open"] += 1
        if f["fixed_version"]:
            b["fixable"] += 1
        if b["worst"] is None or severity_rank(f["severity"]) < severity_rank(b["worst"]):
            b["worst"] = f["severity"]
    for f in new:
        per_target[f["target"]]["new"] += 1
    for f in fixed:
        per_target.setdefault(f["target"], {"new": 0, "fixed": 0, "changed": 0,
                                            "open": 0, "worst": None,
                                            "fixable": 0, "status": "ok"})["fixed"] += 1
    for c in changed:
        per_target[c["after"]["target"]]["changed"] += 1

    return {
        "run_id": latest["run_id"],
        "prev_run_id": (prev or {}).get("run_id"),
        "kind": "change",
        "new": new,
        "fixed": fixed,
        "changed": changed,
        "per_target": per_target,
        "waived_count": latest.get("waived_count", 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--promote", action="store_true")
    args = ap.parse_args()

    if args.promote:
        if not LATEST.exists():
            print("diff: nothing to promote", file=sys.stderr)
            return 1
        shutil.copy(LATEST, SNAPSHOT)
        print("diff: promoted scan-latest.json -> snapshot.json")
        return 0

    latest = cvelib.read_json(LATEST)
    if latest is None:
        print("diff: state/scan-latest.json missing — did scan run?", file=sys.stderr)
        gh_output("error")
        return 1
    if latest.get("status") != "ok":
        cvelib.write_json(DIFF, {"run_id": latest.get("run_id"), "kind": "error",
                                 "targets": latest.get("targets", {})})
        print(f"diff: scan status={latest.get('status')} -> error", file=sys.stderr)
        gh_output("error")
        return 1

    prev = cvelib.read_json(SNAPSHOT)
    if prev is not None and prev.get("content_hash") == latest.get("content_hash"):
        print("diff: unchanged")
        gh_output("unchanged")
        return 0

    diff = build_diff(prev, latest)
    cvelib.write_json(DIFF, diff)
    print(f"diff: changed — new={len(diff['new'])} fixed={len(diff['fixed'])} "
          f"changed={len(diff['changed'])} -> state/diff.json")
    gh_output("changed")
    return 10


if __name__ == "__main__":
    sys.exit(main())
