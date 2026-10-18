# Correction judge rubric

Use this for every item in `judge_inputs.json`. You judge ONE user message: is the user **correcting the bot**?
The answer feeds the search for repeated corrections, which become proposals for a bot's description or memory.
Judge only from the three excerpts. Do not guess what happened outside them. Work in the language of the chat.

## Input (one item)
```
request:  the user's message that started this exchange (context only; may be empty)
prev_bot: the bot's last message before the user's message (may be cut), plus any question cards
user:     the user's message
next_bot: the bot's reply after it (may be empty if it never answered)
```

## Output (one entry in labels.json, keyed by the item's "key")
```json
{"label": true,
 "type": "correction",
 "topic": "format_length",
 "confidence": "high",
 "evidence": "\"too long again\""}
```
- `label` is true **only** when `type` is `correction`.
- `topic` is set for corrections and preferences, null otherwise.
- `evidence` quotes the few words (from `user` or `next_bot`) that decided it. Never copy secrets (codes, keys,
  passwords) into it.
- `fix_promised` (optional) is true when `next_bot` promises a lasting change ("from now on I'll…", in any language).
- `promise_later` (optional) is true when `next_bot` promises to do or send something later on its own ("I'll send it
  when it's ready", in any language). diagnostics lists these as promise leads; you then read whether it was delivered.

## Recording verdicts (labels.tsv)
One line per **correction, preference, keep or ack** (and any item whose reply promises something later); every other
item needs no line and is recorded as type `none`. Items marked `[check: last]` (the bot's last 3 user messages) and
`[check: repeat N days]` (one example of a message sent on 3+ days) are listed after the others; read them for `keep`
and `ack`. Seven
tab-separated columns, `\N` or `-` for an empty cell:

| column | value |
|---|---|
| n | the item number from `--list` |
| type | `correction`, `preference`, `keep` or `ack` (any type from the table below is accepted) |
| topic | one of the fixed topics below |
| confidence | `high`, `medium` or `low` |
| evidence | a few words copied from `user` (or `next_bot`), no quote marks needed, never a secret |
| promised | `yes` if `next_bot` promises a lasting change; `later` if it promises to do or send something later; else empty |
| user_start | the first 5–10 characters of `user`, copied; `--label` refuses the line if they don't match the item |

Example: `17<TAB>correction<TAB>format_length<TAB>high<TAB>too long again<TAB>yes<TAB>Too long`
Work in batches (SKILL.md step 4): `--list --short --from N` prints about 10 KB of items (fewer items for long
messages or non-Latin scripts) and ends with the next `--from`; append that batch's lines, run `--label`, check the
echo, then the next batch. Each run rewrites `labels.json` from the whole file. A refused line (unknown item or type,
or a `user_start` mismatch) must be fixed before going on. No corrections or preferences at all: an empty file, and
`--label` still runs (every item becomes `none`).

## Types
| type | meaning | label |
|---|---|---|
| correction | The user objects to, or changes, something the bot **just produced or did**, or restates a rule the bot broke. This includes criticism ("too long"), a fix ("drop the intro"), catching an error ("that's the wrong logo"), saying the bot misunderstood ("I meant X"), and rejecting an item **with a reason or a criterion** ("already covered that", "too basic"). | true |
| topic_rejection | Rejects an offered item and asks for another **without** saying why ("next", "something else"). | false |
| new_request | A new task, or a change to the last answer **without criticising it** ("summarise it in 3 lines"). A format spec inside a new request is still a new request. | false |
| question | Asks for information, a fact check or an explanation ("is that right?"). | false |
| clarification | Answers the bot's question, picks an option it offered, or gives info it asked for. | false |
| preference | A standing wish **without objecting** to the last output ("also include the link next time"). Not a correction, but keep it: preferences are memory candidates. | false |
| keep | The user says to keep this bot, or that it is paused or unused on purpose (for a season, until a date, as a backup), in any language. The bot is then never a clean-up candidate. | false |
| ack | The message **only** thanks, approves or acknowledges ("thanks, that works", "ok, got it", in any language), with no new request. Similar messages on many days are then not counted as a repeated request. | false |
| other | Small talk, anything else. | false |

## Decision steps (stop at the first that applies)
1. Is the user answering a question the bot asked, or choosing among options it offered? → `clarification`.
2. Does the user say or clearly imply the bot got something wrong? Look for criticism words (too, not, wrong, again, or the same words in the chat's language), "instead of X" or "not X" plus a reason, "I meant / I asked for", "already did that", or counter-evidence ("it has 3,000 stars though?"). → `correction`.
3. Is it a challenge phrased as a question ("really? none of it works?", "is that all?", "did you actually check?")? → `correction` **only if** it states the bot is wrong, or `next_bot` admits an error or a gap ("I was wrong", "I made that too strict", "probably not all"). Otherwise → `question`.
4. Does the user reject an item with no reason? → `topic_rejection`.
5. Does the user ask to change the last output (shorter, simpler, another style) without criticism? → `new_request`.
6. Is it a lasting wish ("from now on", "by default") with no objection to the last output? → `preference`. With an objection, go back to step 2.
7. Otherwise → the non-correction type that fits best.

More rules:
- Asking before an irreversible step is not a correction of the bot, and the bot asking first is not a problem.
- A complaint typed while answering a question card counts as a correction if it criticises earlier output.
- The bot admitting a mistake on its own, with no objection from the user, is not a correction (no user message to label).

A long pasted draft or brief (over ~300 characters, or a numbered outline) is a `new_request` unless the message, anywhere
in it (often after the pasted part), criticises the bot's previous output; then judge it from step 2.
`prev_bot` may end with `[question card: …]`: a choice the app showed the user. Answering or skipping it is a
`clarification`, not a correction. `request` is the user's message that started the exchange, for context.

## Fixed topics (use exactly these)
| topic | covers |
|---|---|
| tone_style | wording, sentence endings, voice, punctuation, plain words |
| format_length | structure, length, layout, visual composition, how much to show at once |
| scope_selection | which topics or items to pick; filters and criteria |
| accuracy_sources | factual errors, sources, faithfulness to the original, wrong logos or names |
| misread_intent | the bot understood the request differently |
| repeated_content | already covered, duplicates, stale or ended items |
| method_choice | how the bot did it: approach, account, where to save, make new vs use the original |
| depth_completeness | did less than asked; missing parts; incomplete list |
| missing_context | the output was wrong because the bot lacked a fact about the user's situation |
| other | none of the above |

Pick the topic of the **main** objection. If two fit, prefer the one a written rule could fix.

## Confidence
- **high**: explicit criticism or an explicit "you misunderstood", or the bot's reply admits it.
- **medium**: the change is clear but there is no criticism word, or a challenge question the bot partly admits.
- **low**: could reasonably be a plain follow-up. Low-confidence corrections never start a proposal on their own.

## Examples (invented, for illustration)
Corrections (label true):
- prev: a five-paragraph product blurb · user: "Too long. Two sentences max." → correction / format_length / high
- prev: a list of topics · user: "I already wrote about the second one. Another." → correction / repeated_content / high
- prev: a summary · user: "It has 3,000 stars though?" · next: "You're right, I misread it." → correction / accuracy_sources / high
- prev: a quote for 500 flyers · user: "That's not what I asked, I meant 50 posters" → correction / misread_intent / high
- prev: a cover letter · user: "Zu förmlich, bitte lockerer" (too formal, more relaxed please) → correction / tone_style / high
- prev: paid tools · user: "Not paid APIs, set up something free" → correction / method_choice / medium

Not corrections (label false):
- "something else" → topic_rejection
- "summarise it in 3 lines" after a long answer → new_request
- "is that claim actually true?" → question
- "also give me the link from now on" → preference
- "is there really no way to use my own login?" · next: "There is, but…" → question (the bot does not admit an error)
- "June" after "Which month?" → clarification

## After judging (done by diagnostics.py, not by you)
- Corrections on the same topic in the same bot within 60 minutes are one **incident** (one exchange).
- A **repeated correction** is the same bot and topic in 2 or more incidents on 2 or more separate occasions (more than 6
  hours apart). Only repeated corrections can become correction proposals; one-off mistakes never become rules. A
  `preference` (a standing wish the user stated) is the exception: it may become a memory proposal on its own.
