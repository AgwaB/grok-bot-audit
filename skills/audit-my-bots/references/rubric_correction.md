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
- `topic` is null when `label` is false.
- `evidence` quotes the few words (from `user` or `next_bot`) that decided it. Never copy secrets (codes, keys,
  passwords) into it.
- Record verdicts as TSV lines `n<TAB>type<TAB>topic<TAB>confidence<TAB>evidence` and run `judge_inputs.py --label`
  (SKILL.md step 4).

## Types
| type | meaning | label |
|---|---|---|
| correction | The user objects to, or changes, something the bot **just produced or did**, or restates a rule the bot broke. This includes criticism ("too long"), a fix ("drop the intro"), catching an error ("that's the wrong logo"), saying the bot misunderstood ("I meant X"), and rejecting an item **with a reason or a criterion** ("already covered that", "too basic"). | true |
| topic_rejection | Rejects an offered item and asks for another **without** saying why ("next", "something else"). | false |
| new_request | A new task, or a change to the last answer **without criticising it** ("summarise it in 3 lines"). A format spec inside a new request is still a new request. | false |
| question | Asks for information, a fact check or an explanation ("is that right?"). | false |
| clarification | Answers the bot's question, picks an option it offered, or gives info it asked for. | false |
| preference | A standing wish **without objecting** to the last output ("also include the link next time"). Not a correction, but keep it: preferences are memory candidates. | false |
| other | Thanks, approval, small talk. | false |

## Decision steps (stop at the first that applies)
1. Is the user answering a question the bot asked, or choosing among options it offered? → `clarification`.
2. Does the user say or clearly imply the bot got something wrong? Look for criticism words (too, not, wrong, again, or the same words in the chat's language), "instead of X" or "not X" plus a reason, "I meant / I asked for", "already did that", or counter-evidence ("it has 3,000 stars though?"). → `correction`.
3. Is it a challenge phrased as a question ("really? none of it works?", "is that all?", "did you actually check?")? → `correction` **only if** it states the bot is wrong, or `next_bot` admits an error or a gap ("I was wrong", "I made that too strict", "probably not all"). Otherwise → `question`.
4. Does the user reject an item with no reason? → `topic_rejection`.
5. Does the user ask to change the last output (shorter, simpler, another style) without criticism? → `new_request`.
6. Is it a lasting wish ("from now on", "by default") with no objection to the last output? → `preference`. With an objection, go back to step 2.
7. Otherwise → the non-correction type that fits best.

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
- prev: a 12-step recipe with history · user: "Too long. Just the steps." → correction / format_length / high
- prev: a list of topics · user: "I already wrote about the second one. Another." → correction / repeated_content / high
- prev: a summary · user: "It has 3,000 stars though?" · next: "You're right, I misread it." → correction / accuracy_sources / high
- prev: hotel options · user: "That's not what I asked, I meant a hostel" → correction / misread_intent / high
- prev: a long summary · user: "Demasiado largo. En una línea, por favor" → correction / format_length / high
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
- A **repeated correction** is the same bot and topic in 2 or more incidents on 2 or more days, or 3 or more incidents. Only repeated corrections can become proposals; one-off mistakes never become rules.
