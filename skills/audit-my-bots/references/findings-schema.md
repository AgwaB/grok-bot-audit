# Findings JSON (schema 3)

`build_findings.py skeleton` writes `findings_draft.json`; you edit it, then `build_findings.py finalize` checks it and writes
`findings.json`, which `make_report.py` renders.

The report is written in the user's language (the language they write to you in; English when unclear):
- `lang` is the BCP 47 code of that language (`en`, `es`, `ja`, `pt-BR`, ...). It becomes the HTML `lang` attribute.
- Every text field is a plain string in that language.
- `ui` holds the report's own labels in that language. Any key you leave out falls back to the English default in
  `make_report.py` (`UI_DEFAULT`). For a non-English report the skeleton copies all English defaults into `ui`
  and sets `"translate": true`; translate every value, keep each `{placeholder}`, then delete `translate`.

```jsonc
{
  "schema": 3,
  "lang": "en",
  "title": "Bot audit report",
  "date": "YYYY-MM-DD",
  "ui": { "glance": "At a glance", "st": {"red": "Clean up", "yellow": "Needs work", "green": "Fine"}, "date_fmt": "{month} {d}, {y}" },
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
    {"date": "", "text": "Last request 03/08"}   // plain fact, not a quote
  ],
  "fix":  "Save the format you want as a default.",
  "copy": "Recipes: list the steps only. No history or stories.",   // text the user pastes; optional
  "copy_kind": "memory|description|routine",
  "score": {"impact": 3, "confidence": "high", "effort": 1, "reversibility": 1.0, "basis": "3 incidents on 3 days"},
  "short": "Recipe Helper: steps only",   // optional short line for the top 3
  "see": "fleet-1",          // optional: this bot's evidence for a shared fleet item (no Apply box, no score)
  "info": true,              // optional: information only (no Apply box, no score)
  "needs_review": true       // set by skeleton; remove after you rewrite the text
}
```

## Quotes
- `orig` is the exact original words, in whatever language the chat was in. Never translate inside `orig`.
- `translation` is the same quote in the report language. Add it only when the chat language differs from the report
  language. The report shows the translation on the main line and the original underneath in smaller type.
- `lang` (optional) is the BCP 47 code of `orig`.

## UI labels (`ui`)
Keys and English defaults are in `UI_DEFAULT` in `scripts/make_report.py`: section titles (`glance`, `top`, `bybot`, `fleet`),
table headers (`th`, a list of 4), status names (`st`), copy-box labels (`kind`), buttons and messages, `footer`, and
dates (`date_fmt` with `{y}`, `{m}`, `{d}`, `{month}`; `months` as 12 names). `quote_marks` is a pair such as `["“", "”"]`;
use `["", ""]` for none.

## Rules finalize enforces
- `status` is one of green / yellow / red.
- Every `quote.orig` must appear word for word (whitespace aside) in the saved chats, the memory block, or a bot's name or description.
  Use "…" to skip words inside a quote; each piece is checked on its own.
- With `--strict`, no `needs_review` flags, no `TODO` text and no `translate` flag may remain.
- Scores become `value`; at most 3 scored findings per bot stay in `findings`, and the rest move to `more`. `top3` is chosen by value
  unless you set `"top3_locked": true` with your own `top3`.
