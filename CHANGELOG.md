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
- Fetching: several pages (several bots) saved in one call; progress notes during long fetches.
- Judging: `--all` is the default for chats not mostly in English; long messages keep their start and end;
  `judge_inputs.py --show KEY` prints the full messages.
- App attachment notices and file paths are stripped from chats before any check and can never be quoted.
- Evidence may quote a memory fact or a bot description (`source`); a shared fix can carry per-bot paste text
  (`copy` as a list); the Proposals column counts real proposals only.
- Offline end-to-end and regression tests on synthetic fixtures, and a skill eval kit: replay mode
  (`sessions.py replay`), scenarios and an objective grader (`tests/EVAL.md`).
