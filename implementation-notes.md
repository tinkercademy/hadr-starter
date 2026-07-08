# Implementation notes

Kept by the agent, reviewed by you. One entry per working block.

## Decisions

### 2026-07-08 — full pipeline built (slices 1–3 code-complete)

- Repo repurposed from the HADR starter to **container-cve-fixer** (renamed
  on GitHub; `feeds/` left in place as ignorable legacy).
- Fleet = ACTIVE_LISTENER_v2 services, **one GitLab project per service on
  gitlab.com**; images are **built from each project's Dockerfile at scan
  time** (nothing is published to a registry). Orchestration stays in this
  repo's GitHub Actions; MRs are opened cross-platform via the GitLab API.
- Shared deterministic core in `scripts/cvelib.py`; entry points `scan.py`,
  `diff.py` (exit contract 0/10/1), `notify.py` (one-way Telegram, dry-run
  when secrets missing), `verify_fix.py` (rebuild+rescan gate),
  `gitlab_mr.py` (one live MR per service).
- `state/scan-latest.json` and `state/diff.json` are transient (CI
  artifacts, gitignored); `snapshot.json`, `fixes.json`,
  `notifications.json`, `waivers.yaml` are committed state.
- Proven locally against the real `backend` service (python:3.10-slim):
  1012 findings (9 CRITICAL base-layer, no upstream fix yet; 7 fixable
  app-layer), diff exit 10, digest dry-run rendered, `dashboard.html`
  generated and snapshot promoted. 20 pytest tests green.

## Open questions

- **GitLab project paths** — `containers.yaml` has `<GITLAB-GROUP>`
  placeholders; owner to supply real paths.
- **BASE_REGISTRY/BASE_IMAGE/BASE_TAG values** — most Dockerfiles need them
  to build; owner to paste values (and registry auth needs, if any). Those
  targets ship `enabled: false` until then.
- **whisper-vllm** (~10 GB base) — likely exceeds GitHub runner disk; needs
  a decision (self-hosted runner, or scan-only via a published ref).
- **Secrets** — `GITLAB_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` to
  be added as repo secrets; workflow stays `.disabled` until then.
- **GitHub Pages** — needs enabling (deploy from `main`, root) for the
  digest's dashboard link.

## Deviations

- **PRD says "10–50 images"; day one ships with 1 enabled target**
  (backend). Reason: the other services cannot build without the BASE_*
  values (open question above). The fleet grows by flipping `enabled: true`.
- **First dashboard was rendered by the session agent, not the headless
  `/cve-report` run.** Reason: identical role (model stage), and the
  workflow that invokes the skill can't be exercised until secrets exist.
  The committed `dashboard.html` is real output from a real scan.

<!-- Anything built that departs from the PRD or CLAUDE.md is recorded here,
     with the reason. An undocumented deviation is a bug. -->
