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
- Iteration 4: `--list` cuts batches by size (about 10 KB) and prints the next `--from`, so no fixed item count (it
  depends on the chats' script and length); evidence `"who": "bot"` is a keyword shown as `ui.who_bot` (the bot's name
  by default), never an English word; count-neutral fallback opening sentences, and the host bot writes the one used
  for the real counts; `ui.footer_q` (quotes are word for word) only when the report has a quote, and `ui.expand_info`
  for sections with no proposals; fix candidates an incident came after are never cut by the cap, left-out saves are
  counted (`fix_check_omitted`), and link lists no longer read as fixes or promises; one rule for one-off mistakes vs
  stated preferences; secrets the user typed and safety events of bots not in the list; `score.basis` documented as
  internal; option order for clean-up bots outside the top 3, and fixed option strings written in the user's language;
  `replay` prints what it skipped as self (`self` in `replay.json`, `tests/EVAL.md`).
- Offline end-to-end and regression tests on synthetic fixtures, and a skill eval kit: replay mode
  (`sessions.py replay`), scenarios and an objective grader (`tests/EVAL.md`).
- Shared cause: a paste test decides specific vs generic (a rule that fits any bot unchanged is generic; one that names
  the kinds of detail to confirm in that bot's domain is specific). The skeleton no longer drafts a generic "confirm when
  ambiguous" fix; finalize `--strict` refuses a fix left as `TODO`.
- An all-kept fleet renders as one compact line (no stray item number, no page of its own); the all-keep default fix
  doesn't talk about deleting. Evidence with no dates has no blank date column.
- One test-mode note (replay then parse; report dates from the replay, the weekly offer in the user's real time zone);
  the weekly re-check is a yes/no choice; `--lang` falls back to English; rewrite the used `ui.lede_*` before finalize.
- Outage item: user quotes from other bots' chats are marked with `chat` (shown as "You (in X)"), not `who`.
- A bot with no proposals shows a dash in the status table instead of "0"; `fleet_note` is optional and normally empty.
- The clean-up finding carries a `short` line ("Show me how to clean up X", rewritten in the user's language): it is
  both its top-3 line and its one option, placed among the bot sections, never with the fleet items.
- Writing: fixes say what the user can do or what is applied when they pick it; routine text is in the user's report
  language and routine times use the user's real time zone. Step 0: source `env.sh` by its printed path; in tests,
  log commands from the first one.
- Eval grader: the chat-language check measures prose only (bot names, tables, code spans, paths, attachment lines and
  test headings are left out); a dash in the Proposals column counts as 0.
- Iteration 6: references carry no test-fixture answers (generic invented examples); the paste test also asks for the
  same kind of action, so unrelated misreads are not one shared cause; clean-up counts routine runs as use, respects a
  bot's own rhythm (a monthly bot is not idle after a month) and gives no verdict on a bot too new to judge; the "3+
  incidents" rule has a rate floor for very busy bots; judge mode ignores code and links, treats mixed scripts and
  accented Latin chats as not English, and stale-memory and promise leads also work without words; each run gets a new
  private work folder; the weekly re-check routine is report-only, quiet when nothing changed (`summary.json`,
  `make_report.py --previous`) and safe to re-run; text for another bot is a message it is asked to remember, not a
  description field; setup checks in their own report section (`references/setup.md`): group chats for hand-offs the
  user does by hand, group chats with the same members, plugins instead of the browser, safety rules kept only in
  memory, routines that run very often.
- Iteration 7: a stopped habit (used regularly, now idle far beyond its rhythm) is a clean-up candidate at any share;
  messages from other bots count as use; hand-offs that are long or repeat themselves get a fixed short format (goal,
  where, done when, waiting on); a mistake that came back after a fix may get an optional low-cadence rule-review
  routine that stays quiet when nothing is new; group suggestions are one group per project with a lead bot, members in
  order and a "blocked: ask the user" step, and finalize checks that structure; the pasted answer is matched to the one
  bot message it fits best.
- Iteration 8 (from a real-data test run): the time zone comes from any timestamped entry, and a bot with none takes
  the fleet's zone; days of use are counted by working session (late-night work is one day); messages judged as
  corrections are no longer also a "same request" item, and the same follow-up after answers becomes a standing rule
  instead of a routine; a stopped habit has its own reason and clean-up title, with optional "if you come back to it"
  lessons from its repeated corrections; file paths with spaces are recognised; new low-priority leads for stalls
  (several short nudges, no reply) and replies in another language than the chat's; no hand-off format for
  machine-made templates or one fan-out burst; report rows in status order and long bot names wrap.
