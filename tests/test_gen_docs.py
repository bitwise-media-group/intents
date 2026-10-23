# Copyright 2026 BitWise Media Group Ltd
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib

import gen_docs
from intentlib import AREAS, by_key, dependents, load

INTENTS = load()
KEYS = by_key(INTENTS)


def test_link_refs_links_known_intents_only() -> None:
    text = "Needs `001-broker-chokepoint` and `999-nothing`, and `plain code`."
    out = gen_docs.link_refs(text, KEYS, "../intents/")
    assert "[`001-broker-chokepoint`](../intents/001-broker-chokepoint.md)" in out
    assert "`999-nothing`" in out and "[`999-nothing`]" not in out


def test_intent_page_has_frontmatter_glance_and_request() -> None:
    intent = KEYS["017-intent-approval"]
    page = gen_docs.intent_page(intent, KEYS, dependents(INTENTS)[intent.key])
    assert page.startswith('---\ntitle: "017 · ')
    assert '!!! abstract "At a glance"' in page
    assert "[Intent lifecycle](../areas/intents.md)" in page
    assert "## What should change, and why?" in page
    assert f"# {intent.title}\n" in page
    assert "# [patchy]" not in page


def test_unblocks_lists_dependents() -> None:
    unblocks = dependents(INTENTS)["001-broker-chokepoint"]
    assert "002-no-credentials-in-agent-pods" in {i.key for i in unblocks}


def test_graph_has_a_node_per_intent_and_an_edge_per_dependency() -> None:
    graph = gen_docs.graph_fragment(INTENTS)
    assert graph.count('"]\n') >= len(INTENTS)
    edges = sum(len(i.depends_on) for i in INTENTS)
    assert graph.count(" --> ") == edges


def test_expected_nav_covers_every_intent_once() -> None:
    nav = gen_docs.expected_areas_nav(INTENTS)
    paths = [path for section in nav for entries in section.values() for e in entries[1:] for path in e.values()]
    assert sorted(paths) == sorted(f"intents/{i.key}.md" for i in INTENTS)
    assert [next(iter(s)) for s in nav] == [a.title for a in AREAS.values() if any(i.area == a for i in INTENTS)]


def test_nav_toml_round_trips() -> None:
    nav = gen_docs.expected_areas_nav(INTENTS)
    parsed = tomllib.loads("nav = [\n" + gen_docs.areas_nav_toml(nav) + "\n]\n")["nav"]
    assert parsed == [{"Areas": nav}]


def test_zensical_nav_and_readme_are_current() -> None:
    assert gen_docs.check(INTENTS) == []
