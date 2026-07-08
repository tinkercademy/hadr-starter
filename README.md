# Container CVE Checker & Fixer

An unattended agent that watches a **specified list of container images**,
rescans them for known CVEs on a schedule, publishes a morning status report to
`dashboard.html` (08:30 Singapore time), and opens **verified fix PRs** — base
image or package bumps proven clean by a rebuild-and-rescan — while staying
quiet on mornings where nothing changed.

Repository: `normalwalrus/container-cve-fixer` (renamed from `hadr-starter`;
the old HADR feed briefs under `feeds/` are legacy starter material and can be
ignored).

## Start here

- [`REQS.md`](REQS.md) — the raw idea and constraints.
- [`docs/PRD.md`](docs/PRD.md) — the PRD: goal, three vertical slices, data
  model, out of scope.

## The shape of the thing

Two-stage pipeline, scheduled by GitHub Actions:

1. A **deterministic script** in `scripts/` (Python) scans every image in
   `containers.yaml` (Trivy, in parallel), drops waived findings, diffs the
   full finding set — all severities — against the last snapshot, and exits
   changed / unchanged / error.
2. **Only on change**, a headless model call regenerates `dashboard.html`
   (published via GitHub Pages) and, per image with fixable findings, clones
   its source repo (fine-grained PAT), applies the bumps, rebuilds and
   rescans in this repo's CI, and opens **one PR per image** — only if the
   rebuilt image is clean of the targeted CVEs, with before/after scan
   evidence.
3. A **deterministic notify script** runs last: on change it sends one
   templated Telegram digest to the team group (new/fixed counts per image,
   worst severity, PR links, dashboard URL); on failure it sends a ⚠️ alert.
   Quiet days send nothing.

> The model never decides whether to wake up, never merges, and never sets the
> triage policy.

## Working conventions

- [`CLAUDE.md`](CLAUDE.md) — language & tooling, test command, conventions,
  deviations policy. Fill in before the first implementation prompt.
- [`implementation-notes.md`](implementation-notes.md) — one entry per working
  block; any departure from the PRD is logged with a reason. *An undocumented
  deviation is a bug.*
- [`docs/solutions/`](docs/solutions/) — greppable knowledge base; anything
  that cost more than ten minutes gets a `YYYY-MM-DD-slug.md`.
- `scripts/` — deterministic checks only: anything that must give the same
  answer twice does not belong in a prompt.
- `skills/` — Claude Code skills (e.g. `/cve-report`), one folder each.

## Expected artefacts

`docs/PRD.md` · `containers.yaml` · `dashboard.html` · `implementation-notes.md`
· at least one skill · the (initially disabled) scheduled workflow.
