# Changelog

## 0.1.0
- `audit-my-bots` skill: checks up on your Grok Bots from their own chat history (read-only) and suggests fixes,
  merges and removals, each backed by word-for-word quotes.
- Analysis scripts, correction rubric, status and scoring criteria, all bundled next to `SKILL.md`
  in `skills/audit-my-bots/` (`scripts/`, `references/`, `assets/fonts/`).
- HTML + PDF report, English by default, Korean optional, with subset OFL fonts embedded (`--no-fonts` uses system fonts).
- The skill finds its files from its own folder, with a fallback to the newest installed copy.
- One-plugin `.cursor-plugin/marketplace.json` so the repository can be imported directly.
- Offline end-to-end test on a synthetic fixture (`python3 tests/test_pipeline.py`).
