# HADR Monitor

A starter for building a monitoring agent for humanitarian assistance and disaster
response (HADR): an unattended agent that watches live disaster feeds, decides what
matters, and publishes a morning situation report — quietly, on a schedule, without
being told to.

## Contents

- [What you'll build](#what-youll-build)
- [This is a starter, not an app](#this-is-a-starter-not-an-app)
- [The three days](#the-three-days)
- [Repository layout](#repository-layout)
- [The data feeds](#the-data-feeds)
- [The morning sitrep pipeline](#the-morning-sitrep-pipeline)
- [Claude Code automation](#claude-code-automation)
- [Working conventions](#working-conventions)
- [Getting started (Day 1 setup)](#getting-started-day-1-setup)
- [Expected artefacts](#expected-artefacts)

## What you'll build

By the end of the exercise this repository contains an agent that:

- watches live disaster feeds — GDACS, USGS and ReliefWeb (see [`feeds/`](feeds/))
- filters out the noise and assesses what remains: what happened, where, how bad, who is affected
- publishes a morning situation report to `dashboard.html` at **08:30 Singapore time**
- runs on a schedule, unattended, and stays quiet when nothing has changed

## This is a starter, not an app

There is no source code here yet. No `package.json`, no `requirements.txt`, no chosen
language, no entry point — nothing that says *how* the agent works.

> How it does any of that is not specified anywhere in this repository. That is the course.

What ships today is scaffolding: feed briefs to study, empty directories with a note on
what belongs in them, the GitHub and Claude Code automation, and the conventions you'll
work under. You pick the tech stack and record it in [`CLAUDE.md`](CLAUDE.md); you fill
in `scripts/`, `skills/`, and the disabled sitrep workflow.

## The three days

1. **Plan** — interrogate the feeds, write the PRD, cut it into vertical slices
2. **Autonomy** — build the first slice, write a skill, wire up the 08:30 routine, launch the overnight loop
3. **Trust** — review code you didn't write, harden the pipeline, demo

## Repository layout

| Path | Purpose | State |
|------|---------|-------|
| [`README.md`](README.md) | This brief. | — |
| [`CLAUDE.md`](CLAUDE.md) | Conventions the agent must follow: language & tooling, test command, conventions, deviations policy. | Empty — fill in before your first prompt |
| [`implementation-notes.md`](implementation-notes.md) | Running log the agent keeps and you review — one entry per working block. | Template |
| [`feeds/`](feeds/) | One brief per data source: endpoint, sample response, and the open design questions each raises. | Content, no code |
| [`scripts/`](scripts/) | Deterministic checks — "anything that must give the same answer twice does not belong in a prompt." | Empty scaffold |
| [`skills/`](skills/) | Claude Code skills you write on Day 2, one folder each (a `SKILL.md`, assets, and a note on which model each step should use). | Empty scaffold |
| [`docs/solutions/`](docs/solutions/) | A greppable knowledge base — one learning per file, so no future session re-pays for a fix. | Convention + one example |
| [`.github/workflows/`](.github/workflows/) | GitHub Actions: Claude on issues/PRs, automated PR review, and the (disabled) morning sitrep. | See below |
| [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) | Templates for vertical slices and skill bug reports. | Content |
| [`.gitignore`](.gitignore) | Toolchain-agnostic; ignores generated `reports/` and `.env*`, but force-includes `dashboard.html`. | — |

## The data feeds

Three live sources, documented in [`feeds/`](feeds/). Each brief carries a sample
response and a set of "open questions" — the real design work is in answering them.

| Feed | What it is | Primary endpoint | Format |
|------|-----------|------------------|--------|
| [GDACS](feeds/gdacs.md) | Global Disaster Alert and Coordination System (EU/UN), multi-hazard, colour-coded alerts | `https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP` | GeoJSON (RSS alt.) |
| [USGS](feeds/usgs.md) | US Geological Survey real-time earthquakes, regenerated every minute | `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson` | GeoJSON |
| [ReliefWeb](feeds/reliefweb.md) | UN OCHA humanitarian service — curated and slower-moving | `https://api.reliefweb.int/v2/disasters?appname=<approved>&preset=latest` | JSON (RSS alt.) |

Gotchas worth knowing before you build:

- **ReliefWeb needs a pre-approved `appname`** (requested by form, confirmed by email) since 1 Nov 2025; without one the API returns HTTP 403. The old `v1` is decommissioned (HTTP 410). The RSS feed at `https://reliefweb.int/disasters/rss.xml` needs no approval — decide what you build against while approval is pending.
- **The same physical event arrives from multiple feeds** under different identifiers (USGS `id` vs its comma-wrapped `ids`, GDACS `eventid`, GLIDE numbers like `EQ-2026-000093-VEN`). Deduplication — and what counts as "the same event" — is the hard problem. GLIDE numbers and `iso3`/country codes are the join hints.
- **Events get revised or deleted after you report on them.** USGS `status` is often `automatic` and `updated` can trail `time`; magnitudes and locations change. Decide what happens to a report you've already published when its event moves underneath it.

## The morning sitrep pipeline

The scheduled report lives in [`.github/workflows/sitrep.yml.disabled`](.github/workflows/sitrep.yml.disabled).
It is **disabled on purpose** — "a scheduled workflow that does nothing still costs
minutes and trust." Rename it to `sitrep.yml` only once both TODO steps exist.

Its shape is the lesson, a two-stage pattern:

1. A **deterministic script** in `scripts/` decides whether anything changed. It must not call a model, and must exit in a way the workflow can branch on.
2. **Only on change**, a headless model call (`claude -p`) runs your `/sitrep` skill and republishes `dashboard.html`.

> The model never decides whether to wake up.

The cron is a `TODO`: 08:30 Asia/Singapore, daily — mind which timezone GitHub cron
runs in. Generated `reports/` and `*.sitrep.html` are gitignored as churn;
`dashboard.html` is the exception — it is the product, and it is committed.

## Claude Code automation

Two active workflows wire Claude into your GitHub flow:

- [`claude.yml`](.github/workflows/claude.yml) — mention `@claude` in an issue, an issue comment, or a PR review and Claude Code responds.
- [`claude-code-review.yml`](.github/workflows/claude-code-review.yml) — automatically runs `/code-review` on every PR (opened, updated, reopened, marked ready) via the `code-review@claude-code-plugins` plugin.

Both require the `CLAUDE_CODE_OAUTH_TOKEN` repository secret. Running
`/install-github-app` (Day 1 setup) wires this up.

## Working conventions

- **[`CLAUDE.md`](CLAUDE.md)** — fill in at least three conventions before your first prompt. An empty conventions file is also a decision, just not one you made.
- **[`implementation-notes.md`](implementation-notes.md)** — record decisions, open questions, and deviations. Anything built that departs from the PRD or `CLAUDE.md` is logged here with the reason. *An undocumented deviation is a bug.*
- **[`docs/solutions/`](docs/solutions/)** — when something costs you more than ten minutes, the fix goes here (`YYYY-MM-DD-short-slug.md`, YAML frontmatter with `date`/`tags`/`problem`, a terse symptom/cause/fix body). A future agent greps this directory before it starts debugging.
- **Issue templates** — file a [vertical slice](.github/ISSUE_TEMPLATE/slice.md) (Goal / Definition of done / Out of scope) for each thin end-to-end feature, and a [skill issue](.github/ISSUE_TEMPLATE/skill.md) against a neighbour's skill after installing it.

## Getting started (Day 1 setup)

1. Sign in to Claude Code with your Team seat
2. Create your own repository from this template, then clone it
3. Run `/install-github-app` so @claude reviews your pull requests from Day 2 (this also sets the `CLAUDE_CODE_OAUTH_TOKEN` secret)
4. Install OpenCode and sign in with your Go key
5. Fill in [`CLAUDE.md`](CLAUDE.md) before your first prompt

Keep secrets out of the repo and out of the agent's context: `.env` and `.env.*` are
gitignored. Local secrets — for example a ReliefWeb `appname` — go there.

## Expected artefacts

By the end of the exercise the repository should contain:

`prd.html` · `system-view.html` · `implementation-notes.md` · `dashboard.html` · `goal.md` · at least one skill
