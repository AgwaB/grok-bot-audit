# Changelog

## 0.1.0
- `audit-my-bots` skill: checks up on your Grok Bots from their own chat history (read-only) and suggests fixes,
  merges and removals, each backed by word-for-word quotes.
- Analysis scripts, correction rubric, status and scoring criteria, all bundled next to `SKILL.md`
  in `skills/audit-my-bots/` (`scripts/`, `references/`).
- HTML + PDF report in the user's language (English when unclear): `lang` and translated `ui` labels come from
  `findings.json`, with English defaults. Quotes keep the original words, plus a translation when the chat language differs.
- Chats in any language: English cue words built in, more per language via `cues.json`; replies in non-Latin scripts are
  never dropped from the correction candidates.
- System fonts only, with stacks for macOS/iOS, Windows, Android and Linux and fallbacks for non-Latin scripts; no font
  files are bundled.
- The skill runs in the host bot only: it fetches every chat itself, never reads app databases instead, and stops if it
  can't read chats. It never deletes or merges bots; it shows the user how to clean up a bot after checking its routines.
- The skill finds its files from its own folder, with a fallback to the newest installed copy.
- One-plugin `.cursor-plugin/marketplace.json` so the repository can be imported directly.
- Offline end-to-end test on a synthetic fixture (`python3 tests/test_pipeline.py`).
