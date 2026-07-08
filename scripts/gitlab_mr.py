#!/usr/bin/env python3
"""Open or update the one live fix MR for a service via the GitLab API.

One MR per service: looks for an open MR from the source branch first and
updates its description instead of stacking siblings. Without GITLAB_TOKEN,
dry-runs (prints what it would do) and exits 0.

  gitlab_mr.py --project group/backend --source-branch cve-fix/backend \\
               --title "fix(cve): ..." --description-file mr_body.md

Prints the MR web_url on success (the skill records it in state/fixes.json).
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--source-branch", required=True)
    ap.add_argument("--target-branch", default="main")
    ap.add_argument("--title", required=True)
    ap.add_argument("--description-file", type=Path, required=True)
    ap.add_argument("--gitlab-host", default="https://gitlab.com")
    args = ap.parse_args()

    description = args.description_file.read_text()
    token = os.environ.get("GITLAB_TOKEN", "")
    if not token:
        print(f"gitlab_mr: [dry-run] would open/update MR on {args.project} "
              f"({args.source_branch} -> {args.target_branch}): {args.title}")
        return 0

    import requests
    api = f"{args.gitlab_host}/api/v4/projects/{urllib.parse.quote_plus(args.project)}"
    headers = {"PRIVATE-TOKEN": token}

    existing = requests.get(
        f"{api}/merge_requests",
        params={"state": "opened", "source_branch": args.source_branch},
        headers=headers, timeout=30)
    existing.raise_for_status()
    mrs = existing.json()

    if mrs:
        iid = mrs[0]["iid"]
        resp = requests.put(f"{api}/merge_requests/{iid}",
                            json={"title": args.title, "description": description},
                            headers=headers, timeout=30)
        resp.raise_for_status()
        print(resp.json()["web_url"])
    else:
        resp = requests.post(
            f"{api}/merge_requests",
            json={"source_branch": args.source_branch,
                  "target_branch": args.target_branch,
                  "title": args.title, "description": description,
                  "remove_source_branch": True},
            headers=headers, timeout=30)
        resp.raise_for_status()
        print(resp.json()["web_url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
