---
description: "How to pick up, refine or add an intent, and how the files, issues and board stay in step."
---

# Picking up an intent

## Pick one up

1. Choose an intent whose dependencies have landed. The [roadmap](roadmap.md) shows the order, and each intent's _At a
   glance_ block lists what it depends on and what it unblocks.
2. Comment on its tracking issue to claim it, and move it to _In progress_ on the
   [project board](https://github.com/orgs/bitwise-media-group/projects/3).
3. Read the intent in full, including its open questions. Settle the ones the work depends on first, by a pull request
   to the intent file.
4. Open pull requests against the repositories in its frontmatter. Refer back to the tracking issue.

The intents are shaped like maul's issue form, so maul itself can plan and build them: open the request in a maul
intents repository, review the plan it posts, and approve it there.

## Refine one

Change the intent file in a pull request. Keep the [writing guidance](concepts/writing-intents.md), then run:

```sh
make lint      # the intent contract, generated-docs drift, prose and licence checks
make serve     # preview the site on http://localhost:8004
```

After the change merges, run `make project` to update the projected issue. The issue is never edited by hand: an edit
there is overwritten the next time the file is projected.

## Add one

Copy [`templates/intent.md`](https://github.com/bitwise-media-group/intents/blob/main/templates/intent.md) to
`intents/<id>-<slug>.md` with the next free id, fill it in, and leave `issue: null`. If it adds an area, add the area to
`AREAS` in `scripts/intentlib.py` and a page under `docs/areas/`. `make lint` prints the navigation entries
`zensical.toml` needs. `make project` creates the issue and writes its URL back into the file.

## Commits

Commits follow [Conventional Commits](https://www.conventionalcommits.org/). Use `feat:` for a new intent, `docs:` for a
refinement, and `chore:` for tooling.
