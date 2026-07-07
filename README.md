# HADR Monitor

Starter template for a three-day course. You build a monitoring agent for
**h**umanitarian **a**ssistance and **d**isaster **r**esponse: it watches live
disaster feeds, filters out the noise, and publishes a morning situation report —
unattended, on a schedule.

This repo gives you the scaffolding and the feed research. **How the agent
actually works is deliberately unspecified — designing that is the course.**

## What you build

An agent that:

- watches live disaster feeds — GDACS, USGS and ReliefWeb (see `feeds/`)
- filters the noise, then assesses what remains: what happened, where, how bad, who is affected
- publishes a morning situation report to `dashboard.html` at 08:30 Singapore time
- runs on a schedule, unattended, and stays quiet when nothing has changed

## The three days

1. **Plan** — study the feeds, write the PRD, cut it into vertical slices
2. **Autonomy** — build the first slice, write a skill, wire up the 08:30 routine, launch the overnight loop
3. **Trust** — review code you didn't write, harden the pipeline, demo

## Deliverables

`prd.html` · `system-view.html` · `implementation-notes.md` · `dashboard.html` · `goal.md` · at least one skill

## Repo layout

| Path | What lives here |
|------|-----------------|
| `feeds/` | Notes and verified endpoints for each source (GDACS, USGS, ReliefWeb) |
| `skills/` | Skills you write on Day 2 — one folder per skill |
| `scripts/` | Deterministic checks — anything that must give the same answer twice |
| `docs/solutions/` | One debugging learning per file, greppable by future sessions |
| `CLAUDE.md` | Your conventions, tooling and test command — fill in before your first prompt |
| `implementation-notes.md` | Decisions, open questions and deviations — kept by the agent, reviewed by you |

## Day 1 setup

1. Sign in to Claude Code with your Team seat
2. Create your own repository from this template, then clone it
3. Run `/install-github-app` so @claude reviews your pull requests from Day 2
4. Install OpenCode and sign in with your Go key

Then fill in `CLAUDE.md` before your first prompt.
