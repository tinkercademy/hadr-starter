#!/usr/bin/env python3
"""Stage 1a: build and scan every enabled target; write state/scan-latest.json.

Deterministic. A target that fails to build or scan is recorded as an error —
never as zero findings. Exit 0 even on partial failure (diff.py owns the
changed/unchanged/error contract); exit 1 only on total failure (no target
scanned, config unreadable).

Usage:
  scan.py [--target NAME]... [--local-root DIR] [--config FILE]

--local-root: development mode — source for target <name> is looked up at
  <DIR>/<project-basename> instead of cloning from GitLab.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cvelib
from cvelib import STATE_DIR


def scan_target(target, gitlab_host, local_root, workdir):
    src = cvelib.fetch_source(target, gitlab_host, local_root, workdir)
    image = cvelib.build_image(target, src)
    report = cvelib.trivy_scan(image)
    findings = cvelib.normalize_findings(target.name, report)
    meta = {
        "scanner_version": (report.get("Metadata") or {}).get("ImageID", ""),
    }
    return findings, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", action="append", default=None,
                    help="scan only these targets (repeatable)")
    ap.add_argument("--local-root", type=Path, default=None)
    ap.add_argument("--config", type=Path, default=None)
    args = ap.parse_args()

    cfg, targets = cvelib.load_config(args.config)
    if args.target:
        targets = [t for t in targets if t.name in args.target]
    if not targets:
        print("scan: no enabled targets selected", file=sys.stderr)
        return 1

    gitlab_host = cfg.get("gitlab_host", "https://gitlab.com")
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    all_findings: list[dict] = []
    target_status: dict[str, str] = {}

    with tempfile.TemporaryDirectory(prefix="cve-patrol-") as tmp:
        workdir = Path(tmp)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(scan_target, t, gitlab_host, args.local_root, workdir): t
                for t in targets
            }
            for fut, t in futures.items():
                try:
                    findings, _meta = fut.result()
                    all_findings.extend(findings)
                    target_status[t.name] = "ok"
                    print(f"scan: {t.name}: {len(findings)} findings")
                except Exception as e:  # noqa: BLE001 — recorded, never swallowed
                    target_status[t.name] = f"error: {e}"
                    print(f"scan: {t.name}: ERROR: {e}", file=sys.stderr)

    waivers = cvelib.load_waivers()
    kept, waived = cvelib.apply_waivers(all_findings, waivers)

    ok = sum(1 for s in target_status.values() if s == "ok")
    status = "ok" if ok == len(target_status) else ("partial" if ok else "failed")

    trivy_version = ""
    try:
        trivy_version = cvelib.run(["trivy", "--version"], timeout=30).splitlines()[0]
    except Exception:
        pass

    snapshot = {
        "run_id": run_id,
        "started_at": run_id,
        "scanner": trivy_version,
        "status": status,
        "targets": target_status,
        "waived_count": waived,
        "findings": sorted(kept, key=cvelib.finding_key),
        "content_hash": cvelib.content_hash(kept),
    }
    cvelib.write_json(STATE_DIR / "scan-latest.json", snapshot)
    print(f"scan: status={status} findings={len(kept)} waived={waived} "
          f"-> state/scan-latest.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
