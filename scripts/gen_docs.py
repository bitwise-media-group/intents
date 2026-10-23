# Copyright 2026 BitWise Media Group Ltd
# SPDX-License-Identifier: MIT

"""Generate the docs site's intent pages and fragments, and the README index, from the intent files.

Writes, all git-ignored and rebuilt by every docs entry point (`make docs-build`, `make serve`, docs.yaml):

- docs/intents/<id>-<slug>.md      one page per intent: an at-a-glance block, then the request verbatim
- build/intent-docs/areas/<area>.md the intents of one area, embedded by docs/areas/<area>.md
- build/intent-docs/roadmap.md      the phases and their intents, embedded by docs/roadmap.md
- build/intent-docs/graph.md        the dependency graph (mermaid), embedded by docs/roadmap.md
- build/intent-docs/catalogue.md    every intent in one table, embedded by docs/catalogue.md
- build/intent-docs/questions.md    every open question, by area, embedded by docs/questions.md

It also rewrites the intent index in README.md between its markers.

With --check it writes nothing and fails when the README index is stale, an area page is missing, or the "Areas"
section of zensical.toml's nav does not list exactly the generated pages; it prints the expected nav section.
"""

from __future__ import annotations

import re
import shutil
import sys
import tomllib

from intentlib import AREAS, PHASES, ROOT, Intent, by_key, dependents, load

DOCS = ROOT / "docs"
PAGES = DOCS / "intents"
FRAGMENTS = ROOT / "build" / "intent-docs"
README = ROOT / "README.md"
ZENSICAL = ROOT / "zensical.toml"

INTENT_REF = re.compile(r"`(\d{3}-[a-z0-9-]+)`")

#: mermaid fill colours per area, from the org palette in docs/stylesheets/extra.css.
AREA_COLOURS = {
    "intents": "#d96c36",
    "records": "#5f8a4e",
    "broker": "#b5462a",
    "runtime": "#e3a33b",
    "previews": "#4f7c8a",
    "ux": "#8a6bb0",
    "quality": "#7a6a58",
    "skills": "#3f6fa8",
    "rebrand": "#a1471f",
}


def label(i: Intent) -> str:
    return f"{i.id} · {i.title}"


def nav_label(i: Intent) -> str:
    return f"{i.id} · {i.short_title}"


def link_refs(text: str, keys: dict[str, Intent], prefix: str) -> str:
    """Turn `NNN-slug` references to known intents into links relative to the including page."""

    def sub(m: re.Match) -> str:
        key = m.group(1)
        return f"[`{key}`]({prefix}{key}.md)" if key in keys else m.group(0)

    return INTENT_REF.sub(sub, text)


def intent_links(refs: list[Intent], prefix: str) -> str:
    return ", ".join(f"[{label(r)}]({prefix}{r.key}.md)" for r in refs) or "none"


def repo_link(url: str) -> str:
    name = url.removeprefix("https://github.com/")
    return f"[{name}]({url})"


def issue_link(i: Intent) -> str:
    if not i.issue:
        return "not projected yet"
    return f"[#{i.issue.rstrip('/').rsplit('/', 1)[1]}]({i.issue})"


def description(i: Intent) -> str:
    """A one-sentence page description from the outcome paragraph, plain text."""
    text = re.sub(r"`([^`]*)`", r"\1", i.outcome)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return first if len(first) <= 300 else first[:297].rstrip() + "..."


def yaml_string(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def intent_page(i: Intent, keys: dict[str, Intent], unblocks: list[Intent]) -> str:
    deps = [keys[d] for d in i.depends_on if d in keys]
    glance = [
        f"- **Area:** [{i.area.title}](../areas/{i.area.key}.md)",
        f"- **Phase:** [{i.phase.label}](../roadmap.md#{i.phase.anchor})",
        f"- **Effort:** {i.effort} · **Status:** {i.status}",
        f"- **Repositories:** {', '.join(repo_link(r) for r in i.repositories)}",
        f"- **Depends on:** {intent_links(deps, '')}",
        f"- **Unblocks:** {intent_links(unblocks, '')}",
        f"- **Tracking issue:** {issue_link(i)} · **Source:** [{i.relpath}]({i.source_url})",
    ]
    return "\n".join(
        [
            "---",
            f"title: {yaml_string(label(i))}",
            f"description: {yaml_string(description(i))}",
            "---",
            "",
            f"# {i.title}",
            "",
            '!!! abstract "At a glance"',
            "",
            *[f"    {line}" for line in glance],
            "",
            link_refs(i.request, keys, ""),
        ]
    )


def area_fragment(area_intents: list[Intent], keys: dict[str, Intent]) -> str:
    out = [
        "| Intent | Phase | Effort | Depends on |",
        "| ------ | ----- | ------ | ---------- |",
    ]
    for i in area_intents:
        deps = ", ".join(f"[{d[:3]}](../intents/{d}.md)" for d in i.depends_on) or "none"
        out.append(f"| [{label(i)}](../intents/{i.key}.md) | {i.phase.number} | {i.effort} | {deps} |")
    for i in area_intents:
        out += [
            "",
            f"## {label(i)}",
            "",
            link_refs(i.outcome, keys, "../intents/"),
            "",
            f"**{i.phase.label}** · **Effort** {i.effort} · **Status** {i.status} · "
            f"[Read the intent](../intents/{i.key}.md) · Issue {issue_link(i)}",
        ]
    return "\n".join(out) + "\n"


def roadmap_fragment(intents: list[Intent]) -> str:
    out: list[str] = []
    for phase in PHASES.values():
        members = [i for i in intents if i.phase.number == phase.number]
        if not members:
            continue
        out += ["", f"## {phase.label}", "", phase.summary, ""]
        for i in members:
            deps = ", ".join(d[:3] for d in i.depends_on) or "none"
            out.append(f"- [{label(i)}](intents/{i.key}.md): {i.area.title}, {i.effort} effort, depends on {deps}")
    return "\n".join(out).lstrip("\n") + "\n"


def graph_fragment(intents: list[Intent]) -> str:
    out = ["```mermaid", "flowchart LR"]
    for phase in PHASES.values():
        members = [i for i in intents if i.phase.number == phase.number]
        if not members:
            continue
        out.append(f'  subgraph p{phase.number}["{phase.number} · {phase.title}"]')
        out += [f'    n{i.id}["{i.id} {i.short_title}"]' for i in members]
        out.append("  end")
    for i in intents:
        out += [f"  n{d[:3]} --> n{i.id}" for d in i.depends_on]
    for key, colour in AREA_COLOURS.items():
        out.append(f"  classDef {key} fill:{colour},stroke:{colour},color:#fff")
    for i in intents:
        out.append(f"  class n{i.id} {i.area.key}")
    out.append("```")
    legend = " · ".join(f"**{AREAS[k].title}** ({k})" for k in AREAS if any(i.area.key == k for i in intents))
    return "\n".join(out) + "\n\nNode colours by area: " + legend + ".\n"


def catalogue_fragment(intents: list[Intent]) -> str:
    out = [
        "| Intent | Area | Phase | Effort | Status | Issue |",
        "| ------ | ---- | ----- | ------ | ------ | ----- |",
    ]
    for i in intents:
        out.append(
            f"| [{label(i)}](intents/{i.key}.md) | [{i.area.title}](areas/{i.area.key}.md) | "
            f"{i.phase.number} | {i.effort} | {i.status} | {issue_link(i)} |"
        )
    return "\n".join(out) + "\n"


def questions_fragment(intents: list[Intent], keys: dict[str, Intent]) -> str:
    out: list[str] = []
    for area in AREAS.values():
        members = [i for i in intents if i.area.key == area.key and i.sections.get("Open questions", "").strip()]
        if not members:
            continue
        out += ["", f"## {area.title}"]
        for i in members:
            out += ["", f"### [{label(i)}](intents/{i.key}.md)", ""]
            out.append(link_refs(i.sections["Open questions"].strip(), keys, "intents/"))
    return "\n".join(out).lstrip("\n") + "\n"


def markdown_table(header: list[str], rows: list[list[str]]) -> list[str]:
    """A table padded the way prettier aligns one, so formatting the README never changes generated output."""
    widths = [max(3, len(h), *(len(r[c]) for r in rows)) for c, h in enumerate(header)]

    def line(cells: list[str]) -> str:
        return "| " + " | ".join(cell.ljust(w) for cell, w in zip(cells, widths, strict=True)) + " |"

    return [line(header), line(["-" * w for w in widths]), *(line(r) for r in rows)]


def readme_index(intents: list[Intent]) -> str:
    out: list[str] = []
    for phase in PHASES.values():
        members = [i for i in intents if i.phase.number == phase.number]
        if not members:
            continue
        rows = [
            [
                i.id,
                f"[{i.title}]({i.relpath})",
                i.area.title,
                i.effort,
                ", ".join(d[:3] for d in i.depends_on) or "none",
                f"[#{i.issue.rstrip('/').rsplit('/', 1)[1]}]({i.issue})" if i.issue else "",
            ]
            for i in members
        ]
        out += [f"### {phase.label}", ""]
        out += markdown_table(["ID", "Intent", "Area", "Effort", "Depends on", "Issue"], rows)
        out.append("")
    return "\n".join(out)


INDEX = re.compile(r"(<!-- index:start -->\n).*?(<!-- index:end -->)", re.S)


def render_readme(intents: list[Intent]) -> str:
    text = README.read_text()
    return INDEX.sub(lambda m: m.group(1) + "\n" + readme_index(intents) + "\n" + m.group(2), text)


def expected_areas_nav(intents: list[Intent]) -> list[dict]:
    nav = []
    for area in AREAS.values():
        members = [i for i in intents if i.area.key == area.key]
        if members:
            nav.append(
                {area.title: [f"areas/{area.key}.md", *({nav_label(i): f"intents/{i.key}.md"} for i in members)]}
            )
    return nav


def areas_nav_toml(nav: list[dict]) -> str:
    lines = ['  { "Areas" = [']
    for section in nav:
        ((title, entries),) = section.items()
        lines.append(f'    {{ "{title}" = [')
        lines.append(f'      "{entries[0]}",')
        for entry in entries[1:]:
            ((name, path),) = entry.items()
            lines.append(f'      {{ "{name}" = "{path}" }},')
        lines.append("    ] },")
    lines.append("  ] },")
    return "\n".join(lines)


def check(intents: list[Intent]) -> list[str]:
    errors: list[str] = []
    if render_readme(intents) != README.read_text():
        errors.append("README.md intent index is stale: run `make docs-gen`")
    for key in {i.area.key for i in intents}:
        if not (DOCS / "areas" / f"{key}.md").exists():
            errors.append(f"docs/areas/{key}.md is missing: every area with intents needs a page")
    nav = tomllib.loads(ZENSICAL.read_text())["project"]["nav"]
    areas = next((v for item in nav for k, v in item.items() if k == "Areas"), None)
    expected = expected_areas_nav(intents)
    if areas != expected:
        errors.append(
            "the Areas section of zensical.toml's nav does not match the intents; expected:\n"
            + areas_nav_toml(expected)
        )
    return errors


def generate(intents: list[Intent]) -> None:
    keys = by_key(intents)
    unblocks = dependents(intents)
    shutil.rmtree(PAGES, ignore_errors=True)
    shutil.rmtree(FRAGMENTS, ignore_errors=True)
    PAGES.mkdir(parents=True)
    (FRAGMENTS / "areas").mkdir(parents=True)
    for i in intents:
        (PAGES / f"{i.key}.md").write_text(intent_page(i, keys, unblocks[i.key]))
    for area in AREAS.values():
        members = [i for i in intents if i.area.key == area.key]
        if members:
            (FRAGMENTS / "areas" / f"{area.key}.md").write_text(area_fragment(members, keys))
    (FRAGMENTS / "roadmap.md").write_text(roadmap_fragment(intents))
    (FRAGMENTS / "graph.md").write_text(graph_fragment(intents))
    (FRAGMENTS / "catalogue.md").write_text(catalogue_fragment(intents))
    (FRAGMENTS / "questions.md").write_text(questions_fragment(intents, keys))
    README.write_text(render_readme(intents))


def main(argv: list[str]) -> int:
    intents = load()
    if "--check" in argv:
        errors = check(intents)
        for e in errors:
            print(e, file=sys.stderr)
        return 1 if errors else 0
    generate(intents)
    print(f"generated {len(intents)} intent pages and their fragments")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
