# Writing the findings

How to turn `findings_draft.json` (a frame: rows with `TODO`, no findings) into the final findings. The schema is in
`findings-schema.md`; what to judge is in `criteria.md`. Everything the reader sees is written by you in the user's language.

## Repeated-correction groups
- Start from `correction_topics` in diag.json and apply the decision procedure in `criteria.md` §5 in order (shared
  cause, merging, normal iteration, fixes, status).
- **Kept group:** one finding; its evidence quotes the incidents (`refs`); its `fix` and `copy` state the specific rule
  from §5 step 1 (it passes the paste test: it names what to check in this bot's domain).
- **Fixes:** `fixes_after` lists saves and promised fixes by id (texts in the bot's `fixes`). Most memory saves are about
  something else (an email address, a schedule). Decide which, if any, are about this problem; the **latest** decides:
  fixed (no finding; one line in `improving`, what was fixed and when), too early (`"too_early": true`, and say in `fix`
  when the rule was saved), or came back (add "came back after a fix" to `score.basis`, impact +1, and a `copy` more
  specific than the rule that failed). `fixes_after_omitted` counts older saves with no incident after them; they are
  in `$W/timelines/<id>.json` (events with `kind` `memory_write`).

## Status
You set every status (`criteria.md` §2) and name the reason in `why`, one sentence.
- **Fine bots:** `issue` is a neutral 2-6 word line ("Working well", "Nothing repeating"). Not a problem statement:
  a small proposal (for example, no saved job description) still belongs in the findings, not in the issue column.
  A bot that is quiet but still wanted (its routine runs, its slow rhythm, the user said to keep it, set up recently)
  says why in `why`.
- **Clean-up bots:** exactly one finding with `"cleanup": true` (finalize checks it) says why, with usage facts as
  `text` lines and the last request as a `ref`. A habit that stopped says it was used regularly and then stopped
  (dates and rhythm), not that it was barely used. Fold any other finding of that bot into it: the only option is
  "Show me how to clean up X". Its repeated corrections are not proposals; you may add them as `lessons` ("if you come
  back to it"), each `copy` the rule to save first. Its `short` is both its top-3 line and its one option (SKILL.md
  step 9). The shared job-text item skips clean-up bots. The fleet keep / clean-up item explains how; don't repeat the
  how in each bot. No `copy` unless the bot's job should move to another bot: then `copy` is the text for that other
  bot, with `copy_kind` `memory` (a message asking it to remember).

## Words
- `fix` is written from the user's side: what they can do, or what will be applied when they pick this item ("Pick this
  and a rule is saved to Garden Helper's memory"; "Send this to Print Desk and ask it to remember it"). Never word it as if you had
  already changed, or will quietly change, another bot: nothing changes until the user picks it (SKILL.md step 9).
- `copy` goes to a bot, so write it in the language the user uses with that bot (it may differ from the report).
  Text for another bot (`copy_kind` `memory`) is a message the user sends that bot, asking it to remember it. Don't
  tell the user to paste it into a description or settings field: personal bots may have none (only a Team Bot has a
  description, edited by its owner).
- **Routine proposals** (`copy_kind` `routine`): you (the auditing bot) create the routine if the user picks it, so
  its `copy` (what the routine does) is in the user's report language, not the other bot's chat language. Any time in
  it (`fix`, `copy`, `short`) is in the user's real time zone from your context, never the replay timeline's UTC offset
  in a test, and names that zone once (for example "every day at 17:00 <zone>").
- Job text for a bot with no saved job description (the `job_text` fleet item): 1-2 sentences, under about 200
  characters, what the bot does for this user and how they like it done, taken from how they actually use it, worded
  as a message to that bot ("Remember: your job is…"). No promises the bot can't keep.
- `date` is the run date (in replay tests, the recorded date). `date_label` is that date as the reader writes it. The
  period covered comes from the data; mention it only if useful.
- Evidence dates (`now[].date`) come as `MM/DD`. You may rewrite them the way the reader writes dates, but use one
  format throughout the report.
- Footer: `ui.footer` is the base sentence; `ui.footer_q` (quotes are word for word) is added only when the report has
  a quote, and `ui.footer_tr` (about translated quotes) only when a translated quote exists. Write all three; with no
  quotes the footer is just the base sentence.
- Opening sentence: before finalize, rewrite the `ui.lede_*` key that fits the final statuses (`findings-schema.md`, UI labels) as a
  natural sentence for those counts, singular or plural; don't leave a form like "1 need work".
- `score.basis` is internal (only in `scores.md`); it is never shown, so it can stay short and in any language.
- Placeholder text: every English string the skeleton wrote is recorded; when the report language isn't English,
  finalize `--strict` lists any left unchanged (including `ui` labels).
- Fleet section: the keep / clean-up item already says nothing is deleted automatically and how to clean up; don't
  repeat it in other items.
- The keep / clean-up item (`"keep": true`): reword it in the user's language. If every bot is kept, one short line
  and a `fix` that says nothing needs cleaning up (no delete steps); with no other fleet item the report shows it as one
  compact line, not a numbered item.
- Evidence lines with no date (`"date": ""`): the report drops the date column when no line of that item has a date.
- The opening sentence (`ui.lede_*`) is also the first sentence of your chat message; keep them the same.

## Quotes
- `quote.orig` is word for word, and its line carries the `ref` of the message it comes from (finalize looks for the
  quote in that message). Memory-block and description quotes have `source` and no `ref`; the finding still cites a message.
- A user quote from another bot's chat gets `"chat": "<that bot's name>"`; the report shows it as `ui.in_chat`
  ("You (in X)"). Use `who` for other speakers. A bot quote leaves out anything the app added (for example, a sent-message notice).
- A quote may come from another bot's chat or memory when it is evidence for this finding; finalize searches the whole
  fleet.
- `source` (`memory` or `description`) goes on the evidence line that holds the quote, nowhere else.
- Never quote file paths, attachment notices or secrets.
- One evidence line holds either a `quote` or a `text`, not both (finalize refuses both). `who` names the speaker when the
  quote isn't the user's words in this bot's chat: `"who": "bot"` for this bot's own words (shown as `ui.who_bot`, by
  default its name), or another bot's name in a fleet item. Never write a fallback word like "Bot" in another language
  than the report's.
- Quote the sentence that decided the label; for a long message, a full sentence or two, never a draft cut mid-sentence.

## Other items
- **Unanswered requests** (not part of a fleet outage) are an info item in the bot's findings, not a scored proposal.
- **Bots not in `bots.json`** (seen only in other chats, for example a bot the user removed) are never rows or bot
  sections and change no listed bot's status. A safety event about one goes in the fleet safety info item: name it as
  the chat does, say it is no longer in the list, and say what the user can do. Don't open files it wrote to check.
- **Safety events** you saw in the chats (a secret printed or written to a log, another bot's settings shown, a risky
  step taken without asking): one fleet info item per kind, saying which bot and when, and what to do (for example,
  change that password). Describe the secret ("a login code"); never quote it.
- **Secrets the user typed** (a password or code pasted into a chat): not a bot's safety event, no status effect. A
  lasting secret gets one line in the safety item suggesting a change; an expired one-time code gets nothing.
- **Leads that aren't corrections** (several skipped questions of one kind, a stale memory fact, a promise not kept)
  can be scored findings with the default impact in `criteria.md` §4.
- **Several messages with no reply** (`unanswered_runs`): read them. A stuck bot, an error, or the user typing ahead.
  A finding only on 2+ days (for example, a rule to say what it is doing when work takes long).
- **Chat language** (`scripts`): low priority. A finding (impact 1, a rule to answer in the user's language) only if
  the user minded it, in the chats or in their request to you; otherwise nothing.
- **Repeated requests** (from the digest): a routine (`copy_kind` `routine`) for the same request by hand on 3+ days;
  a standing rule (`kind` `follow_up`, `copy_kind` `memory`) for the same follow-up after the bot's answers. Never for
  thanks, approvals or keep statements.
- **Stale memory:** a finding only if later chats contradict the fact, or the fact has clearly expired (for example, a
  past date). "Currently" alone isn't enough. Cite the later message by `ref` and quote the fact with `source` `memory`.
- **Skipped questions:** one or two mean nothing. Several of the same kind from one bot can justify a rule like "go
  ahead with the recommended option and say what you did".
- **Setup items** (`kind` group, redundant_groups, handoff_format, connector, safety_rules, routine_cost) and a
  correction finding's optional `review` routine: `setup.md`.
- **Shared causes:** one fleet item; each bot points to it with `"see": "fleet-N"`. When each bot needs its own text,
  `copy` is a list of `{"bot", "text"}`. Bots with no saved job description: one fleet item (`kind` `job_text`).
- **No proposals at all:** the report hides the top-3 section. In the chat, say in one line that there is nothing to
  do, skip the multi-select, and only offer the weekly re-check.

## Chat message and options (SKILL.md steps 8-9)
- The fixed strings in SKILL.md and these references ("Show me how to clean up X", "None for now", "Nothing major to
  fix.") are examples of meaning, not text to copy: write them in the user's language, like every other word.
- Option order: the top 3 in their order, then every other proposal in report order (bot sections top to bottom, each
  bot's findings in order, then the fleet items). A clean-up bot has one option, its clean-up finding's `short` line
  ("show me how to clean up X", in the user's language): at its top-3 place if one of its findings is there, otherwise
  at its bot's place among the bot sections, never with the fleet items (the fleet keep / clean-up item is info, not an
  option). "None for now" is last.
- Never label an option remove, delete or merge, in any language.
