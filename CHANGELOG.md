# Changelog

## 0.1.0
- `audit-my-bots` skill: checks up on your Grok Bots from their own chat history (read-only) and suggests fixes,
  merges and removals, each backed by word-for-word quotes.
- Analysis scripts, correction rubric, status and scoring criteria, all bundled next to `SKILL.md`
  in `skills/audit-my-bots/` (`scripts/`, `references/`).
- The scripts fix only the report's shape (sections, table, order, scores, quote checks, HTML/PDF layout). All wording,
  labels, dates and translations come from `findings.json`, written by the host bot in the user's language; English
  labels are only a fallback. No per-language rules anywhere.
- Quotes keep the original words, with an optional translation.
- Cue phrases: a minimal English fallback, plus `cues.json` from the bot, or `judge_inputs.py --all` to judge every reply.
- System fonts only: one generic sans and one serif stack (the host bot may override them with `fonts`),
  script-agnostic line breaking; no font files bundled.
- The skill runs in the host bot only: it fetches every chat itself, never reads app databases instead, and stops if it
  can't read chats. It never deletes or merges bots; it shows the user how to clean up a bot after checking its routines.
- The skill finds its files from its own folder, with a fallback to the newest installed copy.
- One-plugin `.cursor-plugin/marketplace.json` so the repository can be imported directly.
- Offline end-to-end test on a synthetic fixture (`python3 tests/test_pipeline.py`).
