# Findings JSON (schema 3)

`build_findings.py skeleton` writes `findings_draft.json`; you edit it, then `build_findings.py finalize` checks it and writes
`findings.json`, which `make_report.py` renders. Any text field can be a plain string or `{"en": "...", "ko": "..."}`.
The report falls back to the other language when one is missing, so write at least the report language (English by default).

```jsonc
{
  "schema": 3,
  "title": {"en": "Bot audit report", "ko": "봇 점검 리포트"},
  "date": "YYYY-MM-DD",
  "bots": [
    {
      "id": "<agent id>",            // used for anchors and refs ("<id>-<n>")
      "name": "Recipe Helper",       // the bot's name exactly as in its profile
      "gloss": {"en": "recipes"},    // optional short English gloss for non-English names
      "status": "green|yellow|red",  // Fine | Needs work | Clean up (references/criteria.md §2)
      "issue": {"en": "Answers run long"},         // 2–6 words, shown in the status table
      "why":   {"en": "The same correction keeps coming back."},  // one sentence: why this status
      "improving": [{"en": "Tone: no complaints since it saved a rule on 03/02"}],  // optional; fixed groups
      "findings": [ /* Finding, at most 3 scored ones after finalize */ ],
      "more": [ /* Finding, filled by finalize from the overflow */ ]
    }
  ],
  "fleet": [ /* Finding: shared root causes, outage info, keep/remove summary */ ],
  "top3": [{"text": {"en": "Recipe Helper: keep answers to the steps"}, "ref": "<id>-1"}]  // set by finalize
}
```

## Finding
```jsonc
{
  "title": {"en": "Format and length fixes keep coming up"},
  "now": [                                   // evidence, oldest first
    {"date": "03/01", "quote": {"orig": "Too long. Just give me the steps, no history", "ko": "너무 길어요. 단계만 주세요"}},
    {"date": "03/03", "who": {"en": "Bot", "ko": "봇"}, "quote": {"orig": "From now on I will keep recipes short."}},
    {"date": "", "text": {"en": "Last request 03/08"}}   // plain fact, not a quote
  ],
  "fix":  {"en": "Save the format you want as a default."},
  "copy": {"en": "Recipes: list the steps only. No history or stories."},   // text the user pastes; optional
  "copy_kind": "memory|description|routine",
  "score": {"impact": 3, "confidence": "high", "effort": 1, "reversibility": 1.0, "basis": "3 incidents on 3 days"},
  "short": {"en": "Recipe Helper: steps only"},   // optional short line for the top 3
  "see": "fleet-1",          // optional: this bot's evidence for a shared fleet item (no Apply box, no score)
  "info": true,              // optional: information only (no Apply box, no score)
  "needs_review": true       // set by skeleton; remove after you rewrite the text
}
```

## Rules finalize enforces
- `status` is one of green / yellow / red.
- Every `quote.orig` must appear word for word (whitespace aside) in the saved chats, the memory block, or a bot's name or description.
  Use "…" to skip words inside a quote; each piece is checked on its own. Translations go in `en` / `ko`, never in `orig`.
- With `--strict`, no `needs_review` flags or `TODO` text may remain.
- Scores become `value`; at most 3 scored findings per bot stay in `findings`, and the rest move to `more`. `top3` is chosen by value
  unless you set `"top3_locked": true` with your own `top3`.
