# Findings JSON (schema 3)

`build_findings.py skeleton` writes `findings_draft.json`; you edit it, then `build_findings.py finalize` checks it and writes
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
      "name": "Recipe Helper",       // the bot's name exactly as in its profile
      "gloss": "recipes",            // optional short gloss when the name is in another language than the report
      "status": "green|yellow|red",  // Fine | Needs work | Clean up (references/criteria.md §2)
      "issue": "Answers run long",   // 2–6 words, shown in the status table
      "why": "The same correction keeps coming back.",   // one sentence: why this status
      "improving": ["Tone: no complaints since it saved a rule on 03/02"],  // optional; fixed groups
      "findings": [ /* Finding, at most 3 scored ones after finalize */ ],
      "more": [ /* Finding, filled by finalize from the overflow */ ]
    }
  ],
  "fleet": [ /* Finding: shared root causes, outage info, keep/clean-up summary */ ],
  "top3": [{"text": "Recipe Helper: keep answers to the steps", "ref": "<id>-1"}]  // set by finalize
}
```

## Finding
```jsonc
{
  "title": "Format and length fixes keep coming up",
  "now": [                                   // evidence, oldest first
    {"date": "03/01", "quote": {"orig": "Too long. Just give me the steps, no history"}},
    {"date": "03/02", "quote": {"orig": "Demasiado largo, solo los pasos", "translation": "Too long, just the steps", "lang": "es"}},
    {"date": "03/03", "who": "Bot", "quote": {"orig": "From now on I will keep recipes short."}},
    {"date": "02/20", "source": "memory", "quote": {"orig": "The user currently cooks for two people."}},
    {"date": "", "text": "Last request 03/08"}   // plain fact, not a quote
  ],
  "fix":  "Save the format you want as a default.",
  "copy": "Recipes: list the steps only. No history or stories.",   // text the user pastes; optional
  // or, when one item needs different text per bot (a shared fleet item):
  // "copy": [{"bot": "Trip Planner", "text": "Plans trips…"}, {"bot": "Old Notes", "text": "Keeps notes…"}],
  "copy_kind": "memory|description|routine",
  "score": {"impact": 3, "confidence": "high", "effort": 1, "reversibility": 1.0, "basis": "3 incidents on 3 days"},
  "short": "Recipe Helper: steps only",   // optional short line for the top 3
  "see": "fleet-1",          // optional: this bot's evidence for a shared fleet item (no Apply box, no score)
  "info": true,              // optional: information only (no Apply box, no score)
  "needs_review": true,      // set by skeleton; remove after you rewrite the text
  "fix_check": [{"id": "fx-3", "ts": "…", "incidents_after": 1, "active_days_after": 3}],
             // set by skeleton: unverified fix candidates (texts in the bot's "fix_candidates"); resolve, then delete
  "too_early": true,         // optional: a fix was saved too recently to judge; shown with ui.too_early
  "cleanup": true            // set by skeleton on a clean-up bot's finding: its one option is "Show me how to clean up X"
}
```

## Evidence lines
- One line holds either `quote` (words from a source) or `text` (a plain fact), never both.
- `who` (optional) is the speaker shown before the quote, when it isn't the user in this bot's own chat: "Bot", or
  another bot's name in a fleet item.
- `chat` (optional) is a bot name: the quote is the user's, from that bot's chat. Shown as `ui.in_chat` ("You (in X)").
- `date` is `MM/DD` from the skeleton; you may localise it, with one format throughout.

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
it as a separate small link (`ui.n_see`). Info items are not counted either.

## UI labels (`ui`)
Keys and English defaults are in `UI_DEFAULT` in `scripts/make_report.py`: section titles (`glance`, `top`, `bybot`, `fleet`),
table headers (`th`, a list of 4), status names (`st`), copy-box labels (`kind`), buttons and messages, and `footer`.
Opening sentence: `lede_all` (some need work and some clean-up), `lede_y` (only need work), `lede_r` (only clean-up),
`lede_none` (nothing to fix); make_report writes the rendered one to `report/lede.txt`. `footer_tr` is appended to
`footer` only when a translated quote exists; `in_chat` labels a user quote from another bot's chat (`{bot}`);
`too_early` tags a finding with `"too_early": true`.

## Rules finalize enforces
- `status` is one of green / yellow / red.
- Every `quote.orig` must appear word for word (whitespace aside) in its `source`: the saved chats, the memory, or a bot's
  name or description. No file paths or app notices.
- `copy` is a string or a list of `{"bot", "text"}`.
- An evidence line with both `quote` and `text` is an error.
- A line made only of bot names and punctuation is never treated as placeholder text.
- With `--strict`: no `fix_check` left, and `date_label` has no `TODO`. When `lang` is not English, any visible text
  still equal to the skeleton's English placeholder (recorded in `_skeleton`), and any `ui` label equal to its English
  default, is a warning. finalize removes `_skeleton`.
- `leads` may stay in the draft; finalize removes it from `findings.json`.
  Use "…" to skip words inside a quote; each piece is checked on its own.
- With `--strict`, no `needs_review` flags or `TODO` text may remain.
- Scores become `value`; at most 3 scored findings per bot stay in `findings`, and the rest move to `more`. `top3` is chosen by value
  unless you set `"top3_locked": true` with your own `top3`.
