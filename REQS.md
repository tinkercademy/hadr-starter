# REQS — Container CVE Checker & Fixer (raw idea)

An unattended agent that watches a **specified list of container images**, scans
them for known CVEs on a schedule, decides which findings actually matter, and
**fixes what it can** — opening a pull request with the remediation and proof
that the rebuilt image no longer carries the vulnerability. It publishes a
current-state report to `dashboard.html` and stays quiet when nothing has
changed since the last run.

## The itch

- Teams run dozens of images; nobody re-scans them after the build pipeline
  goes green. CVEs are published against *existing* images daily.
- Scanner output is noise: hundreds of findings, most with no fix available,
  no exploit, or in layers we don't control. Triage is the real work.
- The fix is usually mechanical — bump a base image tag/digest, upgrade a
  pinned OS package or app dependency — exactly the kind of change an agent
  can make and *verify* by rebuilding and rescanning.

## Constraints

- The list of containers is explicit and human-maintained (a config file in
  the repo). The agent never discovers or scans images it wasn't given.
- Two-stage wake-up: a deterministic script decides *whether* the findings
  changed since last run; a model call runs only on change. The model never
  decides whether to wake up.
- Fixes are proposed as PRs, never merged automatically. A fix PR must include
  before/after scan evidence.
- `dashboard.html` is the product and is committed; raw scan output is not.
