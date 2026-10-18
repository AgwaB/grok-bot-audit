# Findings JSON (schema 3)

`build_findings.py skeleton` writes `findings_draft.json` (a frame: one row per bot with `TODO`, no findings); you fill it, then `build_findings.py finalize` checks it and writes
`findings.json`, which `make_report.py` renders.

The scripts fix the structure; every word the reader sees comes from this file, written by you in the user's language.
- `lang`: BCP 47 code of the report language. It becomes the HTML `lang` attribute (the browser picks matching quotation marks).
- Text fields are plain strings. `date_label` is the report date as the reader would write it (fallback: `date`).
- Optional `fonts`: `{"sans": "<CSS font list>", "serif": "<CSS font list>"}` replaces the default system stacks.
- `ui`: the report's own labels. The skeleton fills it with the English fallback (`UI_DEFAULT` in `make_report.py`);
  rewrite the values, keep each `{placeholder}`. Keys you delete fall back to English.

```jsonc
{
  "schema": 3,
  "lang": "en",
  "title": "Bot audit report",
  "date": "YYYY-MM-DD",
  "date_label": "March 11, 2030",
  "ui": { "glance": "At a glance", "st": {"red": "Clean up", "yellow": "Needs work", "green": "Fine"} },
  "bots": [
    {
      "id": "<agent id>",            // used for anchors and refs ("<id>-<n>")
      "name": "Garden Helper",       // the bot's name exactly as in its profile
      "gloss": "garden",            // optional short gloss when the name is in another language than the report
      "status": "green|yellow|red",  // Fine | Needs work | Clean up (references/criteria.md §2)
      "issue": "Advice ignores the light",   // 2–6 words, shown in the status table
      "why": "The same correction keeps coming back.",   // one sentence: why this status
      "improving": ["Watering: no complaints since it saved a rule on 03/02"],  // optional; fixed groups
      "findings": [ /* Finding, at most 3 scored ones after finalize */ ],
      "more": [ /* Finding, filled by finalize from the overflow */ ]
    }
  ],
  "fleet": [ /* Finding: shared root causes, outage info, keep/clean-up summary */ ],
  "top3": [{"text": "Garden Helper: ask about light first", "ref": "<id>-1"}]  // set by finalize
}
```

## Finding
```jsonc
{
  "title": "It advises without knowing the light",
  "now": [                                   // evidence, oldest first
    {"date": "03/01", "ref": "a1b2:14", "quote": {"orig": "That fern is in a dark hallway, I told you"}},
    {"date": "03/02", "ref": "a1b2:31", "quote": {"orig": "Il n'y a presque pas de lumière ici", "translation": "There is almost no light here", "lang": "fr"}},
    {"date": "03/03", "ref": "a1b2:32", "who": "bot", "quote": {"orig": "From now on I will ask about light first."}},
    {"date": "02/20", "source": "memory", "quote": {"orig": "The user has a north-facing balcony."}},
    {"date": "", "text": "Last request 03/08"}   // plain fact, not a quote
  ],
  "fix":  "Pick this and a rule is saved to its memory.",
  "copy": "Before advising on a plant, ask how much light it gets.",   // text for the bot; optional
  // or, when one item needs different text per bot (a shared fleet item):
  // "copy": [{"bot": "Print Desk", "text": "Orders prints…"}, {"bot": "Bill Tracker", "text": "Tracks bills…"}],
  "copy_kind": "memory|description|routine|group|other",   // memory: text the user sends that bot to remember
  "score": {"impact": 3, "confidence": "high", "effort": 1, "reversibility": 1.0, "basis": "3 incidents on 3 days"},
             // "basis" is an internal note for scores.md, never shown in the report; any language is fine
  "short": "Garden Helper: ask about light",   // optional short line for the top 3
  "see": "fleet-1",          // optional: this bot's evidence for a shared fleet item (no Apply box, no score)
  "info": true,              // optional: information only (no Apply box, no score)
  "kind": "follow_up",       // optional: job_text, follow_up, or a setup kind (setup.md)
  "too_early": true,         // optional: a fix was saved too recently to judge; shown with ui.too_early
  "keep": true,              // the fleet keep / clean-up item (in the skeleton); alone in an all-kept fleet it renders
                             // as one compact line (no number, no box)
  "cleanup": true,           // exactly one on each clean-up bot: its one option is "Show me how to clean up X"
  "lessons": [{"topic": "format_length", "title": "…", "now": [ … ], "copy": ""}]
             // optional, clean-up item only: that bot's repeated corrections, shown as "if you come back to it" with
             // each copy as a rule to save first; write copy in the chat's language or delete; finalize drops empty ones
}
```

## Evidence lines
- `ref` is a message id (`<bot prefix>:<i>`, from diag.json, the judge list or the digest). Every finding except the
  keep item needs at least one line with a `ref`; a quote on a line with a `ref` must be in that message.
- One line holds either `quote` (words from a source) or `text` (a plain fact), never both.
- `who` (optional) is the speaker shown before the quote, when it isn't the user in this bot's own chat. The value
  `"bot"` is a keyword, not text: the quote is this bot's own words, and the report shows `ui.who_bot` (default: the
  bot's name). Any other value is shown as written, so write a bot's name (as in a fleet item) or a word in the report
  language. A fleet item has no bot of its own: `"bot"` there is an error; name the bot.
- `chat` (optional) is a bot name: the quote is the user's, from that bot's chat. Shown as `ui.in_chat` ("You (in X)").
- `date` is the message date, written one way throughout the report (for example `MM/DD`, or as the reader writes dates).

## Quotes
- `orig` is the exact original words, in whatever language the chat was in. Never translate inside `orig`.
- `translation` (optional) is the quote in the report language, for chats in another language. The report shows it on the
  main line and the original underneath in smaller type.
- `lang` (optional) is the BCP 47 code of `orig`.
- `source` (optional, on the evidence line): `chat` (default), `memory` (a memory fact or a memory save) or `description`
  (a bot's description). The report labels memory and description quotes as such (`ui.src`); finalize checks the quote
  against that source only.
- Never quote file paths or the app's attachment notices ("The user attached a file…"). They are stripped from the chats,
  and finalize rejects any quote that contains them.

## Counts and pointers
The status table counts real proposals per bot. A pointer (`see`) to a shared fleet item is not counted; the table shows
it as a separate small link (`ui.n_see`). Info items are not counted either. `ui.n_items` (`{n}`) formats the count
only when it is 1 or more: a bot with no proposals shows no "0", just a dash (or only the `n_see` link when it has a
pointer), so `n_items` never needs a zero form.

## UI labels (`ui`)
Keys and English defaults are in `UI_DEFAULT` in `scripts/make_report.py`: section titles (`glance`, `top`, `bybot`, `fleet`),
table headers (`th`, a list of 4), status names (`st`), copy-box labels (`kind`), buttons and messages, and `footer`.
Opening sentence: `lede_all` (some need work and some clean-up), `lede_y` (only need work), `lede_r` (only clean-up),
`lede_none` (nothing to fix), picked from the final statuses; make_report writes the rendered one to `report/lede.txt`.
Write the one that will be used as a whole sentence that fits the real counts (singular or plural as your language
needs; you may write the numbers in instead of `{n}`, `{y}`, `{r}`). The English fallbacks are count-neutral lists.
`footer` is the base line (`{date}`); `footer_q` (quotes are word for word) is appended only when the report has a quote,
and `footer_tr` only when a translated quote exists. `expand` (`{n}` = proposals, as in the table) labels a collapsed
section; `expand_info` replaces it when the section has no proposals. `in_chat` labels a user quote from another bot's
chat (`{bot}`); `who_bot` labels a quote with `"who": "bot"` (`{bot}`); `too_early` tags a finding with
`"too_early": true`. `fleet_note` (default `""`) is an optional sentence shown above the fleet items; leave it empty
unless something about the fleet as a whole is worth saying that no fleet item says. Empty shows nothing and needs no
translation.

## Rules finalize enforces
- Every bot in diag.json has a row; `status` is one of green / yellow / red (the skeleton's `TODO` is an error).
- A bot with `user_keep` is never red and has no clean-up item; a red bot has exactly one `"cleanup": true` finding,
  and only red bots have one.
- Every finding except the keep item cites at least one real message (`ref`); a quote with a `ref` is checked
  against that message.
- Every `quote.orig` must appear word for word (whitespace aside) in its `source`: the saved chats, the memory, or a bot's
  name or description. No file paths or app notices.
- `copy` is a string or a list of `{"bot", "text"}`.
- An evidence line with both `quote` and `text` is an error.
- A line made only of bot names and punctuation is never treated as placeholder text.
- With `--strict`: `date_label` has no `TODO`. When `lang` is not English, any visible text
  still equal to the skeleton's English placeholder (recorded in `_skeleton`), and any `ui` label equal to its English
  default, is a warning. finalize removes `_skeleton`.
- Use "…" to skip words inside a quote; each piece is checked on its own.
- With `--strict`, no `needs_review` flags or `TODO` text may remain.
- Scores become `value`; at most 3 scored findings per bot stay in `findings`, and the rest move to `more`. `top3` is chosen by value
  unless you set `"top3_locked": true` with your own `top3`.
