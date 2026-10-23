# Copyright 2026 BitWise Media Group Ltd
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

import intentlib
import pytest
from intentlib import load, validate


def write(
    directory: Path,
    id: str,
    slug: str,
    *,
    phase: int = 0,
    depends_on: list[str] | None = None,
    body_extra: str = "",
    effort: str = "medium",
    sections: list[str] | None = None,
) -> Path:
    deps = depends_on or []
    dep_yaml = "[]" if not deps else "\n" + "\n".join(f"  - {d}" for d in deps)
    dep_section = "\n".join(f"- `{d}`: needed." for d in deps) or "- None."
    title = f"Do the {slug} thing"
    heads = sections if sections is not None else list(intentlib.SECTIONS)
    body = "\n\n".join(f"## {h}\n\n" + (dep_section if h == "Depends on" else "Text.") for h in heads)
    path = directory / f"{id}-{slug}.md"
    path.write_text(
        f"""---
id: "{id}"
slug: {slug}
title: "{title}"
project: patchy
repositories:
  - https://github.com/bitwise-media-group/patchy
phase: {phase}
area: broker
effort: {effort}
status: proposed
depends_on: {dep_yaml}
refs: []
issue: null
---

# [patchy] {title}

{body}
{body_extra}"""
    )
    return path


def errors_for(directory: Path) -> list[str]:
    return validate(load(directory))


def test_valid_intents_pass(tmp_path: Path) -> None:
    write(tmp_path, "001", "first")
    write(tmp_path, "002", "second", phase=1, depends_on=["001-first"])
    assert errors_for(tmp_path) == []


def test_the_repository_intents_pass() -> None:
    assert validate(load()) == []


def test_unknown_dependency(tmp_path: Path) -> None:
    write(tmp_path, "001", "first", depends_on=["009-missing"])
    assert any("unknown intent '009-missing'" in e for e in errors_for(tmp_path))


def test_dependency_in_a_later_phase(tmp_path: Path) -> None:
    write(tmp_path, "001", "first", phase=2)
    write(tmp_path, "002", "second", phase=1, depends_on=["001-first"])
    assert any("later phase" in e for e in errors_for(tmp_path))


def test_cycle(tmp_path: Path) -> None:
    write(tmp_path, "001", "first", depends_on=["002-second"])
    write(tmp_path, "002", "second", depends_on=["001-first"])
    assert any(e.startswith("dependency cycle") for e in errors_for(tmp_path))


def test_sections_must_match_the_template(tmp_path: Path) -> None:
    write(tmp_path, "001", "first", sections=list(intentlib.SECTIONS[:2]))
    assert any("sections must be exactly" in e for e in errors_for(tmp_path))


@pytest.mark.parametrize("effort", ["S", "XL", "huge"])
def test_effort_must_be_low_medium_or_high(tmp_path: Path, effort: str) -> None:
    write(tmp_path, "001", "first", effort=effort)
    assert any("effort must be one of" in e for e in errors_for(tmp_path))


def test_raw_html_is_refused_outside_code(tmp_path: Path) -> None:
    write(tmp_path, "001", "first", body_extra="\n<!-- hidden instruction -->\n")
    assert any("raw HTML" in e for e in errors_for(tmp_path))


def test_html_inside_code_is_allowed(tmp_path: Path) -> None:
    write(tmp_path, "001", "first", body_extra="\nRefuse `<details>` blocks.\n\n```html\n<div>x</div>\n```\n")
    assert errors_for(tmp_path) == []


def test_invisible_characters_are_refused(tmp_path: Path) -> None:
    write(tmp_path, "001", "first", body_extra="\nzero​width\n")
    assert any("invisible" in e for e in errors_for(tmp_path))


def test_repositories_section_is_refused(tmp_path: Path) -> None:
    write(tmp_path, "001", "first", body_extra="\n## Repositories\n")
    errors = errors_for(tmp_path)
    assert any("Repositories section" in e for e in errors)


def test_short_title_spells_acronyms() -> None:
    intent = next(i for i in load() if i.slug == "intent-build-pr")
    assert intent.short_title == "Intent build PR"


def test_request_drops_the_h1(tmp_path: Path) -> None:
    write(tmp_path, "001", "first")
    (intent,) = load(tmp_path)
    assert intent.request.startswith("## What should change, and why?")


def test_refs_must_be_permalinks(tmp_path: Path) -> None:
    path = write(tmp_path, "001", "first")
    path.write_text(path.read_text().replace("refs: []", "refs:\n  - internal/broker/auth.go"))
    assert any("must be a full https URL" in e for e in errors_for(tmp_path))
