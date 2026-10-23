# Copyright 2026 BitWise Media Group Ltd
# SPDX-License-Identifier: MIT
#
# intents — the agentic PDLC intents for patchy, their validator, their issue
# projection and the documentation site. Everything lives in mise tasks: the
# shared toolchain submodule at .mise/ provides the pinned tools and the
# python archetype (selected in the root mise.toml), and tasks.toml carries
# the repo-local surface. This Makefile is only the thin forwarding shim, so
# `make <task>` == `mise run <task>`.
include .mise/archetypes/python/include.mk
