# Copyright 2026 BitWise Media Group Ltd
# SPDX-License-Identifier: MIT

"""Project intent files onto GitHub issues and the PDLC project board.

The intent files under intents/ are the source of truth. This script renders each one as an issue in this repository
(creating it, or updating its title, body, milestone and issue type), sets its Effort issue field, adds it to the
organisation project, sets its Area project field, gives a new item the Backlog status, links it as a sub-issue of the
tracking epic, records "blocked by" dependencies, and writes the issue URL back into the file's frontmatter. It never
reads anything from an issue back into an intent, and it never touches a board status that is already set.

Usage: uv run python scripts/project_issues.py [--dry-run] [--only 001,002]

Requires the gh CLI authenticated with the repo and project scopes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from intentlib import INTENTS_DIR, PHASES, REPO, REPO_URL, ROOT, Intent, load, parse

OWNER = REPO.split("/")[0]
PROJECT_NUMBER = "3"
EPIC = INTENTS_DIR / "epic.md"
ISSUE_TYPE = "Feature"
#: The organisation issue field that carries an intent's effort; its options are Low, Medium and High.
EFFORT_FIELD = "Effort"


def gh(*args: str, input: str | None = None, check: bool = True) -> str:
    proc = subprocess.run(["gh", *args], input=input, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def api(path: str, *fields: str, method: str = "GET", check: bool = True) -> dict | list:
    out = gh("api", "-X", method, path, *fields, check=check)
    return json.loads(out) if out.strip() else {}


def issue_body(path: Path, request: str) -> str:
    rel = path.relative_to(ROOT).as_posix()
    notice = (
        f"> Projected from [`{rel}`]({REPO_URL}/blob/main/{rel}). The file is the source of truth: change it with a "
        "pull request, not by editing this issue."
    )
    return notice + "\n\n" + request


def number_of(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[1]


def write_issue_url(path: Path, url: str) -> None:
    text = path.read_text()
    path.write_text(re.sub(r"^issue:.*$", f"issue: {url}", text, count=1, flags=re.M))


class Board:
    """The organisation project: its fields, and the items already on it keyed by issue URL."""

    def __init__(self) -> None:
        proj = json.loads(gh("project", "view", PROJECT_NUMBER, "--owner", OWNER, "--format", "json"))
        self.id = proj["id"]
        fields = json.loads(gh("project", "field-list", PROJECT_NUMBER, "--owner", OWNER, "--format", "json"))
        self.fields = {f["name"]: f for f in fields["fields"]}
        items = json.loads(
            gh("project", "item-list", PROJECT_NUMBER, "--owner", OWNER, "--format", "json", "--limit", "1000")
        )
        self.items = {i["content"].get("url"): i for i in items["items"] if i.get("content")}

    def add(self, url: str) -> dict:
        if url not in self.items:
            item = json.loads(
                gh("project", "item-add", PROJECT_NUMBER, "--owner", OWNER, "--url", url, "--format", "json")
            )
            self.items[url] = {"id": item["id"]}
        return self.items[url]

    def clear(self, item: dict, field: str) -> None:
        if field in self.fields and item.get(field.lower()):
            gh(
                "project",
                "item-edit",
                "--id",
                item["id"],
                "--project-id",
                self.id,
                "--field-id",
                self.fields[field]["id"],
                "--clear",
            )

    def select(self, item: dict, field: str, option: str) -> None:
        f = self.fields[field]
        opt = next((o["id"] for o in f.get("options", []) if o["name"] == option), None)
        if opt is None:
            print(f"  ! project field {field} has no option {option!r}", file=sys.stderr)
            return
        gh(
            "project",
            "item-edit",
            "--id",
            item["id"],
            "--project-id",
            self.id,
            "--field-id",
            f["id"],
            "--single-select-option-id",
            opt,
        )


def effort_field() -> int:
    fields = api(f"orgs/{OWNER}/issue-fields")
    return next(f["id"] for f in fields if f["name"] == EFFORT_FIELD)


def set_effort(url: str, field_id: int, effort: str) -> None:
    payload = json.dumps({"issue_field_values": [{"field_id": field_id, "value": effort.capitalize()}]})
    gh("api", "-X", "POST", f"repos/{REPO}/issues/{number_of(url)}/issue-field-values", "--input", "-", input=payload)


def milestones(dry: bool) -> dict[int, int]:
    """Phase number to milestone number, creating any that are missing."""
    existing = {m["title"]: m["number"] for m in api(f"repos/{REPO}/milestones?state=all&per_page=100")}
    out = {}
    for n, phase in PHASES.items():
        if phase.label not in existing and not dry:
            existing[phase.label] = api(f"repos/{REPO}/milestones", "-f", f"title={phase.label}", method="POST")[
                "number"
            ]
        out[n] = existing.get(phase.label, 0)
    return out


def upsert_issue(path: Path, title: str, body: str, milestone: int | None, typed: bool) -> str:
    fields = ["-f", f"title={title}", "-f", f"body={body}"]
    if milestone:
        fields += ["-F", f"milestone={milestone}"]
    if typed:
        fields += ["-f", f"type={ISSUE_TYPE}"]
    url = parse_url(path)
    if url:
        api(f"repos/{REPO}/issues/{number_of(url)}", *fields, method="PATCH")
        return url
    url = api(f"repos/{REPO}/issues", *fields, method="POST")["html_url"]
    write_issue_url(path, url)
    return url


def parse_url(path: Path) -> str | None:
    m = re.search(r"^issue:\s*(\S+)\s*$", path.read_text(), re.M)
    return None if not m or m.group(1) == "null" else m.group(1)


def project(intent: Intent, board: Board, phases: dict[int, int], epic_url: str | None, effort_id: int) -> str:
    url = upsert_issue(
        intent.path,
        f"[{intent.project}] {intent.title}",
        issue_body(intent.path, intent.request),
        phases[intent.phase.number],
        typed=True,
    )
    set_effort(url, effort_id, intent.effort)
    item = board.add(url)
    if not item.get("status"):
        board.select(item, "Status", "Backlog")
    board.select(item, "Area", intent.area.title)
    # Effort replaced the board's t-shirt Size; clear any Size an earlier projection set.
    board.clear(item, "Size")
    if epic_url:
        sub_id = api(f"repos/{REPO}/issues/{number_of(url)}")["id"]
        # Already linked is a 422; linking is idempotent from here.
        api(
            f"repos/{REPO}/issues/{number_of(epic_url)}/sub_issues",
            "-F",
            f"sub_issue_id={sub_id}",
            method="POST",
            check=False,
        )
    return url


def link_dependencies(intents: list[Intent], urls: dict[str, str]) -> None:
    for i in intents:
        if i.key not in urls:
            continue
        number = number_of(urls[i.key])
        existing = {d["number"] for d in api(f"repos/{REPO}/issues/{number}/dependencies/blocked_by")}
        for dep in i.depends_on:
            if dep not in urls:
                print(f"  ! {i.key}: dependency {dep} has no issue", file=sys.stderr)
                continue
            if int(number_of(urls[dep])) in existing:
                continue
            dep_id = api(f"repos/{REPO}/issues/{number_of(urls[dep])}")["id"]
            api(f"repos/{REPO}/issues/{number}/dependencies/blocked_by", "-F", f"issue_id={dep_id}", method="POST")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated intent ids to project")
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    intents = load()
    selected = [i for i in intents if not only or i.id in only]
    if args.dry_run:
        for i in selected:
            verb = "update" if i.issue else "create"
            print(f"would {verb}: [{i.project}] {i.title} (area {i.area.title}, {i.effort} effort, {i.phase.label})")
        return 0

    phases = milestones(dry=False)
    board = Board()
    effort_id = effort_field()

    epic = parse(EPIC) if EPIC.exists() else None
    epic_url = None
    if epic:
        epic_url = upsert_issue(EPIC, epic.meta["title"], issue_body(EPIC, epic.request), None, typed=False)
        item = board.add(epic_url)
        if not item.get("status"):
            board.select(item, "Status", "Backlog")
        print(f"epic: {epic_url}")

    urls = {i.key: i.issue for i in intents if i.issue}
    for i in selected:
        urls[i.key] = project(i, board, phases, epic_url, effort_id)
        print(f"{i.key}: {urls[i.key]}")
    link_dependencies(selected, urls)
    return 0


if __name__ == "__main__":
    sys.exit(main())
