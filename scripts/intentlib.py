# Copyright 2026 BitWise Media Group Ltd
# SPDX-License-Identifier: MIT

"""Load, describe and validate the intent files under intents/.

The intent files are the source of truth for this repository. Every script reads them through this module: the
validator (check_intents.py), the docs generator (gen_docs.py) and the issue projection (project_issues.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
INTENTS_DIR = ROOT / "intents"
REPO = "bitwise-media-group/intents"
REPO_URL = f"https://github.com/{REPO}"

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)

#: Frontmatter keys, in the order the template lists them.
KEYS = (
    "id",
    "slug",
    "title",
    "project",
    "repositories",
    "phase",
    "area",
    "effort",
    "status",
    "depends_on",
    "refs",
    "issue",
)

#: Sections of the request, in order. The first two are the fields of maul's per-project issue form.
SECTIONS = (
    "What should change, and why?",
    "How will we know it is done?",
    "Isolation invariants",
    "Out of scope",
    "Depends on",
    "References",
    "Open questions",
)

#: How slug words are spelled in navigation entries.
ACRONYMS = {"api": "API", "e2e": "E2E", "pdlc": "PDLC", "pr": "PR", "pypi": "PyPI", "ux": "UX"}

#: Relative agent effort, the values of the organisation's Effort issue field (lower case here).
EFFORTS = ("low", "medium", "high")
STATUSES = ("proposed", "ready", "in-progress", "in-review", "done", "dropped")


@dataclass(frozen=True)
class Phase:
    number: int
    title: str
    summary: str

    @property
    def label(self) -> str:
        return f"Phase {self.number}: {self.title}"

    @property
    def anchor(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.label.lower()).strip("-")


PHASES = {
    p.number: p
    for p in (
        Phase(
            0,
            "Isolation floor",
            "Close patchy's existing gaps before adding anything: harden the broker, broker every harness, lock "
            "agent networking, harden Claude postures and build an end-to-end harness. Each item improves today's "
            "Finding flow.",
        ),
        Phase(
            1,
            "Records, contracts and spend",
            "The foundations every later phase writes through: durable git and blob records, the artifact "
            "contract and its validator, one command grammar, cost-based spend limits, a brand registry and the "
            "authoring skills.",
        ),
        Phase(
            2,
            "Repository images",
            "Pin and run agent stages in each application's own toolchain image, under admission control.",
        ),
        Phase(
            3,
            "Intents",
            "Plan, approve, build and revise intents, git-native from request to merge, then across several "
            "repositories.",
        ),
        Phase(
            4,
            "Identity and dependencies",
            "Attribute every run to a person, report usage, and fetch Go, npm and PyPI dependencies through "
            "broker routes.",
        ),
        Phase(
            5,
            "Operator experience",
            "The intents dashboard, actions from the status page and CLI, per-user model credentials and "
            "operator onboarding.",
        ),
        Phase(
            6,
            "Previews",
            "Isolated, signed-in live previews for every intent pull request, with setup and check commands.",
        ),
        Phase(7, "Rebrand", "Rename the product in place, with an upgrade path for existing installs."),
    )
}


@dataclass(frozen=True)
class Area:
    key: str
    title: str
    summary: str


#: Areas in reading order: the lifecycle first, then what it stands on, then what surrounds it.
AREAS = {
    a.key: a
    for a in (
        Area(
            "intents", "Intent lifecycle", "Plan, approve, build and revise intents, git-native from request to merge."
        ),
        Area(
            "records",
            "Records and contracts",
            "Durable git and blob hard copies, the schemas every artifact follows, and one command grammar.",
        ),
        Area(
            "broker",
            "Egress broker",
            "Model traffic, dependency routes, spend limits, attribution and credentials, through one chokepoint.",
        ),
        Area(
            "runtime",
            "Agent runtime",
            "What runs inside an agent pod: postures, sandbox proofs, network lock-down and repository images.",
        ),
        Area("previews", "Previews", "Isolated, signed-in live previews for every intent pull request."),
        Area("ux", "Operator experience", "The intents dashboard, status page and CLI actions, and onboarding."),
        Area("quality", "Quality", "The end-to-end harness that proves the other intents work."),
        Area("skills", "Authoring skills", "A skills plugin for writing intents and reviewing plans."),
        Area("rebrand", "Rebrand", "Centralised product names and an upgradable rename."),
    )
}


@dataclass
class Intent:
    path: Path
    meta: dict
    raw_frontmatter: str
    body: str
    sections: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return str(self.meta["id"])

    @property
    def slug(self) -> str:
        return self.meta["slug"]

    @property
    def key(self) -> str:
        """The id-slug name other intents use in depends_on and in prose."""
        return f"{self.id}-{self.slug}"

    @property
    def title(self) -> str:
        return self.meta["title"]

    @property
    def project(self) -> str:
        return self.meta["project"]

    @property
    def phase(self) -> Phase:
        return PHASES[int(self.meta["phase"])]

    @property
    def area(self) -> Area:
        return AREAS[self.meta["area"]]

    @property
    def effort(self) -> str:
        return self.meta["effort"]

    @property
    def status(self) -> str:
        return self.meta["status"]

    @property
    def depends_on(self) -> list[str]:
        return list(self.meta.get("depends_on") or [])

    @property
    def repositories(self) -> list[str]:
        return list(self.meta.get("repositories") or [])

    @property
    def issue(self) -> str | None:
        return self.meta.get("issue")

    @property
    def short_title(self) -> str:
        """The slug as words, for navigation entries."""
        words = [ACRONYMS.get(w, w) for w in self.slug.split("-")]
        return " ".join([words[0][:1].upper() + words[0][1:], *words[1:]])

    @property
    def relpath(self) -> str:
        """The path from the repository root, or intents/<name> for a file outside it (as in tests)."""
        if self.path.is_relative_to(ROOT):
            return self.path.relative_to(ROOT).as_posix()
        return f"intents/{self.path.name}"

    @property
    def source_url(self) -> str:
        return f"{REPO_URL}/blob/main/{self.relpath}"

    @property
    def outcome(self) -> str:
        """The first paragraph of "What should change, and why?", which states the outcome."""
        text = self.sections.get(SECTIONS[0], "").strip()
        return text.split("\n\n", 1)[0].replace("\n", " ").strip()

    @property
    def request(self) -> str:
        """The request a planner reads: the body after the frontmatter, without its H1."""
        lines = self.body.lstrip("\n").splitlines()
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
        return "\n".join(lines).strip() + "\n"


def split_sections(body: str) -> dict[str, str]:
    """Map each level-two heading to the text under it."""
    out: dict[str, str] = {}
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = ""
        elif current is not None:
            out[current] += line + "\n"
    return out


def parse(path: Path) -> Intent:
    text = path.read_text()
    m = FRONTMATTER.match(text)
    if not m:
        raise ValueError(f"{path}: no YAML frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    body = text[m.end() :]
    return Intent(path=path, meta=meta, raw_frontmatter=m.group(1), body=body, sections=split_sections(body))


def load(directory: Path = INTENTS_DIR) -> list[Intent]:
    """Every intent file, ordered by id."""
    return [parse(p) for p in sorted(directory.glob("[0-9][0-9][0-9]-*.md"))]


def by_key(intents: list[Intent]) -> dict[str, Intent]:
    return {i.key: i for i in intents}


def dependents(intents: list[Intent]) -> dict[str, list[Intent]]:
    """For each intent key, the intents that depend on it."""
    out: dict[str, list[Intent]] = {i.key: [] for i in intents}
    for i in intents:
        for dep in i.depends_on:
            out.setdefault(dep, []).append(i)
    return out


# Characters an approver cannot see: zero-width, bidi controls, the byte order mark, tag characters and variation
# selectors. A request must be plain, visible text.
INVISIBLE = re.compile(r"[​-‏‪-‮⁠-⁩﻿︀-️\U000e0000-\U000e007f]")
CODE_SPAN = re.compile(r"`[^`\n]*`")
FENCED = re.compile(r"^(`{3,}|~{3,}).*?^\1\s*$", re.S | re.M)
HIDDEN_HTML = re.compile(r"<!--|<details|<summary|<[a-z][a-z0-9]*[\s>/]", re.I)


def validate(intents: list[Intent]) -> list[str]:
    """Every contract violation across the intent files, as readable messages."""
    errors: list[str] = []
    keys = by_key(intents)
    ids: dict[str, str] = {}
    for i in intents:
        where = i.relpath
        missing = [k for k in KEYS if k not in i.meta]
        if missing:
            errors.append(f"{where}: missing frontmatter keys {missing}")
            continue
        order = [k for k in i.meta if k in KEYS]
        if order != list(KEYS):
            errors.append(f"{where}: frontmatter keys are not in template order")
        if not re.fullmatch(r"\d{3}", i.id):
            errors.append(f"{where}: id must be three digits, quoted")
        if i.path.name != f"{i.key}.md":
            errors.append(f"{where}: file name must be {i.key}.md")
        if i.id in ids:
            errors.append(f"{where}: id {i.id} is already used by {ids[i.id]}")
        ids[i.id] = where
        if len(i.title) > 100:
            errors.append(f"{where}: title is {len(i.title)} characters; the limit is 100")
        if int(i.meta["phase"]) not in PHASES:
            errors.append(f"{where}: unknown phase {i.meta['phase']}")
        if i.meta["area"] not in AREAS:
            errors.append(f"{where}: unknown area {i.meta['area']!r}; add it to AREAS in scripts/intentlib.py")
        if i.effort not in EFFORTS:
            errors.append(f"{where}: effort must be one of {EFFORTS}")
        if i.status not in STATUSES:
            errors.append(f"{where}: status must be one of {STATUSES}")
        if not i.repositories:
            errors.append(f"{where}: name at least one repository")
        for ref in i.meta.get("refs") or []:
            if not str(ref).startswith("https://"):
                errors.append(f"{where}: ref {ref!r} must be a full https URL, pinned to a commit")
        h1 = f"# [{i.project}] {i.title}"
        if not i.body.lstrip("\n").startswith(h1 + "\n"):
            errors.append(f"{where}: the first line of the body must be {h1!r}")
        headings = [h for h in i.sections]
        if headings != list(SECTIONS):
            errors.append(f"{where}: sections must be exactly {list(SECTIONS)}, in order; found {headings}")
        if "## Repositories" in i.body:
            errors.append(f"{where}: do not add a Repositories section; the intent controller appends it")
        visible = CODE_SPAN.sub("", FENCED.sub("", i.body))
        if HIDDEN_HTML.search(visible):
            errors.append(f"{where}: raw HTML outside code spans; requests must be plain, visible text")
        if INVISIBLE.search(i.body):
            errors.append(f"{where}: invisible or bidi control characters in the body")
        for dep in i.depends_on:
            target = keys.get(dep)
            if target is None:
                errors.append(f"{where}: depends on unknown intent {dep!r}")
            elif int(target.meta["phase"]) > int(i.meta["phase"]):
                errors.append(f"{where}: depends on {dep}, which is in a later phase")
            if f"`{dep}`" not in i.sections.get("Depends on", ""):
                errors.append(f"{where}: {dep} is in depends_on but not in the Depends on section")
    errors += _cycles(intents)
    return errors


def _cycles(intents: list[Intent]) -> list[str]:
    keys = by_key(intents)
    state: dict[str, int] = {}
    found: list[str] = []

    def visit(key: str, trail: list[str]) -> None:
        if state.get(key) == 2 or key not in keys:
            return
        if state.get(key) == 1:
            found.append("dependency cycle: " + " -> ".join(trail[trail.index(key) :] + [key]))
            return
        state[key] = 1
        for dep in keys[key].depends_on:
            visit(dep, trail + [key])
        state[key] = 2

    for k in keys:
        visit(k, [])
    return found
