# Changelog

## 0.1.1
- plugin.json: removed `author.url`, which the official plugin schema rejects (author takes `name` and `email` only).
- Moved `scripts/`, `references/` and the fonts into `skills/audit-my-bots/`, next to `SKILL.md`, as the Agent Skills docs describe.
- The skill now finds its files from its own folder, with a fallback that picks the newest installed copy
  (installed copies are stored per commit, not per version).
- Added a one-plugin `.cursor-plugin/marketplace.json` so the repository can be imported directly.
- README install section updated.

## 0.1.0
- First version: `audit-my-bots` skill, analysis scripts, correction rubric, status and scoring criteria,
  HTML + PDF report (English default, Korean optional), offline test on a synthetic fixture.
