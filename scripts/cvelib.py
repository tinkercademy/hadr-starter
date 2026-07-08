"""Shared deterministic core: config, clone, build, scan, normalise, waivers.

Everything here must give the same answer twice. No model calls, ever.
Finding identity is the tuple (target, cve_id, package) throughout.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
# CVE_PATROL_STATE overrides where state lives — used by tests, never by CI.
STATE_DIR = Path(os.environ.get("CVE_PATROL_STATE") or (REPO_ROOT / "state"))
SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]


# --------------------------------------------------------------------------- config

@dataclass
class Target:
    name: str
    project: str
    dockerfile: str
    context: str = "."
    build_target: Optional[str] = None
    build_args: dict = field(default_factory=dict)
    owner: str = ""
    enabled: bool = True


def load_config(path: Path | None = None) -> tuple[dict, list[Target]]:
    """Return (raw config, enabled targets)."""
    cfg = yaml.safe_load((path or REPO_ROOT / "containers.yaml").read_text())
    defaults = cfg.get("defaults") or {}
    targets = []
    for entry in cfg.get("targets") or []:
        merged = {**defaults, **entry}
        merged["build_args"] = {**(defaults.get("build_args") or {}),
                                **(entry.get("build_args") or {})}
        t = Target(**{k: v for k, v in merged.items() if k in Target.__dataclass_fields__})
        if t.enabled:
            targets.append(t)
    return cfg, targets


# --------------------------------------------------------------------------- source

def fetch_source(target: Target, gitlab_host: str, local_root: Optional[Path],
                 workdir: Path) -> Path:
    """Return a directory containing the target's source.

    local_root maps <local_root>/<project-basename> for development runs;
    otherwise clone the GitLab project with GITLAB_TOKEN (shallow).
    """
    if local_root:
        candidate = local_root / target.project.split("/")[-1]
        if not candidate.is_dir():
            raise RuntimeError(f"{target.name}: no local source at {candidate}")
        return candidate
    token = os.environ.get("GITLAB_TOKEN", "")
    if not token:
        raise RuntimeError(f"{target.name}: GITLAB_TOKEN not set and no --local-root")
    host = gitlab_host.removeprefix("https://")
    url = f"https://oauth2:{token}@{host}/{target.project}.git"
    dest = workdir / target.name
    run(["git", "clone", "--depth", "1", url, str(dest)],
        redact=token, timeout=300)
    return dest


# --------------------------------------------------------------------------- build + scan

def build_image(target: Target, src: Path) -> str:
    """docker build the target; return the image tag."""
    tag = f"cve-patrol/{target.name}:scan"
    cmd = ["docker", "build", "-f", str(src / target.dockerfile),
           "-t", tag]
    if target.build_target:
        cmd += ["--target", target.build_target]
    for k, v in sorted(target.build_args.items()):
        cmd += ["--build-arg", f"{k}={v}"]
    cmd.append(str(src / target.context))
    run(cmd, timeout=1800)
    return tag


def trivy_scan(image: str) -> dict:
    """Run Trivy on a built image, return parsed JSON report."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        out = f.name
    try:
        run(["trivy", "image", "--format", "json", "--output", out,
             "--scanners", "vuln", "--quiet", image], timeout=1200)
        return json.loads(Path(out).read_text())
    finally:
        Path(out).unlink(missing_ok=True)


# --------------------------------------------------------------------------- findings

def normalize_findings(target_name: str, trivy_report: dict) -> list[dict]:
    """Trivy JSON -> canonical finding dicts, sorted by key.

    layer_origin: 'base' for OS packages, 'app' for language packages —
    this decides the fix strategy later.
    """
    findings = {}
    for result in trivy_report.get("Results") or []:
        origin = "base" if result.get("Class") == "os-pkgs" else "app"
        for v in result.get("Vulnerabilities") or []:
            key = (target_name, v["VulnerabilityID"], v.get("PkgName", ""))
            cvss = None
            for src in ("nvd", "redhat", "ghsa"):
                score = (v.get("CVSS") or {}).get(src, {}).get("V3Score")
                if score is not None:
                    cvss = score
                    break
            f = {
                "target": target_name,
                "cve_id": v["VulnerabilityID"],
                "package": v.get("PkgName", ""),
                "installed_version": v.get("InstalledVersion", ""),
                "fixed_version": v.get("FixedVersion") or None,
                "severity": (v.get("Severity") or "UNKNOWN").upper(),
                "cvss": cvss,
                "layer_origin": origin,
            }
            # same CVE+pkg can appear in several Results; keep worst severity
            prev = findings.get(key)
            if prev is None or severity_rank(f["severity"]) < severity_rank(prev["severity"]):
                findings[key] = f
    return [findings[k] for k in sorted(findings)]


def severity_rank(sev: str) -> int:
    return SEVERITY_ORDER.index(sev) if sev in SEVERITY_ORDER else len(SEVERITY_ORDER)


def finding_key(f: dict) -> tuple:
    return (f["target"], f["cve_id"], f["package"])


# --------------------------------------------------------------------------- waivers

def load_waivers(path: Path | None = None,
                 today: Optional[dt.date] = None) -> list[dict]:
    p = path or STATE_DIR / "waivers.yaml"
    if not p.exists():
        return []
    entries = yaml.safe_load(p.read_text()) or []
    today = today or dt.date.today()
    active = []
    for w in entries:
        expires = w.get("expires_at")
        if isinstance(expires, str):
            expires = dt.date.fromisoformat(expires)
        if expires is None or expires >= today:
            active.append(w)
    return active


def apply_waivers(findings: list[dict], waivers: list[dict]) -> tuple[list[dict], int]:
    """Drop waived findings. Returns (kept, waived_count)."""
    waived_keys = {(w["target"], w["cve_id"]) for w in waivers}
    kept = [f for f in findings if (f["target"], f["cve_id"]) not in waived_keys]
    return kept, len(findings) - len(kept)


# --------------------------------------------------------------------------- snapshots

def content_hash(findings: list[dict]) -> str:
    """Hash of what matters for 'did anything change'."""
    canon = [[f["target"], f["cve_id"], f["package"], f["severity"],
              f["installed_version"], f["fixed_version"]]
             for f in sorted(findings, key=finding_key)]
    return hashlib.sha256(json.dumps(canon).encode()).hexdigest()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n")


def read_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


# --------------------------------------------------------------------------- subprocess

def run(cmd: list[str], timeout: int = 600, redact: str = "") -> str:
    shown = " ".join(cmd).replace(redact, "***") if redact else " ".join(cmd)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[-2000:]
        if redact:
            err = err.replace(redact, "***")
        raise RuntimeError(f"command failed ({shown}): {err}")
    return proc.stdout
