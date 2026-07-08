# CLAUDE.md

## Language & tooling

- Python 3.10+ (runner may be newer; code must run on 3.10).
- Dependencies: `pyyaml` and `requests` only, pinned in `requirements.txt`.
  Prefer stdlib; justify any new dependency in implementation-notes.md.
- Container scanning: Trivy, invoked only through `scripts/scan.py`.
- Formatting: PEP 8; type hints on public functions.

## Test command

```
python3 -m pytest tests/ -q
```

All tests must pass before any commit. Golden-file fixtures live in
`tests/fixtures/`; a behaviour change that alters a golden file must change
the fixture in the same commit, visibly.

## Conventions

- `scripts/` is deterministic: no model calls, no prompts, same input → same
  output. Anything judgement-shaped belongs in `skills/`.
- Finding identity is the tuple `(target, cve_id, package)` everywhere.
- Exit contract for `scripts/diff.py`: 0 = unchanged, 10 = changed,
  1 = error. The workflow branches on this; never repurpose these codes.
- Missing secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GITLAB_TOKEN`)
  must degrade to dry-run (log what would have been sent/pushed), never to a
  crash or a silent skip.
- A failed scan is reported as a failure, never as "no findings".
- State files under `state/` are committed; raw Trivy output is not.

## Deviations policy

Anything built that departs from `docs/PRD.md` or this file is logged in
`implementation-notes.md` with the reason, in the same working block.
An undocumented deviation is a bug.
