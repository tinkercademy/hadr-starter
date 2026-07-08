# PRD — Container CVE Checker & Fixer

Produced with the [`build-1-plan-product`](https://github.com/bguiz/build-agent-skills/blob/fb8c2eb7dfb32810e0c19ba964320c6ac0e54ab9/skills/build-1-plan-product/SKILL.md)
process (Shape Up: grill → PRD → shape → breadboard), compressed into one
session for the workshop. Raw idea: [../REQS.md](../REQS.md).
Decisions below were confirmed by grilling the product owner (2026-07-08).

## Problem statement

Container images accumulate vulnerabilities *after* they ship. A CVE published
today applies retroactively to every image already built, but CI only scans at
build time, so nobody notices until an audit or an incident. When someone does
scan, the output is hundreds of findings with no follow-through: the few that
matter need a mechanical remediation (bump a base image, upgrade a pinned
package) that nobody gets around to, because the Dockerfiles are scattered
across many repos.

**Who hurts:** the engineer who owns a fleet of images whose Dockerfiles live
in separate repos, and who is accountable for patching all of them.

**The concrete fleet:** the ACTIVE_LISTENER_v2 microservices (audio processor,
backend, ingestion, diarization, transcript aggregator, preprocessor, cleanup
worker, whisper-vllm, postgres, rabbitmq, seaweedfs, …) — one GitLab project
per service on gitlab.com. The services are not published to a registry, so
images are **built from each project's Dockerfile at scan time**.

## Goal

> **Every morning at 08:30 Singapore time, the owner of a defined list of
> containerised services sees the complete CVE picture for the fleet — every
> finding, every severity — and for each service with available fixes there is
> one open merge request against its GitLab project, carrying the remediation
> and rebuild-and-rescan proof. On any morning with CVE movement, the team's
> Telegram group receives a digest with a link to the dashboard. Quiet only
> when literally nothing changed.**

Success criteria:

- `dashboard.html` is regenerated on schedule, unattended, whenever any
  finding (any severity) appeared, disappeared, or changed; untouched when
  nothing did.
- On every run that detects change, the Telegram group gets **exactly one
  message**: per-image counts of new/fixed CVEs, worst severity, fix MRs
  opened, and a link to the published dashboard. No message on quiet days.
- Every failed run sends a distinct ⚠️ failure alert to the same group — the
  pipeline never fails silently.
- The dashboard shows **all findings** grouped per image, fixable or not,
  with waived findings suppressed (waivers carry reason + expiry).
- Each image with fixable findings has **exactly one open merge request in its
  GitLab project** bundling all available fixes, with before/after scan evidence.
- A fix MR is only opened after the patched image was rebuilt and rescanned
  clean of the targeted CVEs — in this repo's CI, before the MR exists.
- False "all clear" never happens silently: a failed scan is reported as a
  failure, never as "no findings".

## User stories

1. As the fleet owner, I maintain `containers.yaml` — GitLab project path,
   Dockerfile path, and build args per service — so the agent only ever
   builds, scans, and patches what I gave it.
2. As the fleet owner, I open the dashboard each morning and see every CVE per
   image — new, still-open, and fixed since the last run — at all severities.
3. As the fleet owner, when a service has fixable findings, I get one merge
   request in that service's GitLab project bundling the base-image and
   package bumps, with proof the rebuild is clean of the fixed CVEs.
4. As the fleet owner, I can waive a finding (CVE + image + reason + expiry)
   and it stops appearing until the waiver expires.
5. As the fleet owner, if the scanner or a registry is down at run time, the
   dashboard says so explicitly instead of presenting stale data as fresh.
6. As a team member in the Telegram group, on mornings with CVE movement I
   get one digest message — what changed, per image, and where the fix MRs
   are — with a link to the full dashboard; on quiet mornings, nothing.
7. As a team member, if a run fails I see a ⚠️ alert in the group, so a
   silent pipeline death never masquerades as "no news".

## Solution description

A scheduled two-stage pipeline in this repo's GitHub Actions:

1. **Deterministic stage** (`scripts/`, Python, no model): read
   `containers.yaml`, clone each service's GitLab project (token), `docker
   build` its image, scan it with Trivy (parallelised), normalise findings, drop waived ones, diff the full
   finding set against the previous snapshot, and exit with a code the
   workflow branches on: *changed* / *unchanged* / *error*.
2. **Model stage** (only on change): a headless `claude -p /cve-report` run
   regenerates `dashboard.html` (per-image tables, new/fixed deltas, trend
   counts), and for each image with fixable findings prepares the fix: in the
   already-cloned GitLab project, apply the bumps, rebuild in this repo's CI,
   rescan the built image, and — only if the targeted CVEs are gone — push
   the branch and open/update **one merge request per service** via the
   GitLab API.

3. **Notify stage** (deterministic, runs last): a Python script formats the
   diff summary — per-image new/fixed counts, worst severity, fix MR links —
   into a fixed template and sends **one Telegram message to the team group**
   (Bot API `sendMessage`; token and group `chat_id` are Actions secrets),
   linking to the dashboard published on GitHub Pages. It runs after the
   model stage so MR links are real, on the deterministic path so it still
   fires — as a ⚠️ failure alert — when the scan or the model stage dies.
   Unchanged runs send nothing.

The model never decides whether to wake up, never merges, never invents a
fix beyond version/base bumps, and never composes the notification.
Verification and alerting are code, not judgement.

## Three vertical slices

Each slice is thin but end-to-end: real input → real decision → published
output.

### Slice 1 — One image, scanned to dashboard (manual trigger)

Read `containers.yaml` with a single public image, scan it with Trivy, apply
waivers, render `dashboard.html` listing **all** findings for that image.
Run by hand.
**Done when:** the dashboard shows the complete, waiver-filtered CVE list for
one real image, and adding a waiver makes its finding disappear on rerun.
**Out of scope for the slice:** schedule, diffing, multiple images, fixes.

### Slice 2 — Fleet + schedule + quiet-when-unchanged + Telegram

10–50 images scanned in parallel; a snapshot file of the last full finding
set; a deterministic diff script with the changed/unchanged/error exit
contract; the 08:30 SGT scheduled workflow that republishes the dashboard
(to GitHub Pages) only on change; and the templated Telegram digest to the
team group — one message per changed run, a ⚠️ alert per failed run.
**Done when:** two consecutive runs with zero CVE movement produce zero
commits, zero model calls, and zero messages; any new finding at any
severity produces exactly one dashboard update and exactly one group
message; killing the scanner mid-run produces the failure alert.
**Out of scope for the slice:** fix PRs (the digest's "PRs opened" line
stays empty until slice 3).

### Slice 3 — Verified cross-repo fix MRs

For one service with fixable findings: in its cloned GitLab project, bump the
base image and/or package pins in its Dockerfile, build the image in this
repo's Actions, rescan it, and — only if the targeted CVEs are absent — push
the branch and open one MR bundling all the fixes, with before/after scan
evidence in the body. Reruns update the same MR instead of stacking new ones.
**Done when:** one real CVE on a real listed service is closed via an MR in
the service's own GitLab project that a human can review and merge.
**Out of scope for the slice:** app-code changes, transitive dependency
surgery, auto-merge.

## Data model

Persisted as JSON snapshots committed to this repo (tens of images — still
diffable files, no DB to operate); one file per concern.

```
ContainerTarget            # containers.yaml — human-maintained input
  name                     # friendly name, unique
  project                  # GitLab project path (group/name) on gitlab.com
  dockerfile               # path within the project
  build_target             # docker build --target (multi-stage), optional
  build_args               # e.g. BASE_REGISTRY/BASE_IMAGE/BASE_TAG, optional
  owner                    # who reviews the fix MR

ScanRun                    # one per pipeline execution
  run_id, started_at
  scanner, scanner_version, vuln_db_version   # for reproducibility disputes
  status: ok | partial | failed               # partial = some images unscannable
  targets: [target -> ok | error(reason)]

Finding                    # key = (target, cve_id, package)
  cve_id                   # CVE-YYYY-NNNN
  target                   # ContainerTarget.name
  package, installed_version, fixed_version   # fixed_version null => not fixable
  severity                 # scanner severity + CVSS score (ALL severities kept)
  layer_origin: base | app # base-image layer vs app layer — decides fix strategy
  status: new | open | fixed | waived
  first_seen, last_seen    # ScanRun ids

Waiver                     # honored from slice 1
  cve_id, target, reason, expires_at, created_by

FixAttempt                 # one per service per run with fixable findings
  target
  finding_keys[]           # every finding this MR closes
  strategies[]             # base_bump | package_pin | dep_bump (bundled)
  mr_url                   # opened or updated — one live MR per service
  verification: pre_scan_run, post_scan_run, verified: bool

Snapshot                   # what the diff script compares
  run_id
  findings[]               # ALL non-waived finding keys + severities + versions
  content_hash             # equality check = "did anything change"

Notification               # one per message actually sent
  run_id
  kind: digest | failure
  sent_at, delivered: bool # Bot API response — supports "exactly one per run"
```

Key modelling decisions:

- **Finding identity is (target, cve_id, package)** — the same CVE in two
  images, or two packages, is two findings, because they are fixed
  independently.
- **The diff is over all non-waived findings.** Any severity movement wakes
  the pipeline; in practice it will publish most days, and that is accepted —
  "quiet" guards against pointless identical publishes, not against news.
- **"Fixed" is derived, never asserted:** a finding is fixed when it stops
  appearing in a successful scan — not when an MR merges.
- **One live fix MR per service:** reruns force-update the service's fix
  branch and MR rather than opening siblings.

## Implementation decisions

- Scanner: Trivy (single binary, OS + language packages, JSON output),
  wrapped behind one script so it is swappable.
- Scripts in Python; tests with pytest.
- State: JSON files committed to this repo — the diff *is* the git diff.
- Schedule: GitHub Actions cron, daily at 00:30 UTC (= 08:30 SGT), using the
  starter's two-stage disabled-until-ready workflow pattern.
- Cross-repo access: a GitLab access token (`GITLAB_TOKEN`, api + write
  scope over the service projects) stored as an Actions secret; the agent
  clones over HTTPS with it, pushes fix branches, and opens MRs via the
  GitLab REST API.
- Scans and verification builds run in this repo's Actions: clone the GitLab
  project, `docker build` (with the target's `build_args`), Trivy-scan the
  built image; for fixes, rebuild and rescan before any MR exists.
- Registries: base images must be pullable from the runner. The
  `${BASE_REGISTRY}` values are supplied per target in containers.yaml; if
  the registry needs auth, a docker login step gated on secrets is added.
  (Pending: owner to supply the actual values.)
- Notifications: Telegram Bot API (`sendMessage`), one-way, to a team group.
  `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are Actions secrets. The
  message text is a deterministic template — same diff, same message.
- Dashboard hosting: GitHub Pages, so the Telegram link opens for everyone
  in the group. **Accepted trade-off:** the fleet's CVE status is publicly
  visible at that URL.

## Testing decisions

- Golden-file tests: raw Trivy JSON fixtures in, normalised finding set out —
  parser/normaliser changes show up as fixture diffs in review.
- Diff-contract tests: unchanged/changed/error exit codes exercised with
  synthetic snapshots (this is the branch the whole pipeline trusts).
- Waiver tests: active, expired, and wrong-target waivers against a fixture
  finding set.
- Notification tests: golden-file tests for the message template (synthetic
  diff in, exact message text out); failure-path test that a crashed scan
  yields a ⚠️ alert and never a digest; delivery treated as sent only on a
  2xx Bot API response.
- Slice 3 verified end-to-end against the `backend` service (python:3.10-slim
  base — old enough to carry real fixable CVEs), proving a real cross-repo MR
  on demand.

## Out of scope

- **Runtime protection** — no eBPF, no admission control, no IDS. This tool
  reasons about images at rest, not workloads.
- **Discovery** — no crawling registries or clusters for images to scan; the
  list is explicit or it isn't scanned.
- **Build secrets beyond base-image registry auth** — services must build
  with `build_args` alone; anything needing more is out until it isn't.
- **Projects outside the owner's control** — no fork-based MR flow; the
  GitLab token covers every target project or the service doesn't get fix
  MRs.
- **Zero-days / unpublished vulns** — findings come from the scanner's CVE
  database only. No static analysis, no fuzzing.
- **Auto-merge** — fix MRs always require a human. The agent proves; people
  decide.
- **App-code remediation** — version bumps and base-image bumps only; no
  rewriting code that *uses* a vulnerable API.
- **Secrets scanning, license compliance, SBOM signing/attestation** — nearby
  problems, different products.
- **Windows containers** and non-OCI artifacts (VMs, serverless bundles).
- **Interactive Telegram bot** — no commands (/status, /scan), no approving
  or waiving from chat, no buttons. One-way notifications only; anything
  interactive needs an always-on webhook and an auth story this product
  doesn't have.
- **Multi-tenancy / RBAC / notification fan-out** — one repo, one fleet, one
  dashboard, one Telegram group; email/Slack/per-user routing can come later.
