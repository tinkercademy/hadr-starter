#!/usr/bin/env python3
"""Slice 3 gate: prove a fix works before any MR exists.

Rebuilds the target from a (patched) source directory, rescans it, and checks
the targeted CVEs are gone. The model proposes the edit; this script decides.

  verify_fix.py --target backend --src /path/to/patched/checkout \\
                --cves CVE-2025-1234,CVE-2025-5678

Exit 0: verified — every listed CVE absent from the rebuilt image
Exit 2: NOT verified — at least one listed CVE still present
Exit 1: build/scan error

Writes a JSON verdict to stdout (the skill embeds it in the MR body).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cvelib


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--cves", required=True,
                    help="comma-separated CVE ids that must be absent")
    ap.add_argument("--config", type=Path, default=None)
    args = ap.parse_args()

    _cfg, targets = cvelib.load_config(args.config)
    matches = [t for t in targets if t.name == args.target]
    if not matches:
        print(f"verify_fix: unknown/disabled target {args.target}", file=sys.stderr)
        return 1
    target = matches[0]
    wanted_gone = {c.strip() for c in args.cves.split(",") if c.strip()}

    image = cvelib.build_image(target, args.src)
    report = cvelib.trivy_scan(image)
    findings = cvelib.normalize_findings(target.name, report)

    still_present = sorted({f["cve_id"] for f in findings} & wanted_gone)
    verdict = {
        "target": target.name,
        "cves_checked": sorted(wanted_gone),
        "still_present": still_present,
        "verified": not still_present,
        "post_fix_total_findings": len(findings),
    }
    print(json.dumps(verdict, indent=1))
    return 0 if verdict["verified"] else 2


if __name__ == "__main__":
    sys.exit(main())
