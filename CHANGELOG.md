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
- Memory saves after a repeated problem are only fix candidates (`fix_check`): the bot confirms or drops them, and
  they change neither status nor impact until then.
- Judging: mode chosen per bot by its chats' language; question cards and the starting request in each item; a compact
  `--list` view and TSV labels (`--label`); a bot with no cue match gets all its replies judged.
- Writing guide (`references/writing.md`); an all-Fine report hides the empty top-3 section; no duplicated fleet note.
- Consistency between runs: repeated corrections count separate occasions (6+ hours apart), so one long session is
  never "repeated"; fix candidates carry the incidents and days of use after them, and "improving" needs no incident
  after the fix and 2+ later days; an explicit decision procedure for shared causes, merging, normal iteration and
  status overrides (`criteria.md` §5).
- Judging: `--auto` picks the mode per bot from the share of its user messages in Latin letters (printed per bot);
  `--list` shows each bot message once; labels.tsv has fixed columns with a `user_start` check against off-by-one
  mistakes and a `promised` column (in-chat promises become fix candidates); unlisted items are `none`.
- finalize: leftover skeleton placeholders and English `ui` labels are flagged in a non-English report; an evidence line
  with both quote and text is an error. Skeleton quotes whole sentences and uses one date format.
- A request that is the last message in the data isn't counted as unanswered; replay skips only a recorded `self`.
- A fixed recipe for the chat message and the follow-up question; scratch files go in `$W/tmp`.
- Iteration 3: a decisive shared-cause test (a specific rule naming what to check; generic "confirm more" rules never
  count), sub-groups and combined override reasons; fix candidates listed once per bot, only promises said to the user,
  the latest relevant fix decides; make_report writes the opening sentence to `report/lede.txt` and checks the whole
  report (`report/checks.txt`); `chat` evidence ("You (in X)"), a "too early to tell" tag, the translated-quote note only
  when needed; one clean-up option per clean-up bot; `--list --short`; clearer `--auto` lines; `tests/compare_runs.py`.
- Offline end-to-end and regression tests on synthetic fixtures, and a skill eval kit: replay mode
  (`sessions.py replay`), scenarios and an objective grader (`tests/EVAL.md`).
