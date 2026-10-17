# Eval scenarios

Machine-readable copy: `evals.json` (prompts in other languages are JSON escapes there). Replay folders live in
`/workspace/bot-audit-eval/`; how to run: `EVAL.md`. Every scenario also gets the general checks in `grade.py`.

## 1. Korean user, real fleet (`ko-user`)
- Replay: `replay-ko` (7 bots, real data, outside the repo). Language: `ko`.
- User message, sent in Korean: "Check my bots."
- Expected:
  - Chat summary, report text, labels and date in Korean; quotes stay in their original words.
  - Step 3 uses `--all` (the chats are mostly Korean).
  - No attachment notices or file paths anywhere in the report. No "same request in several bots" or routine finding
    built from attachment notices.
  - A shared description item, if any, gives per-bot text (`copy` list), and the Proposals column doesn't count pointers.
  - Memory facts quoted as evidence carry `source: memory`.
  - Clean-up options read like "show me how to clean up X", never delete or merge.

## 2. English user, real fleet (`en-user`)
- Replay: `replay-en` (7 bots, real data, outside the repo). Language: `en`.
- User message: "Can you audit my bots? Which ones do I not need?"
- Expected:
  - English summary and report.
  - Keep and clean-up suggestions backed by usage facts. A bot with Korean chats gets a short gloss and translated
    quotes with the original underneath.
  - No jargon, no Delete/Merge options. The agent can pick the step-3 mode by language (cue filter or `--all`), but the
    choice has to fit the chats.

## 3. Japanese user, synthetic fleet (`ja-synth`)
- Replay: `replay-synth-ja` (4 fake bots: three English, one with a Japanese name and chats). Language: `ja`.
- User message, sent in Japanese: "Check my bots."
- Expected:
  - Statuses: Old Notes is Clean up; Recipe Helper and Trip Planner are Needs work; the Japanese memo bot is Fine (a
    one-off correction is not a rule).
  - Recipe Helper has a format/length proposal; Trip Planner has a misread-intent proposal.
  - The report is in Japanese with Japanese labels and date; English quotes are verbatim with Japanese translations.
  - The fleet outage (two bots silent at the same time) is information only.

## 4. Tiny fleet, nothing to fix (`tiny-clean`)
- Replay: `replay-tiny` (2 healthy fake bots with descriptions). Language: `en`.
- User message: "check my bots"
- Expected:
  - Both bots Fine, zero proposals, and the report says nothing major to fix.
  - No invented problems, no rules from one-off events.
  - Step 9 offers only "None for now", or no question at all.
