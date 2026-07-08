import json

import cvelib
from conftest import FIXTURES


def test_normalize_matches_golden():
    report = json.loads((FIXTURES / "trivy_backend.json").read_text())
    got = cvelib.normalize_findings("backend", report)
    want = json.loads((FIXTURES / "normalized_backend.json").read_text())
    assert got == want


def test_duplicate_cve_keeps_worst_severity():
    report = json.loads((FIXTURES / "trivy_backend.json").read_text())
    got = cvelib.normalize_findings("backend", report)
    libssl = [f for f in got if f["package"] == "libssl3"]
    assert len(libssl) == 1  # HIGH and MEDIUM entries collapse to one
    assert libssl[0]["severity"] == "HIGH"


def test_content_hash_stable_and_sensitive():
    report = json.loads((FIXTURES / "trivy_backend.json").read_text())
    findings = cvelib.normalize_findings("backend", report)
    h1 = cvelib.content_hash(findings)
    assert h1 == cvelib.content_hash(list(reversed(findings)))  # order-free
    bumped = json.loads(json.dumps(findings))
    bumped[0]["severity"] = "CRITICAL"
    assert h1 != cvelib.content_hash(bumped)
    # cvss score alone does NOT wake the pipeline
    rescored = json.loads(json.dumps(findings))
    rescored[0]["cvss"] = 9.9
    assert h1 == cvelib.content_hash(rescored)
