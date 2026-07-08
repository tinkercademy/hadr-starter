import datetime as dt

import cvelib

FINDINGS = [
    {"target": "backend", "cve_id": "CVE-2025-1111", "package": "libssl3"},
    {"target": "backend", "cve_id": "CVE-2025-2222", "package": "zlib1g"},
    {"target": "ingestion", "cve_id": "CVE-2025-1111", "package": "libssl3"},
]


def waiver(target="backend", cve="CVE-2025-1111", expires="2099-01-01"):
    return {"cve_id": cve, "target": target, "reason": "test",
            "expires_at": expires, "created_by": "test"}


def test_active_waiver_drops_only_its_target():
    kept, waived = cvelib.apply_waivers(FINDINGS, [waiver()])
    assert waived == 1
    assert {f["target"] for f in kept if f["cve_id"] == "CVE-2025-1111"} == {"ingestion"}


def test_expired_waiver_is_ignored(tmp_path):
    p = tmp_path / "waivers.yaml"
    p.write_text(
        "- cve_id: CVE-2025-1111\n  target: backend\n  reason: test\n"
        "  expires_at: 2020-01-01\n  created_by: test\n")
    active = cvelib.load_waivers(p, today=dt.date(2026, 7, 8))
    assert active == []


def test_no_expiry_means_active(tmp_path):
    p = tmp_path / "waivers.yaml"
    p.write_text("- cve_id: CVE-2025-1111\n  target: backend\n  reason: test\n")
    assert len(cvelib.load_waivers(p)) == 1


def test_wrong_target_waiver_drops_nothing():
    kept, waived = cvelib.apply_waivers(FINDINGS, [waiver(target="postgres")])
    assert waived == 0 and len(kept) == 3
