# Writing the findings

How to turn `findings_draft.json` into the final findings. The schema is in `findings-schema.md`; the rules and
thresholds are in `criteria.md`. Everything the reader sees is written by you in the user's language.

## Repeated-correction groups
- Apply the decision procedure in `criteria.md` §5 in order (shared cause, merging, normal iteration, fixes, status).
- **Kept group:** its `fix` and `copy` state the specific rule from §5 step 1 (it passes the paste test: it names
  what to check in this bot's domain). The skeleton leaves `fix` as `TODO` where its only default would be generic.
- **Dropped group:** delete the finding. If that group was the only reason for Needs work, set the bot to Fine and name
  the §5 reason in `why`.
- **`fix_check`:** ids of candidates (`{id, ts, incidents_after, active_days_after}`); their texts are in the bot's
  `fix_candidates` list, once per bot. Most memory saves are about something else (an email address, a schedule).
  Decide which candidates, if any, are about this group's problem; then the **latest** of those decides:
  - `incidents_after` = 0 and `active_days_after` ≥ 2: fixed. Delete the finding and add one line to `improving` (what
    was fixed, and when), even if an earlier fix had failed.
  - `incidents_after` = 0 and `active_days_after` < 2: too early to tell. Keep the finding as if unfixed, set
    `"too_early": true` (the report tags it with `ui.too_early`, e.g. "Too early to tell") and say in `fix` when the
    rule was saved, for example "A rule was saved on 10/16; the next check will show whether it holds."
  - `incidents_after` ≥ 1: came back. Keep the finding, add "came back after a fix" to `score.basis` and raise
    `score.impact` by 1 (max 3). The `copy` must not repeat the rule that already failed; make it more specific.
  - None is about this problem: ignore them.
  - `fix_check_omitted` means more saves exist than are listed (none had an incident after it). If none of the listed
    ones fits, look for the rest in `$W/timelines/<id>.json` (events with `kind` `memory_write`) in that time span.
  - Then delete `fix_check` (finalize `--strict` refuses a draft that still has one). finalize drops `fix_candidates`.

## Status
The suggested status comes from `criteria.md` §2; change it only for a reason listed in §5 step 5, named in `why` in
one sentence.
- **Fine bots:** `issue` is a neutral 2-6 word line ("Working well", "Nothing repeating"). Not a problem statement:
  a small proposal (for example, an empty description) still belongs in the findings, not in the issue column.
- **Clean-up bots:** one finding (`"cleanup": true`) says why (usage facts); fold any other finding of that bot into it,
  since the only thing offered is "Show me how to clean up X". It may be in the top 3 like any finding (by value),
  labelled with the clean-up wording. The shared description item skips clean-up bots on purpose: no text is written
  for a bot you suggest removing. The fleet keep / clean-up item explains how; don't repeat
  the how in each bot. No `copy` unless the bot's job should move to another bot: then `copy` is the text for that
  other bot, with `copy_kind` `description` or `memory`.

## Words
- `copy` is pasted into a bot, so write it in the language the user uses with that bot (it may differ from the report).
- Description for an empty-description bot: 1-2 sentences, under about 200 characters: what the bot does for this user
  and how they like it done, taken from how they actually use it. No promises the bot can't keep.
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
- Placeholder text: every English string the skeleton wrote is recorded (lines made only of bot names are not); when the report language isn't English,
  finalize `--strict` lists any left unchanged (including `ui` labels).
- Fleet section: the keep / clean-up item already says nothing is deleted automatically and how to clean up; don't
  repeat it in other items.
- The keep / clean-up item (`"keep": true`): reword it in the user's language. If every bot is kept, one short line
  and a `fix` that says nothing needs cleaning up (no delete steps); with no other fleet item the report shows it as one
  compact line, not a numbered item.
- Evidence lines with no date (`"date": ""`): the report drops the date column when no line of that item has a date.
- The opening sentence (`ui.lede_*`) is also the first sentence of your chat message; keep them the same.

## Quotes
- `quote.orig` is word for word.
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

## Leads and other items
- `leads` may stay in the draft; finalize drops it. Use it as a checklist.
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
- **Stale memory:** a finding only if later chats contradict the fact, or the fact has clearly expired (for example, a
  past date). "Currently" alone isn't enough.
- **Skipped questions:** one or two mean nothing. Several of the same kind from one bot (it keeps asking which next
  step, or for permission it didn't need) can justify a rule like "go ahead with the recommended option and say what
  you did".
- **Shared causes:** one fleet item; each bot points to it with `"see": "fleet-N"`. When each bot needs its own text,
  `copy` is a list of `{"bot", "text"}`.
- **No proposals at all:** the report hides the top-3 section. In the chat, say in one line that there is nothing to
  do, skip the multi-select, and only offer the weekly re-check.

## Chat message and options (SKILL.md steps 8-9)
- The fixed strings in SKILL.md and these references ("Show me how to clean up X", "None for now", "Nothing major to
  fix.") are examples of meaning, not text to copy: write them in the user's language, like every other word.
- Option order: the top 3 in their order, then every other proposal in report order (bot sections top to bottom, each
  bot's findings in order, then the fleet items). A clean-up bot has one option ("show me how to clean up X"): at its
  top-3 place if one of its findings is there, otherwise at its bot's place in report order. "None for now" is last.
- Never label an option remove, delete or merge, in any language.
